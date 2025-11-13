import os
import re


def fix_play_icon_imports():
    """Fix all PlayIcon imports in the project by replacing with ArrowForwardIcon"""

    # Define the replacement mapping
    replacements = {"PlayIcon": "ArrowForwardIcon"}

    # File extensions to search
    extensions = [".tsx", ".ts", ".jsx", ".js"]

    # Walk through the project directory
    for root, dirs, files in os.walk("."):
        # Skip node_modules and other build directories
        if "node_modules" in root or "build" in root or "dist" in root:
            continue

        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Check if file contains PlayIcon
                    if "PlayIcon" in content:
                        print(f"Fixing PlayIcon in: {file_path}")

                        # Replace PlayIcon with ArrowForwardIcon in imports
                        old_import_pattern = r"import\s*{([^}]*PlayIcon[^}]*)}"
                        new_content = content

                        # Replace in import statements
                        for old_icon, new_icon in replacements.items():
                            # Replace in import { ... } statements
                            pattern = (
                                rf"import\s*{{([^}}]*){re.escape(old_icon)}([^}}]*)}}"
                            )
                            replacement = rf"import {{\1{new_icon}\2}}"
                            new_content = re.sub(pattern, replacement, new_content)

                            # Also replace standalone usage
                            new_content = new_content.replace(old_icon, new_icon)

                        # Write the updated content back
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")


def main():
    print("🔧 Fixing PlayIcon imports across the project...")
    fix_play_icon_imports()
    print("✅ All PlayIcon imports have been replaced with ArrowForwardIcon")


if __name__ == "__main__":
    main()
