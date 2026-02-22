import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ContextExplorerPage from "./ContextExplorerPage";
import { getSharedContextFiles } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getSharedContextFiles: vi.fn(),
  getSharedContextFile: vi.fn(),
  updateSharedContextFile: vi.fn(),
  toApiErrorMessage: vi.fn((err: unknown, fallback: string) => fallback),
}));

vi.mock("@/lib/apiClient", () => ({
  toApiErrorMessage: vi.fn((_err: unknown, fallback: string) => fallback),
}));

const mockFiles = [
  {
    filename: "PROJECT_STATE.md",
    size_bytes: 2048,
    updated_at: "2025-06-14T12:00:00Z",
  },
  {
    filename: "INTEGRATIONS_GITHUB.md",
    size_bytes: 1024,
    updated_at: "2025-06-14T11:00:00Z",
  },
];

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ContextExplorerPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ContextExplorerPage", () => {
  const mockedGetFiles = vi.mocked(getSharedContextFiles);

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetFiles.mockResolvedValue(mockFiles);
  });

  it("shows loading state initially", () => {
    mockedGetFiles.mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(
      screen.getByText("Loading shared context files...")
    ).toBeInTheDocument();
  });

  it("renders the page heading", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Shared Context")).toBeInTheDocument();
    });
  });

  it("renders file cards", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("PROJECT_STATE.md")).toBeInTheDocument();
      expect(screen.getByText("INTEGRATIONS_GITHUB.md")).toBeInTheDocument();
    });
  });

  it("shows empty state when no files", async () => {
    mockedGetFiles.mockResolvedValue([]);
    renderWithProviders();
    await waitFor(() => {
      expect(
        screen.getByText(/No shared context files found/)
      ).toBeInTheDocument();
    });
  });
});
