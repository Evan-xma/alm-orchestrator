# Human-in-the-Loop Design

Status: **Ready for Implementation**

## Goal

Flag high-risk Jira issues for human review by detecting sensitive keywords before Claude processes fix/implement actions.

## Decisions Made

### Scope
- **Actions**: fix and implement only (actions that create PRs)
- **Check timing**: Before Claude runs
- **On detection**: Log warning, continue processing, add warning banner to Jira comment with PR link

### Keyword Configuration
- **Location**: `prompts/sensitive_keywords.txt`
- **Format**: Categorized sections with `[category]` headers, one keyword per line, `#` comments

## Architecture

New `InputScanner` class in `src/alm_orchestrator/input_scanner.py`:

```python
from dataclasses import dataclass

@dataclass
class ScanResult:
    has_sensitive_keywords: bool
    matched_keywords: list[str]  # For logging only, not included in Jira comment

class InputScanner:
    def __init__(self, keywords_path: str):
        self._keywords = self._load_keywords(keywords_path)

    def _load_keywords(self, path: str) -> dict[str, list[str]]:
        """Load keywords from file, organized by category."""
        # Returns {"credentials": ["password", ...], "privileged": ["admin", ...]}

    def scan(self, text: str) -> ScanResult:
        """Check text for sensitive keywords (case-insensitive)."""
```

## Keywords File

`prompts/sensitive_keywords.txt`:

```
[credentials]
# Authentication secrets
password
passwd
pwd
secret
api_key
apikey
api-key
auth_key
private_key
client_key
service_key
account_key
access_token
refresh_token
bearer
credential
credentials
contraseña
contrasena

[privileged]
# Elevated access
admin
administrator
root
sudo
superuser
privileged
privilege

[infrastructure]
# Sensitive systems
production
prod
ssh
certificate
cert
encrypt
decrypt
database
db_connection

[cloud]
# Platform credentials
aws_secret
aws_access
azure
gcp
```

Blank lines and `#` comments are ignored. Section headers like `[credentials]` define categories.

## Integration

Only fix and implement actions use the scanner:

```python
# In fix.py / implement.py

def execute(self, issue: Issue) -> ActionResult:
    # 1. Scan Jira content before processing
    content = f"{issue.fields.summary} {issue.fields.description}"
    scan_result = self._scanner.scan(content)

    if scan_result.has_sensitive_keywords:
        logger.warning(f"Sensitive keywords detected for {issue.key}")
        self._flagged = True  # Remember for later

    # 2. Process normally with Claude
    result = self._executor.execute(work_dir, prompt, action)

    # 3. Create PR, then post comment with warning if flagged
    pr = self._github.create_pull_request(...)

    comment = self._build_comment(pr.html_url, self._flagged)
    self._jira.add_comment(issue.key, comment)
```

Scanner is passed to actions via router (same pattern as OutputValidator).

## Jira Comment Format

When flagged (plain text, no markdown):

```
WARNING: SENSITIVE KEYWORDS DETECTED

This issue contained keywords that may indicate sensitive operations (e.g., password, credentials, admin). Please review the changes carefully.

Pull Request: https://github.com/org/repo/pull/123
```

When not flagged:

```
Pull Request: https://github.com/org/repo/pull/123
```

## Implementation Plan

1. Create `prompts/sensitive_keywords.txt` with keyword list
2. Create `src/alm_orchestrator/input_scanner.py` with `InputScanner` class
3. Update daemon/router to instantiate and pass scanner to actions
4. Update fix action to scan input and flag comment
5. Update implement action to scan input and flag comment
6. Add tests for scanner

## References

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Yelp detect-secrets KeywordDetector](https://github.com/Yelp/detect-secrets/blob/master/detect_secrets/plugins/keyword.py)
