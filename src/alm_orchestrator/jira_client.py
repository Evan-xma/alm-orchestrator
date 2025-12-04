"""Jira API client for the ALM Orchestrator."""

from typing import List
from jira import JIRA, Issue
from alm_orchestrator.config import Config


class JiraClient:
    """Client for interacting with Jira Cloud API."""

    AI_LABELS = frozenset([
        "ai-investigate",
        "ai-impact",
        "ai-recommend",
        "ai-fix",
        "ai-implement",
        "ai-code-review",
        "ai-security-review",
    ])

    PROCESSING_LABEL = "ai-processing"
    MAX_RESULTS = 50

    def __init__(self, config: Config):
        """Initialize Jira client with configuration.

        Args:
            config: Application configuration containing Jira credentials.
        """
        self._config = config
        self._jira = JIRA(
            server=config.jira_url,
            basic_auth=(config.jira_user, config.jira_api_token),
        )

    def fetch_issues_with_ai_labels(self) -> List[Issue]:
        """Fetch all issues in the project that have at least one AI label.

        Excludes issues currently being processed (ai-processing label).

        Returns:
            List of Jira issues with AI labels.
        """
        labels_clause = ", ".join(f'"{label}"' for label in self.AI_LABELS)
        jql = (
            f'project = {self._config.jira_project_key} '
            f'AND labels in ({labels_clause}) '
            f'AND labels != "{self.PROCESSING_LABEL}"'
        )

        return self._jira.search_issues(jql, maxResults=self.MAX_RESULTS)

    def get_ai_labels(self, issue: Issue) -> List[str]:
        """Extract AI labels from an issue.

        Args:
            issue: Jira issue object.

        Returns:
            List of AI label strings found on the issue.
        """
        issue_labels = set(issue.fields.labels)
        return sorted(list(issue_labels & self.AI_LABELS))

    def get_issue_description(self, issue: Issue) -> str:
        """Get the description text from an issue.

        Args:
            issue: Jira issue object.

        Returns:
            Description text, or empty string if none.
        """
        return issue.fields.description or ""

    def get_issue_summary(self, issue: Issue) -> str:
        """Get the summary (title) from an issue.

        Args:
            issue: Jira issue object.

        Returns:
            Summary text.
        """
        return issue.fields.summary

    def add_comment(self, issue_key: str, body: str) -> None:
        """Add a comment to a Jira issue.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            body: The comment text (supports Jira markup).
        """
        self._jira.add_comment(issue_key, body)

    def add_label(self, issue_key: str, label: str) -> None:
        """Add a label to a Jira issue.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            label: The label to add.
        """
        issue = self._jira.issue(issue_key)
        current_labels = list(issue.fields.labels)

        if label not in current_labels:
            current_labels.append(label)
            issue.update(fields={"labels": current_labels})

    def remove_label(self, issue_key: str, label: str) -> None:
        """Remove a label from a Jira issue.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            label: The label to remove.
        """
        issue = self._jira.issue(issue_key)
        current_labels = list(issue.fields.labels)

        if label in current_labels:
            current_labels.remove(label)
            issue.update(fields={"labels": current_labels})
