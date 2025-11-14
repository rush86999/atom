#!/bin/bash

# Performance Optimization Script for ATOM

echo "🚀 ATOM Performance Optimization Suite"
echo "===================================="

# Clean dependencies
echo "📦 Cleaning dependencies..."
rm -rf node_modules package-lock.json
npm install --production=false

# Bundle analyzer setup
echo "📊 Setting up bundle analyzer..."
npm install --save-dev @next/bundle-analyzer

# Lighthouse CI setup
echo "🔍 Setting up Lighthouse CI..."
npm install --save-dev @lhci/cli

# Performance monitoring
echo "📈 Setting up performance monitoring..."
npm install --save-dev web-vitals

echo "✅ Performance optimization tools installed"
echo "Run 'npm run analyze' for bundle analysis"
echo "Run 'npm run lighthouse' for performance audit"