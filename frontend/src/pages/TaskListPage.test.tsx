import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TaskListPage from "./TaskListPage";

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TaskListPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TaskListPage", () => {
  it("shows loading state initially", () => {
    renderWithProviders();
    expect(screen.getByText("Loading tasks...")).toBeInTheDocument();
  });

  it("renders kanban column headers", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Tasks")).toBeInTheDocument();
    });
    // Status badges serve as column headers
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("In Progress").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
  });

  it("renders task cards after loading", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("Set up user authentication API")).toBeInTheDocument();
    });
    expect(screen.getByText("Build GitHub ingestion adapter")).toBeInTheDocument();
  });

  it("shows task descriptions on cards", async () => {
    renderWithProviders();
    await waitFor(() => {
      expect(
        screen.getByText(/Implement JWT auth endpoints/)
      ).toBeInTheDocument();
    });
  });
});
