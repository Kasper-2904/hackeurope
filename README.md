# HackEurope: Software Team Orchestration Platform

## What This Project Is
A platform for software teams where a human PM collaborates with an Orchestration Agent to plan work, local agents draft subtasks for developers, and a Reviewer Agent performs a final integration-quality gate.

## Tech Stack
- Python (backend/API)
- React (web app)
- Claude SDK (agents)
- Lovable (UI prototyping and design acceleration)

## Data Sources
- GitHub
- Local agents (uploadable/registrable)

## Core Workflow
1. Task submitted by PM/developer.
2. OA generates team + local-agent plan from shared context.
3. PM reviews and approves plan.
4. Local agents draft subtasks.
5. Developers edit/finalize subtasks.
6. Reviewer Agent runs final whole-task review before merge.

## Shared Context Files (MVP)
- `docs/shared_context/PROJECT_OVERVIEW.md`
- `docs/shared_context/TEAM_MEMBERS.md`
- `docs/shared_context/LOCAL_AGENTS.md`
- `docs/shared_context/PROJECT_PLAN.md`
- `docs/shared_context/TEAM_CONTEXT.md`
- `docs/shared_context/TASK_GRAPH.md`
- `docs/shared_context/INTEGRATIONS_GITHUB.md`

## Dashboards
- Developer Dashboard:
  - task list and sub-actions
  - task detail panel (assigned agents, progress, errors, risks)
  - big-context mode for project-wide visibility
- PM Dashboard:
  - project overview (description, goals, milestones, timeline, GitHub)
  - team members and task stages/progress
  - critical alerts and final-review summary

## Team
- Kasper
- Martin
- Farhan
- Marin

## Core Docs
- `PROJECT_SPEC.md`: full requirements and acceptance criteria
- `ARCHITECTURE.md`: system design and component boundaries
- `TASKS.md`: milestone plan with parallel ownership across the 4-member team

## Development Note
Run `scripts/bootstrap_env.sh` before local development commands in this repo.
