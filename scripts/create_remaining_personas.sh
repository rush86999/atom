#!/bin/bash

# 🚀 ATOM Platform - Create Remaining Persona Onboarding Scripts
# Completes the set of 10 persona onboarding scripts

set -e  # Exit on any error

echo "🚀 Creating remaining persona onboarding scripts..."
echo "=================================================="

# Small Business Owner Onboarding
cat > ../onboarding/scripts/onboard_small_business_owner.sh << 'EOF'
#!/bin/bash
echo "👨‍💼 Small Business Owner Onboarding"
echo "=================================="
echo ""
echo "Welcome to ATOM Platform! Let's set up your business operations."
echo ""

# Step 1: Business Communication
echo "💬 Step 1: Business Communication"
echo "Setting up customer communication hub..."
curl -X POST http://localhost:5058/api/messages/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "business_owner_001",
    "email_accounts": ["info@company.com", "sales@company.com"],
    "phone_numbers": ["+1234567890"]
  }'

# Step 2: Financial Integration
echo ""
echo "💰 Step 2: Financial Management"
echo "Connecting accounting systems..."
curl -X POST http://localhost:5058/api/services/quickbooks/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "business_owner_001", "company": "My Business LLC"}'

# Step 3: Operations Automation
echo ""
echo "⚙️ Step 3: Operations Automation"
echo "Setting up business workflows..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "business_owner_001",
    "workflows": [
      {
        "name": "Customer Onboarding",
        "trigger": "new_customer_signed_up",
        "actions": ["send_welcome_email", "create_account", "schedule_followup"]
      },
      {
        "name": "Invoice Processing",
        "trigger": "invoice_due",
        "actions": ["send_reminder", "process_payment", "update_accounts"]
      }
    ]
  }'

# Step 4: Task Management
echo ""
echo "📋 Step 4: Task Management"
echo "Creating operational task system..."
curl -X POST http://localhost:5058/api/tasks/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "business_owner_001",
    "categories": ["operations", "sales", "finance", "customer_service"]
  }'

echo ""
echo "✅ Small Business Owner onboarding complete!"
echo "Access your business dashboard at: http://localhost:3000"
EOF

# Project Manager Onboarding
cat > ../onboarding/scripts/onboard_project_manager.sh << 'EOF'
#!/bin/bash
echo "👨‍💼 Project Manager Onboarding"
echo "============================="
echo ""
echo "Welcome to ATOM Platform! Let's set up your project management system."
echo ""

# Step 1: Project Tool Integration
echo "📊 Step 1: Project Tool Integration"
echo "Connecting project management platforms..."
curl -X POST http://localhost:5058/api/services/trello/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "project_manager_001", "boards": ["main-project", "backlog"]}'

curl -X POST http://localhost:5058/api/services/asana/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "project_manager_001", "projects": ["product-launch", "q1-goals"]}'

# Step 2: Team Coordination
echo ""
echo "👥 Step 2: Team Coordination"
echo "Setting up team communication..."
curl -X POST http://localhost:5058/api/services/slack/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "project_manager_001", "channels": ["#projects", "#updates"]}'

# Step 3: Project Workflows
echo ""
echo "🔄 Step 3: Project Workflows"
echo "Creating project automation..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "project_manager_001",
    "workflows": [
      {
        "name": "Status Reporting",
        "trigger": "friday_9am",
        "actions": ["collect_updates", "generate_report", "send_to_stakeholders"]
      },
      {
        "name": "Risk Monitoring",
        "trigger": "task_delayed",
        "actions": ["notify_manager", "adjust_timeline", "update_stakeholders"]
      }
    ]
  }'

# Step 4: Resource Management
echo ""
echo "📈 Step 4: Resource Management"
echo "Setting up resource tracking..."
curl -X POST http://localhost:5058/api/tasks/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "project_manager_001",
    "tracking": ["hours", "budget", "milestones", "risks"]
  }'

echo ""
echo "✅ Project Manager onboarding complete!"
echo "Access your project dashboard at: http://localhost:3000"
EOF

# Student Researcher Onboarding
cat > ../onboarding/scripts/onboard_student_researcher.sh << 'EOF'
#!/bin/bash
echo "👩‍🎓 Student Researcher Onboarding"
echo "================================"
echo ""
echo "Welcome to ATOM Platform! Let's set up your research workflow."
echo ""

# Step 1: Research Organization
echo "📚 Step 1: Research Organization"
echo "Setting up document management..."
curl -X POST http://localhost:5058/api/services/google_drive/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "researcher_001", "folders": ["research-papers", "data", "drafts"]}'

curl -X POST http://localhost:5058/api/services/dropbox/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "researcher_001", "folders": ["backup", "shared-research"]}'

# Step 2: Academic Schedule
echo ""
echo "📅 Step 2: Academic Schedule"
echo "Setting up academic calendar..."
curl -X POST http://localhost:5058/api/calendar/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "researcher_001",
    "academic_calendar": true,
    "deadlines": ["proposal", "data-collection", "paper-submission"]
  }'

# Step 3: Research Workflows
echo ""
echo "🔬 Step 3: Research Workflows"
echo "Creating research automation..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "researcher_001",
    "workflows": [
      {
        "name": "Literature Review",
        "trigger": "new_paper_added",
        "actions": ["categorize_paper", "extract_key_points", "update_bibliography"]
      },
      {
        "name": "Data Analysis",
        "trigger": "data_collection_complete",
        "actions": ["run_analysis", "generate_charts", "update_findings"]
      }
    ]
  }'

# Step 4: Collaboration Setup
echo ""
echo "🤝 Step 4: Collaboration Setup"
echo "Setting up research collaboration..."
curl -X POST http://localhost:5058/api/services/slack/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "researcher_001", "channels": ["#research-group", "#lab-updates"]}'

echo ""
echo "✅ Student Researcher onboarding complete!"
echo "Access your research hub at: http://localhost:3000"
EOF

# Sales Professional Onboarding
cat > ../onboarding/scripts/onboard_sales_professional.sh << 'EOF'
#!/bin/bash
echo "👨‍💼 Sales Professional Onboarding"
echo "================================"
echo ""
echo "Welcome to ATOM Platform! Let's set up your sales pipeline."
echo ""

# Step 1: CRM Integration
echo "📊 Step 1: CRM Integration"
echo "Connecting sales platforms..."
curl -X POST http://localhost:5058/api/services/salesforce/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "sales_001", "objects": ["leads", "opportunities", "accounts"]}'

curl -X POST http://localhost:5058/api/services/hubspot/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "sales_001", "pipelines": ["inbound", "outbound"]}'

# Step 2: Communication Setup
echo ""
echo "💬 Step 2: Communication Setup"
echo "Setting up customer communication..."
curl -X POST http://localhost:5058/api/messages/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sales_001",
    "email_accounts": ["sales@company.com"],
    "tracking": ["opens", "clicks", "responses"]
  }'

# Step 3: Sales Workflows
echo ""
echo "🎯 Step 3: Sales Workflows"
echo "Creating sales automation..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sales_001",
    "workflows": [
      {
        "name": "Lead Follow-up",
        "trigger": "new_lead_created",
        "actions": ["send_welcome_email", "schedule_call", "assign_to_rep"]
      },
      {
        "name": "Deal Closing",
        "trigger": "opportunity_won",
        "actions": ["generate_contract", "notify_team", "update_forecast"]
      }
    ]
  }'

# Step 4: Performance Tracking
echo ""
echo "📈 Step 4: Performance Tracking"
echo "Setting up sales analytics..."
curl -X POST http://localhost:5058/api/analytics/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "sales_001",
    "metrics": ["conversion_rate", "pipeline_value", "deal_velocity"]
  }'

echo ""
echo "✅ Sales Professional onboarding complete!"
echo "Access your sales dashboard at: http://localhost:3000"
EOF

# Freelance Consultant Onboarding
cat > ../onboarding/scripts/onboard_freelance_consultant.sh << 'EOF'
#!/bin/bash
echo "👩‍💼 Freelance Consultant Onboarding"
echo "=================================="
echo ""
echo "Welcome to ATOM Platform! Let's set up your consulting business."
echo ""

# Step 1: Client Management
echo "👥 Step 1: Client Management"
echo "Setting up client organization..."
curl -X POST http://localhost:5058/api/services/notion/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "consultant_001", "databases": ["clients", "projects", "invoices"]}'

# Step 2: Time & Billing
echo ""
echo "⏰ Step 2: Time & Billing"
echo "Setting up time tracking and invoicing..."
curl -X POST http://localhost:5058/api/services/quickbooks/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "consultant_001", "invoicing": true}'

# Step 3: Project Workflows
echo ""
echo "🔄 Step 3: Project Workflows"
echo "Creating consulting workflows..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "consultant_001",
    "workflows": [
      {
        "name": "Client Onboarding",
        "trigger": "new_client_signed",
        "actions": ["send_contract", "setup_project", "schedule_kickoff"]
      },
      {
        "name": "Invoice Generation",
        "trigger": "month_end",
        "actions": ["track_time", "generate_invoice", "send_to_client"]
      }
    ]
  }'

# Step 4: Communication Setup
echo ""
echo "💬 Step 4: Communication Setup"
echo "Setting up client communication..."
curl -X POST http://localhost:5058/api/messages/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "consultant_001",
    "email_accounts": ["consulting@company.com"],
    "client_portal": true
  }'

echo ""
echo "✅ Freelance Consultant onboarding complete!"
echo "Access your consulting dashboard at: http://localhost:3000"
EOF

# IT Administrator Onboarding
cat > ../onboarding/scripts/onboard_it_administrator.sh << 'EOF'
#!/bin/bash
echo "👨‍💻 IT Administrator Onboarding"
echo "=============================="
echo ""
echo "Welcome to ATOM Platform! Let's set up your IT management system."
echo ""

# Step 1: System Monitoring
echo "🔍 Step 1: System Monitoring"
echo "Setting up infrastructure monitoring..."
curl -X POST http://localhost:5058/api/services/github/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "it_admin_001", "repositories": ["infrastructure", "monitoring"]}'

# Step 2: Team Coordination
echo ""
echo "👥 Step 2: Team Coordination"
echo "Setting up team communication..."
curl -X POST http://localhost:5058/api/services/slack/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "it_admin_001", "channels": ["#alerts", "#incidents", "#maintenance"]}'

# Step 3: Incident Management
echo ""
echo "🚨 Step 3: Incident Management"
echo "Creating incident response workflows..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "it_admin_001",
    "workflows": [
      {
        "name": "System Alert",
        "trigger": "high_cpu_usage",
        "actions": ["notify_team", "create_ticket", "scale_resources"]
      },
      {
        "name": "Security Incident",
        "trigger": "security_breach_detected",
        "actions": ["lockdown_systems", "notify_security", "start_investigation"]
      }
    ]
  }'

# Step 4: Documentation
echo ""
echo "📋 Step 4: Documentation Setup"
echo "Setting up knowledge base..."
curl -X POST http://localhost:5058/api/services/notion/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "it_admin_001", "databases": ["runbooks", "procedures", "incidents"]}'

echo ""
echo "✅ IT Administrator onboarding complete!"
echo "Access your IT dashboard at: http://localhost:3000"
EOF

# Content Creator Onboarding
cat > ../onboarding/scripts/onboard_content_creator.sh << 'EOF'
#!/bin/bash
echo "👩‍🎨 Content Creator Onboarding"
echo "=============================="
echo ""
echo "Welcome to ATOM Platform! Let's set up your content creation workflow."
echo ""

# Step 1: Content Platforms
echo "📱 Step 1: Content Platform Integration"
echo "Connecting social media and publishing platforms..."
curl -X POST http://localhost:5058/api/services/twitter/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "creator_001", "accounts": ["@personal", "@brand"]}'

curl -X POST http://localhost:5058/api/services/youtube/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "creator_001", "channels": ["main-channel"]}'

curl -X POST http://localhost:5058/api/services/wordpress/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "creator_001", "blogs": ["personal-blog"]}'

# Step 2: Content Calendar
echo ""
echo "📅 Step 2: Content Calendar"
echo "Setting up content scheduling..."
curl -X POST http://localhost:5058/api/calendar/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "creator_001",
    "content_calendar": true,
    "platforms": ["twitter", "youtube", "blog"]
  }'

# Step 3: Content Workflows
echo ""
echo "🔄 Step 3: Content Workflows"
echo "Creating content automation..."
curl -X POST http://localhost:5058/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "creator_001",
    "workflows": [
      {
        "name": "Content Distribution",
        "trigger": "content_published",
        "actions": ["share_twitter", "notify_subscribers", "update_newsletter"]
      },
      {
        "name": "Engagement Tracking",
        "trigger": "new_comment",
        "actions": ["notify_creator", "respond_comment", "update_analytics"]
      }
    ]
  }'

# Step 4: Analytics Setup
echo ""
echo "📊 Step 4: Analytics Setup"
echo "Setting up performance tracking..."
curl -X POST http://localhost:5058/api/analytics/setup \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "creator_001",
    "metrics": ["views", "engagement", "growth", "revenue"]
  }'

echo ""
echo "✅ Content Creator onboarding complete!"
echo "Access your content dashboard at: http://localhost:3000"
EOF

# Make all scripts executable
chmod +x ../onboarding/scripts/onboard_*.sh

echo "✅ All 10 persona onboarding scripts created successfully!"
echo ""
echo "📋 Complete Persona List:"
echo "   - Executive Assistant"
echo "   - Software Developer"
echo "   - Marketing Manager"
echo "   - Small Business Owner"
echo "   - Project Manager"
echo "   - Student Researcher"
echo "   - Sales Professional"
echo "   - Freelance Consultant"
echo "   - IT Administrator"
echo "   - Content Creator"
echo ""
echo "🚀 Ready for user onboarding with 10 personas and 182 services!"
