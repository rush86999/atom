/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { Agent, CalendarEvent, Task, CommunicationsMessage, Integration, Workflow, UserProfile, VoiceCommand, DevProject, Note, Transaction, Budget, DocContent, NewsItem, HealthMetrics, AgentLog, IntegrationConfig } from './types';

export const AGENTS_DATA: Agent[] = [
    { id: 'agent-1', name: 'Scheduler', role: 'calendar_management', status: 'online', capabilities: ['schedule_meeting', 'find_availability', 'send_invites'], performance: { tasksCompleted: 132, successRate: 98, avgResponseTime: 450 } },
    { id: 'agent-2', name: 'Researcher', role: 'information_retrieval', status: 'online', capabilities: ['web_search', 'summarize_document', 'fact_checking'], performance: { tasksCompleted: 89, successRate: 95, avgResponseTime: 1200 } },
    { id: 'agent-3', name: 'Communicator', role: 'email_and_messaging', status: 'busy', capabilities: ['draft_email', 'reply_to_message', 'set_reminder'], performance: { tasksCompleted: 215, successRate: 99, avgResponseTime: 300 } },
    { id: 'agent-4', name: 'Coder', role: 'software_development', status: 'offline', capabilities: ['write_code', 'debug_error', 'refactor_component'], performance: { tasksCompleted: 45, successRate: 92, avgResponseTime: 2500 } },
];

export const getCalendarEventsForMonth = (year: number, month: number): CalendarEvent[] => {
    const events: CalendarEvent[] = [];
    const today = new Date();
    // Ensure we are in the correct month and year for today's events.
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();

    if (year === currentYear && month === currentMonth) {
        const dateForToday = today.getDate();
        events.push({ id: 'event-1', title: 'Team Standup', startTime: new Date(year, month, dateForToday, 9, 0).toISOString(), endTime: new Date(year, month, dateForToday, 9, 15).toISOString(), color: 'blue' });
        events.push({ id: 'event-2', title: 'Project Sync', startTime: new Date(year, month, dateForToday, 14, 0).toISOString(), endTime: new Date(year, month, dateForToday, 15, 0).toISOString(), color: 'green' });
    }
    
    // Add some other events for the month
    events.push({ id: 'event-3', title: 'Design Review', startTime: new Date(year, month, 15, 11, 0).toISOString(), endTime: new Date(year, month, 15, 12, 30).toISOString(), color: 'purple' });
    events.push({ id: 'event-4', title: 'Lunch with Alex', startTime: new Date(year, month, 5, 12, 30).toISOString(), endTime: new Date(year, month, 5, 13, 30).toISOString(), color: 'orange' });
    events.push({ id: 'event-5', title: 'Client Call', startTime: new Date(year, month, 22, 16, 0).toISOString(), endTime: new Date(year, month, 22, 16, 30).toISOString(), color: 'red' });
    
    return events.filter(e => new Date(e.startTime).getMonth() === month && new Date(e.startTime).getFullYear() === year);
};

export const TASKS_DATA: Task[] = [
    { id: 'task-1', title: 'Finalize Q3 report', description: 'Compile all department data and create the final presentation slides.', status: 'in_progress', priority: 'critical', dueDate: new Date(new Date().setDate(new Date().getDate() + 2)).toISOString(), isImportant: true, assignee: 'Alex Doe', tags: ['work', 'reports'], subtasks: [{ id: 'sub-1', title: 'Gather data', completed: true }, { id: 'sub-2', title: 'Create slides', completed: false }] },
    { id: 'task-2', title: 'Prepare for client demo', description: 'Set up the demo environment and run through the presentation script.', status: 'pending', priority: 'high', dueDate: new Date(new Date().setDate(new Date().getDate() + 5)).toISOString(), isImportant: false, assignee: 'Alex Doe', tags: ['work', 'demo'], subtasks: [] },
    { id: 'task-3', title: 'Review PR #245', description: 'Check the new authentication flow implementation.', status: 'pending', priority: 'medium', dueDate: new Date(new Date().setDate(new Date().getDate() + 1)).toISOString(), isImportant: false, assignee: 'Alex Doe', tags: ['work', 'code'], subtasks: [] },
    { id: 'task-4', title: 'Submit expense report', description: 'Upload receipts for last week\'s travel.', status: 'completed', priority: 'low', dueDate: new Date(new Date().setDate(new Date().getDate() - 3)).toISOString(), isImportant: false, assignee: 'Alex Doe', tags: ['work', 'finance'], subtasks: [] },
    { id: 'task-5', title: 'Onboard new hire', description: 'Walk through the codebase and project structure.', status: 'in_progress', priority: 'high', dueDate: new Date(new Date().setDate(new Date().getDate() + 7)).toISOString(), isImportant: true, assignee: 'Alex Doe', tags: ['work', 'hr'], subtasks: [{ id: 'sub-3', title: 'Introduce to team', completed: true }, { id: 'sub-4', title: 'Show codebase', completed: false }] },
];

export const COMMUNICATIONS_DATA: CommunicationsMessage[] = [
    { id: 'msg-1', platform: 'gmail', from: { name: 'Sarah Lee' }, subject: 'Re: Project Alpha Update', preview: 'Thanks for the update! The new designs look great. I have a few questions about...', timestamp: new Date(new Date().setHours(new Date().getHours() - 1)).toISOString(), unread: true, read: false, body: 'Full body of the email from Sarah Lee.' },
    { id: 'msg-2', platform: 'slack', from: { name: 'John Doe' }, subject: '#general', preview: 'Hey team, just a reminder about the all-hands meeting tomorrow at 10 AM.', timestamp: new Date(new Date().setHours(new Date().getHours() - 3)).toISOString(), unread: false, read: true, body: 'Full body of the slack message from John Doe.' },
    { id: 'msg-3', platform: 'teams', from: { name: 'Marketing Team' }, subject: 'Q4 Campaign Ideas', preview: 'Let\'s brainstorm some ideas for the upcoming holiday campaign. Please add your thoughts to the doc.', timestamp: new Date(new Date().setDate(new Date().getDate() - 1)).toISOString(), unread: false, read: true, body: 'Full body of the teams message.' },
    { id: 'msg-4', platform: 'gmail', from: { name: 'Support' }, subject: 'Your ticket has been updated', preview: 'The issue you reported has been resolved. Please let us know if you have any other questions.', timestamp: new Date().toISOString(), unread: true, read: false, body: 'Full body of the support email.' },
];

export const INTEGRATIONS_DATA: Integration[] = [
    // Communication & Collaboration
    { id: 'int-gmail', displayName: 'Gmail', serviceType: 'gmail', category: 'Communication & Collaboration', connected: true, lastSync: new Date().toISOString(), syncStatus: 'success', devStatus: 'implemented' },
    { id: 'int-outlook', displayName: 'Outlook', serviceType: 'outlook', category: 'Communication & Collaboration', connected: false, devStatus: 'implemented' },
    { id: 'int-slack', displayName: 'Slack', serviceType: 'slack', category: 'Communication & Collaboration', connected: true, lastSync: new Date(new Date().setMinutes(new Date().getMinutes() - 15)).toISOString(), syncStatus: 'success', devStatus: 'implemented' },
    { id: 'int-teams', displayName: 'Microsoft Teams', serviceType: 'teams', category: 'Communication & Collaboration', connected: false, devStatus: 'implemented' },
    { id: 'int-discord', displayName: 'Discord', serviceType: 'discord', category: 'Communication & Collaboration', connected: false, devStatus: 'implemented' },
    
    // Calendar & Scheduling
    { id: 'int-gcal', displayName: 'Google Calendar', serviceType: 'google_calendar', category: 'Calendar & Scheduling', connected: true, lastSync: new Date().toISOString(), syncStatus: 'success', devStatus: 'implemented' },
    { id: 'int-ocal', displayName: 'Outlook Calendar', serviceType: 'outlook_calendar', category: 'Calendar & Scheduling', connected: false, devStatus: 'implemented' },
    { id: 'int-calendly', displayName: 'Calendly', serviceType: 'calendly', category: 'Calendar & Scheduling', connected: false, devStatus: 'implemented' },
    { id: 'int-zoom', displayName: 'Zoom', serviceType: 'zoom', category: 'Calendar & Scheduling', connected: true, devStatus: 'implemented' },
    
    // Task & Project Management
    { id: 'int-notion', displayName: 'Notion', serviceType: 'notion', category: 'Task & Project Management', connected: true, lastSync: new Date(new Date().setHours(new Date().getHours() - 4)).toISOString(), syncStatus: 'success', devStatus: 'implemented' },
    { id: 'int-trello', displayName: 'Trello', serviceType: 'trello', category: 'Task & Project Management', connected: false, devStatus: 'implemented' },
    { id: 'int-asana', displayName: 'Asana', serviceType: 'asana', category: 'Task & Project Management', connected: false, devStatus: 'implemented' },
    { id: 'int-jira', displayName: 'Jira', serviceType: 'jira', category: 'Task & Project Management', connected: false, devStatus: 'implemented' },
    
    // Finance & Accounting
    { id: 'int-plaid', displayName: 'Plaid', serviceType: 'plaid', category: 'Finance & Accounting', connected: true, devStatus: 'implemented' },
    { id: 'int-stripe', displayName: 'Stripe', serviceType: 'stripe', category: 'Finance & Accounting', connected: false, devStatus: 'implemented' },
    { id: 'int-paypal', displayName: 'PayPal', serviceType: 'paypal', category: 'Finance & Accounting', connected: false, devStatus: 'implemented' },

    // Social Media
    { id: 'int-twitter', displayName: 'Twitter / X', serviceType: 'twitter', category: 'Social Media', connected: false, devStatus: 'implemented' },
    { id: 'int-linkedin', displayName: 'LinkedIn', serviceType: 'linkedin', category: 'Social Media', connected: false, devStatus: 'implemented' },
    { id: 'int-instagram', displayName: 'Instagram', serviceType: 'instagram', category: 'Social Media', connected: false, devStatus: 'development' },

    // Development & Technical
    { id: 'int-github', displayName: 'GitHub', serviceType: 'github', category: 'Development & Technical', connected: true, lastSync: new Date(new Date().setHours(new Date().getHours() - 1)).toISOString(), syncStatus: 'success', devStatus: 'implemented' },

    // Planned Integrations
    { id: 'int-airtable', displayName: 'Airtable', serviceType: 'airtable', category: 'Planned Integrations', connected: false, devStatus: 'planned' },
    { id: 'int-whatsapp', displayName: 'WhatsApp', serviceType: 'whatsapp', category: 'Planned Integrations', connected: false, devStatus: 'planned' },
    { id: 'int-monday', displayName: 'Monday.com', serviceType: 'monday', category: 'Planned Integrations', connected: false, devStatus: 'planned' },
];


export const WORKFLOWS_DATA: Workflow[] = [
    { id: 'wf-1', name: 'Sync GitHub Issues to Jira', description: 'When a new issue is created in the "WebApp" repo, create a corresponding ticket in Jira.', enabled: true, triggers: [{ type: 'github_new_issue', config: { repo: 'WebApp' } }], actions: [{ type: 'jira_create_ticket', config: { service: 'jira', project: 'WEB' } }], executionCount: 142, lastExecuted: new Date(new Date().setHours(new Date().getHours() - 2)).toISOString() },
    { id: 'wf-2', name: 'Notify Team of High-Priority Emails', description: 'If an email from "client@example.com" arrives, send a notification to the #urgent-client Slack channel.', enabled: true, triggers: [{ type: 'gmail_new_email', config: { from: 'client@example.com' } }], actions: [{ type: 'slack_send_message', config: { platform: 'slack', channel: '#urgent-client' } }], executionCount: 33, lastExecuted: new Date(new Date().setMinutes(new Date().getMinutes() - 45)).toISOString() },
    { id: 'wf-3', name: 'Create Calendar Event from Task', description: 'When a task with a due date is assigned to me in Notion, create a calendar event for it.', enabled: false, triggers: [{ type: 'notion_new_task', config: { assignee: 'me' } }], actions: [{ type: 'google_calendar_create_event', config: { service: 'google_calendar' } }], executionCount: 0, lastExecuted: new Date(new Date().setDate(new Date().getDate() - 10)).toISOString() },
];

export const USER_PROFILE_DATA: UserProfile = {
    name: 'Alex Doe',
    email: 'alex.doe@example.com',
    preferences: {
        language: 'en-US',
        timezone: 'America/New_York',
        theme: 'light',
        notifications: {
            email: true,
            push: false,
            channels: {
                tasks: true,
                calendar: true,
                communications: false,
            }
        }
    },
    advancedSettings: {
        security: {
            twoFactorEnabled: false,
            passwordLastChanged: new Date(new Date().setMonth(new Date().getMonth() - 3)).toISOString(),
            sessionTimeout: 30,
        },
        apiKeys: {
            openai: '',
            google: '',
            github: '',
        },
        privacy: {
            dataSharing: true,
            analytics: true,
            crashReports: false,
        },
        customization: {
            dashboardLayout: 'grid',
            widgetOrder: ['schedule', 'tasks', 'inbox', 'finance', 'weather', 'news', 'health', 'clock'],
            widgets: [
                { id: 'schedule', title: 'Today\'s Schedule', visible: true, position: 0 },
                { id: 'tasks', title: 'Priority Tasks', visible: true, position: 1 },
                { id: 'inbox', title: 'Inbox Summary', visible: true, position: 2 },
                { id: 'finance', title: 'Financial Snapshot', visible: true, position: 3 },
                { id: 'weather', title: 'Current Weather', visible: true, position: 4 },
                { id: 'news', title: 'Latest News', visible: true, position: 5 },
                { id: 'health', title: 'Today\'s Health', visible: true, position: 6 },
                { id: 'productivity', title: 'Productivity Overview', visible: true, position: 7 },
                { id: 'clock', title: 'Current Time', visible: true, position: 8 },
                { id: 'quick-actions', title: 'Quick Actions', visible: true, position: 9 },
            ],
        },
    }
};
export const LANGUAGES = [{ code: 'en-US', name: 'English (United States)' }, { code: 'es-ES', name: 'Español (España)' }];
export const TIMEZONES = ['America/New_York', 'Europe/London', 'Asia/Tokyo'];

export const VOICE_COMMANDS_DATA: VoiceCommand[] = [
    { id: 'vc-1', phrase: 'What\'s on my calendar today?', description: 'Reads out your schedule for the current day.', enabled: true },
    { id: 'vc-2', phrase: 'Create a new task to...', description: 'Creates a new task with the specified title.', enabled: true },
    { id: 'vc-3', phrase: 'Send an email to [Name]', description: 'Initiates drafting an email to a contact.', enabled: true },
    { id: 'vc-4', phrase: 'Summarize my unread messages', description: 'Provides a summary of your latest unread communications.', enabled: false },
];

export const DEV_PROJECT_DATA: DevProject = {
    id: 'proj-1',
    name: 'Atom Personal Dashboard',
    status: 'building',
    progress: 15,
    liveUrl: 'https://atom-dash.dev',
    previewUrl: 'https://preview-atom-dash.dev',
    metrics: {
        performance: 92,
        mobile: 98,
        seo: 85,
        rebuildTime: 45,
    }
};

export const NOTES_DATA: Note[] = [
    { id: 'note-1', title: 'Q3 Brainstorming Session', content: 'Key takeaways:\n- Focus on user retention.\n- Explore gamification features.\n- A/B test new onboarding flow.', createdAt: '2023-10-26T10:00:00Z', updatedAt: '2023-10-26T11:30:00Z', type: 'meeting_notes', eventId: 'event-3' },
    { id: 'note-2', title: 'Project Phoenix Ideas', content: 'A complete redesign of the mobile app. Need to consider a new tech stack. Maybe React Native or Flutter?', createdAt: '2023-10-24T15:12:00Z', updatedAt: '2023-10-24T15:12:00Z', type: 'project_brief' },
    { id: 'note-3', title: 'Groceries List', content: '- Milk\n- Bread\n- Eggs\n- Coffee', createdAt: '2023-10-27T08:00:00Z', updatedAt: '2023-10-27T08:00:00Z', type: 'personal_memo' },
];

export const TRANSACTIONS_DATA: Transaction[] = [
    { id: 'txn-1', date: new Date(new Date().setDate(new Date().getDate() - 1)).toISOString(), description: 'Starbucks', amount: 5.75, category: 'other', type: 'debit' },
    { id: 'txn-2', date: new Date(new Date().setDate(new Date().getDate() - 2)).toISOString(), description: 'Salary', amount: 2500, category: 'income', type: 'credit' },
    { id: 'txn-3', date: new Date(new Date().setDate(new Date().getDate() - 3)).toISOString(), description: 'Whole Foods', amount: 85.40, category: 'groceries', type: 'debit' },
    { id: 'txn-4', date: new Date(new Date().setDate(new Date().getDate() - 4)).toISOString(), description: 'Netflix', amount: 15.99, category: 'entertainment', type: 'debit' },
];

export const BUDGETS_DATA: Budget[] = [
    { id: 'budget-1', category: 'Groceries', amount: 500, spent: 85.40 },
    { id: 'budget-2', category: 'Entertainment', amount: 100, spent: 15.99 },
    { id: 'budget-3', category: 'Utilities', amount: 150, spent: 120.50 },
    { id: 'budget-4', category: 'Transportation', amount: 80, spent: 75.00 },
];

export const DOCS_DATA: DocContent[] = [
    {
        id: 'doc-getting-started',
        title: 'Getting Started',
        content: '# Welcome to Atom\n\nThis is your personal AI assistant dashboard. Here you can manage all aspects of your digital life from a single, unified interface.\n\n## Core Features\n\n- **AI Chat:** Converse with Atom to manage tasks, schedules, and more.\n- **Integrations:** Connect your favorite services like Gmail, Slack, and Google Calendar.\n- **Workflows:** Automate repetitive tasks across your connected services.'
    },
    {
        id: 'doc-api-ref',
        title: 'API Reference',
        content: '## Chat API\n\nThe chat API allows you to programmatically interact with the Atom AI assistant.\n\n### Endpoint\n`POST /api/chat`\n\n### Request Body\n```json\n{\n  "message": "Your message here",\n  "sessionId": "optional-session-id"\n}\n```\n\n### Response\n```json\n{\n  "response": "Atom\'s reply to your message."\n}\n```'
    },
    {
        id: 'doc-integrations',
        title: 'Integrations Guide',
        content: '# Connecting Services\n\nAtom supports a wide range of integrations. To connect a new service:\n\n1. Navigate to the **Integrations** tab from the sidebar.\n2. Find the service you want to connect.\n3. Click the "Connect" button and follow the on-screen authentication prompts.\n\nOnce connected, Atom agents and workflows can access and manage data from that service.'
    },
    {
        id: 'doc-workflows',
        title: 'Workflow Automation',
        content: '# Creating a Workflow\n\nWorkflows are simple "if this, then that" rules.\n\n- **Trigger:** An event that starts the workflow (e.g., "New email in Gmail").\n- **Action:** The task to perform (e.g., "Send a message to a Slack channel").\n\nYou can create new workflows from the **Workflows** tab.'
    }
];

export const WEATHER_DATA = {
    location: 'New York, NY',
    temperature: 72,
    condition: 'Sunny',
    humidity: 45,
    windSpeed: 8,
    icon: 'sunny'
};

export const NEWS_DATA: NewsItem[] = [
    { id: 'news-1', title: 'AI Breakthrough in Natural Language Processing', summary: 'New model achieves 99% accuracy in understanding context.', source: 'TechCrunch', publishedAt: new Date(new Date().setHours(new Date().getHours() - 2)).toISOString(), url: 'https://techcrunch.com/ai-breakthrough' },
    { id: 'news-2', title: 'Stock Market Rises on Positive Economic Data', summary: 'Dow Jones up 1.5% following strong jobs report.', source: 'Bloomberg', publishedAt: new Date(new Date().setHours(new Date().getHours() - 4)).toISOString(), url: 'https://bloomberg.com/stock-market' },
    { id: 'news-3', title: 'New Space Mission Launches Successfully', summary: 'NASA\'s Artemis II mission reaches orbit without issues.', source: 'NASA News', publishedAt: new Date(new Date().setDate(new Date().getDate() - 1)).toISOString(), url: 'https://nasa.gov/artemis' },
];

export const HEALTH_DATA: HealthMetrics = {
    steps: 8500,
    sleepHours: 7.5,
    heartRate: 72,
    caloriesBurned: 2100,
};

export const AGENT_LOGS_DATA: AgentLog[] = [
    { id: 'log-1', timestamp: new Date(new Date().setMinutes(new Date().getMinutes() - 5)).toISOString(), level: 'info', message: 'Scheduler agent processed meeting request.' },
    { id: 'log-2', timestamp: new Date(new Date().setMinutes(new Date().getMinutes() - 15)).toISOString(), level: 'warning', message: 'Researcher agent encountered rate limit on web search.' },
    { id: 'log-3', timestamp: new Date(new Date().setHours(new Date().getHours() - 1)).toISOString(), level: 'error', message: 'Communicator agent failed to send email due to authentication error.' },
];

export const INTEGRATION_CONFIGS_DATA: IntegrationConfig[] = [
    { id: 'config-gmail', name: 'Gmail', connected: true, config: { email: 'alex.doe@example.com' } },
    { id: 'config-slack', name: 'Slack', connected: true, config: { workspace: 'myworkspace', token: 'xoxb-...' } },
    { id: 'config-github', name: 'GitHub', connected: true, config: { username: 'alexdoe', token: 'ghp_...' } },
];
