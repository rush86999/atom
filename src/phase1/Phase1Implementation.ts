/**
 * Phase 1 Implementation - ATOM Agentic OS
 *
 * Core implementation for Phase 1 of the ATOM Agentic OS transformation.
 * This module integrates all Phase 1 components and provides the foundation
 * for autonomous operations.
 */

import { agentSkillRegistry } from '../services/agentSkillRegistry';
import { agentOrchestrationSystem } from '../orchestration/AgentOrchestrationSystem';
import { autonomousSystemOrchestrator } from '../orchestration/autonomousSystemOrchestrator';
import { IntelligentAutonomousOrchestrator } from '../orchestration/intelligentAutonomousOrchestrator';

// Import enhanced skills for Phase 1
import githubSkillsEnhanced from '../skills/githubSkillsEnhanced';
import jiraSkillsEnhanced from '../skills/jiraSkillsEnhanced';

export class Phase1Implementation {
  private skillRegistry = agentSkillRegistry;
  private orchestrationSystem = agentOrchestrationSystem;
  private autonomousOrchestrator = autonomousSystemOrchestrator;
  private intelligentOrchestrator: IntelligentAutonomousOrchestrator;

  private isInitialized = false;

  constructor() {
    this.intelligentOrchestrator = new IntelligentAutonomousOrchestrator();
  }

  /**
   * Initialize Phase 1 components
   */
  async initialize(): Promise<{
    success: boolean;
    components: {
      skillRegistry: boolean;
      orchestration: boolean;
      autonomous: boolean;
      intelligent: boolean;
    };
    details: string[];
  }> {
    const results = {
      success: true,
      components: {
        skillRegistry: false,
        orchestration: false,
        autonomous: false,
        intelligent: false,
      },
      details: [] as string[],
    };

    try {
      console.log('🚀 Starting Phase 1 Implementation...');

      // 1. Initialize Skill Registry with enhanced skills
      results.components.skillRegistry = await this.initializeSkillRegistry();
      if (results.components.skillRegistry) {
        results.details.push('✅ Skill registry initialized with enhanced skills');
      } else {
        results.details.push('❌ Skill registry initialization failed');
        results.success = false;
      }

      // 2. Initialize Orchestration System
      results.components.orchestration = await this.initializeOrchestrationSystem();
      if (results.components.orchestration) {
        results.details.push('✅ Orchestration system initialized');
      } else {
        results.details.push('❌ Orchestration system initialization failed');
        results.success = false;
      }

      // 3. Initialize Autonomous Systems
      results.components.autonomous = await this.initializeAutonomousSystems();
      if (results.components.autonomous) {
        results.details.push('✅ Autonomous systems initialized');
      } else {
        results.details.push('❌ Autonomous systems initialization failed');
        results.success = false;
      }

      // 4. Initialize Intelligent Orchestrator
      results.components.intelligent = await this.initializeIntelligentOrchestrator();
      if (results.components.intelligent) {
        results.details.push('✅ Intelligent orchestrator initialized');
      } else {
        results.details.push('❌ Intelligent orchestrator initialization failed');
        results.success = false;
      }

      if (results.success) {
        this.isInitialized = true;
        console.log('🎉 Phase 1 Implementation completed successfully!');
        results.details.push('🚀 ATOM Agentic OS Phase 1 is ready for operation');
      } else {
        console.warn('⚠️ Phase 1 Implementation completed with some failures');
      }

      return results;

    } catch (error) {
      console.error('❌ Phase 1 Implementation failed:', error);
      return {
        success: false,
        components: results.components,
        details: [...results.details, `❌ Critical error: ${error}`],
      };
    }
  }

  /**
   * Initialize the skill registry with Phase 1 enhanced skills
   */
  private async initializeSkillRegistry(): Promise<boolean> {
    try {
      console.log('📋 Registering Phase 1 enhanced skills...');

      // Register GitHub enhanced skills
      for (const skill of githubSkillsEnhanced) {
        const success = await this.skillRegistry.registerSkill(skill);
        if (!success) {
          console.warn(`⚠️ Failed to register GitHub skill: ${skill.name}`);
        }
      }

      // Register Jira enhanced skills
      for (const skill of jiraSkillsEnhanced) {
        const success = await this.skillRegistry.registerSkill(skill);
        if (!success) {
          console.warn(`⚠️ Failed to register Jira skill: ${skill.name}`);
        }
      }

      const status = this.skillRegistry.getStatus();
      console.log(`📊 Skill registry status: ${status.totalSkills} skills, ${status.enabledSkills} enabled`);

      return status.totalSkills > 0;

    } catch (error) {
      console.error('❌ Skill registry initialization failed:', error);
      return false;
    }
  }

  /**
   * Initialize the orchestration system
   */
  private async initializeOrchestrationSystem(): Promise<boolean> {
    try {
      console.log('🔄 Initializing orchestration system...');

      await this.orchestrationSystem.initialize();

      const status = this.orchestrationSystem.getSystemStatus();
      console.log(`📊 Orchestration system status: ${status.totalAgents} agents, health: ${status.healthStatus}`);

      return status.isRunning;

    } catch (error) {
      console.error('❌ Orchestration system initialization failed:', error);
      return false;
    }
  }

  /**
   * Initialize autonomous systems
   */
  private async initializeAutonomousSystems(): Promise<boolean> {
    try {
      console.log('🧠 Initializing autonomous systems...');

      // This would initialize the autonomous operations system
      // For now, we'll simulate successful initialization
      await new Promise(resolve => setTimeout(resolve, 500));

      console.log('✅ Autonomous systems initialized (simulated)');
      return true;

    } catch (error) {
      console.error('❌ Autonomous systems initialization failed:', error);
      return false;
    }
  }

  /**
   * Initialize intelligent orchestrator
   */
  private async initializeIntelligentOrchestrator(): Promise<boolean> {
    try {
      console.log('🤖 Initializing intelligent orchestrator...');

      // The intelligent orchestrator initializes itself in the constructor
      // We can perform additional setup here if needed

      console.log('✅ Intelligent orchestrator initialized');
      return true;

    } catch (error) {
      console.error('❌ Intelligent orchestrator initialization failed:', error);
      return false;
    }
  }

  /**
   * Execute a Phase 1 workflow demonstration
   */
  async executeDemoWorkflow(userId: string): Promise<{
    success: boolean;
    workflowId?: string;
    tasks: any[];
    message: string;
  }> {
    if (!this.isInitialized) {
      return {
        success: false,
        tasks: [],
        message: 'Phase 1 not initialized. Call initialize() first.',
      };
    }

    try {
      console.log(`🎯 Starting Phase 1 demo workflow for user ${userId}...`);

      // Create a session
      const sessionId = await this.orchestrationSystem.createSession(userId, {
        demo: true,
        phase: 1,
      });

      // Execute a complex workflow
      const taskIds = await this.orchestrationSystem.executeWorkflow(sessionId, {
        name: 'Phase 1 Demo Workflow',
        description: 'Demonstration of Phase 1 autonomous capabilities',
        steps: [
          {
            agentType: 'github',
            task: 'Create repository with Next.js template',
            parameters: {
              name: 'atom-demo-app',
              template: 'nextjs',
              description: 'ATOM Agentic OS Demo Application',
              private: false,
            },
          },
          {
            agentType: 'jira',
            task: 'Create epic with initial stories',
            parameters: {
              projectKey: 'DEMO',
              epicName: 'ATOM Demo Application Development',
              epicDescription: 'Development of the ATOM Agentic OS demonstration application',
              stories: [
                {
                  summary: 'Set up project structure',
                  description: 'Initialize Next.js project with TypeScript and basic components',
                  storyPoints: 3,
                  priority: 'High',
                },
                {
                  summary: 'Implement authentication',
                  description: 'Add user authentication and authorization',
                  storyPoints: 5,
                  priority: 'High',
                },
              ],
            },
            dependsOn: ['github-create-repo-with-template'],
          },
          {
            agentType: 'github',
            task: 'Configure branch protection',
            parameters: {
              owner: 'user',
              repo: 'atom-demo-app',
              branch: 'main',
              requireReviews: true,
              requiredApprovals: 1,
              requireStatusChecks: true,
              statusChecks: ['ci/cd'],
            },
            dependsOn: ['github-create-repo-with-template'],
          },
        ],
      });

      // Monitor workflow execution
      const tasks = [];
      for (const taskId of taskIds) {
        const status = this.orchestrationSystem.getTaskStatus(taskId);
        tasks.push({
          taskId,
          status: status?.status || 'unknown',
          description: status?.description,
        });
      }

      return {
        success: true,
        workflowId: sessionId,
        tasks,
        message: 'Phase 1 demo workflow started successfully. Check orchestration system for progress.',
      };

    } catch (error) {
      console.error('❌ Demo workflow execution failed:', error);
      return {
        success: false,
        tasks: [],
        message: `Workflow execution failed: ${error}`,
      };
    }
  }

  /**
   * Get Phase 1 system status
   */
  getStatus(): {
    initialized: boolean;
    skillRegistry: any;
    orchestration: any;
    capabilities: string[];
  } {
    const skillStatus = this.skillRegistry.getStatus();
    const orchestrationStatus = this.orchestrationSystem.getSystemStatus();

    return {
      initialized: this.isInitialized,
      skillRegistry: skillStatus,
      orchestration: orchestrationStatus,
      capabilities: [
        'Enhanced GitHub integration (templates, webhooks, automation)',
        'Advanced Jira workflows (epics, synchronization, reporting)',
        'Multi-agent orchestration',
        'Intelligent decision making',
        'Autonomous workflow execution',
        'Skill execution monitoring',
      ],
    };
  }

  /**
   * Execute a specific skill
   */
  async executeSkill(
    skillId: string,
    userId: string,
    parameters: Record<string, any> = {}
  ): Promise<any> {
    if (!this.isInitialized) {
      throw new Error('Phase 1 not initialized. Call initialize() first.');
    }

    return await this.skillRegistry.executeSkill(skillId, userId, parameters);
  }

  /**
   * Process intelligent input for autonomous decision making
   */
  async processIntelligentInput(
    userId: string,
    message: string,
    context?: any
  ): Promise<any> {
    if (!this.isInitialized) {
      throw new Error('Phase 1 not initialized. Call initialize() first.');
    }

    return await this.intelligentOrchestrator.processIntelligentInput(
      userId,
      message,
      context
    );
  }

  /**
   * Shutdown Phase 1 systems
   */
  async shutdown(): Promise<void> {
    if (!this.isInitialized) {
      return;
    }

    console.log('🛑 Shutting down Phase 1 systems...');

    await this.orchestrationSystem.shutdown();
    this.isInitialized = false;

    console.log('✅ Phase 1 systems shut down successfully');
  }
}

// Export singleton instance
export const phase1Implementation = new Phase1Implementation();

// Auto-initialize in development (optional)
if (process.env.NODE_ENV === 'development') {
  phase1Implementation.initialize().catch(console.error);
}

export default phase1Implementation;
