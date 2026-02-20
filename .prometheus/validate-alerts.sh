#!/bin/bash

# Validate Prometheus Alerting Rules
# Usage: .prometheus/validate-alerts.sh

echo "=== Validating Prometheus alerting rules ==="

# Check if promtool is installed
if ! command -v promtool &> /dev/null; then
  echo "❌ promtool not found. Install Prometheus CLI:"
  echo "   macOS: brew install prometheus"
  echo "   Linux: wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz"
  exit 1
fi

# Validate rules syntax
echo "Step 1: Validating rules syntax..."
promtool check rules .prometheus/alerts.yml

if [ $? -eq 0 ]; then
  echo "✅ Prometheus alerting rules are valid"
else
  echo "❌ Prometheus alerting rules have syntax errors"
  exit 1
fi

# Check rule count
ALERT_COUNT=$(grep -c "alert:" .prometheus/alerts.yml)
echo ""
echo "Step 2: Counting configured alerts..."
echo "Total alerts configured: $ALERT_COUNT"

# List all alerts
echo ""
echo "Step 3: Listing configured alerts..."
echo "=== Configured Alerts ==="
grep "alert:" .prometheus/alerts.yml | sed 's/.*alert: //' | sed 's/ .*//' | sort

echo ""
echo "✅ Validation complete!"
