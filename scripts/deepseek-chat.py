#!/usr/bin/env python3
"""
DeepSeek API Helper Script for ATOM Project
Provides integration with DeepSeek API for AI-assisted development
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests


class DeepSeekHelper:
    """Helper class for DeepSeek API integration"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> Optional[str]:
        """
        Send chat completion request to DeepSeek API

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: DeepSeek model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Response content or None if error
        """
        if not self.api_key:
            print("❌ DEEPSEEK_API_KEY environment variable not set")
            return None

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            return None
        except KeyError as e:
            print(f"❌ Unexpected API response format: {e}")
            return None

    def get_organization_prompt(self) -> str:
        """Get the organization prompt for maintaining project structure"""
        return """
You are assisting with the ATOM project development. Follow these organization rules:

PROJECT STRUCTURE:
- Root directory should only contain: README.md, .charm
- Python files → backend/
- TypeScript/React files → frontend-nextjs/
- Rust files → desktop-tauri/src-tauri/
- Documentation → docs/
- Scripts → scripts/
- Tests → tests/
- Configuration → config/
- Deployment → deployment/

ORGANIZATION RULES:
1. Prefer existing directories for file placement
2. Create new folders only when necessary for logical organization of new features
3. Use kebab-case for folder names
4. Run organization validation before committing
5. Never create files in root directory

EXISTING DIRECTORIES:
- backend/ - Python backend services and APIs
- frontend-nextjs/ - Next.js web application
- desktop-tauri/ - Tauri desktop application
- docs/ - Documentation and guides
- scripts/ - Automation and utility scripts
- tests/ - Test files and test results
- config/ - Configuration files
- deployment/ - Deployment configurations
- data/ - Database schemas and data files

When creating new files, always place them in the appropriate existing directory.
Only create new folders when absolutely necessary for major new features.
"""

    def code_assistance(
        self, task: str, context_files: List[str] = None, language: str = "python"
    ) -> Optional[str]:
        """
        Get AI assistance for coding tasks with project context

        Args:
            task: Description of the coding task
            context_files: List of file paths to include as context
            language: Programming language for the task

        Returns:
            AI-generated code or assistance
        """
        system_prompt = self.get_organization_prompt()

        # Add context from files if provided
        context = ""
        if context_files:
            for file_path in context_files:
                if Path(file_path).exists():
                    with open(file_path, "r") as f:
                        content = f.read()
                        context += f"\n\n--- {file_path} ---\n{content}"

        user_message = f"""
Task: {task}
Language: {language}
{context}

Please provide code that follows the project organization rules.
Place files in appropriate directories and maintain clean structure.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        return self.chat_completion(messages)

    def organize_suggestion(self, file_path: str) -> Optional[str]:
        """
        Get suggestion for organizing a specific file

        Args:
            file_path: Path to the file that needs organization

        Returns:
            Suggestion for where to move the file
        """
        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            return None

        system_prompt = self.get_organization_prompt()

        user_message = f"""
I have a file at path: {file_path}
Based on the ATOM project organization rules, where should this file be placed?
Please suggest the appropriate directory and explain why.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        return self.chat_completion(messages)


def main():
    """Command line interface for DeepSeek helper"""
    import argparse

    parser = argparse.ArgumentParser(description="DeepSeek API Helper for ATOM Project")
    parser.add_argument("--task", help="Coding task description")
    parser.add_argument("--organize", help="Get organization suggestion for file")
    parser.add_argument("--context", nargs="+", help="Context files to include")
    parser.add_argument("--language", default="python", help="Programming language")

    args = parser.parse_args()

    helper = DeepSeekHelper()

    if args.organize:
        print(f"🔍 Getting organization suggestion for: {args.organize}")
        suggestion = helper.organize_suggestion(args.organize)
        if suggestion:
            print("💡 Organization Suggestion:")
            print(suggestion)
        else:
            print("❌ Failed to get organization suggestion")

    elif args.task:
        print(f"🤖 Getting AI assistance for: {args.task}")
        result = helper.code_assistance(args.task, args.context, args.language)
        if result:
            print("💻 AI Assistance:")
            print(result)
        else:
            print("❌ Failed to get AI assistance")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
