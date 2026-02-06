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
        response = """
        SUMMARY
        The bug is in user_service.py line 42

        ROOT CAUSE
        Null pointer dereference

        EVIDENCE
        Stack trace shows the issue
        """
        result = validator.validate(response, "investigate")

        assert result.is_valid is True
        assert result.failure_reason == ""


class TestHighEntropyDetection:
    def test_detects_high_entropy_string(self):
        """Detects suspicious high-entropy random-looking string."""
        validator = OutputValidator()
        # High entropy: mixed case, numbers, symbols, 25+ chars
        # Use a string that won't match keyword patterns
        response = "Found value: aB3xZ9mK7pL2qR5wT8yU4vN"
        result = validator.validate(response, "investigate")

        assert result.is_valid is False
        assert result.failure_reason == "high_entropy_string"

    def test_allows_normal_prose(self):
        """Allows normal English text with low entropy."""
        validator = OutputValidator()
        response = """
        SUMMARY
        The bug is caused by a null pointer dereference in the authentication module

        ROOT CAUSE
        Missing null check

        EVIDENCE
        Stack trace confirms
        """
        result = validator.validate(response, "investigate")

        assert result.is_valid is True

    def test_allows_code_snippets(self):
        """Allows typical code which may have moderate entropy."""
        validator = OutputValidator()
        response = """
        What files you changed:
        - utils.py

        What the fix does:
        def calculate_total(items):
            return sum(item.price for item in items)
        """
        result = validator.validate(response, "fix")

        assert result.is_valid is True

    def test_allows_short_random_strings(self):
        """Allows short strings even if high entropy (under threshold)."""
        validator = OutputValidator()
        response = """
        What files you created:
        - models/user.py

        How the feature works:
        Use abc123 as the ID
        """
        result = validator.validate(response, "implement")

        assert result.is_valid is True


class TestConnectionStringDetection:
    def test_detects_mongodb_connection_string(self):
        validator = OutputValidator()
        result = validator.validate(
            "mongodb+srv://user:p4ssw0rd@cluster.mongodb.net/db", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_mysql_connection_string(self):
        validator = OutputValidator()
        result = validator.validate(
            "mysql://root:password123@localhost/mydb", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_redis_connection_string(self):
        validator = OutputValidator()
        result = validator.validate(
            "redis://default:s3cret@redis.example.com:6379", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_postgres_connection_string(self):
        validator = OutputValidator()
        result = validator.validate(
            "postgresql://admin:SecretPass123@db.example.com:5432/mydb", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_allows_url_without_credentials(self):
        validator = OutputValidator()
        result = validator.validate(
            "https://api.example.com/v1/users", "investigate"
        )
        assert result.is_valid is True


class TestWebhookDetection:
    def test_detects_slack_webhook(self):
        validator = OutputValidator()
        result = validator.validate(
            "https://hooks.slack.com/services/T00000000/B00000000/xxxxxxxxxxxx",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_discord_webhook(self):
        validator = OutputValidator()
        result = validator.validate(
            "https://discord.com/api/webhooks/123456789/abcdefghijklmnop",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"


class TestPrivateKeyDetection:
    def test_detects_encrypted_private_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "-----BEGIN ENCRYPTED PRIVATE KEY-----", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_generic_private_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "-----BEGIN PRIVATE KEY-----", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_pgp_private_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "-----BEGIN PGP PRIVATE KEY BLOCK-----", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"


class TestSecretKeywordDetection:
    def test_detects_yaml_password(self):
        validator = OutputValidator()
        result = validator.validate(
            "password: MyP@ssw0rd123", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_json_password(self):
        validator = OutputValidator()
        result = validator.validate(
            '"password": "correcthorsebatterystaple"', "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_secret_key_assignment(self):
        validator = OutputValidator()
        result = validator.validate(
            'SECRET_KEY=django-insecure-abc123def', "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_token_in_yaml(self):
        validator = OutputValidator()
        result = validator.validate(
            "token: ghp_abc123def456ghi789jkl012mno345pqr678", "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"


class TestVendorKeyDetection:
    def test_detects_github_pat(self):
        validator = OutputValidator()
        result = validator.validate(
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_github_fine_grained_pat(self):
        validator = OutputValidator()
        result = validator.validate(
            "github_pat_11AAAAAA_abcdefghijklmnopqrstuvwxyz",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_anthropic_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_openai_project_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_slack_bot_token(self):
        validator = OutputValidator()
        # Use short pattern that matches regex but won't trigger GitHub push protection
        result = validator.validate(
            "xoxb-FAKE-TEST-VALUE",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_sendgrid_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "SG.abcdefghij.1234567890abcdefghij",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_stripe_secret_key(self):
        validator = OutputValidator()
        # Use 'test' mode prefix to avoid GitHub push protection
        result = validator.validate(
            "sk_live_00000000000000FAKETEST",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"

    def test_detects_stripe_restricted_key(self):
        validator = OutputValidator()
        result = validator.validate(
            "rk_live_00000000000000FAKETEST",
            "investigate"
        )
        assert result.is_valid is False
        assert result.failure_reason == "credential_detected"
