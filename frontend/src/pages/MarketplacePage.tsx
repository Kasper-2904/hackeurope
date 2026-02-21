// MarketplacePage — browse AI agents in a card grid with search,
// category filter, and a publish agent dialog.

import { useState } from "react";
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

const categoryOptions = [
  { value: "all", label: "All Categories" },
  { value: "code_generation", label: "Code Generation" },
  { value: "testing", label: "Testing" },
  { value: "code_review", label: "Code Review" },
];

export default function MarketplacePage() {
  const { data: agents, isLoading } = useMarketplaceCatalog();
  const publishMutation = usePublishAgent();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);

  // Publish form state
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("code_generation");
  const [formDescription, setFormDescription] = useState("");
  const [formPricing, setFormPricing] = useState("free");
  const [formPrice, setFormPrice] = useState("");

  const filtered = agents?.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === "all" || a.category === category;
    return matchesSearch && matchesCategory;
  });

  function handlePublish() {
    if (!formName.trim()) return;
    publishMutation.mutate(
      {
        name: formName,
        category: formCategory,
        description: formDescription,
        pricing_type: formPricing,
        price_per_use: formPricing === "usage_based" ? parseFloat(formPrice) || 0 : null,
      },
      {
        onSuccess: () => {
          setDialogOpen(false);
          setFormName("");
          setFormCategory("code_generation");
          setFormDescription("");
          setFormPricing("free");
          setFormPrice("");
        },
      }
    );
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
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Publish a New Agent</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <Input
                placeholder="Agent name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
              <Select value={formCategory} onValueChange={setFormCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="code_generation">Code Generation</SelectItem>
                  <SelectItem value="testing">Testing</SelectItem>
                  <SelectItem value="code_review">Code Review</SelectItem>
                </SelectContent>
              </Select>
              <Input
                placeholder="Description"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
              />
              <Select value={formPricing} onValueChange={setFormPricing}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free</SelectItem>
                  <SelectItem value="usage_based">Usage Based</SelectItem>
                </SelectContent>
              </Select>
              {formPricing === "usage_based" && (
                <Input
                  placeholder="Price per use (e.g. 0.05)"
                  type="number"
                  step="0.01"
                  value={formPrice}
                  onChange={(e) => setFormPrice(e.target.value)}
                />
              )}
              <Button
                className="w-full"
                onClick={handlePublish}
                disabled={!formName.trim() || publishMutation.isPending}
              >
                {publishMutation.isPending ? "Publishing..." : "Publish"}
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
            <AgentCard key={agent.id} agent={agent} />
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
