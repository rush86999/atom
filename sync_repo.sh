#!/bin/bash

# Navigate to the repository directory
# Replace /path/to/repo with the actual path to your repository
cd /path/to/repo

# Check if the directory is a Git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Syncing repository..."

    # Fetch the latest changes from the remote
    git fetch origin

    # Push your local changes to the remote
    git push origin

    echo "Repository synced successfully."
else
    echo "Error: This is not a Git repository."
fi
