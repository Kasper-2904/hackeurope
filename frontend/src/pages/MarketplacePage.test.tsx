import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MarketplacePage from "./MarketplacePage";

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
  it("shows loading state initially", () => {
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
});
