"""Tests for label router and action interface."""

import pytest
from unittest.mock import MagicMock, patch
from alm_orchestrator.router import LabelRouter, UnknownLabelError, discover_actions
from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.output_validator import OutputValidator


class MockAction(BaseAction):
    """Test action implementation."""

    def __init__(self, prompts_dir: str = "/tmp/prompts"):
        super().__init__(prompts_dir, validator=MagicMock())
        self._label = "ai-mock"

    @property
    def label(self) -> str:
        return self._label

    def execute(self, issue, jira_client, github_client, claude_executor):
        return "Mock action executed"


class TestLabelRouter:
    def test_register_and_route(self):
        router = LabelRouter()
        action = MockAction()

        router.register("ai-investigate", action)
        result = router.get_action("ai-investigate")

        assert result is action

    def test_unknown_label_raises(self):
        router = LabelRouter()

        with pytest.raises(UnknownLabelError):
            router.get_action("unknown-label")

    def test_register_multiple_labels(self):
        router = LabelRouter()
        investigate = MockAction()
        impact = MockAction()

        router.register("ai-investigate", investigate)
        router.register("ai-impact", impact)

        assert router.get_action("ai-investigate") is investigate
        assert router.get_action("ai-impact") is impact

    def test_has_action(self):
        router = LabelRouter()
        action = MockAction()
        router.register("ai-investigate", action)

        assert router.has_action("ai-investigate") is True
        assert router.has_action("unknown") is False

    def test_action_count(self):
        router = LabelRouter()
        assert router.action_count == 0

        router.register("ai-investigate", MockAction())
        assert router.action_count == 1

        router.register("ai-impact", MockAction())
        assert router.action_count == 2

    def test_action_names(self):
        router = LabelRouter()
        assert router.action_names == []

        router.register("ai-investigate", MockAction())
        router.register("ai-impact", MockAction())

        names = router.action_names
        assert len(names) == 2
        assert "MockAction" in names


class TestBaseAction:
    def test_label_property_is_abstract(self):
        # BaseAction cannot be instantiated directly
        with pytest.raises(TypeError):
            BaseAction("/tmp/prompts", validator=MagicMock())

    def test_get_template_path(self):
        action = MockAction("/tmp/prompts")
        action._label = "ai-investigate"

        path = action.get_template_path()

        assert path == "/tmp/prompts/investigate.md"

    def test_get_template_path_with_underscores(self):
        action = MockAction("/tmp/prompts")
        action._label = "ai-code-review"

        path = action.get_template_path()

        assert path == "/tmp/prompts/code-review.md"


class TestDiscoverActionsWithValidator:
    def test_validator_passed_to_actions(self):
        """Actions are instantiated with validator."""
        validator = OutputValidator()

        # Use the real discover_actions with actual actions
        # This is an integration test that verifies the validator is passed through
        router = discover_actions("/tmp/prompts", validator=validator)

        # Get one of the real actions and verify it has a validator
        # We know at least one action exists in the actions directory
        assert router.action_count > 0

        # Get the first action and check it has the validator
        first_label = list(router._actions.keys())[0]
        first_action = router.get_action(first_label)

        # Verify the action has a validator attribute and it's the one we passed
        assert hasattr(first_action, '_validator')
        assert first_action._validator is validator
