#!/bin/bash
# Coverage script for Tauri desktop application using cargo-tarpaulin
#
# Requirements:
# - x86_64 architecture (tarpaulin limitation)
# - For ARM Macs, use Cross or run in CI/CD
#
# Usage:
#   ./coverage.sh                    # Generate JSON coverage report
#   ./coverage.sh --html             # Generate HTML coverage report
#   ./coverage.sh --stdout           # Output to terminal

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

# Default output format
OUTPUT_FORMAT="Json"
OUTPUT_DIR="coverage"

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
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--html|--stdout]"
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

# Build tarpaulin command
if [[ "$OUTPUT_FORMAT" == "Stdout" ]]; then
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --exclude-files='tests/*' \
        --output-dir "$OUTPUT_DIR" \
        --out Stdout
else
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --exclude-files='tests/*' \
        --output-dir "$OUTPUT_DIR" \
        --out "$OUTPUT_FORMAT"
fi

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}Coverage report generated successfully!${NC}"
    if [[ -f "$OUTPUT_DIR/coverage.json" ]]; then
        echo "Report: $OUTPUT_DIR/coverage.json"
    fi
else
    echo -e "${RED}Coverage generation failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi
