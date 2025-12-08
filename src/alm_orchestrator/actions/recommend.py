"""Recommendation action handler."""

import logging
import os
from alm_orchestrator.actions.base import BaseAction

logger = logging.getLogger(__name__)


class RecommendAction(BaseAction):
    """Handles ai-recommend label - suggests approaches."""

    @property
    def label(self) -> str:
        return "ai-recommend"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute recommendation generation.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for cloning repo.
            claude_executor: ClaudeExecutor for running analysis.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        summary = issue.fields.summary
        description = issue.fields.description or ""

        # Check for prior investigation results
        investigation_comment = jira_client.get_investigation_comment(issue_key)
        if investigation_comment:
            logger.info(
                f"Found investigation comment for {issue_key}, "
                f"including in recommendation context"
            )
            investigation_section = (
                "## Prior Investigation\n\n"
                "The following investigation was already performed on this issue:\n\n"
                f"{investigation_comment}"
            )
        else:
            logger.info(
                f"No investigation comment found for {issue_key} "
                f"from account {jira_client.account_id}"
            )
            investigation_section = ""

        work_dir = github_client.clone_repo()

        try:
            template_path = os.path.join(self._prompts_dir, "recommend.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                    "investigation_section": investigation_section,
                },
                action="recommend",
            )

            header = "RECOMMENDATIONS"
            comment = f"{header}\n{'=' * len(header)}\n\n{result.content}"
            jira_client.add_comment(issue_key, comment)
            jira_client.remove_label(issue_key, self.label)

            return f"Recommendations posted for {issue_key}"

        finally:
            github_client.cleanup(work_dir)
