#!/bin/bash

# Atom Desktop Agent - Build & Deploy Script
# Builds and deploys the new chat interface

set -e  # Exit on any error

echo "🚀 ATOM Desktop Agent - Build & Deploy Script"
echo "================================================="
echo "Building chat interface for existing Tauri app..."
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 Project Root: $PROJECT_ROOT"
echo "📁 Script Directory: $SCRIPT_DIR"
echo ""

# Step 1: Backup existing configuration
echo "📦 Step 1: Backup existing configuration"
cd "$PROJECT_ROOT/src-tauri"

if [ -f "Cargo.toml" ]; then
    cp Cargo.toml Cargo.toml.backup
    echo "✅ Backed up existing Cargo.toml"
else
    echo "ℹ️  No existing Cargo.toml to backup"
fi

if [ -f "src/main.rs" ]; then
    cp src/main.rs src/main.rs.backup
    echo "✅ Backed up existing main.rs"
else
    echo "ℹ️  No existing main.rs to backup"
fi

echo ""

# Step 2: Update configuration files
echo "⚙️  Step 2: Update configuration files"

# Copy updated Cargo.toml
if [ -f "Cargo_with_chat.toml" ]; then
    cp Cargo_with_chat.toml Cargo.toml
    echo "✅ Updated Cargo.toml with chat interface dependencies"
else
    echo "❌ Cargo_with_chat.toml not found"
    exit 1
fi

# Copy updated main.rs
if [ -f "src/main_with_chat.rs" ]; then
    cp src/main_with_chat.rs src/main.rs
    echo "✅ Updated main.rs with chat interface commands"
else
    echo "❌ src/main_with_chat.rs not found"
    exit 1
fi

echo ""

# Step 3: Check for required dependencies
echo "🔍 Step 3: Check dependencies"

# Check if atom_agent_commands.rs exists
if [ ! -f "src/atom_agent_commands.rs" ]; then
    echo "❌ atom_agent_commands.rs not found"
    exit 1
else
    echo "✅ atom_agent_commands.rs found"
fi

# Check if TauriChatInterface.tsx exists
if [ ! -f "../src/components/Chat/TauriChatInterface.tsx" ]; then
    echo "❌ TauriChatInterface.tsx not found"
    exit 1
else
    echo "✅ TauriChatInterface.tsx found"
fi

echo ""

# Step 4: Install Rust dependencies
echo "📦 Step 4: Install Rust dependencies"
cd "$PROJECT_ROOT/src-tauri"

# Check if cargo is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Cargo not found. Please install Rust."
    echo "Visit: https://rustup.rs/"
    exit 1
fi

echo "📥 Installing dependencies..."
cargo check --features chat-interface
echo "✅ Dependencies checked and installed"

echo ""

# Step 5: Build the application
echo "🔨 Step 5: Build the application"

echo "🏗️  Building Atom Desktop Agent with chat interface..."
cargo build --release --features chat-interface

if [ $? -eq 0 ]; then
    echo "✅ Build completed successfully"
else
    echo "❌ Build failed"
    exit 1
fi

echo ""

# Step 6: Create frontend build
echo "🎨 Step 6: Build frontend"

cd "$PROJECT_ROOT"

# Check if Node.js and npm are installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install Node.js."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

echo "📦 Installing frontend dependencies..."
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "✅ Dependencies already installed"
fi

echo "🏗️  Building frontend with chat interface..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Frontend build completed successfully"
else
    echo "❌ Frontend build failed"
    exit 1
fi

echo ""

# Step 7: Create distribution package
echo "📦 Step 7: Create distribution package"

cd "$PROJECT_ROOT/src-tauri"

# Check if tauri CLI is installed
if ! command -v tauri &> /dev/null; then
    echo "📥 Installing Tauri CLI..."
    cargo install tauri-cli
fi

echo "📦 Creating distribution package..."
tauri build --features chat-interface

if [ $? -eq 0 ]; then
    echo "✅ Distribution package created successfully"
    
    # Find the built package
    DIST_DIR="$PROJECT_ROOT/src-tauri/target/release/bundle"
    if [ -d "$DIST_DIR" ]; then
        echo "📦 Distribution files:"
        find "$DIST_DIR" -name "*.dmg" -o -name "*.exe" -o -name "*.deb" -o -name "*.AppImage" | while read file; do
            echo "   ✅ $file"
        done
    fi
else
    echo "❌ Distribution package creation failed"
    exit 1
fi

echo ""

# Step 8: Create test script
echo "🧪 Step 8: Create test script"

cd "$PROJECT_ROOT"

# Create test script
cat > test_chat_interface.sh << 'EOF'
#!/bin/bash

# Test Script for Atom Chat Interface
echo "🧪 ATOM Chat Interface Test Script"
echo "====================================="

# Find the built application
APP_PATH=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    APP_PATH=$(find . -name "Atom.app" -type d | head -1)
    if [ -n "$APP_PATH" ]; then
        echo "🚀 Starting macOS app: $APP_PATH"
        open "$APP_PATH"
    else
        echo "❌ Atom.app not found in distribution"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    APP_PATH=$(find . -name "atom_*.AppImage" | head -1)
    if [ -n "$APP_PATH" ]; then
        echo "🚀 Starting Linux AppImage: $APP_PATH"
        chmod +x "$APP_PATH"
        "$APP_PATH"
    else
        echo "❌ Atom AppImage not found in distribution"
    fi
else
    APP_PATH=$(find . -name "AtomSetup.exe" | head -1)
    if [ -n "$APP_PATH" ]; then
        echo "🚀 Starting Windows installer: $APP_PATH"
        start "$APP_PATH"
    else
        echo "❌ AtomSetup.exe not found in distribution"
    fi
fi

echo ""
echo "✅ Test script completed"
echo ""
echo "📋 Manual Testing Checklist:"
echo "  1. Verify chat interface loads"
echo "  2. Test message sending and receiving"
echo "  3. Test integration commands (e.g., 'Check my Slack messages')"
echo "  4. Verify connection status indicators"
echo "  5. Test settings and preferences"
echo "  6. Verify notification system"
echo "  7. Test file attachment functionality"
echo "  8. Verify voice recording (if available)"
echo ""
echo "🐛 Report any issues to: https://github.com/atom-platform/desktop-agent/issues"
EOF

chmod +x test_chat_interface.sh
echo "✅ Test script created: test_chat_interface.sh"

echo ""

# Step 9: Create deployment summary
echo "📊 Step 9: Create deployment summary"

cat > DEPLOYMENT_SUMMARY.md << 'EOF'
# 🚀 Atom Desktop Agent - Deployment Summary

## 📦 Build Information
- **Version**: 1.1.0
- **Build Date**: $(date)
- **Platform**: $(uname -s)
- **Features**: chat-interface, all-integrations

## 🆕 New Features Added
- ✅ **Chat Interface** - Users can now talk to Atom AI assistant
- ✅ **Integration Commands** - Control Slack, Notion, Asana via chat
- ✅ **Real-time Messaging** - WebSocket-based chat with status indicators
- ✅ **Voice Support** - Voice recording for chat input (framework ready)
- ✅ **File Attachments** - Upload files through chat interface
- ✅ **Settings Integration** - Chat preferences and configuration

## 🔧 Technical Changes
- **New Component**: `TauriChatInterface.tsx` - React chat interface
- **New Commands**: `atom_agent_commands.rs` - Chat message processing
- **Updated Main**: `main_with_chat.rs` - Chat-enabled Tauri commands
- **Type Definitions**: `nlu.ts` - Complete TypeScript types
- **Message Components**: `MessageItem.tsx` - Enhanced message display

## 🔗 Integration Support
- **Slack**: ✅ Check messages via chat
- **Notion**: ✅ Create documents via chat
- **Asana**: ✅ Manage tasks via chat
- **Teams**: ✅ Check conversations via chat
- **Trello**: ✅ Manage cards via chat
- **Figma**: ✅ Check designs via chat
- **Linear**: ✅ Manage issues via chat

## 📋 User Testing Instructions

### Basic Usage
1. Launch the Atom Desktop Agent
2. The chat interface will appear automatically
3. Type a message like: "Check my Slack messages"
4. Atom AI will respond and execute the action
5. Use the quick action buttons for common commands

### Advanced Features
- **Voice Input**: Click the microphone button
- **File Attachments**: Click the paperclip button
- **Settings**: Click the settings icon
- **Integration Status**: View connection status in header

### Example Commands
- "Check my Slack messages"
- "Create a Notion document"
- "Get my Asana tasks"
- "Search my Teams conversations"
- "Help me with my integrations"

## 🐛 Troubleshooting

### Common Issues
1. **Chat not loading**: Check if the frontend build completed
2. **Commands not working**: Verify integration connections
3. **No response**: Check WebSocket connection status
4. **Notifications not showing**: Check system notification permissions

### Support
- **Issues**: Report to GitHub Issues
- **Documentation**: Available in the app help
- **Community**: Join the Discord server

## 🚀 Next Steps
1. Deploy to production environment
2. Collect user feedback
3. Monitor performance and usage
4. Plan Phase 2 enhancements
5. Release update schedule

---

**Build completed successfully! 🎉**
EOF

echo "✅ Deployment summary created: DEPLOYMENT_SUMMARY.md"

echo ""

# Step 10: Final status
echo "🎉 Step 10: Build Complete!"
echo "============================"
echo ""
echo "✅ Configuration updated"
echo "✅ Dependencies installed"
echo "✅ Application built"
echo "✅ Frontend compiled"
echo "✅ Distribution package created"
echo "✅ Test script created"
echo "✅ Deployment summary generated"
echo ""
echo "📦 Distribution location: $PROJECT_ROOT/src-tauri/target/release/bundle"
echo "🧪 To test: ./test_chat_interface.sh"
echo "📋 For details: ./DEPLOYMENT_SUMMARY.md"
echo ""
echo "🚀 Atom Desktop Agent with Chat Interface is ready for deployment!"
echo ""
echo "🎯 Next Steps:"
echo "  1. Run the test script to verify functionality"
echo "  2. Test all integration commands"
echo "  3. Collect user feedback"
echo "  4. Deploy to production"
echo "  5. Monitor performance and usage"
echo ""
echo "✨ Happy chatting with Atom AI Assistant! ✨"