#!/usr/bin/env python3
"""
Environment Setup Helper for Atom Platform E2E Tests
Helps users set up required environment variables and validate their configuration
"""

import os
import sys
from pathlib import Path


def print_header():
    """Print setup header"""
    print("🔧 Atom Platform E2E Test Environment Setup")
    print("=" * 60)


def check_current_environment():
    """Check current environment variables"""
    print("\n📋 Current Environment Status:")

    required_vars = [
        "OPENAI_API_KEY",
        "SLACK_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "OUTLOOK_CLIENT_ID",
        "OUTLOOK_CLIENT_SECRET",
        "ASANA_ACCESS_TOKEN",
        "NOTION_API_KEY",
        "LINEAR_API_KEY",
        "TRELLO_API_KEY",
        "MONDAY_API_KEY",
        "ELEVENLABS_API_KEY",
    ]

    available = []
    missing = []

    for var in required_vars:
        if os.getenv(var):
            available.append(var)
        else:
            missing.append(var)

    print(f"✅ Available: {len(available)}")
    print(f"❌ Missing: {len(missing)}")

    if missing:
        print("\nMissing variables:")
        for var in missing:
            print(f"  - {var}")

    return available, missing


def create_env_file():
    """Create .env file from template"""
    template_path = Path(__file__).parent / ".env.template"
    env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        print(f"\n⚠️  .env file already exists at: {env_path}")
        response = input("Do you want to overwrite it? (y/N): ").lower().strip()
        if response != "y":
            print("Keeping existing .env file")
            return False

    if not template_path.exists():
        print(f"❌ Template file not found: {template_path}")
        return False

    try:
        with open(template_path, "r") as template_file:
            template_content = template_file.read()

        with open(env_path, "w") as env_file:
            env_file.write(template_content)

        print(f"✅ Created .env file at: {env_path}")
        print("📝 Please edit this file with your actual API keys and credentials")
        return True

    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def print_setup_instructions():
    """Print setup instructions for each service"""
    print("\n📚 Setup Instructions:")
    print("=" * 60)

    instructions = {
        "OpenAI API Key": {
            "description": "Required for LLM-based marketing claim verification",
            "steps": [
                "1. Go to https://platform.openai.com/",
                "2. Sign up or log in to your account",
                "3. Navigate to API Keys section",
                "4. Create a new API key",
                "5. Copy the key to OPENAI_API_KEY in .env file",
            ],
        },
        "Slack Integration": {
            "description": "For Slack workspace connectivity",
            "steps": [
                "1. Go to https://api.slack.com/apps",
                "2. Create a new app or use existing one",
                "3. Add 'bot' scope to OAuth & Permissions",
                "4. Install app to workspace",
                "5. Copy Bot User OAuth Token to SLACK_BOT_TOKEN",
            ],
        },
        "Discord Integration": {
            "description": "For Discord server connectivity",
            "steps": [
                "1. Go to https://discord.com/developers/applications",
                "2. Create a new application",
                "3. Go to Bot section",
                "4. Create a bot and copy the token",
                "5. Add bot to your server with appropriate permissions",
            ],
        },
        "Gmail Integration": {
            "description": "For Gmail email connectivity",
            "steps": [
                "1. Go to https://console.cloud.google.com/",
                "2. Create a new project or select existing",
                "3. Enable Gmail API",
                "4. Create OAuth 2.0 credentials",
                "5. Copy Client ID and Client Secret",
            ],
        },
        "Asana Integration": {
            "description": "For Asana workspace connectivity",
            "steps": [
                "1. Go to https://app.asana.com/0/developer-console",
                "2. Create a new app",
                "3. Generate a personal access token",
                "4. Copy token to ASANA_ACCESS_TOKEN",
            ],
        },
        "Notion Integration": {
            "description": "For Notion workspace connectivity",
            "steps": [
                "1. Go to https://www.notion.so/my-integrations",
                "2. Create a new integration",
                "3. Copy the internal integration token",
                "4. Share pages/databases with your integration",
            ],
        },
        "ElevenLabs Integration": {
            "description": "For text-to-speech capabilities",
            "steps": [
                "1. Go to https://elevenlabs.io/",
                "2. Sign up or log in to your account",
                "3. Go to Profile → API Key",
                "4. Copy your API key to ELEVENLABS_API_KEY",
            ],
        },
    }

    for service, info in instructions.items():
        print(f"\n🔧 {service}:")
        print(f"   {info['description']}")
        for step in info["steps"]:
            print(f"   {step}")


def validate_environment():
    """Validate the current environment setup"""
    print("\n🔍 Validating Environment...")

    available, missing = check_current_environment()

    if not missing:
        print("✅ All required environment variables are set!")
        print("🎉 You're ready to run E2E tests!")
        return True
    else:
        print(f"⚠️  {len(missing)} environment variables still need to be configured")
        print("\n💡 Next steps:")
        print("   1. Edit the .env file with your API keys")
        print("   2. Run this script again to validate")
        print("   3. Run: python run_tests.py --list-categories to see available tests")
        return False


def main():
    """Main setup function"""
    print_header()

    print("\nWelcome to the Atom Platform E2E Test Setup!")
    print("This script will help you configure the required environment variables.")

    # Check current environment
    available, missing = check_current_environment()

    # Create .env file if needed
    if missing:
        print(f"\n📝 Creating environment file...")
        create_env_file()

    # Print setup instructions
    if missing:
        print_setup_instructions()

    # Validate environment
    is_ready = validate_environment()

    # Print final instructions
    print("\n🎯 Final Steps:")
    if is_ready:
        print("   • Run: python run_tests.py to start E2E testing")
        print("   • Run: python run_tests.py --list-categories to see available tests")
    else:
        print("   • Complete the missing environment variables in .env file")
        print("   • Run this script again to validate your setup")

    print("\n📖 For more information, see README.md")
    print("🚀 Happy testing!")


if __name__ == "__main__":
    main()
