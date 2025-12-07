"""Fix action handler for bug fixes that create PRs."""

import os
from alm_orchestrator.actions.base import BaseAction


# Branch and commit conventions for fixes
BRANCH_PREFIX_FIX = "fix-"
COMMIT_PREFIX_FIX = "fix: "


class FixAction(BaseAction):
    """Handles ai-fix label - implements bug fix and creates PR."""

    @property
    def label(self) -> str:
        return "ai-fix"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute bug fix and create PR.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for repo/PR operations.
            claude_executor: ClaudeExecutor for running fix.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        summary = issue.fields.summary
        description = issue.fields.description or ""

        # Clone and create branch
        work_dir = github_client.clone_repo()
        branch_name = f"{BRANCH_PREFIX_FIX}{issue_key.lower()}"

        try:
            github_client.create_branch(work_dir, branch_name)

            # Run Claude to implement the fix (read-write tools)
            template_path = os.path.join(self._prompts_dir, "fix.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                },
                action="fix",
            )

            # Commit and push changes
            commit_message = f"{COMMIT_PREFIX_FIX}{summary}\n\nJira: {issue_key}"
            github_client.commit_and_push(work_dir, branch_name, commit_message)

            # Create PR
            pr = github_client.create_pull_request(
                branch=branch_name,
                title=f"{COMMIT_PREFIX_FIX}{summary} [{issue_key}]",
                body=(
                    f"## Summary\n\n"
                    f"Fixes {issue_key}: {summary}\n\n"
                    f"## AI Implementation\n\n"
                    f"{result.content}"
                )
            )

            # Post PR link to Jira
            header = "FIX CREATED"
            comment = (
                f"{header}\n"
                f"{'=' * len(header)}\n\n"
                f"Pull Request: {pr.html_url}\n\n"
                f"Review the changes and merge when ready."
            )
            jira_client.add_comment(issue_key, comment)

            # Remove label
            jira_client.remove_label(issue_key, self.label)

            return f"Fix PR created for {issue_key}: {pr.html_url}"

        finally:
            github_client.cleanup(work_dir)
