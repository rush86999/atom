<file_path>
atom/examples/llama-cpp-integration.ts
</file_path>

import { LlamaCPPBackend } from '../src/llm/llamaCPPBackend';
import { LlamaCPPManager } from '../src/llm/llama-setup';
import { EventEmitter } from 'events';

/**
 * 🦙 Complete Llama.cpp Integration Example for Small Businesses
 *
 * This demonstrates how to set up and use llama.cpp for:
 * - Creating automated workflows via natural language
 * - Setting up business automation systems
 * - Privacy-first AI without API costs
 */

interface SmallBusinessConfig {
  businessType: string;
  employeeCount: number;
  technicalSkill: 'beginner' | 'intermediate' | 'advanced';
  budget: number;
}

class SmallBusinessLlamaManager extends EventEmitter {
  private backend: LlamaCPPBackend;
  private setupManager: LlamaCPPManager;
  private config: SmallBusinessConfig;
  private isSetup = false;

  constructor(config: SmallBusinessConfig) {
    super();
    this.config = config;
    this.backend = new LlamaCPPBackend();
    this.setupManager = new LlamaCPPManager();

    // Choose optimal model based on business size
    const optimalModel = this.getOptimalModel();
    console.log(`🎯 Selected model: ${optimalModel.name} (${optimalModel.reason})`);
  }

  getOptimalModel() {
    if (this.config.employeeCount <= 3 && this.config.technicalSkill === 'beginner') {
      return {
        name: 'mistral-7b-Q4',
        path: './models/mistral-7b-instruct-q4.gguf',
        reason: 'Fast startup, low memory usage, perfect for simple automations'
      };
    }

    if (this.config.employeeCount <= 10) {
      return {
        name: 'llama-3-8b-Q4',
        path: './models/llama-3-8b-instruct-q4.gguf',
        reason: 'Balanced performance and quality for medium complexity tasks'
      };
    }

    return {
      name: 'llama-3-8b-Q8',
      path: './models/llama-3-8b-instruct-q8.gguf',
      reason: 'Higher quality for complex business processes'
    };
  }

  async setupBusinessAutomation(businessGoal: string) {
    console.log(`\n🏪 Setting up automation for: ${businessGoal}`);

    const setup = {
      goal: businessGoal,
      businessType: this.config.businessType,
      estimatedSetupTime: '5-10 minutes',
      dataPrivacy: '100% local - no cloud required'
    };

    try {
      // Auto-download and install llama.cpp
      await this.setupManager.downloadLlamaCPP();
      console.log('✅ Llama.cpp downloaded and installed');

      // Download appropriate model
      await this.setupManager.downloadModel('llama-3-8b', 'small');
      console.log('✅ Model downloaded and ready');

      // Start server
      await this.backend.startServer();
      this.isSetup = true;

      console.log('\n🚀 Ready - generating automation instructions...\n');

      // Generate specific instructions
      const instructions = await this.generateBusinessInstructions(businessGoal);

      return {
        setupComplete: true,
        instructions,
        serverUrl: this.backend.getServerURL(),
        modelFile: await this.getOptimalModel()
      };

    } catch (error) {
      console.error('❌ Setup failed:', error);
      throw error;
    }
  }

  async generateBusinessInstructions(goal: string): Promise<string> {
    const prompt = `
Business context: ${this.config.businessType}, ${this.config.employeeCount} employees
Goal: ${goal}
Skill level: ${this.config.technicalSkill}
Create a step-by-step automation guide with specific tools and expected time savings.
`;

    const response = await this.backend.generate({
      prompt,
      max_tokens: 1000,
      system: "You are a small business automation expert who creates practical, no-code automation guides."
    });

    return response.content;
  }

  async createQuickWorkflow(workflowType: string) {
    const workflows = {
      'receipt-tracking': {
        prompt: `Create 5-minute setup instructions for automated receipt tracking system for ${this.config.businessType} with ${this.config.employeeCount} employees`,
        expected: 'Save 4-6 hours/week on expense management'
      },
      'customer-followup': {
        prompt: `Generate a complete customer follow-up automation system for ${this.config.businessType} including email templates and scheduling`,
        expected: 'Increase customer retention by 30%'
      },
      'appointment-reminders': {
        prompt: `Design a no-show prevention system
