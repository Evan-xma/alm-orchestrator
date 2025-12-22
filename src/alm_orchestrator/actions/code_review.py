"""Code review action handler."""

import logging
import os

from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.utils.pr_extraction import find_pr_in_texts

logger = logging.getLogger(__name__)

LABEL_CODE_REVIEW = "ai-code-review"


class CodeReviewAction(BaseAction):
    """Handles ai-code-review label - performs code review on PR."""

    @property
    def label(self) -> str:
        return LABEL_CODE_REVIEW

    @property
    def allowed_issue_types(self) -> list[str]:
        return ["Bug", "Story"]

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

        # Validate issue type
        if not self.validate_issue_type(issue, jira_client):
            return f"Rejected {issue_key}: invalid issue type"

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

            # Format the review response
            header = "CODE REVIEW"
            response = f"{header}\n{'=' * len(header)}\n\n{result.content}"

            # Validate before posting
            validation = self._validator.validate(response, "code_review")

            if validation.is_valid:
                # Post review to GitHub PR
                github_client.add_pr_comment(pr_number, response)

                # Notify in Jira
                complete_header = "CODE REVIEW COMPLETE"
                jira_response = (
                    f"{complete_header}\n"
                    f"{'=' * len(complete_header)}\n\n"
                    f"Review posted to PR #{pr_number}"
                    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
                )
                jira_client.add_comment(issue_key, jira_response)
            else:
                # Log warning (no sensitive content)
                logger.warning(f"Suspicious response for {issue_key}: {validation.failure_reason}")

                # Post generic warning to Jira
                header = "AI RESPONSE BLOCKED"
                jira_client.add_comment(
                    issue_key,
                    f"{header}\n{'=' * len(header)}\n\n"
                    "The AI agent's response was flagged by automated security checks "
                    "and has not been posted. Please review the issue manually."
                )

            # Always remove the label
            jira_client.remove_label(issue_key, self.label)

            if validation.is_valid:
                return f"Code review complete for PR #{pr_number}"
            else:
                return f"Code review response blocked for {issue_key}"

        finally:
            github_client.cleanup(work_dir)
