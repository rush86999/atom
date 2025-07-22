#!/bin/bash

# Set the project root directory, which is the directory containing this script.
PROJECT_ROOT=$(pwd)

# The PYTHONPATH needs to contain the directory where the top-level 'project' package resides.
# In this project structure, the 'project' package is inside the 'atomic-docker' directory.
# Setting the PYTHONPATH to this directory allows Python to resolve imports like 'from project.functions...'.
export PYTHONPATH="${PROJECT_ROOT}/atomic-docker"

# Specify the absolute path to the Python interpreter in the correct conda environment.
# This avoids issues with shell activation (`conda activate`) and ensures the correct
# interpreter and its installed packages are used.
PYTHON_EXEC="/Users/rushiparikh/anaconda3/envs/learnPytorch/envs/atom-prod/bin/python"

# Verify that the specified Python executable exists before trying to use it.
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Python executable not found at $PYTHON_EXEC"
    echo "Please ensure the 'atom-prod' conda environment exists and is located correctly."
    exit 1
fi

echo "--- Running Atom Project Tests ---"
echo "Using Python interpreter: $PYTHON_EXEC"
echo "Setting PYTHONPATH to: $PYTHONPATH"
echo "------------------------------------"

# Execute the Python unit test discovery.
# The discover command starts its search in the specified directory ('atomic-docker')
# and looks for files matching the pattern ('test_*.py').
# We run this from the project root to ensure all paths are resolved correctly.
"$PYTHON_EXEC" -m unittest discover -s "${PROJECT_ROOT}/atomic-docker" -p "test_*.py"
