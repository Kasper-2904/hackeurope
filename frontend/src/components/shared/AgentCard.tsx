// AgentCard — a card showing an AI agent's name, description,
// category, pricing, and verified status. Clickable.

import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { MarketplaceAgent } from "@/lib/types";

interface AgentCardProps {
  agent: MarketplaceAgent;
}

export function AgentCard({ agent }: AgentCardProps) {
  const navigate = useNavigate();

  return (
    <Card
      className="cursor-pointer transition hover:shadow-md hover:border-slate-300"
      onClick={() => navigate(`/marketplace/${agent.id}`)}
    >
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between">
          <h3 className="font-medium text-sm">{agent.name}</h3>
          {agent.is_verified && (
            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-transparent text-xs">
              Verified
            </Badge>
          )}
        </div>

        {agent.description && (
          <p className="text-xs text-slate-500 line-clamp-2">
            {agent.description}
          </p>
        )}

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-slate-100 text-slate-600 border-transparent text-xs">
            {agent.category.replace("_", " ")}
          </Badge>
          <Badge
            variant="outline"
            className={`border-transparent text-xs ${
              agent.pricing_type === "free"
                ? "bg-green-50 text-green-700"
                : "bg-amber-50 text-amber-700"
            }`}
          >
            {agent.pricing_type === "free"
              ? "Free"
              : `$${agent.price_per_use?.toFixed(2)}/use`}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}
