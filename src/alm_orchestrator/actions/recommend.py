"""Recommendation action handler."""

import logging
import os
from alm_orchestrator.actions.base import BaseAction

logger = logging.getLogger(__name__)

LABEL_RECOMMEND = "ai-recommend"


class RecommendAction(BaseAction):
    """Handles ai-recommend label - suggests approaches."""

    @property
    def label(self) -> str:
        return LABEL_RECOMMEND

    @property
    def allowed_issue_types(self) -> list[str]:
        return ["Bug", "Story"]

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

        # Validate issue type
        if not self.validate_issue_type(issue, jira_client):
            return f"Rejected {issue_key}: invalid issue type"

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
                issue_key=issue_key
            )

            # Format response with cost footer
            header = "RECOMMENDATIONS"
            response = (
                f"{header}\n{'=' * len(header)}\n\n{result.content}"
                f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
            )

            # Validate and post
            posted = self._validate_and_post(
                issue_key=issue_key,
                response=response,
                action_type="recommend",
                jira_client=jira_client
            )

            # Always remove the label to mark as processed (even if blocked)
            jira_client.remove_label(issue_key, self.label)

            if posted:
                return f"Recommendations complete for {issue_key}"
            else:
                return f"Recommendations response blocked for {issue_key}"

        finally:
            github_client.cleanup(work_dir)
