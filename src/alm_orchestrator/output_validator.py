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
