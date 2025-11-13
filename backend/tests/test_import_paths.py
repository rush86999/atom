#!/usr/bin/env python3
"""
Import Path Test for ATOM Platform
Tests which modules are being imported and from which paths
"""

import sys
import os


def test_import_paths():
    """Test import paths for auth handler modules"""
    print("🔍 IMPORT PATH TEST")
    print("=" * 60)

    # Print Python path
    print("\n📁 PYTHON PATH:")
    for path in sys.path:
        print(f"  {path}")

    # Test importing auth handlers
    modules_to_test = [
        "auth_handler_asana",
        "auth_handler_trello",
        "auth_handler_notion",
        "auth_handler_gmail",
        "auth_handler_slack",
    ]

    print(f"\n🔧 MODULE IMPORT TEST:")
    print("-" * 60)

    for module_name in modules_to_test:
        try:
            # Try to import the module
            module = __import__(module_name)
            file_path = getattr(module, "__file__", "Unknown")
            print(f"✅ {module_name}: {file_path}")

            # Try to get blueprint
            try:
                if module_name == "auth_handler_asana":
                    blueprint = getattr(module, "auth_asana_bp")
                elif module_name == "auth_handler_trello":
                    blueprint = getattr(module, "auth_trello_bp")
                elif module_name == "auth_handler_notion":
                    blueprint = getattr(module, "auth_notion_bp")
                elif module_name == "auth_handler_gmail":
                    blueprint = getattr(module, "auth_gmail_bp")
                elif module_name == "auth_handler_slack":
                    blueprint = getattr(module, "auth_slack_bp")

                print(f"   🔐 Blueprint: {blueprint.name}")
            except AttributeError as e:
                print(f"   ❌ No blueprint found: {e}")

        except ImportError as e:
            print(f"❌ {module_name}: ImportError - {e}")
        except Exception as e:
            print(f"❌ {module_name}: Error - {e}")


def check_module_locations():
    """Check where modules are located on disk"""
    print(f"\n📂 MODULE LOCATIONS ON DISK:")
    print("-" * 60)

    modules = ["auth_handler_asana", "auth_handler_trello", "auth_handler_notion"]

    for module_name in modules:
        # Try to find the module file
        for path in sys.path:
            if os.path.isdir(path):
                possible_paths = [
                    os.path.join(path, f"{module_name}.py"),
                    os.path.join(
                        path, "backend", "python-api-service", f"{module_name}.py"
                    ),
                    os.path.join(
                        path,
                        "desktop",
                        "tauri",
                        "src-tauri",
                        "python-backend",
                        "backend",
                        "python-api-service",
                        f"{module_name}.py",
                    ),
                ]

                for possible_path in possible_paths:
                    if os.path.exists(possible_path):
                        print(f"📄 {module_name}: {possible_path}")
                        break
                else:
                    continue
                break
        else:
            print(f"❌ {module_name}: Not found in Python path")


def test_blueprint_imports():
    """Test importing blueprints directly"""
    print(f"\n🎯 DIRECT BLUEPRINT IMPORT TEST:")
    print("-" * 60)

    blueprint_tests = [
        ("auth_handler_asana", "auth_asana_bp"),
        ("auth_handler_trello", "auth_trello_bp"),
        ("auth_handler_notion", "auth_notion_bp"),
        ("auth_handler_gmail", "auth_gmail_bp"),
        ("auth_handler_slack", "auth_slack_bp"),
    ]

    for module_name, blueprint_name in blueprint_tests:
        try:
            module = __import__(module_name, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            print(f"✅ {module_name}.{blueprint_name}: {blueprint.name}")

            # Check routes
            if hasattr(blueprint, "routes"):
                routes = list(blueprint.routes.keys())
                print(f"   📋 Routes: {len(routes)}")
                for route in routes[:3]:  # Show first 3 routes
                    print(f"     - {route}")
                if len(routes) > 3:
                    print(f"     ... and {len(routes) - 3} more")

        except ImportError as e:
            print(f"❌ {module_name}.{blueprint_name}: ImportError - {e}")
        except AttributeError as e:
            print(f"❌ {module_name}.{blueprint_name}: AttributeError - {e}")
        except Exception as e:
            print(f"❌ {module_name}.{blueprint_name}: Error - {e}")


def main():
    """Run all import tests"""
    print("🚀 ATOM PLATFORM IMPORT PATH ANALYSIS")
    print("=" * 60)

    # Change to backend directory to simulate server environment
    original_cwd = os.getcwd()
    backend_dir = os.path.join(original_cwd, "backend", "python-api-service")

    if os.path.exists(backend_dir):
        print(f"\n🔧 Changing to backend directory: {backend_dir}")
        os.chdir(backend_dir)
    else:
        print(f"\n⚠️  Backend directory not found: {backend_dir}")

    try:
        test_import_paths()
        check_module_locations()
        test_blueprint_imports()

        print(f"\n🎯 RECOMMENDATIONS:")
        print("-" * 60)
        print("1. Check Python path order - first match wins")
        print("2. Remove duplicate modules from different locations")
        print("3. Verify blueprint names match between imports and registration")
        print("4. Check for module caching issues")

    finally:
        # Restore original directory
        os.chdir(original_cwd)


if __name__ == "__main__":
    main()
