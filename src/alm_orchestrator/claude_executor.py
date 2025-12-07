"""Claude Code CLI executor for the ALM Orchestrator."""

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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


class ClaudeExecutor:
    """Executes Claude Code CLI commands in headless mode."""

    DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes

    # Tool profiles for different action types (legacy, kept for compatibility)
    TOOLS_READONLY = "Bash,Read,Glob,Grep"
    TOOLS_READWRITE = "Bash,Read,Write,Edit,Glob,Grep"

    def __init__(
        self,
        timeout_seconds: Optional[int] = None,
        prompts_dir: Optional[str] = None
    ):
        """Initialize the executor.

        Args:
            timeout_seconds: Maximum time to wait for Claude Code to complete.
                           Defaults to 600 seconds (10 minutes).
            prompts_dir: Path to prompts directory containing {action}.json settings files.
                        If None, sandbox settings are not used.
        """
        self._timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self._prompts_dir = Path(prompts_dir) if prompts_dir else None

    def _install_sandbox_settings(self, work_dir: str, action: str) -> None:
        """Install sandbox settings for an action to the working directory.

        Args:
            work_dir: The working directory (cloned repo).
            action: Name of the action (matches {action}.json file).

        Raises:
            FileNotFoundError: If the settings file doesn't exist.
        """
        if self._prompts_dir is None:
            return

        settings_src = self._prompts_dir / f"{action}.json"
        if not settings_src.exists():
            raise FileNotFoundError(f"Sandbox settings not found: {settings_src}")

        # Create .claude directory if needed
        claude_dir = Path(work_dir) / ".claude"
        claude_dir.mkdir(exist_ok=True)

        # Copy settings to settings.local.json (higher precedence than settings.json)
        settings_dst = claude_dir / "settings.local.json"
        shutil.copy(settings_src, settings_dst)
        logger.debug(f"Installed sandbox settings for '{action}' to {settings_dst}")

    def execute(
        self,
        work_dir: str,
        prompt: str,
        allowed_tools: Optional[str] = None,
        action: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with the given prompt in headless mode.

        Args:
            work_dir: Working directory (the cloned repo).
            prompt: The prompt to send to Claude Code.
            allowed_tools: Comma-separated list of allowed tools (legacy).
                          Ignored if action is specified and prompts_dir is set.
            action: Action name (e.g., "investigate", "fix", "implement").
                   If specified and prompts_dir is set, installs the action's settings.

        Returns:
            ClaudeResult with content and metadata.

        Raises:
            ClaudeExecutorError: If execution fails or times out.
        """
        # Install sandbox settings if available
        if action and self._prompts_dir:
            self._install_sandbox_settings(work_dir, action)
            # When using sandbox settings, don't pass --allowedTools
            # The settings file handles all permissions
            cmd = [
                "claude",
                "-p", prompt,
                "--output-format", "json",
            ]
        else:
            # Legacy mode: use --allowedTools
            tools = allowed_tools or self.TOOLS_READONLY
            cmd = [
                "claude",
                "-p", prompt,
                "--permission-mode", "acceptEdits",
                "--allowedTools", tools,
                "--output-format", "json",
            ]

        logger.debug(
            f"Executing Claude Code CLI in {work_dir} "
            f"(action={action}, timeout={self._timeout}s)"
        )

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
            logger.debug(f"Claude Code CLI completed in {elapsed:.1f}s")

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise ClaudeExecutorError(f"Claude Code failed: {error_msg}")

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
            return ClaudeResult(
                content=data.get("result", ""),
                cost_usd=data.get("cost_usd", 0.0),
                duration_ms=data.get("duration_ms", 0),
                session_id=data.get("session_id", ""),
            )
        except json.JSONDecodeError:
            # Fall back to raw output if JSON parsing fails
            return ClaudeResult(
                content=result.stdout,
                cost_usd=0.0,
                duration_ms=0,
                session_id="",
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
        allowed_tools: Optional[str] = None,
        action: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with a prompt template.

        Args:
            work_dir: Working directory (the cloned repo).
            template_path: Path to the prompt template file.
            context: Dictionary of variables to substitute in the template.
            allowed_tools: Comma-separated list of allowed tools (legacy).
            action: Action name (e.g., "investigate", "fix").

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
        return self.execute(work_dir, prompt, allowed_tools, action)
