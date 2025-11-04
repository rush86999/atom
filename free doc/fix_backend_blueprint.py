#!/usr/bin/env python3
"""
Backend Blueprint Fix Script
Fixes the blueprint registration conflict preventing backend startup
"""

import os
import sys
import re
from pathlib import Path


class BackendBlueprintFixer:
    def __init__(self):
        self.backend_path = Path("backend/python-api-service")
        self.main_app_file = self.backend_path / "main_api_app.py"
        self.backup_dir = Path("backup")

    def create_backup(self):
        """Create backup of the main app file"""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(exist_ok=True)

        backup_file = (
            self.backup_dir / f"main_api_app_backup_{int(os.times().elapsed)}.py"
        )

        if self.main_app_file.exists():
            with open(self.main_app_file, "r") as source:
                content = source.read()
            with open(backup_file, "w") as backup:
                backup.write(content)
            print(f"✅ Created backup: {backup_file}")
            return True
        else:
            print(f"❌ Main app file not found: {self.main_app_file}")
            return False

    def analyze_blueprint_registration(self):
        """Analyze blueprint registration in main app file"""
        if not self.main_app_file.exists():
            print(f"❌ File not found: {self.main_app_file}")
            return None

        with open(self.main_app_file, "r") as file:
            content = file.read()

        # Find all blueprint registrations
        blueprint_pattern = r'app\.register_blueprint\((\w+_bp),\s*url_prefix=("[^"]+"|\'[^\']+\')(?:,\s*name=("[^"]+"|\'[^\']+\'))?\)'
        matches = re.findall(blueprint_pattern, content)

        print("🔍 Analyzing blueprint registrations:")
        print("=" * 50)

        blueprints = {}
        for match in matches:
            bp_name = match[0]
            url_prefix = match[1].strip("\"'")
            name_param = match[2].strip("\"'") if match[2] else None

            blueprints[bp_name] = {
                "url_prefix": url_prefix,
                "name_param": name_param,
                "line": self.find_line_number(content, f"register_blueprint({bp_name}"),
            }

            status = "✅ Named" if name_param else "⚠️  Unnamed"
            print(f"{status} {bp_name} -> {url_prefix} (name: {name_param or 'None'})")

        return blueprints, content

    def find_line_number(self, content, search_text):
        """Find line number of specific text in content"""
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if search_text in line:
                return i
        return -1

    def fix_blueprint_registration(self):
        """Fix blueprint registration conflicts"""
        print("\n🔧 Fixing Blueprint Registration")
        print("=" * 50)

        # Create backup first
        if not self.create_backup():
            return False

        # Analyze current state
        blueprints, content = self.analyze_blueprint_registration()
        if not blueprints:
            print("❌ No blueprints found to fix")
            return False

        # Find conflicting blueprints (those without names)
        conflicting_blueprints = {
            name: info for name, info in blueprints.items() if not info["name_param"]
        }

        if not conflicting_blueprints:
            print("✅ No conflicting blueprints found - all are properly named")
            return True

        print(f"\n⚠️  Found {len(conflicting_blueprints)} blueprints without names:")
        for bp_name, info in conflicting_blueprints.items():
            print(f"   - {bp_name} at line {info['line']}")

        # Fix the content
        fixed_content = content
        fixes_applied = 0

        for bp_name, info in conflicting_blueprints.items():
            # Generate unique name based on URL prefix
            url_prefix = info["url_prefix"]
            name_suggestion = self.generate_blueprint_name(url_prefix, bp_name)

            # Find and replace the registration line
            old_pattern = f"app.register_blueprint\\({bp_name},\\s*url_prefix={info['url_prefix']}"
            new_line = f'app.register_blueprint({bp_name}, url_prefix={info["url_prefix"]}, name="{name_suggestion}")'

            # Use more precise replacement
            lines = fixed_content.split("\n")
            for i, line in enumerate(lines):
                if (
                    f"register_blueprint({bp_name}" in line
                    and info["url_prefix"] in line
                ):
                    if "name=" not in line:
                        lines[i] = new_line
                        fixes_applied += 1
                        print(f"✅ Fixed {bp_name} -> name: {name_suggestion}")
                        break

        if fixes_applied > 0:
            # Write fixed content
            with open(self.main_app_file, "w") as file:
                file.write("\n".join(lines))

            print(f"\n✅ Applied {fixes_applied} fixes to blueprint registrations")

            # Verify the fix
            print("\n🔍 Verifying fix...")
            self.verify_fix()

            return True
        else:
            print("❌ No fixes were applied")
            return False

    def generate_blueprint_name(self, url_prefix, bp_name):
        """Generate a unique name for the blueprint"""
        # Remove /api/ prefix and replace slashes with underscores
        name = url_prefix.replace("/api/", "").replace("/", "_").strip("_/")
        if not name:
            name = bp_name.replace("_bp", "")
        return f"{name}_blueprint"

    def verify_fix(self):
        """Verify that the blueprint fix was successful"""
        print("\n🔍 Verifying Blueprint Fix")
        print("=" * 50)

        blueprints, _ = self.analyze_blueprint_registration()

        unnamed_blueprints = [
            name for name, info in blueprints.items() if not info["name_param"]
        ]

        if not unnamed_blueprints:
            print("✅ SUCCESS: All blueprints now have unique names!")
            print("\n🚀 Next steps:")
            print("1. Start the backend: ./start-backend.sh")
            print("2. Test Jira OAuth endpoints")
            print("3. Verify integration works end-to-end")
        else:
            print(
                f"❌ FAILED: {len(unnamed_blueprints)} blueprints still without names:"
            )
            for bp_name in unnamed_blueprints:
                print(f"   - {bp_name}")

    def test_backend_startup(self):
        """Test if backend can start after fix"""
        print("\n🚀 Testing Backend Startup")
        print("=" * 50)

        try:
            # Try to import and create the app
            sys.path.insert(0, str(self.backend_path.parent))

            # Import the main app module
            from backend.python_api_service.main_api_app import create_app

            try:
                app = create_app()
                print("✅ Backend app created successfully!")
                print(f"✅ App name: {app.name}")

                # Check registered blueprints
                print(f"✅ Registered blueprints: {len(app.blueprints)}")

                for name, blueprint in app.blueprints.items():
                    print(f"   - {name}: {blueprint.url_prefix}")

                return True

            except Exception as e:
                print(f"❌ Failed to create app: {e}")
                return False

        except ImportError as e:
            print(f"❌ Import error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


def main():
    """Main function to fix backend blueprint issues"""
    print("🔧 ATOM Backend Blueprint Fixer")
    print("=" * 60)

    fixer = BackendBlueprintFixer()

    # Check if main app file exists
    if not fixer.main_app_file.exists():
        print(f"❌ Main app file not found: {fixer.main_app_file}")
        print("💡 Make sure you're running this from the project root")
        return

    # Run the fix
    success = fixer.fix_blueprint_registration()

    if success:
        # Test the fix
        fixer.test_backend_startup()
    else:
        print("\n❌ Fix failed. Check the errors above.")


if __name__ == "__main__":
    main()
