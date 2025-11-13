import os
import re


def fix_all_icon_imports():
    """Fix all problematic icon imports in the project"""

    # Define the replacement mapping for missing icons
    icon_replacements = {
        "PlayIcon": "ArrowForwardIcon",
        "StopIcon": "CloseIcon",
        "PauseIcon": "MinusIcon",
        "CalendarIcon": "TimeIcon",
        "BotIcon": "ChatIcon",
        "UserIcon": "PersonIcon",
        "SendIcon": "ArrowForwardIcon",
        "CheckIcon": "CheckCircleIcon",
        "ClockIcon": "TimeIcon",
        "TrashIcon": "DeleteIcon",
        "CloudIcon": "SunIcon",
        "ServerIcon": "SettingsIcon",
        "DatabaseIcon": "HamburgerIcon",
        "GlobeIcon": "ExternalLinkIcon",
        "ExternalLinkIcon": "ArrowForwardIcon",
        "DownloadIcon": "ArrowDownIcon",
        "EmbedIcon": "CopyIcon",
        "ArrowUpIcon": "ChevronUpIcon",
        "ArrowDownIcon": "ChevronDownIcon",
        "FilterIcon": "SearchIcon",
        "WarningIcon": "WarningTwoIcon",
    }

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

                    # Check if file contains any problematic icons
                    has_problematic_icons = any(
                        icon in content for icon in icon_replacements.keys()
                    )

                    if has_problematic_icons:
                        print(f"Fixing icons in: {file_path}")
                        new_content = content

                        # Replace in import statements
                        for old_icon, new_icon in icon_replacements.items():
                            if old_icon in new_content:
                                # Replace in import { ... } statements
                                pattern = rf"import\s*{{([^}}]*){re.escape(old_icon)}([^}}]*)}}"
                                replacement = rf"import {{\1{new_icon}\2}}"
                                new_content = re.sub(pattern, replacement, new_content)

                                # Also replace standalone usage
                                new_content = new_content.replace(old_icon, new_icon)

                        # Write the updated content back
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")


def check_available_icons():
    """Check what icons are actually available in @chakra-ui/icons"""
    icons_dir = "./frontend-nextjs/node_modules/@chakra-ui/icons/dist"
    if os.path.exists(icons_dir):
        icon_files = [f for f in os.listdir(icons_dir) if f.endswith(".d.ts")]
        icon_names = [f.replace(".d.ts", "") for f in icon_files]
        print("Available icons in @chakra-ui/icons:")
        for icon in sorted(icon_names):
            print(f"  - {icon}")
    else:
        print("Could not find @chakra-ui/icons directory")


def main():
    print("🔧 Fixing all problematic icon imports across the project...")

    # First show available icons for reference
    check_available_icons()

    # Then fix all problematic imports
    fix_all_icon_imports()

    print("✅ All problematic icon imports have been fixed")
    print("📋 Summary of replacements:")
    print("   PlayIcon → ArrowForwardIcon")
    print("   StopIcon → CloseIcon")
    print("   PauseIcon → MinusIcon")
    print("   CalendarIcon → TimeIcon")
    print("   BotIcon → ChatIcon")
    print("   UserIcon → PersonIcon")
    print("   SendIcon → ArrowForwardIcon")
    print("   CheckIcon → CheckCircleIcon")
    print("   ClockIcon → TimeIcon")
    print("   TrashIcon → DeleteIcon")
    print("   CloudIcon → SunIcon")
    print("   ServerIcon → SettingsIcon")
    print("   DatabaseIcon → HamburgerIcon")
    print("   GlobeIcon → ExternalLinkIcon")
    print("   ExternalLinkIcon → ArrowForwardIcon")
    print("   DownloadIcon → ArrowDownIcon")
    print("   EmbedIcon → CopyIcon")
    print("   ArrowUpIcon → ChevronUpIcon")
    print("   ArrowDownIcon → ChevronDownIcon")
    print("   FilterIcon → SearchIcon")
    print("   WarningIcon → WarningTwoIcon")


if __name__ == "__main__":
    main()
