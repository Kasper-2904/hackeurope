import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TaskListPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Tasks</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Task list with filters and actions — coming in M2-T3.
        </p>
      </CardContent>
    </Card>
  );
}
