You are a feature agent implementing `M2-T4 PM Dashboard UI`.

Scope:
- Implement only `M2-T4-ST1` to `M2-T4-ST6` from `docs/plans/M2-T4_IMPLEMENTATION_PLAN.md`.

Mandatory execution rules:
- Work on branch `marin-m2-t4-pm-dashboard-ui`.
- Do not commit on `main`.
- Follow `AGENTS.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `TESTING.md`.

Implementation requirements:
- Implement PM dashboard flows to satisfy M2-T4 acceptance criteria in `TASKS.md`.
- Deliver PM UI for project goals/progress and plan approval gates.
- Implement PM agent allowlist management end-to-end (backend + frontend), without silent architecture contract changes.
- Include loading/error/empty states and deterministic behavior.

Constraints:
- Keep changes scoped to M2-T4 only.
- Do not silently change unrelated architecture contracts.
- Update `TASKS.md` only for completed M2-T4 status/notes, and do not change unrelated items.

Definition of done for this run:
- `M2-T4-ST1` to `M2-T4-ST6` implemented.
- Handoff notes include touched files, command outputs, and unresolved blockers.
