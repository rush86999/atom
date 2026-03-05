#!/bin/bash
# Coverage script for Tauri desktop application using cargo-tarpaulin
#
# Requirements:
# - x86_64 architecture (tarpaulin limitation)
# - For ARM Macs, use Cross or run in CI/CD
#
# Phase 142: Coverage Enforcement
# - Local development runs without enforcement by default (FAIL_UNDER=0)
# - Use --enforce or --fail-under 80 to verify before pushing
# - CI/CD automatically enforces threshold (see .github/workflows/desktop-coverage.yml)
#
# Usage:
#   ./coverage.sh                    # Generate HTML coverage report (informational, no enforcement)
#   ./coverage.sh --html             # Generate HTML coverage report (explicit)
#   ./coverage.sh --stdout           # Output to terminal
#   ./coverage.sh --baseline         # Generate baseline report (Phase 140)
#   ./coverage.sh --enforce          # Enforce 80% threshold (same as --fail-under 80)
#   ./coverage.sh --fail-under 75    # Enforce custom threshold (75% in this example)
#   ./coverage.sh --help             # Show all options

set -e

# Coverage enforcement threshold
# Set to 0 for informational only (local development)
# Set to 80 for CI/CD enforcement
FAIL_UNDER=${FAIL_UNDER:-0}  # Default: no enforcement locally

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
        --fail-under)
            FAIL_UNDER="$2"
            shift 2
            ;;
        --enforce)
            FAIL_UNDER=80
            shift
            ;;
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
        -h|--help)
            echo "Usage: $0 [--fail-under N] [--enforce] [--html] [--stdout] [--baseline] [--baseline-breakdown]"
            echo ""
            echo "Coverage enforcement options:"
            echo "  --fail-under N      Enforce N% coverage threshold (default: 0, informational only)"
            echo "  --enforce           Enforce 80% threshold (same as --fail-under 80)"
            echo ""
            echo "Output format options:"
            echo "  --html              Generate HTML coverage report (default)"
            echo "  --stdout            Output to terminal only"
            echo ""
            echo "Baseline options:"
            echo "  --baseline          Generate baseline report (Phase 140, no fail enforcement)"
            echo "  --baseline-breakdown Generate baseline with per-file breakdown (Phase 141)"
            echo ""
            echo "Examples:"
            echo "  $0                          # Informational coverage (no enforcement)"
            echo "  $0 --enforce                # Enforce 80% threshold (verify before pushing)"
            echo "  $0 --fail-under 75          # Enforce 75% threshold (custom)"
            echo "  FAIL_UNDER=0 $0             # Explicit no enforcement (same as default)"
            echo ""
            echo "Phase 142 Notes:"
            echo "  - Local development runs without enforcement by default (FAIL_UNDER=0)"
            echo "  - CI/CD automatically enforces: PR 75%, main 80%"
            echo "  - Use --enforce locally to verify coverage before pushing"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help to see usage"
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

# Show enforcement status
if [ "$FAIL_UNDER" -gt 0 ]; then
    echo -e "${YELLOW}🚨 Coverage enforcement enabled: ${FAIL_UNDER}% threshold${NC}"
    echo -e "${YELLOW}   Build will fail if coverage is below ${FAIL_UNDER}%${NC}"
else
    echo -e "${GREEN}ℹ️  Coverage enforcement disabled (informational only)${NC}"
    echo -e "${GREEN}   Use --fail-under 80 or --enforce to enable enforcement${NC}"
fi
echo ""

# Build tarpaulin command
if [[ "$OUTPUT_FORMAT" == "Stdout" ]]; then
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --fail-under ${FAIL_UNDER} \
        --config tarpaulin.toml \
        --out Stdout
else
    cargo tarpaulin \
        --verbose \
        --timeout 300 \
        --fail-under ${FAIL_UNDER} \
        --config tarpaulin.toml \
        --out "$OUTPUT_FORMAT"
fi

# Capture tarpaulin exit code
TARP_RESULT=$?

if [[ $TARP_RESULT -eq 0 ]]; then
    echo -e "${GREEN}Coverage report generated successfully!${NC}"

    # Extract coverage percentage for display
    if [[ -f "$OUTPUT_DIR/coverage.json" ]]; then
        COVERAGE=$(node -e "
            const fs = require('fs');
            const data = JSON.parse(fs.readFileSync('${OUTPUT_DIR}/coverage.json', 'utf8'));
            console.log((data.coverage * 100).toFixed(2));
        " 2>/dev/null || echo "N/A")
        echo -e "${GREEN}✅ Coverage: ${COVERAGE}%${NC}"
    fi

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

    # Show enforcement success message
    if [ "$FAIL_UNDER" -gt 0 ]; then
        echo -e "${GREEN}✅ Coverage meets ${FAIL_UNDER}% threshold requirement${NC}"
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
    # Coverage generation failed
    echo -e "${RED}Coverage generation failed with exit code $TARP_RESULT${NC}"

    if [ "$FAIL_UNDER" -gt 0 ]; then
        # Try to extract coverage percentage even on failure
        if [[ -f "$OUTPUT_DIR/coverage.json" ]]; then
            COVERAGE=$(node -e "
                const fs = require('fs');
                const data = JSON.parse(fs.readFileSync('${OUTPUT_DIR}/coverage.json', 'utf8'));
                console.log((data.coverage * 100).toFixed(2));
            " 2>/dev/null || echo "N/A")

            if [[ "$COVERAGE" != "N/A" ]]; then
                echo -e "${RED}❌ Coverage ${COVERAGE}% is below ${FAIL_UNDER}% threshold${NC}"
                echo -e "${YELLOW}   Add tests to increase coverage or adjust threshold with --fail-under${NC}"
            fi
        fi
    fi

    exit $TARP_RESULT
fi
