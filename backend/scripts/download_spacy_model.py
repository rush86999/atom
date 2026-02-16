#!/usr/bin/env python3
"""
Download Spacy English model for Presidio PII detection.

This script downloads the en_core_web_lg model required for
accurate PII detection using Microsoft Presidio.

Usage:
    python scripts/download_spacy_model.py

Requirements:
    pip install spacy
"""

import subprocess
import sys


def main():
    """Download Spacy English model (en_core_web_lg)"""
    print("Downloading Spacy English model (en_core_web_lg)...")
    print("This may take a few minutes...")

    try:
        # Download the model
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_lg"],
            check=True,
            capture_output=False,
            text=True
        )
        print("\n✓ Spacy model downloaded successfully")
        print("Presidio will use en_core_web_lg for PII detection")
        print("\nModel features:")
        print("  - 500k vocabulary size")
        print("  - Word vectors (300-dimensional)")
        print("  - Part-of-speech tagging")
        print("  - Named entity recognition")
        print("  - Dependency parsing")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed to download Spacy model: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure you have internet connection")
        print("  2. Try: pip install spacy --upgrade")
        print("  3. Try: python -m spacy download en_core_web_lg directly")
        print("\nFallback: Presidio will use smaller built-in models")
        return 1

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
