import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AgentDetailPage from "./AgentDetailPage";

function renderWithProviders(agentId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/marketplace/${agentId}`]}>
        <Routes>
          <Route path="/marketplace/:agentId" element={<AgentDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AgentDetailPage", () => {
  it("shows loading state initially", () => {
    renderWithProviders("mp-1");
    expect(screen.getByText("Loading agent...")).toBeInTheDocument();
  });

  it("renders agent name after loading", async () => {
    renderWithProviders("mp-1");
    await waitFor(() => {
      expect(screen.getByText("CodeDrafter")).toBeInTheDocument();
    });
  });

  it("shows verified badge for verified agent", async () => {
    renderWithProviders("mp-1");
    await waitFor(() => {
      expect(screen.getByText("Verified")).toBeInTheDocument();
    });
  });

  it("shows not found for invalid agent", async () => {
    renderWithProviders("nonexistent");
    await waitFor(() => {
      expect(screen.getByText("Agent not found")).toBeInTheDocument();
    });
  });

  it("shows back to marketplace link", async () => {
    renderWithProviders("mp-1");
    await waitFor(() => {
      expect(screen.getByText("Back to marketplace")).toBeInTheDocument();
    });
  });
});
