import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AgentCard } from "./AgentCard";
import type { MarketplaceAgent } from "@/lib/types";

const freeAgent: MarketplaceAgent = {
  id: "mp-1",
  agent_id: "agent-1",
  seller_id: "user-1",
  name: "TestBot",
  category: "testing",
  description: "A helpful testing agent",
  pricing_type: "free",
  price_per_use: null,
  is_verified: true,
  is_active: true,
};

const paidAgent: MarketplaceAgent = {
  id: "mp-2",
  agent_id: "agent-2",
  seller_id: "user-1",
  name: "CodeBot",
  category: "code_generation",
  description: "Generates code",
  pricing_type: "usage_based",
  price_per_use: 0.05,
  is_verified: false,
  is_active: true,
};

function renderCard(agent: MarketplaceAgent) {
  return render(
    <MemoryRouter>
      <AgentCard agent={agent} />
    </MemoryRouter>
  );
}

describe("AgentCard", () => {
  it("renders agent name", () => {
    renderCard(freeAgent);
    expect(screen.getByText("TestBot")).toBeInTheDocument();
  });

  it("renders description", () => {
    renderCard(freeAgent);
    expect(screen.getByText("A helpful testing agent")).toBeInTheDocument();
  });

  it("shows Verified badge for verified agents", () => {
    renderCard(freeAgent);
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("does not show Verified badge for unverified agents", () => {
    renderCard(paidAgent);
    expect(screen.queryByText("Verified")).not.toBeInTheDocument();
  });

  it("shows Free badge for free agents", () => {
    renderCard(freeAgent);
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("shows price for usage-based agents", () => {
    renderCard(paidAgent);
    expect(screen.getByText("$0.05/use")).toBeInTheDocument();
  });

  it("shows category badge", () => {
    renderCard(freeAgent);
    expect(screen.getByText("testing")).toBeInTheDocument();
  });
});
