# Project Spec: Team Orchestration Platform for Software Delivery

## Problem Statement
Software teams lose time because project context is fragmented across tools and people, task ownership is unclear, and delivery risks (merge conflicts, CI failures) are found too late.

## Product Vision
A web platform for software teams where an Orchestration Agent (OA), human Project Manager (PM), developers, local agents, and a Reviewer Agent collaborate through a shared structured context.

The platform merges data from:
- GitHub
- Miro
- Local agents (uploadable/registrable into the platform)

## Primary Users
- Project Manager (human in the loop): collaborates with OA and approves implementation plans.
- Developer: receives subtask drafts from local agents, edits, approves, and finalizes work.
- Reviewer Agent: monitors delivery in real time and performs final quality/risk gate.

## Product Goals
1. Centralize team/project context into a single shared, structured context.
2. Plan and distribute tasks with OA, with PM approval before execution.
3. Enable local agents to draft work per developer and subtask.
4. Predict and prevent merge conflicts/CI failures before integration.
5. Provide role-specific dashboards for developers and PM.

## Non-Goals (MVP)
- Full enterprise portfolio management across many business units.
- Autonomous merge/deploy without human approval.
- Deep financial/resource planning.

## Core Workflow (Required)
1. Task is submitted (PM or developer).
2. OA creates initial implementation plan from shared context.
3. OA may query local agents for capability/context fit on subtasks.
4. PM collaborates with OA and must approve final plan.
5. OA assigns subtasks to team members and local agents.
6. Local agents produce drafts for assigned humans.
7. Humans edit/approve/finalize subtasks.
8. Reviewer Agent monitors in real time and flags risks early.
9. Reviewer Agent performs final pre-merge review for integration safety.

## Shared Context Model (MVP)
The platform must maintain a structured shared context containing at least:
- Team members on project (role, capacity, current load)
- Registered local agents per team member
- Local agent capability summaries
- Links to local agent context files (detailed behavior/constraints)
- Project plan, milestones, timeline
- Team member context (skills, ownership, historical activity)
- Task graph (dependencies, status, blockers, risk)
- GitHub + Miro references

## Functional Requirements

### FR-1 Context Ingestion and Normalization
- Ingest project/task/PR/CI/context data from GitHub, Miro, and local-agent metadata.
- Normalize all entities into a unified internal model.

### FR-2 Local Agent Registry
- Allow local agents to be uploaded/registered to the platform.
- Store metadata: owner, capabilities, supported task types, context-file links, status.

### FR-3 Orchestration Planning
- OA generates implementation plan and team+agent assignment per task.
- OA can request additional local-agent context before finalizing recommendations.
- Plan is not executable until PM approval.

### FR-4 PM Approval Gate
- PM can review, edit, approve, or reject OA plan.
- Approved plan is versioned and auditable.

### FR-5 Execution and Drafting
- For each approved subtask, assigned local agent produces draft output.
- Human assignee can revise, approve, and mark subtask complete.

### FR-6 Reviewer Agent Governance
- Real-time monitoring for merge-conflict risk, CI risk, and integration risk.
- Final holistic review when all subtasks are submitted.
- Blocking warnings when predicted merge/CI failures exceed threshold.

### FR-7 Developer Dashboard
- Task list + sub-actions per task.
- Detail panel with: task goal, assigned agents, progress, errors, and risks.
- Visual risk/progress graph per task.
- Big context mode with: other project tasks, who/which agent works on what, project description, historical timeline.

### FR-8 PM Dashboard
- Projects overview with: description, goals, milestones, timeline, GitHub references.
- Team members, current tasks, stage/progress, assigned agents.
- Critical alerts and delivery risk summary.

## Non-Functional Requirements
- Performance: dashboard APIs p95 < 700 ms for active project views.
- Freshness: shared context refresh and risk recompute within 2 minutes.
- Reliability: degraded mode if one source (GitHub/Miro/local agent) is temporarily unavailable.
- Explainability: all OA/Reviewer recommendations include rationale.
- Security: role-based access (`pm`, `developer`, `admin`), audit logs for plan approvals and final reviews.
- Scalability (MVP target): multi-member teams (>= 4 contributors) per project.

## Acceptance Criteria
- [ ] PM can submit task and approve/reject OA plan before execution.
- [ ] OA can generate team-member + local-agent assignment plan using shared context.
- [ ] Local agent registry supports upload/registration and capability visibility.
- [ ] Developer can receive local-agent draft, edit it, and finalize subtask.
- [ ] Reviewer Agent flags high-risk merge/CI cases before final integration.
- [ ] Developer dashboard includes task details, risks/errors, and big context view.
- [ ] PM dashboard includes macro project status, team progress, and critical alerts.

## Test Strategy
- Unit tests:
  - planning/assignment scoring and constraints
  - PM approval gate and plan versioning logic
  - reviewer risk scoring thresholds
- Integration tests:
  - GitHub/Miro/local-agent ingestion and normalization
  - end-to-end task lifecycle from submit -> approve -> execute -> review
- End-to-end tests:
  - developer workflow (draft -> edit -> finalize)
  - PM workflow (plan review/approval and critical-risk handling)
- Non-functional checks:
  - API latency smoke tests
  - source outage resilience tests

## Open Clarifications
1. Should local-agent upload accept executable bundles, metadata manifests, or both?
2. Should Reviewer Agent be allowed to hard-block merge, or only request PM override?
3. For MVP, should PM be one user role or multiple leads per project?
