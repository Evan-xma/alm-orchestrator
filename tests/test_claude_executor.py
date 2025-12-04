"""Tests for Claude Code CLI executor."""

import json
import subprocess
import pytest
from unittest.mock import MagicMock
from alm_orchestrator.claude_executor import ClaudeExecutor, ClaudeExecutorError, ClaudeResult


def mock_json_response(content: str, cost: float = 0.01, duration: int = 5000) -> str:
    """Create a mock JSON response from Claude Code."""
    return json.dumps({
        "result": content,
        "cost_usd": cost,
        "duration_ms": duration,
        "session_id": "test-session-123"
    })


class TestClaudeExecutor:
    def test_execute_runs_claude_cli(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Analysis complete. The root cause is..."),
            stderr=""
        )

        executor = ClaudeExecutor()
        result = executor.execute(
            work_dir="/tmp/repo",
            prompt="Investigate this bug..."
        )

        assert isinstance(result, ClaudeResult)
        assert "Analysis complete" in result.content
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == "/tmp/repo"

    def test_execute_with_timeout(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        executor = ClaudeExecutor(timeout_seconds=300)
        executor.execute(work_dir="/tmp/repo", prompt="Do something")

        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 300

    def test_execute_handles_nonzero_exit(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: something went wrong"
        )

        executor = ClaudeExecutor()
        with pytest.raises(ClaudeExecutorError) as exc_info:
            executor.execute(work_dir="/tmp/repo", prompt="Do something")

        assert "something went wrong" in str(exc_info.value)

    def test_execute_handles_timeout(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)

        executor = ClaudeExecutor(timeout_seconds=300)
        with pytest.raises(ClaudeExecutorError) as exc_info:
            executor.execute(work_dir="/tmp/repo", prompt="Long task")

        assert "timed out" in str(exc_info.value).lower()

    def test_execute_uses_headless_flags(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Output"),
            stderr=""
        )

        executor = ClaudeExecutor()
        executor.execute(work_dir="/tmp/repo", prompt="Investigate")

        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd                              # Print mode
        assert "--permission-mode" in cmd               # Permission handling
        assert "acceptEdits" in cmd                     # Auto-approve
        assert "--allowedTools" in cmd                  # Tool whitelist
        assert "--output-format" in cmd                 # Output format
        assert "json" in cmd                            # JSON output

    def test_execute_with_custom_tools(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        executor = ClaudeExecutor()
        executor.execute(
            work_dir="/tmp/repo",
            prompt="Fix the bug",
            allowed_tools=ClaudeExecutor.TOOLS_READWRITE
        )

        cmd = mock_run.call_args[0][0]
        assert "Bash,Read,Write,Edit,Glob,Grep" in cmd

    def test_execute_parses_json_metadata(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Result", cost=0.05, duration=10000),
            stderr=""
        )

        executor = ClaudeExecutor()
        result = executor.execute(work_dir="/tmp/repo", prompt="Test")

        assert result.content == "Result"
        assert result.cost_usd == 0.05
        assert result.duration_ms == 10000
        assert result.session_id == "test-session-123"


class TestClaudeExecutorTemplate:
    def test_execute_with_template(self, mocker, tmp_path):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Template result"),
            stderr=""
        )

        # Create a temp template file
        template_file = tmp_path / "test_template.md"
        template_file.write_text("Investigate {issue_key}: {issue_summary}")

        executor = ClaudeExecutor()
        result = executor.execute_with_template(
            work_dir="/tmp/repo",
            template_path=str(template_file),
            context={
                "issue_key": "TEST-123",
                "issue_summary": "Bug in recipe deletion"
            }
        )

        assert result.content == "Template result"
        # Verify the prompt was formatted
        call_args = mock_run.call_args[0][0]
        prompt_idx = call_args.index("-p") + 1
        assert "TEST-123" in call_args[prompt_idx]
        assert "Bug in recipe deletion" in call_args[prompt_idx]

    def test_execute_with_template_escapes_format_strings(self, mocker, tmp_path):
        """SEC-001: Verify format string injection is prevented."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Safe result"),
            stderr=""
        )

        template_file = tmp_path / "test_template.md"
        template_file.write_text("Issue: {issue_key}\nDescription: {issue_description}")

        executor = ClaudeExecutor()
        # Malicious input with format string attack
        result = executor.execute_with_template(
            work_dir="/tmp/repo",
            template_path=str(template_file),
            context={
                "issue_key": "TEST-456",
                "issue_description": "Attack: {__class__} and {config.github_token}"
            }
        )

        # Should succeed without KeyError
        assert result.content == "Safe result"

        # Verify the curly braces were escaped (not interpreted)
        call_args = mock_run.call_args[0][0]
        prompt_idx = call_args.index("-p") + 1
        prompt = call_args[prompt_idx]
        assert "{__class__}" in prompt  # Literal braces in output
        assert "{config.github_token}" in prompt


class TestEscapeFormatString:
    """Tests for the _escape_format_string helper."""

    def test_escapes_single_braces(self):
        assert ClaudeExecutor._escape_format_string("{foo}") == "{{foo}}"

    def test_escapes_multiple_braces(self):
        result = ClaudeExecutor._escape_format_string("a {x} b {y} c")
        assert result == "a {{x}} b {{y}} c"

    def test_handles_nested_braces(self):
        result = ClaudeExecutor._escape_format_string("{a{b}c}")
        assert result == "{{a{{b}}c}}"

    def test_preserves_non_string_types(self):
        assert ClaudeExecutor._escape_format_string(123) == 123
        assert ClaudeExecutor._escape_format_string(None) is None
        assert ClaudeExecutor._escape_format_string(True) is True

    def test_handles_empty_string(self):
        assert ClaudeExecutor._escape_format_string("") == ""

    def test_handles_no_braces(self):
        assert ClaudeExecutor._escape_format_string("plain text") == "plain text"
