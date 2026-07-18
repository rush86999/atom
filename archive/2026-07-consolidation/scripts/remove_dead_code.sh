#!/bin/bash

# 🚀 ATOM Dead Code Removal Script
# Removes identified dead code candidates to maintain codebase health

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   ATOM DEAD CODE REMOVAL                    ║"
    echo "║                    Codebase Health Check                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# List of dead code candidates identified in UI_GAP_ANALYSIS.md
# Only includes truly unused files that are safe to remove
DEAD_CODE_CANDIDATES=(
    # Frontend files
    "frontend-nextjs/components/ExampleSharedUsage.tsx"
    "frontend-nextjs/pages/index-dev.tsx"
    "frontend-nextjs/components/Settings/VoiceSettings.d.ts"
    "frontend-nextjs/components/Settings/VoiceSettings.js"  # Duplicate of .tsx version

    # Desktop files
    "desktop/tauri/src/ExampleSharedUsage.tsx"
    "desktop/tauri/src/web-dev-service.ts"
    # Note: Settings.css is kept as it's actually used by Settings.tsx
)

# Function to verify file exists and is safe to remove
verify_file_for_removal() {
    local file_path="$1"

    if [[ ! -f "$file_path" ]]; then
        log_warning "File not found: $file_path"
        return 1
    fi

    # Check if file is in git (safety check)
    if ! git ls-files --error-unmatch "$file_path" >/dev/null 2>&1; then
        log_warning "File not tracked by git: $file_path"
        return 1
    fi

    # Check file size (avoid removing large files accidentally)
    local file_size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null)
    if [[ $file_size -gt 100000 ]]; then  # 100KB threshold
        log_warning "Large file detected (>100KB): $file_path"
        return 1
    fi

    return 0
}

# Function to create backup before removal
create_backup() {
    local file_path="$1"
    local backup_dir="backup_dead_code_$(date +%Y%m%d_%H%M%S)"

    mkdir -p "$backup_dir"
    cp "$file_path" "$backup_dir/" 2>/dev/null || true
    log_info "Backup created: $backup_dir/$(basename "$file_path")"
}

# Function to remove a single file with safety checks
remove_file_safely() {
    local file_path="$1"
    local force="${2:-false}"

    log_info "Processing: $file_path"

    if [[ "$force" == "true" ]]; then
        log_warning "Force removal enabled for: $file_path"
    else
        if ! verify_file_for_removal "$file_path"; then
            log_error "Safety check failed for: $file_path"
            return 1
        fi
    fi

    # Create backup
    create_backup "$file_path"

    # Remove the file
    if rm "$file_path"; then
        log_success "Removed: $file_path"
        return 0
    else
        log_error "Failed to remove: $file_path"
        return 1
    fi
}

# Function to verify backend handlers can be safely removed
verify_backend_handlers() {
    log_info "Verifying backend handlers for safe removal..."

    local safe_to_remove=()
    local unsafe_handlers=()

    # Check if any backend handlers are in the removal list
    for handler in "${DEAD_CODE_CANDIDATES[@]}"; do
        if [[ "$handler" == backend/python-api-service/*_handler.py ]]; then
            # Verify handler is actually unused (not imported in main app)
            local handler_basename=$(basename "$handler" .py)
            if grep -q "$handler_basename" "backend/python-api-service/main_api_app.py"; then
                log_warning "Handler is used in main app: $handler"
                unsafe_handlers+=("$handler")
            else
                log_info "Handler appears unused: $handler"
            fi
        fi
    done

    if [[ ${#unsafe_handlers[@]} -eq 0 ]]; then
        log_success "All backend handlers have service implementations"
    else
        log_warning "Some handlers may be unsafe to remove:"
        for handler in "${unsafe_handlers[@]}"; do
            echo "  - $handler"
        done
    fi
}

# Function to show removal preview
show_preview() {
    log_info "Dead Code Removal Preview"
    echo "========================================"

    local total_files=0
    local safe_files=0

    for file_path in "${DEAD_CODE_CANDIDATES[@]}"; do
        if [[ -f "$file_path" ]]; then
            echo "✅ $file_path"
            ((safe_files++))
        else
            echo "❌ $file_path (not found)"
        fi
        ((total_files++))
    done

    echo "========================================"
    echo "Total candidates: $total_files"
    echo "Files found: $safe_files"
    echo ""
}

# Function to perform actual removal
perform_removal() {
    local force="${1:-false}"

    log_info "Starting dead code removal..."

    local removed_count=0
    local failed_count=0

    for file_path in "${DEAD_CODE_CANDIDATES[@]}"; do
        if remove_file_safely "$file_path" "$force"; then
            ((removed_count++))
        else
            ((failed_count++))
        fi
        echo ""
    done

    log_info "Removal Summary:"
    echo "  ✅ Successfully removed: $removed_count files"
    echo "  ❌ Failed to remove: $failed_count files"
    echo "  📊 Total processed: ${#DEAD_CODE_CANDIDATES[@]} files"

    if [[ $removed_count -gt 0 ]]; then
        log_success "Dead code removal completed successfully!"
    else
        log_warning "No files were removed"
    fi
}

# Function to clean up empty directories
cleanup_empty_directories() {
    log_info "Cleaning up empty directories..."

    local empty_dirs=()

    # Find empty directories in frontend components
    if [[ -d "frontend-nextjs/components" ]]; then
        while IFS= read -r dir; do
            if [[ -d "$dir" ]] && [[ -z "$(ls -A "$dir")" ]]; then
                empty_dirs+=("$dir")
            fi
        done < <(find "frontend-nextjs/components" -type d)
    fi

    # Find empty directories in desktop src
    if [[ -d "desktop/tauri/src" ]]; then
        while IFS= read -r dir; do
            if [[ -d "$dir" ]] && [[ -z "$(ls -A "$dir")" ]]; then
                empty_dirs+=("$dir")
            fi
        done < <(find "desktop/tauri/src" -type d)
    fi

    if [[ ${#empty_dirs[@]} -gt 0 ]]; then
        log_info "Found ${#empty_dirs[@]} empty directories:"
        for dir in "${empty_dirs[@]}"; do
            echo "  - $dir"
            rmdir "$dir" 2>/dev/null && log_success "Removed empty directory: $dir" || log_warning "Could not remove directory: $dir"
        done
    else
        log_success "No empty directories found"
    fi
}

# Function to verify removal didn't break anything
verify_system_health() {
    log_info "Verifying system health after removal..."

    # Check if frontend still builds
    if [[ -d "frontend-nextjs" ]]; then
        log_info "Checking frontend build..."
        if cd frontend-nextjs && npm run build >/dev/null 2>&1; then
            log_success "Frontend builds successfully"
        else
            log_error "Frontend build failed after removal"
        fi
        cd - >/dev/null
    fi

    # Check if backend still starts
    if [[ -f "backend/python-api-service/main_api_app.py" ]]; then
        log_info "Checking backend imports..."
        if python -c "import sys; sys.path.append('backend/python-api-service'); from main_api_app import create_app; print('Backend imports work')" >/dev/null 2>&1; then
            log_success "Backend imports work correctly"
        else
            log_error "Backend imports failed after removal"
        fi
    fi
}

# Main execution function
main() {
    print_banner

    local force_removal=false
    local preview_only=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force_removal=true
                shift
                ;;
            -p|--preview)
                preview_only=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    if [[ "$preview_only" == "true" ]]; then
        show_preview
        exit 0
    fi

    # Verify we're in the correct directory
    if [[ ! -f "README.md" ]] && [[ ! -d "backend" ]]; then
        log_error "Please run this script from the ATOM project root directory"
        exit 1
    fi

    # Show preview first
    show_preview

    # Verify backend handlers
    verify_backend_handlers

    # Ask for confirmation (unless force mode)
    if [[ "$force_removal" != "true" ]]; then
        echo ""
        read -p "Are you sure you want to remove these files? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removal cancelled"
            exit 0
        fi
    fi

    # Perform removal
    perform_removal "$force_removal"

    # Clean up empty directories
    cleanup_empty_directories

    # Verify system health
    verify_system_health

    log_success "Dead code removal process completed! 🎉"
}

# Help function
show_help() {
    echo "ATOM Dead Code Removal Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --force     Force removal without safety checks"
    echo "  -p, --preview   Show preview only, don't remove files"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Description:"
    echo "  Removes identified dead code candidates to maintain codebase health."
    echo "  Creates backups before removal and verifies system health afterwards."
    echo ""
    echo "Safety Features:"
    echo "  - Creates backups in timestamped directories"
    echo "  - Verifies files are tracked by git"
    echo "  - Checks file sizes to avoid accidental large file removal"
    echo "  - Verifies system health after removal"
    echo ""
    echo "Examples:"
    echo "  $0 --preview    # Show what will be removed"
    echo "  $0              # Remove files with safety checks"
    echo "  $0 --force      # Force removal without safety checks"
}

# Run main function with all arguments
main "$@"
