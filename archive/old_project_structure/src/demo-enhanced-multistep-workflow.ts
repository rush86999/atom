import { MultiIntegrationWorkflowEngine, WorkflowDefinition, WorkflowStep } from '../src/orchestration/MultiIntegrationWorkflowEngine';

/**
 * Enhanced Multistep Automation Workflow Demo
 * 
 * This demo showcases the enhanced workflow engine with:
 * - Advanced branching with multiple condition types
 * - AI-powered nodes for intelligent decision making
 * - Complex multi-step automation workflows
 * - Integration with multiple services
 */

// Demo Configuration
const config: any = {
  maxConcurrentExecutions: 5,
  maxStepsPerExecution: 50,
  defaultTimeout: 300000,
  defaultRetryAttempts: 3,
  enableCaching: true,
  enableMetrics: true,
  enableOptimization: true,
  healthCheckInterval: 60000,
  integrationHealthThreshold: 0.8,
  autoRetryFailures: true,
  logLevel: 'info',
};

// Initialize the enhanced workflow engine
const workflowEngine = new MultiIntegrationWorkflowEngine(config);

// Demo Data
const customerData = {
  id: 'cust_12345',
  name: 'John Doe',
  email: 'john.doe@example.com',
  age: 28,
  plan: 'premium',
  riskScore: 0.2,
  lastPurchase: new Date('2024-01-15'),
  totalSpent: 2500,
  supportTickets: 2,
  location: 'US',
  language: 'en'
};

const supportTicketData = {
  ticketId: 'ticket_789',
  customerId: 'cust_12345',
  subject: 'Issue with billing',
  priority: 'medium',
  category: 'billing',
  description: 'Customer was charged incorrectly for their monthly subscription',
  createdAt: new Date(),
  status: 'open',
  customerAge: 28,
  customerPlan: 'premium',
  customerRiskScore: 0.2
};

// Enhanced Workflow 1: Customer Onboarding with AI Decision Making
const createCustomerOnboardingWorkflow = (): WorkflowDefinition => ({
  id: 'customer-onboarding-ai-enhanced',
  name: 'AI-Enhanced Customer Onboarding',
  description: 'Intelligent customer onboarding with AI-powered decision making and personalization',
  version: '2.0.0',
  category: 'Customer Management',
  steps: [
    // Step 1: Validate customer data
    {
      id: 'validate-data',
      name: 'Validate Customer Data',
      type: 'data_transform',
      parameters: {
        transformType: 'calculate',
        calculations: {
          isAdult: 'age >= 18',
          emailValid: 'email.includes("@")',
          riskCategory: 'riskScore < 0.3 ? "low" : riskScore < 0.7 ? "medium" : "high"'
        }
      },
      dependsOn: [],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      metadata: { description: 'Validate and calculate derived customer metrics' }
    },

    // Step 2: AI-powered customer analysis
    {
      id: 'ai-customer-analysis',
      name: 'AI Customer Analysis',
      type: 'ai_task',
      parameters: {},
      dependsOn: ['validate-data'],
      retryPolicy: { maxAttempts: 2, delay: 2000, backoffMultiplier: 1.5 },
      timeout: 60000,
      aiConfiguration: {
        aiType: 'prebuilt',
        prebuiltTask: 'classify',
        prompt: 'Analyze this customer profile and classify their value and potential risks',
        model: 'gpt-4',
        temperature: 0.3,
        maxTokens: 500
      },
      metadata: { description: 'AI-powered customer value and risk analysis' }
    },

    // Step 3: Advanced branching based on AI analysis
    {
      id: 'branch-customer-type',
      name: 'Customer Type Branch',
      type: 'advanced_branch',
      parameters: {},
      dependsOn: ['ai-customer-analysis'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      branchConfiguration: {
        conditionType: 'ai',
        value: 'Based on the customer analysis, determine if this is a high-value customer, standard customer, or high-risk customer. Respond with: "high_value", "standard", or "high_risk"',
        branches: [
          { id: 'high_value', label: 'High Value Customer' },
          { id: 'standard', label: 'Standard Customer' },
          { id: 'high_risk', label: 'High Risk Customer' }
        ]
      },
      metadata: { description: 'AI-powered customer segmentation branching' }
    },

    // Step 4A: High value customer onboarding
    {
      id: 'high-value-onboarding',
      name: 'High Value Onboarding',
      type: 'integration_action',
      integrationId: 'crm',
      action: 'create_premium_profile',
      parameters: {
        priority: 'high',
        assignManager: true,
        welcomePackage: 'premium'
      },
      dependsOn: ['branch-customer-type'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 45000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'high_value' },
      metadata: { description: 'Premium onboarding flow for high-value customers' }
    },

    // Step 4B: Standard customer onboarding
    {
      id: 'standard-onboarding',
      name: 'Standard Onboarding',
      type: 'integration_action',
      integrationId: 'crm',
      action: 'create_standard_profile',
      parameters: {
        priority: 'normal',
        assignManager: false,
        welcomePackage: 'standard'
      },
      dependsOn: ['branch-customer-type'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'standard' },
      metadata: { description: 'Standard onboarding flow for regular customers' }
    },

    // Step 4C: High risk customer handling
    {
      id: 'high-risk-handling',
      name: 'High Risk Handling',
      type: 'integration_action',
      integrationId: 'fraud-detection',
      action: 'flag_for_review',
      parameters: {
        priority: 'urgent',
        requiresManualReview: true
      },
      dependsOn: ['branch-customer-type'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'high_risk' },
      metadata: { description: 'Enhanced verification for high-risk customers' }
    },

    // Step 5: Personalized welcome message generation
    {
      id: 'ai-welcome-message',
      name: 'AI Welcome Message',
      type: 'ai_task',
      parameters: {},
      dependsOn: ['high-value-onboarding', 'standard-onboarding', 'high-risk-handling'],
      retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
      timeout: 60000,
      aiConfiguration: {
        aiType: 'generate',
        prompt: 'Generate a personalized welcome message for this customer based on their profile and customer type',
        model: 'gpt-4',
        temperature: 0.8,
        maxTokens: 300
      },
      metadata: { description: 'AI-generated personalized welcome message' }
    },

    // Step 6: Send welcome communication
    {
      id: 'send-welcome',
      name: 'Send Welcome',
      type: 'integration_action',
      integrationId: 'email',
      action: 'send_welcome_email',
      parameters: {
        template: 'welcome_v2',
        personalize: true,
        trackOpen: true
      },
      dependsOn: ['ai-welcome-message'],
      retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
      timeout: 45000,
      metadata: { description: 'Send personalized welcome email' }
    }
  ],
  triggers: [
    {
      id: 'new-customer-trigger',
      type: 'integration_event',
      integrationId: 'signup-form',
      eventType: 'customer_registered',
      enabled: true,
      metadata: { description: 'Trigger when new customer registers' }
    }
  ],
  variables: {},
  settings: {
    timeout: 300000,
    retryPolicy: { maxAttempts: 2, delay: 5000 },
    priority: 'high',
    parallelExecution: false
  },
  integrations: ['crm', 'email', 'fraud-detection'],
  tags: ['onboarding', 'ai', 'customer', 'automation'],
  createdAt: new Date(),
  updatedAt: new Date(),
  enabled: true
});

// Enhanced Workflow 2: Intelligent Support Ticket Processing
const createSupportTicketWorkflow = (): WorkflowDefinition => ({
  id: 'intelligent-support-ticket-processing',
  name: 'AI-Powered Support Ticket Processing',
  description: 'Intelligent support ticket routing and resolution with AI analysis',
  version: '2.0.0',
  category: 'Customer Support',
  steps: [
    // Step 1: Initial ticket analysis
    {
      id: 'analyze-ticket',
      name: 'AI Ticket Analysis',
      type: 'ai_task',
      parameters: {},
      dependsOn: [],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 60000,
      aiConfiguration: {
        aiType: 'prebuilt',
        prebuiltTask: 'classify',
        prompt: 'Analyze this support ticket and classify its urgency, category, and complexity',
        model: 'gpt-4',
        temperature: 0.2,
        maxTokens: 400
      },
      metadata: { description: 'AI-powered ticket classification and analysis' }
    },

    // Step 2: Sentiment analysis
    {
      id: 'sentiment-analysis',
      name: 'Customer Sentiment Analysis',
      type: 'ai_task',
      parameters: {},
      dependsOn: ['analyze-ticket'],
      retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
      timeout: 45000,
      aiConfiguration: {
        aiType: 'prebuilt',
        prebuiltTask: 'sentiment',
        prompt: 'Analyze customer sentiment from this support ticket',
        model: 'gpt-3.5-turbo',
        temperature: 0.1,
        maxTokens: 200
      },
      metadata: { description: 'Analyze customer sentiment for priority routing' }
    },

    // Step 3: Complex branching for ticket routing
    {
      id: 'route-ticket',
      name: 'Intelligent Ticket Routing',
      type: 'advanced_branch',
      parameters: {},
      dependsOn: ['analyze-ticket', 'sentiment-analysis'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      branchConfiguration: {
        conditionType: 'ai',
        value: `Based on the ticket analysis and sentiment, determine the best routing:
        - "urgent_critical": High urgency + negative sentiment
        - "urgent_standard": High urgency + neutral/positive sentiment  
        - "standard_priority": Medium urgency + any sentiment
        - "low_priority": Low urgency or simple issues
        
        Customer data: Age ${supportTicketData.customerAge}, Plan: ${supportTicketData.customerPlan}, Risk Score: ${supportTicketData.customerRiskScore}
        
        Respond with only the routing decision.`,
        branches: [
          { id: 'urgent_critical', label: 'Urgent - Critical' },
          { id: 'urgent_standard', label: 'Urgent - Standard' },
          { id: 'standard_priority', label: 'Standard Priority' },
          { id: 'low_priority', label: 'Low Priority' }
        ]
      },
      metadata: { description: 'AI-powered intelligent ticket routing' }
    },

    // Step 4A: Critical escalation
    {
      id: 'critical-escalation',
      name: 'Critical Escalation',
      type: 'integration_action',
      integrationId: 'support-system',
      action: 'escalate_critical',
      parameters: {
        notifyManager: true,
        responseSLA: 30, // minutes
        autoAssign: true
      },
      dependsOn: ['route-ticket'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'urgent_critical' },
      metadata: { description: 'Immediate escalation for critical issues' }
    },

    // Step 4B: Urgent handling
    {
      id: 'urgent-handling',
      name: 'Urgent Handling',
      type: 'integration_action',
      integrationId: 'support-system',
      action: 'assign_urgent',
      parameters: {
        responseSLA: 120, // minutes
        priorityAssignment: true
      },
      dependsOn: ['route-ticket'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'urgent_standard' },
      metadata: { description: 'Urgent ticket handling with priority assignment' }
    },

    // Step 4C: Standard processing
    {
      id: 'standard-processing',
      name: 'Standard Processing',
      type: 'integration_action',
      integrationId: 'support-system',
      action: 'assign_standard',
      parameters: {
        responseSLA: 480, // minutes
        autoAssignment: false
      },
      dependsOn: ['route-ticket'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'standard_priority' },
      metadata: { description: 'Standard ticket processing queue' }
    },

    // Step 4D: Low priority handling
    {
      id: 'low-priority-handling',
      name: 'Low Priority Processing',
      type: 'integration_action',
      integrationId: 'support-system',
      action: 'queue_low_priority',
      parameters: {
        responseSLA: 1440, // 24 hours
        batchProcessing: true
      },
      dependsOn: ['route-ticket'],
      retryPolicy: { maxAttempts: 2, delay: 2000, backoffMultiplier: 2 },
      timeout: 30000,
      condition: { field: '_selectedBranch', operator: 'equals', value: 'low_priority' },
      metadata: { description: 'Low priority batch processing' }
    },

    // Step 5: AI-powered suggested responses
    {
      id: 'ai-response-suggestions',
      name: 'AI Response Suggestions',
      type: 'ai_task',
      parameters: {},
      dependsOn: ['critical-escalation', 'urgent-handling', 'standard-processing', 'low-priority-handling'],
      retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
      timeout: 60000,
      aiConfiguration: {
        aiType: 'generate',
        prompt: 'Generate 3 suggested responses for this support ticket based on the customer profile and issue context',
        model: 'gpt-4',
        temperature: 0.6,
        maxTokens: 600
      },
      metadata: { description: 'AI-generated response suggestions for support agents' }
    },

    // Step 6: Update ticket with AI insights
    {
      id: 'update-ticket-insights',
      name: 'Update with AI Insights',
      type: 'data_transform',
      parameters: {
        transformType: 'map_fields',
        mapping: {
          'aiInsights.analysis': 'ai-customer-analysis.result',
          'aiInsights.sentiment': 'sentiment-analysis.result',
          'aiInsights.suggestions': 'ai-response-suggestions.result',
          'routing.decision': '_selectedBranch',
          'routing.reasoning': '_branchDecision.branchReasoning'
        }
      },
      dependsOn: ['ai-response-suggestions'],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      metadata: { description: 'Consolidate AI insights into ticket data' }
    }
  ],
  triggers: [
    {
      id: 'new-ticket-trigger',
      type: 'integration_event',
      integrationId: 'support-portal',
      eventType: 'ticket_created',
      enabled: true,
      metadata: { description: 'Trigger when new support ticket is created' }
    }
  ],
  variables: {},
  settings: {
    timeout: 600000,
    retryPolicy: { maxAttempts: 2, delay: 3000 },
    priority: 'normal',
    parallelExecution: true
  },
  integrations: ['support-system', 'ai-service'],
  tags: ['support', 'ai', 'automation', 'customer-service'],
  createdAt: new Date(),
  updatedAt: new Date(),
  enabled: true
});

// Mock Integration Registration
const registerMockIntegrations = async () => {
  // CRM Integration
  await workflowEngine.registerIntegration({
    id: 'crm',
    name: 'Customer Relationship Management',
    integrationType: 'rest_api',
    supportedActions: ['create_premium_profile', 'create_standard_profile', 'update_customer'],
    supportedTriggers: ['customer_updated', 'customer_segmented'],
    rateLimit: { requestsPerSecond: 10, requestsPerHour: 1000 },
    requiresAuth: true,
    authType: 'oauth',
    healthStatus: 'healthy',
    lastHealthCheck: new Date(),
    metadata: { version: '2.1.0', endpoint: 'https://api.crm.example.com' }
  });

  // Email Integration
  await workflowEngine.registerIntegration({
    id: 'email',
    name: 'Email Service',
    integrationType: 'smtp',
    supportedActions: ['send_welcome_email', 'send_notification', 'send_marketing'],
    supportedTriggers: ['email_sent', 'email_opened', 'email_clicked'],
    rateLimit: { requestsPerSecond: 20, requestsPerHour: 2000 },
    requiresAuth: true,
    authType: 'api_key',
    healthStatus: 'healthy',
    lastHealthCheck: new Date(),
    metadata: { version: '1.5.0', provider: 'sendgrid' }
  });

  // Fraud Detection Integration
  await workflowEngine.registerIntegration({
    id: 'fraud-detection',
    name: 'Fraud Detection Service',
    integrationType: 'ml_service',
    supportedActions: ['flag_for_review', 'analyze_risk', 'verify_identity'],
    supportedTriggers: ['fraud_detected', 'risk_score_updated'],
    rateLimit: { requestsPerSecond: 5, requestsPerHour: 500 },
    requiresAuth: true,
    authType: 'oauth',
    healthStatus: 'healthy',
    lastHealthCheck: new Date(),
    metadata: { version: '3.0.0', model: 'risk_model_v2' }
  });

  // Support System Integration
  await workflowEngine.registerIntegration({
    id: 'support-system',
    name: 'Support Ticket System',
    integrationType: 'rest_api',
    supportedActions: ['escalate_critical', 'assign_urgent', 'assign_standard', 'queue_low_priority'],
    supportedTriggers: ['ticket_created', 'ticket_updated', 'agent_assigned'],
    rateLimit: { requestsPerSecond: 15, requestsPerHour: 1500 },
    requiresAuth: true,
    authType: 'oauth',
    healthStatus: 'healthy',
    lastHealthCheck: new Date(),
    metadata: { version: '4.2.0', provider: 'zendesk' }
  });

  // AI Service Integration
  await workflowEngine.registerIntegration({
    id: 'ai-service',
    name: 'AI Processing Service',
    integrationType: 'ml_api',
    supportedActions: ['process_text', 'classify_content', 'generate_response'],
    supportedTriggers: ['model_updated', 'processing_completed'],
    rateLimit: { requestsPerSecond: 50, requestsPerHour: 5000 },
    requiresAuth: true,
    authType: 'api_key',
    healthStatus: 'healthy',
    lastHealthCheck: new Date(),
    metadata: { version: '1.0.0', provider: 'openai' }
  });
};

// Event Listeners for monitoring
const setupEventListeners = () => {
  workflowEngine.on('workflow-execution-started', (event) => {
    console.log(`🚀 Workflow started: ${event.workflowId} (Execution: ${event.executionId})`);
  });

  workflowEngine.on('step-execution-completed', (event) => {
    console.log(`✅ Step completed: ${event.stepId} in ${event.executionTime}ms`);
  });

  workflowEngine.on('ai-task-completed', (event) => {
    const confidence = event.confidence ? event.confidence.toFixed(2) : 'N/A';
    console.log(`🤖 AI task completed: ${event.stepId} using ${event.model} (confidence: ${confidence})`);
  });

  workflowEngine.on('branch-evaluated', (event) => {
    console.log(`🔀 Branch evaluated: ${event.stepId} -> ${event.selectedBranch} (${event.conditionType})`);
  });

  workflowEngine.on('workflow-execution-completed', (event) => {
    console.log(`🎉 Workflow completed: ${event.executionId}`);
  });

  workflowEngine.on('workflow-execution-failed', (event) => {
    console.log(`❌ Workflow failed: ${event.executionId} - ${event.error}`);
  });
};

// Main demo execution
const runEnhancedWorkflowDemo = async () => {
  console.log('🎯 Enhanced Multistep Automation Workflow Demo');
  console.log('='.repeat(60));

  try {
    // Setup
    console.log('🔧 Setting up enhanced workflow engine...');
    await registerMockIntegrations();
    setupEventListeners();

    // Register workflows
    console.log('📝 Registering enhanced workflows...');
    await workflowEngine.registerWorkflow(createCustomerOnboardingWorkflow());
    await workflowEngine.registerWorkflow(createSupportTicketWorkflow());

    console.log('🎬 Starting workflow demonstrations...');
    console.log('');

    // Demo 1: Customer Onboarding
    console.log('👤 Demo 1: AI-Enhanced Customer Onboarding');
    console.log('-'.repeat(40));
    const onboardingExecutionId = await workflowEngine.executeWorkflow(
      'customer-onboarding-ai-enhanced',
      'demo_user',
      customerData
    );

    // Wait for completion
    await waitForExecution(onboardingExecutionId);
    console.log('');

    // Demo 2: Support Ticket Processing
    console.log('🎫 Demo 2: Intelligent Support Ticket Processing');
    console.log('-'.repeat(50));
    const supportExecutionId = await workflowEngine.executeWorkflow(
      'intelligent-support-ticket-processing',
      'demo_user',
      supportTicketData
    );

    // Wait for completion
    await waitForExecution(supportExecutionId);
    console.log('');

    // Show analytics
    console.log('📊 Workflow Analytics Summary');
    console.log('-'.repeat(30));
    
    const onboardingAnalytics = await workflowEngine.getWorkflowAnalytics('customer-onboarding-ai-enhanced');
    const supportAnalytics = await workflowEngine.getWorkflowAnalytics('intelligent-support-ticket-processing');

    if (onboardingAnalytics) {
      console.log(`👤 Customer Onboarding:`);
      console.log(`   Executions: ${onboardingAnalytics.totalExecutions}`);
      console.log(`   Success Rate: ${(onboardingAnalytics.successRate * 100).toFixed(1)}%`);
      console.log(`   Avg Time: ${(onboardingAnalytics.averageExecutionTime / 1000).toFixed(1)}s`);
    }

    if (supportAnalytics) {
      console.log(`🎫 Support Processing:`);
      console.log(`   Executions: ${supportAnalytics.totalExecutions}`);
      console.log(`   Success Rate: ${(supportAnalytics.successRate * 100).toFixed(1)}%`);
      console.log(`   Avg Time: ${(supportAnalytics.averageExecutionTime / 1000).toFixed(1)}s`);
    }

    // System health
    console.log('');
    console.log('🏥 System Health');
    console.log('-'.repeat(20));
    const health = workflowEngine.getSystemHealth();
    console.log(`Active Executions: ${health.activeExecutions}`);
    console.log(`Healthy Integrations: ${health.healthyIntegrations}/${health.totalIntegrations}`);
    console.log(`Queued Executions: ${health.queuedExecutions}`);

    console.log('');
    console.log('✨ Enhanced workflow demo completed successfully!');

  } catch (error) {
    console.error('❌ Demo failed:', error);
  }
};

// Helper function to wait for execution completion
const waitForExecution = async (executionId: string, timeout = 60000) => {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeout) {
    const execution = await workflowEngine.getExecution(executionId);
    
    if (execution && ['completed', 'failed'].includes(execution.status)) {
      if (execution.status === 'completed') {
        console.log(`✅ Execution completed in ${(execution.executionTime! / 1000).toFixed(1)}s`);
      } else {
        console.log(`❌ Execution failed: ${execution.error}`);
      }
      
      // Show branch decisions if any
      if (execution.variables._branchDecision) {
        console.log(`🔀 Branch Decision: ${execution.variables._branchDecision.selectedBranch}`);
        console.log(`   Reasoning: ${execution.variables._branchDecision.branchReasoning}`);
      }
      
      return execution;
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  throw new Error(`Execution timeout: ${executionId}`);
};

// Run the demo
if (require.main === module) {
  runEnhancedWorkflowDemo().catch(console.error);
}

export {
  runEnhancedWorkflowDemo,
  createCustomerOnboardingWorkflow,
  createSupportTicketWorkflow
};