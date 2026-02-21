# Project Spec: Team Orchestration Platform for Software Delivery

## Problem Statement
Software teams lose time because project context is fragmented, task ownership is unclear, and delivery risks (merge conflicts, CI failures) are found too late.

## Product Vision
A web platform where an Orchestration Agent (OA), human Project Manager (PM), developers, hosted autonomous agents, and a Reviewer Agent collaborate through one shared structured context.

The platform merges data from:
- GitHub
- Platform-hosted agents and task execution state

## Primary Users
- Project Manager (human in the loop): collaborates with OA, selects project agents, and approves implementation plans.
- Developer: receives agent-produced drafts, edits, approves, and finalizes subtasks.
- Reviewer Agent: performs final quality/risk gate on whole task after subtasks are done.
- Team Admin: manages subscription, seats, and billing visibility.

## Tech Stack (MVP)
- Backend/API: Python
- Frontend: React
- Agent SDK: Claude SDK (Anthropic)
- UI acceleration/prototyping: Lovable
- Payments: Stripe (seat-based subscription)
- Agent usage pricing: Paid.ai

## Product Goals
1. Centralize team/project context into a single structured context.
2. Plan and distribute tasks with OA, with PM approval before execution.
3. Execute subtasks using platform-hosted autonomous agents selected for the project.
4. Predict and prevent merge conflicts/CI failures before integration.
5. Offer an Agent Marketplace where teams can use public agents or create their own.
6. Monetize with seat-based subscriptions plus usage-based agent charging.

## Non-Goals (MVP)
- Full enterprise portfolio management across many business units.
- Autonomous merge/deploy without human approval.
- Real-time reviewer intervention during implementation (post-MVP).

## Core Workflow (Required)
1. Task is submitted (PM or developer).
2. OA creates initial implementation plan from shared context.
3. OA may query hosted-agent capabilities for subtask fit.
4. PM collaborates with OA and must approve final plan.
5. OA assigns subtasks to hosted agents selected for the project.
6. Hosted autonomous agents produce drafts for assigned humans.
7. Humans edit/approve/finalize subtasks locally.
8. Reviewer Agent performs final pre-merge review for integration safety.

## Task Ownership Rule
- One task is assigned to exactly one team member.
- A task can contain multiple subtasks, but task-level ownership remains singular.

## Shared Context Model (MVP)
The platform maintains structured shared context in explicit markdown documents:
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/HOSTED_AGENTS.md`
- `docs/shared_context/AGENT_MARKETPLACE.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`
- `docs/shared_context/BILLING_SUBSCRIPTIONS.md`

## Functional Requirements

### FR-1 Context Ingestion and Normalization
- Ingest project/task/PR/CI/context data from GitHub and platform execution state.
- Normalize all entities into a unified internal model.

### FR-2 Hosted Agent Registry and Project Agent Selection
- Register/manage hosted agents in platform (no local agents in MVP).
- PM selects which agents are available per project.
- Store metadata: owner/team, capabilities, supported task types, version, status, cost profile.

### FR-3 Agent Marketplace
- Teams can browse available agents in marketplace.
- Teams can create new agents.
- Agent creators can publish agents as public or keep private.
- Public agents are available for other teams to attach to projects.

### FR-4 Orchestration Planning
- OA generates implementation plan and team+agent assignment per task.
- OA can request additional capability details from hosted agents before finalizing.
- Plan is not executable until PM approval.

### FR-5 PM Approval Gate
- PM can review, edit, approve, or reject OA plan.
- Approved plan is versioned and auditable.

### FR-6 Execution and Drafting
- For each approved subtask, assigned hosted agent produces draft output.
- Human assignee can revise, approve, and mark subtask complete.
- Draft provenance is stored (agent ID, version, timestamp, run metadata).

### FR-7 Reviewer Agent Governance
- Reviewer Agent runs final holistic review only when all subtasks are submitted.
- Reviewer output includes blocker/non-blocker findings and merge-readiness decision.
- PM can override blocker with explicit audit reason.

### FR-8 Developer Dashboard
- Task list + sub-actions per task.
- Detail panel: task goal, assigned agents, progress, errors, risks.
- Visual risk/progress graph per task.
- Big context mode: other project tasks, who/which agent works on what, project description, timeline.

### FR-9 PM Dashboard
- Projects overview: description, goals, milestones, timeline, GitHub references.
- Team members, current tasks, stage/progress, selected agents.
- Critical delivery risk summary.

### FR-10 Stripe Subscription Billing
- Seat-based subscription per team/workspace.
- Stripe checkout + subscription lifecycle handling (create, update, cancel).
- Seat count controls access limits and provisioning.

### FR-11 Paid.ai Usage Billing
- Track agent usage events per run/task.
- Send usage/value metrics to Paid.ai for pricing/billing computation.
- Show usage and cost attribution per project/team/agent.

### FR-12 Claude-Powered Reasoning
- OA and Reviewer logic must use Claude API/SDK for reasoning and analysis.
- Preserve deterministic validation/guardrails around model outputs.

## Non-Functional Requirements
- Performance: dashboard APIs p95 < 700 ms for active project views.
- Freshness: context and orchestration state refresh < 2 minutes.
- Reliability: degraded mode if GitHub, Stripe, or Paid.ai is temporarily unavailable.
- Explainability: OA/Reviewer recommendations include rationale.
- Security: role-based access (`pm`, `developer`, `admin`), audit logs for approvals/reviewer decisions/billing actions.
- Scalability (MVP): multi-member teams (>= 4 contributors) per project.

## Acceptance Criteria
- [ ] PM can submit task and approve/reject OA plan before execution.
- [ ] OA can generate team-member + hosted-agent assignment plan using shared context.
- [ ] One task is always assigned to exactly one team member.
- [ ] Marketplace supports private/public agent lifecycle and project-level selection.
- [ ] Hosted agents produce drafts tied to agent/version metadata.
- [ ] Reviewer Agent performs final whole-task review and returns merge-readiness.
- [ ] Stripe seat subscription flow is functional for team onboarding.
- [ ] Paid.ai usage reporting is functional for agent-run pricing.
- [ ] Developer and PM dashboards expose required execution/risk/billing context.

## Test Strategy
- Unit tests:
  - task ownership constraints (one task -> one member)
  - OA planning constraints and agent selection
  - reviewer final-gate decision logic
  - billing adapters (Stripe + Paid.ai payload validation)
- Integration tests:
  - GitHub ingestion and normalization
  - marketplace flows (create/publish/select agent)
  - full lifecycle: submit -> plan -> approve -> draft -> finalize -> final review
  - Stripe subscription webhooks and seat updates
  - Paid.ai usage event reporting
- End-to-end tests:
  - developer workflow (draft -> edit -> finalize)
  - PM workflow (agent selection -> approval -> final review)
  - billing workflow (subscribe -> consume agent usage -> view charges)
- Non-functional checks:
  - API latency smoke tests
  - transient dependency outage resilience tests

## Open Clarifications
1. Should public agents require manual moderation before marketplace listing?
2. Should PM override of reviewer blocker require one additional human approver?
3. Which billing granularity for Paid.ai MVP: per agent run, per task, or both?
