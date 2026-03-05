#!/bin/bash
# Coverage script for Tauri desktop application using cargo-tarpaulin
#
# Requirements:
# - x86_64 architecture (tarpaulin limitation)
# - For ARM Macs, use Cross or run in CI/CD
#
# Usage:
#   ./coverage.sh                    # Generate HTML coverage report (default)
#   ./coverage.sh --html             # Generate HTML coverage report (explicit)
#   ./coverage.sh --stdout           # Output to terminal
#   ./coverage.sh --baseline         # Generate baseline report (Phase 140)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect architecture
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo -e "${YELLOW}Warning: ARM architecture detected. cargo-tarpaulin requires x86_64.${NC}"
    echo -e "${YELLOW}Please use Cross or run this script in CI/CD (x86_64 runner).${NC}"
    echo -e "${YELLOW}See: https://github.com/rust-embedded/cross${NC}"
    exit 1
fi

# Default output format (changed to HTML for Phase 140 baseline)
OUTPUT_FORMAT="Html"
OUTPUT_DIR="coverage-report"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --html)
            OUTPUT_FORMAT="Html"
            shift
            ;;
        --stdout)
            OUTPUT_FORMAT="Stdout"
            OUTPUT_DIR=""
            shift
            ;;
        --baseline)
            # Phase 140: Baseline measurement with --fail-under 0
            OUTPUT_FORMAT="Html"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--html|--stdout|--baseline]"
            echo "  --html     Generate HTML coverage report (default)"
            echo "  --stdout   Output to terminal only"
            echo "  --baseline Generate baseline report (Phase 140, no fail enforcement)"
            exit 1
            ;;
    esac
done

# Create output directory if needed
if [[ -n "$OUTPUT_DIR" ]]; then
    mkdir -p "$OUTPUT_DIR"
fi

echo -e "${GREEN}Running cargo-tarpaulin for desktop coverage...${NC}"
echo "Architecture: $ARCH"
echo "Output format: $OUTPUT_FORMAT"
echo "Configuration: tarpaulin.toml"

# Build tarpaulin command
if [[ "$OUTPUT_FORMAT" == "Stdout" ]]; then
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --config tarpaulin.toml \
        --out Stdout
else
    # Phase 140: Use --fail-under 0 for baseline measurement (no enforcement)
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --fail-under 0 \
        --config tarpaulin.toml \
        --out "$OUTPUT_FORMAT"
fi

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}Coverage report generated successfully!${NC}"
    if [[ -f "$OUTPUT_DIR/index.html" ]]; then
        echo "HTML Report: $OUTPUT_DIR/index.html"
        echo "Open in browser: file://$(pwd)/$OUTPUT_DIR/index.html"
    fi
    if [[ -f "$OUTPUT_DIR/coverage.json" ]]; then
        echo "JSON Report: $OUTPUT_DIR/coverage.json"
    fi
    if [[ -f "$OUTPUT_DIR/cobertura.xml" ]]; then
        echo "Cobertura Report: $OUTPUT_DIR/cobertura.xml"
    fi
else
    echo -e "${RED}Coverage generation failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi
