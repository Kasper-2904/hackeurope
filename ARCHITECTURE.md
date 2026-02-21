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
- `apps/web`: developer, PM, and marketplace/billing views (React).
- `apps/api`: Python API for ingestion, planning, approvals, agent execution, review, marketplace, and billing.
- `packages/shared-context`: schemas and services for shared context documents.
- `packages/orchestrator-core`: OA planning, assignment, explainability.
- `packages/agent-runtime`: hosted autonomous agent execution orchestration.
- `packages/reviewer-core`: final whole-task review and merge-readiness scoring.
- `packages/marketplace-core`: agent catalog, publish/private flags, project agent selection.
- `packages/billing-core`: Stripe seat subscription + Paid.ai usage metering integration.
- `packages/integrations`: GitHub adapter + vendor connectors.
- `packages/shared`: shared types, validation, auth helpers, constants.

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
2. OA reads shared context and builds initial plan.
3. OA queries hosted-agent capability endpoints when needed.
4. Plan enters PM approval state.
5. On approval, subtasks are dispatched to selected hosted agents.
6. Hosted agents generate drafts; human owner finalizes subtasks.
7. Reviewer Agent runs final gate once subtasks are complete.
8. Billing layer records seat usage (Stripe) and agent usage (Paid.ai).

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
- `apps/web`
- `apps/api`
- `packages/shared-context`
- `packages/orchestrator-core`
- `packages/agent-runtime`
- `packages/reviewer-core`
- `packages/marketplace-core`
- `packages/billing-core`
- `packages/integrations`
- `packages/shared`
- `docs/shared_context`
- `tests/unit`
- `tests/integration`
- `tests/e2e`
