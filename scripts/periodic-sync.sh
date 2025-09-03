#!/bin/bash

# Periodic Git Sync Script for Atom Project
# This script automatically syncs with remote repository periodically

# Configuration
SYNC_INTERVAL=300  # 5 minutes in seconds
MAX_RETRIES=3
RETRY_DELAY=30
LOG_FILE="/tmp/atom-sync.log"
BRANCH="main"
REMOTE="origin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log function
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        "INFO") color=$BLUE ;;
        "SUCCESS") color=$GREEN ;;
        "WARNING") color=$YELLOW ;;
        "ERROR") color=$RED ;;
        *) color=$NC ;;
    esac

    echo -e "${color}[$timestamp] $level: $message${NC}"
    echo "[$timestamp] $level: $message" >> "$LOG_FILE"
}

# Check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log "ERROR" "Not in a git repository"
        exit 1
    fi
}

# Check for uncommitted changes
has_uncommitted_changes() {
    if ! git diff --quiet --exit-code; then
        return 0  # Has changes
    fi
    if ! git diff --cached --quiet --exit-code; then
        return 0  # Has staged changes
    fi
    return 1  # No changes
}

# Backup current changes
backup_changes() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_dir="/tmp/atom_backups"
    local backup_file="$backup_dir/changes_$timestamp.patch"

    mkdir -p "$backup_dir"
    git diff > "$backup_file"
    git diff --cached >> "$backup_file" 2>/dev/null

    if [ -s "$backup_file" ]; then
        log "INFO" "Backed up changes to $backup_file"
    else
        rm -f "$backup_file"
    fi
}

# Stash changes temporarily
stash_changes() {
    if has_uncommitted_changes; then
        log "INFO" "Stashing local changes"
        git stash push -m "Auto-stash for sync $(date '+%Y-%m-%d %H:%M:%S')"
        return $?
    fi
    return 0
}

# Restore stashed changes
restore_changes() {
    if git stash list | grep -q "Auto-stash for sync"; then
        log "INFO" "Restoring stashed changes"
        git stash pop
        return $?
    fi
    return 0
}

# Pull latest changes from remote
pull_changes() {
    local retry_count=0
    local success=0

    while [ $retry_count -lt $MAX_RETRIES ]; do
        log "INFO" "Pulling changes from $REMOTE/$BRANCH (attempt $((retry_count+1))/$MAX_RETRIES)"

        if git pull --rebase $REMOTE $BRANCH; then
            success=1
            break
        fi

        retry_count=$((retry_count+1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            log "WARNING" "Pull failed, retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    done

    if [ $success -eq 1 ]; then
        log "SUCCESS" "Successfully pulled changes from $REMOTE/$BRANCH"
        return 0
    else
        log "ERROR" "Failed to pull changes after $MAX_RETRIES attempts"
        return 1
    fi
}

# Push local changes to remote
push_changes() {
    local retry_count=0
    local success=0

    while [ $retry_count -lt $MAX_RETRIES ]; do
        log "INFO" "Pushing changes to $REMOTE/$BRANCH (attempt $((retry_count+1))/$MAX_RETRIES)"

        if git push $REMOTE $BRANCH; then
            success=1
            break
        fi

        retry_count=$((retry_count+1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            log "WARNING" "Push failed, retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    done

    if [ $success -eq 1 ]; then
        log "SUCCESS" "Successfully pushed changes to $REMOTE/$BRANCH"
        return 0
    else
        log "ERROR" "Failed to push changes after $MAX_RETRIES attempts"
        return 1
    fi
}

# Check if remote has changes
remote_has_changes() {
    git fetch $REMOTE
    local local_commit=$(git rev-parse $BRANCH)
    local remote_commit=$(git rev-parse $REMOTE/$BRANCH)

    if [ "$local_commit" != "$remote_commit" ]; then
        return 0  # Remote has changes
    fi
    return 1  # No remote changes
}

# Main sync function
sync_repository() {
    log "INFO" "Starting synchronization process"
    check_git_repo

    local has_remote_changes=0
    local has_local_changes=0

    # Check for remote changes
    if remote_has_changes; then
        has_remote_changes=1
        log "INFO" "Remote repository has new changes"
    fi

    # Check for local changes
    if has_uncommitted_changes; then
        has_local_changes=1
        log "INFO" "Local repository has uncommitted changes"
    fi

    # Handle different scenarios
    if [ $has_remote_changes -eq 1 ] && [ $has_local_changes -eq 1 ]; then
        log "WARNING" "Both remote and local have changes - attempting to merge"
        backup_changes
        stash_changes
        if pull_changes; then
            restore_changes
            # Try to commit and push if changes are restored successfully
            if has_uncommitted_changes; then
                git add .
                git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')" --no-verify
                push_changes
            fi
        else
            restore_changes
        fi

    elif [ $has_remote_changes -eq 1 ]; then
        log "INFO" "Only remote has changes - pulling"
        pull_changes

    elif [ $has_local_changes -eq 1 ]; then
        log "INFO" "Only local has changes - committing and pushing"
        git add .
        git commit -m "Auto-commit: $(date '+%Y-%m-%d %H:%M:%S')" --no-verify
        push_changes

    else
        log "INFO" "No changes to sync"
    fi

    log "SUCCESS" "Synchronization completed"
}

# Continuous sync mode
continuous_sync() {
    log "INFO" "Starting continuous sync mode (interval: ${SYNC_INTERVAL}s)"
    while true; do
        sync_repository
        log "INFO" "Next sync in $SYNC_INTERVAL seconds..."
        sleep $SYNC_INTERVAL
    done
}

# One-time sync mode
one_time_sync() {
    log "INFO" "Performing one-time sync"
    sync_repository
}

# Show help
show_help() {
    echo "Usage: $0 [OPTION]"
    echo "Periodically sync Atom repository with remote"
    echo ""
    echo "Options:"
    echo "  -c, --continuous   Run in continuous mode (default)"
    echo "  -o, --once         Run one-time sync"
    echo "  -i, --interval N   Set sync interval in seconds (default: 300)"
    echo "  -h, --help         Show this help message"
    echo "  -l, --log          Show log file"
    echo ""
    echo "Examples:"
    echo "  $0 -c              Run continuous sync every 5 minutes"
    echo "  $0 -o              Run one-time sync"
    echo "  $0 -i 60           Run continuous sync every 60 seconds"
}

# Parse command line arguments
parse_args() {
    local mode="continuous"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--continuous)
                mode="continuous"
                shift
                ;;
            -o|--once)
                mode="once"
                shift
                ;;
            -i|--interval)
                if [[ $2 =~ ^[0-9]+$ ]]; then
                    SYNC_INTERVAL=$2
                    shift 2
                else
                    log "ERROR" "Interval must be a number"
                    exit 1
                fi
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -l|--log)
                if [ -f "$LOG_FILE" ]; then
                    cat "$LOG_FILE"
                else
                    echo "Log file not found: $LOG_FILE"
                fi
                exit 0
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    case $mode in
        "continuous") continuous_sync ;;
        "once") one_time_sync ;;
    esac
}

# Main execution
main() {
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"

    # Parse command line arguments
    parse_args "$@"
}

# Run main function with all arguments
main "$@"
