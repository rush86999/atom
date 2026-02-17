#!/bin/bash
# Setup script for PII Redaction with Presidio
# This script downloads the spaCy English model required for Presidio

set -e

echo "Setting up PII Redaction with Presidio..."
echo ""

# Check if Python 3.11+ is available
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Error: Python 3.11+ required but not found"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version
echo ""

# Install Presidio dependencies
echo "Installing Presidio dependencies..."
$PYTHON_CMD -m pip install 'presidio-analyzer>=2.2.0' 'presidio-anonymizer>=2.2.0' 'spacy>=3.7.0'
echo ""

# Download spaCy English model
echo "Downloading spaCy English model (en_core_web_lg)..."
$PYTHON_CMD -m spacy download en_core_web_lg
echo ""

# Verify installation
echo "Verifying installation..."
$PYTHON_CMD -c "from presidio_analyzer import AnalyzerEngine; print('✓ Presidio Analyzer installed')"
$PYTHON_CMD -c "from presidio_anonymizer import AnonymizerEngine; print('✓ Presidio Anonymizer installed')"
$PYTHON_CMD -c "import spacy; print('✓ spaCy installed')"
$PYTHON_CMD -c "import en_core_web_lg; print('✓ en_core_web_lg model downloaded')"
echo ""

echo "Setup complete! PII Redaction is ready to use."
