"""Base class for AI action handlers."""

import os
from abc import ABC, abstractmethod
from typing import Any


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
