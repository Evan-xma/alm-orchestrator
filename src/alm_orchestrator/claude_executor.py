"""Claude Code CLI executor for the ALM Orchestrator."""

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from alm_orchestrator.config import DEFAULT_CLAUDE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class ClaudeExecutorError(Exception):
    """Raised when Claude Code execution fails."""
    pass


@dataclass
class ClaudeResult:
    """Result from a Claude Code execution."""
    content: str
    cost_usd: float
    duration_ms: int
    session_id: str
    permission_denials: list = field(default_factory=list)


class ClaudeExecutor:
    """Executes Claude Code CLI commands in headless mode."""

    def __init__(
        self,
        prompts_dir: str,
        timeout_seconds: Optional[int] = None,
        log_output: bool = False,
        logs_dir: str = "logs"
    ):
        """Initialize the executor.

        Args:
            prompts_dir: Path to prompts directory containing {action}.json settings files.
            timeout_seconds: Maximum time to wait for Claude Code to complete.
                           Defaults to 600 seconds (10 minutes).
            log_output: If True, log execution details to files.
            logs_dir: Directory for log files.
        """
        self._prompts_dir = Path(prompts_dir)
        self._timeout = timeout_seconds or DEFAULT_CLAUDE_TIMEOUT_SECONDS
        self._log_output = log_output
        self._logs_dir = Path(logs_dir)

    def _install_sandbox_settings(self, work_dir: str, action: str) -> None:
        """Install sandbox settings for an action to the working directory.

        Args:
            work_dir: The working directory (cloned repo).
            action: Name of the action (matches {action}.json file).

        Raises:
            FileNotFoundError: If the settings file doesn't exist.
        """
        settings_src = self._prompts_dir / f"{action}.json"
        if not settings_src.exists():
            raise FileNotFoundError(f"Sandbox settings not found: {settings_src}")

        # Create .claude directory if needed
        claude_dir = Path(work_dir) / ".claude"
        claude_dir.mkdir(exist_ok=True)

        # Copy settings to settings.local.json (higher precedence than settings.json)
        settings_dst = claude_dir / "settings.local.json"
        shutil.copy(settings_src, settings_dst)
        logger.info(f"Installed sandbox settings for '{action}' to {settings_dst}")

    def execute(
        self,
        work_dir: str,
        prompt: str,
        action: str,
        issue_key: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with the given prompt in headless mode.

        Args:
            work_dir: Working directory (the cloned repo).
            prompt: The prompt to send to Claude Code.
            action: Action name (e.g., "investigate", "fix", "implement").
            issue_key: Optional Jira issue key for logging.

        Returns:
            ClaudeResult with content and metadata.

        Raises:
            ClaudeExecutorError: If execution fails or times out.
        """
        self._install_sandbox_settings(work_dir, action)

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
        ]

        logger.info(
            f"Executing Claude Code CLI in {work_dir} "
            f"(action={action}, timeout={self._timeout}s)"
        )
        logger.info("Running command: claude -p <prompt> --output-format json")

        start_time = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ClaudeExecutorError(
                f"Claude Code timed out after {self._timeout} seconds"
            ) from e
        finally:
            elapsed = time.monotonic() - start_time
            logger.info(f"Claude Code CLI completed in {elapsed:.1f}s")

        # Optionally log execution details
        if self._log_output and issue_key:
            self._log_execution_details(
                issue_key=issue_key,
                action=action,
                prompt=prompt,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                elapsed=elapsed
            )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise ClaudeExecutorError(f"Claude Code failed: {error_msg}")

        # Parse JSON output
        try:
            data = json.loads(result.stdout)

            # Check for permission denials (potential prompt injection or missing permissions)
            denials = data.get("permission_denials", [])
            if denials:
                denied_tools = [d.get("tool", "unknown") for d in denials]
                logger.warning(
                    f"Permission denials detected: {denied_tools}. "
                    f"This may indicate prompt injection or insufficient permissions. "
                    f"Details: {denials}"
                )

            # Extract cost from metadata if available, fallback to top-level
            metadata = data.get("metadata", {})
            cost_usd = metadata.get("cost_usd") or data.get("cost_usd", 0.0)

            return ClaudeResult(
                content=data.get("result", ""),
                cost_usd=cost_usd,
                duration_ms=data.get("duration_ms", 0),
                session_id=data.get("session_id", ""),
                permission_denials=denials,
            )
        except json.JSONDecodeError:
            # Fall back to raw output if JSON parsing fails
            return ClaudeResult(
                content=result.stdout,
                cost_usd=0.0,
                duration_ms=0,
                session_id="",
                permission_denials=[],
            )

    @staticmethod
    def _escape_format_string(value: str) -> str:
        """Escape curly braces in user input to prevent format string injection.

        Args:
            value: The string value to escape.

        Returns:
            String with { and } replaced by {{ and }}.
        """
        if not isinstance(value, str):
            return value
        return value.replace("{", "{{").replace("}", "}}")

    def execute_with_template(
        self,
        work_dir: str,
        template_path: str,
        context: dict,
        action: str,
        issue_key: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with a prompt template.

        Args:
            work_dir: Working directory (the cloned repo).
            template_path: Path to the prompt template file.
            context: Dictionary of variables to substitute in the template.
            action: Action name (e.g., "investigate", "fix").
            issue_key: Optional Jira issue key for logging.

        Returns:
            ClaudeResult with content and metadata.

        Raises:
            ClaudeExecutorError: If execution fails.
            FileNotFoundError: If template doesn't exist.
        """
        with open(template_path, "r") as f:
            template = f.read()

        # Escape curly braces in context values to prevent format string injection
        # (SEC-001: user-controlled Jira content could contain {malicious} patterns)
        safe_context = {
            key: self._escape_format_string(value)
            for key, value in context.items()
        }

        prompt = template.format(**safe_context)
        return self.execute(work_dir, prompt, action, issue_key=issue_key)

    def _log_execution_details(
        self,
        issue_key: str,
        action: str,
        prompt: str,
        stdout: str,
        stderr: str,
        returncode: int,
        elapsed: float
    ) -> None:
        """Log full execution details to a file.

        Args:
            issue_key: Jira issue key (e.g., BUG-123).
            action: Action name (e.g., investigate, fix).
            prompt: The prompt sent to Claude.
            stdout: Standard output from Claude CLI.
            stderr: Standard error from Claude CLI.
            returncode: Process exit code.
            elapsed: Execution time in seconds.
        """
        from datetime import datetime

        # Create logs directory if needed
        self._logs_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = self._logs_dir / f"ccout-{issue_key}-{timestamp}.txt"

        # Try to extract Claude's response and cost from JSON
        claude_response = None
        extracted_cost = None
        try:
            data = json.loads(stdout)
            claude_response = data.get("result", "")
            # Extract cost from metadata or top-level
            metadata = data.get("metadata", {})
            extracted_cost = metadata.get("cost_usd") or data.get("cost_usd")
        except (json.JSONDecodeError, AttributeError):
            pass

        # Write detailed log
        with open(log_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("CLAUDE CODE EXECUTION LOG\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Issue Key: {issue_key}\n")
            f.write(f"Action: {action}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Duration: {elapsed:.2f}s\n")
            f.write(f"Return Code: {returncode}\n")
            if extracted_cost is not None:
                f.write(f"Cost: ${extracted_cost:.4f}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(prompt)

            # Add Claude's response section if available
            if claude_response:
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("CLAUDE'S RESPONSE (extracted from JSON)\n")
                f.write("=" * 80 + "\n")
                f.write(claude_response)

            f.write("\n\n" + "=" * 80 + "\n")
            f.write("STDOUT (raw JSON output)\n")
            f.write("=" * 80 + "\n")
            f.write(stdout)
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("STDERR\n")
            f.write("=" * 80 + "\n")
            f.write(stderr)
            f.write("\n")

        logger.info(f"Claude execution log written to: {log_file}")
