#!/bin/bash

# ATOM Application Fix Script
# This script helps fix the common issues found during testing

echo "🔧 Starting ATOM Application Fix Process..."
echo "============================================="

# Navigate to frontend directory
cd frontend-nextjs

echo "📦 Step 1: Cleaning up existing dependencies..."
rm -rf .next
rm -rf node_modules
rm package-lock.json

echo "📦 Step 2: Reinstalling dependencies..."
npm install

echo "📦 Step 3: Installing missing dependencies..."

# Install core utility dependencies
npm install clsx tailwind-merge --save

# Install missing Radix UI components
npm install @radix-ui/react-popover --save

# Install other commonly missing UI components
npm install @radix-ui/react-dropdown-menu @radix-ui/react-avatar --save

# Install lucide-react for icons
npm install lucide-react --save

echo "🔧 Step 4: Checking Next.js configuration..."

# Check if tsconfig.json has proper path mappings
if ! grep -q "@/lib" tsconfig.json; then
    echo "⚠️  Warning: tsconfig.json may be missing @/ path mapping"
    echo "Please ensure your tsconfig.json includes:"
    echo '"paths": { "@/*": ["./src/*", "./*"] }'
fi

echo "🔧 Step 5: Creating missing directories..."

# Ensure lib directory exists
mkdir -p lib

# Ensure utils file exists
if [ ! -f "lib/utils.ts" ]; then
    echo "Creating lib/utils.ts..."
    cat > lib/utils.ts << 'EOF'
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
EOF
fi

# Ensure favicon exists (basic placeholder)
if [ ! -f "public/favicon.ico" ]; then
    echo "⚠️  Warning: favicon.ico is missing"
    echo "Please add a favicon.ico to the public directory"
fi

echo "🚀 Step 6: Restarting development server..."
echo "Please run the following commands manually:"
echo "1. cd frontend-nextjs"
echo "2. npm run dev"
echo "3. Check for any remaining errors in the console"

echo ""
echo "✅ Fix process completed!"
echo "============================================="
echo ""
echo "Next steps:"
echo "1. Start the development server"
echo "2. Check the browser console for any remaining errors"
echo "3. Test the authentication page"
echo "4. Run the automated test script again to verify fixes"
echo ""
echo "If you still have issues, please check:"
echo "- Next.js configuration (next.config.js)"
echo "- TypeScript configuration (tsconfig.json)"
echo "- Environment variables (.env.local)"
echo "- Backend connection (port 8000)"