import axios from 'axios';
import { EventEmitter } from 'events';

interface AutonomousAgentConfig {
  userId: string;
  mode: 'startup' | 'continuous' | 'learning';
  apiEndpoint: string;
  enableLearning: boolean;
}

interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
  celeryConnected: boolean;
  activeTriggers: number;
  lastUpdate: Date;
}

export class AutonomousAgentSystem extends EventEmitter {
  private config: AutonomousAgentConfig;
  private apiEndpoint: string;
  private isRunning: boolean = false;
  private status: SystemStatus;
  private heartbeat: any;

  constructor(config: AutonomousAgentConfig) {
    super();
    this.config = config;
    this.apiEndpoint = config.apiEndpoint || 'http://localhost:8004';
    this.status = {
      health: 'healthy',
      celeryConnected: false,
      activeTriggers: 0,
      lastUpdate: new Date()
    };
  }

  async start(): Promise<void> {
    console.log(`[AutonomousAgent] Starting for user: ${this.config.userId}`);
    this.isRunning = true;

    // Test system connectivity
    await this.systemHealthCheck();

    // Setup autonomous triggers
    await this.setupAutonomousMonitoring();

    // Start heartbeat
    this.startHeartbeat();

    this.emit('started', { status: this.status });
  }

  async systemHealthCheck(): Promise<void> {
    try {
      const response = await axios.get(`${this.apiEndpoint}/health`, { timeout: 5000 });
      this.status.celeryConnected = response.status === 200;
      this.status.lastUpdate = new Date();
    } catch {
      this.status.celeryConnected = false;
      this.status.health = 'degraded';
    }
  }

  async setupAutonomousMonitoring(): Promise<void> {
    const triggers = [
      {
        workflow_id: `autonomous-sales-${this.config.userId}`,
        trigger_type: 'sales-threshold',
        parameters: { threshold: 25 },
        schedule: '*/15 * * * *'
      },
      {
        workflow_id: `autonomous-website-${this.config.userId}`,
        trigger_type: 'web-polling',
        parameters: { url: 'https://example.com' },
        schedule: '*/10 * * * *'
      },
      {
        workflow_id: `autonomous-performance-${this.config.userId}`,
        trigger_type: 'api-monitoring',
        parameters: { endpoint: `${this.apiEndpoint}/health`, threshold: 2000 },
        schedule: '*/5 * * * *'
      }
    ];

    let registeredTriggers = 0;
    for (const trigger of triggers) {
      try {
        await axios.post(`${this.apiEndpoint}/triggers/smart`, trigger);
        registeredTriggers++;
      } catch (error) {
        console.warn(`Failed to register trigger ${trigger.workflow_id}:`, error);
      }
    }

    this.status.activeTriggers = registeredTriggers;
  }

  startHeartbeat(): void {
    this.heartbeat = setInterval(async () => {
      await this.systemHealthCheck();
      this.emit('heartbeat', this.status);
    }, 30000); // 30 seconds
  }

  getStatus(): SystemStatus {
    return { ...this.status, lastUpdate: new Date() };
  }

  async stop(): Promise<void> {
    this.isRunning = false;
    if (this.heartbeat) {
      clearInterval(this.heartbeat);
    }
    this.emit('stopped');
  }
}

// Quick start function
export async function startAutonomousSystem(userId: string): Promise<AutonomousAgentSystem> {
  const system = new AutonomousAgentSystem({
    userId,
    mode: 'continuous',
    apiEndpoint: process.env.AUTONOMOUS_API_URL || 'http://localhost:8004',
    enableLearning: true
  });

  await system.start();
  return system;
}
