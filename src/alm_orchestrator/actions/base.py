"""Base class for AI action handlers."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# Action label and template conventions
AI_LABEL_PREFIX = "ai-"
TEMPLATE_EXTENSION = ".md"


class BaseAction(ABC):
    """Abstract base class for all AI actions.

    Each action handles a specific AI label (e.g., ai-investigate, ai-fix).
    """

    def __init__(self, prompts_dir: str, validator: Any):
        """Initialize with prompts directory and validator.

        Args:
            prompts_dir: Path to directory containing prompt templates.
            validator: OutputValidator instance for response validation.
        """
        self._prompts_dir = prompts_dir
        self._validator = validator

    @property
    @abstractmethod
    def label(self) -> str:
        """The AI label this action handles (e.g., 'ai-investigate')."""
        pass

    @abstractmethod
    def execute(
        self,
        issue: Any,
        jira_client: Any,
        github_client: Any,
        claude_executor: Any
    ) -> str:
        """Execute the action for the given Jira issue.

        Args:
            issue: The Jira issue object.
            jira_client: JiraClient instance for posting comments.
            github_client: GitHubClient instance for repo/PR operations.
            claude_executor: ClaudeExecutor instance for running Claude Code.

        Returns:
            A summary of what was done.
        """
        pass

    def get_template_path(self) -> str:
        """Get the path to this action's prompt template.

        Convention: ai-{name} label uses {name}.md template.

        Returns:
            Absolute path to the template file.
        """
        template_name = self.label.replace(AI_LABEL_PREFIX, "") + TEMPLATE_EXTENSION
        return os.path.join(self._prompts_dir, template_name)

    @property
    def allowed_issue_types(self) -> list[str]:
        """Issue types this action can run on. Override in subclasses.

        Returns:
            List of allowed issue type names (e.g., ["Bug", "Story"]).
            Empty list means no validation (all types allowed).
        """
        return []

    def validate_issue_type(self, issue, jira_client) -> bool:
        """Check if issue type is allowed. Posts rejection comment if not.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting comments and removing labels.

        Returns:
            True if valid (or no validation configured), False if rejected.
        """
        allowed = self.allowed_issue_types
        if not allowed:
            return True

        issue_type = issue.fields.issuetype.name
        if issue_type in allowed:
            return True

        # Log rejection
        logger.debug(
            f"Rejecting {issue.key}: {self.label} does not support issue type {issue_type}"
        )

        # Post rejection comment
        allowed_str = ", ".join(allowed)
        header = "INVALID ISSUE TYPE"
        comment = (
            f"{header}\n"
            f"{'=' * len(header)}\n\n"
            f"The {self.label} action only works on: {allowed_str}\n\n"
            f"This issue is a {issue_type}. "
            f"Please use an appropriate action for this issue type."
        )
        jira_client.add_comment(issue.key, comment)

        # Remove label
        jira_client.remove_label(issue.key, self.label)

        return False

    def _validate_and_post(
        self,
        issue_key: str,
        response: str,
        action_type: str,
        jira_client: Any
    ) -> bool:
        """Validate response and post to Jira if safe.

        Args:
            issue_key: The Jira issue key.
            response: Claude's response text.
            action_type: The action type for structural validation.
            jira_client: JiraClient for posting comments.

        Returns:
            True if response was posted, False if blocked.
        """
        # Ensure validator is initialized
        if self._validator is None:
            raise RuntimeError(
                f"Validator not initialized for {self.__class__.__name__}. "
                "This is a configuration error."
            )

        # Validate response
        validation = self._validator.validate(response, action_type)

        if not validation.is_valid:
            # Log warning (issue key only, no sensitive content)
            logger.warning(
                f"Suspicious response for {issue_key}: {validation.failure_reason}"
            )

            # Post generic warning comment
            header = "AI RESPONSE BLOCKED"
            comment = (
                f"{header}\n{'=' * len(header)}\n\n"
                "The AI agent's response was flagged by automated security checks "
                "and has not been posted. Please review the issue manually."
            )
            jira_client.add_comment(issue_key, comment)

            return False

        # Valid - post the response
        jira_client.add_comment(issue_key, response)
        return True
