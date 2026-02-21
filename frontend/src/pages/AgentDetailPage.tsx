// AgentDetailPage — shows full details for a marketplace agent.

import { useParams, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMarketplaceAgent } from "@/hooks/use-api";

export default function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const { data: agent, isLoading } = useMarketplaceAgent(agentId!);

  if (isLoading) {
    return <div className="text-sm text-slate-500">Loading agent...</div>;
  }

  if (!agent) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Agent not found</p>
        <Link to="/marketplace" className="text-sky-600 hover:underline text-sm mt-2 inline-block">
          Back to marketplace
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{agent.name}</CardTitle>
            <div className="flex gap-2">
              {agent.is_verified && (
                <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-transparent">
                  Verified
                </Badge>
              )}
              {agent.is_active && (
                <Badge variant="outline" className="bg-green-50 text-green-700 border-transparent">
                  Active
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {agent.description && (
            <p className="text-sm text-slate-600">{agent.description}</p>
          )}

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-slate-500">Category</span>
              <div className="mt-1">
                <Badge variant="outline" className="bg-slate-100 text-slate-600 border-transparent">
                  {agent.category.replace("_", " ")}
                </Badge>
              </div>
            </div>
            <div>
              <span className="text-slate-500">Pricing</span>
              <div className="mt-1">
                <Badge
                  variant="outline"
                  className={`border-transparent ${
                    agent.pricing_type === "free"
                      ? "bg-green-50 text-green-700"
                      : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {agent.pricing_type === "free"
                    ? "Free"
                    : `$${agent.price_per_use?.toFixed(2)} per use`}
                </Badge>
              </div>
            </div>
            <div>
              <span className="text-slate-500">Agent ID</span>
              <div className="mt-1 font-mono text-xs">{agent.agent_id}</div>
            </div>
            <div>
              <span className="text-slate-500">Seller</span>
              <div className="mt-1">{agent.seller_id}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Link to="/marketplace" className="text-sm text-sky-600 hover:underline inline-block">
        Back to marketplace
      </Link>
    </div>
  );
}
