# Output Monitoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement output validation to detect leaked credentials and malformed responses before posting to Jira/GitHub.

**Architecture:** Create `OutputValidator` class for pre-posting validation. Integrate with `BaseAction` via helper method. Pass validator instance from daemon through router to all actions.

**Tech Stack:** Python 3.x, regex pattern matching, Shannon entropy calculation

**Key Decisions:**
- Validator is required (not optional) for all actions
- Blocked responses still remove the label (no retry)
- Entropy threshold is configurable via OutputValidator constructor
- No full end-to-end integration tests (unit tests sufficient)

---

## Task 1: Create OutputValidator Module with Data Classes

**Files:**
- Create: `src/alm_orchestrator/output_validator.py`
- Test: `tests/test_output_validator.py`

**Step 1: Write the failing test for ValidationResult dataclass**

```python
"""Tests for OutputValidator."""

import pytest
from alm_orchestrator.output_validator import ValidationResult, OutputValidator


class TestValidationResult:
    def test_validation_result_valid(self):
        """ValidationResult can represent valid response."""
        result = ValidationResult(is_valid=True, failure_reason="")
        assert result.is_valid is True
        assert result.failure_reason == ""

    def test_validation_result_invalid(self):
        """ValidationResult can represent invalid response."""
        result = ValidationResult(
            is_valid=False,
            failure_reason="credential_detected"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestValidationResult -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'alm_orchestrator.output_validator'"

**Step 3: Write minimal implementation for dataclass**

```python
"""Output validation for Claude responses."""

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Pattern, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating Claude's response."""
    is_valid: bool
    failure_reason: str  # Generic, no sensitive content


class OutputValidator:
    """Validates Claude's responses before posting to Jira/GitHub."""

    def __init__(self, entropy_threshold: float = 4.5, min_entropy_length: int = 20):
        """Initialize the validator with credential patterns.

        Args:
            entropy_threshold: Shannon entropy threshold for flagging suspicious strings.
            min_entropy_length: Minimum string length to check for high entropy.
        """
        self._entropy_threshold = entropy_threshold
        self._min_entropy_length = min_entropy_length
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestValidationResult -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_output_validator.py src/alm_orchestrator/output_validator.py
git commit -m "feat: add OutputValidator module with ValidationResult dataclass"
```

---

## Task 2: Implement Credential Pattern Detection

**Files:**
- Modify: `src/alm_orchestrator/output_validator.py:10-20`
- Test: `tests/test_output_validator.py`

**Step 1: Write the failing test for credential detection**

Add to `tests/test_output_validator.py`:

```python
class TestCredentialDetection:
    def test_detects_aws_access_key(self):
        """Detects AWS access key ID pattern."""
        validator = OutputValidator()
        response = "Found key: AKIAIOSFODNN7EXAMPLE in the logs"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_private_key_header(self):
        """Detects private key BEGIN header."""
        validator = OutputValidator()
        response = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_jwt_token(self):
        """Detects JWT token pattern."""
        validator = OutputValidator()
        response = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_api_key_assignment(self):
        """Detects API key in assignment statement."""
        validator = OutputValidator()
        response = "The config has api_key='sk_live_1234567890abcdefghij'"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_env_var_secret(self):
        """Detects secret in environment variable."""
        validator = OutputValidator()
        response = "Found PASSWORD=SuperSecret123!@# in .env"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_allows_safe_response(self):
        """Allows response with no credentials."""
        validator = OutputValidator()
        response = "The bug is in user_service.py line 42"
        result = validator.validate(response, "investigate")

        assert result.is_valid is True
        assert result.failure_reason == ""
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestCredentialDetection -v`
Expected: FAIL with "AttributeError: 'OutputValidator' object has no attribute 'validate'"

**Step 3: Implement credential pattern matching**

Update `src/alm_orchestrator/output_validator.py`:

```python
"""Output validation for Claude responses."""

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Pattern, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating Claude's response."""
    is_valid: bool
    failure_reason: str  # Generic, no sensitive content


# Credential detection patterns
CREDENTIAL_PATTERNS = [
    # AWS
    r"AKIA[0-9A-Z]{16}",  # AWS Access Key ID
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


class OutputValidator:
    """Validates Claude's responses before posting to Jira/GitHub."""

    def __init__(self, entropy_threshold: float = 4.5, min_entropy_length: int = 20):
        """Initialize the validator with credential patterns.

        Args:
            entropy_threshold: Shannon entropy threshold for flagging suspicious strings.
            min_entropy_length: Minimum string length to check for high entropy.
        """
        self._entropy_threshold = entropy_threshold
        self._min_entropy_length = min_entropy_length
        self._credential_patterns: List[Pattern] = [
            re.compile(pattern) for pattern in CREDENTIAL_PATTERNS
        ]

    def validate(self, response: str, action: str) -> ValidationResult:
        """Check response for secrets and expected structure.

        Args:
            response: Claude's response text.
            action: The action type (investigate, fix, etc).

        Returns:
            ValidationResult indicating if response is safe to post.
        """
        # Check for credentials
        has_creds, reason = self._has_credentials(response)
        if has_creds:
            return ValidationResult(is_valid=False, failure_reason=reason)

        return ValidationResult(is_valid=True, failure_reason="")

    def _has_credentials(self, response: str) -> Tuple[bool, str]:
        """Check for leaked secrets/credentials.

        Args:
            response: The response text to check.

        Returns:
            Tuple of (found, reason) where reason is "credential_detected" if found.
        """
        for pattern in self._credential_patterns:
            if pattern.search(response):
                return (True, "credential_detected")

        return (False, "")
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestCredentialDetection -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add tests/test_output_validator.py src/alm_orchestrator/output_validator.py
git commit -m "feat: add credential pattern detection to OutputValidator"
```

---

## Task 3: Implement High-Entropy String Detection

**Files:**
- Modify: `src/alm_orchestrator/output_validator.py:70-100`
- Test: `tests/test_output_validator.py`

**Step 1: Write the failing test for high-entropy detection**

Add to `tests/test_output_validator.py`:

```python
class TestHighEntropyDetection:
    def test_detects_high_entropy_string(self):
        """Detects suspicious high-entropy random-looking string."""
        validator = OutputValidator()
        # High entropy: mixed case, numbers, symbols, 25+ chars
        response = "Found token: aB3$xZ9!mK7@pL2&qR5#wT8"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "high_entropy_string"

    def test_allows_normal_prose(self):
        """Allows normal English text with low entropy."""
        validator = OutputValidator()
        response = "The bug is caused by a null pointer dereference in the authentication module"
        result = validator.validate(response, "investigate")

        assert result.is_valid is True

    def test_allows_code_snippets(self):
        """Allows typical code which may have moderate entropy."""
        validator = OutputValidator()
        response = "def calculate_total(items):\n    return sum(item.price for item in items)"
        result = validator.validate(response, "fix")

        assert result.is_valid is True

    def test_allows_short_random_strings(self):
        """Allows short strings even if high entropy (under threshold)."""
        validator = OutputValidator()
        response = "Use abc123 as the ID"
        result = validator.validate(response, "implement")

        assert result.is_valid is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestHighEntropyDetection::test_detects_high_entropy_string -v`
Expected: FAIL (assertion error, is_valid is True when should be False)

**Step 3: Implement high-entropy string detection**

Update `src/alm_orchestrator/output_validator.py`:

```python
class OutputValidator:
    """Validates Claude's responses before posting to Jira/GitHub."""

    def __init__(self, entropy_threshold: float = 4.5, min_entropy_length: int = 20):
        """Initialize the validator with credential patterns.

        Args:
            entropy_threshold: Shannon entropy threshold for flagging suspicious strings.
            min_entropy_length: Minimum string length to check for high entropy.
        """
        self._entropy_threshold = entropy_threshold
        self._min_entropy_length = min_entropy_length
        self._credential_patterns: List[Pattern] = [
            re.compile(pattern) for pattern in CREDENTIAL_PATTERNS
        ]

    def validate(self, response: str, action: str) -> ValidationResult:
        """Check response for secrets and expected structure.

        Args:
            response: Claude's response text.
            action: The action type (investigate, fix, etc).

        Returns:
            ValidationResult indicating if response is safe to post.
        """
        # Check for credentials
        has_creds, reason = self._has_credentials(response)
        if has_creds:
            return ValidationResult(is_valid=False, failure_reason=reason)

        # Check for high-entropy strings
        if self._has_high_entropy_strings(response):
            return ValidationResult(is_valid=False, failure_reason="high_entropy_string")

        return ValidationResult(is_valid=True, failure_reason="")

    def _has_credentials(self, response: str) -> Tuple[bool, str]:
        """Check for leaked secrets/credentials.

        Args:
            response: The response text to check.

        Returns:
            Tuple of (found, reason) where reason is "credential_detected" if found.
        """
        for pattern in self._credential_patterns:
            if pattern.search(response):
                return (True, "credential_detected")

        return (False, "")

    def _has_high_entropy_strings(self, response: str) -> bool:
        """Check for suspicious random-looking strings.

        Args:
            response: The response text to check.

        Returns:
            True if high-entropy strings found that may be leaked secrets.
        """
        # Split into words, check each for high entropy
        words = re.findall(r'\S+', response)

        for word in words:
            # Skip short strings
            if len(word) < self._min_entropy_length:
                continue

            # Calculate Shannon entropy
            entropy = self._calculate_entropy(word)

            # Flag if entropy is suspiciously high
            if entropy > self._entropy_threshold:
                return True

        return False

    def _calculate_entropy(self, s: str) -> float:
        """Calculate Shannon entropy of a string.

        Args:
            s: The string to analyze.

        Returns:
            Shannon entropy value.
        """
        if not s:
            return 0.0

        # Count character frequencies
        char_counts: Dict[str, int] = {}
        for char in s:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        length = len(s)
        entropy = 0.0
        for count in char_counts.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestHighEntropyDetection -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add tests/test_output_validator.py src/alm_orchestrator/output_validator.py
git commit -m "feat: add high-entropy string detection to OutputValidator"
```

---

## Task 4: Implement Structural Validation

**Files:**
- Modify: `src/alm_orchestrator/output_validator.py:10-15`
- Test: `tests/test_output_validator.py`

**Step 1: Write the failing test for structural validation**

Add to `tests/test_output_validator.py`:

```python
class TestStructuralValidation:
    def test_investigate_valid_structure(self):
        """Validates investigate response with all required sections."""
        validator = OutputValidator()
        response = """
        SUMMARY
        The bug occurs in auth module.

        ROOT CAUSE
        Null pointer dereference on line 42.

        EVIDENCE
        Stack trace shows the crash point.
        """
        result = validator.validate(response, "investigate")

        assert result.is_valid is True

    def test_investigate_missing_section(self):
        """Rejects investigate response missing required sections."""
        validator = OutputValidator()
        response = """
        SUMMARY
        The bug occurs in auth module.

        Some other content but no ROOT CAUSE or EVIDENCE.
        """
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "missing_structure"

    def test_fix_valid_structure(self):
        """Validates fix response with required sections."""
        validator = OutputValidator()
        response = """
        What files you changed:
        - auth.py
        - utils.py

        What the fix does:
        Adds null check before dereferencing.
        """
        result = validator.validate(response, "fix")

        assert result.is_valid is True

    def test_recommend_valid_structure(self):
        """Validates recommend response with options."""
        validator = OutputValidator()
        response = """
        OPTION 1: Refactor auth module

        OPTION 2: Add caching layer

        RECOMMENDATION: Use option 1 for better maintainability.
        """
        result = validator.validate(response, "recommend")

        assert result.is_valid is True

    def test_case_insensitive_matching(self):
        """Section matching is case-insensitive."""
        validator = OutputValidator()
        response = """
        summary
        Bug in auth.

        root cause
        Null pointer.

        evidence
        Stack trace.
        """
        result = validator.validate(response, "investigate")

        assert result.is_valid is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestStructuralValidation::test_investigate_missing_section -v`
Expected: FAIL (is_valid is True when should be False)

**Step 3: Implement structural validation**

Update `src/alm_orchestrator/output_validator.py`:

```python
# Add after CREDENTIAL_PATTERNS constant
SECTION_REQUIREMENTS = {
    "investigate": ["SUMMARY", "ROOT CAUSE", "EVIDENCE"],
    "impact": ["FILES THAT WOULD CHANGE", "RISK ASSESSMENT"],
    "recommend": ["OPTION 1", "RECOMMENDATION"],
    "fix": ["What files you changed", "What the fix does"],
    "implement": ["What files you created", "How the feature works"],
    "code_review": ["SUMMARY", "HIGH PRIORITY", "LOW PRIORITY"],
    "security_review": ["SUMMARY", "HIGH PRIORITY FINDINGS"],
}


class OutputValidator:
    """Validates Claude's responses before posting to Jira/GitHub."""

    def __init__(self, entropy_threshold: float = 4.5, min_entropy_length: int = 20):
        """Initialize the validator with credential patterns.

        Args:
            entropy_threshold: Shannon entropy threshold for flagging suspicious strings.
            min_entropy_length: Minimum string length to check for high entropy.
        """
        self._entropy_threshold = entropy_threshold
        self._min_entropy_length = min_entropy_length
        self._credential_patterns: List[Pattern] = [
            re.compile(pattern) for pattern in CREDENTIAL_PATTERNS
        ]
        self._section_requirements: Dict[str, List[str]] = SECTION_REQUIREMENTS

    def validate(self, response: str, action: str) -> ValidationResult:
        """Check response for secrets and expected structure.

        Args:
            response: Claude's response text.
            action: The action type (investigate, fix, etc).

        Returns:
            ValidationResult indicating if response is safe to post.
        """
        # Check for credentials
        has_creds, reason = self._has_credentials(response)
        if has_creds:
            return ValidationResult(is_valid=False, failure_reason=reason)

        # Check for high-entropy strings
        if self._has_high_entropy_strings(response):
            return ValidationResult(is_valid=False, failure_reason="high_entropy_string")

        # Check for expected structure
        if not self._has_expected_structure(response, action):
            return ValidationResult(is_valid=False, failure_reason="missing_structure")

        return ValidationResult(is_valid=True, failure_reason="")

    def _has_expected_structure(self, response: str, action: str) -> bool:
        """Check if expected section headers are present.

        Args:
            response: The response text to check.
            action: The action type (determines required sections).

        Returns:
            True if all required sections found (or no requirements defined).
        """
        # Get required sections for this action
        required_sections = self._section_requirements.get(action, [])

        # No requirements means pass
        if not required_sections:
            return True

        # Case-insensitive substring matching
        response_lower = response.lower()

        for section in required_sections:
            if section.lower() not in response_lower:
                return False

        return True
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_output_validator.py::TestStructuralValidation -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add tests/test_output_validator.py src/alm_orchestrator/output_validator.py
git commit -m "feat: add structural validation to OutputValidator"
```

---

## Task 5: Add Validation Helper to BaseAction

**Files:**
- Modify: `src/alm_orchestrator/actions/base.py:22-30,56-75`
- Test: `tests/test_actions/test_base.py`

**Step 1: Write the failing test for _validate_and_post helper**

Add to `tests/test_actions/test_base.py`:

```python
from alm_orchestrator.output_validator import OutputValidator, ValidationResult


class ValidatorTestAction(BaseAction):
    """Action for testing validator integration."""

    @property
    def label(self) -> str:
        return "ai-validatortest"

    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        return "executed"


class TestValidateAndPost:
    def test_posts_valid_response(self):
        """Valid response is posted to Jira."""
        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=True,
            failure_reason=""
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action._validate_and_post(
            issue_key="TEST-123",
            response="The bug is in auth.py",
            action_type="investigate",
            jira_client=mock_jira
        )

        assert result is True
        mock_validator.validate.assert_called_once_with(
            "The bug is in auth.py",
            "investigate"
        )
        mock_jira.add_comment.assert_called_once_with(
            "TEST-123",
            "The bug is in auth.py"
        )

    def test_blocks_invalid_response(self, caplog):
        """Invalid response is blocked and warning posted."""
        import logging
        caplog.set_level(logging.WARNING)

        mock_jira = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            is_valid=False,
            failure_reason="credential_detected"
        )

        action = ValidatorTestAction(prompts_dir="/tmp/prompts")
        action._validator = mock_validator

        result = action._validate_and_post(
            issue_key="TEST-456",
            response="Found key: AKIAIOSFODNN7EXAMPLE",
            action_type="investigate",
            jira_client=mock_jira
        )

        assert result is False

        # Verify validator was called
        mock_validator.validate.assert_called_once()

        # Verify warning comment was posted
        assert mock_jira.add_comment.call_count == 1
        call_args = mock_jira.add_comment.call_args[0]
        assert call_args[0] == "TEST-456"
        assert "AI RESPONSE BLOCKED" in call_args[1]
        assert "flagged by automated security checks" in call_args[1]

        # Verify original response was NOT posted
        assert "AKIAIOSFODNN7EXAMPLE" not in str(mock_jira.add_comment.call_args_list)

        # Verify warning was logged
        assert any(
            "Suspicious response for TEST-456" in record.message
            and "credential_detected" in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_base.py::TestValidateAndPost -v`
Expected: FAIL with "AttributeError: 'ValidatorTestAction' object has no attribute '_validate_and_post'"

**Step 3: Implement _validate_and_post helper in BaseAction**

Update `src/alm_orchestrator/actions/base.py`:

```python
"""Base class for AI action handlers."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# Action label and template conventions
AI_LABEL_PREFIX = "ai-"
TEMPLATE_EXTENSION = ".md"


class BaseAction(ABC):
    """Abstract base class for all AI actions.

    Each action handles a specific AI label (e.g., ai-investigate, ai-fix).
    """

    def __init__(self, prompts_dir: str, validator: Any):
        """Initialize with prompts directory and validator.

        Args:
            prompts_dir: Path to directory containing prompt templates.
            validator: OutputValidator instance for response validation.
        """
        self._prompts_dir = prompts_dir
        self._validator = validator

    @property
    @abstractmethod
    def label(self) -> str:
        """The AI label this action handles (e.g., 'ai-investigate')."""
        pass

    @abstractmethod
    def execute(
        self,
        issue: Any,
        jira_client: Any,
        github_client: Any,
        claude_executor: Any
    ) -> str:
        """Execute the action for the given Jira issue.

        Args:
            issue: The Jira issue object.
            jira_client: JiraClient instance for posting comments.
            github_client: GitHubClient instance for repo/PR operations.
            claude_executor: ClaudeExecutor instance for running Claude Code.

        Returns:
            A summary of what was done.
        """
        pass

    def get_template_path(self) -> str:
        """Get the path to this action's prompt template.

        Convention: ai-{name} label uses {name}.md template.

        Returns:
            Absolute path to the template file.
        """
        template_name = self.label.replace(AI_LABEL_PREFIX, "") + TEMPLATE_EXTENSION
        return os.path.join(self._prompts_dir, template_name)

    @property
    def allowed_issue_types(self) -> list[str]:
        """Issue types this action can run on. Override in subclasses.

        Returns:
            List of allowed issue type names (e.g., ["Bug", "Story"]).
            Empty list means no validation (all types allowed).
        """
        return []

    def validate_issue_type(self, issue, jira_client) -> bool:
        """Check if issue type is allowed. Posts rejection comment if not.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting comments and removing labels.

        Returns:
            True if valid (or no validation configured), False if rejected.
        """
        allowed = self.allowed_issue_types
        if not allowed:
            return True

        issue_type = issue.fields.issuetype.name
        if issue_type in allowed:
            return True

        # Log rejection
        logger.debug(
            f"Rejecting {issue.key}: {self.label} does not support issue type {issue_type}"
        )

        # Post rejection comment
        allowed_str = ", ".join(allowed)
        header = "INVALID ISSUE TYPE"
        comment = (
            f"{header}\n"
            f"{'=' * len(header)}\n\n"
            f"The {self.label} action only works on: {allowed_str}\n\n"
            f"This issue is a {issue_type}. "
            f"Please use an appropriate action for this issue type."
        )
        jira_client.add_comment(issue.key, comment)

        # Remove label
        jira_client.remove_label(issue.key, self.label)

        return False

    def _validate_and_post(
        self,
        issue_key: str,
        response: str,
        action_type: str,
        jira_client: Any
    ) -> bool:
        """Validate response and post to Jira if safe.

        Args:
            issue_key: The Jira issue key.
            response: Claude's response text.
            action_type: The action type for structural validation.
            jira_client: JiraClient for posting comments.

        Returns:
            True if response was posted, False if blocked.
        """
        # Validate response
        validation = self._validator.validate(response, action_type)

        if not validation.is_valid:
            # Log warning (issue key only, no sensitive content)
            logger.warning(
                f"Suspicious response for {issue_key}: {validation.failure_reason}"
            )

            # Post generic warning comment
            header = "AI RESPONSE BLOCKED"
            comment = (
                f"{header}\n{'=' * len(header)}\n\n"
                "The AI agent's response was flagged by automated security checks "
                "and has not been posted. Please review the issue manually."
            )
            jira_client.add_comment(issue_key, comment)

            return False

        # Valid - post the response
        jira_client.add_comment(issue_key, response)
        return True
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_base.py::TestValidateAndPost -v`
Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add tests/test_actions/test_base.py src/alm_orchestrator/actions/base.py
git commit -m "feat: add _validate_and_post helper to BaseAction"
```

---

## Task 6: Integrate Validator into Daemon and Router

**Files:**
- Modify: `src/alm_orchestrator/daemon.py:3,11-12,39-41`
- Modify: `src/alm_orchestrator/router.py:74-106`
- Test: `tests/test_daemon.py`
- Test: `tests/test_router.py`

**Step 1: Write the failing test for daemon validator instantiation**

Add to `tests/test_daemon.py`:

```python
from alm_orchestrator.output_validator import OutputValidator


class TestDaemonValidatorIntegration:
    def test_daemon_creates_validator(self):
        """Daemon instantiates OutputValidator on init."""
        config = MagicMock()
        config.claude_timeout_seconds = 600

        with patch('alm_orchestrator.daemon.JiraClient'), \
             patch('alm_orchestrator.daemon.GitHubClient'), \
             patch('alm_orchestrator.daemon.ClaudeExecutor'), \
             patch('alm_orchestrator.daemon.discover_actions') as mock_discover:

            mock_router = MagicMock()
            mock_router.action_count = 1
            mock_router.action_names = ["TestAction"]
            mock_discover.return_value = mock_router

            daemon = Daemon(config, prompts_dir="/tmp/prompts")

            # Verify validator was created and passed to discover_actions
            mock_discover.assert_called_once()
            call_kwargs = mock_discover.call_args[1]
            assert 'validator' in call_kwargs
            assert isinstance(call_kwargs['validator'], OutputValidator)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon.py::TestDaemonValidatorIntegration -v`
Expected: FAIL with "AssertionError: 'validator' not in call_kwargs"

**Step 3: Update daemon to create and pass validator**

Update `src/alm_orchestrator/daemon.py`:

```python
"""Main daemon loop for the ALM Orchestrator."""

import logging
import signal
import time

from alm_orchestrator.config import Config
from alm_orchestrator.jira_client import JiraClient
from alm_orchestrator.github_client import GitHubClient
from alm_orchestrator.claude_executor import ClaudeExecutor
from alm_orchestrator.output_validator import OutputValidator
from alm_orchestrator.router import discover_actions


logger = logging.getLogger(__name__)


class Daemon:
    """Long-running daemon that polls Jira and processes AI labels."""

    def __init__(self, config: Config, prompts_dir: str):
        """Initialize the daemon.

        Args:
            config: Application configuration.
            prompts_dir: Path to prompt templates directory.
        """
        self._config = config
        self._prompts_dir = prompts_dir
        self._running = False

        # Initialize clients
        self._jira = JiraClient(config)
        self._github = GitHubClient(config)
        self._claude = ClaudeExecutor(
            prompts_dir=prompts_dir,
            timeout_seconds=config.claude_timeout_seconds
        )

        # Initialize output validator
        self._validator = OutputValidator()

        # Auto-discover and register all actions
        self._router = discover_actions(prompts_dir, validator=self._validator)
        logger.info(f"Discovered {self._router.action_count} action(s): {', '.join(self._router.action_names)}")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
```

**Step 4: Write the failing test for router validator passing**

Add to `tests/test_router.py`:

```python
from alm_orchestrator.output_validator import OutputValidator


class TestDiscoverActionsWithValidator:
    def test_validator_passed_to_actions(self):
        """Actions are instantiated with validator."""
        validator = OutputValidator()

        with patch('alm_orchestrator.router.pkgutil.iter_modules') as mock_iter, \
             patch('alm_orchestrator.router.importlib.import_module') as mock_import:

            # Mock module with a test action
            mock_action_class = MagicMock()
            mock_action_instance = MagicMock()
            mock_action_instance.label = "ai-test"
            mock_action_class.return_value = mock_action_instance

            mock_module = MagicMock()
            mock_module.TestAction = mock_action_class

            mock_iter.return_value = [(None, "test", False)]
            mock_import.return_value = mock_module

            # Make it look like a BaseAction subclass
            with patch('alm_orchestrator.router.BaseAction', MagicMock()):
                mock_action_class.__bases__ = (MagicMock(),)

                router = discover_actions("/tmp/prompts", validator=validator)

                # Verify action was instantiated with prompts_dir and validator
                mock_action_class.assert_called_once_with(
                    "/tmp/prompts",
                    validator=validator
                )
```

**Step 5: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_router.py::TestDiscoverActionsWithValidator -v`
Expected: FAIL with TypeError or assertion error on validator argument

**Step 6: Update discover_actions to accept and pass validator**

Update `src/alm_orchestrator/router.py`:

```python
def discover_actions(prompts_dir: str, validator: Any = None) -> LabelRouter:
    """Auto-discover and register all action handlers.

    Scans the actions package for BaseAction subclasses,
    instantiates each with prompts_dir and validator, and registers them.

    Args:
        prompts_dir: Path to prompt templates directory.
        validator: Optional OutputValidator instance for response validation.

    Returns:
        LabelRouter with all discovered actions registered.
    """
    import importlib
    import pkgutil
    from alm_orchestrator import actions

    router = LabelRouter()

    # Iterate through all modules in the actions package
    for importer, modname, ispkg in pkgutil.iter_modules(actions.__path__):
        if modname == "base":
            continue  # Skip the base module

        module = importlib.import_module(f"alm_orchestrator.actions.{modname}")

        # Find all BaseAction subclasses in this module
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and
                issubclass(obj, BaseAction) and
                obj is not BaseAction):
                action = obj(prompts_dir, validator=validator)
                router.register(action.label, action)

    return router
```

Add import at top:

```python
from typing import Any, Dict, List
```

**Step 7: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_daemon.py::TestDaemonValidatorIntegration tests/test_router.py::TestDiscoverActionsWithValidator -v`
Expected: PASS (both tests)

**Step 8: Commit**

```bash
git add src/alm_orchestrator/daemon.py src/alm_orchestrator/router.py tests/test_daemon.py tests/test_router.py
git commit -m "feat: integrate OutputValidator into daemon and router"
```

---

## Task 7: Update InvestigateAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/investigate.py:56-66`
- Test: `tests/test_actions/test_investigate.py`

**Step 1: Write the failing test for validator usage**

Add to `tests/test_actions/test_investigate.py`:

```python
from alm_orchestrator.output_validator import OutputValidator, ValidationResult


class TestInvestigateWithValidator:
    def test_uses_validator_when_available(self):
        """InvestigateAction uses _validate_and_post when validator present."""
        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_executor = MagicMock()
        mock_validator = MagicMock()

        mock_issue = MagicMock()
        mock_issue.key = "BUG-123"
        mock_issue.fields.summary = "Test bug"
        mock_issue.fields.description = "Description"
        mock_issue.fields.issuetype.name = "Bug"

        mock_github.clone_repo.return_value = "/tmp/test"

        mock_result = MagicMock()
        mock_result.content = "Investigation results"
        mock_result.cost_usd = 0.05
        mock_executor.execute_with_template.return_value = mock_result

        mock_validator.validate.return_value = ValidationResult(
            is_valid=True,
            failure_reason=""
        )

        action = InvestigateAction(prompts_dir="/tmp/prompts", validator=mock_validator)
        result = action.execute(mock_issue, mock_jira, mock_github, mock_executor)

        # Verify validator was used
        mock_validator.validate.assert_called_once()

        # Verify comment was posted (validation passed)
        assert mock_jira.add_comment.call_count == 1

    def test_blocks_response_when_validation_fails(self):
        """InvestigateAction blocks response when validator rejects it."""
        mock_jira = MagicMock()
        mock_github = MagicMock()
        mock_executor = MagicMock()
        mock_validator = MagicMock()

        mock_issue = MagicMock()
        mock_issue.key = "BUG-456"
        mock_issue.fields.summary = "Test bug"
        mock_issue.fields.description = "Description"
        mock_issue.fields.issuetype.name = "Bug"

        mock_github.clone_repo.return_value = "/tmp/test"

        mock_result = MagicMock()
        mock_result.content = "Found key: AKIAIOSFODNN7EXAMPLE"
        mock_result.cost_usd = 0.05
        mock_executor.execute_with_template.return_value = mock_result

        mock_validator.validate.return_value = ValidationResult(
            is_valid=False,
            failure_reason="credential_detected"
        )

        action = InvestigateAction(prompts_dir="/tmp/prompts", validator=mock_validator)
        result = action.execute(mock_issue, mock_jira, mock_github, mock_executor)

        # Verify validation was attempted
        mock_validator.validate.assert_called_once_with(
            "Found key: AKIAIOSFODNN7EXAMPLE",
            "investigate"
        )

        # Verify blocked comment was posted (not the actual response)
        assert mock_jira.add_comment.call_count == 1
        call_args = mock_jira.add_comment.call_args[0]
        assert "AI RESPONSE BLOCKED" in call_args[1]
        assert "AKIAIOSFODNN7EXAMPLE" not in call_args[1]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_investigate.py::TestInvestigateWithValidator -v`
Expected: FAIL (validator not called, or called with wrong arguments)

**Step 3: Update InvestigateAction to use _validate_and_post**

Update `src/alm_orchestrator/actions/investigate.py`:

```python
    def execute(self, issue, jira_client, github_client, claude_executor) -> str:
        """Execute root cause investigation.

        Args:
            issue: Jira issue object.
            jira_client: JiraClient for posting results.
            github_client: GitHubClient for cloning repo.
            claude_executor: ClaudeExecutor for running analysis.

        Returns:
            Summary of the action.
        """
        issue_key = issue.key
        summary = issue.fields.summary
        description = issue.fields.description or ""

        # Validate issue type
        if not self.validate_issue_type(issue, jira_client):
            return f"Rejected {issue_key}: invalid issue type"

        # Clone the repo
        work_dir = github_client.clone_repo()

        try:
            # Run Claude with the investigate template (read-only tools)
            template_path = os.path.join(self._prompts_dir, "investigate.md")
            result = claude_executor.execute_with_template(
                work_dir=work_dir,
                template_path=template_path,
                context={
                    "issue_key": issue_key,
                    "issue_summary": summary,
                    "issue_description": description,
                },
                action="investigate",
            )

            # Format response with cost footer
            header = "INVESTIGATION RESULTS"
            response = (
                f"{header}\n{'=' * len(header)}\n\n{result.content}"
                f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
            )

            # Validate and post (or block if suspicious)
            posted = self._validate_and_post(
                issue_key=issue_key,
                response=response,
                action_type="investigate",
                jira_client=jira_client
            )

            # Always remove the label to mark as processed (even if blocked)
            jira_client.remove_label(issue_key, self.label)

            if posted:
                return f"Investigation complete for {issue_key}"
            else:
                return f"Investigation response blocked for {issue_key}"

        finally:
            # Always cleanup
            github_client.cleanup(work_dir)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_investigate.py::TestInvestigateWithValidator -v`
Expected: PASS (both tests)

**Step 5: Run all investigate tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_investigate.py -v`
Expected: PASS (all tests still pass)

**Step 6: Commit**

```bash
git add src/alm_orchestrator/actions/investigate.py tests/test_actions/test_investigate.py
git commit -m "feat: use OutputValidator in InvestigateAction"
```

---

## Task 8: Update ImpactAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/impact.py`
- Test: `tests/test_actions/test_impact.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/impact.py`:

```python
# Replace the comment posting section with:
# Format response with cost footer
header = "IMPACT ANALYSIS"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="impact",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Impact analysis complete for {issue_key}"
else:
    return f"Impact analysis response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_impact.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/impact.py
git commit -m "feat: use OutputValidator in ImpactAction"
```

---

## Task 9: Update RecommendAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/recommend.py`
- Test: `tests/test_actions/test_recommend.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/recommend.py`:

```python
# Replace the comment posting section with:
# Format response with cost footer
header = "RECOMMENDATIONS"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="recommend",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Recommendations complete for {issue_key}"
else:
    return f"Recommendations response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_recommend.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/recommend.py
git commit -m "feat: use OutputValidator in RecommendAction"
```

---

## Task 10: Update FixAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/fix.py`
- Test: `tests/test_actions/test_fix.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/fix.py`:

```python
# Replace the comment posting section with:
# Format response with PR link and cost
header = "FIX IMPLEMENTATION"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\nPull Request: {pr_url}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="fix",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Fix complete for {issue_key}: {pr_url}"
else:
    return f"Fix response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_fix.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/fix.py
git commit -m "feat: use OutputValidator in FixAction"
```

---

## Task 11: Update ImplementAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/implement.py`
- Test: `tests/test_actions/test_implement.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/implement.py`:

```python
# Replace the comment posting section with:
# Format response with PR link and cost
header = "FEATURE IMPLEMENTATION"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\nPull Request: {pr_url}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="implement",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Implementation complete for {issue_key}: {pr_url}"
else:
    return f"Implementation response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_implement.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/implement.py
git commit -m "feat: use OutputValidator in ImplementAction"
```

---

## Task 12: Update CodeReviewAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/code_review.py`
- Test: `tests/test_actions/test_code_review.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/code_review.py`:

```python
# Replace the comment posting section with:
# Format response with cost footer
header = "CODE REVIEW"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="code_review",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Code review complete for {issue_key}"
else:
    return f"Code review response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_code_review.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/code_review.py
git commit -m "feat: use OutputValidator in CodeReviewAction"
```

---

## Task 13: Update SecurityReviewAction to Use Validator

**Files:**
- Modify: `src/alm_orchestrator/actions/security_review.py`
- Test: `tests/test_actions/test_security_review.py`

**Step 1: Update execute method to use _validate_and_post**

Update the execute method in `src/alm_orchestrator/actions/security_review.py`:

```python
# Replace the comment posting section with:
# Format response with cost footer
header = "SECURITY REVIEW"
response = (
    f"{header}\n{'=' * len(header)}\n\n{result.content}"
    f"\n\n---\n_Cost: ${result.cost_usd:.4f}_"
)

# Validate and post
posted = self._validate_and_post(
    issue_key=issue_key,
    response=response,
    action_type="security_review",
    jira_client=jira_client
)

# Always remove the label to mark as processed (even if blocked)
jira_client.remove_label(issue_key, self.label)

if posted:
    return f"Security review complete for {issue_key}"
else:
    return f"Security review response blocked for {issue_key}"
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_actions/test_security_review.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/alm_orchestrator/actions/security_review.py
git commit -m "feat: use OutputValidator in SecurityReviewAction"
```

---

## Task 14: Integration Testing and Documentation

**Files:**
- Test: Run full test suite with coverage
- Update: `docs/2025-12-08-output-monitoring-design.md` status

**Step 1: Run full test suite with coverage**

Run: `source .venv/bin/activate && pytest tests/ -v --cov=src/alm_orchestrator --cov-report=term-missing`
Expected: PASS with high coverage for output_validator.py

**Step 2: Verify all action tests still pass**

Run: `source .venv/bin/activate && pytest tests/test_actions/ -v`
Expected: PASS (all action tests)

**Step 3: Manual smoke test of validator**

Run Python REPL test:

```python
from alm_orchestrator.output_validator import OutputValidator

validator = OutputValidator()

# Test credential detection
result = validator.validate("Found key: AKIAIOSFODNN7EXAMPLE", "investigate")
assert result.is_valid is False
assert result.failure_reason == "credential_detected"

# Test structural validation
result = validator.validate("SUMMARY\nBug in auth\nROOT CAUSE\nNull ptr\nEVIDENCE\nStack trace", "investigate")
assert result.is_valid is True

print("Manual validation tests passed!")
```

**Step 4: Update design doc status**

Update `docs/2025-12-08-output-monitoring-design.md` line 3:

```markdown
Status: **Implemented**
```

**Step 5: Commit documentation update**

```bash
git add docs/2025-12-08-output-monitoring-design.md
git commit -m "docs: mark output monitoring as implemented"
```

---

## Completion Checklist

After completing all tasks, verify:

- [ ] `OutputValidator` class created with all three detection methods
- [ ] Credential patterns detect AWS keys, private keys, JWTs, API keys, env vars
- [ ] High-entropy detection uses Shannon entropy threshold
- [ ] Structural validation checks for required sections per action type
- [ ] `BaseAction._validate_and_post()` helper implemented
- [ ] Daemon creates and passes validator to router
- [ ] Router passes validator to all action constructors
- [ ] All 7 actions use `_validate_and_post()` instead of direct posting
- [ ] Full test suite passes with good coverage
- [ ] Design doc updated to "Implemented" status

**IMPORTANT:** Use TDD throughout - write failing test, verify failure, implement, verify success, commit. No shortcuts.
