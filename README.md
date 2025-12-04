# ALM Orchestrator

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
| `ai-code-review` | Review a pull request | No |
| `ai-security-review` | Security-focused PR review | No |

## Requirements

- Python 3.12+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Jira Cloud account with API access
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
| `JIRA_USER` | Jira account email |
| `JIRA_API_TOKEN` | Jira API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| `JIRA_PROJECT_KEY` | Project key to poll (e.g., `DEMO`) |
| `GITHUB_TOKEN` | GitHub personal access token with repo access |
| `GITHUB_REPO` | Repository in `owner/repo` format |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `POLL_INTERVAL_SECONDS` | How often to poll Jira (default: 30) |

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

3. Restart the daemon — actions are auto-discovered

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
