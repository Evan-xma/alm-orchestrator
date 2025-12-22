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
