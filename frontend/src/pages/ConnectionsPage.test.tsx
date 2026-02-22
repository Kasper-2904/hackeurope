import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ConnectionsPage from "./ConnectionsPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ConnectionsPage />
    </MemoryRouter>
  );
}

describe("ConnectionsPage", () => {
  it("renders the page heading", () => {
    renderPage();
    expect(screen.getByText("Connections")).toBeInTheDocument();
  });

  it("renders all 4 integration cards", () => {
    renderPage();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
    expect(screen.getByText("Stripe")).toBeInTheDocument();
    expect(screen.getByText("Paid")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
  });

  it("shows Connected badge for GitHub, Stripe, and Paid", () => {
    renderPage();
    const connectedBadges = screen.getAllByText("Connected");
    expect(connectedBadges).toHaveLength(3);
  });

  it("shows Available badge for Slack", () => {
    renderPage();
    expect(screen.getByText("Available")).toBeInTheDocument();
  });

  it("shows Configure button for connected services", () => {
    renderPage();
    const configureButtons = screen.getAllByText("Configure");
    expect(configureButtons).toHaveLength(3);
  });

  it("shows Connect button for Slack", () => {
    renderPage();
    expect(screen.getByText("Connect")).toBeInTheDocument();
  });
});
