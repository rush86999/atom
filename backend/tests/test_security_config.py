"""
Unit Tests for Security Configuration

Tests for SECRET_KEY validation and security configuration checks.
"""

import os
import pytest
from unittest.mock import patch, Mock

from core.config import SecurityConfig, get_config


class TestSecurityConfig:
    """Test cases for SecurityConfig"""

    def test_default_secret_key_in_development(self):
        """Test that default SECRET_KEY is allowed in development"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=False):
            config = SecurityConfig()

            assert config.secret_key == "atom-secret-key-change-in-production"

    def test_custom_secret_key(self):
        """Test that custom SECRET_KEY can be set"""
        custom_key = "my-custom-secret-key"

        with patch.dict(os.environ, {'SECRET_KEY': custom_key}, clear=False):
            config = SecurityConfig()

            assert config.secret_key == custom_key

    @patch('core.config.logger')
    def test_default_secret_key_warning_in_production(self, mock_logger):
        """Test that default SECRET_KEY logs error in production"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=False):
            config = SecurityConfig()

            # Should log error about using default key
            assert mock_logger.error.called
            assert any(
                "CRITICAL" in str(call) and "default SECRET_KEY" in str(call)
                for call in mock_logger.error.call_args_list
            )

    @patch('core.config.logger')
    @patch('core.config.secrets')
    def test_automatic_key_generation_in_development(self, mock_secrets, mock_logger):
        """Test automatic key generation in development when SECRET_KEY not set"""
        mock_key = "generated-random-key-12345678"
        mock_secrets.token_urlsafe.return_value = mock_key

        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=False):
            # Remove SECRET_KEY from environment
            original_env = os.environ.get('SECRET_KEY')
            if 'SECRET_KEY' in os.environ:
                del os.environ['SECRET_KEY']

            try:
                config = SecurityConfig()

                # Should have generated a random key
                mock_secrets.token_urlsafe.assert_called_once_with(32)

                # Should log warning
                assert mock_logger.warning.called
            finally:
                # Restore original env var
                if original_env:
                    os.environ['SECRET_KEY'] = original_env

    def test_allow_dev_temp_users_default(self):
        """Test default value of allow_dev_temp_users"""
        config = SecurityConfig()

        assert config.allow_dev_temp_users is False

    def test_allow_dev_temp_users_enabled(self):
        """Test that allow_dev_temp_users can be enabled"""
        with patch.dict(os.environ, {'ALLOW_DEV_TEMP_USERS': 'true'}, clear=False):
            config = SecurityConfig()

            assert config.allow_dev_temp_users is True

    def test_encryption_key_optional(self):
        """Test that ENCRYPTION_KEY is optional"""
        config = SecurityConfig()

        assert config.encryption_key is None

    def test_encryption_key_can_be_set(self):
        """Test that ENCRYPTION_KEY can be set"""
        custom_key = "my-encryption-key"

        with patch.dict(os.environ, {'ENCRYPTION_KEY': custom_key}, clear=False):
            config = SecurityConfig()

            assert config.encryption_key == custom_key

    def test_cors_origins_default(self):
        """Test default CORS origins"""
        config = SecurityConfig()

        assert config.cors_origins is not None
        assert len(config.cors_origins) > 0

    def test_cors_origins_custom(self):
        """Test custom CORS origins"""
        custom_origins = "http://example.com,http://test.com"

        with patch.dict(os.environ, {'CORS_ORIGINS': custom_origins}, clear=False):
            config = SecurityConfig()

            assert "http://example.com" in config.cors_origins
            assert "http://test.com" in config.cors_origins

    def test_jwt_expiration_default(self):
        """Test default JWT expiration"""
        config = SecurityConfig()

        assert config.jwt_expiration == 86400  # 24 hours

    def test_jwt_expiration_custom(self):
        """Test custom JWT expiration"""
        custom_expiration = 3600  # 1 hour

        with patch.dict(os.environ, {'JWT_EXPIRATION': str(custom_expiration)}, clear=False):
            config = SecurityConfig()

            assert config.jwt_expiration == custom_expiration


class TestGetConfig:
    """Test cases for get_config function"""

    def test_get_config_returns_singleton(self):
        """Test that get_config returns the same instance"""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_get_config_security_config(self):
        """Test that get_config includes SecurityConfig"""
        config = get_config()

        assert config.security is not None
        assert isinstance(config.security, SecurityConfig)


class TestSecurityValidation:
    """Test cases for security validation in config"""

    @patch('core.config.logger')
    def test_validate_security_issues_production_default_key(self, mock_logger):
        """Test validation catches default key in production"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=False):
            config = SecurityConfig()
            issues = config.validate()

            assert issues['valid'] is False
            assert len(issues['issues']) > 0
            assert any('Secret key' in issue for issue in issues['issues'])

    def test_validate_security_passes_with_custom_key(self):
        """Test validation passes with custom key"""
        with patch.dict(
            os.environ,
            {
                'SECRET_KEY': 'my-secure-custom-key',
                'ENVIRONMENT': 'production'
            },
            clear=False
        ):
            config = SecurityConfig()
            issues = config.validate()

            # Should not have secret key issue
            secret_key_issues = [issue for issue in issues['issues'] if 'Secret key' in issue]
            assert len(secret_key_issues) == 0
