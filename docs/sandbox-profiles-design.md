# Sandbox Profiles Design

**Date:** 2025-12-07
**Status:** Draft
**Related:** SEC-002 (Prompt Injection via Jira Content)

---

## Problem Statement

The ALM Orchestrator invokes Claude Code CLI to process Jira issues. User-controlled content (issue summary, description) is passed directly to Claude, creating prompt injection risk. Even with tool restrictions (`--allowedTools`), the `Bash` tool allows Claude to:

- Read any file on the system (`cat /etc/passwd`, `env`)
- Exfiltrate data via network (`curl`, `nc`)
- Access credentials outside the working directory

Current mitigations (tool profiles) are insufficient for zero-trust security.

---

## Goals

1. Restrict Claude Code to the cloned repository's working directory
2. Block network access for read-only actions
3. Allow controlled network access for actions that need package registries
4. Prevent access to `.env` files and credentials
5. Apply different restrictions per action type

---

## Solution: Per-Action Sandbox Profiles

Use Claude Code's native OS-level sandboxing (Linux bubblewrap) combined with granular permission rules via `.claude/settings.local.json`.

### Key Discovery

Claude Code settings follow this precedence (highest to lowest):

1. Enterprise managed policies (`/etc/claude-code/managed-settings.json`)
2. Command-line arguments
3. **`.claude/settings.local.json`** (local project)
4. `.claude/settings.json` (shared project/repo)
5. `~/.claude/settings.json` (user)

**Verified behavior:** Deny rules in `settings.local.json` override allow rules in `settings.json`. This means our security profiles take precedence over any repo-provided settings.

---

## Profile Definitions

### Profile: `investigate` (read-only, no network)

Used by: `ai-investigate`, `ai-impact`, `ai-recommend`, `ai-code-review`, `ai-security-review`

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
      "Bash(wc:*)"
    ],
    "deny": [
      "Write(**)",
      "Edit(**)",
      "WebFetch",
      "WebSearch",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Read(.env)",
      "Read(.env.*)"
    ]
  }
}
```

### Profile: `fix` (read-write, GitHub only)

Used by: `ai-fix`

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false,
    "network": {
      "allowedDomains": ["github.com", "api.github.com"]
    }
  },
  "permissions": {
    "allow": [
      "Read(**)",
      "Write(**)",
      "Edit(**)",
      "Glob(**)",
      "Grep(**)",
      "Bash(git:*)",
      "Bash(npm test:*)",
      "Bash(npm run:*)",
      "Bash(pytest:*)",
      "Bash(python -m pytest:*)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Bash(ssh:*)",
      "Bash(scp:*)"
    ]
  }
}
```

### Profile: `implement` (read-write, package registries allowed)

Used by: `ai-implement`

```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false,
    "network": {
      "allowedDomains": [
        "github.com",
        "api.github.com",
        "registry.npmjs.org",
        "pypi.org",
        "files.pythonhosted.org"
      ]
    }
  },
  "permissions": {
    "allow": [
      "Read(**)",
      "Write(**)",
      "Edit(**)",
      "Glob(**)",
      "Grep(**)",
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(python:*)",
      "Bash(pytest:*)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(nc:*)",
      "Bash(ssh:*)"
    ]
  }
}
```

---

## Implementation

### File Structure

```
src/alm_orchestrator/
  sandbox_profiles/
    investigate.json
    fix.json
    implement.json
  claude_executor.py
```

### Modified Executor

```python
# claude_executor.py
import shutil
from pathlib import Path

PROFILES_DIR = Path(__file__).parent / "sandbox_profiles"

# Map action labels to profiles
PROFILE_MAP = {
    "ai-investigate": "investigate",
    "ai-impact": "investigate",
    "ai-recommend": "investigate",
    "ai-code-review": "investigate",
    "ai-security-review": "investigate",
    "ai-fix": "fix",
    "ai-implement": "implement",
}

def execute(self, work_dir: str, prompt: str, profile: str = "investigate"):
    # Write security profile to settings.local.json (higher precedence)
    profile_src = PROFILES_DIR / f"{profile}.json"
    claude_dir = Path(work_dir) / ".claude"
    claude_dir.mkdir(exist_ok=True)

    profile_dst = claude_dir / "settings.local.json"
    shutil.copy(profile_src, profile_dst)

    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
    ]

    # Note: --allowedTools and --permission-mode no longer needed
    # Sandbox profile handles all restrictions

    # ... rest of execution
```

### Action Changes

Each action handler passes its profile name:

```python
# actions/investigate.py
result = self._executor.execute(
    work_dir=temp_dir,
    prompt=prompt,
    profile="investigate",  # NEW
)

# actions/fix.py
result = self._executor.execute(
    work_dir=temp_dir,
    prompt=prompt,
    profile="fix",  # NEW
)
```

---

## Security Properties

| Property | Investigate | Fix | Implement |
|----------|-------------|-----|-----------|
| Filesystem: working dir only | Yes | Yes | Yes |
| Filesystem: block .env | Yes | Yes | Yes |
| Network: none | Yes | No | No |
| Network: GitHub only | N/A | Yes | No |
| Network: + package registries | N/A | N/A | Yes |
| Bash: allowlist only | Yes | Yes | Yes |
| Write/Edit: blocked | Yes | No | No |

---

## Alternatives Considered

### CLI Flags Only

```python
cmd = [
    "claude", "-p", prompt,
    "--allowedTools", "Read,Glob,Grep,Bash",
    "--disallowedTools", "Write,Edit,WebFetch",
]
```

**Rejected:** CLI flags don't support:
- Granular `Bash(command:*)` patterns
- Network domain allowlists
- File path deny rules like `Read(.env)`
- Sandbox enablement

### Enterprise Managed Policy

Write to `/etc/claude-code/managed-settings.json` for highest precedence.

**Rejected:**
- Requires root access
- Applies system-wide (can't vary per action)
- Operational complexity

### Overwrite `settings.json`

Copy profile directly to `.claude/settings.json`, backing up original.

**Rejected:**
- Destructive to repo configuration
- More complex cleanup logic
- `settings.local.json` achieves same precedence

---

## Testing Plan

1. **Unit tests:** Verify profile files are copied correctly
2. **Integration tests:**
   - Confirm `curl` blocked in investigate profile
   - Confirm `git push` works in fix profile
   - Confirm `.env` reads blocked in all profiles
3. **Manual verification:** Run each action against a test repo with malicious Jira content

---

## Open Questions

1. Should we add a cleanup step to remove `settings.local.json` after execution?
2. Do we need per-language profiles (e.g., `implement-python` vs `implement-node`)?
3. Should we log when permission denials occur for audit purposes?

---

## References

- [Claude Code Sandboxing - Anthropic Engineering](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Claude Code Settings Documentation](https://code.claude.com/docs/en/settings)
- SEC-002: Prompt Injection via Jira Content (security-review.md)
