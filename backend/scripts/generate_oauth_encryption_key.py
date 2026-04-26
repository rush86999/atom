#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OAuth Encryption Key Generator

Generates a Fernet encryption key for securing OAuth tokens at rest.

Usage:
    python scripts/generate_oauth_encryption_key.py

Output:
    A Fernet encryption key (44-character base64 string)

IMPORTANT:
- Store this key securely and never commit it to version control
- If you lose this key, all encrypted tokens will be permanently lost
- Keep backups of this key in a secure location
- Rotate keys periodically (requires re-encrypting all tokens)
"""

import sys
import os


def generate_encryption_key():
    """Generate a Fernet encryption key for OAuth token storage."""
    try:
        from cryptography.fernet import Fernet

        # Generate the key
        key = Fernet.generate_key()

        # Decode to string for environment variable use
        key_string = key.decode('utf-8')

        return key_string

    except ImportError:
        print("ERROR: cryptography package not installed")
        print("\nInstall it with:")
        print("  pip install cryptography")
        sys.exit(1)


def main():
    """Main function to generate and display the encryption key."""
    print("=" * 70)
    print("OAuth Token Encryption Key Generator")
    print("=" * 70)
    print()

    print("Generating Fernet encryption key...")
    key = generate_encryption_key()

    print()
    print("Encryption key generated successfully!")
    print()
    print("-" * 70)
    print("YOUR ENCRYPTION KEY:")
    print("-" * 70)
    print()
    print(key)
    print()
    print("-" * 70)
    print()
    print("SETUP INSTRUCTIONS:")
    print("-" * 70)
    print()
    print("1. Copy the key above")
    print("2. Add it to your .env file:")
    print("   OAUTH_ENCRYPTION_KEY=" + key)
    print()
    print("3. Store a backup of this key in a secure location")
    print("   (password manager, encrypted file, etc.)")
    print()
    print("4. NEVER commit this key to version control")
    print()
    print("5. Add .env to your .gitignore file:")
    print("   echo '.env' >> .gitignore")
    print()
    print("WARNING: If you lose this key, all encrypted OAuth tokens")
    print("   will be permanently unrecoverable!")
    print()
    print("=" * 70)
    print()

    # Option to save to file
    save_to_file = input("Save key to file? (y/N): ").strip().lower()

    if save_to_file == 'y':
        filename = input("Filename (default: oauth_encryption_key.txt): ").strip()
        if not filename:
            filename = "oauth_encryption_key.txt"

        # Don't overwrite existing files
        if os.path.exists(filename):
            overwrite = input("File '" + filename + "' exists. Overwrite? (y/N): ").strip().lower()
            if overwrite != 'y':
                print("Skipped saving to file.")
                return

        try:
            import datetime
            with open(filename, 'w') as f:
                f.write("# OAuth Token Encryption Key\n")
                f.write("# Generated: " + datetime.datetime.now().isoformat() + "\n")
                f.write("# Add this to your .env file as OAUTH_ENCRYPTION_KEY\n")
                f.write("\nOAUTH_ENCRYPTION_KEY=" + key + "\n")

            print("Key saved to: " + filename)
            print("  Remember to add " + filename + " to .gitignore!")

        except Exception as e:
            print("ERROR: Failed to save key: " + str(e))


if __name__ == "__main__":
    main()
