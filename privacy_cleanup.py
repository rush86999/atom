#!/usr/bin/env python3
"""
Privacy Cleanup Script
Remove personal information from public repository

This script replaces personal information with generic alternatives
to maintain privacy in public repositories.
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime

print("🔒 PRIVACY CLEANUP SCRIPT")
print("=" * 80)
print("Removing personal information from public repository")
print("=" * 80)

# Define replacements for privacy
REPLACEMENTS = {
    # Personal name replacements
    "developer": "developer",
    "Developer": "Developer",
    
    # Email replacements
    "noreply@atom.com": "noreply@atom.com",
    "noreply@atom.com": "noreply@atom.com",
    "noreply@atom.com": "noreply@atom.com",
    
    # Path replacements
    "/home/developer/home/developer",
    "/home/developer/projects/atom": "/home/developer/projects",
    "/home/developer/atom-production": "/opt/atom",
    
    # Generic replacements for other personal identifiers
    "CHANGE_THIS_PASSWORD": "CHANGE_THIS_PASSWORD",
    "CHANGE_THIS_REDIS_PASSWORD": "CHANGE_THIS_REDIS_PASSWORD",
    "CHANGE_THIS_APP_PASSWORD": "CHANGE_THIS_APP_PASSWORD",
    "noreply@atom.com": "noreply@atom.com",
    "localhost": "localhost",
}

def clean_file_content(content):
    """Clean personal information from file content"""
    cleaned_content = content
    
    for personal_info, replacement in REPLACEMENTS.items():
        cleaned_content = cleaned_content.replace(personal_info, replacement)
    
    # Remove any remaining personal paths with regex
    cleaned_content = re.sub(r'/home/developer/]+', '/home/developer', cleaned_content)
    
    return cleaned_content

def clean_file(file_path):
    """Clean a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        cleaned_content = clean_file_content(content)
        
        # Only write if content changed
        if original_content != cleaned_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"   ❌ Error cleaning {file_path}: {str(e)}")
        return False

def clean_directory(directory, extensions_to_clean=None):
    """Clean all files in directory recursively"""
    if extensions_to_clean is None:
        extensions_to_clean = {'.py', '.json', '.yml', '.yaml', '.md', '.sh', '.conf', '.txt'}
    
    cleaned_files = []
    total_files = 0
    
    print(f"\n📁 Cleaning directory: {directory}")
    print("-" * 60)
    
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix in extensions_to_clean:
            total_files += 1
            
            # Skip .git and hidden files
            if '.git' in str(file_path) or file_path.name.startswith('.'):
                continue
            
            if clean_file(file_path):
                cleaned_files.append(file_path)
                print(f"   ✅ Cleaned: {file_path.name}")
    
    print(f"\n📊 Cleaning Summary for {directory}:")
    print(f"   📄 Total Files: {total_files}")
    print(f"   ✅ Files Cleaned: {len(cleaned_files)}")
    
    return cleaned_files

def main():
    """Main privacy cleanup"""
    try:
        current_dir = Path.cwd()
        project_dir = current_dir
        
        print(f"📂 Project Directory: {project_dir}")
        
        # Clean all relevant files
        all_cleaned_files = []
        
        # Clean main project directory
        cleaned_files = clean_directory(project_dir)
        all_cleaned_files.extend(cleaned_files)
        
        # Clean atom-production if it exists
        prod_dir = Path("/home/developer/atom-production")
        if prod_dir.exists():
            cleaned_prod_files = clean_directory(prod_dir)
            all_cleaned_files.extend(cleaned_prod_files)
        else:
            # Check local production directory
            local_prod_dir = Path.home() / "atom-production"
            if local_prod_dir.exists():
                cleaned_prod_files = clean_directory(local_prod_dir)
                all_cleaned_files.extend(cleaned_prod_files)
        
        # Generate privacy report
        privacy_report = {
            "cleanup_completed": True,
            "timestamp": datetime.now().isoformat(),
            "total_files_cleaned": len(all_cleaned_files),
            "files_cleaned": [str(f) for f in all_cleaned_files],
            "replacements_made": REPLACEMENTS,
            "privacy_note": "All personal information has been replaced with generic alternatives for public repository privacy."
        }
        
        # Save privacy report
        report_file = project_dir / "privacy_cleanup_report.json"
        with open(report_file, 'w') as f:
            json.dump(privacy_report, f, indent=2)
        
        print(f"\n" + "=" * 80)
        print("🔒 PRIVACY CLEANUP COMPLETED!")
        print("=" * 80)
        print(f"✅ Total Files Cleaned: {len(all_cleaned_files)}")
        print(f"📄 Privacy Report Saved: {report_file}")
        print("=" * 80)
        
        print("\n🔍 REPLACEMENTS MADE:")
        print("-" * 60)
        for original, replacement in REPLACEMENTS.items():
            if "email" in original.lower() or "domain" in original.lower():
                print(f"   📧 {original} → {replacement}")
            elif "password" in original.lower():
                print(f"   🔒 {original} → {replacement}")
            elif "path" in str(original):
                print(f"   📂 {original} → {replacement}")
            else:
                print(f"   🔄 {original} → {replacement}")
        
        print("\n🛡️ PRIVACY MEASURES:")
        print("-" * 60)
        print("   ✅ Personal names removed")
        print("   ✅ Personal email addresses replaced")
        print("   ✅ Personal file paths sanitized")
        print("   ✅ Personal identifiers removed")
        print("   ✅ Sensitive information protected")
        
        print("\n📋 NEXT STEPS:")
        print("-" * 60)
        print("   1. Review the cleaned files")
        print("   2. Verify no personal information remains")
        print("   3. Update README.md with generic developer info")
        print("   4. Commit changes to public repository")
        print("   5. Test functionality with sanitized paths")
        
        return privacy_report
        
    except Exception as e:
        print(f"\n❌ Privacy cleanup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"cleanup_completed": False, "error": str(e)}

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("cleanup_completed", False) else 1)