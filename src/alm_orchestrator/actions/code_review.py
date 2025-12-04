"""Code review action handler."""

import os
import re
from typing import Optional

from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.claude_executor import ClaudeExecutor


class CodeReviewAction(BaseAction):
    """Handles ai-code-review label - performs code review on PR."""

    @property
    def label(self) -> str:
        return "ai-code-review"

    def _extract_pr_number(self, description: str) -> Optional[int]:
        """Extract PR number from issue description.

        Looks for patterns like:
        - PR: https://github.com/owner/repo/pull/42
        - Pull Request: #42
        - PR #42
        """
        patterns = [
            r"github\.com/[^/]+/[^/]+/pull/(\d+)",
            r"PR[:\s#]+(\d+)",
            r"Pull Request[:\s#]+(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

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

        pr_number = self._extract_pr_number(description)
        if not pr_number:
            jira_client.add_comment(
                issue_key,
                "## AI Code Review Failed\n\n"
                "Could not find PR number in issue description. "
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
