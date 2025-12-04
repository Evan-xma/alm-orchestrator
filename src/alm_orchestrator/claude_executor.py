"""Claude Code CLI executor for the ALM Orchestrator."""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional


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

    # Tool profiles for different action types
    TOOLS_READONLY = "Bash,Read,Glob,Grep"
    TOOLS_READWRITE = "Bash,Read,Write,Edit,Glob,Grep"

    def __init__(self, timeout_seconds: Optional[int] = None):
        """Initialize the executor.

        Args:
            timeout_seconds: Maximum time to wait for Claude Code to complete.
                           Defaults to 600 seconds (10 minutes).
        """
        self._timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS

    def execute(
        self,
        work_dir: str,
        prompt: str,
        allowed_tools: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with the given prompt in headless mode.

        Args:
            work_dir: Working directory (the cloned repo).
            prompt: The prompt to send to Claude Code.
            allowed_tools: Comma-separated list of allowed tools.
                          Defaults to TOOLS_READONLY.

        Returns:
            ClaudeResult with content and metadata.

        Raises:
            ClaudeExecutorError: If execution fails or times out.
        """
        tools = allowed_tools or self.TOOLS_READONLY

        cmd = [
            "claude",
            "-p", prompt,                           # Non-interactive print mode
            "--permission-mode", "acceptEdits",     # Auto-approve edits
            "--allowedTools", tools,                # Whitelist tools
            "--output-format", "json",              # Structured output
        ]

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

    def execute_with_template(
        self,
        work_dir: str,
        template_path: str,
        context: dict,
        allowed_tools: Optional[str] = None
    ) -> ClaudeResult:
        """Execute Claude Code with a prompt template.

        Args:
            work_dir: Working directory (the cloned repo).
            template_path: Path to the prompt template file.
            context: Dictionary of variables to substitute in the template.
            allowed_tools: Comma-separated list of allowed tools.

        Returns:
            ClaudeResult with content and metadata.

        Raises:
            ClaudeExecutorError: If execution fails.
            FileNotFoundError: If template doesn't exist.
        """
        with open(template_path, "r") as f:
            template = f.read()

        prompt = template.format(**context)
        return self.execute(work_dir, prompt, allowed_tools)
