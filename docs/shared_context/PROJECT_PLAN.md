# Project Plan

## Milestones

### M1: Foundation (Week 1-2) — COMPLETED
- User auth + JWT token management
- Team + project CRUD
- Database schema + migrations
- GitHub OAuth integration

### M2: Core Agent Pipeline (Week 3-4) — COMPLETED
- LangGraph orchestrator: analyze -> select -> execute -> aggregate
- Specialist agent inference via litellm (Anthropic, Crusoe, OpenAI-compatible)
- Reviewer Agent with direct Anthropic SDK
- Event bus for internal pub/sub

### M3: Billing & Marketplace (Week 5-6) — COMPLETED
- Stripe seat-based subscriptions
- Paid.ai usage metering per agent call
- Agent marketplace with public/private listings
- Seller profiles + payout tracking

### M4: Integration & QA (Week 7-8) — IN PROGRESS
- GitHub context sync (PRs, commits, CI status)
- Shared context auto-refresh on every sync
- End-to-end orchestration tests
- Seed scripts for reproducible demo data

### M5: Polish & Demo (Week 9) — IN PROGRESS
- Start button plan-first flow with rich plan review card
- Context Explorer for viewing/editing shared context
- Connections page for GitHub/Stripe/Paid/Slack integrations
- Token usage billing dashboard
- Demo prep + Devpost submission

## Task Breakdown

| Task | Status | Agent | Owner |
|------|--------|-------|-------|
| User Authentication API | Completed | Claude Code Assistant | Bob |
| Product Catalog Component | In Progress | Claude Frontend Expert | Charlie |
| Security Audit: Payment Module | Pending Approval | Claude Security Reviewer | Bob |
| CI/CD Pipeline Setup | Assigned | DevOps Pro Agent | Bob |
| Shopping Cart + Checkout Flow | Pending | — | Unassigned |
| Search & Filter API | Pending | — | Unassigned |
| Admin Dashboard Analytics | Pending | — | Unassigned |
| Performance Load Testing | Pending | — | Unassigned |

## Dependency Notes
- Product Catalog must be finalized before Shopping Cart can begin (shared product data model)
- Security Audit should complete before any payment endpoints go to production
- CI/CD pipeline is a prerequisite for staging deployments
- Search API depends on the product data model finalized in the Catalog task

## Approval Notes
- All plans require PM approval before agent execution begins
- Security-related tasks require additional review from Claude Security Reviewer
- Infrastructure tasks (CI/CD, deployment) need admin sign-off
