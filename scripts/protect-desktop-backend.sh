#!/bin/bash

# Desktop Backend Protection Script
# Prevents accidental deletion of critical desktop backend files

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_BACKEND_DIR="$PROJECT_ROOT/src-tauri"
PROTECTION_LOG="$PROJECT_ROOT/logs/desktop-backend-protection.log"

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$PROTECTION_LOG")"

# Function to log protection events
log_protection() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$PROTECTION_LOG"
}

# Function to check if a path is protected
is_protected_path() {
    local path="$1"

    # Critical desktop backend directories
    local protected_dirs=(
        "$DESKTOP_BACKEND_DIR"
        "$DESKTOP_BACKEND_DIR/src"
        "$DESKTOP_BACKEND_DIR/icons"
        "$PROJECT_ROOT/src/ui-shared/desktop"
        "$PROJECT_ROOT/frontend-nextjs"
    )

    # Critical desktop backend files
    local protected_files=(
        "$DESKTOP_BACKEND_DIR/Cargo.toml"
        "$DESKTOP_BACKEND_DIR/tauri.conf.json"
        "$DESKTOP_BACKEND_DIR/build.rs"
        "$DESKTOP_BACKEND_DIR/src/main.rs"
        "$PROJECT_ROOT/scripts/start_desktop.sh"
        "$PROJECT_ROOT/DESKTOP_APP_README.md"
        "$PROJECT_ROOT/DESKTOP_APP_CONSOLIDATION.md"
    )

    # Check if path matches any protected directory
    for dir in "${protected_dirs[@]}"; do
        if [[ "$path" == "$dir"* ]]; then
            return 0
        fi
    done

    # Check if path matches any protected file
    for file in "${protected_files[@]}"; do
        if [[ "$path" == "$file" ]]; then
            return 0
        fi
    done

    return 1
}

# Function to create backup before any operation
create_backup() {
    local operation="$1"
    local paths=("${@:2}")

    local backup_dir="$PROJECT_ROOT/backups/desktop-backend/$(date '+%Y%m%d_%H%M%S')_$operation"
    mkdir -p "$backup_dir"

    for path in "${paths[@]}"; do
        if [ -e "$path" ]; then
            if [ -f "$path" ]; then
                cp "$path" "$backup_dir/"
                log_protection "BACKUP: Copied file $path to $backup_dir"
            elif [ -d "$path" ]; then
                cp -r "$path" "$backup_dir/"
                log_protection "BACKUP: Copied directory $path to $backup_dir"
            fi
        fi
    done

    echo "$backup_dir"
}

# Function to validate deletion operations
validate_deletion() {
    local paths=("$@")
    local blocked_paths=()
    local allowed_paths=()

    for path in "${paths[@]}"; do
        if is_protected_path "$path"; then
            blocked_paths+=("$path")
            log_protection "BLOCKED: Attempted to delete protected path: $path"
        else
            allowed_paths+=("$path")
        fi
    done

    if [ ${#blocked_paths[@]} -gt 0 ]; then
        echo "ERROR: Cannot delete protected paths:"
        printf '  %s\n' "${blocked_paths[@]}"
        echo "Use --force to override protection (not recommended)"
        return 1
    fi

    return 0
}

# Function to handle forced operations (with extreme caution)
handle_forced_operation() {
    local operation="$1"
    local paths=("${@:2}")

    echo "⚠️  WARNING: FORCE MODE ENABLED"
    echo "   This will bypass all protection safeguards!"
    echo "   Protected paths that will be affected:"

    for path in "${paths[@]}"; do
        if is_protected_path "$path"; then
            echo "   - $path"
        fi
    done

    read -p "   Are you absolutely sure? (yes/NO): " confirmation
    if [[ "$confirmation" != "yes" ]]; then
        echo "Operation cancelled"
        exit 1
    fi

    # Create backup even in force mode
    local backup_dir=$(create_backup "force_$operation" "${paths[@]}")
    echo "   Backup created at: $backup_dir"

    return 0
}

# Main function
main() {
    local operation=""
    local paths=()
    local force=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --delete|--move|--rename)
                operation="${1#--}"
                shift
                ;;
            --force)
                force=true
                shift
                ;;
            -*)
                echo "Unknown option: $1"
                exit 1
                ;;
            *)
                paths+=("$1")
                shift
                ;;
        esac
    done

    if [ ${#paths[@]} -eq 0 ]; then
        echo "Usage: $0 [--delete|--move|--rename] [--force] <paths...>"
        echo ""
        echo "Protects desktop backend files from accidental deletion"
        echo ""
        echo "Options:"
        echo "  --delete    Protect against deletion operations"
        echo "  --move      Protect against move operations"
        echo "  --rename    Protect against rename operations"
        echo "  --force     Bypass protection (use with extreme caution)"
        echo ""
        echo "Protected paths include:"
        echo "  - Tauri desktop application (src-tauri/)"
        echo "  - Frontend application (frontend-nextjs/)"
        echo "  - Desktop-specific UI components"
        echo "  - Desktop configuration and scripts"
        exit 1
    fi

    # Convert relative paths to absolute paths
    local absolute_paths=()
    for path in "${paths[@]}"; do
        if [[ "$path" != /* ]]; then
            absolute_paths+=("$(realpath "$path")")
        else
            absolute_paths+=("$path")
        fi
    done

    case "$operation" in
        delete)
            if [ "$force" = true ]; then
                handle_forced_operation "delete" "${absolute_paths[@]}"
            else
                if ! validate_deletion "${absolute_paths[@]}"; then
                    exit 1
                fi
                # Create backup before allowed deletion
                create_backup "delete" "${absolute_paths[@]}"
            fi
            ;;
        move|rename)
            if [ "$force" = true ]; then
                handle_forced_operation "$operation" "${absolute_paths[@]}"
            else
                for path in "${absolute_paths[@]}"; do
                    if is_protected_path "$path"; then
                        echo "ERROR: Cannot $operation protected path: $path"
                        log_protection "BLOCKED: Attempted to $operation protected path: $path"
                        exit 1
                    fi
                done
                # Create backup before allowed operation
                create_backup "$operation" "${absolute_paths[@]}"
            fi
            ;;
        *)
            echo "No operation specified. Use --delete, --move, or --rename"
            exit 1
            ;;
    esac

    echo "✅ Protection checks passed. Operation can proceed."
    log_protection "ALLOWED: $operation operation on paths: ${paths[*]}"
}

# Run main function with all arguments
main "$@"
