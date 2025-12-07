"""Security review action handler."""

import os

from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.utils.pr_extraction import find_pr_in_texts


class SecurityReviewAction(BaseAction):
    """Handles ai-security-review label - performs security review on PR."""

    @property
    def label(self) -> str:
        return "ai-security-review"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute security review on PR.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for PR operations.
            claude_executor: ClaudeExecutor for running review.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        description = issue.fields.description or ""

        # Fetch comments (sorted newest-first)
        comments = jira_client.get_comments(issue_key)

        # Search description first, then comments
        pr_number = find_pr_in_texts(description, comments)

        if not pr_number:
            jira_client.add_comment(
                issue_key,
                "SECURITY REVIEW FAILED\n"
                "======================\n\n"
                "Could not find PR number in issue description or comments. "
                "Please include the PR URL or number."
            )
            jira_client.remove_label(issue_key, self.label)
            return f"No PR found for {issue_key}"

        work_dir = github_client.clone_repo()

        try:
            # Run Claude for security review (read-only tools)
            template_path = os.path.join(self._prompts_dir, "security_review.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={"issue_key": issue_key},
                action="security_review",
            )

            comment = f"SECURITY REVIEW\n{'=' * 15}\n\n{result.content}"
            github_client.add_pr_comment(pr_number, comment)

            jira_client.add_comment(
                issue_key,
                f"SECURITY REVIEW COMPLETE\n"
                f"========================\n\n"
                f"Review posted to PR #{pr_number}"
            )
            jira_client.remove_label(issue_key, self.label)

            return f"Security review complete for PR #{pr_number}"

        finally:
            github_client.cleanup(work_dir)
