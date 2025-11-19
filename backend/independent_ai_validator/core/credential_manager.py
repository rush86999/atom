#!/usr/bin/env python3
"""
Secure Credential Manager for Independent AI Validator
Loads credentials from notes/credentials.md with in-memory storage only
"""

import os
import re
import json
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CredentialInfo:
    """Credential information structure"""
    name: str
    key: str
    provider: str
    pattern: str
    description: str
    weight: float = 1.0

class CredentialManager:
    """
    Secure credential manager for AI validation system
    Loads credentials from file and stores in memory only
    """

    def __init__(self, credentials_file: str = None):
        self.credentials_file = credentials_file or "../notes/credentials.md"
        self.credentials: Dict[str, CredentialInfo] = {}
        self.is_loaded = False

    def load_credentials(self) -> bool:
        """
        Load credentials from notes/credentials.md file
        Returns True if successful, False otherwise
        """
        try:
            print(f"DEBUG: self.credentials_file type: {type(self.credentials_file)}, value: {self.credentials_file}")
            credentials_path = Path(__file__).parent.parent.parent / self.credentials_file

            if not credentials_path.exists():
                logger.error(f"Credentials file not found: {credentials_path}")
                return False

            with open(credentials_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract credentials using regex patterns
            extracted_creds = self._extract_credentials(content)

            if not extracted_creds:
                logger.warning("No credentials extracted from file")
                return False

            self.credentials = extracted_creds
            self.is_loaded = True

            logger.info(f"Successfully loaded {len(self.credentials)} credentials")
            return True

        except Exception as e:
            logger.error(f"Failed to load credentials: {str(e)}")
            return False

    def _extract_credentials(self, content: str) -> Dict[str, CredentialInfo]:
        """Extract credentials from file content using regex patterns"""
        credentials = {}

        # Define credential patterns and their metadata
        credential_patterns = {
            'glm': {
                'pattern': r'GLM_API_KEY=([^\s\n]+)',
                'key_pattern': r'[a-zA-Z0-9._-]+',
                'description': 'GLM-4 API for cost-effective AI analysis',
                'weight': 1.0
            },
            'openai': {
                'pattern': r'OPENAI_API_KEY=([^\s\n]+)',
                'key_pattern': r'sk-proj-[^"\s\n]+',
                'description': 'OpenAI GPT-4 API for AI analysis (paused for cost optimization)',
                'weight': 1.0
            },
            'anthropic': {
                'pattern': r'ANTHROPIC_API_KEY=([^\s\n]+)',
                'key_pattern': r'sk-ant-[^"\s\n]+',
                'description': 'Anthropic Claude API for AI analysis',
                'weight': 1.0
            },
            'deepseek': {
                'pattern': r'DEEPSEEK_API_KEY=([^\s\n]+)',
                'key_pattern': r'sk-[a-zA-Z0-9]+',
                'description': 'DeepSeek AI API for cost-effective analysis',
                'weight': 0.8
            },
            'google': {
                'pattern': r'GOOGLE_API_KEY=([^\s\n]+)',
                'key_pattern': r'AIzaSy[A-Za-z0-9_-]+',
                'description': 'Google Gemini API for validation',
                'weight': 0.9
            },
            'slack': {
                'pattern': r'SLACK_BOT_TOKEN=([^\s\n]+)',
                'key_pattern': r'xoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+',
                'description': 'Slack Bot Token for integration testing',
                'weight': 0.7
            },
            'github': {
                'pattern': r'GITHUB_TOKEN=([^\s\n]+)',
                'key_pattern': r'github_pat_[a-zA-Z0-9_]+',
                'description': 'GitHub Personal Access Token for testing',
                'weight': 0.7
            },
            'notion': {
                'pattern': r'NOTION_API_KEY=([^\s\n]+)',
                'key_pattern': r'secret_[a-zA-Z0-9_-]+',
                'description': 'Notion API key for integration testing',
                'weight': 0.6
            },
            'trello': {
                'pattern': r'TRELLO_API_KEY=([^\s\n]+)',
                'key_pattern': r'[a-f0-9]{32}',
                'description': 'Trello API key for integration testing',
                'weight': 0.5
            },
            'asana': {
                'pattern': r'ASANA_CLIENT_ID=([^\s\n]+)',
                'key_pattern': r'\d+',
                'description': 'Asana Client ID for integration testing',
                'weight': 0.5
            }
        }

        for provider, config in credential_patterns.items():
            # Try to extract credential using pattern
            match = re.search(config['pattern'], content, re.IGNORECASE)
            if match:
                key = match.group(1).strip('"\'')

                # Validate key pattern
                if re.match(config['key_pattern'], key):
                    credentials[provider] = CredentialInfo(
                        name=provider.title(),
                        key=key,
                        provider=provider,
                        pattern=config['key_pattern'],
                        description=config['description'],
                        weight=config['weight']
                    )
                    logger.info(f"Loaded {provider} credential")
                else:
                    logger.warning(f"{provider} key doesn't match expected pattern")
            else:
                logger.debug(f"No {provider} credential found")

        return credentials

    def get_credential(self, provider: str) -> Optional[CredentialInfo]:
        """Get credential for specific provider"""
        if not self.is_loaded:
            self.load_credentials()

        return self.credentials.get(provider)

    def get_credential_key(self, provider: str) -> Optional[str]:
        """Get just the API key for a provider"""
        cred = self.get_credential(provider)
        return cred.key if cred else None

    def list_available_providers(self) -> list:
        """List all available credential providers"""
        if not self.is_loaded:
            self.load_credentials()

        return list(self.credentials.keys())

    def validate_credentials(self) -> Dict[str, bool]:
        """Validate all loaded credentials"""
        validation_results = {}

        for provider, cred in self.credentials.items():
            try:
                if provider == 'openai':
                    validation_results[provider] = self._validate_openai(cred.key)
                elif provider == 'anthropic':
                    validation_results[provider] = self._validate_anthropic(cred.key)
                elif provider == 'deepseek':
                    validation_results[provider] = self._validate_deepseek(cred.key)
                elif provider == 'google':
                    validation_results[provider] = self._validate_google(cred.key)
                elif provider == 'slack':
                    validation_results[provider] = self._validate_slack(cred.key)
                elif provider == 'github':
                    validation_results[provider] = self._validate_github(cred.key)
                else:
                    validation_results[provider] = True  # Assume valid for others

            except Exception as e:
                logger.error(f"Failed to validate {provider}: {str(e)}")
                validation_results[provider] = False

        return validation_results

    def _validate_openai(self, key: str) -> bool:
        """Validate OpenAI API key"""
        try:
            import requests
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def _validate_anthropic(self, key: str) -> bool:
        """Validate Anthropic API key"""
        try:
            import requests
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "test"}]
                },
                timeout=10
            )
            return response.status_code in [200, 201]
        except:
            return False

    def _validate_deepseek(self, key: str) -> bool:
        """Validate DeepSeek API key"""
        try:
            import requests
            response = requests.get(
                "https://api.deepseek.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def _validate_google(self, key: str) -> bool:
        """Validate Google API key"""
        try:
            import requests
            response = requests.get(
                f"https://www.googleapis.com/books/v1/volumes?q=test&key={key}",
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def _validate_slack(self, key: str) -> bool:
        """Validate Slack Bot Token"""
        try:
            import requests
            response = requests.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10
            )
            return response.status_code == 200 and response.json().get("ok", False)
        except:
            return False

    def _validate_github(self, key: str) -> bool:
        """Validate GitHub Personal Access Token"""
        try:
            import requests
            response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {key}"},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def get_provider_weights(self) -> Dict[str, float]:
        """Get reliability weights for each provider"""
        if not self.is_loaded:
            self.load_credentials()

        return {provider: cred.weight for provider, cred in self.credentials.items()}

    def clear_credentials(self):
        """Clear all credentials from memory (security cleanup)"""
        self.credentials.clear()
        self.is_loaded = False
        logger.info("All credentials cleared from memory")

    def __del__(self):
        """Destructor - ensure credentials are cleared"""
        self.clear_credentials()