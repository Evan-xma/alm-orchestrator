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
