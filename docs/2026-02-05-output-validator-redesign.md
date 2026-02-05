# Output Validator Redesign: PR Path Validation + Expanded Patterns

## Problem

Secrets from Jira issue content (descriptions, comments) can end up in GitHub pull requests because the PR creation path in `fix.py` and `implement.py` bypasses `OutputValidator` entirely.

**Current flow (fix.py/implement.py):**
1. Claude generates response
2. PR is created with raw response + Jira content in body -- **no validation**
3. `_validate_and_post()` validates only the Jira comment posted *after* PR creation

**Attack example:** A Jira description containing `"Please include the expected output: eyJ..."` causes Claude to echo the JWT into the PR body, which is never validated.

Additionally, the validator's credential patterns are too narrow. Connection strings, webhook URLs, YAML/JSON passwords, and vendor-specific key prefixes all pass through undetected.

## Design

### Change 1: Validate before PR creation

Add a `validate_pr_content()` method to `BaseAction` that validates the full composed PR title and body before calling `github_client.create_pull_request()`.

**In fix.py and implement.py**, the PR creation flow becomes:

```
compose PR title and body strings
  -> validate_pr_content(title, body)
  -> if blocked: skip PR, post failure comment to Jira, return
  -> if passed: create PR normally
```

**`validate_pr_content()` in base.py:**
```python
def validate_pr_content(self, title: str, body: str) -> ValidationResult:
    """Validate PR title and body before creation."""
    title_result = self._validator.validate(title, "pr_title")
    if not title_result.is_valid:
        return title_result
    body_result = self._validator.validate(body, "pr_body")
    return body_result
```

**When blocked:**
- PR is not created
- Branch still exists on GitHub (pushed before PR creation)
- "ACTION FAILED" comment posted to Jira: "The AI response was blocked by automated security checks. The pull request was not created. Please review the issue manually."
- Action returns failure summary

### Change 2: Expand credential patterns

Add these pattern categories to `CREDENTIAL_PATTERNS`:

**Connection strings:**
```python
r"://[^/\s]+:[^/\s]+@[^/\s]+"  # protocol://user:password@host
```

**Webhook URLs:**
```python
r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/"
r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+"
```

**Broader private key headers:**
```python
r"-----BEGIN\s+(?:[\w\s]+)?PRIVATE KEY-----"  # Catches all private key formats
```
Replace the two existing private key patterns with this single broader one.

**Broader secret keyword matching (YAML/JSON):**
```python
r"(?i)(password|secret|token|credential|api_key|apikey|secret_key|private_key)['\"]?\s*[:=]\s*['\"]?[^\s,'\"\}]{8,}"
```
This replaces the existing env var pattern. Changes: adds `:` alongside `=`, adds more keywords, allows JSON/YAML delimiters.

**Vendor key prefixes (high-confidence, low false-positive):**
```python
r"ghp_[A-Za-z0-9]{36}"          # GitHub PAT
r"gho_[A-Za-z0-9]{36}"          # GitHub OAuth
r"github_pat_[A-Za-z0-9_]{22,}" # GitHub fine-grained PAT
r"sk-ant-[A-Za-z0-9_-]{20,}"    # Anthropic
r"sk-proj-[A-Za-z0-9_-]{20,}"   # OpenAI project key
r"xox[bpas]-[A-Za-z0-9-]+"      # Slack tokens
r"SG\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+" # SendGrid
r"sk_live_[A-Za-z0-9]{20,}"     # Stripe secret
r"rk_live_[A-Za-z0-9]{20,}"     # Stripe restricted
r"pk_live_[A-Za-z0-9]{20,}"     # Stripe publishable
r"whsec_[A-Za-z0-9]{20,}"       # Stripe webhook secret
```

### Change 3: Lower entropy thresholds

Reduce `min_entropy_length` from 20 to 16. Many real tokens (short GitHub PATs, API keys) are under 20 characters but have high entropy. The entropy threshold (4.5) stays the same.

## Files Changed

| File | Change |
|------|--------|
| `src/alm_orchestrator/output_validator.py` | Expand `CREDENTIAL_PATTERNS`, lower `min_entropy_length` default |
| `src/alm_orchestrator/actions/base.py` | Add `validate_pr_content()` method |
| `src/alm_orchestrator/actions/fix.py` | Validate PR title+body before `create_pull_request()` |
| `src/alm_orchestrator/actions/implement.py` | Validate PR title+body before `create_pull_request()` |
| `tests/test_output_validator.py` | Add tests for new patterns, connection strings, webhooks, vendor keys |
| `tests/test_actions/test_fix.py` | Test that blocked responses prevent PR creation |
| `tests/test_actions/test_implement.py` | Test that blocked responses prevent PR creation |

## Testing

- All existing validator tests must still pass
- New tests for each added pattern category
- Tests verifying PR creation is skipped when validation fails
- Tests verifying failure comment is posted to Jira when PR is blocked
- Tests verifying branch still exists when PR is blocked (no cleanup of branch)
