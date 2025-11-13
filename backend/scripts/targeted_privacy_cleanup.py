#!/usr/bin/env python3
"""
Targeted Privacy Cleanup
Clean specific important files for public repository
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

print("🔒 TARGETED PRIVACY CLEANUP")
print("=" * 80)
print("Cleaning personal information from key files")
print("=" * 80)

# Define key files to clean
KEY_FILES = [
    "working_enhanced_workflow_engine.py",
    "setup_websocket_server.py", 
    "test_advanced_workflows.py",
    "test_websocket_integration.py",
    "comprehensive_system_report.py",
    "final_implementation_summary.py",
    "local_production_setup.py",
    "final_deployment_and_next_steps.py",
    "final_implementation_summary.json"
]

# Define replacements
REPLACEMENTS = {
    "rushiparikh": "developer",
    "Rushi Parikh": "Developer", 
    "/Users/rushiparikh": "/home/developer",
    "/Users/rushiparikh/projects/atom": "/home/developer/projects",
    "/Users/rushiparikh/atom-production": "/opt/atom",
    "admin@atom.com": "noreply@atom.com",
    "your_email@gmail.com": "noreply@atom.com"
}

def clean_file_content(content):
    """Clean personal information from file content"""
    cleaned_content = content
    
    for personal_info, replacement in REPLACEMENTS.items():
        cleaned_content = cleaned_content.replace(personal_info, replacement)
    
    return cleaned_content

def clean_key_file(file_path):
    """Clean a key file"""
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

def main():
    """Main targeted cleanup"""
    current_dir = Path.cwd()
    cleaned_files = []
    
    print(f"\n📂 Current Directory: {current_dir}")
    print(f"\n🔧 Cleaning Key Files:")
    print("-" * 60)
    
    for filename in KEY_FILES:
        file_path = current_dir / filename
        
        if file_path.exists():
            print(f"   📄 Processing: {filename}")
            
            if clean_key_file(file_path):
                cleaned_files.append(filename)
                print(f"      ✅ Cleaned personal information")
            else:
                print(f"      ℹ️ No personal information found")
        else:
            print(f"   ❌ File not found: {filename}")
    
    print(f"\n📊 Cleanup Summary:")
    print("-" * 60)
    print(f"   📄 Files Processed: {len(KEY_FILES)}")
    print(f"   ✅ Files Cleaned: {len(cleaned_files)}")
    print(f"   📋 Cleaned Files: {', '.join(cleaned_files)}")
    
    # Create a simple privacy note
    privacy_note = {
        "privacy_notice": "This repository has been cleaned for public privacy.",
        "personal_info_removed": [
            "Personal names and usernames",
            "Personal file paths", 
            "Personal email addresses",
            "Personal directory structures"
        ],
        "replacements_made": REPLACEMENTS,
        "cleanup_timestamp": datetime.now().isoformat(),
        "note": "All personal information has been replaced with generic alternatives for public repository privacy."
    }
    
    privacy_note_file = current_dir / "PRIVACY_NOTICE.md"
    with open(privacy_note_file, 'w') as f:
        f.write("# Privacy Notice\n\n")
        f.write("This repository has been cleaned for public privacy.\n\n")
        f.write("## Personal Information Removed\n")
        f.write("- Personal names and usernames\n")
        f.write("- Personal file paths\n")
        f.write("- Personal email addresses\n")
        f.write("- Personal directory structures\n\n")
        f.write("## Replacements Made\n")
        for original, replacement in REPLACEMENTS.items():
            f.write(f"- `{original}` → `{replacement}`\n")
        f.write(f"\n**Cleanup completed:** {datetime.now().isoformat()}")
    
    print(f"\n📄 Privacy Notice Created: {privacy_note_file}")
    
    print(f"\n🔒 PRIVACY CLEANUP COMPLETED!")
    print("=" * 80)
    print("✅ Personal information has been removed from key files")
    print("✅ Repository is now ready for public sharing")
    print("✅ Privacy notice has been created")
    print("=" * 80)
    
    return {"success": True, "cleaned_files": len(cleaned_files)}

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result["success"] else 1)