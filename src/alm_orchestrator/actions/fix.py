"""Fix action handler for bug fixes that create PRs."""

import logging
import os
from alm_orchestrator.actions.base import BaseAction

logger = logging.getLogger(__name__)

# Label and conventions for fixes
LABEL_FIX = "ai-fix"
BRANCH_PREFIX_FIX = "fix-"
COMMIT_PREFIX_FIX = "fix: "


class FixAction(BaseAction):
    """Handles ai-fix label - implements bug fix and creates PR."""

    @property
    def label(self) -> str:
        return LABEL_FIX

    @property
    def allowed_issue_types(self) -> list[str]:
        return ["Bug"]

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

        # Validate issue type
        if not self.validate_issue_type(issue, jira_client):
            return f"Rejected {issue_key}: invalid issue type"

        # Check for prior analysis results
        prior_analysis_section = self._build_prior_analysis_section(
            issue_key, jira_client
        )

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
                    "prior_analysis_section": prior_analysis_section,
                },
                action="fix",
            )

            # Commit and push changes
            commit_message = f"{COMMIT_PREFIX_FIX}{summary}\n\nJira: {issue_key}"
            github_client.commit_and_push(work_dir, branch_name, commit_message, issue_key)

            # Create PR
            pr = github_client.create_pull_request(
                branch=branch_name,
                title=f"{COMMIT_PREFIX_FIX}{summary} [{issue_key}]",
                body=(
                    f"## Summary\n\n"
                    f"Fixes {issue_key}: {summary}\n\n"
                    f"## Implementation\n\n"
                    f"{result.content}"
                )
            )

            # Format response with PR link and cost
            header = "FIX CREATED"
            response = (
                f"{header}\n"
                f"{'=' * len(header)}\n\n"
                f"Pull Request: {pr.html_url}\n\n"
                f"Review the changes and merge when ready."
                f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
            )

            # Validate and post
            posted = self._validate_and_post(
                issue_key=issue_key,
                response=response,
                action_type="fix",
                jira_client=jira_client
            )

            # Always remove the label to mark as processed (even if blocked)
            jira_client.remove_label(issue_key, self.label)

            if posted:
                return f"Fix PR created for {issue_key}: {pr.html_url}"
            else:
                return f"Fix response blocked for {issue_key}"

        finally:
            github_client.cleanup(work_dir)

    def _build_prior_analysis_section(self, issue_key: str, jira_client) -> str:
        """Build the prior analysis section from investigation and recommendation.

        Args:
            issue_key: The issue key (e.g., "TEST-123").
            jira_client: JiraClient for fetching comments.

        Returns:
            Formatted prior analysis section, or empty string if none found.
        """
        sections = []

        # Fetch investigation context
        investigation_comment = jira_client.get_investigation_comment(issue_key)
        if investigation_comment:
            sections.append(
                "## Prior Investigation\n\n"
                "The following investigation was already performed on this issue:\n\n"
                f"{investigation_comment}"
            )
        else:
            logger.info(f"No investigation comment found for {issue_key}")

        # Fetch recommendation context
        recommendation_comment = jira_client.get_recommendation_comment(issue_key)
        if recommendation_comment:
            sections.append(
                "## Recommendations\n\n"
                "The following recommendations were provided:\n\n"
                f"{recommendation_comment}"
            )
        else:
            logger.info(f"No recommendation comment found for {issue_key}")

        return "\n\n".join(sections)
