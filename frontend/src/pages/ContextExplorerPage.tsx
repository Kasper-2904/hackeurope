// ContextExplorerPage — view and edit shared context files
// that the orchestrator uses as its "memory" between agent runs.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useSharedContextFiles } from "@/hooks/use-api";
import { getSharedContextFile, updateSharedContextFile } from "@/lib/api";
import type { SharedContextFileDetail } from "@/lib/api";
import { toApiErrorMessage } from "@/lib/apiClient";

export default function ContextExplorerPage() {
  const { data: files, isLoading, isError, error } = useSharedContextFiles();
  const [selectedFile, setSelectedFile] = useState<SharedContextFileDetail | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) return Promise.reject(new Error("No file selected"));
      return updateSharedContextFile(selectedFile.filename, editContent);
    },
    onSuccess: (updated) => {
      setSelectedFile(updated);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["shared-context-files"] });
    },
  });

  async function handleSelectFile(filename: string) {
    setFileError(null);
    setEditing(false);
    saveMutation.reset();

    if (selectedFile?.filename === filename) {
      setSelectedFile(null);
      return;
    }

    setFileLoading(true);
    try {
      const detail = await getSharedContextFile(filename);
      setSelectedFile(detail);
    } catch (err) {
      setFileError(toApiErrorMessage(err, "Failed to load file"));
      setSelectedFile(null);
    } finally {
      setFileLoading(false);
    }
  }

  function handleEdit() {
    if (!selectedFile) return;
    setEditContent(selectedFile.content);
    setEditing(true);
    saveMutation.reset();
  }

  function handleCancelEdit() {
    setEditing(false);
    saveMutation.reset();
  }

  if (isLoading) {
    return <div className="text-sm text-slate-500">Loading shared context files...</div>;
  }

  if (isError) {
    return (
      <div className="text-sm text-red-600">
        {toApiErrorMessage(error, "Failed to load shared context files")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Shared Context</h2>
        <p className="text-sm text-slate-500 mt-1">
          Files the orchestrator reads before planning and updates after execution.
        </p>
      </div>

      {!files || files.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No shared context files found. Run the seed script or trigger a GitHub sync to populate them.
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {files.map((f) => (
            <button
              key={f.filename}
              onClick={() => handleSelectFile(f.filename)}
              className={`rounded-lg border p-3 text-left transition hover:border-sky-400 ${
                selectedFile?.filename === f.filename
                  ? "border-sky-600 bg-sky-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="text-sm font-medium truncate">{f.filename}</div>
              <div className="mt-1 text-xs text-slate-400">
                {f.size_bytes > 0
                  ? `${(f.size_bytes / 1024).toFixed(1)} KB`
                  : "empty"}
              </div>
              <div className="mt-0.5 text-xs text-slate-400">
                {new Date(f.updated_at).toLocaleString()}
              </div>
            </button>
          ))}
        </div>
      )}

      {fileLoading && (
        <div className="text-sm text-slate-500">Loading file...</div>
      )}

      {fileError && (
        <div className="text-sm text-red-600">{fileError}</div>
      )}

      {selectedFile && !fileLoading && (
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">
              {selectedFile.filename}
            </CardTitle>
            <div className="flex gap-2">
              {editing ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancelEdit}
                    disabled={saveMutation.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending}
                  >
                    {saveMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                </>
              ) : (
                <Button variant="outline" size="sm" onClick={handleEdit}>
                  Edit
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {saveMutation.isError && (
              <div className="mb-3 text-sm text-red-600">
                {toApiErrorMessage(saveMutation.error, "Failed to save file")}
              </div>
            )}
            {editing ? (
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full min-h-[300px] rounded-md border border-slate-300 bg-white p-3 font-mono text-sm leading-relaxed focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                disabled={saveMutation.isPending}
              />
            ) : (
              <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed font-mono bg-slate-50 rounded-md p-3 overflow-x-auto">
                {selectedFile.content || "(empty file)"}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
