#!/bin/bash

# ATOM Platform - Comprehensive Monitoring Script
echo "🔍 ATOM Platform Status Monitor"
echo "================================"
echo "Timestamp: $(date)"
echo ""

# System Health Checks
echo "🏥 SYSTEM HEALTH:"
services=(
    "Frontend:http://localhost:3000"
    "Backend API:http://localhost:8001"
    "OAuth Server:http://localhost:5058"
    "API Docs:http://localhost:8001/docs"
)

for service in "${services[@]}"; do
    IFS=':' read -r name url <<< "$service"
    if curl -s --head "$url" > /dev/null; then
        echo "   ✅ $name: HEALTHY ($url)"
    else
        echo "   ❌ $name: UNHEALTHY ($url)"
    fi
done

echo ""
echo "📊 INTEGRATION STATUS:"
integration_status=$(curl -s http://localhost:8001/api/integrations/status)
if [ $? -eq 0 ]; then
    total=$(echo "$integration_status" | grep -o '"total_integrations":[0-9]*' | cut -d: -f2)
    available=$(echo "$integration_status" | grep -o '"available_integrations":[0-9]*' | cut -d: -f2)
    success_rate=$(echo "$integration_status" | grep -o '"success_rate":"[^"]*"' | cut -d: -f2 | tr -d '"')
    echo "   ✅ Integrations: $available/$total available ($success_rate)"
else
    echo "   ❌ Failed to fetch integration status"
fi

echo ""
echo "🎯 QUICK ACTIONS:"
echo "   Frontend:    http://localhost:3000"
echo "   API Docs:    http://localhost:8001/docs"
echo "   System Info: http://localhost:8001/api/system/status"
echo "   OAuth Status: http://localhost:5058/healthz"
echo ""
echo "💡 TIPS:"
echo "   - Use 'docker-compose logs -f' to view all logs"
echo "   - Check 'PRODUCTION_DEPLOYMENT_GUIDE.md' for troubleshooting"
echo "   - Monitor integration status regularly"
