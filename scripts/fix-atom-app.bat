@echo off
REM ATOM Application Fix Script for Windows
REM This script helps fix the common issues found during testing

echo 🔧 Starting ATOM Application Fix Process...
echo =============================================

REM Navigate to frontend directory
cd frontend-nextjs

echo 📦 Step 1: Cleaning up existing dependencies...
if exist .next rmdir /s /q .next
if exist node_modules rmdir /s /q node_modules
if exist package-lock.json del package-lock.json

echo 📦 Step 2: Reinstalling dependencies...
call npm install

echo 📦 Step 3: Installing missing dependencies...

REM Install core utility dependencies
call npm install clsx tailwind-merge --save

REM Install missing Radix UI components
call npm install @radix-ui/react-popover --save

REM Install other commonly missing UI components
call npm install @radix-ui/react-dropdown-menu @radix-ui/react-avatar --save

REM Install lucide-react for icons
call npm install lucide-react --save

echo 🔧 Step 4: Checking Next.js configuration...
echo Checking tsconfig.json for path mappings...
findstr /C:"@/lib" tsconfig.json >nul
if %errorlevel% neq 0 (
    echo ⚠️  Warning: tsconfig.json may be missing @/ path mapping
    echo Please ensure your tsconfig.json includes:
    echo "paths": { "@/*": ["./src/*", "./*"] }
)

echo 🔧 Step 5: Creating missing directories...

REM Ensure lib directory exists
if not exist lib mkdir lib

REM Ensure utils file exists
if not exist lib\utils.ts (
    echo Creating lib\utils.ts...
    (
        echo import { type ClassValue, clsx } from "clsx"
        echo import { twMerge } from "tailwind-merge"
        echo.
        echo export function cn^(...inputs: ClassValue[]^) {
        echo   return twMerge^(clsx^(inputs^)^)
        echo }
    ) > lib\utils.ts
)

REM Check if favicon exists
if not exist public\favicon.ico (
    echo ⚠️  Warning: favicon.ico is missing
    echo Please add a favicon.ico to the public directory
)

echo.
echo ✅ Fix process completed!
echo =============================================
echo.
echo Next steps:
echo 1. cd frontend-nextjs
echo 2. npm run dev
echo 3. Check for any remaining errors in the console
echo.
echo If you still have issues, please check:
echo - Next.js configuration (next.config.js)
echo - TypeScript configuration (tsconfig.json)
echo - Environment variables (.env.local)
echo - Backend connection (port 5059)

pause