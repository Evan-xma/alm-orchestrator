"""Implement action handler for feature implementation."""

import logging
import os
from alm_orchestrator.actions.base import BaseAction

logger = logging.getLogger(__name__)


# Label and conventions for features
LABEL_IMPLEMENT = "ai-implement"
BRANCH_PREFIX_FEATURE = "feature-"
COMMIT_PREFIX_FEAT = "feat: "


class ImplementAction(BaseAction):
    """Handles ai-implement label - implements feature and creates PR."""

    @property
    def label(self) -> str:
        return LABEL_IMPLEMENT

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute feature implementation and create PR.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for repo/PR operations.
            claude_executor: ClaudeExecutor for running implementation.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        summary = issue.fields.summary
        description = issue.fields.description or ""

        # Check for prior analysis results
        prior_analysis_section = self._build_prior_analysis_section(
            issue_key, jira_client
        )

        work_dir = github_client.clone_repo()
        branch_name = f"{BRANCH_PREFIX_FEATURE}{issue_key.lower()}"

        try:
            github_client.create_branch(work_dir, branch_name)

            # Run Claude to implement the feature (read-write tools)
            template_path = os.path.join(self._prompts_dir, "implement.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                    "prior_analysis_section": prior_analysis_section,
                },
                action="implement",
            )

            commit_message = f"{COMMIT_PREFIX_FEAT}{summary}\n\nJira: {issue_key}"
            github_client.commit_and_push(work_dir, branch_name, commit_message)

            pr = github_client.create_pull_request(
                branch=branch_name,
                title=f"{COMMIT_PREFIX_FEAT}{summary} [{issue_key}]",
                body=(
                    f"## Summary\n\n"
                    f"Implements {issue_key}: {summary}\n\n"
                    f"## Description\n\n"
                    f"{description}\n\n"
                    f"## AI Implementation\n\n"
                    f"{result.content}"
                )
            )

            header = "IMPLEMENTATION CREATED"
            comment = (
                f"{header}\n"
                f"{'=' * len(header)}\n\n"
                f"Pull Request: {pr.html_url}\n\n"
                f"Review the changes and merge when ready."
            )
            jira_client.add_comment(issue_key, comment)
            jira_client.remove_label(issue_key, self.label)

            return f"Feature PR created for {issue_key}: {pr.html_url}"

        finally:
            github_client.cleanup(work_dir)

    def _build_prior_analysis_section(self, issue_key: str, jira_client) -> str:
        """Build the prior analysis section from recommendation.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            jira_client: JiraClient for fetching comments.

        Returns:
            Formatted prior analysis section, or empty string if none found.
        """
        recommendation_comment = jira_client.get_recommendation_comment(issue_key)
        if recommendation_comment:
            return (
                "## Recommended Approach\n\n"
                f"{recommendation_comment}"
            )
        else:
            logger.info(f"No recommendation comment found for {issue_key}")
            return ""
