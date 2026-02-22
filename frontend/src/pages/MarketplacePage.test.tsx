import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MarketplacePage from "./MarketplacePage";
import { getMarketplaceCatalog, publishAgent } from "@/lib/api";
import type { MarketplaceAgent } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getMarketplaceCatalog: vi.fn(),
  publishAgent: vi.fn(),
}));

vi.mock("@/lib/apiClient", () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn(),
  },
  toApiErrorMessage: vi.fn((error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
  ),
}));

const mockAgents: MarketplaceAgent[] = [
  {
    id: "mp-1",
    agent_id: "agent-1",
    seller_id: "user-1",
    seller_name: null,
    name: "CodeDrafter",
    category: "code_generation",
    description: "Generates production-ready code.",
    pricing_type: "usage_based",
    price_per_use: 0.1,
    is_verified: true,
    is_active: true,
  },
  {
    id: "mp-2",
    agent_id: "agent-3",
    seller_id: "user-2",
    seller_name: null,
    name: "TestWriter",
    category: "testing",
    description: "Writes unit and integration tests.",
    pricing_type: "free",
    price_per_use: null,
    is_verified: false,
    is_active: true,
  },
];

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <MarketplacePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("MarketplacePage", () => {
  const mockedGetCatalog = vi.mocked(getMarketplaceCatalog);
  const mockedPublishAgent = vi.mocked(publishAgent);

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetCatalog.mockResolvedValue(mockAgents);
    mockedPublishAgent.mockResolvedValue(mockAgents[0]);
  });

  it("shows loading state initially", () => {
    mockedGetCatalog.mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByText("Loading marketplace...")).toBeInTheDocument();
  });

  it("renders agent cards after loading", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("CodeDrafter")).toBeInTheDocument();
    });
    expect(screen.getByText("TestWriter")).toBeInTheDocument();
  });

  it("renders the search input", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search agents...")).toBeInTheDocument();
    });
  });

  it("renders the Publish Agent button", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Publish Agent")).toBeInTheDocument();
    });
  });

  it("renders the page heading", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Agent Marketplace")).toBeInTheDocument();
    });
  });

  it("publishes with required access token payload", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(await screen.findByText("Publish Agent"));
    await user.type(screen.getByPlaceholderText("e.g., Code Reviewer Pro"), "Publish Bot");
    await user.type(screen.getByPlaceholderText("https://your-agent.com/v1"), "https://agent.example.com/v1");
    await user.type(screen.getByPlaceholderText("Token for authenticating with your agent"), "secret-token");
    await user.click(screen.getByRole("button", { name: "Publish Agent" }));

    await waitFor(() => {
      expect(mockedPublishAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Publish Bot",
          inference_endpoint: "https://agent.example.com/v1",
          access_token: "secret-token",
        }),
        undefined, // Free agents don't need onboarding URLs
      );
    });
  });

  it("shows actionable publish error message", async () => {
    const user = userEvent.setup();
    mockedPublishAgent.mockRejectedValueOnce(new Error("Field required"));
    renderWithProviders();

    await user.click(await screen.findByText("Publish Agent"));
    await user.type(screen.getByPlaceholderText("e.g., Code Reviewer Pro"), "Publish Bot");
    await user.type(screen.getByPlaceholderText("https://your-agent.com/v1"), "https://agent.example.com/v1");
    await user.type(screen.getByPlaceholderText("Token for authenticating with your agent"), "secret-token");
    await user.click(screen.getByRole("button", { name: "Publish Agent" }));

    await waitFor(() => {
      expect(
        screen.getByText("Missing required publish details. Add endpoint URL and API token, then try again."),
      ).toBeInTheDocument();
    });
  });
});
