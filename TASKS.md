# Tasks

## Team Alignment
*   **Backend & Integrations**: Farhan & Kasper
*   **Frontend & UI**: Martin & Marin

## Milestone 1: Core Setup & Context

### M1-T1 Core Backend Models & Auth API (owner: Farhan)
- Status: Done
- Description: Setup SQLite database, core models (Users, Teams, Projects, Tasks), and JWT Auth APIs.
- Acceptance Criteria:
  - Database is initialized.
  - Auth endpoints (`/register`, `/login`) work.

### M1-T2 GitHub Ingestion Adapter (owner: Kasper)
- Status: Done
- Description: Build connector and normalization for GitHub task/PR/CI context.
- Acceptance Criteria:
  - Ingestion jobs fetch and normalize core GitHub entities.
  - Adapter failures are retried and surfaced.

### M1-T3 Scaffold Frontend Repository (owner: Martin)
- Status: In Progress
- Description: Setup Vite + React + TypeScript + TailwindCSS environment.
- Acceptance Criteria:
  - Frontend app runs locally on port 5173.
  - Proxy configured to `localhost:8000/api`.

### M1-T4 Shared UI Components & Auth Flow (owner: Marin)
- Status: In Progress
- Description: Build base UI shell, navigation, and Login/Register screens.
- Acceptance Criteria:
  - User can register, login, and persist token in frontend state.
  - Navigation layout handles authenticated state.

## Milestone 2: Orchestration & Workflows

### M2-T1 LangGraph Orchestrator & Reviewer API (owner: Kasper)
- Status: In Progress
- Description: Implement OA planning logic and Final Reviewer gate.
- Acceptance Criteria:
  - OA generates plan with agent assignment.
  - Reviewer agent can process GitHub commits and flag risks.

### M2-T2 Agent Execution & PM Approval APIs (owner: Farhan)
- Status: Done
- Description: Build hosted agent inference, tool execution, and PM approval endpoints.
- Acceptance Criteria:
  - PM can approve/reject plans (with role verification).
  - Tasks can be dispatched to agents via hosted inference.
- Notes:
  - PM role verification added to approve/reject endpoints
  - Uses hosted inference (LiteLLM) instead of MCP protocol
  - Skills loaded from markdown files (`src/skills/*.md`)
  - Unit tests added for PM role verification (11 tests)

### M2-T3 Developer Dashboard UI (owner: Martin)
- Status: In Progress
- Description: Build developer UI for task list, sub-actions, agent draft review, and risk graphs.
- Acceptance Criteria:
  - Developer sees assigned tasks.
  - Developer can finalize a draft.

### M2-T4 PM Dashboard UI (owner: Marin)
- Status: Done
- Description: Build PM view with goals, team progress, and approval gates.
- Notes: 2026-02-21 - M2-T4-ST1 through M2-T4-ST6 implemented (PM routes/pages, project allowlist backend+frontend flows, PM approval/rejection interactions with loading/error/empty states). M2-T4-ST7 and M2-T4-ST8 tests are now added (backend allowlist + plan action coverage, frontend PM dashboard interaction/state coverage). M2-T4-ST9 quality gates pass with local commands (`cd backend && .venv/bin/pytest`, `cd frontend && npm run lint && npm run build && npm run test`).
- Acceptance Criteria:
  - PM can manage project agent allowlist.
  - PM can review and approve OA plans.

## Milestone 3: Marketplace & Billing

### M3-T1 Marketplace API & Stripe Integration (owner: Farhan)
- Status: Done
- Description: Build agent catalog APIs, Stripe seat checkout, and Stripe Connect.
- Acceptance Criteria:
  - `MarketplaceAgent` catalog endpoints work.
  - Stripe subscriptions can be created via checkout session.
- Notes:
  - Marketplace endpoints: publish, catalog, subscribe
  - Billing endpoints: purchase-agent, onboard-seller, seller-status, webhook
  - Stripe Product/Price auto-created for paid agents
  - Stripe Connect for seller payouts
  - Webhook handler for checkout.session.completed and account.updated

### M3-T2 Paid.ai Usage Metering (owner: Kasper)
- Status: In Progress
- Description: Emit hosted-agent usage events to Paid.ai and track internal usage DB.
- Acceptance Criteria:
  - Agent runs produce billable usage events.
  - Usage limits are enforced.

### M3-T3 Agent Marketplace UI (owner: Martin)
- Status: Todo
- Description: Build the Agent Catalog and the "Publish Agent" flow.
- Acceptance Criteria:
  - Teams can browse public agents.
  - Agent creators can publish versions.

### M3-T4 Billing & Settings UI (owner: Marin)
- Status: In Progress
- Description: Build the workspace settings page for Stripe checkout and Paid.ai cost visibility.
- Notes: 2026-02-21 - Implementation prep completed with M3-T4-ST0 (branch + scoped subtask plan + agent prompt pack in `prompts/`).
- Notes: 2026-02-21 - ST1-ST6 completed: backend billing summary endpoint with team ownership + usage aggregation, hardened subscribe response/error contract, frontend billing API/types, `/billing` page + nav integration, subscribe CTA flow with Stripe redirect, and usage visibility widgets with empty states.
- Subtasks:
  - M3-T4-ST0 (owner: Marin) - Done - Prepare branch, subtasks, and agent prompts.
  - M3-T4-ST1 (owner: Farhan) - Done - Added `GET /api/v1/billing/summary/{team_id}` with strict owner-only access, subscription snapshot, total usage cost, per-agent rollup, and recent usage records.
  - M3-T4-ST2 (owner: Farhan) - Done - Hardened `POST /billing/subscribe` with typed response payload (`checkout_url`, `team_id`), URL validation, and stable checkout failure errors for UI consumption.
  - M3-T4-ST3 (owner: Martin) - Done - Added `frontend/src/lib/billingApi.ts` and shared billing TS types in `frontend/src/lib/types.ts`.
  - M3-T4-ST4 (owner: Martin) - Done - Replaced `/billing` placeholder with `BillingPage` and added Billing nav entry in app shell.
  - M3-T4-ST5 (owner: Martin) - Done - Implemented workspace selection + subscribe CTA flow with loading/error handling and Stripe checkout redirect.
  - M3-T4-ST6 (owner: Martin) - Done - Implemented billing usage widgets for total cost, per-agent breakdown, and recent usage table with empty states.
  - M3-T4-ST7 (owner: Marin) - Done - Added backend billing tests for summary empty-state/response-shape, non-owner/unknown-team authorization, and subscribe validation/service-failure paths.
  - M3-T4-ST8 (owner: Marin) - Done - Added frontend BillingPage tests covering success rendering, subscribe redirect + error handling, and summary loading/error/empty states.
  - M3-T4-ST9 (owner: Marin) - Todo - Review pass and quality gates (`cd backend && .venv/bin/pytest`, `cd frontend && npm run lint && npm run build && npm run test`).
  - Notes: 2026-02-21 - Test updates: `backend/tests/api/test_billing.py`, `frontend/src/pages/BillingPage.test.tsx`; commands run: `cd backend && .venv/bin/pytest`, `cd frontend && npm run lint && npm run build && npm run test`.
- Acceptance Criteria:
  - User can click "Subscribe" to trigger Stripe flow.
  - Usage dashboards visualize costs.

## Milestone 4: Polish & Demo

### M4-T1 Security, Audits, & Perf Tuning (owner: Farhan)
- Status: Todo
- Description: Finalize role checks, audit trails, and API latency.
- Acceptance Criteria:
  - Role-matrix enforced.
  - Audit logs cover all critical actions.

### M4-T2 Backend QA & Seed Scripts (owner: Kasper)
- Status: In Progress
- Description: Write DB seeders for the demo and run integration tests.
- Acceptance Criteria:
  - Demo scenario data is easily loadable via script.
- Notes:
  - Seed script fixed and working (`uv run python scripts/seed_db.py`)
  - Skills refactored to use markdown files in `src/skills/`
  - Unit tests added for skills loading (15 tests passing)

### M4-T3 Context Explorer & Explainability UI (owner: Martin)
- Status: Todo
- Description: Build views for shared context entities and OA/Reviewer rationale traces.
- Acceptance Criteria:
  - OA/Reviewer decisions show explainable factors in UI.

### M4-T4 Frontend QA & Demo Script (owner: Marin)
- Status: Todo
- Description: Final UI polish, fix UX glitches, prepare demo runbook.
- Acceptance Criteria:
  - Demo scenario is reproducible and documented.
