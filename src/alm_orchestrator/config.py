"""Configuration management for ALM Orchestrator."""

import os
from dataclasses import dataclass
from typing import Optional


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


# Default values
DEFAULT_POLL_INTERVAL_SECONDS = 30
DEFAULT_CLAUDE_TIMEOUT_SECONDS = 600  # 10 minutes
DEFAULT_ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
DEFAULT_ATLASSIAN_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
DEFAULT_ATLASSIAN_API_URL_PATTERN = "https://api.atlassian.com/ex/jira/{cloud_id}"
DEFAULT_GITHUB_CLONE_URL_PATTERN = "https://{token}@github.com/{repo}.git"


@dataclass(frozen=True)
class Config:
    """Immutable configuration for the orchestrator."""

    jira_url: str
    jira_project_key: str
    github_token: str
    github_repo: str
    jira_client_id: str
    jira_client_secret: str
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS
    claude_timeout_seconds: int = DEFAULT_CLAUDE_TIMEOUT_SECONDS
    anthropic_api_key: Optional[str] = None
    atlassian_token_url: str = DEFAULT_ATLASSIAN_TOKEN_URL
    atlassian_resources_url: str = DEFAULT_ATLASSIAN_RESOURCES_URL
    atlassian_api_url_pattern: str = DEFAULT_ATLASSIAN_API_URL_PATTERN
    github_clone_url_pattern: str = DEFAULT_GITHUB_CLONE_URL_PATTERN

    @property
    def github_owner(self) -> str:
        """Extract owner from 'owner/repo' format."""
        return self.github_repo.split("/")[0]

    @property
    def github_repo_name(self) -> str:
        """Extract repo name from 'owner/repo' format."""
        return self.github_repo.split("/")[1]

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Raises:
            ConfigError: If required environment variables are missing.
        """
        required = [
            "JIRA_URL",
            "JIRA_PROJECT_KEY",
            "JIRA_CLIENT_ID",
            "JIRA_CLIENT_SECRET",
            "GITHUB_TOKEN",
            "GITHUB_REPO",
        ]

        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

        poll_interval = os.getenv("POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS))
        try:
            poll_interval_int = int(poll_interval)
        except ValueError:
            raise ConfigError(f"POLL_INTERVAL_SECONDS must be an integer, got: {poll_interval}")

        claude_timeout = os.getenv("CLAUDE_TIMEOUT_SECONDS", str(DEFAULT_CLAUDE_TIMEOUT_SECONDS))
        try:
            claude_timeout_int = int(claude_timeout)
        except ValueError:
            raise ConfigError(f"CLAUDE_TIMEOUT_SECONDS must be an integer, got: {claude_timeout}")

        return cls(
            jira_url=os.environ["JIRA_URL"],
            jira_project_key=os.environ["JIRA_PROJECT_KEY"],
            jira_client_id=os.environ["JIRA_CLIENT_ID"],
            jira_client_secret=os.environ["JIRA_CLIENT_SECRET"],
            github_token=os.environ["GITHUB_TOKEN"],
            github_repo=os.environ["GITHUB_REPO"],
            poll_interval_seconds=poll_interval_int,
            claude_timeout_seconds=claude_timeout_int,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            atlassian_token_url=os.getenv(
                "ATLASSIAN_TOKEN_URL",
                DEFAULT_ATLASSIAN_TOKEN_URL
            ),
            atlassian_resources_url=os.getenv(
                "ATLASSIAN_RESOURCES_URL",
                DEFAULT_ATLASSIAN_RESOURCES_URL
            ),
            atlassian_api_url_pattern=os.getenv(
                "ATLASSIAN_API_URL_PATTERN",
                DEFAULT_ATLASSIAN_API_URL_PATTERN
            ),
            github_clone_url_pattern=os.getenv(
                "GITHUB_CLONE_URL_PATTERN",
                DEFAULT_GITHUB_CLONE_URL_PATTERN
            ),
        )
