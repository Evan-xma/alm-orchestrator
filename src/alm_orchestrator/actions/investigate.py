"""Investigate action handler for root cause analysis."""

import os
from alm_orchestrator.actions.base import BaseAction

LABEL_INVESTIGATE = "ai-investigate"


class InvestigateAction(BaseAction):
    """Handles ai-investigate label - performs root cause analysis."""

    @property
    def label(self) -> str:
        return LABEL_INVESTIGATE

    @property
    def allowed_issue_types(self) -> list[str]:
        return ["Bug"]

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute root cause investigation.

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

        # Clone the repo
        work_dir = github_client.clone_repo()

        try:
            # Run Claude with the investigate template (read-only tools)
            template_path = os.path.join(self._prompts_dir, "investigate.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                },
                action="investigate",
            )

            # Post findings as Jira comment
            header = "INVESTIGATION RESULTS"
            comment = (
                f"{header}\n{'=' * len(header)}\n\n{result.content}"
                f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
            )
            jira_client.add_comment(issue_key, comment)

            # Remove the label to mark as processed
            jira_client.remove_label(issue_key, self.label)

            return f"Investigation complete for {issue_key}"

        finally:
            # Always cleanup
            github_client.cleanup(work_dir)
