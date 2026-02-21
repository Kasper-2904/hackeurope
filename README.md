# HackEurope: Software Team Orchestration Platform

## What This Project Is
A platform for software teams where a human PM collaborates with an Orchestration Agent to plan work, local agents draft subtasks for developers, and a Reviewer Agent guards against merge/CI risks.

## Data Sources
- GitHub
- Miro
- Local agents (uploadable/registrable)

## Core Workflow
1. Task submitted by PM/developer.
2. OA generates team + local-agent plan from shared context.
3. PM reviews and approves plan.
4. Local agents draft subtasks.
5. Developers edit/finalize subtasks.
6. Reviewer Agent monitors risks in real time and runs final gate.

## Dashboards
- Developer Dashboard:
  - task list and sub-actions
  - task detail panel (assigned agents, progress, errors, risks)
  - big-context mode for project-wide visibility
- PM Dashboard:
  - project overview (description, goals, milestones, timeline, GitHub)
  - team members and task stages/progress
  - critical alerts and risk summary

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
