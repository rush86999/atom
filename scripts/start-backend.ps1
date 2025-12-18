# ATOM Backend Startup Script - SIMPLIFIED
# This script safely starts the Python/FastAPI backend

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ATOM Backend Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  X Python not found! Please install Python 3.8+" -ForegroundColor Red
    exit 1
}
Write-Host "  OK Found: $pythonVersion" -ForegroundColor Green

# Navigate to backend directory
Write-Host ""
Write-Host "[2/4] Navigating to backend directory..." -ForegroundColor Yellow
Set-Location -Path "$PSScriptRoot\backend"
Write-Host "  OK Current directory: $(Get-Location)" -ForegroundColor Green

# Check if virtual environment exists
Write-Host ""
Write-Host "[3/4] Checking Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    Write-Host "  INFO Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "  OK Virtual environment created" -ForegroundColor Green
    
    Write-Host "  INFO Installing dependencies..." -ForegroundColor Cyan
    .\venv\Scripts\pip.exe install -r requirements.txt --quiet
    Write-Host "  OK Dependencies installed" -ForegroundColor Green
}
else {
    Write-Host "  OK Virtual environment exists" -ForegroundColor Green
}

# Start the server
Write-Host ""
Write-Host "[4/4] Starting FastAPI server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Backend is starting!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API Documentation: http://localhost:5059/docs" -ForegroundColor Cyan
Write-Host "  Health Check:      http://localhost:5059/health" -ForegroundColor Cyan
Write-Host "  API Root:          http://localhost:5059/" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run the server with reload for development
.\venv\Scripts\uvicorn.exe main_api_app:app --host 0.0.0.0 --port 5059 --reload
