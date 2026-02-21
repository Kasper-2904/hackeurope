import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent: {agentId}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Agent detail and capabilities — coming in M3-T3.
        </p>
      </CardContent>
    </Card>
  );
}
