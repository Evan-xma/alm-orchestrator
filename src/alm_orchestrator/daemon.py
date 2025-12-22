"""Main daemon loop for the ALM Orchestrator."""

import logging
import signal
import time

from alm_orchestrator.config import Config
from alm_orchestrator.jira_client import JiraClient
from alm_orchestrator.github_client import GitHubClient
from alm_orchestrator.claude_executor import ClaudeExecutor
from alm_orchestrator.output_validator import OutputValidator
from alm_orchestrator.router import discover_actions


logger = logging.getLogger(__name__)


class Daemon:
    """Long-running daemon that polls Jira and processes AI labels."""

    def __init__(self, config: Config, prompts_dir: str):
        """Initialize the daemon.

        Args:
            config: Application configuration.
            prompts_dir: Path to prompt templates directory.
        """
        self._config = config
        self._prompts_dir = prompts_dir
        self._running = False

        # Initialize clients
        self._jira = JiraClient(config)
        self._github = GitHubClient(config)
        self._claude = ClaudeExecutor(
            prompts_dir=prompts_dir,
            timeout_seconds=config.claude_timeout_seconds
        )

        # Initialize output validator
        self._validator = OutputValidator()

        # Auto-discover and register all actions
        self._router = discover_actions(prompts_dir, validator=self._validator)
        logger.info(f"Discovered {self._router.action_count} action(s): {', '.join(self._router.action_names)}")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def stop(self) -> None:
        """Stop the daemon."""
        self._running = False

    def poll_once(self) -> int:
        """Execute a single poll cycle.

        Returns:
            Number of issues processed.
        """
        issues = self._jira.fetch_issues_with_ai_labels()
        logger.info(f"Found {len(issues)} issue(s) with AI labels")
        processed = 0

        for issue in issues:
            ai_labels = self._jira.get_ai_labels(issue)

            for label in ai_labels:
                if self._router.has_action(label):
                    # Remove original label and mark as processing to prevent duplicate pickup
                    self._jira.remove_label(issue.key, label)
                    self._jira.add_label(issue.key, JiraClient.PROCESSING_LABEL)

                    try:
                        logger.info(f"Processing {issue.key} with action: {label}")
                        action = self._router.get_action(label)
                        result = action.execute(
                            issue=issue,
                            jira_client=self._jira,
                            github_client=self._github,
                            claude_executor=self._claude,
                        )
                        logger.info(f"Completed: {result}")
                        processed += 1
                    except Exception as e:
                        logger.error(f"Error processing {issue.key}/{label}: {e}")
                        # Post error to Jira as comment (fail fast)
                        header = "ACTION FAILED"
                        self._jira.add_comment(
                            issue.key,
                            f"{header}\n{'=' * len(header)}\n\nLabel: {label}\n\nCheck logs for details."
                        )
                    finally:
                        # Always remove processing label
                        self._jira.remove_label(issue.key, JiraClient.PROCESSING_LABEL)

        return processed

    def run(self) -> None:
        """Run the daemon loop."""
        self._running = True
        poll_interval = self._config.poll_interval_seconds

        logger.info(f"Starting daemon, polling every {poll_interval} seconds")

        while self._running:
            try:
                processed = self.poll_once()
                if processed > 0:
                    logger.info(f"Processed {processed} issue(s)")
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}")

            # Sleep in small increments to allow for quick shutdown
            for _ in range(poll_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Daemon stopped")
