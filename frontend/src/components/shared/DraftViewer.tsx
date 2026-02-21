// DraftViewer — renders the code/content that an AI agent drafted.
// The draft_content from the backend is a JSON object with:
//   { type: "code", language: "python", code: "..." }
// This component shows it as a formatted code block.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DraftViewerProps {
  content: string | Record<string, unknown> | null;
  generatedAt?: string | null;
  agentId?: string | null;
}

export function DraftViewer({ content, generatedAt, agentId }: DraftViewerProps) {
  if (!content) {
    return (
      <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        No draft generated yet
      </div>
    );
  }

  const language = typeof content === "string" ? "text" : ((content.language as string) ?? "text");
  const code = typeof content === "string" ? content : ((content.code as string) ?? JSON.stringify(content, null, 2));

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Agent Draft</CardTitle>
          <div className="flex gap-3 text-xs text-slate-500">
            {language && <span>{language}</span>}
            {agentId && <span>by {agentId}</span>}
            {generatedAt && (
              <span>{new Date(generatedAt).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <pre className="overflow-x-auto rounded-md bg-slate-900 p-4 text-sm text-slate-100">
          <code>{code}</code>
        </pre>
      </CardContent>
    </Card>
  );
}
