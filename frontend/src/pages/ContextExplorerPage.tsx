// ContextExplorerPage — view, edit, and upload shared context files
// that the orchestrator uses as its "memory" between agent runs.

import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useSharedContextFiles } from "@/hooks/use-api";
import {
  getSharedContextFile,
  updateSharedContextFile,
  createSharedContextFile,
} from "@/lib/api";
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

  // Upload / create new file state
  const [showCreate, setShowCreate] = useState(false);
  const [newFilename, setNewFilename] = useState("");
  const [newContent, setNewContent] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const createMutation = useMutation({
    mutationFn: () => {
      const filename = newFilename.endsWith(".md") ? newFilename : `${newFilename}.md`;
      return createSharedContextFile(filename, newContent);
    },
    onSuccess: (created) => {
      setShowCreate(false);
      setNewFilename("");
      setNewContent("");
      setSelectedFile(created);
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

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setNewContent(content);
      // Use uploaded filename, ensure .md extension
      const name = file.name.endsWith(".md")
        ? file.name
        : file.name.replace(/\.[^.]+$/, ".md");
      setNewFilename(name);
      setShowCreate(true);
    };
    reader.readAsText(file);

    // Reset input so the same file can be re-selected
    e.target.value = "";
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
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold">Shared Context</h2>
          <p className="text-sm text-slate-500 mt-1">
            Files the orchestrator reads before planning and updates after execution.
            Upload your own context to give agents more project knowledge.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.txt,.markdown"
            className="hidden"
            onChange={handleFileUpload}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
          >
            Upload File
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setShowCreate(true);
              setNewFilename("");
              setNewContent("");
              createMutation.reset();
            }}
          >
            + New Context
          </Button>
        </div>
      </div>

      {/* Create / Upload new file form */}
      {showCreate && (
        <Card className="border-sky-300 bg-sky-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Add New Context File
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {createMutation.isError && (
              <div className="text-sm text-red-600">
                {toApiErrorMessage(createMutation.error, "Failed to create file")}
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Filename (must end in .md)
              </label>
              <input
                type="text"
                value={newFilename}
                onChange={(e) => setNewFilename(e.target.value)}
                placeholder="e.g. ARCHITECTURE_DECISIONS.md"
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                disabled={createMutation.isPending}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Content
              </label>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="# My Context File&#10;&#10;Add project knowledge that agents should know about..."
                className="w-full min-h-[200px] rounded-md border border-slate-300 bg-white p-3 font-mono text-sm leading-relaxed focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                disabled={createMutation.isPending}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowCreate(false);
                  createMutation.reset();
                }}
                disabled={createMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || !newFilename.trim() || !newContent.trim()}
              >
                {createMutation.isPending ? "Creating..." : "Create File"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {!files || files.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          No shared context files found. Upload a file or create one to get started.
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
