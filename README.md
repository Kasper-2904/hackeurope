# HackEurope: Software Team Orchestration Platform

## What This Project Is
A platform for software teams where a human PM collaborates with an Orchestration Agent to plan work, hosted autonomous agents draft subtasks, and a Reviewer Agent performs a final integration-quality gate.

## HackEurope Challenge Alignment
- Anthropic: Claude-powered orchestration, reasoning, and review.
- Stripe: seat-based subscription billing.
- Paid.ai: usage-based agent pricing and value measurement.

## Tech Stack
- Python (backend/API)
- React (web app)
- Claude SDK (agents)
- Lovable (UI prototyping and design acceleration)
- Stripe (subscriptions)
- Paid.ai (agent usage pricing)

## Data Sources
- GitHub
- Platform-hosted agent execution data

## Docker Standard (Team)
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Dummy agents:
  - `http://localhost:8001`
  - `http://localhost:8002`
  - `http://localhost:8003`

Run all services:
```bash
docker compose up --build
```

## Core Workflow
1. Task submitted by PM/developer.
2. OA analyzes task + shared context and selects a specialist agent.
3. Specialist agent produces a 70% draft and OA suggests team-member assignment.
4. PM reviews and approves/reassigns the suggested owner.
5. Team member completes final 30% and commits to GitHub.
6. Reviewer Agent runs on commit detection, checks conflicts/consistency, and updates shared context.

## Agent Marketplace
- Teams can browse public agents.
- Teams can create custom agents.
- Agent creators can publish agents publicly for other teams or keep them private.
- PM selects project-allowed agents from the marketplace/catalog.

## Shared Context Files (MVP)
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/HOSTED_AGENTS.md`
- `docs/shared_context/AGENT_MARKETPLACE.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`
- `docs/shared_context/BILLING_SUBSCRIPTIONS.md`

## Key Rule
- One task is assigned to exactly one team member.

## Team
- Kasper
- Martin
- Farhan
- Marin

## Core Docs
- `PROJECT_SPEC.md`: full requirements and acceptance criteria
- `ARCHITECTURE.md`: system design and component boundaries
- `TASKS.md`: milestone plan with parallel ownership across the 4-member team
- `AGENTS.md`: shared team operating rules
- `TESTING.md`: shared unit-test standard
