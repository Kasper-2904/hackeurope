import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { AgentCard } from "@/components/shared/AgentCard";
import { useMarketplaceCatalog, usePublishAgent } from "@/hooks/use-api";
import { useQuery } from "@tanstack/react-query";
import { apiClient, toApiErrorMessage } from "@/lib/apiClient";
import type { Team, Project, MarketplaceAgent, PricingType } from "@/lib/types";

const categoryOptions = [
  { value: "all", label: "All Categories" },
  { value: "Development", label: "Development" },
  { value: "Testing", label: "Testing" },
  { value: "Security", label: "Security" },
  { value: "Research", label: "Research" },
  { value: "DevOps", label: "DevOps" },
  { value: "Frontend", label: "Frontend" },
];

export default function MarketplacePage() {
  const { data: agents, isLoading } = useMarketplaceCatalog();
  const publishMutation = usePublishAgent();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<MarketplaceAgent | null>(null);

  // Teams/Projects for adding agent
  const { data: teams } = useQuery<Team[]>({
    queryKey: ["teams"],
    queryFn: async () => {
      const { data } = await apiClient.get<Team[]>("/teams");
      return data;
    },
  });

  const [selectedTeam, setSelectedTeam] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  // Publish form state
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("Development");
  const [formDescription, setFormDescription] = useState("");
  const [formPricing, setFormPricing] = useState("free");
  const [formPrice, setFormPrice] = useState("");
  const [formEndpoint, setFormEndpoint] = useState("");
  const [formToken, setFormToken] = useState("");
  const [formProvider, setFormProvider] = useState("openai-compatible");
  const [formModel, setFormModel] = useState("");
  const [formSystemPrompt, setFormSystemPrompt] = useState("");
  const [formSkills, setFormSkills] = useState("");
  const [publishMessage, setPublishMessage] = useState<string | null>(null);

  // Handle return from Stripe onboarding
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const onboardingStatus = urlParams.get("onboarding");
    
    if (onboardingStatus === "complete") {
      // User returned from Stripe onboarding, try to restore and publish
      const pendingPublishStr = sessionStorage.getItem("pendingPublish");
      if (pendingPublishStr) {
        try {
          const pendingData = JSON.parse(pendingPublishStr);
          // Restore form fields
          setFormName(pendingData.name || "");
          setFormCategory(pendingData.category || "Development");
          setFormDescription(pendingData.description || "");
          setFormPricing(pendingData.pricing_type || "free");
          setFormPrice(pendingData.price_per_use?.toString() || "");
          setFormProvider(pendingData.inference_provider || "openai-compatible");
          setFormEndpoint(pendingData.inference_endpoint || "");
          setFormToken(pendingData.access_token || "");
          setFormModel(pendingData.inference_model || "");
          setFormSystemPrompt(pendingData.system_prompt || "");
          setFormSkills(pendingData.skills?.join(", ") || "");
          // Open dialog and show message
          setDialogOpen(true);
          setPublishMessage("Stripe setup complete! Click 'Publish Agent' to finish publishing.");
        } catch {
          // Invalid stored data
        }
        // Clear the stored data
        sessionStorage.removeItem("pendingPublish");
      }
      // Clean up URL
      window.history.replaceState({}, "", window.location.pathname);
    } else if (onboardingStatus === "refresh") {
      // User needs to restart onboarding
      setPublishMessage("Stripe setup was not completed. Please try publishing again.");
      sessionStorage.removeItem("pendingPublish");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  // Fetch projects for selected team
  const { data: projects } = useQuery<Project[]>({
    queryKey: ["team-projects", selectedTeam],
    queryFn: async () => {
      if (!selectedTeam) return [];
      const { data } = await apiClient.get<Project[]>(`/teams/${selectedTeam}/projects`);
      return data;
    },
    enabled: Boolean(selectedTeam),
  });

  const filtered = agents?.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === "all" || a.category === category;
    return matchesSearch && matchesCategory;
  });

  function getPublishErrorMessage(error: unknown): string {
    const apiMessage = toApiErrorMessage(error, "Could not publish agent. Please try again.");
    if (apiMessage.toLowerCase().includes("field required")) {
      return "Missing required publish details. Add endpoint URL and API token, then try again.";
    }
    return apiMessage;
  }

  function handlePublish() {
    if (!formName.trim()) {
      setPublishMessage("Agent name is required.");
      return;
    }
    if (!formEndpoint.trim()) {
      setPublishMessage("API endpoint is required.");
      return;
    }
    if (!formToken.trim()) {
      setPublishMessage("API token is required so we can call your agent.");
      return;
    }

    setPublishMessage(null);

    // For paid agents, we need to provide onboarding URLs
    const isPaidAgent = formPricing === "usage_based" && parseFloat(formPrice) > 0;
    const currentUrl = window.location.href;
    const returnUrl = isPaidAgent ? `${currentUrl}?onboarding=complete` : undefined;
    const refreshUrl = isPaidAgent ? `${currentUrl}?onboarding=refresh` : undefined;

    publishMutation.mutate(
      {
        agentData: {
          name: formName.trim(),
          category: formCategory,
          description: formDescription.trim() || undefined,
          pricing_type: formPricing as PricingType,
          price_per_use: formPricing === "usage_based" ? parseFloat(formPrice) || 0 : null,
          inference_provider: formProvider,
          inference_endpoint: formEndpoint.trim(),
          access_token: formToken.trim(),
          inference_model: formModel.trim() || undefined,
          system_prompt: formSystemPrompt.trim() || undefined,
          skills: formSkills.split(",").map((s) => s.trim()).filter(Boolean),
        },
        options: isPaidAgent ? { returnUrl, refreshUrl } : undefined,
      },
      {
        onSuccess: (response) => {
          // Check if onboarding is required (for paid agents without Stripe Connect)
          if (response.onboarding_required && response.onboarding_url) {
            setPublishMessage("Redirecting to Stripe to set up payments...");
            // Store form data in sessionStorage so we can restore after onboarding
            sessionStorage.setItem("pendingPublish", JSON.stringify({
              name: formName.trim(),
              category: formCategory,
              description: formDescription.trim(),
              pricing_type: formPricing,
              price_per_use: formPricing === "usage_based" ? parseFloat(formPrice) || 0 : null,
              inference_provider: formProvider,
              inference_endpoint: formEndpoint.trim(),
              access_token: formToken.trim(),
              inference_model: formModel.trim(),
              system_prompt: formSystemPrompt.trim(),
              skills: formSkills.split(",").map((s) => s.trim()).filter(Boolean),
            }));
            // Redirect to Stripe onboarding
            window.location.href = response.onboarding_url;
            return;
          }
          // Normal success - agent was published
          setDialogOpen(false);
          resetForm();
        },
        onError: (error) => {
          setPublishMessage(getPublishErrorMessage(error));
        },
      }
    );
  }

  function resetForm() {
    setFormName("");
    setFormCategory("Development");
    setFormDescription("");
    setFormPricing("free");
    setFormPrice("");
    setFormEndpoint("");
    setFormToken("");
    setFormProvider("openai-compatible");
    setFormModel("");
    setFormSystemPrompt("");
    setFormSkills("");
    setPublishMessage(null);
  }

  async function handleAddToProject() {
    if (!selectedProject || !selectedAgent) return;
    setAddLoading(true);
    try {
      await apiClient.post(`/projects/${selectedProject}/allowlist/${selectedAgent.agent_id}`);
      setAddDialogOpen(false);
      setSelectedAgent(null);
      setSelectedTeam("");
      setSelectedProject("");
    } catch (error) {
      console.error("Failed to add agent:", error);
    } finally {
      setAddLoading(false);
    }
  }

  function openAddDialog(agent: MarketplaceAgent) {
    setSelectedAgent(agent);
    setAddDialogOpen(true);
  }

  if (isLoading) {
    return <div className="text-sm text-slate-500">Loading marketplace...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Agent Marketplace</h2>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">Publish Agent</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Publish a New Agent</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div>
                <label className="text-sm font-medium text-slate-700">Agent Name *</label>
                <Input
                  placeholder="e.g., Code Reviewer Pro"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700">Category *</label>
                <Select value={formCategory} onValueChange={setFormCategory}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.filter(c => c.value !== "all").map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700">Description</label>
                <Input
                  placeholder="What does this agent do?"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="mt-1"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-700">Pricing *</label>
                  <Select value={formPricing} onValueChange={setFormPricing}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="free">Free</SelectItem>
                      <SelectItem value="usage_based">Usage Based</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {formPricing === "usage_based" && (
                  <div>
                    <label className="text-sm font-medium text-slate-700">Price per use ($)</label>
                    <Input
                      placeholder="0.05"
                      type="number"
                      step="0.01"
                      value={formPrice}
                      onChange={(e) => setFormPrice(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                )}
              </div>

              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-slate-800 mb-3">Agent Configuration</h4>
                
                <div>
                  <label className="text-sm font-medium text-slate-700">API Endpoint *</label>
                  <Input
                    placeholder="https://your-agent.com/v1"
                    value={formEndpoint}
                    onChange={(e) => setFormEndpoint(e.target.value)}
                    className="mt-1"
                  />
                  <p className="text-xs text-slate-500 mt-1">Your agent's OpenAI-compatible API endpoint</p>
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-slate-700">API Token *</label>
                  <Input
                    placeholder="Token for authenticating with your agent"
                    type="password"
                    value={formToken}
                    onChange={(e) => setFormToken(e.target.value)}
                    className="mt-1"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4 mt-3">
                  <div>
                    <label className="text-sm font-medium text-slate-700">Provider</label>
                    <Select value={formProvider} onValueChange={setFormProvider}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai-compatible">OpenAI Compatible</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700">Model</label>
                    <Input
                      placeholder="e.g., gpt-4o"
                      value={formModel}
                      onChange={(e) => setFormModel(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-slate-700">System Prompt</label>
                  <Input
                    placeholder="Instructions for the agent..."
                    value={formSystemPrompt}
                    onChange={(e) => setFormSystemPrompt(e.target.value)}
                    className="mt-1"
                  />
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-slate-700">Skills</label>
                  <Input
                    placeholder="generate_code, review_code, debug_code"
                    value={formSkills}
                    onChange={(e) => setFormSkills(e.target.value)}
                    className="mt-1"
                  />
                  <p className="text-xs text-slate-500 mt-1">Comma-separated list of skills</p>
                </div>
              </div>

              <Button
                className="w-full"
                onClick={handlePublish}
                disabled={!formName.trim() || !formEndpoint.trim() || !formToken.trim() || publishMutation.isPending}
              >
                {publishMutation.isPending ? "Publishing..." : "Publish Agent"}
              </Button>
              {publishMessage && (
                <p className="text-sm text-slate-600" role="status">
                  {publishMessage}
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Add to Project Dialog */}
        <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Agent to Project</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              {selectedAgent && (
                <div className="p-3 bg-slate-50 rounded-lg">
                  <p className="font-medium">{selectedAgent.name}</p>
                  <p className="text-sm text-slate-500">{selectedAgent.description}</p>
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-slate-700">Select Team</label>
                <Select value={selectedTeam} onValueChange={(v: string) => { setSelectedTeam(v); setSelectedProject(""); }}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Choose a team..." />
                  </SelectTrigger>
                  <SelectContent>
                    {teams?.map((team) => (
                      <SelectItem key={team.id} value={team.id}>
                        {team.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedTeam && projects && projects.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-slate-700">Select Project</label>
                  <Select value={selectedProject} onValueChange={setSelectedProject}>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Choose a project..." />
                    </SelectTrigger>
                    <SelectContent>
                      {projects.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {selectedTeam && projects && projects.length === 0 && (
                <p className="text-sm text-slate-500">No projects in this team</p>
              )}

              <Button
                className="w-full"
                onClick={handleAddToProject}
                disabled={!selectedProject || addLoading}
              >
                {addLoading ? "Adding..." : "Add to Project"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search and filter */}
      <div className="flex gap-3">
        <Input
          placeholder="Search agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categoryOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Agent grid */}
      {filtered && filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((agent) => (
            <AgentCard 
              key={agent.id} 
              agent={agent} 
              showAddButton
              onAddClick={() => openAddDialog(agent)}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No agents found
        </div>
      )}
    </div>
  );
}
