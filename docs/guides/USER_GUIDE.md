# Atom User Guide

## Welcome to Atom

Atom is your intelligent personal assistant that helps you manage your entire life in one place. From calendar management and task organization to financial tracking and AI-powered automation, Atom brings all your productivity tools together with advanced AI capabilities.

## Getting Started

### First Time Setup

1. **Account Creation**
   - Visit `/auth/signup` to create an account
   - Sign up with email and password (minimum 8 characters)
   - Or use social login: Google or GitHub
   - Complete the onboarding wizard to configure your preferences
   - Connect your essential services (calendar, email, etc.)

2. **Sign In Options**
   - Email and password
   - Google OAuth
   - GitHub OAuth
   - Forgot password? Use the password reset flow

3. **Dashboard Overview**
   - Access the main dashboard for an overview of your day
   - View upcoming events, pending tasks, and recent messages
   - Monitor connected services and system status

3. **Basic Navigation**
   - Use the main tabs: Overview, Workflow Automation, Service Integrations, Service Management
   - Access specialized pages: Calendar, Tasks, Communication, Finance, Agents, Automations, Voice

## Core Features

### 📅 Calendar Management

**Smart Scheduling**
- Create and manage events with natural language input
- Automatic conflict detection and resolution
- Find optimal meeting times across multiple calendars
- Set recurring events with custom patterns

**Event Templates**
- Train events to create reusable templates
- Apply consistent settings (duration, color, reminders) automatically
- Use semantic search to find similar events

**Multi-Calendar Support**
- Connect Google Calendar, Outlook Calendar, and other providers
- View all calendars in a unified interface
- Manage availability across different accounts

### ✅ Task Management

**Task Creation & Organization**
- Create tasks with priorities, due dates, and categories
- Organize tasks using Kanban boards or lists
- Set dependencies between related tasks
- Add detailed descriptions and attachments

**Project Management**
- Group tasks into projects with shared goals
- Track progress with visual indicators
- Assign tasks to team members (in team plans)
- Monitor project timelines and milestones

**Smart Prioritization**
- Automatic priority assignment based on due dates and importance
- Focus mode for high-priority tasks
- Daily task recommendations

### 🌐 Universal Communication Hub
**Atom Anywhere**
- **11+ Supported Platforms**: Connect with Atom via Slack, WhatsApp, Discord, Microsoft Teams, Telegram, Google Chat, Twilio (SMS), Matrix, Facebook Messenger, Line, and Signal.
- **Standardized Messaging**: All platforms share a unified interface (`UnifiedIncomingMessage`), ensuring consistent agent behavior regardless of where you message from.

**Platform Native Commands**
- `/run [workflow_name]`: Directly trigger a specific workflow.
- `/workflow [query]`: Search for and list available workflows.
- `/agents`: Discover specialized agents currently active in your workforce.
- `/help`: Get a list of supported commands and capabilities.

**Async Feedback Loop**
- Receive real-time updates and status reports directly in your chat thread.
- Human-in-the-loop approvals can be processed directly via chat buttons or response keywords.

### 💰 Financial Dashboard

**Transaction Management**
- View all financial transactions in one dashboard
- Automatic categorization of expenses and income
- Set custom categories and rules
- Import transactions from multiple sources

**Budget Planning**
- Create and track monthly budgets
- Set spending limits by category
- Receive alerts for unusual spending
- View budget vs. actual comparisons

**Financial Insights**
- Visual charts and reports
- Spending patterns and trends
- Savings goals tracking
- Investment portfolio overview
### 🚀 Sales & CRM Intelligence

**Lead Qualification & Intake**
- Automatically ingest leads from Zoho CRM, HubSpot, and Salesforce
- AI-powered lead scoring based on firmographics and behavior
- Intelligent spam and competitor filtering
- Natural language queries like "Show me my top leads this week"

**Deal Health & Pipeline Analytics**
- Real-time health scoring for every deal in your pipeline
- Automated risk detection for stalled or inactive deals
- Weighted forecasting based on deal value and health scores
- "High-Risk Deal" alerts to focus your attention where it matters most

**Call & Meeting Automation**
- "Talk-to-Task" conversion: Summaries and action items extracted from transcripts
- Automatic creation of follow-up tasks linked to deals
- Objection tracking: Summaries of red flags and concerns raised in meetings
- Semantic search across all historical sales calls and transcripts

## Advanced Features

### 🤖 Multi-Agent System (Enhanced 2026)

**Agent Management**
- Create specialized AI agents for different tasks
- Assign roles: Personal Assistant, Research Agent, Coding Agent, Data Analyst, etc.
- Configure agent capabilities and permissions
- Monitor agent performance and activity

**Agent Maturity Levels (4-Tier Governance)** ✨ NEW
- **STUDENT**: Read-only access (charts, markdown presentations)
- **INTERN**: Streaming and form presentations (requires approval for state changes)
- **SUPERVISED**: Full access with real-time supervision monitoring
- **AUTONOMOUS**: Complete independence, no oversight required

**Agent Graduation** ✨ ENHANCED
- Experience-driven promotion based on quality, not just episode count
- 20% improvement in graduation accuracy with POMDP memory framework
- Canvas feedback contributes to graduation criteria
- Intervention rate trajectory analysis for fair assessment

**Example**:
```
You: "Atom, create a research agent for competitive analysis."
Atom: "Creating new agent 'CompetitiveAnalyst' with STUDENT maturity.
The agent can present charts and summaries but cannot modify data.
As it learns from your feedback, it will graduate to higher maturity levels."
```

**Enhanced Coordination (2026)** ✨ NEW
- **Conductor Agent**: Orchestrates complex workflows with 5 execution strategies
  - SEQUENTIAL: Step-by-step execution
  - PARALLEL: Concurrent task execution
  - HYBRID: Mixed sequential and parallel
  - ADAPTIVE: Adjusts based on feedback
  - ROLLBACK_SAFE: Automatic recovery on errors
- **Event Bus**: Real-time event-driven workflow triggering
- **Workflow Templates**: 8 composition primitives for common patterns

### 🧠 Episodic Memory (Enhanced 2026) ✨ NEW

**Memory Framework**
- **POMDP (Partially Observable Markov Decision Process)**: Formal memory-as-learning framework
- **Write-Manage-Read Loop**: Structured memory creation, management, and retrieval
- **Quality-Weighted Episodes**: High-quality experiences weighted more heavily
- **Memory Consolidation**: Overnight processing (inspired by human sleep)

**Memory Retrieval Modes**
- **Temporal**: Recent episodes first
- **Semantic**: Vector similarity search
- **Sequential**: Episode chains with context
- **Contextual**: Situation-aware retrieval

**Canvas-Enhanced Memory** ✨ ENHANCED
- Canvases automatically linked to episodes
- User feedback on presentations improves future retrieval
- Canvas engagement patterns influence learning

**Example**:
```
You: "Atom, what did I decide about the Q4 budget?"
Atom: "Based on Episode #45 (Budget Meeting, Oct 15): You approved $50K for
marketing with the condition to review results in 30 days. [Canvas shows
the original budget chart you presented and approved]"
```

### 🔍 Knowledge Graph & GraphRAG (Enhanced 2026) ✨ NEW

**Multi-Hop Query Expansion**
- Trace relationships across multiple entities
- Cue-driven activation for relevant information
- Configurable hop depth limits

**Dynamic Graph Construction**
- Incremental updates (no full rebuild required)
- Temporal graph evolution tracking
- Graph versioning for rollback capability

**Community Detection**
- Leiden algorithm for entity clustering
- Community-based summarization
- Optimized query performance using clusters

**Example**:
```
You: "Show me how the Q4 budget connects to marketing results."
Atom: "Tracing relationships: Budget → (hop 1) → Marketing Campaign →
(hop 2) → Customer Acquisition → (hop 3) → Revenue Impact. [Canvas shows
connected knowledge graph with 7 related entities]"
```

### 🔌 Deep Integrations (35+)

**Communication**
- Email: Gmail, Outlook
- Chat: Slack, Microsoft Teams, Discord
- Social: Twitter, LinkedIn

**Productivity**
- Task Management: Notion, Trello, Asana, Jira
- File Storage: Google Drive, Dropbox, OneDrive, Box
- Calendar: Google Calendar, Outlook Calendar

**Finance**
- Banking: Plaid integration
- Accounting: QuickBooks, Xero
- Payments: Stripe, PayPal

**CRM & Business**
- CRM: Salesforce, HubSpot
- E-commerce: Shopify
- Development: GitHub

### ⚙️ Automation Workflows

**Visual Workflow Editor**
- Create automation workflows with drag-and-drop interface
- Connect triggers, actions, and conditions
- Build complex multi-step automations
- Test workflows before activation

**Trigger Configuration**
- Set up triggers from various sources:
  - Calendar events
  - Email messages
  - Task completions
  - Time-based schedules
  - Webhook events
  - Voice commands

**Workflow Monitoring**
- Real-time execution tracking
- Error handling and retry logic
- Performance analytics
- Execution history and logs

### 🎤 Voice & AI Features

**Voice Commands**
- Use natural language to control Atom
- Common commands:
  - "Open calendar" - Navigate to calendar view
  - "Create task" - Add new task
  - "Check messages" - View recent communications
  - "Show finances" - Open financial dashboard
  - "Start workflow" - Trigger automation

**Wake Word Detection**
- Hands-free activation with wake word "Atom"
- Continuous listening in web version
- Event-based activation in desktop version
- Privacy-focused audio processing

**AI Chat Interface**
- Natural conversation with AI assistant
- Context-aware responses
- Multi-session chat management
- File attachments and processing
- Model selection and configuration

## Service Integrations

### Available Integrations

**Communication**
- Email: Gmail, Outlook
- Chat: Slack, Microsoft Teams, Discord
- Social: Twitter, LinkedIn

**Productivity**
- Task Management: Notion, Trello, Asana, Jira
- File Storage: Google Drive, Dropbox, OneDrive, Box
- Calendar: Google Calendar, Outlook Calendar

**Finance**
- Banking: Plaid integration
- Accounting: QuickBooks, Xero
- Payments: Stripe, PayPal

**CRM & Business**
- CRM: Salesforce, HubSpot
- E-commerce: Shopify
- Development: GitHub

### Integration Setup

1. **Access Settings**
   - Navigate to Service Management
   - Select the service you want to connect
   - Follow the OAuth authorization flow

2. **Configuration**
   - Set sync preferences and frequency
   - Configure data access permissions
   - Test connection and verify data flow

3. **Management**
   - Monitor sync status and errors
   - Revoke access when needed
   - Update configuration settings

## Settings & Preferences

### Personalization

**Appearance**
- Light/Dark theme selection
- Custom color schemes
- Layout preferences
- Font size and accessibility options

**Notifications**
- Email notifications for important events
- Browser push notifications
- Mobile app alerts
- Quiet hours and do-not-disturb

**Privacy & Security**
- Data retention settings
- Export personal data
- Account security options
- Connected app permissions

### Performance Optimization

**Data Management**
- Cache settings for faster loading
- Data sync frequency
- Storage usage monitoring
- Cleanup and optimization tools

**Network Settings**
- API rate limit configuration
- Offline mode preferences
- Bandwidth usage optimization

## Tips & Best Practices

### Daily Workflow

**Morning Routine**
1. Check dashboard for daily overview
2. Review and prioritize tasks
3. Schedule focus time blocks
4. Set daily intentions with AI assistant

**Throughout the Day**
- Use voice commands for quick actions
- Let automations handle routine tasks
- Monitor agent performance
- Stay on top of communications

**Evening Wrap-up**
- Review completed tasks
- Plan for tomorrow
- Check financial updates
- Archive completed conversations

### Productivity Tips

**Task Management**
- Break large projects into smaller tasks
- Use due dates and priorities effectively
- Leverage templates for recurring tasks
- Review and adjust priorities regularly

**Calendar Optimization**
- Use time blocking for focused work
- Schedule buffer time between meetings
- Set realistic time estimates
- Use event templates for consistency

**Communication Efficiency**
- Use quick replies for common responses
- Schedule messages for optimal timing
- Leverage AI for message drafting
- Archive completed conversations

## Troubleshooting

### Common Issues

**Connection Problems**
- Check internet connection
- Verify service credentials
- Review API rate limits
- Check firewall settings

**Sync Issues**
- Force manual sync from settings
- Check service status pages
- Review error logs
- Clear cache and retry

**Performance Issues**
- Close unused browser tabs
- Clear application cache
- Check system resources
- Update to latest version

### Getting Help

**Support Resources**
- In-app help and documentation
- Community forums
- Email support
- Feature requests

**Feedback**
- Use the feedback button in the app
- Report bugs with detailed descriptions
- Suggest new features and improvements
- Share success stories and use cases

## Advanced Usage

### Custom Automations

**Building Workflows**
1. Identify repetitive tasks
2. Design workflow logic
3. Test with sample data
4. Deploy and monitor

**Common Automation Patterns**
- Email to task creation
- Calendar event reminders
- Financial transaction categorization
- Communication follow-ups

### API Integration

**Developer Access**
- REST API documentation
- Webhook configuration
- Custom integration development
- Third-party app connections

**Advanced Features**
- Custom agent development
- Workflow extensions
- Data export and analysis
- System monitoring

---

## Need More Help?

- **Documentation**: Complete technical documentation available
- **Tutorials**: Step-by-step guides for all features
- **Community**: Join our user community for tips and support
- **Updates**: Check for new features and improvements regularly

Atom is constantly evolving to better serve your productivity needs. We welcome your feedback and suggestions for making Atom even more helpful in managing your life and work.