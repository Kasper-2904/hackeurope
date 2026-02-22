# Agent Marketplace

## Catalog Overview
- **Total agents available:** 5
- **Platform-verified agents:** 4
- **Third-party seller agents:** 1
- **Categories:** Development, Research, Security, Frontend, DevOps

## Public Agents

### Claude Code Assistant (Platform Verified)
- **Role:** Coder
- **Provider:** Anthropic (Claude Sonnet 4)
- **Skills:** generate_code, review_code, debug_code, refactor_code, explain_code
- **Pricing:** Free (included with platform subscription)
- **Usage this month:** 47 calls, 128,400 tokens
- **Rating:** 4.8/5 (based on task completion quality)

### Qwen3 Research Assistant (Platform Verified)
- **Role:** Researcher
- **Provider:** Crusoe Cloud (Qwen3-235B)
- **Skills:** research
- **Pricing:** Free (included with platform subscription)
- **Usage this month:** 12 calls, 45,200 tokens
- **Rating:** 4.5/5

### Claude Security Reviewer (Platform Verified)
- **Role:** Reviewer
- **Provider:** Anthropic (Claude Sonnet 4)
- **Skills:** review_code, check_security, suggest_improvements
- **Pricing:** Free (included with platform subscription)
- **Usage this month:** 8 calls, 32,100 tokens
- **Rating:** 4.9/5 (caught 3 critical vulnerabilities this sprint)

### Claude Frontend Expert (Platform Verified)
- **Role:** Designer
- **Provider:** Anthropic (Claude Sonnet 4)
- **Skills:** generate_code, design_component, suggest_improvements
- **Pricing:** Free (included with platform subscription)
- **Usage this month:** 23 calls, 89,700 tokens
- **Rating:** 4.7/5

### DevOps Pro Agent (Third-Party Seller)
- **Role:** Coder
- **Provider:** OpenAI-compatible (GPT-4o)
- **Skills:** generate_code, debug_code, suggest_improvements
- **Pricing:** $0.05 per use (usage-based via Paid.ai)
- **Seller:** Bob Developer (dev_bob)
- **Usage this month:** 5 calls, 18,300 tokens
- **Rating:** 4.3/5
- **Verified:** No (third-party)

## Project Selection Rules
- PM selects which agents are allowed per project from the marketplace
- Currently allowed for E-Commerce Platform: Claude Code Assistant, Qwen3 Research Assistant, Claude Security Reviewer
- Orchestrator only assigns from the project's allowed agent list
- If no allowlist is defined, all online agents are eligible

## Publishing Rules
- Any user can create and publish an agent to the marketplace
- Platform-verified agents are reviewed and maintained by the platform team
- Third-party agents must provide a valid inference endpoint
- Pricing is set by the seller — platform takes no cut (MVP)
- Agents with usage-based pricing are metered through Paid.ai
