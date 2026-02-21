// TaskListPage — Kanban board showing tasks grouped by status.
// Click a card to navigate to the task detail page.

import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { useTasks } from "@/hooks/use-api";
import { TaskStatus } from "@/lib/types";

const columns = [
  { status: TaskStatus.PENDING, label: "Pending" },
  { status: TaskStatus.ASSIGNED, label: "Assigned" },
  { status: TaskStatus.IN_PROGRESS, label: "In Progress" },
  { status: TaskStatus.COMPLETED, label: "Completed" },
  { status: TaskStatus.FAILED, label: "Failed" },
  { status: TaskStatus.CANCELLED, label: "Cancelled" },
];

export default function TaskListPage() {
  const { data: tasks, isLoading } = useTasks();
  const navigate = useNavigate();

  if (isLoading) {
    return <div className="text-sm text-slate-500">Loading tasks...</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Tasks</h2>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {columns.map((col) => {
          const columnTasks = tasks?.filter((t) => t.status === col.status) ?? [];

          return (
            <div
              key={col.status}
              className="flex-shrink-0 w-[260px]"
            >
              {/* Column header */}
              <div className="flex items-center justify-between mb-3 px-1">
                <div className="flex items-center gap-2">
                  <StatusBadge status={col.status} />
                  <span className="text-xs text-slate-500">{columnTasks.length}</span>
                </div>
              </div>

              {/* Column body */}
              <div className="space-y-3 min-h-[200px] rounded-lg bg-slate-50 p-3">
                {columnTasks.length > 0 ? (
                  columnTasks.map((task) => (
                    <Card
                      key={task.id}
                      className="cursor-pointer transition hover:shadow-md hover:border-slate-300"
                      onClick={() => navigate(`/tasks/${task.id}`)}
                    >
                      <CardContent className="p-3 space-y-2">
                        <div className="font-medium text-sm leading-tight">
                          {task.title}
                        </div>
                        {task.description && (
                          <p className="text-xs text-slate-500 line-clamp-2">
                            {task.description}
                          </p>
                        )}
                        <ProgressBar value={task.progress} />
                        {task.assigned_agent_id && (
                          <div className="text-xs text-slate-400">
                            {task.assigned_agent_id}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))
                ) : (
                  <div className="text-xs text-slate-400 text-center py-8">
                    No tasks
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
