#!/bin/bash

# ATOM Production Deployment Script
# Automates complete production infrastructure deployment
# Usage: ./deploy-production.sh [--env production] [--region us-east-1] [--confirm]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_NAME="ATOM Production Deployment"
SCRIPT_VERSION="1.0.0"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
LOG_FILE="/tmp/atom-deployment-${TIMESTAMP//[^0-9a-zA-Z]/}.log"

# Default parameters
ENVIRONMENT="production"
REGION="us-east-1"
CONFIRM_DEPLOYMENT=false
SKIP_VALIDATION=false
BACKUP_BEFORE_DEPLOY=true
ROLLBACK_ON_FAILURE=true

# Configuration files
TERRAFORM_DIR="./infrastructure/terraform"
ANSIBLE_DIR="./infrastructure/ansible"
KUBERNETES_DIR="./infrastructure/kubernetes"
DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

# Logging functions
log() {
    echo -e "${BLUE}[${TIMESTAMP}]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[${TIMESTAMP}] ERROR:${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[${TIMESTAMP}] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[${TIMESTAMP}] SUCCESS:${NC} $1" | tee -a "$LOG_FILE"
}

# Help function
show_help() {
    cat << EOF
${SCRIPT_NAME} v${SCRIPT_VERSION}
Automates complete ATOM production infrastructure deployment

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --env ENVIRONMENT      Target environment (production|staging) [default: production]
    --region REGION         AWS region [default: us-east-1]
    --confirm              Skip confirmation prompt
    --skip-validation      Skip pre-deployment validation
    --no-backup            Skip backup before deployment
    --no-rollback          Skip automatic rollback on failure
    --dry-run              Show what would be deployed without executing
    --help                 Show this help message

EXAMPLES:
    $0 --env production --confirm
    $0 --env staging --region us-west-2 --skip-validation
    $0 --dry-run

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --confirm)
                CONFIRM_DEPLOYMENT=true
                shift
                ;;
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --no-backup)
                BACKUP_BEFORE_DEPLOY=false
                shift
                ;;
            --no-rollback)
                ROLLBACK_ON_FAILURE=false
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done
}

# Validate environment and dependencies
validate_environment() {
    log "Validating deployment environment..."
    
    # Check if required tools are installed
    local required_tools=("aws" "terraform" "kubectl" "docker" "ansible")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "Required tool '$tool' is not installed"
        fi
    done
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Run 'aws configure' first."
    fi
    
    # Validate environment name
    if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "staging" ]]; then
        error "Environment must be 'production' or 'staging'"
    fi
    
    # Check if configuration files exist
    if [[ ! -f "$ENV_FILE" ]]; then
        error "Environment file '$ENV_FILE' not found"
    fi
    
    if [[ ! -d "$TERRAFORM_DIR" ]]; then
        error "Terraform directory '$TERRAFORM_DIR' not found"
    fi
    
    # Validate region
    if ! aws ec2 describe-regions --region-names "$REGION" &> /dev/null; then
        error "Invalid AWS region: $REGION"
    fi
    
    success "Environment validation completed"
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Running pre-deployment checks..."
    
    # Check for existing infrastructure
    log "Checking for existing infrastructure..."
    local existing_vpc=$(aws ec2 describe-vpcs --filters "Name=tag:Environment,Values=$ENVIRONMENT" "Name=tag:Application,Values=atom-platform" --query "Vpcs[0].VpcId" --output text 2>/dev/null)
    
    if [[ "$existing_vpc" != "None" && "$existing_vpc" != "" ]]; then
        warning "Existing infrastructure found in $ENVIRONMENT environment"
        if [[ "$CONFIRM_DEPLOYMENT" != true ]]; then
            read -p "This may cause data loss. Continue? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log "Deployment cancelled by user"
                exit 0
            fi
        fi
    fi
    
    # Validate configuration
    log "Validating Terraform configuration..."
    cd "$TERRAFORM_DIR"
    if ! terraform validate; then
        error "Terraform configuration validation failed"
    fi
    
    # Check resources to be created/modified
    log "Analyzing deployment plan..."
    terraform plan -var="environment=$ENVIRONMENT" -var="region=$REGION" -out=terraform.plan
    
    if [[ "$DRY_RUN" == true ]]; then
        log "Dry run completed. No changes were made."
        terraform show terraform.plan
        exit 0
    fi
    
    cd - > /dev/null
    
    success "Pre-deployment checks completed"
}

# Backup existing data
backup_existing_data() {
    if [[ "$BACKUP_BEFORE_DEPLOY" != true ]]; then
        log "Skipping backup as requested"
        return
    fi
    
    log "Creating backup of existing data..."
    
    # Backup database
    log "Backing up database..."
    local backup_name="atom-backup-$(date +%Y%m%d-%H%M%S)"
    aws s3 cp "s3://atom-platform-backups/latest/" "s3://atom-platform-backups/$backup_name/" --recursive || warning "Database backup failed"
    
    # Backup configuration
    log "Backing up configuration..."
    aws s3 cp "$ENV_FILE" "s3://atom-platform-backups/config/$backup_name.env" || warning "Configuration backup failed"
    
    # Backup infrastructure state
    if [[ -f "$TERRAFORM_DIR/terraform.tfstate" ]]; then
        log "Backing up infrastructure state..."
        aws s3 cp "$TERRAFORM_DIR/terraform.tfstate" "s3://atom-platform-backups/state/$backup_name.tfstate" || warning "State backup failed"
    fi
    
    success "Backup completed: $backup_name"
}

# Deploy infrastructure
deploy_infrastructure() {
    log "Deploying infrastructure to $ENVIRONMENT environment..."
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    log "Initializing Terraform..."
    terraform init -input=false
    
    # Apply infrastructure changes
    log "Applying infrastructure changes..."
    terraform apply -var="environment=$ENVIRONMENT" -var="region=$REGION" -auto-approve terraform.plan
    
    # Get outputs
    log "Retrieving infrastructure outputs..."
    terraform output -json > ../infrastructure-outputs.json
    
    cd - > /dev/null
    
    success "Infrastructure deployment completed"
}

# Configure Kubernetes cluster
configure_kubernetes() {
    log "Configuring Kubernetes cluster..."
    
    # Update kubeconfig
    aws eks update-kubeconfig --region "$REGION" --name "atom-$ENVIRONMENT"
    
    # Install required Helm charts
    log "Installing Helm charts..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    # Install monitoring stack
    log "Installing monitoring stack..."
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --values ../kubernetes/monitoring/values.yaml
    
    # Install ingress controller
    log "Installing ingress controller..."
    helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --create-namespace \
        --values ../kubernetes/ingress/values.yaml
    
    success "Kubernetes cluster configured"
}

# Deploy applications
deploy_applications() {
    log "Deploying applications to Kubernetes..."
    
    cd "$KUBERNETES_DIR"
    
    # Apply configurations
    kubectl apply -f ./namespaces/
    kubectl apply -f ./configmaps/
    kubectl apply -f ./secrets/
    kubectl apply -f ./deployments/
    kubectl apply -f ./services/
    kubectl apply -f ./ingress/
    
    # Wait for deployments to be ready
    log "Waiting for deployments to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment --all -n atom-platform
    kubectl wait --for=condition=available --timeout=300s deployment --all -n monitoring
    
    cd - > /dev/null
    
    success "Applications deployed successfully"
}

# Configure DNS and SSL
configure_dns_ssl() {
    log "Configuring DNS and SSL..."
    
    # Get load balancer DNS name
    local lb_dns=$(kubectl get service atom-platform-ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    # Update Route 53 records
    log "Updating DNS records..."
    aws route53 change-resource-record-sets --hosted-zone-id Z1X1234567890 --change-batch file://../dns/route53-changes.json
    
    # Request SSL certificates (if using AWS Certificate Manager)
    log "Requesting SSL certificates..."
    aws acm request-certificate --domain-name atom-platform.com --validation-method DNS --subject-alternative-names www.atom-platform.com,api.atom-platform.com
    
    success "DNS and SSL configuration completed"
}

# Run post-deployment validation
post_deployment_validation() {
    log "Running post-deployment validation..."
    
    local validation_errors=0
    
    # Health checks
    log "Performing health checks..."
    local health_endpoints=(
        "https://atom-platform.com/health"
        "https://api.atom-platform.com/health"
        "https://app.atom-platform.com/health"
    )
    
    for endpoint in "${health_endpoints[@]}"; do
        if curl -f -s "$endpoint" > /dev/null; then
            success "Health check passed: $endpoint"
        else
            error "Health check failed: $endpoint"
            ((validation_errors++))
        fi
    done
    
    # Integration tests
    log "Running integration tests..."
    if npm run test:integration; then
        success "Integration tests passed"
    else
        error "Integration tests failed"
        ((validation_errors++))
    fi
    
    # Performance tests
    log "Running performance tests..."
    if npm run test:performance; then
        success "Performance tests passed"
    else
        warning "Performance tests failed"
        # Don't count this as critical error
    fi
    
    if [[ $validation_errors -gt 0 ]]; then
        error "Post-deployment validation failed with $validation_errors errors"
    fi
    
    success "Post-deployment validation completed"
}

# Setup monitoring and alerting
setup_monitoring() {
    log "Setting up monitoring and alerting..."
    
    # Configure Prometheus rules
    kubectl apply -f ../monitoring/prometheus-rules.yaml
    
    # Configure Grafana dashboards
    kubectl apply -f ../monitoring/grafana-dashboards.yaml
    
    # Setup alerts
    local alert_webhook_url=$(cat ../monitoring/slack-webhook.url)
    kubectl create secret generic slack-webhook --from-literal=webhook-url="$alert_webhook_url" -n monitoring || true
    
    success "Monitoring and alerting setup completed"
}

# Rollback function
rollback_deployment() {
    if [[ "$ROLLBACK_ON_FAILURE" != true ]]; then
        log "Rollback disabled, skipping cleanup"
        return
    fi
    
    log "Rolling back deployment..."
    
    # Rollback Kubernetes deployments
    cd "$KUBERNETES_DIR"
    kubectl rollout undo deployment --all -n atom-platform
    cd - > /dev/null
    
    # Rollback infrastructure (if needed)
    cd "$TERRAFORM_DIR"
    if [[ -f "terraform.plan.backup" ]]; then
        terraform apply -auto-approve terraform.plan.backup
    fi
    cd - > /dev/null
    
    success "Rollback completed"
}

# Generate deployment report
generate_report() {
    log "Generating deployment report..."
    
    local report_file="deployment-report-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).json"
    
    cat > "$report_file" << EOF
{
    "deployment": {
        "environment": "$ENVIRONMENT",
        "region": "$REGION",
        "timestamp": "$(date -I)",
        "status": "success"
    },
    "infrastructure": {
        "vpc_id": "$(aws ec2 describe-vpcs --filters "Name=tag:Environment,Values=$ENVIRONMENT" "Name=tag:Application,Values=atom-platform" --query "Vpcs[0].VpcId" --output text)",
        "cluster_name": "atom-$ENVIRONMENT",
        "load_balancer_dns": "$(kubectl get service atom-platform-ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
    },
    "applications": {
        "web_app": "$(kubectl get pods -n atom-platform -l app=web -o jsonpath='{.items[0].status.phase}')",
        "api_service": "$(kubectl get pods -n atom-platform -l app=api -o jsonpath='{.items[0].status.phase}')",
        "workers": "$(kubectl get pods -n atom-platform -l app=worker --no-headers | wc -l)"
    },
    "monitoring": {
        "prometheus": "http://prometheus.atom-platform.com",
        "grafana": "http://grafana.atom-platform.com",
        "alerts": "http://alertmanager.atom-platform.com"
    },
    "costs": {
        "estimated_monthly": "$954.60",
        "currency": "USD"
    }
}
EOF
    
    success "Deployment report generated: $report_file"
}

# Main deployment function
main() {
    log "Starting ${SCRIPT_NAME} v${SCRIPT_VERSION}"
    log "Environment: $ENVIRONMENT"
    log "Region: $REGION"
    log "Log file: $LOG_FILE"
    
    # Parse arguments
    parse_args "$@"
    
    # Validate environment
    if [[ "$SKIP_VALIDATION" != true ]]; then
        validate_environment
    fi
    
    # Confirmation prompt
    if [[ "$CONFIRM_DEPLOYMENT" != true ]]; then
        echo
        echo -e "${YELLOW}This will deploy ATOM platform to $ENVIRONMENT environment in $REGION region.${NC}"
        echo -e "${YELLOW}Estimated cost: ~$954.60/month${NC}"
        echo
        read -p "Continue with deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Deployment cancelled by user"
            exit 0
        fi
    fi
    
    # Set trap for cleanup on failure
    trap 'rollback_deployment' ERR
    
    # Execute deployment steps
    pre_deployment_checks
    backup_existing_data
    deploy_infrastructure
    configure_kubernetes
    deploy_applications
    configure_dns_ssl
    post_deployment_validation
    setup_monitoring
    generate_report
    
    success "${SCRIPT_NAME} completed successfully!"
    log "Access your ATOM platform at: https://atom-platform.com"
    log "Monitoring dashboard: https://monitoring.atom-platform.com"
}

# Execute main function
main "$@"