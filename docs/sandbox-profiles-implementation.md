# Sandbox Profiles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace CLI tool flags with OS-level sandbox profiles that restrict Claude Code to the working directory with per-action permissions.

**Architecture:** Create JSON settings files in `prompts/` alongside prompt templates. Each action gets its own settings file following the naming convention `{action_name}.json`. Before each Claude invocation, copy the action's settings file to `.claude/settings.local.json` in the cloned repo.

**Convention:** `prompts/{action}.md` (prompt template) + `prompts/{action}.json` (settings file)

**Tech Stack:** Python 3.13, pytest, Claude Code CLI sandbox features (bubblewrap)

**Note on Toolchains:** The default settings files include common build tools for Python, Node.js, Java, Go, and Rust. Deployers can customize these permissions by editing the JSON files to match their specific environment.

---

## Task 1: Create Settings Files for Each Action

**Files:**
- Create: `prompts/investigate.json`
- Create: `prompts/impact.json`
- Create: `prompts/recommend.json`
- Create: `prompts/code_review.json`
- Create: `prompts/security_review.json`
- Create: `prompts/fix.json`
- Create: `prompts/implement.json`

**Step 1: Create investigate.json (read-only, no network)**

Create `prompts/investigate.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false
  },
  "permissions": {
    "allow": [
      "Read(**)",
      "Glob(**)",
      "Grep(**)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(git show:*)",
      "Bash(git blame:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(wc:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(cat:*)"
    ],
    "deny": [
      "Write(**)",
      "Edit(**)",
      "WebFetch",
      "WebSearch",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/.env)",
      "Read(**/.env.*)"
    ]
  }
}
```

**Step 2: Create impact.json (same as investigate - read-only analysis)**

Create `prompts/impact.json` with identical content to `investigate.json`.

**Step 3: Create recommend.json (same as investigate - read-only analysis)**

Create `prompts/recommend.json` with identical content to `investigate.json`.

**Step 4: Create code_review.json (same as investigate - read-only analysis)**

Create `prompts/code_review.json` with identical content to `investigate.json`.

**Step 5: Create security_review.json (same as investigate - read-only analysis)**

Create `prompts/security_review.json` with identical content to `investigate.json`.

**Step 6: Create fix.json (read-write, no network)**

Create `prompts/fix.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false
  },
  "permissions": {
    "allow": [
      "Read(**)",
      "Write(**)",
      "Edit(**)",
      "Glob(**)",
      "Grep(**)",
      "Bash(git:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(wc:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(cat:*)",
      "Bash(mkdir:*)",
      "Bash(rm:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(make:*)",
      "Bash(cmake:*)",
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(npm test:*)",
      "Bash(npm run:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(yarn:*)",
      "Bash(pnpm:*)",
      "Bash(mvn:*)",
      "Bash(./mvnw:*)",
      "Bash(gradle:*)",
      "Bash(./gradlew:*)",
      "Bash(java:*)",
      "Bash(javac:*)",
      "Bash(jar:*)",
      "Bash(go:*)",
      "Bash(cargo:*)",
      "Bash(rustc:*)"
    ],
    "deny": [
      "WebFetch",
      "WebSearch",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/.env)",
      "Read(**/.env.*)"
    ]
  }
}
```

**Step 7: Create implement.json (read-write, package registries allowed)**

Create `prompts/implement.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false
  },
  "permissions": {
    "allow": [
      "Read(**)",
      "Write(**)",
      "Edit(**)",
      "Glob(**)",
      "Grep(**)",
      "Bash(git:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(wc:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(cat:*)",
      "Bash(mkdir:*)",
      "Bash(rm:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(make:*)",
      "Bash(cmake:*)",
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(yarn:*)",
      "Bash(pnpm:*)",
      "Bash(mvn:*)",
      "Bash(./mvnw:*)",
      "Bash(gradle:*)",
      "Bash(./gradlew:*)",
      "Bash(java:*)",
      "Bash(javac:*)",
      "Bash(jar:*)",
      "Bash(go:*)",
      "Bash(cargo:*)",
      "Bash(rustc:*)",
      "WebFetch"
    ],
    "deny": [
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)",
      "Read(.env)",
      "Read(.env.*)",
      "Read(**/.env)",
      "Read(**/.env.*)"
    ]
  }
}
```

**Step 8: Commit**

```bash
git add prompts/*.json
git commit -m "feat: add per-action sandbox settings files"
```

---

## Task 2: Add Settings Installation to ClaudeExecutor

**Files:**
- Modify: `src/alm_orchestrator/claude_executor.py`
- Test: `tests/test_claude_executor.py`

**Step 1: Write the failing test for settings installation**

Add to `tests/test_claude_executor.py`:

```python
class TestSandboxSettings:
    """Tests for sandbox settings installation."""

    def test_installs_settings_to_settings_local(self, mocker, tmp_path):
        """Verify settings file is copied to .claude/settings.local.json."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        # Create mock prompts directory with settings file
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        settings_file = prompts_dir / "investigate.json"
        settings_file.write_text('{"sandbox": {"enabled": true}}')

        # Create work directory
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

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
```

**Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestSandboxSettings::test_installs_settings_to_settings_local -v
```

Expected: FAIL with `TypeError` (prompts_dir not accepted)

**Step 3: Add prompts_dir parameter and settings installation**

Modify `src/alm_orchestrator/claude_executor.py`:

```python
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
```

**Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestSandboxSettings::test_installs_settings_to_settings_local -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/alm_orchestrator/claude_executor.py tests/test_claude_executor.py
git commit -m "feat: add sandbox settings installation to ClaudeExecutor"
```

---

## Task 3: Add More Executor Tests

**Files:**
- Modify: `tests/test_claude_executor.py`

**Step 1: Write test for missing settings file**

Add to `tests/test_claude_executor.py` in `TestSandboxSettings`:

```python
    def test_raises_on_missing_settings(self, mocker, tmp_path):
        """Verify FileNotFoundError when settings file doesn't exist."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            executor.execute(
                work_dir=str(work_dir),
                prompt="Test",
                action="nonexistent"
            )
```

**Step 2: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestSandboxSettings::test_raises_on_missing_settings -v
```

Expected: PASS

**Step 3: Write test for legacy mode (no prompts_dir)**

Add to `tests/test_claude_executor.py` in `TestSandboxSettings`:

```python
    def test_legacy_mode_without_prompts_dir(self, mocker, tmp_path):
        """Verify legacy --allowedTools mode when prompts_dir is None."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        # No prompts_dir = legacy mode
        executor = ClaudeExecutor()
        executor.execute(
            work_dir=str(work_dir),
            prompt="Test",
            allowed_tools=ClaudeExecutor.TOOLS_READONLY
        )

        cmd = mock_run.call_args[0][0]
        assert "--allowedTools" in cmd
        assert "--permission-mode" in cmd

        # No settings.local.json should be created
        settings_file = work_dir / ".claude" / "settings.local.json"
        assert not settings_file.exists()
```

**Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestSandboxSettings::test_legacy_mode_without_prompts_dir -v
```

Expected: PASS

**Step 5: Write test for action mode skipping --allowedTools**

Add to `tests/test_claude_executor.py` in `TestSandboxSettings`:

```python
    def test_action_mode_skips_allowed_tools_flag(self, mocker, tmp_path):
        """Verify --allowedTools is NOT passed when using action settings."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_json_response("Done"),
            stderr=""
        )

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "investigate.json").write_text('{"sandbox": {"enabled": true}}')

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        executor = ClaudeExecutor(prompts_dir=str(prompts_dir))
        executor.execute(
            work_dir=str(work_dir),
            prompt="Test",
            action="investigate"
        )

        cmd = mock_run.call_args[0][0]
        assert "--allowedTools" not in cmd
        assert "--permission-mode" not in cmd
```

**Step 6: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestSandboxSettings::test_action_mode_skips_allowed_tools_flag -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add tests/test_claude_executor.py
git commit -m "test: add sandbox settings edge case tests"
```

---

## Task 4: Update Daemon to Pass prompts_dir

**Files:**
- Modify: `src/alm_orchestrator/daemon.py`
- Test: `tests/test_daemon.py`

**Step 1: Read the current daemon.py to understand structure**

Read `src/alm_orchestrator/daemon.py` to find where `ClaudeExecutor` is instantiated.

**Step 2: Write failing test for daemon using prompts_dir**

Add to `tests/test_daemon.py`:

```python
def test_daemon_initializes_executor_with_prompts_dir(self, mocker):
    """Verify daemon passes prompts_dir to ClaudeExecutor."""
    mocker.patch.dict(os.environ, {
        "JIRA_URL": "https://test.atlassian.net",
        "JIRA_PROJECT_KEY": "TEST",
        "JIRA_CLIENT_ID": "client-id",
        "JIRA_CLIENT_SECRET": "client-secret",
        "GITHUB_TOKEN": "ghp_test",
        "GITHUB_REPO": "owner/repo",
    })

    mock_executor_class = mocker.patch("alm_orchestrator.daemon.ClaudeExecutor")

    from alm_orchestrator.daemon import Daemon
    from alm_orchestrator.config import Config

    config = Config.from_env()
    daemon = Daemon(config)

    # Verify ClaudeExecutor was called with prompts_dir
    mock_executor_class.assert_called_once()
    call_kwargs = mock_executor_class.call_args[1]
    assert "prompts_dir" in call_kwargs
    assert "prompts" in call_kwargs["prompts_dir"]
```

**Step 3: Run test to verify it fails**

```bash
source .venv/bin/activate && pytest tests/test_daemon.py::test_daemon_initializes_executor_with_prompts_dir -v
```

Expected: FAIL (prompts_dir not passed)

**Step 4: Modify daemon.py to pass prompts_dir**

Find the line that creates `ClaudeExecutor()` and update it:

```python
# Add import at top
from pathlib import Path

# In __init__ or wherever ClaudeExecutor is created:
prompts_dir = Path(__file__).parent.parent.parent / "prompts"
self._executor = ClaudeExecutor(
    prompts_dir=str(prompts_dir)
)
```

**Step 5: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_daemon.py::test_daemon_initializes_executor_with_prompts_dir -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/alm_orchestrator/daemon.py tests/test_daemon.py
git commit -m "feat: configure daemon to use prompts_dir for sandbox settings"
```

---

## Task 5: Update Actions to Use Action Parameter

**Files:**
- Modify: `src/alm_orchestrator/actions/investigate.py`
- Modify: `src/alm_orchestrator/actions/impact.py`
- Modify: `src/alm_orchestrator/actions/recommend.py`
- Modify: `src/alm_orchestrator/actions/code_review.py`
- Modify: `src/alm_orchestrator/actions/security_review.py`
- Modify: `src/alm_orchestrator/actions/fix.py`
- Modify: `src/alm_orchestrator/actions/implement.py`

**Step 1: Update investigate.py**

Change:
```python
allowed_tools=ClaudeExecutor.TOOLS_READONLY,
```

To:
```python
action="investigate",
```

Also remove the `ClaudeExecutor` import if no longer needed for `TOOLS_READONLY`.

**Step 2: Update impact.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READONLY` to `action="impact"`.

**Step 3: Update recommend.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READONLY` to `action="recommend"`.

**Step 4: Update code_review.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READONLY` to `action="code_review"`.

**Step 5: Update security_review.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READONLY` to `action="security_review"`.

**Step 6: Update fix.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READWRITE` to `action="fix"`.

**Step 7: Update implement.py**

Change `allowed_tools=ClaudeExecutor.TOOLS_READWRITE` to `action="implement"`.

**Step 8: Run all action tests**

```bash
source .venv/bin/activate && pytest tests/test_actions/ -v
```

Expected: PASS (tests mock execute_with_template, so they don't care about the parameter name change)

**Step 9: Commit**

```bash
git add src/alm_orchestrator/actions/
git commit -m "refactor: switch actions from allowed_tools to action parameter"
```

---

## Task 6: Update Action Tests to Verify Action Parameter

**Files:**
- Modify: `tests/test_actions/test_investigate.py`
- Modify: `tests/test_actions/test_fix.py`
- Modify: `tests/test_actions/test_implement.py`

**Step 1: Update test_investigate.py to verify action parameter**

In `test_execute_flow`, add assertion:

```python
# Verify action was passed instead of allowed_tools
call_kwargs = mock_claude.execute_with_template.call_args[1]
assert call_kwargs.get("action") == "investigate"
assert "allowed_tools" not in call_kwargs or call_kwargs.get("allowed_tools") is None
```

**Step 2: Run test to verify it passes**

```bash
source .venv/bin/activate && pytest tests/test_actions/test_investigate.py::TestInvestigateAction::test_execute_flow -v
```

Expected: PASS

**Step 3: Update test_fix.py similarly**

Add assertion for `action="fix"`.

**Step 4: Update test_implement.py similarly**

Add assertion for `action="implement"`.

**Step 5: Run all tests**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add tests/test_actions/
git commit -m "test: verify actions use correct action parameter"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `docs/sandbox-profiles-design.md`
- Modify: `CLAUDE.md`

**Step 1: Update design doc status**

Change status from "Draft" to "Implemented".

**Step 2: Add settings file convention to CLAUDE.md architecture section**

Add under Architecture:

```markdown
### Sandbox Settings

Each action has a corresponding sandbox settings file in `prompts/`:

| Action | Settings File | Permissions |
|--------|---------------|-------------|
| `investigate` | `prompts/investigate.json` | Read-only, no network |
| `impact` | `prompts/impact.json` | Read-only, no network |
| `recommend` | `prompts/recommend.json` | Read-only, no network |
| `code_review` | `prompts/code_review.json` | Read-only, no network |
| `security_review` | `prompts/security_review.json` | Read-only, no network |
| `fix` | `prompts/fix.json` | Read-write, no network |
| `implement` | `prompts/implement.json` | Read-write, WebFetch allowed |

Convention: `prompts/{action}.md` (prompt) + `prompts/{action}.json` (settings)
```

**Step 3: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: update sandbox settings documentation"
```

---

## Task 8: Final Verification

**Step 1: Run full test suite**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: All PASS

**Step 2: Verify settings files are valid JSON**

```bash
python -c "import json; [json.load(open(f'prompts/{a}.json')) for a in ['investigate', 'impact', 'recommend', 'code_review', 'security_review', 'fix', 'implement']]"
```

Expected: No errors

**Step 3: Manual smoke test (optional)**

```bash
# Clone a test repo and verify sandbox is applied
cd /tmp
git clone https://github.com/some/test-repo test-repo
mkdir -p test-repo/.claude
cp /path/to/prompts/investigate.json test-repo/.claude/settings.local.json
cd test-repo
claude -p "Run: curl --version" --output-format json
# Should show permission_denials for curl
```

---

## Task 9: Detect and Handle Permission Denials

**Files:**
- Modify: `src/alm_orchestrator/claude_executor.py`
- Test: `tests/test_claude_executor.py`

**Goal:** Detect when Claude Code attempts to use denied tools (potential prompt injection or missing permissions) and surface this to operators.

**Step 1: Write failing test for permission denial detection**

Add to `tests/test_claude_executor.py`:

```python
class TestPermissionDenials:
    """Tests for permission denial detection."""

    def test_logs_permission_denials(self, mocker, tmp_path, caplog):
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        executor = ClaudeExecutor()
        result = executor.execute(work_dir=str(work_dir), prompt="Test")

        assert "permission denial" in caplog.text.lower()
        assert "curl" in caplog.text

    def test_returns_denials_in_result(self, mocker, tmp_path):
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

        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        executor = ClaudeExecutor()
        result = executor.execute(work_dir=str(work_dir), prompt="Test")

        assert len(result.permission_denials) == 1
        assert result.permission_denials[0]["tool"] == "WebSearch"
```

**Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestPermissionDenials -v
```

Expected: FAIL (permission_denials not in ClaudeResult)

**Step 3: Update ClaudeResult dataclass**

Modify `src/alm_orchestrator/claude_executor.py`:

```python
@dataclass
class ClaudeResult:
    """Result from a Claude Code execution."""
    content: str
    cost_usd: float
    duration_ms: int
    session_id: str
    permission_denials: list  # New field
```

**Step 4: Update execute() to parse and log denials**

In the JSON parsing section of `execute()`:

```python
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

    return ClaudeResult(
        content=data.get("result", ""),
        cost_usd=data.get("cost_usd", 0.0),
        duration_ms=data.get("duration_ms", 0),
        session_id=data.get("session_id", ""),
        permission_denials=denials,
    )
except json.JSONDecodeError:
    return ClaudeResult(
        content=result.stdout,
        cost_usd=0.0,
        duration_ms=0,
        session_id="",
        permission_denials=[],
    )
```

**Step 5: Run tests to verify they pass**

```bash
source .venv/bin/activate && pytest tests/test_claude_executor.py::TestPermissionDenials -v
```

Expected: PASS

**Step 6: Update actions to surface denials in Jira comments (optional)**

In `src/alm_orchestrator/actions/base.py` or individual actions, add logic to append a warning to Jira comments when denials occur:

```python
if result.permission_denials:
    denied_tools = ", ".join(d.get("tool", "?") for d in result.permission_denials)
    warning = f"\n\n---\n**Security Note:** Some operations were blocked by sandbox policy: {denied_tools}"
    content = result.content + warning
```

**Step 7: Commit**

```bash
git add src/alm_orchestrator/claude_executor.py tests/test_claude_executor.py
git commit -m "feat: detect and log permission denials from Claude Code"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create per-action settings JSONs | `prompts/*.json` (7 files) |
| 2 | Add settings installation to executor | `claude_executor.py` |
| 3 | Add executor edge case tests | `test_claude_executor.py` |
| 4 | Update daemon to pass prompts_dir | `daemon.py` |
| 5 | Switch actions to use action parameter | `actions/*.py` (7 files) |
| 6 | Update action tests | `test_actions/*.py` |
| 7 | Update documentation | `docs/`, `CLAUDE.md` |
| 8 | Final verification | N/A |
| 9 | Detect and handle permission denials | `claude_executor.py`, `test_claude_executor.py` |

**Total commits:** 9

**Key changes from original plan:**
- Settings files stored in `prompts/` (not `prompts/sandbox/`)
- One settings file per action (7 files instead of 3)
- Convention: `{action}.json` matches `{action}.md`
- Parameter renamed from `profile` to `action` for clarity
- Added permission denial detection for security observability
