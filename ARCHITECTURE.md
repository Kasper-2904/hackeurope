# Architecture

## Overview
Monorepo architecture with a web app, Python API, shared context store, OA planning engine, hosted-agent runtime, reviewer final-gate engine, marketplace service, and billing integrations.

## Technology Choices
- Backend: Python service(s)
- Frontend: React
- Agent orchestration SDK: Claude SDK (Anthropic)
- UI prototyping/acceleration: Lovable (handoff into React codebase)
- Seat billing: Stripe
- Agent usage billing: Paid.ai

## Core Components
- `frontend/`: React app for developer, PM, marketplace, and billing views.
- `backend/`: Python API for ingestion, planning, approvals, agent execution, review, marketplace, and billing.
- `docs/shared_context/`: Canonical markdown files serving as the shared orchestration memory.

## Shared Context Files (Canonical)
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/HOSTED_AGENTS.md`
- `docs/shared_context/AGENT_MARKETPLACE.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`
- `docs/shared_context/BILLING_SUBSCRIPTIONS.md`

## Shared Context Schema (MVP)
- `Project`: description, goals, milestones, timeline.
- `TeamMember`: role, skills, capacity, current assignments.
- `HostedAgent`: owner, capabilities summary, version, status, pricing metadata.
- `MarketplaceAgent`: visibility (`private`/`public`), publisher, usage terms.
- `Task`: status, single owner, dependencies, priority, plan version, approvals.
- `Subtask`: assigned agent, draft status, execution metadata.
- `ReviewResult`: blocker/non-blocker findings, rationale, readiness decision.
- `BillingState`: subscription tier, seat count, usage counters, charge status.

## Workflow Architecture
1. `Task Submitted` event enters API.
2. OA reads shared context and selects specialist hosted agent for task drafting.
3. Specialist agent run generates 70% draft output.
4. OA proposes suggested team-member assignment with the draft.
5. PM approves or reassigns task owner.
6. Assigned team member completes final 30% and commits to GitHub.
7. GitHub commit event triggers Reviewer Agent checks (consistency + conflict risk).
8. Reviewer findings update shared context and project memory.
9. Billing layer records seat usage (Stripe) and agent usage (Paid.ai).

## Marketplace Architecture
- Agent creation API for team-defined agents.
- Publication toggle (`private`/`public`) per agent version.
- Agent discovery/search for project attachment.
- Project-level allowlist of selectable agents enforced by OA.

## Billing Architecture
- Stripe:
  - checkout/session setup
  - subscription lifecycle webhooks
  - seat count synchronization
- Paid.ai:
  - usage event emitter for agent runs
  - pricing/charge fetch and reconciliation
- Internal ledger:
  - project/team/agent cost attribution snapshots

## API Surface (MVP)
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `POST /api/v1/plans/generate`
- `POST /api/v1/plans/{id}/approve`
- `POST /api/v1/plans/{id}/reject`
- `POST /api/v1/agents`
- `POST /api/v1/agents/{id}/publish`
- `GET /api/v1/marketplace/agents`
- `POST /api/v1/projects/{id}/agents/select`
- `POST /api/v1/reviewer/finalize/{task_id}`
- `POST /api/v1/billing/stripe/checkout`
- `POST /api/v1/billing/stripe/webhook`
- `POST /api/v1/billing/paidai/usage`
- `GET /api/v1/dashboard/developer/{user_id}`
- `GET /api/v1/dashboard/pm/{project_id}`

## Data and Storage
- Primary DB for normalized context and workflow state.
- Event log for approvals, assignments, agent runs, reviewer findings, and billing events.
- Agent artifact metadata store for cataloged hosted agents.
- Billing ledger tables for subscription and usage attribution.

## Non-Functional Design Choices
- Deterministic validation around Claude SDK outputs.
- Strict role-based authorization for PM/developer/admin actions.
- Full audit trail for approvals, reviewer decisions, marketplace publication, and billing changes.
- Final-review-only reviewer flow in MVP.

## Repository Layout
- `frontend/` (React + Vite + TypeScript + TailwindCSS)
- `backend/` (FastAPI + LangGraph + SQLAlchemy + SQLite)
- `docs/shared_context/` (Markdown state files)
- `tests/`
