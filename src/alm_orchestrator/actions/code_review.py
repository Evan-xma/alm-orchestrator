"""Code review action handler."""

import os

from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.claude_executor import ClaudeExecutor
from alm_orchestrator.utils.pr_extraction import find_pr_in_texts


class CodeReviewAction(BaseAction):
    """Handles ai-code-review label - performs code review on PR."""

    @property
    def label(self) -> str:
        return "ai-code-review"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute code review on PR.

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
                "## AI Code Review Failed\n\n"
                "Could not find PR number in issue description or comments. "
                "Please include the PR URL or number."
            )
            jira_client.remove_label(issue_key, self.label)
            return f"No PR found for {issue_key}"

        work_dir = github_client.clone_repo()

        try:
            # Run Claude for code review (read-only tools)
            template_path = os.path.join(self._prompts_dir, "code_review.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={"issue_key": issue_key},
                allowed_tools=ClaudeExecutor.TOOLS_READONLY,
            )

            # Post review as PR comment
            comment = f"## AI Code Review\n\n{result.content}"
            github_client.add_pr_comment(pr_number, comment)

            # Notify in Jira
            jira_client.add_comment(
                issue_key,
                f"## AI Code Review Complete\n\nReview posted to PR #{pr_number}"
            )
            jira_client.remove_label(issue_key, self.label)

            return f"Code review complete for PR #{pr_number}"

        finally:
            github_client.cleanup(work_dir)
