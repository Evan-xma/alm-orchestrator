# Output Monitoring Design

Status: **Ready for Implementation**

## Goal

Validate Claude's responses before posting to Jira/GitHub to:
1. Detect leaked credentials/secrets
2. Catch off-topic or manipulated responses via structural validation

## Decisions Made

### When to Monitor
**Before posting** - Check response before posting to Jira/GitHub; block suspicious responses.

### On Detection
- Don't post the response
- Log WARN with issue key only (no sensitive content in logs)
- Post comment to Jira that the agent's response was flagged

### Detection Methods
1. **Credential detection** - Pattern matching for secrets (language-agnostic)
2. **Structural validation** - Loose check that expected sections exist

### Skipped
- Injection success phrase detection (easily bypassed with non-English)
- Leaked prompt fragment detection

## Architecture

New `OutputValidator` class in `src/alm_orchestrator/output_validator.py`:

```python
from dataclasses import dataclass
from typing import Dict, List
import re
import math

@dataclass
class ValidationResult:
    is_valid: bool
    failure_reason: str  # Generic, no sensitive content

class OutputValidator:
    def __init__(self):
        self._credential_patterns = [...]  # Compiled regex
        self._section_requirements = {...}  # Per action

    def validate(self, response: str, action: str) -> ValidationResult:
        """Check response for secrets and expected structure."""

    def _has_credentials(self, response: str) -> tuple[bool, str]:
        """Check for leaked secrets/credentials. Returns (found, reason)."""

    def _has_expected_structure(self, response: str, action: str) -> bool:
        """Check if expected section headers are present."""

    def _has_high_entropy_strings(self, response: str) -> bool:
        """Check for suspicious random-looking strings."""
```

## Credential Detection Patterns

```python
CREDENTIAL_PATTERNS = [
    # AWS
    r"AKIA[0-9A-Z]{16}",           # AWS Access Key ID
    r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]",

    # Private keys
    r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"-----BEGIN PGP PRIVATE KEY BLOCK-----",

    # JWTs
    r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",

    # Generic API keys / tokens
    r"(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token)['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",

    # Environment variable assignments
    r"(?i)(PASSWORD|SECRET|TOKEN|CREDENTIAL|API_KEY)\s*=\s*['\"]?[^\s'\"]{8,}",
]
```

For high-entropy detection: check for strings 20+ chars with mixed case, numbers, and symbols. Use Shannon entropy > 4.5 as threshold.

## Structural Validation

Expected sections per action (loose check - case-insensitive substring match):

```python
SECTION_REQUIREMENTS = {
    "investigate": ["SUMMARY", "ROOT CAUSE", "EVIDENCE"],
    "impact": ["FILES THAT WOULD CHANGE", "RISK ASSESSMENT"],
    "recommend": ["OPTION 1", "RECOMMENDATION"],
    "fix": ["What files you changed", "What the fix does"],
    "implement": ["What files you created", "How the feature works"],
    "code_review": ["SUMMARY", "HIGH PRIORITY", "LOW PRIORITY"],
    "security_review": ["SUMMARY", "HIGH PRIORITY FINDINGS"],
}
```

Response passes if all required sections are found somewhere in the text.

## Response Handling

When validation fails:

```python
# In action
result = self._executor.execute(work_dir, prompt, "investigate")

validation = self._validator.validate(result.content, "investigate")
if not validation.is_valid:
    # 1. Log warning with issue key only
    logger.warning(f"Suspicious response detected for {issue_key}: {validation.failure_reason}")

    # 2. Post generic comment to Jira
    self._jira.add_comment(
        issue_key,
        "⚠️ AI RESPONSE BLOCKED\n\n"
        "The AI agent's response was flagged by automated security checks "
        "and has not been posted. Please review the issue manually."
    )

    # 3. Return early
    return ActionResult(success=False, message=f"Response blocked: {validation.failure_reason}")
```

Failure reasons:
- `"credential_detected"` - Found potential secret/key
- `"high_entropy_string"` - Suspicious random-looking string
- `"missing_structure"` - Expected sections not found

## Integration

Validator instantiated once in daemon, passed to actions via router:

```python
# daemon.py
class Daemon:
    def __init__(self, config: Config):
        self._validator = OutputValidator()
        self._router = LabelRouter(
            jira_client=self._jira,
            github_client=self._github,
            executor=self._executor,
            validator=self._validator,
        )
```

Base action provides helper method:

```python
# actions/base.py
class BaseAction:
    def __init__(self, jira, github, executor, validator):
        self._validator = validator

    def _validate_and_post(self, issue_key: str, response: str, action: str) -> bool:
        """Validate response and post to Jira if safe. Returns True if posted."""
        validation = self._validator.validate(response, action)
        if not validation.is_valid:
            logger.warning(f"Suspicious response for {issue_key}: {validation.failure_reason}")
            self._jira.add_comment(issue_key, "⚠️ AI RESPONSE BLOCKED\n\n...")
            return False
        self._jira.add_comment(issue_key, response)
        return True
```

## Implementation Plan

1. Create `output_validator.py` with `OutputValidator` class
2. Add credential pattern matching
3. Add high-entropy string detection
4. Add structural validation per action
5. Update `BaseAction` with `_validate_and_post()` helper
6. Update daemon/router to pass validator to actions
7. Update each action to use `_validate_and_post()`
8. Add tests for validator
