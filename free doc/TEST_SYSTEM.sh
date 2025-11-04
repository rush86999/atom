#!/bin/bash
echo "🧪 ATOM Platform - Quick Test"
echo "============================="
echo "Testing core functionality..."
echo ""
echo "1. Backend Health:"
curl -s http://localhost:5058/healthz | jq '.status'
echo ""
echo "2. Service Registry:"
curl -s http://localhost:5058/api/services | jq '.total_services'
echo ""
echo "3. Task Management:"
curl -s http://localhost:5058/api/tasks | jq '.success'
echo ""
echo "4. Frontend Access:"
curl -s -I http://localhost:3000 | head -1
echo ""
echo "✅ Quick test completed"
