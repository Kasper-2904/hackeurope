# Project Spec: Team Orchestration Platform for Software Delivery

## Problem Statement
Software teams lose time because project context is fragmented, task ownership is unclear, and delivery risks (merge conflicts, CI failures) are found too late.

## Product Vision
A web platform where an Orchestration Agent (OA), human Project Manager (PM), developers, local agents, and a Reviewer Agent collaborate through one shared structured context.

The platform merges data from:
- GitHub
- Local agents (uploadable/registrable in platform)

## Primary Users
- Project Manager (human in the loop): collaborates with OA and approves implementation plans.
- Developer: receives subtask drafts from local agents, edits, approves, and finalizes work.
- Reviewer Agent: performs final quality/risk gate on whole task after subtasks are done.

## Tech Stack (MVP)
- Backend/API: Python
- Frontend: React
- Agent SDK: Claude SDK
- UI acceleration/prototyping: Lovable

## Product Goals
1. Centralize team/project context into a single structured context.
2. Plan and distribute tasks with OA, with PM approval before execution.
3. Enable local agents to draft work per developer and subtask.
4. Predict and prevent merge conflicts/CI failures before integration.
5. Provide role-specific dashboards for developers and PM.

## Non-Goals (MVP)
- Full enterprise portfolio management across many business units.
- Autonomous merge/deploy without human approval.
- Deep financial/resource planning.
- Real-time reviewer intervention during implementation (post-MVP).

## Core Workflow (Required)
1. Task is submitted (PM or developer).
2. OA creates initial implementation plan from shared context.
3. OA may query local-agent capabilities for subtask fit.
4. PM collaborates with OA and must approve final plan.
5. OA assigns subtasks to team members and local agents.
6. Local agents produce drafts for assigned humans.
7. Humans edit/approve/finalize subtasks.
8. Reviewer Agent performs final pre-merge review for integration safety.

## Shared Context Model (MVP)
The platform maintains structured shared context in explicit markdown documents:
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/LOCAL_AGENTS.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`

Each file is platform-managed as canonical context, and API state is derived from the same schema.

## Functional Requirements

### FR-1 Context Ingestion and Normalization
- Ingest project/task/PR/CI/context data from GitHub and local-agent metadata/events.
- Normalize all entities into a unified internal model.

### FR-2 Local Agent Registry and Two-Way Sync
- Allow local agents to be uploaded/registered to platform.
- Store metadata: owner, capabilities, supported task types, version, heartbeat status.
- Support two-way sync between platform and local development:
  - Platform -> Local agent: assignments, task updates, plan/version changes.
  - Local agent -> Platform: draft submitted, task progress changed, human-approved/finalized state.
- Best-approach sync contract (MVP):
  - Local sync daemon/CLI runs on developer machine.
  - Outbound event API: local daemon posts events (`draft_created`, `developer_approved`, `subtask_completed`).
  - Inbound update API: daemon polls/streams for assignment updates.
  - Idempotency keys + monotonically increasing `event_version` prevent duplicates/out-of-order writes.
  - Conflict handling: if local and platform diverge, platform returns `409` with latest version; daemon rebases and retries.

### FR-3 Orchestration Planning
- OA generates implementation plan and team+agent assignment per task.
- OA can request additional local-agent capability details before finalizing recommendations.
- Plan is not executable until PM approval.

### FR-4 PM Approval Gate
- PM can review, edit, approve, or reject OA plan.
- Approved plan is versioned and auditable.

### FR-5 Execution and Drafting
- For each approved subtask, assigned local agent produces draft output.
- Human assignee can revise, approve, and mark subtask complete.
- Finalized local state must sync to platform via FR-2 two-way sync.

### FR-6 Reviewer Agent Governance
- Reviewer Agent runs final holistic review only when all subtasks are submitted.
- Reviewer output includes blocker/non-blocker findings and merge-readiness decision.
- PM can override blocker with explicit audit reason.

### FR-7 Developer Dashboard
- Task list + sub-actions per task.
- Detail panel: task goal, assigned agents, progress, errors, risks.
- Visual risk/progress graph per task.
- Big context mode: other project tasks, who/which agent works on what, project description, timeline.

### FR-8 PM Dashboard
- Projects overview: description, goals, milestones, timeline, GitHub references.
- Team members, current tasks, stage/progress, assigned agents.
- Critical delivery risk summary.

## Non-Functional Requirements
- Performance: dashboard APIs p95 < 700 ms for active project views.
- Freshness: context refresh and sync propagation < 2 minutes.
- Reliability: degraded mode if GitHub or local-agent source is temporarily unavailable.
- Explainability: OA/Reviewer recommendations include rationale.
- Security: role-based access (`pm`, `developer`, `admin`), audit logs for approvals/reviewer decisions.
- Scalability (MVP): multi-member teams (>= 4 contributors) per project.

## Acceptance Criteria
- [ ] PM can submit task and approve/reject OA plan before execution.
- [ ] OA can generate team-member + local-agent assignment plan using shared context.
- [ ] Local agent registry supports upload/registration and capability visibility.
- [ ] Local completion/approval on developer machine syncs back to platform state.
- [ ] Reviewer Agent performs final whole-task review and returns merge-readiness.
- [ ] Developer dashboard includes task details, risks/errors, and big context view.
- [ ] PM dashboard includes macro project status, team progress, and critical alerts.

## Test Strategy
- Unit tests:
  - planning/assignment constraints
  - PM approval gate and plan versioning
  - local sync event versioning/idempotency
  - reviewer final-gate decision logic
- Integration tests:
  - GitHub + local-agent ingestion and normalization
  - sync daemon APIs (outbound events + inbound updates)
  - full lifecycle: submit -> plan -> approve -> draft -> finalize -> final review
- End-to-end tests:
  - developer workflow (draft -> edit -> finalize -> sync)
  - PM workflow (plan approval -> final review -> merge decision)
- Non-functional checks:
  - API latency smoke tests
  - transient source outage resilience tests

## Open Clarifications
1. For local-agent upload, do you want metadata-only in MVP, or executable package upload too?
2. Should PM override of reviewer blocker require one additional human approver?
3. Do you want polling-only sync in MVP, or polling + websocket streaming?
