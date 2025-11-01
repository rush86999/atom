"""
Production Deployment Configuration for Atom AI Assistant

This configuration file contains all the settings needed for production deployment
of the Atom system with BYOK (Bring Your Own Keys) functionality.
"""

import os
import secrets
from typing import Dict, Any


class ProductionConfig:
    """Production configuration for Atom deployment"""

    # Application Settings
    APP_NAME = "Atom AI Assistant"
    APP_VERSION = "1.0.0"
    FLASK_ENV = "production"
    DEBUG = False

    # Server Configuration
    HOST = "0.0.0.0"
    PORT = 5058
    WORKERS = 4
    THREADS = 2
    TIMEOUT = 120

    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/atom_production.db")
    DATABASE_POOL_SIZE = 10
    DATABASE_MAX_OVERFLOW = 20
    DATABASE_POOL_RECYCLE = 3600

    # Security Configuration
    SECRET_KEY = os.getenv("ATOM_OAUTH_ENCRYPTION_KEY", secrets.token_urlsafe(32))
    ENCRYPTION_ALGORITHM = "fernet"
    TOKEN_EXPIRY_HOURS = 24

    # BYOK AI Provider Configuration
    AI_PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"],
            "cost_per_1m_tokens": {
                "gpt-4": 30.00,
                "gpt-4-turbo": 10.00,
                "gpt-3.5-turbo": 0.50,
                "gpt-4o": 5.00,
            },
        },
        "deepseek": {
            "name": "DeepSeek AI",
            "base_url": "https://api.deepseek.com/v1",
            "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
            "cost_per_1m_tokens": {
                "deepseek-chat": 0.14,
                "deepseek-coder": 0.28,
                "deepseek-reasoner": 1.40,
            },
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "base_url": "https://api.anthropic.com/v1",
            "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "cost_per_1m_tokens": {
                "claude-3-opus": 15.00,
                "claude-3-sonnet": 3.00,
                "claude-3-haiku": 0.25,
            },
        },
        "google_gemini": {
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1",
            "models": ["gemini-2.0-flash", "gemini-2.0-pro", "text-embedding-004"],
            "cost_per_1m_tokens": {
                "gemini-2.0-flash": 0.075,
                "gemini-2.0-pro": 1.25,
                "text-embedding-004": 0.0001,
            },
        },
        "azure_openai": {
            "name": "Azure OpenAI",
            "base_url": None,  # Custom per deployment
            "models": ["gpt-4", "gpt-35-turbo"],
            "cost_per_1m_tokens": {"gpt-4": 30.00, "gpt-35-turbo": 0.50},
        },
    }

    # Service Integration Configuration
    SERVICE_INTEGRATIONS = {
        "slack": {
            "enabled": True,
            "scopes": ["channels:read", "chat:write", "files:write"],
        },
        "notion": {"enabled": True, "scopes": ["read", "write"]},
        "gmail": {
            "enabled": True,
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        },
        "google_calendar": {
            "enabled": True,
            "scopes": ["https://www.googleapis.com/auth/calendar"],
        },
        "google_drive": {
            "enabled": True,
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        },
        "asana": {"enabled": True, "scopes": ["default"]},
        "trello": {"enabled": True, "scopes": ["read", "write"]},
    }

    # OAuth Configuration
    OAUTH_CONFIG = {
        "google": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": "http://localhost:5058/api/auth/gdrive/oauth2callback",
        },
        "asana": {
            "client_id": os.getenv("ASANA_CLIENT_ID"),
            "client_secret": os.getenv("ASANA_CLIENT_SECRET"),
            "redirect_uri": "http://localhost:5058/api/auth/asana/oauth2callback",
        },
    }

    # Performance Configuration
    MAX_WORKFLOW_STEPS = 10
    MAX_CONCURRENT_WORKFLOWS = 5
    CACHE_TIMEOUT = 300  # 5 minutes
    RATE_LIMIT_REQUESTS = 1000
    RATE_LIMIT_WINDOW = 3600  # 1 hour

    # Monitoring Configuration
    ENABLE_METRICS = True
    ENABLE_LOGGING = True
    LOG_LEVEL = "INFO"
    HEALTH_CHECK_INTERVAL = 30

    # Cost Optimization Settings
    COST_OPTIMIZATION_ENABLED = True
    DEFAULT_COST_THRESHOLD = 0.10  # $0.10 per request
    AUTO_PROVIDER_SWITCHING = True
    FALLOVER_ENABLED = True

    # Voice Processing Configuration
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    VOICE_PROCESSING_ENABLED = True
    MAX_AUDIO_DURATION = 300  # 5 minutes

    @classmethod
    def validate_configuration(cls) -> Dict[str, Any]:
        """Validate production configuration and return status"""
        validation_results = {
            "database": cls._validate_database(),
            "security": cls._validate_security(),
            "ai_providers": cls._validate_ai_providers(),
            "service_integrations": cls._validate_service_integrations(),
            "performance": cls._validate_performance(),
        }

        all_valid = all(result["valid"] for result in validation_results.values())

        return {
            "valid": all_valid,
            "details": validation_results,
            "summary": f"Configuration {'VALID' if all_valid else 'INVALID'} for production deployment",
        }

    @classmethod
    def _validate_database(cls) -> Dict[str, Any]:
        """Validate database configuration"""
        db_url = cls.DATABASE_URL
        if db_url and ("postgresql://" in db_url or "sqlite://" in db_url):
            return {"valid": True, "message": "Database URL properly configured"}
        else:
            return {"valid": False, "message": "Invalid database URL format"}

    @classmethod
    def _validate_security(cls) -> Dict[str, Any]:
        """Validate security configuration"""
        if len(cls.SECRET_KEY) >= 32:
            return {"valid": True, "message": "Encryption key properly configured"}
        else:
            return {"valid": False, "message": "Encryption key too short"}

    @classmethod
    def _validate_ai_providers(cls) -> Dict[str, Any]:
        """Validate AI provider configuration"""
        if cls.AI_PROVIDERS and len(cls.AI_PROVIDERS) >= 3:
            return {
                "valid": True,
                "message": f"{len(cls.AI_PROVIDERS)} AI providers configured",
            }
        else:
            return {"valid": False, "message": "Insufficient AI providers configured"}

    @classmethod
    def _validate_service_integrations(cls) -> Dict[str, Any]:
        """Validate service integration configuration"""
        enabled_services = [
            name
            for name, config in cls.SERVICE_INTEGRATIONS.items()
            if config.get("enabled", False)
        ]
        if len(enabled_services) >= 5:
            return {
                "valid": True,
                "message": f"{len(enabled_services)} services enabled",
            }
        else:
            return {
                "valid": False,
                "message": f"Only {len(enabled_services)} services enabled (minimum 5 required)",
            }

    @classmethod
    def _validate_performance(cls) -> Dict[str, Any]:
        """Validate performance configuration"""
        checks = []

        if cls.WORKERS >= 2:
            checks.append("Adequate worker count")
        else:
            checks.append("Insufficient workers")

        if cls.TIMEOUT >= 60:
            checks.append("Reasonable timeout")
        else:
            checks.append("Timeout too short")

        if cls.RATE_LIMIT_REQUESTS > 0:
            checks.append("Rate limiting enabled")
        else:
            checks.append("Rate limiting disabled")

        valid = all(
            "Adequate" in check or "Reasonable" in check or "enabled" in check
            for check in checks
        )

        return {"valid": valid, "message": ", ".join(checks), "details": checks}

    @classmethod
    def get_cost_optimization_strategy(cls) -> Dict[str, Any]:
        """Get cost optimization strategy based on configuration"""
        return {
            "enabled": cls.COST_OPTIMIZATION_ENABLED,
            "strategies": [
                {
                    "provider": "google_gemini",
                    "use_cases": ["embeddings", "general_chat", "cost_sensitive"],
                    "savings_potential": "70-93%",
                },
                {
                    "provider": "deepseek",
                    "use_cases": ["code_generation", "technical_tasks"],
                    "savings_potential": "40-60%",
                },
                {
                    "provider": "anthropic",
                    "use_cases": ["complex_reasoning", "long_context"],
                    "savings_potential": "0-20%",
                },
                {
                    "provider": "openai",
                    "use_cases": ["highest_quality", "enterprise_requirements"],
                    "savings_potential": "baseline",
                },
            ],
            "auto_failover": cls.FALLOVER_ENABLED,
            "cost_threshold": cls.DEFAULT_COST_THRESHOLD,
        }


# Production deployment settings
PRODUCTION_SETTINGS = {
    "deployment_type": "docker_compose",
    "health_check_endpoint": "/healthz",
    "readiness_endpoint": "/api/services/status",
    "liveness_endpoint": "/api/transcription/health",
    "monitoring_endpoints": [
        "/api/user/api-keys/{user_id}/status",
        "/api/workflow-automation/generate",
        "/api/services",
    ],
    "backup_strategy": {
        "database_backup": "daily",
        "log_retention": "30d",
        "encryption_key_backup": "secure_storage",
    },
    "scaling_config": {
        "min_instances": 2,
        "max_instances": 10,
        "cpu_threshold": 80,
        "memory_threshold": 85,
    },
}


if __name__ == "__main__":
    # Test configuration validation
    validation = ProductionConfig.validate_configuration()
    print("🔧 Production Configuration Validation")
    print("=" * 50)

    for component, result in validation["details"].items():
        status = "✅" if result["valid"] else "❌"
        print(f"{status} {component.upper()}: {result['message']}")

    print(f"\n📊 Overall: {validation['summary']}")

    # Show cost optimization strategy
    cost_strategy = ProductionConfig.get_cost_optimization_strategy()
    print(
        f"\n💰 Cost Optimization: {'ENABLED' if cost_strategy['enabled'] else 'DISABLED'}"
    )
    for strategy in cost_strategy["strategies"]:
        print(
            f"   • {strategy['provider']}: {strategy['use_cases']} ({strategy['savings_potential']})"
        )
