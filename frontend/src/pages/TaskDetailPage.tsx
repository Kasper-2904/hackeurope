import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Task: {id}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Task detail with draft viewer, subtasks, and risks — coming in M2-T3.
        </p>
      </CardContent>
    </Card>
  );
}
