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
