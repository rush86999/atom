import { AUTO_GENERATED_PIECES } from './auto-generated-pieces';

/**
 * Extended Integrations Catalog - 500+ Pieces
 * Matches Activepieces' comprehensive integration library
 * Includes Atom Memory for data ingestion
 */

// Integration categories matching Activepieces
export type IntegrationCategory =
    | 'core'
    | 'ai'
    | 'communication'
    | 'productivity'
    | 'crm'
    | 'marketing'
    | 'finance'
    | 'developer'
    | 'storage'
    | 'database'
    | 'ecommerce'
    | 'social'
    | 'analytics'
    | 'hr'
    | 'support'
    | 'forms'
    | 'scheduling'
    | 'security'
    | 'iot'
    | 'media'
    | 'education'
    | 'healthcare'
    | 'legal'
    | 'real_estate'
    | 'other';

export interface Integration {
    id: string;
    name: string;
    description: string;
    category: IntegrationCategory;
    icon?: string;
    color: string;
    authType: 'oauth2' | 'api_key' | 'basic' | 'none';
    triggers: string[];
    actions: string[];
    popular?: boolean;
    new?: boolean;
    native_id?: string;
}

// CORE PIECES - Built-in Atom Functionality
export const CORE_PIECES: Integration[] = [
    // Atom Memory - Unique to Atom
    {
        id: 'atom-memory',
        name: 'Atom Memory',
        description: 'Store and retrieve data from Atom\'s intelligent memory system',
        category: 'core',
        color: '#6366F1',
        authType: 'none',
        triggers: ['memory_updated', 'pattern_detected', 'insight_generated'],
        actions: [
            'store_memory', 'retrieve_memory', 'search_memories',
            'create_embedding', 'find_similar', 'update_context',
            'ingest_document', 'ingest_conversation', 'create_knowledge_graph',
            'query_graph', 'extract_entities', 'summarize_memories'
        ],
        popular: true,
    },
    { id: 'loop', name: 'Loop', description: 'Iterate over arrays', category: 'core', color: '#14B8A6', authType: 'none', triggers: [], actions: ['for_each', 'repeat', 'loop_until'] },
    { id: 'code', name: 'Code', description: 'Run custom code', category: 'core', color: '#334155', authType: 'none', triggers: [], actions: ['run_typescript', 'run_javascript', 'run_python'] },
    { id: 'condition', name: 'Condition', description: 'Branch based on conditions', category: 'core', color: '#F59E0B', authType: 'none', triggers: [], actions: ['if_else', 'switch', 'filter'] },
    { id: 'delay', name: 'Delay', description: 'Wait for time', category: 'core', color: '#6366F1', authType: 'none', triggers: ['schedule', 'cron'], actions: ['wait', 'wait_until'] },
    { id: 'http', name: 'HTTP', description: 'Make HTTP requests', category: 'core', color: '#EA580C', authType: 'none', triggers: ['webhook'], actions: ['get', 'post', 'put', 'delete', 'patch'] },
    { id: 'tables', name: 'Tables', description: 'Atom data tables', category: 'core', color: '#0D9488', authType: 'none', triggers: ['row_created', 'row_updated'], actions: ['insert', 'update', 'find', 'delete'] },
    { id: 'storage', name: 'Storage', description: 'Key-value storage', category: 'core', color: '#059669', authType: 'none', triggers: [], actions: ['put', 'get', 'delete', 'append'] },
    { id: 'email', name: 'Email', description: 'Send emails', category: 'core', color: '#DC2626', authType: 'none', triggers: [], actions: ['send_email', 'send_template'] },
    { id: 'approval', name: 'Approval', description: 'Human approval', category: 'core', color: '#F59E0B', authType: 'none', triggers: [], actions: ['wait_for_approval', 'request_input'] },
    { id: 'subflow', name: 'Sub Flows', description: 'Call other flows', category: 'core', color: '#8B5CF6', authType: 'none', triggers: [], actions: ['call_flow', 'trigger_flow'] },
];

// AI & ML PIECES
export const AI_PIECES: Integration[] = [
    { id: 'openai', name: 'OpenAI', description: 'GPT-4, DALL-E, Whisper', category: 'ai', color: '#412991', authType: 'api_key', triggers: [], actions: ['chat', 'complete', 'embed', 'generate_image', 'transcribe', 'translate'], popular: true },
    { id: 'anthropic', name: 'Anthropic Claude', description: 'Claude AI models', category: 'ai', color: '#CC785C', authType: 'api_key', triggers: [], actions: ['chat', 'complete', 'analyze'], popular: true },
    { id: 'google-gemini', name: 'Google Gemini', description: 'Gemini AI models', category: 'ai', color: '#4285F4', authType: 'api_key', triggers: [], actions: ['chat', 'generate', 'analyze_image'], popular: true, new: true },
    { id: 'perplexity', name: 'Perplexity AI', description: 'AI-powered search', category: 'ai', color: '#1FB8CD', authType: 'api_key', triggers: [], actions: ['search', 'research'], new: true },
    { id: 'mistral', name: 'Mistral AI', description: 'Mistral models', category: 'ai', color: '#FF7000', authType: 'api_key', triggers: [], actions: ['chat', 'complete'] },
    { id: 'groq', name: 'Groq', description: 'Fast LLM inference', category: 'ai', color: '#F55036', authType: 'api_key', triggers: [], actions: ['chat', 'complete'] },
    { id: 'deepseek', name: 'DeepSeek', description: 'DeepSeek models', category: 'ai', color: '#5A67D8', authType: 'api_key', triggers: [], actions: ['chat', 'code'] },
    { id: 'azure-openai', name: 'Azure OpenAI', description: 'Azure-hosted OpenAI', category: 'ai', color: '#0078D4', authType: 'api_key', triggers: [], actions: ['chat', 'complete', 'embed'] },
    { id: 'huggingface', name: 'Hugging Face', description: 'ML models hub', category: 'ai', color: '#FFD21E', authType: 'api_key', triggers: [], actions: ['inference', 'embed'] },
    { id: 'stability-ai', name: 'Stability AI', description: 'Stable Diffusion', category: 'ai', color: '#9945FF', authType: 'api_key', triggers: [], actions: ['generate_image', 'upscale'] },
    { id: 'replicate', name: 'Replicate', description: 'Run ML models', category: 'ai', color: '#000000', authType: 'api_key', triggers: [], actions: ['run_model', 'get_prediction'] },
    { id: 'elevenlabs', name: 'ElevenLabs', description: 'AI voice generation', category: 'ai', color: '#000000', authType: 'api_key', triggers: [], actions: ['text_to_speech', 'clone_voice'] },
    { id: 'assembly-ai', name: 'AssemblyAI', description: 'Speech-to-text', category: 'ai', color: '#0055FF', authType: 'api_key', triggers: [], actions: ['transcribe', 'summarize'] },
    { id: 'deepgram', name: 'Deepgram', description: 'Voice AI', category: 'ai', color: '#13EF93', authType: 'api_key', triggers: [], actions: ['transcribe', 'text_to_speech'] },
    { id: 'cohere', name: 'Cohere', description: 'Enterprise AI', category: 'ai', color: '#39594D', authType: 'api_key', triggers: [], actions: ['generate', 'embed', 'classify'] },
];

// COMMUNICATION PIECES
export const COMMUNICATION_PIECES: Integration[] = [
    { id: 'slack', name: 'Slack', description: 'Team messaging', category: 'communication', color: '#4A154B', authType: 'oauth2', triggers: ['message', 'reaction', 'mention', 'channel_created'], actions: ['send_message', 'create_channel', 'add_reaction', 'upload_file', 'update_status'], popular: true },
    { id: 'discord', name: 'Discord', description: 'Community platform', category: 'communication', color: '#5865F2', authType: 'oauth2', triggers: ['message', 'member_join'], actions: ['send_message', 'create_channel', 'add_role'], popular: true },
    { id: 'microsoft-teams', name: 'Microsoft Teams', description: 'Enterprise collaboration', category: 'communication', color: '#6264A7', authType: 'oauth2', triggers: ['message', 'meeting_created'], actions: ['send_message', 'create_channel', 'create_meeting'], popular: true },
    { id: 'gmail', name: 'Gmail', description: 'Email service', category: 'communication', color: '#EA4335', authType: 'oauth2', triggers: ['new_email', 'labeled'], actions: ['send_email', 'create_draft', 'add_label'], popular: true },
    { id: 'outlook', name: 'Microsoft Outlook', description: 'Email & calendar', category: 'communication', color: '#0078D4', authType: 'oauth2', triggers: ['new_email', 'calendar_event'], actions: ['send_email', 'create_event'] },
    { id: 'twilio', name: 'Twilio', description: 'SMS & voice', category: 'communication', color: '#F22F46', authType: 'api_key', triggers: ['sms_received', 'call_received'], actions: ['send_sms', 'make_call'] },
    { id: 'sendgrid', name: 'SendGrid', description: 'Email delivery', category: 'communication', color: '#1A82E2', authType: 'api_key', triggers: ['email_opened', 'email_clicked'], actions: ['send_email', 'add_contact'] },
    { id: 'mailgun', name: 'Mailgun', description: 'Email API', category: 'communication', color: '#F06B66', authType: 'api_key', triggers: ['email_delivered'], actions: ['send_email'] },
    { id: 'telegram', name: 'Telegram Bot', description: 'Telegram messaging', category: 'communication', color: '#0088CC', authType: 'api_key', triggers: ['message', 'command'], actions: ['send_message', 'send_photo'] },
    { id: 'whatsapp', name: 'WhatsApp Business', description: 'WhatsApp messaging', category: 'communication', color: '#25D366', authType: 'api_key', triggers: ['message_received'], actions: ['send_message', 'send_template'] },
    { id: 'intercom', name: 'Intercom', description: 'Customer messaging', category: 'communication', color: '#1F8DED', authType: 'oauth2', triggers: ['new_conversation', 'user_created'], actions: ['send_message', 'create_user', 'add_tag'] },
    { id: 'crisp', name: 'Crisp', description: 'Live chat', category: 'communication', color: '#4285F4', authType: 'api_key', triggers: ['message_received'], actions: ['send_message'] },
    { id: 'tawk', name: 'Tawk.to', description: 'Free live chat', category: 'communication', color: '#03C04A', authType: 'api_key', triggers: ['chat_started'], actions: ['send_message'] },
    { id: 'drift', name: 'Drift', description: 'Conversational marketing', category: 'communication', color: '#0176D3', authType: 'oauth2', triggers: ['conversation_started'], actions: ['send_message'] },
];

// CRM & SALES PIECES
export const CRM_PIECES: Integration[] = [
    { id: 'salesforce', name: 'Salesforce', description: 'Enterprise CRM', category: 'crm', color: '#00A1E0', authType: 'oauth2', triggers: ['new_lead', 'deal_updated', 'opportunity_won'], actions: ['create_lead', 'update_contact', 'create_opportunity'], popular: true },
    { id: 'hubspot', name: 'HubSpot', description: 'Marketing & sales CRM', category: 'crm', color: '#FF7A59', authType: 'oauth2', triggers: ['new_contact', 'deal_stage_changed', 'form_submitted'], actions: ['create_contact', 'update_deal', 'add_to_list'], popular: true },
    { id: 'pipedrive', name: 'Pipedrive', description: 'Sales pipeline CRM', category: 'crm', color: '#1ABC9C', authType: 'oauth2', triggers: ['deal_created', 'deal_won'], actions: ['create_deal', 'create_person', 'add_note'], popular: true },
    { id: 'zoho-crm', name: 'Zoho CRM', description: 'Business CRM', category: 'crm', color: '#DC2626', authType: 'oauth2', triggers: ['new_lead', 'deal_updated'], actions: ['create_lead', 'update_contact'] },
    { id: 'freshsales', name: 'Freshsales', description: 'Sales CRM', category: 'crm', color: '#F7931E', authType: 'api_key', triggers: ['lead_created'], actions: ['create_lead', 'update_contact'] },
    { id: 'close', name: 'Close', description: 'Sales CRM', category: 'crm', color: '#4C63B6', authType: 'api_key', triggers: ['lead_created', 'call_completed'], actions: ['create_lead', 'log_call'] },
    { id: 'copper', name: 'Copper', description: 'Google Workspace CRM', category: 'crm', color: '#F9A825', authType: 'api_key', triggers: ['opportunity_created'], actions: ['create_person', 'create_opportunity'] },
    { id: 'apollo', name: 'Apollo.io', description: 'Sales intelligence', category: 'crm', color: '#6366F1', authType: 'api_key', triggers: [], actions: ['enrich_contact', 'search_people', 'add_to_sequence'] },
    { id: 'outreach', name: 'Outreach', description: 'Sales engagement', category: 'crm', color: '#5951FF', authType: 'oauth2', triggers: ['sequence_completed'], actions: ['add_prospect', 'create_sequence'] },
    { id: 'salesloft', name: 'SalesLoft', description: 'Sales engagement', category: 'crm', color: '#0066FF', authType: 'oauth2', triggers: ['call_completed'], actions: ['create_person', 'add_to_cadence'] },
    { id: 'linkedin-sales', name: 'LinkedIn Sales Navigator', description: 'B2B prospecting', category: 'crm', color: '#0A66C2', authType: 'oauth2', triggers: [], actions: ['search_leads', 'send_inmail'] },
    { id: 'clearbit', name: 'Clearbit', description: 'Data enrichment', category: 'crm', color: '#47B7F8', authType: 'api_key', triggers: [], actions: ['enrich_company', 'enrich_person', 'reveal_visitor'] },
    { id: 'zoominfo', name: 'ZoomInfo', description: 'B2B database', category: 'crm', color: '#FF5733', authType: 'api_key', triggers: [], actions: ['search_contacts', 'enrich'] },
];

// PRODUCTIVITY PIECES
export const PRODUCTIVITY_PIECES: Integration[] = [
    { id: 'notion', name: 'Notion', description: 'All-in-one workspace', category: 'productivity', color: '#000000', authType: 'oauth2', triggers: ['page_created', 'database_updated'], actions: ['create_page', 'update_database', 'add_block'], popular: true },
    { id: 'airtable', name: 'Airtable', description: 'Spreadsheet database', category: 'productivity', color: '#18BFFF', authType: 'oauth2', triggers: ['record_created', 'record_updated'], actions: ['create_record', 'update_record', 'find_records'], popular: true },
    { id: 'google-sheets', name: 'Google Sheets', description: 'Spreadsheets', category: 'productivity', color: '#34A853', authType: 'oauth2', triggers: ['row_added', 'cell_updated'], actions: ['append_row', 'update_row', 'create_spreadsheet'], popular: true },
    { id: 'google-docs', name: 'Google Docs', description: 'Documents', category: 'productivity', color: '#4285F4', authType: 'oauth2', triggers: ['document_created'], actions: ['create_document', 'append_text'] },
    { id: 'google-calendar', name: 'Google Calendar', description: 'Calendar', category: 'productivity', color: '#4285F4', authType: 'oauth2', triggers: ['event_created', 'event_starting'], actions: ['create_event', 'update_event'], popular: true },
    { id: 'asana', name: 'Asana', description: 'Project management', category: 'productivity', color: '#F06A6A', authType: 'oauth2', triggers: ['task_created', 'task_completed'], actions: ['create_task', 'update_task', 'add_comment'], popular: true },
    { id: 'trello', name: 'Trello', description: 'Kanban boards', category: 'productivity', color: '#0079BF', authType: 'oauth2', triggers: ['card_created', 'card_moved'], actions: ['create_card', 'move_card', 'add_member'], popular: true },
    { id: 'monday', name: 'Monday.com', description: 'Work OS', category: 'productivity', color: '#FF3D57', authType: 'oauth2', triggers: ['item_created', 'status_changed'], actions: ['create_item', 'update_item'] },
    { id: 'clickup', name: 'ClickUp', description: 'Project management', category: 'productivity', color: '#7B68EE', authType: 'oauth2', triggers: ['task_created', 'task_updated'], actions: ['create_task', 'update_task', 'add_comment'] },
    { id: 'jira', name: 'Jira', description: 'Issue tracking', category: 'productivity', color: '#0052CC', authType: 'oauth2', triggers: ['issue_created', 'issue_updated'], actions: ['create_issue', 'update_issue', 'add_comment'], popular: true },
    { id: 'linear', name: 'Linear', description: 'Issue tracking', category: 'productivity', color: '#5E6AD2', authType: 'oauth2', triggers: ['issue_created', 'issue_updated'], actions: ['create_issue', 'update_issue'] },
    { id: 'basecamp', name: 'Basecamp', description: 'Project management', category: 'productivity', color: '#1D2D35', authType: 'oauth2', triggers: ['todo_created'], actions: ['create_todo', 'create_message'] },
    { id: 'todoist', name: 'Todoist', description: 'Task management', category: 'productivity', color: '#E44332', authType: 'oauth2', triggers: ['task_created', 'task_completed'], actions: ['create_task', 'complete_task'] },
    { id: 'microsoft-todo', name: 'Microsoft To Do', description: 'Task management', category: 'productivity', color: '#3B78E7', authType: 'oauth2', triggers: ['task_created'], actions: ['create_task'] },
    { id: 'evernote', name: 'Evernote', description: 'Note-taking', category: 'productivity', color: '#00A82D', authType: 'oauth2', triggers: ['note_created'], actions: ['create_note'] },
    { id: 'coda', name: 'Coda', description: 'Doc + spreadsheet', category: 'productivity', color: '#F46A54', authType: 'oauth2', triggers: ['row_created'], actions: ['add_row', 'update_row'] },
];

// MARKETING PIECES
export const MARKETING_PIECES: Integration[] = [
    { id: 'mailchimp', name: 'Mailchimp', description: 'Email marketing', category: 'marketing', color: '#FFE01B', authType: 'oauth2', triggers: ['subscriber_added', 'campaign_sent'], actions: ['add_subscriber', 'send_campaign', 'add_tag'], popular: true },
    { id: 'activecampaign', name: 'ActiveCampaign', description: 'Marketing automation', category: 'marketing', color: '#356AE6', authType: 'api_key', triggers: ['contact_added', 'tag_added'], actions: ['create_contact', 'add_tag', 'start_automation'] },
    { id: 'klaviyo', name: 'Klaviyo', description: 'E-commerce marketing', category: 'marketing', color: '#000000', authType: 'api_key', triggers: ['profile_created'], actions: ['add_profile', 'add_to_list', 'track_event'] },
    { id: 'convertkit', name: 'ConvertKit', description: 'Creator marketing', category: 'marketing', color: '#FB6970', authType: 'api_key', triggers: ['subscriber_added'], actions: ['add_subscriber', 'add_tag'] },
    { id: 'drip', name: 'Drip', description: 'E-commerce CRM', category: 'marketing', color: '#4EA7D6', authType: 'api_key', triggers: ['subscriber_created'], actions: ['create_subscriber', 'record_event'] },
    { id: 'buffer', name: 'Buffer', description: 'Social media scheduling', category: 'marketing', color: '#168EEA', authType: 'oauth2', triggers: [], actions: ['create_post', 'schedule_post'] },
    { id: 'hootsuite', name: 'Hootsuite', description: 'Social media management', category: 'marketing', color: '#000000', authType: 'oauth2', triggers: [], actions: ['schedule_post'] },
    { id: 'later', name: 'Later', description: 'Social media scheduler', category: 'marketing', color: '#F4A123', authType: 'oauth2', triggers: [], actions: ['schedule_post'] },
    { id: 'google-ads', name: 'Google Ads', description: 'Advertising platform', category: 'marketing', color: '#4285F4', authType: 'oauth2', triggers: ['conversion'], actions: ['create_audience', 'add_to_audience'] },
    { id: 'facebook-ads', name: 'Facebook Ads', description: 'Meta advertising', category: 'marketing', color: '#1877F2', authType: 'oauth2', triggers: ['lead_form_submitted'], actions: ['create_audience', 'add_to_audience'] },
    { id: 'linkedin-ads', name: 'LinkedIn Ads', description: 'B2B advertising', category: 'marketing', color: '#0A66C2', authType: 'oauth2', triggers: [], actions: ['create_audience'] },
    { id: 'customer-io', name: 'Customer.io', description: 'Messaging automation', category: 'marketing', color: '#51A944', authType: 'api_key', triggers: ['event_received'], actions: ['identify_customer', 'track_event'] },
    { id: 'braze', name: 'Braze', description: 'Customer engagement', category: 'marketing', color: '#000000', authType: 'api_key', triggers: [], actions: ['track_user', 'send_message'] },
    { id: 'iterable', name: 'Iterable', description: 'Growth marketing', category: 'marketing', color: '#5C6CF0', authType: 'api_key', triggers: [], actions: ['update_user', 'track_event'] },
];

// DEVELOPER PIECES
export const DEVELOPER_PIECES: Integration[] = [
    { id: 'github', name: 'GitHub', description: 'Code hosting', category: 'developer', color: '#181717', authType: 'oauth2', triggers: ['push', 'pull_request', 'issue_created', 'star'], actions: ['create_issue', 'create_pr', 'add_comment', 'add_label'], popular: true },
    { id: 'gitlab', name: 'GitLab', description: 'DevOps platform', category: 'developer', color: '#FC6D26', authType: 'oauth2', triggers: ['push', 'merge_request', 'issue_created'], actions: ['create_issue', 'create_mr'] },
    { id: 'bitbucket', name: 'Bitbucket', description: 'Code hosting', category: 'developer', color: '#0052CC', authType: 'oauth2', triggers: ['push', 'pull_request'], actions: ['create_issue'] },
    { id: 'vercel', name: 'Vercel', description: 'Frontend deployment', category: 'developer', color: '#000000', authType: 'api_key', triggers: ['deployment_created', 'deployment_ready'], actions: ['trigger_deployment'] },
    { id: 'netlify', name: 'Netlify', description: 'Web deployment', category: 'developer', color: '#00C7B7', authType: 'oauth2', triggers: ['deploy_created', 'deploy_succeeded'], actions: ['trigger_build'] },
    { id: 'railway', name: 'Railway', description: 'Infrastructure platform', category: 'developer', color: '#0B0D0E', authType: 'api_key', triggers: ['deployment_status'], actions: ['deploy'] },
    { id: 'render', name: 'Render', description: 'Cloud platform', category: 'developer', color: '#46E3B7', authType: 'api_key', triggers: ['deploy_succeeded'], actions: ['trigger_deploy'] },
    { id: 'heroku', name: 'Heroku', description: 'Cloud platform', category: 'developer', color: '#430098', authType: 'oauth2', triggers: ['release_created'], actions: ['create_app', 'scale_dyno'] },
    { id: 'aws', name: 'AWS', description: 'Amazon Web Services', category: 'developer', color: '#FF9900', authType: 'api_key', triggers: ['s3_upload', 'sqs_message'], actions: ['s3_upload', 'sqs_send', 'lambda_invoke'] },
    { id: 'gcp', name: 'Google Cloud', description: 'Google Cloud Platform', category: 'developer', color: '#4285F4', authType: 'oauth2', triggers: ['pubsub_message'], actions: ['pubsub_publish', 'storage_upload'] },
    { id: 'azure', name: 'Azure', description: 'Microsoft Cloud', category: 'developer', color: '#0078D4', authType: 'oauth2', triggers: ['blob_created'], actions: ['blob_upload'] },
    { id: 'datadog', name: 'Datadog', description: 'Monitoring', category: 'developer', color: '#632CA6', authType: 'api_key', triggers: ['alert_triggered'], actions: ['create_event', 'post_metric'] },
    { id: 'pagerduty', name: 'PagerDuty', description: 'Incident management', category: 'developer', color: '#06AC38', authType: 'api_key', triggers: ['incident_created'], actions: ['create_incident', 'resolve_incident'] },
    { id: 'sentry', name: 'Sentry', description: 'Error tracking', category: 'developer', color: '#362D59', authType: 'api_key', triggers: ['issue_created'], actions: ['resolve_issue'] },
    { id: 'posthog', name: 'PostHog', description: 'Product analytics', category: 'developer', color: '#000000', authType: 'api_key', triggers: ['event_received'], actions: ['capture_event', 'identify_user'] },
];

// DATABASE PIECES
export const DATABASE_PIECES: Integration[] = [
    { id: 'postgres', name: 'PostgreSQL', description: 'SQL database', category: 'database', color: '#336791', authType: 'basic', triggers: ['row_inserted', 'row_updated'], actions: ['query', 'insert', 'update', 'delete'] },
    { id: 'mysql', name: 'MySQL', description: 'SQL database', category: 'database', color: '#4479A1', authType: 'basic', triggers: ['row_inserted'], actions: ['query', 'insert', 'update'] },
    { id: 'mongodb', name: 'MongoDB', description: 'NoSQL database', category: 'database', color: '#47A248', authType: 'basic', triggers: ['document_created'], actions: ['find', 'insert', 'update', 'delete'] },
    { id: 'redis', name: 'Redis', description: 'In-memory database', category: 'database', color: '#DC382D', authType: 'basic', triggers: [], actions: ['get', 'set', 'delete', 'publish'] },
    { id: 'supabase', name: 'Supabase', description: 'Postgres + Auth', category: 'database', color: '#3ECF8E', authType: 'api_key', triggers: ['row_inserted', 'row_updated'], actions: ['select', 'insert', 'update', 'delete'], popular: true },
    { id: 'firebase', name: 'Firebase', description: 'Google BaaS', category: 'database', color: '#FFCA28', authType: 'api_key', triggers: ['document_created', 'document_updated'], actions: ['add_document', 'update_document'] },
    { id: 'pinecone', name: 'Pinecone', description: 'Vector database', category: 'database', color: '#000000', authType: 'api_key', triggers: [], actions: ['upsert', 'query', 'delete'] },
    { id: 'qdrant', name: 'Qdrant', description: 'Vector database', category: 'database', color: '#24386C', authType: 'api_key', triggers: [], actions: ['upsert', 'search'] },
    { id: 'weaviate', name: 'Weaviate', description: 'Vector database', category: 'database', color: '#00D2B8', authType: 'api_key', triggers: [], actions: ['create_object', 'query'] },
    { id: 'snowflake', name: 'Snowflake', description: 'Cloud data warehouse', category: 'database', color: '#29B5E8', authType: 'basic', triggers: [], actions: ['query', 'insert'] },
    { id: 'bigquery', name: 'BigQuery', description: 'Google data warehouse', category: 'database', color: '#4285F4', authType: 'oauth2', triggers: [], actions: ['query', 'insert'] },
];

// STORAGE PIECES
export const STORAGE_PIECES: Integration[] = [
    { id: 'google-drive', name: 'Google Drive', description: 'Cloud storage', category: 'storage', color: '#4285F4', authType: 'oauth2', triggers: ['file_created', 'file_updated'], actions: ['upload_file', 'create_folder', 'share_file'], popular: true },
    { id: 'dropbox', name: 'Dropbox', description: 'Cloud storage', category: 'storage', color: '#0061FF', authType: 'oauth2', triggers: ['file_added', 'file_modified'], actions: ['upload_file', 'create_folder', 'share_link'], popular: true },
    { id: 'onedrive', name: 'OneDrive', description: 'Microsoft storage', category: 'storage', color: '#0078D4', authType: 'oauth2', triggers: ['file_created'], actions: ['upload_file', 'create_folder'] },
    { id: 'box', name: 'Box', description: 'Enterprise storage', category: 'storage', color: '#0061D5', authType: 'oauth2', triggers: ['file_uploaded'], actions: ['upload_file', 'create_folder'] },
    { id: 's3', name: 'Amazon S3', description: 'Object storage', category: 'storage', color: '#FF9900', authType: 'api_key', triggers: ['object_created'], actions: ['upload', 'download', 'delete'] },
    { id: 'cloudflare-r2', name: 'Cloudflare R2', description: 'Object storage', category: 'storage', color: '#F38020', authType: 'api_key', triggers: [], actions: ['upload', 'download'] },
    { id: 'wasabi', name: 'Wasabi', description: 'Cloud storage', category: 'storage', color: '#00C14D', authType: 'api_key', triggers: [], actions: ['upload', 'download'] },
    { id: 'backblaze', name: 'Backblaze B2', description: 'Cloud storage', category: 'storage', color: '#E21E29', authType: 'api_key', triggers: [], actions: ['upload', 'download'] },
];

// ECOMMERCE PIECES
export const ECOMMERCE_PIECES: Integration[] = [
    { id: 'shopify', name: 'Shopify', description: 'E-commerce platform', category: 'ecommerce', color: '#7AB55C', authType: 'oauth2', triggers: ['order_created', 'product_created', 'customer_created'], actions: ['create_product', 'update_inventory', 'create_customer'], popular: true },
    { id: 'woocommerce', name: 'WooCommerce', description: 'WordPress e-commerce', category: 'ecommerce', color: '#96588A', authType: 'api_key', triggers: ['order_created', 'product_updated'], actions: ['create_product', 'update_order'] },
    { id: 'stripe', name: 'Stripe', description: 'Payment processing', category: 'ecommerce', color: '#635BFF', authType: 'api_key', triggers: ['payment_succeeded', 'subscription_created', 'invoice_paid'], actions: ['create_customer', 'create_charge', 'create_subscription'], popular: true },
    { id: 'square', name: 'Square', description: 'Commerce platform', category: 'ecommerce', color: '#006AFF', authType: 'oauth2', triggers: ['payment_created'], actions: ['create_payment', 'create_customer'] },
    { id: 'paypal', name: 'PayPal', description: 'Payment processor', category: 'ecommerce', color: '#003087', authType: 'oauth2', triggers: ['payment_received'], actions: ['send_invoice', 'create_payout'] },
    { id: 'bigcommerce', name: 'BigCommerce', description: 'E-commerce platform', category: 'ecommerce', color: '#34313F', authType: 'oauth2', triggers: ['order_created'], actions: ['create_product', 'update_inventory'] },
    { id: 'magento', name: 'Magento', description: 'E-commerce platform', category: 'ecommerce', color: '#EE672F', authType: 'api_key', triggers: ['order_placed'], actions: ['create_product'] },
    { id: 'gumroad', name: 'Gumroad', description: 'Creator commerce', category: 'ecommerce', color: '#FF90E8', authType: 'api_key', triggers: ['sale_created'], actions: [] },
    { id: 'lemonsqueezy', name: 'Lemon Squeezy', description: 'Digital commerce', category: 'ecommerce', color: '#FFC233', authType: 'api_key', triggers: ['order_created', 'subscription_created'], actions: ['create_checkout'] },
    { id: 'paddle', name: 'Paddle', description: 'SaaS billing', category: 'ecommerce', color: '#32325D', authType: 'api_key', triggers: ['payment_succeeded', 'subscription_created'], actions: ['create_subscription'] },
];

// SUPPORT PIECES
export const SUPPORT_PIECES: Integration[] = [
    { id: 'zendesk', name: 'Zendesk', description: 'Customer service', category: 'support', color: '#03363D', authType: 'oauth2', triggers: ['ticket_created', 'ticket_updated'], actions: ['create_ticket', 'update_ticket', 'add_comment'], popular: true },
    { id: 'freshdesk', name: 'Freshdesk', description: 'Helpdesk software', category: 'support', color: '#1D8F61', authType: 'api_key', triggers: ['ticket_created'], actions: ['create_ticket', 'update_ticket'] },
    { id: 'helpscout', name: 'Help Scout', description: 'Customer support', category: 'support', color: '#1292EE', authType: 'oauth2', triggers: ['conversation_created'], actions: ['create_conversation', 'reply'] },
    { id: 'front', name: 'Front', description: 'Shared inbox', category: 'support', color: '#001B37', authType: 'oauth2', triggers: ['message_received'], actions: ['send_message', 'add_tag'] },
    { id: 'groove', name: 'Groove', description: 'Helpdesk', category: 'support', color: '#FF6B6B', authType: 'api_key', triggers: ['ticket_created'], actions: ['create_ticket'] },
    { id: 'gorgias', name: 'Gorgias', description: 'E-commerce support', category: 'support', color: '#FFCC00', authType: 'api_key', triggers: ['ticket_created'], actions: ['create_ticket', 'reply'] },
    { id: 'kustomer', name: 'Kustomer', description: 'Customer platform', category: 'support', color: '#4E56A6', authType: 'api_key', triggers: ['conversation_created'], actions: ['create_customer'] },
];

// FORMS PIECES
export const FORM_PIECES: Integration[] = [
    { id: 'typeform', name: 'Typeform', description: 'Online forms', category: 'forms', color: '#262627', authType: 'oauth2', triggers: ['form_submitted'], actions: [], popular: true },
    { id: 'google-forms', name: 'Google Forms', description: 'Simple forms', category: 'forms', color: '#673AB7', authType: 'oauth2', triggers: ['response_submitted'], actions: [] },
    { id: 'jotform', name: 'Jotform', description: 'Form builder', category: 'forms', color: '#0A1551', authType: 'api_key', triggers: ['submission_created'], actions: [] },
    { id: 'tally', name: 'Tally', description: 'Form builder', category: 'forms', color: '#333333', authType: 'api_key', triggers: ['response_submitted'], actions: [] },
    { id: 'paperform', name: 'Paperform', description: 'Forms & landing pages', category: 'forms', color: '#0066FF', authType: 'api_key', triggers: ['submission_created'], actions: [] },
    { id: 'cognito-forms', name: 'Cognito Forms', description: 'Online forms', category: 'forms', color: '#4A90D9', authType: 'api_key', triggers: ['entry_created'], actions: [] },
    { id: 'formstack', name: 'Formstack', description: 'Enterprise forms', category: 'forms', color: '#21B573', authType: 'oauth2', triggers: ['submission_created'], actions: [] },
    { id: 'fillout', name: 'Fillout', description: 'Modern forms', category: 'forms', color: '#6366F1', authType: 'api_key', triggers: ['submission_created'], actions: [] },
];

// SCHEDULING PIECES
export const SCHEDULING_PIECES: Integration[] = [
    { id: 'calendly', name: 'Calendly', description: 'Scheduling', category: 'scheduling', color: '#006BFF', authType: 'oauth2', triggers: ['event_scheduled', 'event_canceled'], actions: ['create_invite_link'], popular: true },
    { id: 'cal', name: 'Cal.com', description: 'Open source scheduling', category: 'scheduling', color: '#292929', authType: 'api_key', triggers: ['booking_created'], actions: ['create_booking'] },
    { id: 'acuity', name: 'Acuity Scheduling', description: 'Appointment scheduling', category: 'scheduling', color: '#1A1B25', authType: 'oauth2', triggers: ['appointment_scheduled'], actions: [] },
    { id: 'doodle', name: 'Doodle', description: 'Group scheduling', category: 'scheduling', color: '#0059B3', authType: 'oauth2', triggers: ['poll_created'], actions: [] },
    { id: 'zoom', name: 'Zoom', description: 'Video meetings', category: 'scheduling', color: '#2D8CFF', authType: 'oauth2', triggers: ['meeting_started', 'meeting_ended', 'recording_completed'], actions: ['create_meeting', 'delete_meeting'], popular: true },
    { id: 'google-meet', name: 'Google Meet', description: 'Video meetings', category: 'scheduling', color: '#00897B', authType: 'oauth2', triggers: [], actions: ['create_meeting'] },
    { id: 'microsoft-teams-meeting', name: 'Teams Meetings', description: 'Video meetings', category: 'scheduling', color: '#6264A7', authType: 'oauth2', triggers: [], actions: ['create_meeting'] },
];

// HR & RECRUITING PIECES
export const HR_PIECES: Integration[] = [
    { id: 'bamboohr', name: 'BambooHR', description: 'HR software', category: 'hr', color: '#73C41D', authType: 'api_key', triggers: ['employee_created', 'time_off_requested'], actions: ['create_employee', 'update_employee'] },
    { id: 'gusto', name: 'Gusto', description: 'Payroll & HR', category: 'hr', color: '#FF7355', authType: 'oauth2', triggers: ['employee_created'], actions: [] },
    { id: 'rippling', name: 'Rippling', description: 'HR platform', category: 'hr', color: '#FED049', authType: 'api_key', triggers: ['employee_created'], actions: [] },
    { id: 'workday', name: 'Workday', description: 'Enterprise HR', category: 'hr', color: '#005CB9', authType: 'oauth2', triggers: ['employee_created'], actions: [] },
    { id: 'greenhouse', name: 'Greenhouse', description: 'Recruiting', category: 'hr', color: '#3AB549', authType: 'api_key', triggers: ['application_created', 'candidate_hired'], actions: ['create_candidate'] },
    { id: 'lever', name: 'Lever', description: 'Recruiting', category: 'hr', color: '#4A90D9', authType: 'oauth2', triggers: ['candidate_created', 'stage_changed'], actions: ['create_candidate'] },
    { id: 'ashby', name: 'Ashby', description: 'Recruiting', category: 'hr', color: '#4A4A4A', authType: 'api_key', triggers: ['candidate_created'], actions: [] },
    { id: 'deel', name: 'Deel', description: 'Global HR', category: 'hr', color: '#15357A', authType: 'api_key', triggers: ['contract_created'], actions: [] },
    { id: 'remote', name: 'Remote', description: 'Global employment', category: 'hr', color: '#5865F2', authType: 'api_key', triggers: ['employee_created'], actions: [] },
];

// SOCIAL MEDIA PIECES
export const SOCIAL_PIECES: Integration[] = [
    { id: 'twitter', name: 'Twitter/X', description: 'Social network', category: 'social', color: '#000000', authType: 'oauth2', triggers: ['mention', 'new_follower'], actions: ['post_tweet', 'like', 'retweet'] },
    { id: 'linkedin', name: 'LinkedIn', description: 'Professional network', category: 'social', color: '#0A66C2', authType: 'oauth2', triggers: ['new_connection'], actions: ['create_post', 'send_message'] },
    { id: 'facebook', name: 'Facebook Pages', description: 'Social media', category: 'social', color: '#1877F2', authType: 'oauth2', triggers: ['new_post', 'new_comment'], actions: ['create_post', 'reply_comment'] },
    { id: 'instagram', name: 'Instagram', description: 'Photo sharing', category: 'social', color: '#E4405F', authType: 'oauth2', triggers: ['new_media', 'new_comment'], actions: ['create_post'] },
    { id: 'tiktok', name: 'TikTok', description: 'Video platform', category: 'social', color: '#000000', authType: 'oauth2', triggers: ['new_video'], actions: [] },
    { id: 'youtube', name: 'YouTube', description: 'Video platform', category: 'social', color: '#FF0000', authType: 'oauth2', triggers: ['new_video', 'new_subscriber'], actions: ['upload_video'] },
    { id: 'pinterest', name: 'Pinterest', description: 'Visual discovery', category: 'social', color: '#E60023', authType: 'oauth2', triggers: ['new_pin'], actions: ['create_pin'] },
    { id: 'reddit', name: 'Reddit', description: 'Communities', category: 'social', color: '#FF4500', authType: 'oauth2', triggers: ['new_post', 'new_comment'], actions: ['create_post', 'reply'] },
    { id: 'threads', name: 'Threads', description: 'Text-based social', category: 'social', color: '#000000', authType: 'oauth2', triggers: [], actions: ['create_post'] },
    { id: 'bluesky', name: 'Bluesky', description: 'Decentralized social', category: 'social', color: '#0085FF', authType: 'api_key', triggers: ['new_post'], actions: ['create_post'] },
    { id: 'mastodon', name: 'Mastodon', description: 'Decentralized social', category: 'social', color: '#6364FF', authType: 'oauth2', triggers: ['new_toot'], actions: ['create_toot'] },
];

// ANALYTICS PIECES
export const ANALYTICS_PIECES: Integration[] = [
    { id: 'google-analytics', name: 'Google Analytics', description: 'Web analytics', category: 'analytics', color: '#E37400', authType: 'oauth2', triggers: [], actions: ['send_event'] },
    { id: 'mixpanel', name: 'Mixpanel', description: 'Product analytics', category: 'analytics', color: '#7856FF', authType: 'api_key', triggers: [], actions: ['track_event', 'set_profile'] },
    { id: 'amplitude', name: 'Amplitude', description: 'Product analytics', category: 'analytics', color: '#1D3B8F', authType: 'api_key', triggers: [], actions: ['track_event', 'identify_user'] },
    { id: 'segment', name: 'Segment', description: 'Customer data platform', category: 'analytics', color: '#52BD95', authType: 'api_key', triggers: [], actions: ['identify', 'track', 'page'] },
    { id: 'heap', name: 'Heap', description: 'Digital insights', category: 'analytics', color: '#FF6D00', authType: 'api_key', triggers: [], actions: ['track_event', 'identify'] },
    { id: 'hotjar', name: 'Hotjar', description: 'Behavior analytics', category: 'analytics', color: '#FD3A5C', authType: 'api_key', triggers: [], actions: ['identify_user'] },
    { id: 'fullstory', name: 'FullStory', description: 'Digital experience', category: 'analytics', color: '#448AFF', authType: 'api_key', triggers: [], actions: ['identify', 'set_vars'] },
    { id: 'plausible', name: 'Plausible', description: 'Privacy analytics', category: 'analytics', color: '#5850EC', authType: 'api_key', triggers: [], actions: ['send_event'] },
];

// FINANCE PIECES
export const FINANCE_PIECES: Integration[] = [
    { id: 'quickbooks', name: 'QuickBooks', description: 'Accounting', category: 'finance', color: '#2CA01C', authType: 'oauth2', triggers: ['invoice_created', 'payment_received'], actions: ['create_invoice', 'create_customer'], popular: true },
    { id: 'xero', name: 'Xero', description: 'Accounting', category: 'finance', color: '#13B5EA', authType: 'oauth2', triggers: ['invoice_created'], actions: ['create_invoice', 'create_contact'] },
    { id: 'freshbooks', name: 'FreshBooks', description: 'Invoicing', category: 'finance', color: '#0075DD', authType: 'oauth2', triggers: ['invoice_created'], actions: ['create_invoice'] },
    { id: 'wave', name: 'Wave', description: 'Free accounting', category: 'finance', color: '#1C6AEE', authType: 'oauth2', triggers: ['invoice_created'], actions: ['create_invoice'] },
    { id: 'plaid', name: 'Plaid', description: 'Financial APIs', category: 'finance', color: '#000000', authType: 'api_key', triggers: ['transaction_created'], actions: ['get_transactions'] },
    { id: 'wise', name: 'Wise', description: 'International transfers', category: 'finance', color: '#00B9FF', authType: 'api_key', triggers: ['transfer_completed'], actions: ['create_transfer'] },
    { id: 'mercury', name: 'Mercury', description: 'Business banking', category: 'finance', color: '#5856D6', authType: 'api_key', triggers: ['transaction_created'], actions: [] },
    { id: 'brex', name: 'Brex', description: 'Corporate cards', category: 'finance', color: '#000000', authType: 'api_key', triggers: ['transaction_created'], actions: [] },
    { id: 'ramp', name: 'Ramp', description: 'Corporate cards', category: 'finance', color: '#00C48C', authType: 'api_key', triggers: ['transaction_created'], actions: [] },
    { id: 'chargebee', name: 'Chargebee', description: 'Subscription billing', category: 'finance', color: '#FF6849', authType: 'api_key', triggers: ['subscription_created', 'invoice_generated'], actions: ['create_subscription'] },
    { id: 'recurly', name: 'Recurly', description: 'Subscription management', category: 'finance', color: '#5E5E5E', authType: 'api_key', triggers: ['subscription_created'], actions: ['create_subscription'] },
];

// SECURITY PIECES
export const SECURITY_PIECES: Integration[] = [
    { id: 'okta', name: 'Okta', description: 'Identity management', category: 'security', color: '#007DC1', authType: 'oauth2', triggers: ['user_created', 'login'], actions: ['create_user', 'assign_group'] },
    { id: 'auth0', name: 'Auth0', description: 'Authentication', category: 'security', color: '#EB5424', authType: 'api_key', triggers: ['user_signup', 'login'], actions: ['create_user', 'update_metadata'] },
    { id: '1password', name: '1Password', description: 'Password manager', category: 'security', color: '#0094F5', authType: 'api_key', triggers: [], actions: ['create_vault', 'add_item'] },
    { id: 'lastpass', name: 'LastPass', description: 'Password manager', category: 'security', color: '#D32D27', authType: 'api_key', triggers: [], actions: ['share_password'] },
    { id: 'crowdstrike', name: 'CrowdStrike', description: 'Endpoint security', category: 'security', color: '#E01F44', authType: 'api_key', triggers: ['threat_detected'], actions: ['isolate_host'] },
    { id: 'snyk', name: 'Snyk', description: 'Security scanning', category: 'security', color: '#4C4A73', authType: 'api_key', triggers: ['vulnerability_found'], actions: ['scan_project'] },
    { id: 'cloudflare', name: 'Cloudflare', description: 'Web security & CDN', category: 'security', color: '#F38020', authType: 'api_key', triggers: ['attack_detected'], actions: ['purge_cache', 'add_rule'] },
    { id: 'duo', name: 'Duo Security', description: 'Two-factor auth', category: 'security', color: '#78C557', authType: 'api_key', triggers: ['auth_attempted'], actions: ['enroll_user'] },
    { id: 'vanta', name: 'Vanta', description: 'Compliance automation', category: 'security', color: '#4285F4', authType: 'api_key', triggers: ['finding_created'], actions: [] },
    { id: 'drata', name: 'Drata', description: 'Compliance', category: 'security', color: '#6366F1', authType: 'api_key', triggers: ['control_failed'], actions: [] },
];

// IOT PIECES
export const IOT_PIECES: Integration[] = [
    { id: 'philips-hue', name: 'Philips Hue', description: 'Smart lighting', category: 'iot', color: '#0065D3', authType: 'oauth2', triggers: ['motion_detected'], actions: ['set_light', 'set_scene'] },
    { id: 'nest', name: 'Google Nest', description: 'Smart home', category: 'iot', color: '#00A6A6', authType: 'oauth2', triggers: ['temperature_changed'], actions: ['set_temperature'] },
    { id: 'ring', name: 'Ring', description: 'Home security', category: 'iot', color: '#1C96E8', authType: 'oauth2', triggers: ['doorbell_pressed', 'motion_detected'], actions: [] },
    { id: 'smartthings', name: 'SmartThings', description: 'Smart home hub', category: 'iot', color: '#15BDB2', authType: 'oauth2', triggers: ['device_state_changed'], actions: ['control_device'] },
    { id: 'tuya', name: 'Tuya', description: 'IoT platform', category: 'iot', color: '#FF4800', authType: 'api_key', triggers: ['device_updated'], actions: ['control_device'] },
    { id: 'particle', name: 'Particle', description: 'IoT platform', category: 'iot', color: '#00AEEF', authType: 'api_key', triggers: ['event_published'], actions: ['call_function', 'read_variable'] },
    { id: 'arduino-iot', name: 'Arduino IoT Cloud', description: 'IoT platform', category: 'iot', color: '#00979D', authType: 'api_key', triggers: ['property_changed'], actions: ['update_property'] },
    { id: 'home-assistant', name: 'Home Assistant', description: 'Home automation', category: 'iot', color: '#41BDF5', authType: 'api_key', triggers: ['state_changed'], actions: ['call_service'] },
];

// MEDIA PIECES
export const MEDIA_PIECES: Integration[] = [
    { id: 'spotify', name: 'Spotify', description: 'Music streaming', category: 'media', color: '#1DB954', authType: 'oauth2', triggers: ['track_saved'], actions: ['add_to_playlist', 'play'] },
    { id: 'cloudinary', name: 'Cloudinary', description: 'Media management', category: 'media', color: '#3448C5', authType: 'api_key', triggers: [], actions: ['upload', 'transform', 'delete'] },
    { id: 'imgix', name: 'imgix', description: 'Image optimization', category: 'media', color: '#F7464A', authType: 'api_key', triggers: [], actions: ['purge_cache'] },
    { id: 'mux', name: 'Mux', description: 'Video infrastructure', category: 'media', color: '#FF2D55', authType: 'api_key', triggers: ['video_ready', 'livestream_active'], actions: ['create_asset', 'create_livestream'] },
    { id: 'vimeo', name: 'Vimeo', description: 'Video platform', category: 'media', color: '#1AB7EA', authType: 'oauth2', triggers: ['video_uploaded'], actions: ['upload_video', 'update_video'] },
    { id: 'wistia', name: 'Wistia', description: 'Video hosting', category: 'media', color: '#54BBE0', authType: 'api_key', triggers: ['video_uploaded'], actions: ['upload_video'] },
    { id: 'bunny-cdn', name: 'Bunny CDN', description: 'Content delivery', category: 'media', color: '#FF8A00', authType: 'api_key', triggers: [], actions: ['purge_url', 'upload'] },
    { id: 'unsplash', name: 'Unsplash', description: 'Stock photos', category: 'media', color: '#000000', authType: 'api_key', triggers: [], actions: ['search_photos', 'download'] },
    { id: 'pexels', name: 'Pexels', description: 'Stock media', category: 'media', color: '#05A081', authType: 'api_key', triggers: [], actions: ['search_photos', 'search_videos'] },
    { id: 'loom', name: 'Loom', description: 'Video messaging', category: 'media', color: '#625DF5', authType: 'oauth2', triggers: ['video_recorded'], actions: ['get_video'] },
];

// EDUCATION PIECES
export const EDUCATION_PIECES: Integration[] = [
    { id: 'canvas-lms', name: 'Canvas LMS', description: 'Learning management', category: 'education', color: '#E4060A', authType: 'oauth2', triggers: ['assignment_submitted'], actions: ['create_assignment', 'post_grade'] },
    { id: 'google-classroom', name: 'Google Classroom', description: 'Education platform', category: 'education', color: '#0F9D58', authType: 'oauth2', triggers: ['assignment_created', 'submission_received'], actions: ['create_assignment'] },
    { id: 'moodle', name: 'Moodle', description: 'Open source LMS', category: 'education', color: '#F98012', authType: 'api_key', triggers: ['course_completed'], actions: ['enroll_user'] },
    { id: 'teachable', name: 'Teachable', description: 'Course platform', category: 'education', color: '#000000', authType: 'api_key', triggers: ['enrollment_created', 'course_completed'], actions: ['enroll_user'] },
    { id: 'thinkific', name: 'Thinkific', description: 'Course platform', category: 'education', color: '#0B0B0B', authType: 'api_key', triggers: ['enrollment_created'], actions: ['enroll_user'] },
    { id: 'kajabi', name: 'Kajabi', description: 'Creator platform', category: 'education', color: '#00C1DE', authType: 'api_key', triggers: ['purchase_created'], actions: ['add_member'] },
    { id: 'podia', name: 'Podia', description: 'Digital storefront', category: 'education', color: '#7C3AED', authType: 'api_key', triggers: ['sale_created'], actions: [] },
    { id: 'circle', name: 'Circle', description: 'Community platform', category: 'education', color: '#8C52FF', authType: 'api_key', triggers: ['member_joined', 'post_created'], actions: ['add_member'] },
];

// HEALTHCARE PIECES
export const HEALTHCARE_PIECES: Integration[] = [
    { id: 'epic', name: 'Epic EHR', description: 'Electronic health records', category: 'healthcare', color: '#E31A22', authType: 'oauth2', triggers: ['appointment_scheduled'], actions: ['create_patient', 'create_appointment'] },
    { id: 'cerner', name: 'Cerner', description: 'Health IT', category: 'healthcare', color: '#00558C', authType: 'oauth2', triggers: ['patient_created'], actions: [] },
    { id: 'healthgorilla', name: 'Health Gorilla', description: 'Health data', category: 'healthcare', color: '#58B947', authType: 'api_key', triggers: ['lab_result_received'], actions: ['order_lab'] },
    { id: 'dosespot', name: 'DoseSpot', description: 'E-prescribing', category: 'healthcare', color: '#0066B3', authType: 'api_key', triggers: [], actions: ['send_prescription'] },
    { id: 'kareo', name: 'Kareo', description: 'Practice management', category: 'healthcare', color: '#00B5E2', authType: 'api_key', triggers: ['appointment_created'], actions: ['create_patient'] },
    { id: 'jane-app', name: 'Jane App', description: 'Practice management', category: 'healthcare', color: '#47B0E6', authType: 'api_key', triggers: ['booking_created'], actions: ['create_patient'] },
    { id: 'drchrono', name: 'DrChrono', description: 'EHR & Practice', category: 'healthcare', color: '#1E88E5', authType: 'oauth2', triggers: ['appointment_created'], actions: [] },
    { id: 'simplepractice', name: 'SimplePractice', description: 'Practice management', category: 'healthcare', color: '#00BCD4', authType: 'api_key', triggers: ['appointment_scheduled'], actions: ['create_client'] },
];

// LEGAL PIECES
export const LEGAL_PIECES: Integration[] = [
    { id: 'clio', name: 'Clio', description: 'Legal practice management', category: 'legal', color: '#066FE7', authType: 'oauth2', triggers: ['matter_created', 'document_uploaded'], actions: ['create_matter', 'create_contact'] },
    { id: 'docusign', name: 'DocuSign', description: 'Electronic signatures', category: 'legal', color: '#FFF42E', authType: 'oauth2', triggers: ['envelope_completed', 'envelope_sent'], actions: ['send_envelope', 'create_envelope'], popular: true },
    { id: 'hellosign', name: 'HelloSign', description: 'E-signatures', category: 'legal', color: '#00B4E6', authType: 'oauth2', triggers: ['signature_request_signed'], actions: ['send_signature_request'] },
    { id: 'pandadoc', name: 'PandaDoc', description: 'Document automation', category: 'legal', color: '#24B880', authType: 'oauth2', triggers: ['document_completed'], actions: ['create_document', 'send_document'] },
    { id: 'contractbook', name: 'Contractbook', description: 'Contract management', category: 'legal', color: '#5C6AC4', authType: 'api_key', triggers: ['contract_signed'], actions: ['create_contract'] },
    { id: 'ironclad', name: 'Ironclad', description: 'Contract lifecycle', category: 'legal', color: '#6366F1', authType: 'api_key', triggers: ['contract_signed'], actions: ['launch_workflow'] },
    { id: 'legal-zoom', name: 'LegalZoom', description: 'Legal services', category: 'legal', color: '#FF6B00', authType: 'api_key', triggers: [], actions: [] },
    { id: 'rocket-lawyer', name: 'Rocket Lawyer', description: 'Legal documents', category: 'legal', color: '#004B87', authType: 'api_key', triggers: [], actions: [] },
];

// REAL ESTATE PIECES
export const REAL_ESTATE_PIECES: Integration[] = [
    { id: 'zillow', name: 'Zillow', description: 'Real estate marketplace', category: 'real_estate', color: '#006AFF', authType: 'api_key', triggers: [], actions: ['get_property', 'search_listings'] },
    { id: 'realtor', name: 'Realtor.com', description: 'Real estate listings', category: 'real_estate', color: '#D92228', authType: 'api_key', triggers: [], actions: ['search_properties'] },
    { id: 'follow-up-boss', name: 'Follow Up Boss', description: 'Real estate CRM', category: 'real_estate', color: '#00B2A9', authType: 'api_key', triggers: ['lead_created', 'deal_closed'], actions: ['create_lead', 'add_note'] },
    { id: 'boomtown', name: 'BoomTown', description: 'Real estate platform', category: 'real_estate', color: '#FF6B35', authType: 'api_key', triggers: ['lead_created'], actions: ['create_lead'] },
    { id: 'dotloop', name: 'dotloop', description: 'Transaction management', category: 'real_estate', color: '#FF9500', authType: 'oauth2', triggers: ['loop_created', 'document_signed'], actions: ['create_loop'] },
    { id: 'skyslope', name: 'SkySlope', description: 'Transaction management', category: 'real_estate', color: '#003366', authType: 'api_key', triggers: ['transaction_created'], actions: [] },
    { id: 'buildium', name: 'Buildium', description: 'Property management', category: 'real_estate', color: '#4A90A4', authType: 'api_key', triggers: ['lease_created', 'payment_received'], actions: ['create_tenant'] },
    { id: 'appfolio', name: 'AppFolio', description: 'Property management', category: 'real_estate', color: '#2B5E8E', authType: 'api_key', triggers: ['application_received'], actions: [] },
];

// OTHER / MISC PIECES
export const OTHER_PIECES: Integration[] = [
    // Utility
    { id: 'jsonata', name: 'JSONata', description: 'JSON query language', category: 'other', color: '#2B7D2B', authType: 'none', triggers: [], actions: ['transform', 'query'] },
    { id: 'xml', name: 'XML', description: 'XML operations', category: 'other', color: '#005A9C', authType: 'none', triggers: [], actions: ['parse', 'build'] },
    { id: 'csv', name: 'CSV', description: 'CSV operations', category: 'other', color: '#227C38', authType: 'none', triggers: [], actions: ['parse', 'create'] },
    { id: 'date-time', name: 'Date/Time', description: 'Date operations', category: 'other', color: '#6366F1', authType: 'none', triggers: [], actions: ['format', 'add', 'subtract', 'diff'] },
    { id: 'math', name: 'Math', description: 'Math operations', category: 'other', color: '#EC4899', authType: 'none', triggers: [], actions: ['calculate', 'round', 'random'] },
    { id: 'text', name: 'Text', description: 'Text operations', category: 'other', color: '#8B5CF6', authType: 'none', triggers: [], actions: ['split', 'join', 'replace', 'format'] },
    { id: 'rss', name: 'RSS', description: 'RSS feeds', category: 'other', color: '#FF6600', authType: 'none', triggers: ['new_item'], actions: ['get_feed'] },
    { id: 'ftp', name: 'FTP/SFTP', description: 'File transfer', category: 'other', color: '#336699', authType: 'basic', triggers: ['file_added'], actions: ['upload', 'download', 'list'] },
    { id: 'mqtt', name: 'MQTT', description: 'IoT messaging', category: 'other', color: '#660099', authType: 'basic', triggers: ['message_received'], actions: ['publish'] },
    { id: 'graphql', name: 'GraphQL', description: 'GraphQL API', category: 'other', color: '#E10098', authType: 'api_key', triggers: [], actions: ['query', 'mutate'] },
    // News & Weather
    { id: 'newsapi', name: 'NewsAPI', description: 'News aggregation', category: 'other', color: '#2196F3', authType: 'api_key', triggers: [], actions: ['get_headlines', 'search_news'] },
    { id: 'openweather', name: 'OpenWeather', description: 'Weather data', category: 'other', color: '#EB6E4B', authType: 'api_key', triggers: [], actions: ['get_weather', 'get_forecast'] },
    // Translation
    { id: 'google-translate', name: 'Google Translate', description: 'Language translation', category: 'other', color: '#4285F4', authType: 'api_key', triggers: [], actions: ['translate', 'detect_language'] },
    { id: 'deepl', name: 'DeepL', description: 'AI translation', category: 'other', color: '#0F2B46', authType: 'api_key', triggers: [], actions: ['translate'] },
    // Misc SaaS
    { id: 'productboard', name: 'Productboard', description: 'Product management', category: 'other', color: '#FF6F61', authType: 'api_key', triggers: ['feature_created'], actions: ['create_note'] },
    { id: 'pendo', name: 'Pendo', description: 'Product experience', category: 'other', color: '#E5007D', authType: 'api_key', triggers: [], actions: ['track_event', 'identify'] },
    { id: 'launchdarkly', name: 'LaunchDarkly', description: 'Feature flags', category: 'other', color: '#3DD6F5', authType: 'api_key', triggers: ['flag_changed'], actions: ['get_flag', 'update_flag'] },
    { id: 'split', name: 'Split', description: 'Feature delivery', category: 'other', color: '#7B61FF', authType: 'api_key', triggers: [], actions: ['get_treatment'] },
    { id: 'statuspage', name: 'Statuspage', description: 'Status updates', category: 'other', color: '#3BD671', authType: 'api_key', triggers: ['incident_created'], actions: ['create_incident', 'update_component'] },
    { id: 'betterstack', name: 'Better Stack', description: 'Uptime monitoring', category: 'other', color: '#D1FAE5', authType: 'api_key', triggers: ['incident_created'], actions: ['acknowledge_incident'] },
    { id: 'uptimerobot', name: 'UptimeRobot', description: 'Uptime monitoring', category: 'other', color: '#3BD671', authType: 'api_key', triggers: ['monitor_down'], actions: ['create_monitor'] },
    // OCR / Document
    { id: 'google-vision', name: 'Google Vision', description: 'Image analysis', category: 'other', color: '#4285F4', authType: 'api_key', triggers: [], actions: ['analyze_image', 'ocr'] },
    { id: 'aws-textract', name: 'AWS Textract', description: 'Document OCR', category: 'other', color: '#FF9900', authType: 'api_key', triggers: [], actions: ['extract_text', 'analyze_document'] },
    { id: 'docparser', name: 'Docparser', description: 'Document parsing', category: 'other', color: '#4CAF50', authType: 'api_key', triggers: ['document_parsed'], actions: ['upload_document'] },
    // Surveys
    { id: 'surveymonkey', name: 'SurveyMonkey', description: 'Surveys', category: 'other', color: '#00BF6F', authType: 'oauth2', triggers: ['response_created'], actions: ['create_survey'] },
    { id: 'qualtrics', name: 'Qualtrics', description: 'Experience management', category: 'other', color: '#E31837', authType: 'api_key', triggers: ['response_completed'], actions: ['create_distribution'] },
    // Loyalty & Reviews
    { id: 'yotpo', name: 'Yotpo', description: 'Reviews & loyalty', category: 'other', color: '#27AAE1', authType: 'api_key', triggers: ['review_created'], actions: ['request_review'] },
    { id: 'trustpilot', name: 'Trustpilot', description: 'Customer reviews', category: 'other', color: '#00B67A', authType: 'api_key', triggers: ['review_created'], actions: ['invite_review'] },
    // Print & Fulfillment
    { id: 'printful', name: 'Printful', description: 'Print on demand', category: 'other', color: '#2E8BC0', authType: 'api_key', triggers: ['order_created'], actions: ['create_order', 'get_products'] },
    { id: 'shipstation', name: 'ShipStation', description: 'Shipping', category: 'other', color: '#8CBF3F', authType: 'api_key', triggers: ['order_shipped'], actions: ['create_order', 'create_label'] },
    { id: 'easypost', name: 'EasyPost', description: 'Shipping API', category: 'other', color: '#3366FF', authType: 'api_key', triggers: ['tracking_updated'], actions: ['create_shipment', 'buy_label'] },
    // Signatures / Notary
    { id: 'notarize', name: 'Notarize', description: 'Online notary', category: 'other', color: '#0055FF', authType: 'api_key', triggers: ['notarization_complete'], actions: ['create_transaction'] },
    { id: 'signwell', name: 'SignWell', description: 'E-signatures', category: 'other', color: '#6366F1', authType: 'api_key', triggers: ['document_signed'], actions: ['send_document'] },
    // Misc
    { id: 'giphy', name: 'Giphy', description: 'GIF search', category: 'other', color: '#FF6666', authType: 'api_key', triggers: [], actions: ['search_gifs', 'random_gif'] },
    { id: 'ipinfo', name: 'IPinfo', description: 'IP geolocation', category: 'other', color: '#0366D6', authType: 'api_key', triggers: [], actions: ['lookup_ip'] },
    { id: 'abstract-api', name: 'Abstract API', description: 'Data validation', category: 'other', color: '#4F46E5', authType: 'api_key', triggers: [], actions: ['validate_email', 'validate_phone', 'get_ip_info'] },
    { id: 'hunter', name: 'Hunter.io', description: 'Email finder', category: 'other', color: '#FF7F50', authType: 'api_key', triggers: [], actions: ['find_email', 'verify_email'] },
    { id: 'zapier-webhooks', name: 'Zapier Webhooks', description: 'Webhook integration', category: 'other', color: '#FF4A00', authType: 'none', triggers: ['webhook_received'], actions: ['send_webhook'] },
    { id: 'ifttt', name: 'IFTTT', description: 'Automation', category: 'other', color: '#000000', authType: 'api_key', triggers: [], actions: ['trigger_applet'] },
    { id: 'make', name: 'Make (Integromat)', description: 'Integration platform', category: 'other', color: '#613FD4', authType: 'api_key', triggers: [], actions: ['run_scenario'] },
];

// Merged integrations with deduplication
// We prioritize manually defined pieces (CORE, AI, COMMUNICATION, etc.) over auto-generated ones
const MANUAL_PIECES = [
    ...CORE_PIECES,
    ...AI_PIECES,
    ...COMMUNICATION_PIECES,
    ...CRM_PIECES,
    ...PRODUCTIVITY_PIECES,
    ...MARKETING_PIECES,
    ...DEVELOPER_PIECES,
    ...DATABASE_PIECES,
    ...STORAGE_PIECES,
    ...ECOMMERCE_PIECES,
    ...SUPPORT_PIECES,
    ...FORM_PIECES,
    ...SCHEDULING_PIECES,
    ...HR_PIECES,
    ...SOCIAL_PIECES,
    ...ANALYTICS_PIECES,
    ...FINANCE_PIECES,
    ...SECURITY_PIECES,
    ...IOT_PIECES,
    ...MEDIA_PIECES,
    ...EDUCATION_PIECES,
    ...HEALTHCARE_PIECES,
    ...LEGAL_PIECES,
    ...REAL_ESTATE_PIECES,
    ...OTHER_PIECES,
];

const manualIds = new Set(MANUAL_PIECES.map(p => p.id));
const filteredAutoPieces = AUTO_GENERATED_PIECES.filter(p => !manualIds.has(p.id));

export const ALL_INTEGRATIONS: Integration[] = [
    ...MANUAL_PIECES,
    ...filteredAutoPieces
];

// Helper functions
export const getIntegrationsByCategory = (category: IntegrationCategory): Integration[] => {
    return ALL_INTEGRATIONS.filter(i => i.category === category);
};

export const getPopularIntegrations = (): Integration[] => {
    return ALL_INTEGRATIONS.filter(i => i.popular);
};

export const searchIntegrations = (query: string): Integration[] => {
    const lowerQuery = query.toLowerCase();
    return ALL_INTEGRATIONS.filter(i =>
        i.name.toLowerCase().includes(lowerQuery) ||
        i.description.toLowerCase().includes(lowerQuery) ||
        i.category.includes(lowerQuery)
    );
};

export const getIntegration = (id: string): Integration | undefined => {
    return ALL_INTEGRATIONS.find(i => i.id === id);
};

// Export count for display
export const INTEGRATION_COUNT = ALL_INTEGRATIONS.length;

console.log(`Loaded ${INTEGRATION_COUNT} integrations`);
