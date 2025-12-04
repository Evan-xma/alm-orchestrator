"""Tests for label router and action interface."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.router import LabelRouter, UnknownLabelError
from alm_orchestrator.actions.base import BaseAction


class MockAction(BaseAction):
    """Test action implementation."""

    def __init__(self, prompts_dir: str = "/tmp/prompts"):
        super().__init__(prompts_dir)
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


class TestBaseAction:
    def test_label_property_is_abstract(self):
        # BaseAction cannot be instantiated directly
        with pytest.raises(TypeError):
            BaseAction("/tmp/prompts")

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
