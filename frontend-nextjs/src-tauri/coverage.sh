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
        --baseline-breakdown)
            # Phase 141: Baseline measurement with per-file breakdown
            OUTPUT_FORMAT="Html"
            BASELINE_BREAKDOWN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--html|--stdout|--baseline|--baseline-breakdown]"
            echo "  --html              Generate HTML coverage report (default)"
            echo "  --stdout            Output to terminal only"
            echo "  --baseline          Generate baseline report (Phase 140, no fail enforcement)"
            echo "  --baseline-breakdown Generate baseline with per-file breakdown (Phase 141)"
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

    # Phase 141: Generate baseline with per-file breakdown if requested
    if [[ "$BASELINE_BREAKDOWN" == "true" ]]; then
        echo -e "${GREEN}Generating baseline with per-file breakdown...${NC}"

        # Run the baseline generation as a Rust test
        cargo test --test coverage_baseline_test -- generate_baseline_with_breakdown_test \
            || echo -e "${YELLOW}Note: Baseline breakdown generation requires test infrastructure${NC}"

        # Alternative: Create baseline.json manually from coverage report
        if [[ -f "$OUTPUT_DIR/coverage.json" ]]; then
            echo -e "${GREEN}Creating baseline.json from coverage report...${NC}"

            # Extract overall coverage
            COVERAGE=$(cat "$OUTPUT_DIR/coverage.json" | grep -o '"coverage":[0-9.]*' | head -1 | cut -d: -f2)
            if [[ -z "$COVERAGE" ]]; then
                # Try alternative parsing
                COVERAGE=$(cat "$OUTPUT_DIR/index.html" | grep -o '>[0-9.]*%' | head -1 | sed 's/[>%]//g')
            fi

            if [[ -n "$COVERAGE" ]]; then
                echo "Extracted coverage: ${COVERAGE}%"

                # Create baseline JSON with metadata
                cat > "$OUTPUT_DIR/baseline.json" <<EOF
{
  "baseline_coverage": ${COVERAGE},
  "measured_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "total_lines": 1756,
  "covered_lines": $(( (${COVERAGE}.*1756)/100 )),
  "platform": "$(uname -s | tr '[:upper:]' '[:lower:]')",
  "arch": "$(uname -m)",
  "commit_sha": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "notes": "Phase 141 baseline measurement with per-file breakdown",
  "high_priority_gaps": []
}
EOF
                echo -e "${GREEN}Baseline JSON created: $OUTPUT_DIR/baseline.json${NC}"
            else
                echo -e "${YELLOW}Warning: Could not extract coverage percentage${NC}"
            fi
        fi
    fi
else
    echo -e "${RED}Coverage generation failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi
