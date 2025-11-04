#!/bin/bash

# ATOM Platform - Real-time Monitoring Dashboard
echo "🚀 ATOM PLATFORM - REAL-TIME STATUS"
echo "===================================="
echo "Last updated: $(date)"
echo ""

# Service Status
echo "🔧 SERVICE STATUS:"
services=(
    "OAuth Server|http://localhost:5058/healthz"
    "Backend API|http://localhost:8000/health"
    "Frontend App|http://localhost:3000"
    "NLU System|http://localhost:8000/api/workflow-agent/analyze"
    "Workflow Gen|http://localhost:8000/api/workflow-automation/generate"
)

for service in "${services[@]}"; do
    IFS='|' read -r name url <<< "$service"

    if [[ $url == *"workflow-agent"* ]] || [[ $url == *"workflow-automation"* ]]; then
        # POST endpoints
        response=$(curl -s -X POST "$url" -H "Content-Type: application/json" -d '{"user_input":"test","user_id":"monitor"}' --max-time 5 2>/dev/null || echo "ERROR")
    else
        # GET endpoints
        response=$(curl -s "$url" --max-time 5 2>/dev/null || echo "ERROR")
    fi

    if [[ "$response" == "ERROR" ]]; then
        status="❌ OFFLINE"
    elif [[ "$response" == *"status"* ]] && [[ "$response" == *"ok"* ]]; then
        status="✅ HEALTHY"
    elif [[ "$response" == *"success"* ]] && [[ "$response" == *"true"* ]]; then
        status="✅ WORKING"
    elif [[ "$response" == *"200"* ]] || [[ "$response" == *"<!DOCTYPE"* ]]; then
        status="✅ RUNNING"
    else
        status="⚠️  ISSUES"
    fi

    echo "   $status $name"
done

echo ""
echo "🌐 ACCESS POINTS:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   OAuth Server: http://localhost:5058"
echo ""

echo "🔍 CRITICAL ENDPOINTS:"
critical_endpoints=(
    "/search"
    "/tasks"
    "/communication"
    "/automations"
    "/calendar"
)

for endpoint in "${critical_endpoints[@]}"; do
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000$endpoint" --max-time 3 2>/dev/null || echo "000")
    if [[ "$status_code" == "200" ]]; then
        echo "   ✅ $endpoint: HTTP $status_code"
    else
        echo "   ❌ $endpoint: HTTP $status_code"
    fi
done

echo ""
echo "💡 QUICK ACTIONS:"
echo "   Test NLU: curl -X POST http://localhost:8000/api/workflow-agent/analyze -H 'Content-Type: application/json' -d '{"user_input":"test","user_id":"test"}'"
echo "   Test Workflow: curl -X POST http://localhost:8000/api/workflow-automation/generate -H 'Content-Type: application/json' -d '{"user_input":"Schedule meeting","user_id":"test"}'"
echo "   Check Services: curl http://localhost:8000/api/services/status"
