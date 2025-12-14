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

    def __init__(self, prompts_dir: str):
        """Initialize with prompts directory.

        Args:
            prompts_dir: Path to directory containing prompt templates.
        """
        self._prompts_dir = prompts_dir

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
