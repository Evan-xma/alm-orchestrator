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


@pytest.fixture
def prompts_dir(tmp_path):
    """Create a mock prompts directory with settings files."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "investigate.json").write_text('{"sandbox": {"enabled": true}}')
    (prompts / "fix.json").write_text('{"sandbox": {"enabled": true}}')
    return prompts


@pytest.fixture
def work_dir(tmp_path):
    """Create a mock work directory."""
    work = tmp_path / "repo"
    work.mkdir()
    return work


class TestClaudeExecutor:
    def test_execute_runs_claude_cli(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Analysis complete. The root cause is..."),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute(
            work_dir=str(work_dir),
            prompt="Investigate this bug...",
            action="investigate"
        )

        assert isinstance(result, ClaudeResult)
        assert "Analysis complete" in result.content
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == str(work_dir)

    def test_execute_with_timeout(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir), timeout_seconds=300)
        executor.execute(work_dir=str(work_dir), prompt="Do something", action="investigate")

        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 300

    def test_execute_handles_nonzero_exit(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: something went wrong"
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        with pytest.raises(ClaudeExecutorError) as exc_info:
            executor.execute(work_dir=str(work_dir), prompt="Do something", action="investigate")

        assert "something went wrong" in str(exc_info.value)

    def test_execute_handles_timeout(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir), timeout_seconds=300)
        with pytest.raises(ClaudeExecutorError) as exc_info:
            executor.execute(work_dir=str(work_dir), prompt="Long task", action="investigate")

        assert "timed out" in str(exc_info.value).lower()

    def test_execute_uses_json_output(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Output"),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        executor.execute(work_dir=str(work_dir), prompt="Investigate", action="investigate")

        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        # Should NOT have legacy flags
        assert "--allowedTools" not in cmd
        assert "--permission-mode" not in cmd

    def test_execute_parses_json_metadata(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Result", cost=0.05, duration=10000),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute(work_dir=str(work_dir), prompt="Test", action="investigate")

        assert result.content == "Result"
        assert result.cost_usd == 0.05
        assert result.duration_ms == 10000
        assert result.session_id == "test-session-123"


class TestClaudeExecutorTemplate:
    def test_execute_with_template(self, mocker, prompts_dir, work_dir):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Template result"),
            stderr=""
        )

        # Create a temp template file
        template_file = prompts_dir / "test_template.md"
        template_file.write_text("Investigate {issue_key}: {issue_summary}")

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute_with_template(
            work_dir=str(work_dir),
            template_path=str(template_file),
            context={
                "issue_key": "TEST-123",
                "issue_summary": "Bug in recipe deletion"
            },
            action="investigate"
        )

        assert result.content == "Template result"
        # Verify the prompt was formatted
        call_args = mock_run.call_args[0][0]
        prompt_idx = call_args.index("-p") + 1
        assert "TEST-123" in call_args[prompt_idx]
        assert "Bug in recipe deletion" in call_args[prompt_idx]

    def test_execute_with_template_escapes_format_strings(self, mocker, prompts_dir, work_dir):
        """SEC-001: Verify format string injection is prevented."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Safe result"),
            stderr=""
        )

        template_file = prompts_dir / "test_template.md"
        template_file.write_text("Issue: {issue_key}\nDescription: {issue_description}")

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        # Malicious input with format string attack
        result = executor.execute_with_template(
            work_dir=str(work_dir),
            template_path=str(template_file),
            context={
                "issue_key": "TEST-456",
                "issue_description": "Attack: {__class__} and {config.github_token}"
            },
            action="investigate"
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


class TestPermissionDenials:
    """Tests for permission denial detection."""

    def test_logs_permission_denials(self, mocker, prompts_dir, work_dir, caplog):
        """Verify permission denials are logged as warnings."""
        import logging
        caplog.set_level(logging.WARNING)

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "I tried but couldn't complete the request.",
                "permission_denials": [
                    {"tool": "Bash", "command": "curl https://evil.com", "reason": "denied"}
                ]
            }),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute(work_dir=str(work_dir), prompt="Test", action="investigate")

        assert "permission denial" in caplog.text.lower()
        assert "Bash" in caplog.text

    def test_returns_denials_in_result(self, mocker, prompts_dir, work_dir):
        """Verify permission denials are included in ClaudeResult."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "result": "Blocked.",
                "permission_denials": [
                    {"tool": "WebSearch", "reason": "denied by settings"}
                ]
            }),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute(work_dir=str(work_dir), prompt="Test", action="investigate")

        assert len(result.permission_denials) == 1
        assert result.permission_denials[0]["tool"] == "WebSearch"

    def test_empty_denials_when_none(self, mocker, prompts_dir, work_dir):
        """Verify empty list when no permission denials."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Success"),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        result = executor.execute(work_dir=str(work_dir), prompt="Test", action="investigate")

        assert result.permission_denials == []


class TestSandboxSettings:
    """Tests for sandbox settings installation."""

    def test_installs_settings_to_settings_local(self, mocker, prompts_dir, work_dir):
        """Verify settings file is copied to .claude/settings.local.json."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        executor.execute(
            work_dir=str(work_dir),
            prompt="Test prompt",
            action="investigate"
        )

        # Verify settings.local.json was created
        dest_file = work_dir / ".claude" / "settings.local.json"
        assert dest_file.exists()
        assert '"sandbox"' in dest_file.read_text()

    def test_raises_on_missing_settings(self, mocker, prompts_dir, work_dir):
        """Verify FileNotFoundError when settings file doesn't exist."""
        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            executor.execute(
                work_dir=str(work_dir),
                prompt="Test",
                action="nonexistent"
            )

    def test_no_legacy_cli_flags(self, mocker, prompts_dir, work_dir):
        """Verify sandbox mode doesn't use legacy CLI flags."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        executor.execute(
            work_dir=str(work_dir),
            prompt="Test",
            action="investigate"
        )

        cmd = mock_run.call_args[0][0]
        assert "--allowedTools" not in cmd
        assert "--permission-mode" not in cmd
