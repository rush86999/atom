import { EventEmitter } from 'events';
import { CommunicationAnalyzer } from './communicationAnalyzer';
import { CommunicationScheduler } from './communicationScheduler';
import { PlatformRouter } from './platformRouter';
import { CommunicationMemory } from './communicationMemory';
import { RelationshipTracker } from './relationshipTracker';
import { ToneAnalyzer } from './toneAnalyzer';
import { CrisisDetector } from './crisisDetector';
import { AutonomousCommunications, CommunicationContext } from './types';

export class AutonomousCommunicationOrchestrator extends EventEmitter {
  private analyzer: CommunicationAnalyzer;
  private scheduler: CommunicationScheduler;
  private router: PlatformRouter;
  private memory: CommunicationMemory;
  private relationshipTracker: RelationshipTracker;
  private toneAnalyzer: ToneAnalyzer;
  private crisisDetector: CrisisDetector;

  private isRunning = false;
  private userId: string;
  private interval: NodeJS.Timeout | null = null;
  private learningEnabled = true;

  constructor(userId: string) {
    super();
    this.userId = userId;
    this.analyzer = new CommunicationAnalyzer();
    this.scheduler = new CommunicationScheduler();
    this.router = new PlatformRouter(userId);
    this.memory = new CommunicationMemory(userId);
    this.relationshipTracker = new RelationshipTracker(userId);
    this.toneAnalyzer = new ToneAnalyzer();
    this.crisisDetector = new CrisisDetector();
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    this.crisisDetector.on('crisis-detected', async (context: CommunicationContext) => {
      await this.handleCrisisCommunication(context);
    });

    this.relationshipTracker.on('relationship-stale', async (contactId: string) => {
      await this.handleRelationshipMaintenance(contactId);
    });

    this.scheduler.on('communication-due', async (communication: AutonomousCommunications) => {
      await this.executeScheduledCommunication(communication);
    });
  }

  public async start(): Promise<void> {
    if (this.isRunning) return;

    this.isRunning = true;
    console.log(`[AutonomousCommunication] Starting for user ${this.userId}`);

    await this.router.initializeConnections();
    await this.loadHistoricalContext();

    this.interval = setInterval(async () => {
      await this.performAutonomousCheck();
    }, 30000);

    this.emit('started');
  }

  public async stop(): Promise<void> {
    if (!this.isRunning) return;

    this.isRunning = false;

    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }

    await this.router.cleanup();
    this.emit('stopped');
  }

  private async performAutonomousCheck(): Promise<void> {
    try {
      const context = await this.buildCurrentContext();
      const analysis = await this.analyzer.analyzeCommunicationPatterns(context);
      const opportunities = await this.identifyCommunicationOpportunities(context, analysis);

      await this.scheduler.scheduleFromAnalysis(opportunities);

      if (this.learningEnabled) {
        await this.updateLearningModels(context);
      }

    } catch (error) {
      console.error('[AutonomousCommunication] Error in autonomous check:', error);
      this.emit('error', error);
    }
  }

  private async executeCommunications(communications: AutonomousCommunications[]): Promise<void> {
    for (const communication of communications) {
      try {
        const success = await this.router.sendCommunication(communication);
        if (success) {
          await this.memory.recordCommunication(communication);
          await this.relationshipTracker.updateInteraction(communication.recipient);
        }
      } catch (error) {
        console.error('Failed to execute communication:', error);
        this.emit('error', error);
      }
    }
  }

  public async executeWorkflows(workflows: string[], context: any): Promise<{
    success: boolean;
    results: any[];
    insights: any[];
  }> {
    const results: any[] = [];
    const insights: any[] = [];

    for (const workflow of workflows) {
      try {
        const result = await this.executeSingleWorkflow(workflow, context);
        results.push(result);

        // Generate insights for learning
        if (result.success) {
          insights.push({
            workflow,
            outcome: result.message || 'Completed successfully',
            metadata: result.metadata
          });
        }
      } catch (error) {
        results.push({
          workflow,
          success: false,
          error: error.message
        });
      }
    }

    return { success: results.some(r => r.success), results, insights };
  }

  private async executeSingleWorkflow(workflow: string, context: any) {
    let result = { success: false, message: '', metadata: {} };

    switch (workflow) {
      case 'shopify-automation':
        result = await this.executeShopifyAutomation(context);
        break;
      case 'social-media-automation':
        result = await this.executeSocialMediaAutomation(context);
