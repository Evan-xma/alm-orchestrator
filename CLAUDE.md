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
python main.py --dry-run        # Poll once without processing
python main.py --poll-interval 10
python main.py -v               # Verbose logging
```

## Architecture

ALM Orchestrator is a daemon that polls Jira for issues with AI labels, invokes Claude Code CLI to process them, and posts results back to Jira/GitHub.

### Core Flow

1. **Daemon** (`daemon.py`) polls Jira at configured intervals
2. **JiraClient** (`jira_client.py`) fetches issues with `ai-*` labels
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
4. Implement the `execute()` method
5. Create `prompts/{name}.md` template with your prompt
6. Create `prompts/{name}.json` with sandbox settings
7. Restart daemon — auto-discovered

**Conventions:**
- Label to template: `ai-investigate` → `prompts/investigate.md`
- Label to settings: `ai-investigate` → `prompts/investigate.json`
- Template variables are substituted using `.format()`, with automatic escaping of user-controlled content to prevent format string injection

### Action Chaining

Some actions automatically include context from prior actions on the same issue:

| Action | Uses Context From |
|--------|-------------------|
| `ai-recommend` | `ai-investigate` results |
| `ai-fix` | `ai-investigate` and `ai-recommend` results |
| `ai-implement` | `ai-recommend` results |

Context is fetched via `JiraClient.get_investigation_comment()` and `get_recommendation_comment()`, which match by comment header and service account ID.

### Supported Labels

| Label | Action | Creates PR? |
|-------|--------|-------------|
| `ai-investigate` | Root cause analysis | No |
| `ai-impact` | Impact analysis | No |
| `ai-recommend` | Suggest approaches | No |
| `ai-fix` | Bug fix implementation | Yes |
| `ai-implement` | Feature implementation | Yes |
| `ai-code-review` | Code review on PR | No |
| `ai-security-review` | Security review on PR | No |

### Sandbox Settings

Each action has a corresponding sandbox settings file in `prompts/`:

| Action | Settings File | Permissions |
|--------|---------------|-------------|
| `investigate` | `prompts/investigate.json` | Read-only, no network |
| `impact` | `prompts/impact.json` | Read-only, no network |
| `recommend` | `prompts/recommend.json` | Read-only, no network |
| `code_review` | `prompts/code_review.json` | Read-only, no network |
| `security_review` | `prompts/security_review.json` | Read-only, no network |
| `fix` | `prompts/fix.json` | Read-write, GitHub access |
| `implement` | `prompts/implement.json` | Read-write, WebFetch allowed |

Convention: `prompts/{action}.md` (prompt) + `prompts/{action}.json` (settings)

### Configuration

Environment variables loaded from `.env` and validated in `config.py`:

**Required:**
- `JIRA_URL` - Jira instance URL (e.g., `https://your-domain.atlassian.net`)
- `JIRA_PROJECT_KEY` - Project key to poll
- `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` - OAuth 2.0 credentials for service account
- `GITHUB_TOKEN` - GitHub PAT with repo access
- `GITHUB_REPO` - Repository in `owner/repo` format

**Optional (with defaults):**
- `ANTHROPIC_API_KEY` - Optional if using Vertex AI
- `POLL_INTERVAL_SECONDS` - Polling frequency (default: 30)
- `CLAUDE_TIMEOUT_SECONDS` - Claude Code CLI timeout (default: 600)
- `ATLASSIAN_TOKEN_URL` - OAuth token endpoint (default: `https://auth.atlassian.com/oauth/token`)
- `ATLASSIAN_RESOURCES_URL` - Accessible resources endpoint (default: `https://api.atlassian.com/oauth/token/accessible-resources`)
- `ATLASSIAN_API_URL_PATTERN` - Jira API URL pattern (default: `https://api.atlassian.com/ex/jira/{cloud_id}`)
- `GITHUB_CLONE_URL_PATTERN` - Clone URL pattern (default: `https://{token}@github.com/{repo}.git`)

#### Creating Jira OAuth 2.0 Credentials

1. Go to [admin.atlassian.com](https://admin.atlassian.com)
2. Navigate to **Directory > Service accounts**
3. Select your service account
4. Click **Create credentials** → **OAuth 2.0**
5. Select scopes: `read:jira-work`, `write:jira-work`
6. Save the Client ID and Client Secret (cannot be retrieved later)

### Key Implementation Details

**ClaudeExecutor (`claude_executor.py`):**
- Runs Claude Code CLI in headless mode with `--output-format json`
- Installs sandbox settings to `.claude/settings.local.json` before execution (higher precedence than `settings.json`)
- Parses JSON output to extract `result`, `cost_usd`, `duration_ms`, `session_id`, and `permission_denials`
- Logs warnings if permission denials detected (indicates potential prompt injection or missing permissions)
- Timeout configurable via `CLAUDE_TIMEOUT_SECONDS`

**JiraClient (`jira_client.py`):**
- Uses OAuth 2.0 with service account credentials
- Adds `ai-processing` label during execution to prevent duplicate processing
- Context retrieval methods (`get_investigation_comment()`, `get_recommendation_comment()`) match by comment header and service account ID
- Fetches issues with JQL: `project = {key} AND labels IN ({ai_labels})`

**GitHubClient (`github_client.py`):**
- Clones repos to temporary directories with token authentication
- Creates branches named `{action}/{issue-key}`
- Handles PR creation and commenting

**Error Handling:**
- Actions that fail post an "ACTION FAILED" comment to Jira
- `ai-processing` label is always removed after execution (in `finally` block)
- Permission denials are logged as warnings for security monitoring

## Commit Guidelines

- Do NOT add `Co-Authored-By` lines to commit messages
- Do NOT sign Claude Code in commit descriptions or PR descriptions
