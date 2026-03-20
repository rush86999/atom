"""
Unit Tests for Lux Config Service

Tests application configuration management:
- get_anthropic_key() - Retrieve Anthropic API key
- BYOK system integration
- Environment variable fallback
- Error handling

Target Coverage: 90%
Target Branch Coverage: 60%+
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.lux_config import LuxConfig


class TestGetAnthropicKey:
    """Tests for get_anthropic_key method."""

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'})
    def test_get_anthropic_key_from_byok_anthropic(self, mock_get_manager):
        """Test get_anthropic_key returns key from BYOK system (anthropic provider)."""
        # Arrange: BYOK manager returns anthropic key
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = 'byok-anthropic-key'
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: BYOK key returned (priority over env)
        assert result == 'byok-anthropic-key'
        mock_manager.get_api_key.assert_called_with('anthropic')

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'})
    def test_get_anthropic_key_from_byok_lux(self, mock_get_manager):
        """Test get_anthropic_key returns key from BYOK system (lux provider)."""
        # Arrange: BYOK manager returns lux key (after anthropic fails)
        mock_manager = MagicMock()
        def mock_get_key(provider):
            if provider == 'anthropic':
                return None
            elif provider == 'lux':
                return 'byok-lux-key'
            return None
        mock_manager.get_api_key.side_effect = mock_get_key
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: BYOK lux key returned
        assert result == 'byok-lux-key'
        assert mock_manager.get_api_key.call_count == 2

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'})
    def test_get_anthropic_key_from_env_anthropic(self, mock_get_manager):
        """Test get_anthropic_key falls back to ANTHROPIC_API_KEY env var."""
        # Arrange: BYOK manager returns None
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = None
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: Environment variable returned
        assert result == 'env-key-123'

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'LUX_MODEL_API_KEY': 'lux-env-key-456'})
    def test_get_anthropic_key_from_env_lux(self, mock_get_manager):
        """Test get_anthropic_key falls back to LUX_MODEL_API_KEY env var."""
        # Arrange: BYOK manager returns None, ANTHROPIC_API_KEY not set
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = None
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: LUX_MODEL_API_KEY returned
        assert result == 'lux-env-key-456'

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {}, clear=True)
    def test_get_anthropic_key_no_key_available(self, mock_get_manager):
        """Test get_anthropic_key returns None when no key available."""
        # Arrange: BYOK manager returns None, no env vars
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = None
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: None returned
        assert result is None

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123', 'LUX_MODEL_API_KEY': 'lux-key-456'})
    def test_get_anthropic_key_anthropic_env_priority_over_lux(self, mock_get_manager):
        """Test ANTHROPIC_API_KEY takes priority over LUX_MODEL_API_KEY."""
        # Arrange: BYOK manager returns None
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = None
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: ANTHROPIC_API_KEY returned (first in or chain)
        assert result == 'env-key-123'

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'})
    def test_get_anthropic_key_byok_exception_fallback_to_env(self, mock_get_manager):
        """Test get_anthropic_key falls back to env on BYOK exception."""
        # Arrange: BYOK manager raises exception
        mock_get_manager.side_effect = Exception('BYOK unavailable')

        config = LuxConfig()

        # Act: Get key (should not raise, should fallback)
        result = config.get_anthropic_key()

        # Assert: Environment variable returned
        assert result == 'env-key-123'

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'})
    def test_get_anthropic_key_byok_exception_logs_debug(self, mock_get_manager, caplog):
        """Test get_anthropic_key logs debug message on BYOK exception."""
        # Arrange: BYOK manager raises exception
        mock_get_manager.side_effect = Exception('Connection timeout')

        config = LuxConfig()

        # Act: Get key
        with caplog.at_level('DEBUG'):
            result = config.get_anthropic_key()

        # Assert: Debug log present, env var returned
        assert result == 'env-key-123'
        assert any('BYOK system unavailable' in record.message for record in caplog.records)

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {})
    def test_get_anthropic_key_byok_exception_no_env_fallback(self, mock_get_manager):
        """Test get_anthropic_key returns None when BYOK fails and no env vars."""
        # Arrange: BYOK manager raises exception, no env vars
        mock_get_manager.side_effect = Exception('BYOK down')

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: None returned (no fallback available)
        assert result is None

    @patch('core.lux_config.get_byok_manager')
    def test_get_anthropic_key_byok_returns_empty_string(self, mock_get_manager):
        """Test get_anthropic_key handles empty string from BYOK."""
        # Arrange: BYOK manager returns empty string (falsy but not None)
        mock_manager = MagicMock()
        def mock_get_key(provider):
            if provider == 'anthropic':
                return ''
            return None
        mock_manager.get_api_key.side_effect = mock_get_key
        mock_get_manager.return_value = mock_manager

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'}):
            config = LuxConfig()

            # Act: Get key
            result = config.get_anthropic_key()

            # Assert: Falls through to check lux, then env
            # Empty string is falsy, so should continue to lux provider
            assert result == 'env-key-123'

    @patch('core.lux_config.get_byok_manager')
    def test_multiple_calls_to_get_anthropic_key(self, mock_get_manager):
        """Test multiple calls to get_anthropic_key work correctly."""
        # Arrange: BYOK manager returns key
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = 'byok-key-789'
        mock_get_manager.return_value = mock_manager

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key-123'}):
            config = LuxConfig()

            # Act: Get key multiple times
            result1 = config.get_anthropic_key()
            result2 = config.get_anthropic_key()
            result3 = config.get_anthropic_key()

            # Assert: All return BYOK key
            assert result1 == 'byok-key-789'
            assert result2 == 'byok-key-789'
            assert result3 == 'byok-key-789'

    @patch('core.lux_config.get_byok_manager')
    def test_get_anthropic_key_with_special_characters(self, mock_get_manager):
        """Test get_anthropic_key handles keys with special characters."""
        # Arrange: BYOK manager returns key with special chars
        special_key = 'sk-ant-api03-1234abcd-5678efgh!@#$%^&*()'
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = special_key
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: Special characters preserved
        assert result == special_key
        assert '!' in result
        assert '@' in result

    @patch('core.lux_config.get_byok_manager')
    def test_get_anthropic_key_with_unicode(self, mock_get_manager):
        """Test get_anthropic_key handles unicode characters in key."""
        # Arrange: BYOK manager returns key with unicode (unusual but possible)
        unicode_key = 'sk-ant-测试-123'
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = unicode_key
        mock_get_manager.return_value = mock_manager

        config = LuxConfig()

        # Act: Get key
        result = config.get_anthropic_key()

        # Assert: Unicode preserved
        assert result == unicode_key
        assert '测试' in result


class TestLuxConfigModule:
    """Tests for LuxConfig module-level instance."""

    @patch('core.lux_config.get_byok_manager')
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'module-env-key'})
    def test_module_level_lux_config_instance(self, mock_get_manager):
        """Test lux_config module-level instance is accessible."""
        # Arrange: BYOK manager returns None
        from core import lux_config
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = None
        mock_get_manager.return_value = mock_manager

        # Act: Use module-level instance
        result = lux_config.lux_config.get_anthropic_key()

        # Assert: Module instance works
        assert result == 'module-env-key'

    def test_lux_config_class_instantiation(self):
        """Test LuxConfig can be instantiated multiple times."""
        # Arrange & Act: Create multiple instances
        config1 = LuxConfig()
        config2 = LuxConfig()
        config3 = LuxConfig()

        # Assert: All are instances of LuxConfig
        assert isinstance(config1, LuxConfig)
        assert isinstance(config2, LuxConfig)
        assert isinstance(config3, LuxConfig)
        assert config1 is not config2  # Different instances


class TestConfigErrorHandling:
    """Tests for error handling in config operations."""

    @patch('core.lux_config.get_byok_manager')
    def test_byok_manager_various_exceptions(self, mock_get_manager):
        """Test get_anthropic_key handles various exception types."""
        # Arrange: Different exception types
        exceptions = [
            Exception('Generic error'),
            ConnectionError('Connection failed'),
            TimeoutError('Timeout'),
            RuntimeError('Runtime error'),
        ]

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fallback-key'}):
            config = LuxConfig()

            for exc in exceptions:
                mock_get_manager.side_effect = exc

                # Act: Get key (should not raise)
                result = config.get_anthropic_key()

                # Assert: Fallback to env var
                assert result == 'fallback-key'
