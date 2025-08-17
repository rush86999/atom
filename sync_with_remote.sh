#!/bin/bash

# Comprehensive repository sync and PR merge script
# This script handles syncing with remote repo and merging PRs

set -e  # Exit on any error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ATOM REPOSITORY SYNC & PR MANAGER${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if git is available
if ! command -v git &> /dev/null; then
    print_error "Git is not installed"
    exit 1
fi

# Check if we're in a git repository
if [ ! -d .git ]; then
    print_error "Not in a git repository"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
print_status "Currently on branch: $CURRENT_BRANCH"

# Fetch latest changes from all remotes
print_status "Fetching latest changes from remote..."
git fetch --all --prune

# Show current status
echo ""
echo -e "${BLUE}--- CURRENT STATUS ---${NC}"
git status --short | head -20
echo ""

# Function to show available PR branches
show_available_branches() {
    echo -e "${BLUE}--- AVAILABLE REMOTE BRANCHES ---${NC}"
    local branches=$(git branch -r | grep -v 'HEAD' | grep -v 'main' | sed 's/origin\///' | sort)

    if [ -z "$branches" ]; then
        print_warning "No remote branches found (excluding main)"
        return
    fi

    echo "$branches" | nl
    echo ""
}

# Function to merge a specific branch
merge_branch() {
    local branch_name=$1
    local merge_message=$2

    print_status "Merging origin/$branch_name into $CURRENT_BRANCH..."

    # Check if branch exists
    if ! git ls-remote --heads origin "$branch_name" | grep "$branch_name" >/dev/null; then
        print_error "Branch '$branch_name' not found on origin"
        return 1
    fi

    # Create merge commit
    git merge "origin/$branch_name" -m "$merge_message" --no-ff

    if [ $? -eq 0 ]; then
        print_status "Successfully merged $branch_name"
    else
        print_error "Failed to merge $branch_name"
        return 1
    fi
}

# Function to handle interactive branch selection
interactive_merge() {
    local branches=$(git branch -r | grep -v 'HEAD' | grep -v 'main' | sed 's/origin\///')

    if [ -z "$branches" ]; then
        print_warning "No branches available for merging"
        return
    fi

    echo -e "${BLUE}Available branches to merge:${NC}"
    printf "%s\n" $branches | nl

    read -p "Enter branch numbers to merge (space-separated), or 'all': " selection

    if [ "$selection" = "all" ]; then
        printf "%s\n" $branches | while read -r branch; do
            merge_branch "$branch" "Merge $branch into $CURRENT_BRANCH"
        done
    else
        for num in $selection; do
            local branch=$(printf "%s\n" $branches | sed -n "${num}p")
            if [ -n "$branch" ]; then
                merge_branch "$branch" "Merge $branch into $CURRENT_BRANCH"
            else
                print_error "Invalid branch number: $num"
            fi
        done
    fi
}

# Function to sync with main
sync_with_main() {
    print_status "Syncing with main branch..."

    # Switch to main
    git checkout main
    git pull origin main

    # Switch back to current branch and rebase
    git checkout "$CURRENT_BRANCH"
    git rebase main

    print_status "Successfully synced with main"
}

# Function to push local changes
push_changes() {
print_status "Pushing local changes to origin..."

# Push current branch
git push origin "$CURRENT_BRANCH"

if [ $? -eq 0 ]; then
    print_status "Changes pushed successfully"
else
    print_error "Failed to push changes"
    return 1
fi
}

# Main menu
echo ""
echo -e "${BLUE}--- SYNCHRONIZATION OPTIONS ---${NC}"
echo "1. Sync with main branch (rebase current branch on main)"
echo "2. Show available PR branches to merge"
echo "3. Interactive branch merging (select branches to merge)"
echo "4. Push local changes to remote"
echo "5. Full sync (fetch, merge main, push)"
echo "6. Exit"

read -p "Choose an option [1-6]: " choice

case $choice in
1)
    sync_with_main
    ;;
2)
    show_available_branches
    ;;
3)
    interactive_merge
    ;;
4)
    push_changes
    ;;
5)
    sync_with_main
    echo ""
    push_changes
    ;;
6)
    print_status "Exiting..."
    exit 0
    ;;
*)
    print_error "Invalid option"
    echo "Usage: ./sync_with_remote.sh"
    echo ""
    echo "Available options:"
    echo "1-6 - Interactive menu"
    echo ""
esac

print_status "Synchronization complete!"
