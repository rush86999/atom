#!/usr/bin/env python3
"""
Quick Start Script for ATOM Google Drive Integration
Sets up environment, installs dependencies, and starts the application
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# Colors for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_color(message: str, color: str = Colors.WHITE):
    """Print colored message"""
    print(f"{color}{message}{Colors.END}")

def print_header(title: str):
    """Print header"""
    print_color("\n" + "="*60, Colors.CYAN)
    print_color(f"  {title}", Colors.BOLD + Colors.CYAN)
    print_color("="*60, Colors.CYAN)

def print_step(step: int, total: int, message: str):
    """Print step"""
    print_color(f"\n[Step {step}/{total}] {message}", Colors.BLUE + Colors.BOLD)

def print_success(message: str):
    """Print success message"""
    print_color(f"✅ {message}", Colors.GREEN + Colors.BOLD)

def print_warning(message: str):
    """Print warning message"""
    print_color(f"⚠️  {message}", Colors.YELLOW)

def print_error(message: str):
    """Print error message"""
    print_color(f"❌ {message}", Colors.RED + Colors.BOLD)

def print_info(message: str):
    """Print info message"""
    print_color(f"ℹ️  {message}", Colors.CYAN)

def run_command(command: str, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run command and return result"""
    try:
        print_color(f"Running: {command}", Colors.MAGENTA)
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True
        )
        if result.stdout:
            print_color(result.stdout.strip(), Colors.WHITE)
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {e}")
        if e.stdout:
            print_color(f"STDOUT: {e.stdout}", Colors.WHITE)
        if e.stderr:
            print_color(f"STDERR: {e.stderr}", Colors.RED)
        raise

def check_prerequisites() -> bool:
    """Check if prerequisites are installed"""
    print_step(1, 8, "Checking Prerequisites")
    
    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        print_error(f"Python {python_version.major}.{python_version.minor} is not supported. Please use Python 3.8 or higher.")
        return False
    
    print_success(f"Python {python_version.major}.{python_version.minor}.{python_version.micro} detected")
    
    # Check pip
    try:
        result = run_command("pip --version", capture_output=True)
        print_success(f"pip detected: {result.stdout.strip()}")
    except Exception as e:
        print_error("pip is not installed or not in PATH")
        return False
    
    # Check git
    try:
        result = run_command("git --version", capture_output=True)
        print_success(f"git detected: {result.stdout.strip()}")
    except Exception as e:
        print_warning("git is not installed. Some features may not work.")
    
    # Check PostgreSQL
    try:
        result = run_command("psql --version", capture_output=True)
        print_success(f"PostgreSQL detected: {result.stdout.strip()}")
    except Exception as e:
        print_warning("PostgreSQL is not installed. You may need to install it for the database.")
    
    # Check Redis
    try:
        result = run_command("redis-cli --version", capture_output=True)
        print_success(f"Redis detected: {result.stdout.strip()}")
    except Exception as e:
        print_warning("Redis is not installed. You may need to install it for caching.")
    
    return True

def setup_environment() -> bool:
    """Set up environment"""
    print_step(2, 8, "Setting Up Environment")
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    env_example_file = Path(".env.example")
    
    if not env_file.exists():
        if env_example_file.exists():
            print_info("Creating .env file from .env.example")
            with open(env_example_file, 'r') as f:
                content = f.read()
            
            # Generate random secret key
            import secrets
            secret_key = secrets.token_urlsafe(32)
            content = content.replace('your-super-secret-key-change-in-production', secret_key)
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print_success(".env file created successfully")
            print_warning("Please edit .env file with your Google Drive API credentials")
        else:
            print_error("Neither .env nor .env.example found. Please create .env file manually.")
            return False
    else:
        print_success(".env file already exists")
    
    # Create required directories
    directories = [
        "logs",
        "lancedb/data",
        "temp",
        "uploads",
        "backups"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created directory: {directory}")
        else:
            print_success(f"Directory already exists: {directory}")
    
    return True

def install_dependencies() -> bool:
    """Install Python dependencies"""
    print_step(3, 8, "Installing Dependencies")
    
    # Check if requirements file exists
    requirements_file = Path("requirements.txt")
    requirements_new_file = Path("requirements_new.txt")
    
    if not requirements_file.exists():
        if requirements_new_file.exists():
            requirements_file = requirements_new_file
            print_info("Using requirements_new.txt")
        else:
            print_error("Neither requirements.txt nor requirements_new.txt found")
            return False
    
    # Create virtual environment if it doesn't exist
    venv_dir = Path("venv")
    if not venv_dir.exists():
        print_info("Creating virtual environment")
        run_command("python -m venv venv")
        print_success("Virtual environment created")
    else:
        print_success("Virtual environment already exists")
    
    # Activate virtual environment and install dependencies
    if os.name == 'nt':  # Windows
        pip_command = "venv\\Scripts\\pip"
        python_command = "venv\\Scripts\\python"
    else:  # Unix/macOS
        pip_command = "venv/bin/pip"
        python_command = "venv/bin/python"
    
    # Upgrade pip
    print_info("Upgrading pip")
    run_command(f"{pip_command} install --upgrade pip")
    
    # Install dependencies
    print_info("Installing dependencies")
    run_command(f"{pip_command} install -r {requirements_file}")
    
    # Download NLTK data
    print_info("Downloading NLTK data")
    run_command(f"{python_command} -c \"import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')\"")
    
    return True

def setup_database() -> bool:
    """Set up database"""
    print_step(4, 8, "Setting Up Database")
    
    # Check if PostgreSQL is running
    try:
        run_command("pg_isready -U postgres", check=False, capture_output=True)
        print_success("PostgreSQL is running")
    except Exception as e:
        print_error("PostgreSQL is not running. Please start PostgreSQL service.")
        print_info("On Ubuntu/Debian: sudo systemctl start postgresql")
        print_info("On macOS: brew services start postgresql")
        print_info("On Windows: net start postgresql")
        return False
    
    # Create database
    try:
        print_info("Creating database")
        run_command("createdb -U postgres atom", check=False)
        print_success("Database 'atom' created or already exists")
    except Exception as e:
        print_warning("Database creation failed. It may already exist.")
    
    # Run database initialization
    print_info("Initializing database schema")
    try:
        if os.name == 'nt':  # Windows
            python_command = "venv\\Scripts\\python"
        else:
            python_command = "venv/bin/python"
        
        run_command(f"{python_command} scripts/init_database.py")
        print_success("Database initialized successfully")
    except Exception as e:
        print_error(f"Database initialization failed: {e}")
        return False
    
    return True

def start_services() -> bool:
    """Start required services"""
    print_step(5, 8, "Starting Services")
    
    # Check Redis
    try:
        run_command("redis-cli ping", capture_output=True)
        print_success("Redis is running")
    except Exception as e:
        print_error("Redis is not running. Please start Redis service.")
        print_info("On Ubuntu/Debian: sudo systemctl start redis-server")
        print_info("On macOS: brew services start redis")
        print_info("On Windows: net start redis")
        return False
    
    return True

def configure_google_drive() -> bool:
    """Configure Google Drive API"""
    print_step(6, 8, "Configuring Google Drive API")
    
    print_info("Google Drive API Configuration Required")
    print_color("\n1. Go to Google Cloud Console: https://console.cloud.google.com/", Colors.CYAN)
    print_color("2. Create a new project or select existing project", Colors.CYAN)
    print_color("3. Enable APIs:", Colors.CYAN)
    print_color("   - Google Drive API", Colors.WHITE)
    print_color("   - Google Drive API (v3)", Colors.WHITE)
    print_color("4. Create OAuth 2.0 Credentials:", Colors.CYAN)
    print_color("   - Go to 'Credentials' → 'Create Credentials' → 'OAuth 2.0 Client ID'", Colors.WHITE)
    print_color("   - Select 'Web application'", Colors.WHITE)
    print_color("   - Add authorized redirect URI: http://localhost:8000/auth/google/callback", Colors.WHITE)
    print_color("5. Download JSON credentials file", Colors.CYAN)
    print_color("6. Update .env file with your CLIENT_ID and CLIENT_SECRET", Colors.CYAN)
    
    # Check if credentials are configured
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
        
        if 'your-google-client-id' in content or 'your-google-client-secret' in content:
            print_warning("Google Drive credentials not configured in .env file")
            print_info("Please update .env file with your actual Google Drive API credentials")
            return False
        else:
            print_success("Google Drive credentials appear to be configured")
            return True
    else:
        print_error(".env file not found")
        return False

def run_tests() -> bool:
    """Run tests to verify installation"""
    print_step(7, 8, "Running Tests")
    
    try:
        if os.name == 'nt':  # Windows
            python_command = "venv\\Scripts\\python"
        else:
            python_command = "venv/bin/python"
        
        # Run basic health check
        run_command(f"{python_command} -c \"from config import get_config; config = get_config(); print('Configuration loaded successfully')\"")
        
        print_success("Basic tests passed")
        return True
    except Exception as e:
        print_error(f"Tests failed: {e}")
        return False

def start_application() -> bool:
    """Start the application"""
    print_step(8, 8, "Starting Application")
    
    try:
        if os.name == 'nt':  # Windows
            python_command = "venv\\Scripts\\python"
        else:
            python_command = "venv/bin/python"
        
        print_success("Starting ATOM Google Drive Integration...")
        print_color("\n🚀 Application is starting...", Colors.GREEN + Colors.BOLD)
        print_color("📍 Health Check: http://localhost:8000/health", Colors.CYAN)
        print_color("📍 API Documentation: http://localhost:8000/docs", Colors.CYAN)
        print_color("📍 Google Drive Integration: http://localhost:8000/api/google-drive", Colors.CYAN)
        print_color("📍 Search UI: http://localhost:8000/api/search", Colors.CYAN)
        print_color("\n🛑 Press Ctrl+C to stop the application", Colors.YELLOW)
        print_color("\n", Colors.WHITE)
        
        # Start the application
        run_command(f"{python_command} app.py", check=False)
        
        return True
    except KeyboardInterrupt:
        print_info("\nApplication stopped by user")
        return True
    except Exception as e:
        print_error(f"Failed to start application: {e}")
        return False

def show_next_steps():
    """Show next steps"""
    print_header("Next Steps")
    
    print_color("1. 📱 Connect your Google Drive account:", Colors.BLUE + Colors.BOLD)
    print_color("   Visit: http://localhost:8000/api/google-drive/auth", Colors.CYAN)
    
    print_color("\n2. 🔍 Test the search functionality:", Colors.BLUE + Colors.BOLD)
    print_color("   Visit: http://localhost:8000/api/search/providers", Colors.CYAN)
    
    print_color("\n3. 🤖 Create automation workflows:", Colors.BLUE + Colors.BOLD)
    print_color("   Visit: http://localhost:8000/api/google-drive/automation", Colors.CYAN)
    
    print_color("\n4. 📊 Monitor system health:", Colors.BLUE + Colors.BOLD)
    print_color("   Visit: http://localhost:8000/health", Colors.CYAN)
    
    print_color("\n5. 📚 Read the documentation:", Colors.BLUE + Colors.BOLD)
    print_color("   - SETUP_GUIDE.md", Colors.CYAN)
    print_color("   - CODE_STRUCTURE_OVERVIEW.md", Colors.CYAN)
    print_color("   - IMPLEMENTATION_ROADMAP.md", Colors.CYAN)
    
    print_color("\n🎉 Your ATOM Google Drive Integration is ready!", Colors.GREEN + Colors.BOLD)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Quick Start ATOM Google Drive Integration")
    parser.add_argument("--skip-dependencies", action="store_true", help="Skip dependency installation")
    parser.add_argument("--skip-database", action="store_true", help="Skip database setup")
    parser.add_argument("--skip-google-config", action="store_true", help="Skip Google Drive configuration")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument("--test", action="store_true", help="Run tests only")
    
    args = parser.parse_args()
    
    # Print welcome message
    print_header("ATOM Google Drive Integration - Quick Start")
    print_color("This script will set up your environment and start the application.", Colors.WHITE)
    print_color(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.CYAN)
    
    try:
        # Run setup steps
        if not check_prerequisites():
            sys.exit(1)
        
        if not setup_environment():
            sys.exit(1)
        
        if not args.skip_dependencies:
            if not install_dependencies():
                sys.exit(1)
        else:
            print_warning("Skipping dependency installation")
        
        if not args.skip_database:
            if not setup_database():
                sys.exit(1)
        else:
            print_warning("Skipping database setup")
        
        if not args.skip_google_config:
            if not configure_google_drive():
                sys.exit(1)
        else:
            print_warning("Skipping Google Drive configuration")
        
        if args.test:
            print_info("Running tests in test mode")
            if not run_tests():
                sys.exit(1)
            print_success("All tests passed!")
            return
        
        # Start services and application
        if not start_services():
            sys.exit(1)
        
        if not run_tests():
            sys.exit(1)
        
        if not start_application():
            sys.exit(1)
        
        # Show next steps
        show_next_steps()
        
    except KeyboardInterrupt:
        print_info("\nSetup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()