"""Jira API client for the ALM Orchestrator."""

import logging
import time
from typing import List, Optional

import requests
from jira import JIRA, Issue
from alm_orchestrator.config import Config

logger = logging.getLogger(__name__)


# OAuth constants
OAUTH_GRANT_TYPE = "client_credentials"
OAUTH_CONTENT_TYPE = "application/x-www-form-urlencoded"
DEFAULT_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour

# API URL pattern for Atlassian service accounts
ATLASSIAN_API_URL_PATTERN = "https://api.atlassian.com/ex/jira/{cloud_id}"


class OAuthTokenManager:
    """Manages OAuth 2.0 access tokens for Atlassian service accounts."""

    # Refresh token 5 minutes before expiry
    REFRESH_BUFFER_SECONDS = 300

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        resources_url: str,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._resources_url = resources_url
        self._access_token: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._cloud_id: Optional[str] = None

    def get_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._needs_refresh():
            self._refresh_token()
        return self._access_token

    def get_cloud_id(self) -> str:
        """Get the cloud ID for the Atlassian site.

        Must be called after get_token() to ensure we have a valid token.
        """
        if self._cloud_id is None:
            self._fetch_cloud_id()
        return self._cloud_id

    def get_api_url(self) -> str:
        """Get the API base URL for Jira REST API calls.

        Service accounts must use api.atlassian.com with the cloudId.
        """
        cloud_id = self.get_cloud_id()
        return ATLASSIAN_API_URL_PATTERN.format(cloud_id=cloud_id)

    def _needs_refresh(self) -> bool:
        """Check if token needs to be refreshed."""
        if self._access_token is None or self._expires_at is None:
            return True
        return time.time() >= (self._expires_at - self.REFRESH_BUFFER_SECONDS)

    def _refresh_token(self) -> None:
        """Fetch a new access token using client credentials."""
        response = requests.post(
            self._token_url,
            data={
                "grant_type": OAUTH_GRANT_TYPE,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": OAUTH_CONTENT_TYPE},
        )
        response.raise_for_status()

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", DEFAULT_TOKEN_EXPIRY_SECONDS)
        self._expires_at = time.time() + expires_in
        # Reset cloud_id so it gets re-fetched with new token if needed
        self._cloud_id = None

    def _fetch_cloud_id(self) -> None:
        """Fetch the cloud ID from accessible resources."""
        response = requests.get(
            self._resources_url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()

        resources = response.json()
        if not resources:
            raise ValueError("No accessible Atlassian sites found for this service account")
        # Use the first available site
        self._cloud_id = resources[0]["id"]


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
        self._token_manager = OAuthTokenManager(
            client_id=config.jira_client_id,
            client_secret=config.jira_client_secret,
            token_url=config.atlassian_token_url,
            resources_url=config.atlassian_resources_url,
        )
        self._jira: Optional[JIRA] = None
        self._account_id: Optional[str] = None
        self._fetch_account_id()

    @property
    def account_id(self) -> str:
        """The Jira account ID of this service account."""
        return self._account_id

    def _get_jira(self) -> JIRA:
        """Get a JIRA client with a valid access token.

        The client is recreated when the token is refreshed to ensure
        the Bearer token in the Authorization header is always valid.

        For OAuth 2.0 service accounts, we use api.atlassian.com with
        the cloudId instead of the direct instance URL.
        """
        # Get current token (will refresh if needed)
        token = self._token_manager.get_token()

        # Recreate client if token was refreshed or doesn't exist yet
        if self._jira is None:
            # Service accounts must use api.atlassian.com endpoint
            api_url = self._token_manager.get_api_url()
            self._jira = JIRA(
                server=api_url,
                token_auth=token,
            )
        return self._jira

    def _fetch_account_id(self) -> None:
        """Fetch and cache the service account's Jira account ID."""
        jira = self._get_jira()
        myself = jira.myself()
        self._account_id = myself["accountId"]
        logger.debug(f"Service account ID: {self._account_id}")

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

        return self._get_jira().search_issues(jql, maxResults=self.MAX_RESULTS)

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
        self._get_jira().add_comment(issue_key, body)

    def add_label(self, issue_key: str, label: str) -> None:
        """Add a label to a Jira issue.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            label: The label to add.
        """
        issue = self._get_jira().issue(issue_key)
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
        issue = self._get_jira().issue(issue_key)
        current_labels = list(issue.fields.labels)

        if label in current_labels:
            current_labels.remove(label)
            issue.update(fields={"labels": current_labels})

    def get_comments(self, issue_key: str) -> List[dict]:
        """Get comments for an issue, sorted newest-first.

        Args:
            issue_key: The issue key (e.g., "TEST-123").

        Returns:
            List of comment dicts with body, author_id, and created fields,
            ordered from newest to oldest.
        """
        issue = self._get_jira().issue(issue_key, fields="comment")
        comments = issue.fields.comment.comments
        sorted_comments = sorted(
            comments,
            key=lambda c: c.created,
            reverse=True
        )
        return [
            {
                "body": c.body,
                "author_id": c.author.accountId,
                "created": c.created,
            }
            for c in sorted_comments
        ]

    def get_comment_by_header(self, issue_key: str, header: str) -> Optional[str]:
        """Get the most recent comment from this service account matching a header.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            header: The header text the comment should start with.

        Returns:
            The comment body if found, None otherwise.
        """
        comments = self.get_comments(issue_key)
        for comment in comments:
            if (
                comment["author_id"] == self._account_id
                and comment["body"].startswith(header)
            ):
                return comment["body"]
        return None

    def get_investigation_comment(self, issue_key: str) -> Optional[str]:
        """Get the most recent investigation comment from this service account.

        Args:
            issue_key: The issue key (e.g., "TEST-123").

        Returns:
            The comment body if found, None otherwise.
        """
        return self.get_comment_by_header(issue_key, "INVESTIGATION RESULTS")
