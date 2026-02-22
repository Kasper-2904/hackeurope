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

## Milestone 5: MVP Review Hardening

### M5-T1 Marketplace Publish Flow Error Fix (owner: Martin)
- Status: Done
- Description: Investigate and fix frontend publish flow errors shown in browser console when publishing an agent in the marketplace.
- Notes: 2026-02-22 - Fixed marketplace publish request contract mismatch by sending required `access_token` from frontend, added client-side required-field checks, and added actionable non-technical publish error messaging; updated `MarketplacePage` tests to cover required publish payload and user-facing error states.
- Acceptance Criteria:
  - Publish flow completes without uncaught frontend console errors.
  - Error states shown to users are actionable and non-technical.

### M5-T2 PM Approval Must Trigger Task Assignment (owner: Farhan)
- Status: Todo
- Description: Fix orchestration transition so PM plan approval reliably starts assignment/execution flow.
- Acceptance Criteria:
  - Approving a plan moves it into active assignment/execution state.
  - Backend tests cover approve -> assign transition.

### M5-T3 Context Page Real OA Reasoning (owner: Martin)
- Status: Todo
- Description: Replace mock context page data with OA reasoning/rationale from real backend responses.
- Acceptance Criteria:
  - Context page renders persisted OA reasoning data, not static mocks.
  - Empty/error states are handled for missing reasoning entries.

### M5-T4 Real-Time OA Reasoning Logs in Frontend (owner: Marin)
- Status: In Progress
- Description: Add real-time reasoning/action log updates in frontend task/detail views.
- Notes: 2026-02-22 - Implementation prep completed with M5-T4-ST0 (branch + scoped subtask plan + agent prompt pack in `prompts/`).
  2026-02-22 - Implemented ST1-ST5: persisted lifecycle logs, snapshot + SSE APIs with task-level auth, frontend stream hook, and Task Detail reasoning timeline UI with reconnect warning.
- Subtasks:
  - M5-T4-ST0 (owner: Marin) - Done - Prepare branch, subtasks, and agent prompts.
  - M5-T4-ST1 (owner: Farhan) - Done - Persist orchestration event timeline for task/plan runs (task started/assigned/progress/completed/failed) in backend storage with stable event payload shape.
  - M5-T4-ST2 (owner: Farhan) - Done - Add task reasoning log APIs for snapshot retrieval and real-time streaming (SSE) with auth + access checks.
  - M5-T4-ST3 (owner: Martin) - Done - Add frontend reasoning-log API/types + streaming hook to consume incremental SSE updates and merge with initial history.
  - M5-T4-ST4 (owner: Martin) - Done - Implement Task Detail reasoning log timeline UI (in-progress vs completed states, ordering, reconnect/error/empty states).
  - M5-T4-ST5 (owner: Martin) - Done - Wire orchestration-triggered refresh behavior so live logs appear during active runs without manual page reload.
  - M5-T4-ST6 (owner: Marin) - Done - Added backend API tests for reasoning-log snapshot ordering/shape, unauthorized access behavior, empty/unknown payload handling, SSE event formatting, and disconnect cleanup behavior.
  - M5-T4-ST7 (owner: Marin) - Done - Expanded frontend Task Detail tests for initial reasoning timeline rendering, incremental stream updates with ordering, in-progress/completed state visibility, disconnect warning UX with history preservation, empty-state fallback, and stream/snapshot dedupe.
  - M5-T4-ST8 (owner: Marin) - Todo - Review pass and quality gates (`cd backend && .venv/bin/pytest`, `cd frontend && npm run lint && npm run build && npm run test`).
- Acceptance Criteria:
  - Reasoning/action logs stream incrementally during orchestration runs.
  - UI clearly distinguishes in-progress vs completed reasoning steps.

### M5-T5 OA Must Load Shared Context Before Planning (owner: Kasper)
- Status: Todo
- Description: Ensure OA planning reads canonical shared context sources before generating assignments/plans.
- Acceptance Criteria:
  - OA planning requests include shared context inputs from configured sources.
  - Tests verify plans change when shared context input changes.

### M5-T6 Failed Subagent Runs Mark Task Failed (owner: Farhan)
- Status: Todo
- Description: Propagate subagent execution failures to task status so tasks become `failed` instead of hanging in active states.
- Acceptance Criteria:
  - Subagent hard failure updates task status to `failed`.
  - Failure reason is persisted for PM/developer visibility.

### M5-T7 Subtasks Execute with Same Lifecycle Guarantees as Tasks (owner: Farhan)
- Status: Todo
- Description: Align subtask execution lifecycle/state transitions with main task execution behavior.
- Acceptance Criteria:
  - Subtasks support same status lifecycle and retries as tasks (where applicable).
  - Integration test covers task + subtask coordinated execution.

### M5-T8 PM Can Create Tasks via Tasks API Flow (owner: Marin)
- Status: In Progress
- Description: Enable PM creation flow wired to `POST /api/v1/tasks` with proper frontend entry point and role handling.
- Notes: 2026-02-22 - Implementation prep completed with M5-T8-ST0 (single branch setup + scoped subtask plan + agent prompt pack in `prompts/`).
- Notes: 2026-02-22 - Implemented ST1-ST4: backend project-scoped PM role enforcement for `POST /tasks` (owner/PM/admin/superuser), stable 404/403 handling, direct project linkage in `/projects/{id}/tasks`, and PM Tasks-tab creation form with typed client wiring + loading/success/error UX.
- Notes: 2026-02-22 - Implemented ST5-ST7 test coverage and quality gates: backend tests now cover PM/admin/owner create-task authorization, inaccessible-project and payload validation errors (including API-level 422 for missing required fields and project/team mismatch), direct project linkage visibility, and legacy non-project creation; frontend tests now cover PM create-task success with task-board refresh trigger, loading disabled states, backend 422/403 messaging, and task-board rendering safety. Quality gates pass with `cd backend && .venv/bin/pytest` and `cd frontend && npm run lint && npm run build && npm run test`.
- Subtasks:
  - M5-T8-ST0 (owner: Marin) - Done - Prepare branch, subtasks, and agent prompts.
  - M5-T8-ST1 (owner: Farhan) - Done - Backend task creation contract hardening: require PM/Admin role for project-scoped task creation, validate project/task ownership boundaries, and return stable authorization/validation errors.
  - M5-T8-ST2 (owner: Farhan) - Done - Ensure PM-created tasks are linked into project task flow so PM dashboard task board reflects newly created tasks without manual DB intervention.
  - M5-T8-ST3 (owner: Martin) - Done - Add PM task creation entry point in PM project detail UI (`ProjectDetailPage`) and wire submit to `POST /api/v1/tasks`.
  - M5-T8-ST4 (owner: Martin) - Done - Add frontend PM task-creation client/types/form UX states (loading/success/error/validation) with clear non-technical messages.
  - M5-T8-ST5 (owner: Marin) - Done - Added backend tests for owner/PM/admin happy path, non-PM denial, inaccessible project 404 behavior, missing required-field 422 response, project/team mismatch 422 response, project linkage discoverability via project task listing, and legacy non-project creation regression.
  - M5-T8-ST6 (owner: Marin) - Done - Added frontend PM project-detail tests for create-task submit success with refresh trigger + success banner, loading-disabled submit state, missing-title submit prevention, backend 422 validation messaging, and permission-denied messaging while task board remains functional.
  - M5-T8-ST7 (owner: Marin) - Done - Completed review pass and executed quality gates (`cd backend && .venv/bin/pytest`, `cd frontend && npm run lint && npm run build && npm run test`) successfully.
- Acceptance Criteria:
  - PM can create a task end-to-end from UI/API flow.
  - Authorization and validation errors are surfaced clearly.

### M5-T9 Paid.ai Token Usage Billing for LLM Calls (owner: Kasper)
- Status: Todo
- Description: Extend usage metering to include token-based LLM call billing events, not only tool-call events.
- Acceptance Criteria:
  - Token usage per LLM call is captured and emitted to Paid.ai payloads.
  - Billing summary reflects token-driven usage costs.

### M5-T10 GitHub Sync Must Auto-Refresh Shared Context Files (owner: Kasper)
- Status: Todo
- Description: Ensure GitHub ingestion automatically refreshes internal context and populates canonical `docs/shared_context/*.md` context files.
- Acceptance Criteria:
  - GitHub sync updates shared context state without manual intervention.
  - Canonical shared context markdown files are populated from latest sync data.

### M5-T11 OA Must Wait for PM Start Signal Before Execution (owner: Marin)
- Status: Todo
- Description: Ensure new tasks first generate an OA implementation plan, then pause for PM approval/start signal before any implementation agents begin execution.
- Acceptance Criteria:
  - Creating a new task triggers OA planning first and stores a plan artifact before execution starts.
  - No implementation agent execution begins until PM provides explicit approval/start signal.
  - After PM start signal, full task implementation flow transitions to active execution automatically.

### M5-T12 Shared Context Files Must Be Visible in Frontend (owner: Kasper)
- Status: Todo
- Description: Add a clean, user-friendly UI view that surfaces files from `docs/shared_context` so teams can inspect current shared context in-app.
- Acceptance Criteria:
  - Frontend includes a dedicated shared context view that lists files from `docs/shared_context`.
  - Users can open and read shared context file contents with clear loading, empty, and error states.
  - UI is accessible and consistent with existing app navigation/layout patterns.

### M5-T13 Marketplace Stripe Onboarding and Subscribe Flows Must Work (owner: Farhan)
- Status: Todo
- Description: Fix Stripe regressions where seller onboarding is not triggered on agent publish and project subscription flow is failing.
- Acceptance Criteria:
  - Publishing an agent triggers seller onboarding flow when required and returns actionable status to frontend.
  - Project subscription flow completes successfully end-to-end for valid Stripe checkout cases.
  - Backend tests cover publish->onboarding trigger behavior and successful subscription creation path.
