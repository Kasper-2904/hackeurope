import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ContextExplorerPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Context Explorer</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Shared context browser and OA/Reviewer explainability — coming in
          M4-T3.
        </p>
      </CardContent>
    </Card>
  );
}
