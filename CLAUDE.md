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

Actions are auto-discovered from `src/alm_orchestrator/actions/`. To add a new action:

1. Create `actions/{name}.py` with a class extending `BaseAction`
2. Define label as a module constant (e.g., `LABEL_MYACTION = "ai-myaction"`)
3. Return the constant from the `label` property
4. Create `prompts/{name}.md` template
5. Restart daemon — auto-discovered

Label-to-template convention: `ai-investigate` → `prompts/investigate.md`

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

Environment variables loaded from `.env`:
- `JIRA_URL`, `JIRA_PROJECT_KEY` - Jira instance URL and project key
- `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` - OAuth 2.0 credentials for service account
- `GITHUB_TOKEN`, `GITHUB_REPO` - GitHub PAT and repo in `owner/repo` format
- `ANTHROPIC_API_KEY` (optional if using Vertex AI)
- `POLL_INTERVAL_SECONDS` (default: 30)

#### Creating Jira OAuth 2.0 Credentials

1. Go to [admin.atlassian.com](https://admin.atlassian.com)
2. Navigate to **Directory > Service accounts**
3. Select your service account
4. Click **Create credentials** → **OAuth 2.0**
5. Select scopes: `read:jira-work`, `write:jira-work`
6. Save the Client ID and Client Secret (cannot be retrieved later)

## Commit Guidelines

- Do NOT add `Co-Authored-By` lines to commit messages
- Do NOT sign Claude Code in commit descriptions or PR descriptions
