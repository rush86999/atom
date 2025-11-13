#!/bin/bash
# ATOM Platform Desktop App Startup Script

echo "🌟 ATOM Platform Desktop App Starting..."
echo "========================================"

# Check if we're in the right directory
if [ ! -d "desktop/tauri" ]; then
    echo "❌ Error: desktop/tauri directory not found"
    echo "   Please run this script from atom root directory"
    exit 1
fi

# Change to desktop directory
cd desktop/tauri

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    echo "   Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed"
    echo "   Please install npm (comes with Node.js)"
    exit 1
fi

echo "✅ npm version: $(npm --version)"

# Check if Rust is installed (required for Tauri)
if ! command -v rustc &> /dev/null; then
    echo "❌ Error: Rust is not installed"
    echo "   Please install Rust from https://rustup.rs/"
    echo "   Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo "✅ Rust version: $(rustc --version)"

# Check if Cargo is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Error: Cargo is not installed"
    echo "   Please install Rust (Cargo comes with Rust)"
    exit 1
fi

echo "✅ Cargo version: $(cargo --version)"

# Check if Tauri CLI is installed
if ! command -v tauri &> /dev/null; then
    echo "📦 Installing Tauri CLI..."
    npm install -g @tauri-apps/cli
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install Tauri CLI"
        exit 1
    fi
    echo "✅ Tauri CLI installed"
else
    echo "✅ Tauri CLI available"
fi

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found"
    echo "   Please ensure you're in the correct directory"
    exit 1
fi

echo "✅ package.json found"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

# Check if .env exists, create from .env.example if not
if [ ! -f ".env" ] && [ -f ".env.google.example" ]; then
    echo "📝 Creating .env from .env.google.example..."
    cp .env.google.example .env
    echo "✅ .env created"
fi

# Check if Python backend exists and set it up
if [ -d "src-tauri/resources/python-backend" ]; then
    echo "🐍 Setting up Python backend..."
    cd src-tauri/resources/python-backend
    
    # Check if Python is available
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "⚠️  Warning: Python not found, backend features may not work"
        PYTHON_CMD=""
    fi
    
    if [ -n "$PYTHON_CMD" ]; then
        # Create virtual environment if it doesn't exist
        if [ ! -d "venv" ]; then
            echo "📦 Creating Python virtual environment..."
            $PYTHON_CMD -m venv venv
            if [ $? -eq 0 ]; then
                echo "✅ Virtual environment created"
            else
                echo "⚠️  Warning: Failed to create virtual environment"
            fi
        fi
        
        # Activate virtual environment and install dependencies
        if [ -d "venv" ]; then
            echo "📦 Installing Python dependencies..."
            source venv/bin/activate
            pip install -r requirements.txt > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                echo "✅ Python dependencies installed"
            else
                echo "⚠️  Warning: Failed to install Python dependencies"
            fi
            deactivate
        fi
    fi
    
    # Go back to tauri directory
    cd ../../..
fi

# Show configuration
echo ""
echo "⚙️  Configuration:"
echo "   Directory: $(pwd)"
echo "   Node.js: $(node --version)"
echo "   Rust: $(rustc --version)"

# Start development server
echo ""
echo "🚀 Starting Tauri development server..."
echo "   Desktop app will open automatically"
echo "   Press Ctrl+C to stop"
echo ""

npm run tauri:dev