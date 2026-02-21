# Tasks

## Milestone 1: Core Context, Marketplace, and Ownership Rules

### M1-T1 Define shared context schema + single-owner task rule (owner: Marin)
- Status: Todo
- Description: Finalize schemas and canonical markdown file structure, including enforcement that one task has one owner.
- Acceptance Criteria:
  - Shared context `.md` files exist with documented sections.
  - Task schema enforces exactly one owner per task.
- Test Strategy:
  - Unit tests for schema validation and ownership constraint.

### M1-T2 Implement GitHub ingestion adapter (owner: Kasper)
- Status: Todo
- Description: Build connector and normalization for GitHub task/PR/CI context.
- Acceptance Criteria:
  - Ingestion jobs fetch and normalize core GitHub entities.
  - Adapter failures are retried and surfaced.
- Test Strategy:
  - Integration tests with mocked GitHub responses.

### M1-T3 Implement hosted-agent registry + runtime metadata (owner: Martin)
- Status: Todo
- Description: Build API/storage for hosted-agent registration, capabilities, versioning, and execution status.
- Acceptance Criteria:
  - Hosted agent can be created/listed and referenced by OA.
  - Runtime metadata is queryable and auditable.
- Test Strategy:
  - Integration tests for create/list/update/error paths.

### M1-T4 Implement PM project-agent selection and approval state model (owner: Farhan)
- Status: Todo
- Description: Add PM controls for selecting allowed agents per project and versioned plan approval states.
- Acceptance Criteria:
  - PM can configure project agent allowlist.
  - OA plans cannot execute before PM approval.
- Test Strategy:
  - Integration tests for allowlist enforcement and approval transitions.

## Milestone 2: Orchestration and Final Review

### M2-T1 Build OA planning engine with hosted-agent capability checks (owner: Marin)
- Status: Todo
- Description: OA creates assignment plan using shared context and hosted-agent capability queries.
- Acceptance Criteria:
  - OA outputs one task owner + subtask-to-agent mapping.
  - Plan includes rationale for each assignment.
- Test Strategy:
  - Unit tests for planning constraints.
  - Integration tests for capability query fallback behavior.

### M2-T2 Implement hosted-agent autonomous execution pipeline (owner: Kasper)
- Status: Todo
- Description: Dispatch approved subtasks to hosted agents and collect draft outputs.
- Acceptance Criteria:
  - Agent runs are tracked with status and run metadata.
  - Draft outputs are attached to correct task/subtask.
- Test Strategy:
  - Integration tests for dispatch/retry/failure handling.

### M2-T3 Implement final reviewer gate (owner: Martin)
- Status: Todo
- Description: Add final all-subtasks-submitted review stage with blocker/non-blocker findings.
- Acceptance Criteria:
  - Reviewer runs only when subtasks are complete.
  - Final review produces merge-readiness decision and rationale.
- Test Strategy:
  - End-to-end tests for pass and block scenarios.

### M2-T4 Implement developer finalize flow over agent drafts (owner: Farhan)
- Status: Todo
- Description: Build developer actions to inspect, edit, approve, and finalize agent-generated drafts.
- Acceptance Criteria:
  - Developers can finalize subtasks with full audit trail.
  - Finalized state updates task progress consistently.
- Test Strategy:
  - Integration tests for draft lifecycle and finalization.

## Milestone 3: Marketplace and Billing (HackEurope Challenges)

### M3-T1 Build agent marketplace catalog and visibility model (owner: Martin)
- Status: Todo
- Description: Implement marketplace listing, private/public visibility, and discovery filters.
- Acceptance Criteria:
  - Teams can browse public agents.
  - Private agents are scoped to creator team only.
- Test Strategy:
  - Integration tests for visibility and access control.

### M3-T2 Implement custom agent creation and publication flow (owner: Marin)
- Status: Todo
- Description: Build flow to create custom agents and publish new versions publicly.
- Acceptance Criteria:
  - Agent creator can create, version, and publish/unpublish agents.
  - OA can reference selected published versions.
- Test Strategy:
  - Integration tests for create/version/publish lifecycle.

### M3-T3 Integrate Stripe seat-based subscriptions (owner: Farhan)
- Status: Todo
- Description: Implement checkout, subscription lifecycle, and seat-count enforcement.
- Acceptance Criteria:
  - Teams can subscribe and manage seats.
  - Seat limit enforcement is active.
- Test Strategy:
  - Integration tests for Stripe webhook flows and seat updates.

### M3-T4 Integrate Paid.ai usage metering (owner: Kasper)
- Status: Todo
- Description: Emit hosted-agent usage events to Paid.ai and ingest cost/value data.
- Acceptance Criteria:
  - Agent runs produce billable usage events.
  - Usage/cost is visible by project/team/agent.
- Test Strategy:
  - Integration tests for usage event payloads and reconciliation.

## Milestone 4: Dashboard Experiences and Demo Readiness

### M4-T1 Developer dashboard: task list + detail panel + risk graph (owner: Kasper)
- Status: Todo
- Description: Build developer UI with task list/sub-actions and detail panel for agents/progress/errors/risks.
- Acceptance Criteria:
  - Selecting a task updates detail panel with required data.
  - Risk/progress visualization is present and readable.
- Test Strategy:
  - Component tests and e2e task navigation.

### M4-T2 PM macro dashboard + marketplace controls (owner: Farhan)
- Status: Todo
- Description: Build PM view with goals, milestones, timeline, team progress, selected agents, and approval/final-review decisions.
- Acceptance Criteria:
  - PM can manage project agent allowlist from dashboard.
  - PM sees critical items and final-review outcomes.
- Test Strategy:
  - Component tests and E2E PM approval/manage flow.

### M4-T3 Shared context explorer and explainability UI (owner: Marin)
- Status: Todo
- Description: Build views for shared context entities and OA/Reviewer rationale traces.
- Acceptance Criteria:
  - OA/Reviewer decisions show explainable factors.
  - Users can inspect linked team/agent/task context.
- Test Strategy:
  - Component tests for rationale rendering.
  - Integration tests for context retrieval.

### M4-T4 Security, audit, QA, and demo script (owner: Martin)
- Status: Todo
- Description: Finalize role checks, audit trails, final QA pass, and demo runbook.
- Acceptance Criteria:
  - Unauthorized actions are blocked.
  - Demo scenario is reproducible and documented.
- Test Strategy:
  - Role-matrix integration tests and full regression dry run.

## Parallelization Plan (Team of 4)
- Kasper track: GitHub ingestion + agent execution pipeline + Paid.ai + developer dashboard.
- Martin track: hosted-agent registry + reviewer gate + marketplace visibility + security/QA.
- Farhan track: PM selection/approval + Stripe subscriptions + PM dashboard.
- Marin track: shared schema + OA planning + agent creation/publish + explainability.
