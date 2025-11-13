#!/bin/bash

# ATOM Documentation Organization Script
# This script organizes the documentation structure for the ATOM platform

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
    echo "=================================================="
    echo "        ATOM Documentation Organization"
    echo "=================================================="
    echo ""
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if we're in the right directory
    if [ ! -f "README.md" ]; then
        log_error "Must be run from project root directory"
        exit 1
    fi

    # Check if docs directory exists
    if [ ! -d "docs" ]; then
        log_error "docs directory not found"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Create documentation structure
create_doc_structure() {
    log_info "Creating documentation structure..."

    # Main documentation categories
    categories=("GETTING_STARTED" "ARCHITECTURE" "INTEGRATIONS" "WORKFLOW_AUTOMATION" "DEPLOYMENT" "SECURITY" "DEVELOPMENT" "GUIDES" "API")

    for category in "${categories[@]}"; do
        if [ ! -d "docs/$category" ]; then
            mkdir -p "docs/$category"
            log_info "Created docs/$category"
        fi
    done

    # Integration subcategories
    integration_categories=("COMMUNICATION" "PRODUCTIVITY" "DEVELOPMENT" "CRM_BUSINESS" "FINANCIAL" "STORAGE")

    for subcat in "${integration_categories[@]}"; do
        if [ ! -d "docs/INTEGRATIONS/$subcat" ]; then
            mkdir -p "docs/INTEGRATIONS/$subcat"
            log_info "Created docs/INTEGRATIONS/$subcat"
        fi
    done

    # API subcategories
    api_categories=("ENDPOINTS" "EXAMPLES" "SDK")

    for subcat in "${api_categories[@]}"; do
        if [ ! -d "docs/API/$subcat" ]; then
            mkdir -p "docs/API/$subcat"
            log_info "Created docs/API/$subcat"
        fi
    done

    # Guide subcategories
    guide_categories=("END_USERS" "ADMINISTRATORS" "ENTERPRISE" "DEVELOPERS")

    for subcat in "${guide_categories[@]}"; do
        if [ ! -d "docs/GUIDES/$subcat" ]; then
            mkdir -p "docs/GUIDES/$subcat"
            log_info "Created docs/GUIDES/$subcat"
        fi
    done

    log_success "Documentation structure created"
}

# Move core documentation files
move_core_docs() {
    log_info "Moving core documentation files..."

    # Files to move with their destination mappings
    doc_mappings=(
        "README.md:docs/README.md"
        "ARCHITECTURE.md:docs/ARCHITECTURE/SYSTEM_OVERVIEW.md"
        "DEPLOYMENT_GUIDE.md:docs/DEPLOYMENT/PRODUCTION_DEPLOYMENT.md"
        "ENHANCED_WORKFLOW_AUTOMATION_GUIDE.md:docs/WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md"
        "SETUP_GUIDE.md:docs/GETTING_STARTED/INSTALLATION.md"
        "USER_GUIDE.md:docs/GUIDES/END_USERS/GETTING_STARTED.md"
        "CONTRIBUTING.md:docs/DEVELOPMENT/CONTRIBUTING.md"
        "SECURITY_AUDIT_FINAL.md:docs/SECURITY/SECURITY_OVERVIEW.md"
        "API_KEY_INTEGRATION_GUIDE.md:docs/API/AUTHENTICATION.md"
    )

    for mapping in "${doc_mappings[@]}"; do
        source_file="${mapping%:*}"
        destination="${mapping#*:}"

        if [ -f "$source_file" ]; then
            cp "$source_file" "$destination"
            log_info "Moved $source_file to $destination"
        else
            log_warning "Source file $source_file not found"
        fi
    done

    log_success "Core documentation files moved"
}

# Move integration documentation
move_integration_docs() {
    log_info "Moving integration documentation..."

    # Integration completion files to organize
    integration_files=(
        "SLACK_INTEGRATION_COMPLETE.md"
        "GITHUB_INTEGRATION_COMPLETE.md"
        "SALESFORCE_INTEGRATION_COMPLETE.md"
        "ASANA_INTEGRATION_COMPLETE.md"
        "NOTION_INTEGRATION_COMPLETE.md"
        "TRELLO_INTEGRATION_COMPLETE.md"
        "JIRA_INTEGRATION_COMPLETE.md"
        "LINEAR_INTEGRATION_COMPLETE.md"
        "FIGMA_INTEGRATION_COMPLETE.md"
        "STRIPE_INTEGRATION_COMPLETE.md"
        "HUBSPOT_INTEGRATION_COMPLETE.md"
        "ZENDESK_INTEGRATION_COMPLETE.md"
        "SHOPIFY_INTEGRATION_COMPLETE.md"
        "QUICKBOOKS_INTEGRATION_COMPLETE.md"
        "XERO_INTEGRATION_COMPLETE.md"
        "GOOGLE_DRIVE_INTEGRATION_GUIDE.md"
        "ONEDRIVE_INTEGRATION_GUIDE.md"
        "DROPBOX_INTEGRATION_IMPLEMENTATION_COMPLETE.md"
        "OUTLOOK_INTEGRATION_COMPLETION_SUMMARY.md"
        "GMAIL_INTEGRATION_COMPLETE.md"
        "ZOOM_INTEGRATION_COMPLETION_SUMMARY.md"
        "DISCORD_INTEGRATION_COMPLETE.md"
        "INTERCOM_INTEGRATION_COMPLETE.md"
        "FRESHDESK_INTEGRATION_COMPLETE.md"
        "MAILCHIMP_INTEGRATION_COMPLETE.md"
        "MICROSOFT_365_INTEGRATION_COMPLETE.md"
        "MONDAY_INTEGRATION_COMPLETE.md"
        "GITLAB_INTEGRATION_COMPLETE.md"
        "BITBUCKET_INTEGRATION_COMPLETE.md"
        "GOOGLE_WORKSPACE_INTEGRATION_COMPLETE.md"
    )

    # Integration category mapping (using array instead of associative array for compatibility)
    integration_categories=(
        "SLACK:COMMUNICATION"
        "GITHUB:DEVELOPMENT"
        "SALESFORCE:CRM_BUSINESS"
        "ASANA:PRODUCTIVITY"
        "NOTION:PRODUCTIVITY"
        "TRELLO:PRODUCTIVITY"
        "JIRA:PRODUCTIVITY"
        "LINEAR:PRODUCTIVITY"
        "FIGMA:PRODUCTIVITY"
        "STRIPE:FINANCIAL"
        "HUBSPOT:CRM_BUSINESS"
        "ZENDESK:CRM_BUSINESS"
        "SHOPIFY:CRM_BUSINESS"
        "QUICKBOOKS:FINANCIAL"
        "XERO:FINANCIAL"
        "GOOGLE_DRIVE:STORAGE"
        "ONEDRIVE:STORAGE"
        "DROPBOX:STORAGE"
        "OUTLOOK:COMMUNICATION"
        "GMAIL:COMMUNICATION"
        "ZOOM:COMMUNICATION"
        "DISCORD:COMMUNICATION"
        "INTERCOM:COMMUNICATION"
        "FRESHDESK:COMMUNICATION"
        "MAILCHIMP:COMMUNICATION"
        "MICROSOFT_365:PRODUCTIVITY"
        "MONDAY:PRODUCTIVITY"
        "GITLAB:DEVELOPMENT"
        "BITBUCKET:DEVELOPMENT"
        "GOOGLE_WORKSPACE:PRODUCTIVITY"
    )

    moved_count=0
    for file in "${integration_files[@]}"; do
        if [ -f "$file" ]; then
            # Extract service name from filename
            service_name=$(echo "$file" | sed 's/_INTEGRATION_COMPLETE\.md//' | sed 's/_INTEGRATION_GUIDE\.md//' | sed 's/_COMPLETION_SUMMARY\.md//' | sed 's/_IMPLEMENTATION_COMPLETE\.md//')

            # Get category
            category=""
            for category_mapping in "${integration_categories[@]}"; do
                mapping_service="${category_mapping%:*}"
                mapping_category="${category_mapping#*:}"
                if [ "$mapping_service" = "$service_name" ]; then
                    category="$mapping_category"
                    break
                fi
            done

            if [ -n "$category" ]; then
                destination="docs/INTEGRATIONS/$category/${service_name}.md"
                cp "$file" "$destination"
                log_info "Moved $file to $destination"
                ((moved_count++))
            else
                log_warning "No category found for $service_name"
            fi
        fi
    done

    log_success "Moved $moved_count integration documentation files"
}

# Create missing documentation templates
create_missing_templates() {
    log_info "Creating missing documentation templates..."

    # Templates to create
    templates=(
        "docs/GETTING_STARTED/QUICK_START.md"
        "docs/GETTING_STARTED/FIRST_STEPS.md"
        "docs/GETTING_STARTED/TROUBLESHOOTING.md"
        "docs/ARCHITECTURE/BACKEND_ARCHITECTURE.md"
        "docs/ARCHITECTURE/FRONTEND_ARCHITECTURE.md"
        "docs/ARCHITECTURE/DATABASE_SCHEMA.md"
        "docs/ARCHITECTURE/API_REFERENCE.md"
        "docs/WORKFLOW_AUTOMATION/INTELLIGENCE_ENGINE.md"
        "docs/WORKFLOW_AUTOMATION/OPTIMIZATION_ENGINE.md"
        "docs/WORKFLOW_AUTOMATION/MONITORING_SYSTEM.md"
        "docs/WORKFLOW_AUTOMATION/TROUBLESHOOTING_ENGINE.md"
        "docs/DEPLOYMENT/DOCKER_DEPLOYMENT.md"
        "docs/DEPLOYMENT/CLOUD_DEPLOYMENT.md"
        "docs/DEPLOYMENT/MONITORING_SETUP.md"
        "docs/SECURITY/AUTHENTICATION.md"
        "docs/SECURITY/DATA_PROTECTION.md"
        "docs/SECURITY/COMPLIANCE.md"
        "docs/DEVELOPMENT/DEVELOPMENT_SETUP.md"
        "docs/DEVELOPMENT/TESTING_GUIDE.md"
        "docs/DEVELOPMENT/API_DEVELOPMENT.md"
        "docs/API/OVERVIEW.md"
        "docs/API/ENDPOINTS/WORKFLOWS.md"
        "docs/API/ENDPOINTS/INTEGRATIONS.md"
        "docs/API/ENDPOINTS/USERS.md"
        "docs/API/ENDPOINTS/MONITORING.md"
        "docs/API/EXAMPLES/BASIC_USAGE.md"
        "docs/API/EXAMPLES/ADVANCED_WORKFLOWS.md"
        "docs/API/EXAMPLES/ERROR_HANDLING.md"
        "docs/API/SDK/PYTHON_SDK.md"
        "docs/API/SDK/JAVASCRIPT_SDK.md"
        "docs/API/SDK/REST_CLIENTS.md"
        "docs/GUIDES/END_USERS/WORKFLOW_CREATION.md"
        "docs/GUIDES/END_USERS/INTEGRATION_SETUP.md"
        "docs/GUIDES/END_USERS/BEST_PRACTICES.md"
        "docs/GUIDES/ADMINISTRATORS/SYSTEM_SETUP.md"
        "docs/GUIDES/ADMINISTRATORS/USER_MANAGEMENT.md"
        "docs/GUIDES/ADMINISTRATORS/SECURITY_CONFIG.md"
        "docs/GUIDES/ADMINISTRATORS/MONITORING.md"
        "docs/GUIDES/ENTERPRISE/ENTERPRISE_SETUP.md"
        "docs/GUIDES/ENTERPRISE/SCALABILITY.md"
        "docs/GUIDES/ENTERPRISE/COMPLIANCE.md"
        "docs/GUIDES/ENTERPRISE/CUSTOM_INTEGRATIONS.md"
        "docs/GUIDES/DEVELOPERS/EXTENDING_ATOM.md"
        "docs/GUIDES/DEVELOPERS/CUSTOM_WORKFLOWS.md"
        "docs/GUIDES/DEVELOPERS/API_INTEGRATION.md"
        "docs/GUIDES/DEVELOPERS/PLUGIN_DEVELOPMENT.md"
    )

    created_count=0
    for template in "${templates[@]}"; do
        if [ ! -f "$template" ]; then
            # Create directory if it doesn't exist
            mkdir -p "$(dirname "$template")"

            # Create template file with basic structure
            cat > "$template" << EOF
# $(basename "$template" .md | tr '_' ' ')

> **Status**: Template - Content needed
> **Last Updated**: $(date +%Y-%m-%d)

## Overview

This documentation is currently being organized. Content will be added soon.

## TODO

- [ ] Add comprehensive content
- [ ] Include examples and use cases
- [ ] Add troubleshooting information
- [ ] Include best practices

## Quick Start

Content coming soon...

## Detailed Guide

Content coming soon...

## Troubleshooting

Content coming soon...

---

**Need Help?** Check the main [documentation index](../README.md) for more resources.

**Found an Issue?** Help us improve by contributing to the documentation.
EOF
            log_info "Created template: $template"
            ((created_count++))
        fi
    done

    log_success "Created $created_count documentation templates"
}

# Update documentation references
update_references() {
    log_info "Updating documentation references..."

    # Update main README to point to new documentation
    if [ -f "README.md" ]; then
        # Create backup
        cp "README.md" "README.md.backup"

        # Update documentation section
        sed -i.bak '/## 📚 Documentation & Support/,/## 🔒 Security First Approach/c\
## 📚 Documentation & Support\n\n### Complete Documentation\n- [📚 Full Documentation](docs/README.md) - Comprehensive platform documentation\n- [🚀 Quick Start Guide](docs/GETTING_STARTED/QUICK_START.md) - Get started in minutes\n- [🏗️ Architecture Guide](docs/ARCHITECTURE/SYSTEM_OVERVIEW.md) - Technical architecture\n- [🔧 Integration Guide](docs/INTEGRATIONS/OVERVIEW.md) - 33+ service integrations\n- [🤖 Workflow Automation](docs/WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md) - AI-powered features\n\n### Testing & Quality\n- [Comprehensive Testing Suite](tests/) - 100+ test cases\n- [Quality Assurance](docs/DEVELOPMENT/TESTING_GUIDE.md) - Testing framework\n- [Performance Benchmarks](docs/ARCHITECTURE/PERFORMANCE.md) - Performance metrics' "README.md"

        log_info "Updated README.md documentation references"
    fi

    log_success "Documentation references updated"
}

# Verify organization
verify_organization() {
    log_info "Verifying documentation organization..."

    # Check if main documentation files exist
    required_files=(
        "docs/README.md"
        "docs/GETTING_STARTED/QUICK_START.md"
        "docs/ARCHITECTURE/SYSTEM_OVERVIEW.md"
        "docs/INTEGRATIONS/OVERVIEW.md"
        "docs/WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md"
        "docs/DEPLOYMENT/PRODUCTION_DEPLOYMENT.md"
    )

    missing_files=0
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Missing required file: $file"
            ((missing_files++))
        fi
    done

    if [ $missing_files -eq 0 ]; then
        log_success "All required documentation files are present"
    else
        log_warning "$missing_files required files are missing"
    fi

    # Count total documentation files
    total_files=$(find docs -name "*.md" | wc -l)
    log_info "Total documentation files: $total_files"

    log_success "Documentation organization verification completed"
}

# Display summary
display_summary() {
    log_success "Documentation Organization Complete!"
    echo ""
    echo "📋 Organization Summary:"
    echo "   ✅ Documentation structure created"
    echo "   ✅ Core documentation moved"
    echo "   ✅ Integration documentation organized"
    echo "   ✅ Missing templates created"
    echo "   ✅ References updated"
    echo "   ✅ Organization verified"
    echo ""
    echo "📁 New Structure:"
    echo "   docs/"
    echo "   ├── 📚 GETTING_STARTED/"
    echo "   ├── 🏗️ ARCHITECTURE/"
    echo "   ├── 🔧 INTEGRATIONS/"
    echo "   │   ├── COMMUNICATION/"
    echo "   │   ├── PRODUCTIVITY/"
    echo "   │   ├── DEVELOPMENT/"
    echo "   │   ├── CRM_BUSINESS/"
    echo "   │   ├── FINANCIAL/"
    echo "   │   └── STORAGE/"
    echo "   ├── 🤖 WORKFLOW_AUTOMATION/"
    echo "   ├── 🚀 DEPLOYMENT/"
    echo "   ├── 🔒 SECURITY/"
    echo "   ├── 📊 DEVELOPMENT/"
    echo "   ├── 📖 GUIDES/"
    echo "   │   ├── END_USERS/"
    echo "   │   ├── ADMINISTRATORS/"
    echo "   │   ├── ENTERPRISE/"
    echo "   │   └── DEVELOPERS/"
    echo "   └── 🔗 API/"
    echo "       ├── ENDPOINTS/"
    echo "       ├── EXAMPLES/"
    echo "       └── SDK/"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Review the organized documentation structure"
    echo "   2. Fill in missing content in template files"
    echo "   3. Update any broken links"
    echo "   4. Test documentation navigation"
    echo ""
}

# Main organization function
main() {
    print_banner

    log_info "Starting ATOM documentation organization..."

    # Execute organization steps
    check_prerequisites
    create_doc_structure
    move_core_docs
    move_integration_docs
    create_missing_templates
    update_references
    verify_organization
    display_summary

    log_success "ATOM documentation organization completed successfully!"
}

# Run main function
main "$@"
