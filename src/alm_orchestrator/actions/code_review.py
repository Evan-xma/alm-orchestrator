"""Code review action handler."""

import os

from alm_orchestrator.actions.base import BaseAction
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
        comment_bodies = [c["body"] for c in comments]

        # Search description first, then comments
        pr_number = find_pr_in_texts(description, comment_bodies)

        if not pr_number:
            header = "CODE REVIEW FAILED"
            jira_client.add_comment(
                issue_key,
                f"{header}\n"
                f"{'=' * len(header)}\n\n"
                "Could not find PR number in issue description or comments. "
                "Please include the PR URL or number."
            )
            jira_client.remove_label(issue_key, self.label)
            return f"No PR found for {issue_key}"

        # Get PR info including head branch and changed files
        pr_info = github_client.get_pr_info(pr_number)
        changed_files = pr_info["changed_files"]

        # Clone the PR's head branch to review the actual changes
        work_dir = github_client.clone_repo(branch=pr_info["head_branch"])

        try:
            # Format changed files list for the prompt
            changed_files_text = "\n".join(f"- {f}" for f in changed_files)

            # Run Claude for code review (read-only tools)
            template_path = os.path.join(self._prompts_dir, "code_review.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "changed_files": changed_files_text,
                    "pr_title": pr_info["title"],
                    "pr_description": pr_info["body"],
                },
                action="code_review",
            )

            # Post review as PR comment
            header = "CODE REVIEW"
            comment = f"{header}\n{'=' * len(header)}\n\n{result.content}"
            github_client.add_pr_comment(pr_number, comment)

            # Notify in Jira
            complete_header = "CODE REVIEW COMPLETE"
            jira_client.add_comment(
                issue_key,
                f"{complete_header}\n"
                f"{'=' * len(complete_header)}\n\n"
                f"Review posted to PR #{pr_number}"
            )
            jira_client.remove_label(issue_key, self.label)

            return f"Code review complete for PR #{pr_number}"

        finally:
            github_client.cleanup(work_dir)
