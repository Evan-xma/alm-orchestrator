# Application Lifecycle Management (ALM) Orchestrator

A Python daemon that integrates Jira, Claude Code, and GitHub to automate AI-powered development workflows. Add an AI label to a Jira issue, and the orchestrator will invoke Claude Code to analyze, fix, or implement the request.

## How It Works

1. Add an AI label (e.g., `ai-investigate`, `ai-fix`) to a Jira issue
2. The daemon polls Jira and picks up the issue
3. Claude Code analyzes the codebase and performs the requested action
4. Results are posted back to Jira (and GitHub for code changes)

## Supported Labels

| Label | Description | Creates PR? |
|-------|-------------|-------------|
| `ai-investigate` | Root cause analysis | No |
| `ai-impact` | Impact analysis for proposed changes | No |
| `ai-recommend` | Suggest implementation approaches | No |
| `ai-fix` | Implement a bug fix | Yes |
| `ai-implement` | Implement a new feature | Yes |
| `ai-code-review` | Review a pull request* | No |
| `ai-security-review` | Security-focused PR review* | No |

*Requires PR reference in issue. See [Specifying a Pull Request](#specifying-a-pull-request).

### Specifying a Pull Request

The `ai-code-review` and `ai-security-review` labels require a PR reference
in the Jira issue. The orchestrator searches the issue description first,
then comments (newest to oldest).

Supported formats:
- Full URL: `https://github.com/owner/repo/pull/42`
- Short: `PR #42` or `PR: 42`
- Explicit: `Pull Request #42`

If multiple PRs appear in comments, the most recent one is used.

## Requirements

- Python 3.12+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Jira Cloud with a service account and OAuth 2.0 credentials
- GitHub account with repo access

## Installation

```bash
git clone https://github.com/ronstarling9/alm-orchestrator.git
cd alm-orchestrator
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | Your Jira instance URL (e.g., `https://your-domain.atlassian.net`) |
| `JIRA_PROJECT_KEY` | Project key to poll (e.g., `DEMO`) |
| `JIRA_CLIENT_ID` | OAuth 2.0 Client ID for service account |
| `JIRA_CLIENT_SECRET` | OAuth 2.0 Client Secret for service account |
| `GITHUB_TOKEN` | GitHub personal access token with repo access |
| `GITHUB_REPO` | Repository in `owner/repo` format |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional if using Vertex AI) |
| `POLL_INTERVAL_SECONDS` | How often to poll Jira (default: 30) |

### Creating Jira OAuth 2.0 Credentials

1. Go to [admin.atlassian.com](https://admin.atlassian.com)
2. Navigate to **Directory > Service accounts**
3. Create or select a service account
4. Click **Create credentials** → **OAuth 2.0**
5. Select scopes: `read:jira-work`, `write:jira-work`
6. Save the Client ID and Client Secret (cannot be retrieved later)

## Usage

```bash
# Start the daemon
python main.py

# Start with custom poll interval
python main.py --poll-interval 10

# Dry run (poll once, show what would be processed)
python main.py --dry-run

# Verbose logging
python main.py -v
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--poll-interval` | Override poll interval in seconds |
| `--dry-run` | Poll once and exit without processing |
| `-v, --verbose` | Enable debug logging |
| `--env-file` | Path to .env file (default: `.env`) |
| `--logs-dir` | Directory for log files (default: `logs`) |

## Adding New Actions

1. Create `src/alm_orchestrator/actions/{name}.py`:

```python
from alm_orchestrator.actions.base import BaseAction
from alm_orchestrator.claude_executor import ClaudeExecutor

class MyAction(BaseAction):
    @property
    def label(self) -> str:
        return "ai-myaction"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        # Your implementation here
        pass
```

2. Create `prompts/{name}.md` with the prompt template

3. Create `prompts/{name}.json` with sandbox settings (see below)

4. Restart the daemon — actions are auto-discovered

## Security: Sandbox Profiles

Each action runs Claude Code in a sandboxed environment with restricted permissions. Settings files in `prompts/` define what each action can do:

| Action | Settings File | Filesystem | Network | Write/Edit |
|--------|---------------|------------|---------|------------|
| `investigate` | `prompts/investigate.json` | Read-only | Blocked | No |
| `impact` | `prompts/impact.json` | Read-only | Blocked | No |
| `recommend` | `prompts/recommend.json` | Read-only | Blocked | No |
| `code_review` | `prompts/code_review.json` | Read-only | Blocked | No |
| `security_review` | `prompts/security_review.json` | Read-only | Blocked | No |
| `fix` | `prompts/fix.json` | Read-write | Allowed | Yes |
| `implement` | `prompts/implement.json` | Read-write | Allowed | Yes |

All profiles:
- Enable OS-level sandboxing (bubblewrap on Linux)
- Block access to `.env` files and credentials
- Deny network tools (`curl`, `wget`, `nc`, `ssh`)
- Restrict Claude Code to the cloned repository directory

Permission denials are logged as warnings for security monitoring.

### Customizing Permissions

Edit the JSON settings files in `prompts/` to adjust permissions for your environment. For example, to allow additional build tools:

```json
{
  "permissions": {
    "allow": [
      "Bash(my-custom-tool:*)"
    ]
  }
}
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test
pytest tests/test_daemon.py::TestDaemon::test_initialization -v
```

## License

MIT
