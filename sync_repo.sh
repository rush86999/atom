#!/bin/bash

# Navigate to the repository directory
# Replace /path/to/repo with the actual path to your repository
cd /path/to/repo

# Check if the directory is a Git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Checking repository sync status..."

    # Fetch the latest changes from the remote
    git fetch origin

    # Check if the local branch is up-to-date with the remote branch
    if git diff --quiet origin/main; then
        echo "Repository is synced."
    else
        echo "Repository is not synced. Pushing local changes..."

        # Push your local changes to the remote
        git push origin

        echo "Repository synced successfully."
    fi
else
    echo "Error: This is not a Git repository."
fi
