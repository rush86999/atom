#!/bin/bash
# ATOM Platform Desktop App Startup Script - Consolidated Architecture

echo "🌟 ATOM Platform Desktop App Starting..."
echo "========================================"
echo "📁 Consolidated Architecture: Tauri + Next.js"
echo ""

# Check if we're in the right directory
if [ ! -d "src-tauri" ]; then
    echo "❌ Error: src-tauri directory not found"
    echo "   Please run this script from atom root directory"
    exit 1
fi

# Check if frontend-nextjs exists
if [ ! -d "frontend-nextjs" ]; then
    echo "❌ Error: frontend-nextjs directory not found"
    echo "   Frontend is required for desktop app"
    exit 1
fi

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
    cargo install tauri-cli
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install Tauri CLI"
        exit 1
    fi
    echo "✅ Tauri CLI installed"
else
    echo "✅ Tauri CLI available"
fi

# Check frontend dependencies
echo ""
echo "🔍 Checking frontend dependencies..."
cd frontend-nextjs

if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install frontend dependencies"
        exit 1
    fi
    echo "✅ Frontend dependencies installed"
else
    echo "✅ Frontend dependencies already installed"
fi

# Check if frontend builds successfully
echo "🏗️  Testing frontend build..."
npm run build > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: Frontend build failed"
    echo "   Please fix frontend build issues first"
    exit 1
fi
echo "✅ Frontend builds successfully"

# Go back to root
cd ..

# Check Tauri dependencies
echo ""
echo "🔍 Checking Tauri dependencies..."
cd src-tauri

# Check if Cargo.toml exists
if [ ! -f "Cargo.toml" ]; then
    echo "❌ Error: Cargo.toml not found in src-tauri"
    echo "   Please ensure Tauri configuration is correct"
    exit 1
fi

echo "✅ Tauri configuration found"

# Check if icons directory exists
if [ ! -d "icons" ]; then
    echo "❌ Error: icons directory not found"
    echo "   Please ensure icons are available for desktop app"
    exit 1
fi

echo "✅ Application icons available"

# Test Tauri compilation
echo "🔧 Testing Tauri compilation..."
cargo check > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: Tauri compilation failed"
    echo "   Please fix Rust compilation issues first"
    exit 1
fi
echo "✅ Tauri compiles successfully"

# Go back to root
cd ..

# Show configuration
echo ""
echo "⚙️  Configuration Summary:"
echo "   Architecture: Consolidated Tauri + Next.js"
echo "   Frontend: frontend-nextjs/"
echo "   Backend: src-tauri/"
echo "   Node.js: $(node --version)"
echo "   Rust: $(rustc --version)"
echo "   Tauri: $(tauri --version 2>/dev/null || echo 'CLI installed')"

# Start development
echo ""
echo "🚀 Starting Desktop Application..."
echo "   Frontend: http://localhost:3000"
echo "   Desktop: Tauri development mode"
echo "   Press Ctrl+C to stop"
echo ""

# Start frontend dev server in background
echo "🌐 Starting frontend development server..."
cd frontend-nextjs
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait a moment for frontend to start
sleep 3

# Start Tauri desktop app
echo "🖥️  Starting Tauri desktop application..."
cd src-tauri
cargo tauri dev

# Cleanup: kill frontend process when Tauri exits
kill $FRONTEND_PID 2>/dev/null

echo ""
echo "👋 Desktop application stopped"
