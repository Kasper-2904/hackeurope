"""Service for calling hosted agent inference APIs."""

import os
from pathlib import Path
from typing import Any

import httpx
import litellm


# Skills directory path
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_skill_prompt(skill_name: str) -> str | None:
    """Load skill prompt from markdown file."""
    skill_file = SKILLS_DIR / f"{skill_name}.md"
    if skill_file.exists():
        return skill_file.read_text()
    return None


def get_available_skills() -> list[str]:
    """Get list of available skills from markdown files."""
    if not SKILLS_DIR.exists():
        return []
    return [f.stem for f in SKILLS_DIR.glob("*.md")]


class AgentInferenceService:
    """Calls hosted agent inference APIs (OpenAI-compatible or LiteLLM)."""

    def __init__(self):
        # Cache loaded skill prompts
        self._skill_cache: dict[str, str] = {}

    def _get_skill_prompt(self, skill_name: str) -> str | None:
        """Get skill prompt from cache or load from file."""
        if skill_name not in self._skill_cache:
            prompt = load_skill_prompt(skill_name)
            if prompt:
                self._skill_cache[skill_name] = prompt
        return self._skill_cache.get(skill_name)

    async def chat(
        self,
        agent: Any,
        message: str,
        conversation_history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Send a chat message to a hosted agent.

        Args:
            agent: Agent model with inference config
            message: User's message
            conversation_history: Previous messages
            system_prompt: System prompt (override or from agent)

        Returns:
            Agent's response
        """
        messages = []

        # Add system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add current message
        messages.append({"role": "user", "content": message})

        # Determine provider and call
        provider = agent.inference_provider or "custom"

        # Standard providers use LiteLLM
        # Custom/seller-hosted endpoints use direct HTTP calls with access token
        if provider in ("openai", "anthropic", "groq", "ollama"):
            return await self._call_litellm(agent, messages)
        else:
            # "custom", "openai-compatible", or any other provider
            return await self._call_custom_endpoint(agent, messages)

    async def _call_litellm(self, agent: Any, messages: list[dict]) -> str:
        """Call via LiteLLM for standard providers."""
        provider = agent.inference_provider
        model = agent.inference_model or "gpt-4o-mini"

        # Build model string
        if provider == "openai":
            model_str = model
        else:
            model_str = f"{provider}/{model}"

        # Get API key
        api_key = agent.inference_api_key_encrypted

        try:
            response = await litellm.acompletion(
                model=model_str,
                messages=messages,
                api_key=api_key,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Error calling agent: {e}"

    async def _call_custom_endpoint(self, agent: Any, messages: list[dict]) -> str:
        """
        Call seller-hosted OpenAI-compatible endpoint.

        Uses the seller's access token for authentication.
        """
        endpoint = agent.inference_endpoint
        access_token = agent.inference_api_key_encrypted  # Seller's access token
        model = agent.inference_model or "default"

        if not endpoint:
            return "Error: No inference endpoint configured for this agent"

        if not access_token:
            return "Error: No access token configured for this agent"

        # Build headers with seller's access token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Build request payload (OpenAI-compatible format)
        payload = {
            "model": model,
            "messages": messages,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{endpoint.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                return (
                    f"Error calling seller agent (HTTP {e.response.status_code}): {e.response.text}"
                )
            except httpx.RequestError as e:
                return f"Error connecting to seller agent at {endpoint}: {e}"
            except Exception as e:
                return f"Error calling seller agent: {e}"

    def _build_skill_user_prompt(self, skill: str, inputs: dict[str, Any]) -> str:
        """Build the user prompt with inputs for a skill."""
        # Format inputs into a readable string
        input_parts = []
        for key, value in inputs.items():
            if key == "code" and value:
                input_parts.append(f"**Code:**\n```\n{value}\n```")
            elif value:
                input_parts.append(f"**{key.replace('_', ' ').title()}:** {value}")

        if input_parts:
            return "\n\n".join(input_parts)
        return f"Execute skill '{skill}'"

    async def execute_skill(
        self,
        agent: Any,
        skill: str,
        inputs: dict[str, Any],
        system_prompt: str | None = None,
    ) -> str:
        """
        Execute a specific skill on the agent.

        Skills are loaded from markdown files in the skills directory.
        The markdown content becomes part of the system prompt.

        Args:
            agent: Agent model with inference config
            skill: Name of the skill to execute
            inputs: Input parameters for the skill
            system_prompt: Optional override for system prompt

        Returns:
            Agent's response
        """
        # Load skill prompt from markdown file
        skill_prompt = self._get_skill_prompt(skill)

        # Build the combined system prompt
        combined_system_prompt = ""

        # Start with agent's base system prompt if available
        if system_prompt:
            combined_system_prompt = system_prompt
        elif hasattr(agent, "system_prompt") and agent.system_prompt:
            combined_system_prompt = agent.system_prompt

        # Append skill-specific instructions from markdown
        if skill_prompt:
            if combined_system_prompt:
                combined_system_prompt += f"\n\n---\n\n{skill_prompt}"
            else:
                combined_system_prompt = skill_prompt

        # Build user message with inputs
        user_message = self._build_skill_user_prompt(skill, inputs)

        return await self.chat(
            agent,
            user_message,
            system_prompt=combined_system_prompt if combined_system_prompt else None,
        )


_inference_service: AgentInferenceService | None = None


def get_inference_service() -> AgentInferenceService:
    """Get singleton inference service."""
    global _inference_service
    if _inference_service is None:
        _inference_service = AgentInferenceService()
    return _inference_service
