"""Tests for BaseAction validation."""

import pytest
from unittest.mock import MagicMock
from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.output_validator import OutputValidator, ValidationResult


class ConcreteAction(BaseAction):
    """Concrete implementation for testing."""

    def __init__(self, prompts_dir: str):
        # Pass a dummy validator for testing
        super().__init__(prompts_dir, validator=None)

    @property
    def label(self) -> str:
        return "ai-test"

    @property
    def allowed_issue_types(self) -> list[str]:
        return ["Bug"]

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        return "executed"


class TestValidateIssueType:
    def test_valid_issue_type_returns_true(self):
        """Valid issue type returns True without posting comment."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Bug"

        mock_jira = MagicMock()

        action = ConcreteAction(prompts_dir="/tmp/prompts")
        result = action.validate_issue_type(mock_issue, mock_jira)

        assert result is True
        mock_jira.add_comment.assert_not_called()
        mock_jira.remove_label.assert_not_called()

    def test_invalid_issue_type_returns_false_and_posts_comment(self, caplog):
        """Invalid issue type returns False, posts comment, removes label, logs DEBUG."""
        import logging
        caplog.set_level(logging.DEBUG)

        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Story"

        mock_jira = MagicMock()

        action = ConcreteAction(prompts_dir="/tmp/prompts")
        result = action.validate_issue_type(mock_issue, mock_jira)

        assert result is False

        # Verify comment was posted
        mock_jira.add_comment.assert_called_once()
        comment_args = mock_jira.add_comment.call_args[0]
        assert comment_args[0] == "TEST-123"
        assert "INVALID ISSUE TYPE" in comment_args[1]
        assert "ai-test" in comment_args[1]
        assert "Bug" in comment_args[1]
        assert "Story" in comment_args[1]

        # Verify label was removed
        mock_jira.remove_label.assert_called_once_with("TEST-123", "ai-test")

        # Verify DEBUG log
        assert any(
            "Rejecting TEST-123" in record.message
            and "Story" in record.message
            for record in caplog.records
            if record.levelno == logging.DEBUG
        )


class NoValidationAction(BaseAction):
    """Action with no issue type validation."""

    def __init__(self, prompts_dir: str):
        # Pass a dummy validator for testing
        super().__init__(prompts_dir, validator=None)

    @property
    def label(self) -> str:
        return "ai-novalidation"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        return "executed"


class TestValidateIssueTypeNoValidation:
    def test_empty_allowed_list_returns_true(self):
        """Empty allowed_issue_types returns True for any issue type."""
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.issuetype.name = "Epic"

        mock_jira = MagicMock()

        action = NoValidationAction(prompts_dir="/tmp/prompts")
        result = action.validate_issue_type(mock_issue, mock_jira)

        assert result is True
        mock_jira.add_comment.assert_not_called()
        mock_jira.remove_label.assert_not_called()


class ValidatorTestAction(BaseAction):
    """Action for testing validator integration."""

    def __init__(self, prompts_dir: str):
        # Pass a dummy validator for testing (will be set manually in tests)
        super().__init__(prompts_dir, validator=None)

    @property
    def label(self) -> str:
        return "ai-validatortest"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        return "executed"


class TestValidateAndPost:
    def test_posts_valid_response(self):
        """Valid response is posted to Jira."""
        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=True,
            failure_reason=""
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action._validate_and_post(
            issue_key="TEST-123",
            response="The bug is in auth.py",
            action_type="investigate",
            jira_client=mock_jira
        )

        assert result is True
        mock_validator.validate.assert_called_once_with(
            "The bug is in auth.py",
            "investigate"
        )
        mock_jira.add_comment.assert_called_once_with(
            "TEST-123",
            "The bug is in auth.py"
        )

    def test_blocks_invalid_response(self, caplog):
        """Invalid response is blocked and warning posted."""
        import logging
        caplog.set_level(logging.WARNING)

        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=False,
            failure_reason="credential_detected"
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action._validate_and_post(
            issue_key="TEST-456",
            response="Found key: AKIAIOSFODNN7EXAMPLE",
            action_type="investigate",
            jira_client=mock_jira
        )

        assert result is False

        # Verify validator was called
        mock_validator.validate.assert_called_once()

        # Verify warning comment was posted
        assert mock_jira.add_comment.call_count == 1
        call_args = mock_jira.add_comment.call_args[0]
        assert call_args[0] == "TEST-456"
        assert "AI RESPONSE BLOCKED" in call_args[1]
        assert "flagged by automated security checks" in call_args[1]

        # Verify original response was NOT posted
        assert "AKIAIOSFODNN7EXAMPLE" not in str(mock_jira.add_comment.call_args_list)

        # Verify warning was logged
        assert any(
            "Suspicious response for TEST-456" in record.message
            and "credential_detected" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )


class TestValidateInputs:
    def test_safe_inputs_return_true(self):
        """Safe inputs pass validation."""
        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=True, failure_reason=""
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action.validate_inputs(
            "TEST-123", mock_jira,
            summary="Fix the login bug",
            description="Users cannot log in"
        )

        assert result is True
        mock_jira.add_comment.assert_not_called()
        mock_jira.remove_label.assert_not_called()

    def test_secret_in_description_returns_false(self, caplog):
        """Secret in description blocks and posts failure comment."""
        import logging
        caplog.set_level(logging.WARNING)

        mock_jira = MagicMock()
        mock_validator = MagicMock()
        # First call (summary) passes, second call (description) fails
        mock_validator.validate.side_effect = [
            ValidationResult(is_valid=True, failure_reason=""),
            ValidationResult(is_valid=False, failure_reason="credential_detected"),
        ]

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action.validate_inputs(
            "TEST-123", mock_jira,
            summary="Fix the bug",
            description="Use token AKIAIOSFODNN7EXAMPLE"
        )

        assert result is False

        # Failure comment posted
        mock_jira.add_comment.assert_called_once()
        comment = mock_jira.add_comment.call_args[0][1]
        assert "ACTION FAILED" in comment
        assert "secrets or credentials" in comment

        # Label removed
        mock_jira.remove_label.assert_called_once_with(
            "TEST-123", "ai-validatortest"
        )

        # Warning logged
        assert any(
            "Secret detected" in record.message
            and "TEST-123" in record.message
            for record in caplog.records
        )

    def test_skips_empty_inputs(self):
        """Empty/None inputs are skipped without validation."""
        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=True, failure_reason=""
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action.validate_inputs(
            "TEST-123", mock_jira,
            summary="Fix bug",
            description="",
            prior_analysis=None
        )

        assert result is True
        # Only summary should be validated (description and prior_analysis are empty/None)
        assert mock_validator.validate.call_count == 1
