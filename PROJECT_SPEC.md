# Project Spec: Team Orchestration Platform for Software Delivery

## Problem Statement
Software teams lose time because project context is fragmented, task ownership is unclear, and delivery risks (merge conflicts, CI failures) are found too late.

## Product Vision
A web platform where an Orchestration Agent (OA), human Project Manager (PM), developers, MCP-connected specialist agents, and a Reviewer Agent collaborate through one shared structured context.

The platform merges data from:
- GitHub
- Agent execution state from MCP-connected agents

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
3. Execute subtasks using MCP-connected specialist agents selected for the project.
4. Predict and prevent merge conflicts/CI failures before integration.
5. Offer an Agent Marketplace where teams can use public agents or create their own.
6. Monetize with seat-based subscriptions plus usage-based agent charging.

## Non-Goals (MVP)
- Full enterprise portfolio management across many business units.
- Autonomous merge/deploy without human approval.
- Real-time reviewer intervention during implementation (post-MVP).

## Core Workflow (Required)
1. Task is submitted (PM or developer).
2. OA analyzes task + shared context.
3. OA selects a specialist agent (not a person) to execute the task draft.
4. OA provides execution plan + suggested team-member assignment for PM review.
5. PM approves assignment/plan or reassigns to a different team member.
6. Specialist agent produces a 70% draft (real code/research/output).
7. Assigned team member completes the final 30% and commits to GitHub.
8. GitHub commit is detected; Reviewer Agent analyzes consistency/conflicts and updates shared context.
9. Project context is enriched from outcomes so future agent runs improve.

## Implementation Snapshot (Current)
- Implemented:
  - Auth, users, teams, projects, tasks, plans, subtasks, risks, dashboards APIs
  - GitHub ingestion/sync endpoints and backend tests
  - Marketplace and billing API scaffolding (Stripe/Paid.ai integrations)
  - MCP client manager for agent connection/capability routing
- In progress / partial:
  - OA 70/30 specialist draft flow end-to-end enforcement
  - Commit-triggered reviewer automation and full conflict analysis pipeline
  - Frontend feature completeness for PM/developer workflows

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
- Register/manage MCP-connected specialist agents in platform.
- PM selects which agents are available per project.
- Store metadata: owner/team, capabilities, supported task types, version, status, cost profile.

### FR-3 Agent Marketplace
- Teams can browse available agents in marketplace.
- Teams can create new agents.
- Agent creators can publish agents as public or keep private.
- Public agents are available for other teams to attach to projects.

### FR-4 Orchestration Planning
- OA generates implementation plan by first selecting a specialist hosted agent.
- OA produces draft + suggested team-member assignment for PM decision.
- Plan is not executable until PM approval.

### FR-5 PM Approval Gate
- PM can review, edit, approve, or reject OA plan.
- Approved plan is versioned and auditable.

### FR-6 Execution and Drafting
- For each approved task, specialist hosted agent produces a 70% draft output.
- Human assignee completes the remaining 30%, then commits to GitHub.
- Draft provenance is stored (agent ID, version, timestamp, run metadata).

### FR-7 Reviewer Agent Governance
- Reviewer Agent runs on GitHub commit detection.
- Reviewer checks consistency with other tasks and conflicts with in-flight work.
- Reviewer updates shared context with findings, decisions, and learned patterns.
- Reviewer output includes blocker/non-blocker findings and merge-readiness decision.
- PM can override blocker with explicit audit reason.

### FR-8 Developer Dashboard
- Task list + sub-actions per task.
- Detail panel: task goal, assigned agents, progress, errors, risks.
- Visual risk/progress graph per task.
- Big context mode: other project tasks, who/which agent works on what, project description, timeline.
- Agent Marketplace access: browse available agents and view agent capabilities/pricing before PM selection.

### FR-9 PM Dashboard
- Projects overview: description, goals, milestones, timeline, GitHub references.
- Team members, current tasks, stage/progress, selected agents.
- Critical delivery risk summary.
- Agent Marketplace management: discover agents, approve project-allowed agents, and manage public/private usage policy per project.

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
- [ ] Hosted agents produce 70% drafts tied to agent/version metadata.
- [ ] Reviewer Agent is triggered by GitHub commit and returns merge-readiness with context updates.
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
  - full lifecycle: submit -> specialist draft -> PM assignment approval -> human complete -> commit review
  - Stripe subscription webhooks and seat updates
  - Paid.ai usage event reporting
- End-to-end tests:
  - developer workflow (receive 70% draft -> complete 30% -> commit)
  - PM workflow (agent selection -> assignment approval/reassign -> review outcome)
  - billing workflow (subscribe -> consume agent usage -> view charges)
- Non-functional checks:
  - API latency smoke tests
  - transient dependency outage resilience tests

## Open Clarifications
1. Should public agents require manual moderation before marketplace listing?
2. Should PM override of reviewer blocker require one additional human approver?
3. Which billing granularity for Paid.ai MVP: per agent run, per task, or both?
