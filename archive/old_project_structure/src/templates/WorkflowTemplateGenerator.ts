
export class WorkflowTemplateGenerator {
  private templates: Map<string, WorkflowTemplate> = new Map();

  constructor() {
    this.initializeBuiltinTemplates();
  }

  private initializeBuiltinTemplates(): void {
    // Customer Onboarding Template
    this.addTemplate('customer_onboarding', {
      name: 'Customer Onboarding',
      description: 'Automated customer onboarding with AI-powered analysis',
      category: 'Customer Management',
      difficulty: 'intermediate',
      tags: ['onboarding', 'customer', 'ai', 'automation'],
      variables: [
        { name: 'customer_data', type: 'object', required: true },
        { name: 'welcome_email_enabled', type: 'boolean', default: true },
        { name: 'fraud_check_enabled', type: 'boolean', default: true }
      ],
      steps: [
        {
          id: 'validate_customer',
          name: 'Validate Customer Data',
          type: 'data_transform',
          config: {
            validation_rules: ['email_format', 'required_fields']
          }
        },
        {
          id: 'ai_analysis',
          name: 'AI Customer Analysis',
          type: 'ai_task',
          config: {
            ai_type: 'classify',
            model: 'gpt-4',
            prompt: 'Analyze customer profile for value and risk assessment'
          }
        },
        {
          id: 'route_customer',
          name: 'Route Customer',
          type: 'advanced_branch',
          config: {
            condition_type: 'ai',
            branches: ['high_value', 'standard', 'high_risk']
          }
        }
      ]
    });

    // Support Ticket Processing Template
    this.addTemplate('support_ticket_processing', {
      name: 'Support Ticket Processing',
      description: 'Intelligent support ticket routing and resolution',
      category: 'Customer Support',
      difficulty: 'advanced',
      tags: ['support', 'ticket', 'ai', 'routing'],
      variables: [
        { name: 'ticket_data', type: 'object', required: true },
        { name: 'priority_threshold', type: 'number', default: 3 },
        { name: 'auto_response_enabled', type: 'boolean', default: false }
      ],
      steps: [
        {
          id: 'analyze_ticket',
          name: 'AI Ticket Analysis',
          type: 'ai_task',
          config: {
            ai_type: 'sentiment',
            model: 'gpt-3.5-turbo'
          }
        },
        {
          id: 'classify_ticket',
          name: 'Classify Ticket',
          type: 'ai_task',
          config: {
            ai_type: 'classify',
            prompt: 'Categorize ticket and assign priority'
          }
        },
        {
          id: 'route_ticket',
          name: 'Route Ticket',
          type: 'advanced_branch',
          config: {
            condition_type: 'ai',
            branches: ['urgent', 'standard', 'low_priority']
          }
        }
      ]
    });

    // Financial Transaction Monitoring Template
    this.addTemplate('transaction_monitoring', {
      name: 'Financial Transaction Monitoring',
      description: 'AI-powered fraud detection and transaction processing',
      category: 'Finance',
      difficulty: 'expert',
      tags: ['finance', 'fraud', 'transaction', 'ai'],
      variables: [
        { name: 'transaction_data', type: 'object', required: true },
        { name: 'risk_threshold', type: 'number', default: 0.7 },
        { name: 'auto_approval_limit', type: 'number', default: 1000 }
      ],
      steps: [
        {
          id: 'validate_transaction',
          name: 'Validate Transaction',
          type: 'data_transform',
          config: {
            validation_rules: ['amount_range', 'account_status']
          }
        },
        {
          id: 'risk_assessment',
          name: 'AI Risk Assessment',
          type: 'ai_task',
          config: {
            ai_type: 'decision',
            prompt: 'Assess fraud risk and approve/reject transaction'
          }
        },
        {
          id: 'process_transaction',
          name: 'Process Transaction',
          type: 'advanced_branch',
          config: {
            condition_type: 'ai',
            branches: ['approved', 'flagged_for_review', 'rejected']
          }
        }
      ]
    });
  }

  generateWorkflow(templateId: string, variables: any): WorkflowDefinition {
    const template = this.getTemplate(templateId);
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }

    return this.instantiateTemplate(template, variables);
  }

  createCustomTemplate(template: WorkflowTemplate): void {
    this.addTemplate(template.id, template);
  }

  getTemplate(templateId: string): WorkflowTemplate | undefined {
    return this.templates.get(templateId);
  }

  getAllTemplates(): WorkflowTemplate[] {
    return Array.from(this.templates.values());
  }

  searchTemplates(query: string): WorkflowTemplate[] {
    const lowerQuery = query.toLowerCase();
    return Array.from(this.templates.values()).filter(template => 
      template.name.toLowerCase().includes(lowerQuery) ||
      template.description.toLowerCase().includes(lowerQuery) ||
      template.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
    );
  }

  private addTemplate(id: string, template: WorkflowTemplate): void {
    this.templates.set(id, template);
  }

  private instantiateTemplate(template: WorkflowTemplate, variables: any): WorkflowDefinition {
    // Create workflow definition from template
    const workflow: WorkflowDefinition = {
      id: `${template.id}_${Date.now()}`,
      name: template.name,
      description: template.description,
      version: '1.0.0',
      category: template.category,
      steps: template.steps.map(step => this.instantiateStep(step, variables)),
      triggers: [],
      variables: this.processVariables(template.variables, variables),
      settings: {
        timeout: 300000,
        retryPolicy: { maxAttempts: 3, delay: 5000 },
        priority: 'normal',
        parallelExecution: false
      },
      integrations: this.extractIntegrations(template.steps),
      tags: template.tags,
      createdAt: new Date(),
      updatedAt: new Date(),
      enabled: true
    };

    return workflow;
  }

  private instantiateStep(step: TemplateStep, variables: any): any {
    // Apply variables to step configuration
    return {
      ...step,
      parameters: this.replaceVariables(step.config, variables),
      dependsOn: step.dependsOn || []
    };
  }

  private processVariables(templateVariables: TemplateVariable[], providedVariables: any): any {
    const processed: any = {};
    
    templateVariables.forEach(variable => {
      if (providedVariables[variable.name] !== undefined) {
        processed[variable.name] = providedVariables[variable.name];
      } else if (variable.default !== undefined) {
        processed[variable.name] = variable.default;
      } else if (variable.required) {
        throw new Error(`Required variable ${variable.name} not provided`);
      }
    });

    return processed;
  }

  private replaceVariables(config: any, variables: any): any {
    // Simple variable replacement
    const configStr = JSON.stringify(config);
    let replaced = configStr;
    
    Object.entries(variables).forEach(([key, value]) => {
      const regex = new RegExp(`\\${\${key}\}\`, 'g');
      replaced = replaced.replace(regex, value);
    });

    return JSON.parse(replaced);
  }

  private extractIntegrations(steps: TemplateStep[]): string[] {
    const integrations = new Set<string>();
    
    steps.forEach(step => {
      if (step.type === 'ai_task') {
        integrations.add('ai-service');
      }
      // Add integration extraction logic for other step types
    });

    return Array.from(integrations);
  }
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  tags: string[];
  variables: TemplateVariable[];
  steps: TemplateStep[];
}

interface TemplateVariable {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required: boolean;
  default?: any;
  description?: string;
}

interface TemplateStep {
  id: string;
  name: string;
  type: 'data_transform' | 'ai_task' | 'advanced_branch' | 'integration_action';
  dependsOn?: string[];
  config: any;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  steps: any[];
  triggers: any[];
  variables: any;
  settings: any;
  integrations: string[];
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
  enabled: boolean;
}
