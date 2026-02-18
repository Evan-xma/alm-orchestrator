# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

**Important:** Always activate the virtual environment first:

```bash
source .venv/bin/activate
```

Then run commands:

```bash
# Install dependencies (editable mode with dev tools)
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_daemon.py -v

# Run a specific test
pytest tests/test_router.py::TestLabelRouter::test_action_count -v

# Run the daemon
python main.py

# Run with options
python main.py --dry-run              # Poll once without processing
python main.py --poll-interval 10
python main.py -v                     # Verbose logging
python main.py --env-file custom.env  # Use custom env file (default: .env)
python main.py --logs-dir custom-logs # Custom logs directory (default: logs)
```

No linting or formatting tools are configured (no ruff, black, flake8, mypy, or pre-commit).

## Architecture

ALM Orchestrator is a daemon that polls Jira for issues with AI labels, invokes Claude Code CLI to process them, and posts results back to Jira/GitHub.

### Core Flow

1. **Daemon** (`daemon.py`) polls Jira at configured intervals
2. **JiraClient** (`jira_client.py`) fetches issues with `ai-*` labels via JQL
3. **LabelRouter** (`router.py`) maps labels to action handlers via auto-discovery
4. **Actions** (`actions/*.py`) execute Claude Code and post results
5. **GitHubClient** (`github_client.py`) handles cloning, branching, and PRs
6. **ClaudeExecutor** (`claude_executor.py`) runs Claude Code CLI in headless mode

### Action System

Actions are auto-discovered from `src/alm_orchestrator/actions/`. The router (`router.py`) uses `pkgutil.iter_modules()` to scan the actions package, instantiate all `BaseAction` subclasses, and register them by their label property.

To add a new action:

1. Create `src/alm_orchestrator/actions/{name}.py` with a class extending `BaseAction`
2. Define label as a module constant (e.g., `LABEL_MYACTION = "ai-myaction"`)
3. Return the constant from the `label` property
4. Override `allowed_issue_types` to restrict which Jira issue types can use this action (e.g., `["Bug"]` or `["Bug", "Story"]`). Empty list means all types allowed.
5. Implement the `execute()` method following the standard pattern:
   - Call `validate_issue_type()` first
   - Call `validate_inputs()` to check issue content for secrets
   - Clone repo, run Claude with `claude_executor.execute_with_template()`
   - Call `_validate_and_post()` to validate and post results
   - Always cleanup in `finally` block via `github_client.cleanup(work_dir)`
6. Create `prompts/{name}.md` template with your prompt
7. Create `prompts/{name}.json` with sandbox settings
8. Restart daemon — auto-discovered

**Conventions:**
- Label to template: `ai-investigate` → `prompts/investigate.md`
- Label to settings: `ai-investigate` → `prompts/investigate.json`
- Template variables are substituted using `.format()`, with automatic escaping of user-controlled content to prevent format string injection

### Supported Labels

| Label | Action | Creates PR? | Allowed Issue Types |
|-------|--------|-------------|---------------------|
| `ai-investigate` | Root cause analysis | No | Bug |
| `ai-impact` | Impact analysis | No | Bug, Story |
| `ai-recommend` | Suggest approaches | No | Bug, Story |
| `ai-fix` | Bug fix implementation | Yes | Bug |
| `ai-implement` | Feature implementation | Yes | Story |
| `ai-code-review` | Code review on PR | No | Bug, Story |
| `ai-security-review` | Security review on PR | No | Bug, Story |

### Action Chaining

Some actions automatically include context from prior actions on the same issue:

| Action | Uses Context From |
|--------|-------------------|
| `ai-recommend` | `ai-investigate` results |
| `ai-fix` | `ai-investigate` and `ai-recommend` results |
| `ai-implement` | `ai-recommend` results |

Context is fetched via `JiraClient.get_investigation_comment()` and `get_recommendation_comment()`, which match by comment header (`"INVESTIGATION RESULTS"`, `"RECOMMENDATIONS"`) and service account ID.

### Input & Output Validation

**Input Validation:**
All actions validate issue content (summary, description) before cloning repos or invoking Claude via `validate_inputs()`. This prevents prompt injection and catches secrets in user-provided content. If validation fails:
- A generic "ACTION FAILED" comment is posted to Jira
- The label is removed
- No repo cloning or Claude invocation occurs (fail fast)

**Output Validation:**
All action responses pass through `OutputValidator` (in `output_validator.py`) before being posted to Jira. The base action method `_validate_and_post()` handles this. The validator checks for:

- **Credential patterns:** AWS keys, private key headers, JWTs, API key assignments, env vars with secrets
- **High-entropy strings:** Shannon entropy > 4.5 on words >= 20 chars (catches leaked secrets)

If validation fails, a generic "AI RESPONSE BLOCKED" comment is posted instead — failure reasons never expose what was detected to prevent information leakage.

### Sandbox Settings

Each action has a sandbox settings file: `prompts/{action}.json`. Read-only actions (investigate, impact, recommend, code_review, security_review) block network and writes. Read-write actions (fix, implement) allow GitHub access and file writes. Settings are installed to `.claude/settings.local.json` before execution (higher precedence than `settings.json`).

### Configuration

**Environment Variables:**
Loaded from `.env` and validated in `config.py`. See `.env.example` for all variables. Key required vars: `JIRA_URL`, `JIRA_PROJECT_KEY`, `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET`, `GITHUB_TOKEN`, `GITHUB_REPO`.

**Claude Code Settings:**
The `.claude/settings.json` file configures the status line for this repository. Action-specific sandbox settings in `prompts/*.json` are installed to `.claude/settings.local.json` at runtime (higher precedence than `settings.json`).

### Key Implementation Details

**ClaudeExecutor (`claude_executor.py`):**
- Runs Claude Code CLI in headless mode with `--output-format json`
- Parses JSON output to extract `result`, `cost_usd`, `duration_ms`, `session_id`, and `permission_denials`
- Logs warnings if permission denials detected (indicates potential prompt injection or missing permissions)
- Timeout configurable via `CLAUDE_TIMEOUT_SECONDS`

**JiraClient (`jira_client.py`):**
- Uses OAuth 2.0 with service account credentials and automatic token refresh
- Adds `ai-processing` label during execution to prevent duplicate processing
- Fetches issues with JQL: `project = {key} AND labels IN ({ai_labels})`

**GitHubClient (`github_client.py`):**
- Clones repos to temporary directories with token authentication
- Branch naming: `{prefix}{issuekey}-{YYYYMMDD-HHMM}` via `generate_branch_name()`
- Always call `cleanup(work_dir)` in finally blocks

**PR Extraction (`utils/pr_extraction.py`):**
- Used by code_review and security_review actions to find PR numbers
- Searches issue description first, then comments (newest-first)
- Supports formats: GitHub URLs, `PR #123`, `PR: 123`, `Pull Request #123`

**Error Handling:**
- Actions that fail post an "ACTION FAILED" comment to Jira
- `ai-processing` label is always removed after execution (in `finally` block)
- Permission denials are logged as warnings for security monitoring

**Logging:**
- CSV format: `asctime,levelname,name,message`
- Console + file logging (file at DEBUG, console configurable)
- File logs: `logs/run-{YYYYMMDD-HHMMSS}.log` (can be customized via `--logs-dir`)
- Claude execution logs: Captured in dedicated directory with full prompts + responses for audit/debugging

### Testing Patterns

- Uses pytest with pytest-mock (`mocker` fixture)
- Mock all external dependencies (Jira, GitHub, subprocess for Claude CLI)
- Test files mirror source: `test_actions/test_investigate.py` for `actions/investigate.py`
- Verify cleanup happens on error paths (finally blocks)
- Test both happy path and validation rejection paths

## Commit Guidelines

- Do NOT add `Co-Authored-By` lines to commit messages
- Do NOT sign Claude Code in commit descriptions or PR descriptions
