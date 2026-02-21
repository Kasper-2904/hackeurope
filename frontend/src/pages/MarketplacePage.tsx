import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function MarketplacePage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Marketplace</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Browse and publish agents — coming in M3-T3.
        </p>
      </CardContent>
    </Card>
  );
}
