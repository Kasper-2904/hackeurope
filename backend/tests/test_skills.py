"""Unit tests for skills loading and agent inference service."""

import pytest
from pathlib import Path

from src.services.agent_inference import (
    AgentInferenceService,
    get_available_skills,
    get_inference_service,
    load_skill_prompt,
    SKILLS_DIR,
)


class TestSkillsLoading:
    """Tests for skills loading from markdown files."""

    def test_skills_directory_exists(self):
        """Verify the skills directory exists."""
        assert SKILLS_DIR.exists(), f"Skills directory not found: {SKILLS_DIR}"
        assert SKILLS_DIR.is_dir(), f"Skills path is not a directory: {SKILLS_DIR}"

    def test_get_available_skills_returns_list(self):
        """Verify get_available_skills returns a non-empty list."""
        skills = get_available_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0, "No skills found"

    def test_expected_skills_are_available(self):
        """Verify all expected skills are available."""
        expected_skills = [
            "generate_code",
            "review_code",
            "debug_code",
            "refactor_code",
            "explain_code",
            "design_component",
            "check_security",
            "suggest_improvements",
        ]
        available = get_available_skills()

        for skill in expected_skills:
            assert skill in available, f"Expected skill '{skill}' not found"

    def test_load_skill_prompt_returns_content(self):
        """Verify load_skill_prompt returns markdown content."""
        content = load_skill_prompt("generate_code")
        assert content is not None, "Failed to load generate_code skill"
        assert isinstance(content, str)
        assert len(content) > 0
        assert "# Generate Code Skill" in content

    def test_load_skill_prompt_returns_none_for_unknown(self):
        """Verify load_skill_prompt returns None for unknown skills."""
        content = load_skill_prompt("nonexistent_skill")
        assert content is None

    def test_all_skill_files_are_valid_markdown(self):
        """Verify all skill files contain valid markdown with expected sections."""
        skills = get_available_skills()

        for skill in skills:
            content = load_skill_prompt(skill)
            assert content is not None, f"Failed to load skill: {skill}"
            # Each skill should have a header
            assert content.startswith("#"), f"Skill '{skill}' doesn't start with markdown header"
            # Each skill should have instructions
            assert "## " in content, f"Skill '{skill}' missing sections"


class TestAgentInferenceService:
    """Tests for AgentInferenceService."""

    def test_get_inference_service_returns_singleton(self):
        """Verify get_inference_service returns a singleton."""
        service1 = get_inference_service()
        service2 = get_inference_service()
        assert service1 is service2, "Service is not a singleton"

    def test_inference_service_has_skill_cache(self):
        """Verify service has skill caching capability."""
        service = AgentInferenceService()
        assert hasattr(service, "_skill_cache")
        assert isinstance(service._skill_cache, dict)

    def test_get_skill_prompt_caches_result(self):
        """Verify _get_skill_prompt caches loaded skills."""
        service = AgentInferenceService()

        # First load
        content1 = service._get_skill_prompt("generate_code")
        assert content1 is not None

        # Check cache
        assert "generate_code" in service._skill_cache

        # Second load should come from cache
        content2 = service._get_skill_prompt("generate_code")
        assert content1 == content2

    def test_build_skill_user_prompt_formats_inputs(self):
        """Verify _build_skill_user_prompt formats inputs correctly."""
        service = AgentInferenceService()

        # Test with code input
        inputs = {"code": "def hello(): pass", "language": "python"}
        prompt = service._build_skill_user_prompt("review_code", inputs)

        assert "**Code:**" in prompt
        assert "def hello(): pass" in prompt
        assert "**Language:**" in prompt

    def test_build_skill_user_prompt_handles_empty_inputs(self):
        """Verify _build_skill_user_prompt handles empty inputs."""
        service = AgentInferenceService()

        prompt = service._build_skill_user_prompt("generate_code", {})
        assert "Execute skill 'generate_code'" in prompt


class TestSkillMarkdownContent:
    """Tests for specific skill markdown content."""

    @pytest.mark.parametrize(
        "skill,expected_sections",
        [
            ("generate_code", ["Instructions", "Input Parameters", "Output Format"]),
            ("review_code", ["Instructions", "Review Checklist", "Output Format"]),
            ("debug_code", ["Instructions", "Debugging Process", "Output Format"]),
            ("check_security", ["OWASP Top 10", "Additional Checks"]),
        ],
    )
    def test_skill_has_expected_sections(self, skill, expected_sections):
        """Verify each skill has expected sections in its markdown."""
        content = load_skill_prompt(skill)
        assert content is not None

        for section in expected_sections:
            assert section in content, f"Skill '{skill}' missing section: {section}"
