"""
LUX Model Configuration
Load and manage real credentials from notes folder
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class LuxConfig:
    """LUX Model configuration management"""

    def __init__(self):
        self.credentials_file = Path(__file__).parent.parent.parent / "notes" / "credentials.md"
        self.api_keys = {}
        self.config = {}
        self.load_credentials()

    def load_credentials(self):
        """Load credentials from notes folder"""
        try:
            if not self.credentials_file.exists():
                logger.warning(f"Credentials file not found: {self.credentials_file}")
                return

            with open(self.credentials_file, 'r') as f:
                content = f.read()

            # Parse credentials
            lines = content.split('\n')
            current_key = None

            for line in lines:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Handle key-value pairs
                if ':' in line and not line.startswith(' '):
                    if '=' in line:
                        # Environment variable format
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        os.environ[key] = value
                        self.config[key] = value

                        # Extract specific keys we need
                        if 'ANTHROPIC' in key:
                            self.api_keys['anthropic'] = value
                        elif 'OPENAI' in key or 'GPT' in key:
                            self.api_keys['openai'] = value
                        elif 'DEEPSEEK' in key:
                            self.api_keys['deepseek'] = value
                        elif 'GOOGLE_API_KEY' in key:
                            self.api_keys['google'] = value
                    else:
                        # YAML-like format
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        current_key = key

                        if value:
                            self.api_keys[key.lower()] = value

                elif line.startswith('-') or line.startswith('*'):
                    # Handle list items
                    if current_key:
                        item = line.lstrip('-* ').strip()
                        if '=' in item:
                            kv = item.split('=', 1)
                            os.environ[kv[0].strip()] = kv[1].strip().strip('"\'')
                            self.config[kv[0].strip()] = kv[1].strip().strip('"\'')

            logger.info("Credentials loaded successfully")
            logger.info(f"Loaded {len(self.config)} configuration values")
            logger.info(f"Loaded {len(self.api_keys)} API keys")

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for specific provider"""
        provider_lower = provider.lower()

        # Try direct lookup
        if provider_lower in self.api_keys:
            return self.api_keys[provider_lower]

        # Try environment variables
        env_var_names = [
            f"{provider.upper()}_API_KEY",
            f"{provider.upper()}_KEY",
            provider.upper()
        ]

        for env_var in env_var_names:
            if env_var in os.environ:
                return os.environ[env_var]

        return None

    def get_anthropic_key(self) -> Optional[str]:
        """Get Anthropic API key for LUX model"""
        return self.get_api_key('anthropic')

    def get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key"""
        return self.get_api_key('openai')

    def get_google_key(self) -> Optional[str]:
        """Get Google API key"""
        return self.get_api_key('google')

    def get_deepseek_key(self) -> Optional[str]:
        """Get DeepSeek API key"""
        return self.get_api_key('deepseek')

    def get_all_keys(self) -> Dict[str, str]:
        """Get all available API keys"""
        return self.api_keys.copy()

    def validate_keys(self) -> Dict[str, bool]:
        """Validate API keys by checking format"""
        validation = {}

        for provider, key in self.api_keys.items():
            if key:
                # Basic validation - check if key looks like a real API key
                if provider == 'anthropic':
                    # Anthropic keys start with sk-ant-
                    validation[provider] = key.startswith('sk-ant-')
                elif provider == 'openai':
                    # OpenAI keys start with sk-
                    validation[provider] = key.startswith('sk-')
                elif provider == 'google':
                    # Google keys are typically longer
                    validation[provider] = len(key) > 20
                elif provider == 'deepseek':
                    # DeepSeek keys start with sk-
                    validation[provider] = key.startswith('sk-')
                else:
                    # Generic validation
                    validation[provider] = len(key) > 10
            else:
                validation[provider] = False

        return validation

# Global configuration instance
lux_config = LuxConfig()