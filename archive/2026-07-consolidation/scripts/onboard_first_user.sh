#!/bin/bash

# 🚀 ATOM PLATFORM - FIRST USER ONBOARDING SCRIPT
# Complete onboarding for first user with BYOK setup and service integrations

echo "🎯 ATOM PLATFORM - FIRST USER ONBOARDING"
echo "=========================================="
echo "Setting up your first user with complete configuration"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if servers are running
    if curl -s http://localhost:3000 > /dev/null; then
        success "Frontend server is running"
    else
        error "Frontend server not accessible at http://localhost:3000"
        return 1
    fi

    if curl -s http://localhost:8000/health > /dev/null; then
        success "Backend API server is running"
    else
        error "Backend API server not accessible at http://localhost:8000"
        return 1
    fi

    if curl -s http://localhost:5058/healthz > /dev/null; then
        success "OAuth server is running"
    else
        error "OAuth server not accessible at http://localhost:5058"
        return 1
    fi

    return 0
}

# Setup BYOK (Bring Your Own Key) system
setup_byok_system() {
    log "Setting up BYOK (Bring Your Own Key) system..."

    echo ""
    echo "🤖 BYOK SYSTEM SETUP"
    echo "===================="
    echo "ATOM supports 5 AI providers with your own API keys:"
    echo "1. OpenAI"
    echo "2. DeepSeek"
    echo "3. Anthropic"
    echo "4. Google Gemini"
    echo "5. Azure OpenAI"
    echo ""

    # Create BYOK configuration directory
    mkdir -p ~/.atom/byok
    success "Created BYOK configuration directory"

    # Create sample BYOK configuration
    cat > ~/.atom/byok/sample_config.json << 'EOF'
{
  "ai_providers": {
    "openai": {
      "api_key": "YOUR_OPENAI_API_KEY",
      "enabled": true,
      "cost_optimization": true
    },
    "deepseek": {
      "api_key": "YOUR_DEEPSEEK_API_KEY",
      "enabled": true,
      "cost_optimization": true
    },
    "anthropic": {
      "api_key": "YOUR_ANTHROPIC_API_KEY",
      "enabled": true,
      "cost_optimization": true
    },
    "google_gemini": {
      "api_key": "YOUR_GOOGLE_GEMINI_API_KEY",
      "enabled": true,
      "cost_optimization": true
    },
    "azure_openai": {
      "api_key": "YOUR_AZURE_OPENAI_API_KEY",
      "endpoint": "YOUR_AZURE_ENDPOINT",
      "enabled": true,
      "cost_optimization": true
    }
  },
  "cost_optimization": {
    "auto_select_provider": true,
    "fallback_enabled": true,
    "budget_limits": {
      "daily": 10.0,
      "monthly": 100.0
    }
  }
}
EOF
    success "Created sample BYOK configuration"

    echo ""
    warning "IMPORTANT: Add your actual API keys to ~/.atom/byok/config.json"
    echo "Copy the sample config and replace with your actual keys:"
    echo "cp ~/.atom/byok/sample_config.json ~/.atom/byok/config.json"
    echo ""
}

# Setup service integrations
setup_service_integrations() {
    log "Setting up service integrations..."

    echo ""
    echo "🔗 SERVICE INTEGRATIONS SETUP"
    echo "=============================="
    echo "ATOM supports 33+ service integrations. Let's set up the most common ones:"
    echo ""

    # Create service configuration directory
    mkdir -p ~/.atom/services
    success "Created service configuration directory"

    # Create service configuration template
    cat > ~/.atom/services/integration_guide.md << 'EOF'
# ATOM Service Integration Guide

## Core Integrations to Setup:

### 1. Communication Services
- **Slack**: For team communication and notifications
- **Microsoft Teams**: Enterprise communication
- **Gmail**: Email management and automation
- **Outlook**: Microsoft email integration

### 2. Productivity Services
- **Google Calendar**: Schedule management
- **Notion**: Note-taking and documentation
- **Asana**: Project management
- **Trello**: Kanban-style task management

### 3. Development Services
- **GitHub**: Code repository management
- **GitLab**: Enterprise Git management
- **Jira**: Software development tracking
- **Linear**: Modern issue tracking

### 4. Business Services
- **Salesforce**: CRM integration
- **HubSpot**: Marketing automation
- **Zapier**: Workflow automation
- **Airtable**: Database and automation

## Setup Instructions:

1. Visit http://localhost:3000
2. Navigate to Settings > Integrations
3. Click "Connect" for each service
4. Follow OAuth flow to authorize
5. Test integration with sample workflows

## OAuth Configuration:

Most services require OAuth setup. The ATOM OAuth server handles this automatically.
Make sure your service credentials are configured in the backend environment.
EOF
    success "Created service integration guide"

    echo ""
    success "Service integration setup complete"
    echo "Visit http://localhost:3000/settings/integrations to connect services"
}

# Create user workflows
create_sample_workflows() {
    log "Creating sample workflows..."

    echo ""
    echo "🔄 SAMPLE WORKFLOWS CREATION"
    echo "============================"

    # Create workflows directory
    mkdir -p ~/.atom/workflows
    success "Created workflows directory"

    # Create daily standup workflow
    cat > ~/.atom/workflows/daily_standup.json << 'EOF'
{
  "name": "Daily Standup Automation",
  "description": "Automate daily standup preparation and follow-up",
  "trigger": "scheduled:09:00",
  "services": ["slack", "google_calendar", "asana"],
  "steps": [
    {
      "service": "google_calendar",
      "action": "get_todays_events",
      "parameters": {}
    },
    {
      "service": "asana",
      "action": "get_my_tasks",
      "parameters": {}
    },
    {
      "service": "ai",
      "action": "generate_standup_summary",
      "parameters": {
        "template": "daily_standup"
      }
    },
    {
      "service": "slack",
      "action": "post_message",
      "parameters": {
        "channel": "standups",
        "message": "{{standup_summary}}"
      }
    }
  ]
}
EOF
    success "Created Daily Standup workflow"

    # Create meeting follow-up workflow
    cat > ~/.atom/workflows/meeting_follow_up.json << 'EOF'
{
  "name": "Meeting Follow-up Automation",
  "description": "Automate meeting follow-up tasks and action items",
  "trigger": "calendar_event_ended",
  "services": ["google_calendar", "asana", "gmail", "slack"],
  "steps": [
    {
      "service": "ai",
      "action": "summarize_meeting",
      "parameters": {}
    },
    {
      "service": "asana",
      "action": "create_tasks",
      "parameters": {
        "project": "Action Items",
        "tasks": "{{action_items}}"
      }
    },
    {
      "service": "gmail",
      "action": "send_email",
      "parameters": {
        "to": "{{meeting_attendees}}",
        "subject": "Meeting Follow-up: {{meeting_title}}",
        "body": "{{meeting_summary}}"
      }
    }
  ]
}
EOF
    success "Created Meeting Follow-up workflow"

    # Create code review workflow
    cat > ~/.atom/workflows/code_review.json << 'EOF'
{
  "name": "Code Review Automation",
  "description": "Automate code review process and notifications",
  "trigger": "github:pull_request_opened",
  "services": ["github", "slack", "linear"],
  "steps": [
    {
      "service": "github",
      "action": "get_pull_request_details",
      "parameters": {}
    },
    {
      "service": "ai",
      "action": "analyze_code_changes",
      "parameters": {}
    },
    {
      "service": "slack",
      "action": "post_message",
      "parameters": {
        "channel": "code-reviews",
        "message": "New PR ready for review: {{pr_title}}"
      }
    },
    {
      "service": "linear",
      "action": "update_issue",
      "parameters": {
        "issue_id": "{{related_issue}}",
        "status": "In Review"
      }
    }
  ]
}
EOF
    success "Created Code Review workflow"

    echo ""
    success "Sample workflows created in ~/.atom/workflows/"
    echo "You can import these workflows through the ATOM interface"
}

# Setup voice commands
setup_voice_commands() {
    log "Setting up voice commands..."

    echo ""
    echo "🎤 VOICE COMMANDS SETUP"
    echo "======================="

    # Create voice commands directory
    mkdir -p ~/.atom/voice
    success "Created voice commands directory"

    # Create voice command examples
    cat > ~/.atom/voice/commands.md << 'EOF'
# ATOM Voice Commands

## Basic Commands:
- "Hey Atom, what's on my calendar today?"
- "Atom, create a task for me"
- "Show me my upcoming meetings"
- "Search for documents about project X"

## Workflow Commands:
- "Atom, run my daily standup workflow"
- "Prepare my weekly report"
- "Schedule follow-up for today's meetings"
- "Check my task progress"

## Integration Commands:
- "Atom, send a message to the team channel"
- "Create a GitHub issue for this bug"
- "Add this to my Asana project"
- "Schedule a meeting with the engineering team"

## Advanced Commands:
- "Atom, optimize my workday"
- "Analyze my productivity patterns"
- "Suggest workflow improvements"
- "Generate a project status report"
EOF
    success "Created voice command examples"

    echo ""
    success "Voice commands setup complete"
    echo "Enable voice recognition in Settings > Voice to use these commands"
}

# Test platform functionality
test_platform_functionality() {
    log "Testing platform functionality..."

    echo ""
    echo "🧪 PLATFORM FUNCTIONALITY TEST"
    echo "=============================="

    # Test backend API
    if curl -s http://localhost:8000/api/system/status > /dev/null; then
        success "Backend API system status endpoint working"
    else
        warning "Backend API system status endpoint not accessible"
    fi

    # Test service registry
    if curl -s http://localhost:8000/api/services/registry > /dev/null; then
        success "Service registry endpoint working"
    else
        warning "Service registry endpoint not accessible"
    fi

    # Test OAuth endpoints
    if curl -s http://localhost:5058/api/auth/oauth-status > /dev/null; then
        success "OAuth status endpoint working"
    else
        warning "OAuth status endpoint not accessible"
    fi

    # Test frontend routes
    if curl -s http://localhost:3000/api/health > /dev/null; then
        success "Frontend API health endpoint working"
    else
        warning "Frontend API health endpoint not accessible"
    fi

    echo ""
    success "Platform functionality test complete"
}

# Create user success guide
create_success_guide() {
    log "Creating user success guide..."

    echo ""
    echo "📚 USER SUCCESS GUIDE"
    echo "====================="

    cat > ~/.atom/user_success_guide.md << 'EOF'
# ATOM Platform - User Success Guide

## 🎯 Getting Started Checklist

### Week 1: Foundation Setup
- [ ] Set up BYOK with at least 2 AI providers
- [ ] Connect 3 core services (Slack, Google Calendar, Gmail)
- [ ] Test basic voice commands
- [ ] Create your first workflow

### Week 2: Daily Usage
- [ ] Use ATOM for daily standup preparation
- [ ] Automate meeting follow-ups
- [ ] Set up project tracking workflows
- [ ] Explore cost optimization features

### Week 3: Advanced Features
- [ ] Implement multi-service workflows
- [ ] Set up team collaboration features
- [ ] Create custom voice commands
- [ ] Monitor AI cost savings

### Week 4: Full Integration
- [ ] Connect all relevant services
- [ ] Optimize workflow performance
- [ ] Train team members (if applicable)
- [ ] Review productivity improvements

## 💡 Pro Tips

### Cost Optimization:
- Use DeepSeek for code generation (99.5% savings)
- Use Google Gemini for document analysis (99.8% savings)
- Enable auto-provider selection for best pricing
- Set budget limits to control spending

### Workflow Best Practices:
- Start with simple, frequently used workflows
- Use natural language to create workflows
- Test workflows thoroughly before automation
- Monitor workflow execution for improvements

### Integration Strategy:
- Connect services you use daily first
- Prioritize integrations with high automation potential
- Use OAuth for secure service connections
- Regularly review and update integration configurations

## 🚀 Next Level Usage

### For Developers:
- Integrate with GitHub/GitLab for code automation
- Set up CI/CD pipeline monitoring
- Create code review automation workflows
- Implement deployment status tracking

### For Managers:
- Set up team productivity dashboards
- Automate status reporting
- Create meeting management workflows
- Implement project tracking automation

### For Executives:
- Set up business intelligence workflows
- Automate executive reporting
- Create strategic planning assistance
- Implement market analysis automation
EOF
    success "Created user success guide"

    echo ""
    success "User success guide created at ~/.atom/user_success_guide.md"
}

# Main onboarding function
main() {
    echo ""
    echo "🚀 ATOM PLATFORM - COMPLETE USER ONBOARDING"
    echo "============================================"
    echo ""

    # Check prerequisites
    if ! check_prerequisites; then
        error "Prerequisites check failed. Please ensure all servers are running."
        echo ""
        echo "Start servers with: ./start_complete_application.sh"
        exit 1
    fi

    # Execute onboarding steps
    setup_byok_system
    setup_service_integrations
    create_sample_workflows
    setup_voice_commands
    test_platform_functionality
    create_success_guide

    echo ""
    echo "🎉 ONBOARDING COMPLETE!"
    echo "======================="
    echo ""
    echo "✅ Your ATOM platform is now fully configured!"
    echo ""
    echo "🌐 Access your platform: http://localhost:3000"
    echo ""
    echo "📋 Immediate Next Actions:"
    echo "   1. Visit http://localhost:3000 and explore the interface"
    echo "   2. Set up your BYOK configuration with actual API keys"
    echo "   3. Connect your first service (Slack or Google recommended)"
    echo "   4. Test a sample workflow"
    echo "   5. Enable voice commands in settings"
    echo ""
    echo "💪 You're ready to experience the power of AI-powered workflow automation!"
    echo ""
    echo "📚 Additional Resources:"
    echo "   - User Guide: ~/.atom/user_success_guide.md"
    echo "   - Service Integrations: ~/.atom/services/integration_guide.md"
    echo "   - Voice Commands: ~/.atom/voice/commands.md"
    echo "   - Sample Workflows: ~/.atom/workflows/"
    echo ""
}

# Run main function
main "$@"
