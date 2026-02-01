import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { SkillRegistry } from "../skills";
import { AgentProfile } from "./OrchestrationEngine";

export interface AgentDefinition {
  id: string;
  name: string;
  type: "specialist" | "generalist" | "coordinator" | "monitor";
  skills: string[];
  capabilities: string[];
  priority: number;
  confidence: number;
  description: string;
  executionConstraints: {
    maxConcurrent: number;
    timeout: number;
    maxRetries: number;
    fallbackStrategy: "retry" | "delegate" | "fail";
  };
}

export class AgentRegistry extends EventEmitter {
  private logger: Logger;
  private skillRegistry: SkillRegistry;
  private agents: Map<string, AgentDefinition> = new Map();

  constructor(skillRegistry: SkillRegistry) {
    super();
    this.logger = new Logger("AgentRegistry");
    this.skillRegistry = skillRegistry;
    this.initializePreconfiguredAgents();
  }

  private initializePreconfiguredAgents(): void {
    this.logger.info("Initializing preconfigured autonomous agents");

    // Business Strategist Agent
    this.registerAgent({
      id: "business-strategist",
      name: "Business Intelligence Officer",
      type: "specialist",
      skills: [
        "business-analysis",
        "market-research",
        "competitive-intelligence",
        "roi-calculation",
        "strategic-planning",
      ],
      capabilities: [
        "quantitative-analysis",
        "predictive-modeling",
        "risk-assessment",
        "revenue-optimization",
      ],
      priority: 9,
      confidence: 0.92,
      description:
        "Specializes in business intelligence, market analysis, and strategic revenue optimization",
      executionConstraints: {
        maxConcurrent: 3,
        timeout: 120000,
        maxRetries: 2,
        fallbackStrategy: "delegate",
      },
    });

    // Customer Success Agent
    this.registerAgent({
      id: "customer-success",
      name: "Customer Experience Manager",
      type: "specialist",
      skills: [
        "crm-integration",
        "customer-segmentation",
        "retention-strategies",
        "satisfaction-analysis",
        "feedback-loop",
      ],
      capabilities: [
        "sentiment-analysis",
        "personalization",
        "lifecycle-marketing",
        "upselling-optimization",
      ],
      priority: 8,
      confidence: 0.89,
      description:
        "Manages customer relationships and optimizes lifetime value through intelligent retention strategies",
      executionConstraints: {
        maxConcurrent: 5,
        timeout: 90000,
        maxRetries: 3,
        fallbackStrategy: "delegate",
      },
    });

    // Marketing Automation Agent
    this.registerAgent({
      id: "marketing-automation",
      name: "Digital Marketing Coordinator",
      type: "specialist",
      skills: [
        "content-creation",
        "social-media-automation",
        "campaign-optimization",
        "lead-generation",
        "a-b-testing",
      ],
      capabilities: [
        "trend-analysis",
        "audience-targeting",
        "conversion-optimization",
        "brand-consistency",
      ],
      priority: 7,
      confidence: 0.88,
      description:
        "Orchestrates marketing campaigns with data-driven optimization and automated content creation",
      executionConstraints: {
        maxConcurrent: 4,
        timeout: 60000,
        maxRetries: 2,
        fallbackStrategy: "retry",
      },
    });

    // Financial Planning Agent
    this.registerAgent({
      id: "financial-planner",
      name: "Personal Finance Advisor",
      type: "specialist",
      skills: [
        "goal-planning",
        "budget-optimization",
        "expense-analysis",
        "investment-strategy",
        "tax-optimization",
      ],
      capabilities: [
        "forecasting",
        "risk-assessment",
        "portfolio-analysis",
        "retirement-planning",
      ],
      priority: 9,
      confidence: 0.94,
      description:
        "Provides comprehensive financial planning and investment optimization based on business and personal goals",
      executionConstraints: {
        maxConcurrent: 2,
        timeout: 150000,
        maxRetries: 1,
        fallbackStrategy: "delegate",
      },
    });

    // Operations Manager Agent
    this.registerAgent({
      id: "operations-manager",
      name: "Business Operations Coordinator",
      type: "coordinator",
      skills: [
        "process-automation",
        "workflow-optimization",
        "resource-allocation",
        "efficiency-analysis",
        "scalability-planning",
      ],
      capabilities: [
        "system-integration",
        "bottleneck-detection",
        "performance-monitoring",
        "capacity-planning",
      ],
      priority: 8,
      confidence: 0.9,
      description:
        "Coordinates complex business operations and optimizes workflows across multiple systems",
      executionConstraints: {
        maxConcurrent: 1,
        timeout: 180000,
        maxRetries: 3,
        fallbackStrategy: "delegate",
      },
    });

    // Data Insights Agent
    this.registerAgent({
      id: "data-insights",
      name: "Analytics & Intelligence Officer",
      type: "specialist",
      skills: [
        "data-engineering",
        "performance-analytics",
        "predictive-modeling",
        "business-intelligence",
        "kpi-tracking",
      ],
      capabilities: [
        "machine-learning",
        "statistical-analysis",
        "data-visualization",
        "real-time-monitoring",
        "trend-forecasting",
      ],
      priority: 8,
      confidence: 0.91,
      description:
        "Provides deep analytics and actionable insights from business data with machine learning and predictive capabilities",
      executionConstraints: {
        maxConcurrent: 3,
        timeout: 120000,
        maxRetries: 2,
        fallbackStrategy: "delegate",
      },
    });

    // Web Development Agent
    this.registerAgent({
      id: "web-developer",
      name: "Full-Stack Engineer",
      type: "specialist",
      skills: [
        "react-nextjs",
        "full-stack-development",
        "api-design",
        "database-optimization",
        "development-workflows",
      ],
      capabilities: [
        "code-generation",
        "architecture-planning",
        "testing-automation",
        "deployment-pipeline",
        "performance-optimization",
      ],
      priority: 7,
      confidence: 0.93,
      description:
        "Handles web application development, optimization, and deployment automation",
      executionConstraints: {
        maxConcurrent: 2,
        timeout: 180000,
        maxRetries: 2,
        fallbackStrategy: "retry",
      },
    });

    // Communication Coordinator Agent
    this.registerAgent({
      id: "communication-coordinator",
      name: "Multi-Channel Communicator",
      type: "coordinator",
      skills: [
        "multi-channel-messaging",
        "meeting-coordination",
        "document-management",
        "notification-systems",
        "knowledge-sharing",
      ],
      capabilities: [
        "real-time-sync",
        "priority-routing",
        "response-automation",
        "escalation-management",
        "cross-platform-integration",
      ],
      priority: 9,
      confidence: 0.87,
      description:
        "Orchestrates communication across all channels including email, meetings, documents, and notifications",
      executionConstraints: {
        maxConcurrent: 4,
        timeout: 60000,
        maxRetries: 3,
        fallbackStrategy: "delegate",
      },
    });

    // Emergency Response Agent
    this.registerAgent({
      id: "emergency-response",
      name: "Critical Issues Manager",
      type: "specialist",
      skills: [
        "crisis-management",
        "incident-response",
        "system-recovery",
        "failover-activation",
        "stakeholder-notification",
      ],
      capabilities: [
        "real-time-monitoring",
        "automated-checkout",
        "rollback-execution",
        "escalation-triggers",
        "business-continuity",
      ],
      priority: 10,
      confidence: 0.95,
      description:
        "Handles critical system issues, failover scenarios, and business continuity management",
      executionConstraints: {
        maxConcurrent: 1,
        timeout: 30000,
        maxRetries: 1,
        fallbackStrategy: "delegate",
      },
    });
  }

  registerAgent(agentDefinition: AgentDefinition): void {
    this.agents.set(agentDefinition.id, agentDefinition);
    this.logger.info(
      `Registered agent: ${agentDefinition.name} (${agentDefinition.id})`,
    );
    this.emit("agent-registered", agentDefinition);
  }

  unregisterAgent(agentId: string): void {
    if (this.agents.has(agentId)) {
      const agent = this.agents.get(agentId)!;
      this.agents.delete(agentId);
      this.logger.info(`Unregistered agent: ${agent.name} (${agentId})`);
      this.emit("agent-unregistered", { agentId });
    }
  }

  getAgentDefinition(agentId: string): AgentDefinition | undefined {
    return this.agents.get(agentId);
  }

  getAllAgents(): AgentDefinition[] {
    return Array.from(this.agents.values());
  }

  findAgentsBySkill(skill: string): AgentDefinition[] {
    return Array.from(this.agents.values()).filter(
      (agent) =>
        agent.skills.includes(skill) || agent.capabilities.includes(skill),
    );
  }

  findAgentsForWorkflow(workflowTypes: string[]): AgentDefinition[] {
    const matchingAgents: AgentDefinition[] = [];
    const agentScores = new Map<string, number>();

    for (const agent of this.agents.values()) {
      const skillScore = workflowTypes.reduce((score, type) => {
        const hasSkill =
          agent.skills.includes(type) || agent.capabilities.includes(type);
        return score + (hasSkill ? 1 : 0);
      }, 0);

      if (skillScore > 0) {
        agentScores.set(agent.id, skillScore);
      }
    }

    // Sort by score and return
    return Array.from(agentScores.entries())
      .sort(([, scoreA], [, scoreB]) => scoreB - scoreA)
      .map(([agentId]) => this.agents.get(agentId)!);
  }

  getAgentHealthStatus(): Record<
    string,
    {
      id: string;
      name: string;
      status: "healthy" | "degraded" | "critical";
      lastUsed?: Date;
      confidence: number;
    }
  > {
    const healthStatus: ReturnType<AgentRegistry["getAgentHealthStatus"]> = {};

    for (const [id, agent] of this.agents.entries()) {
      healthStatus[id] = {
        id: agent.id,
        name: agent.name,
        status:
          agent.confidence > 0.8
            ? "healthy"
            : agent.confidence > 0.6
              ? "degraded"
              : "critical",
        confidence: agent.confidence,
      };
    }

    return healthStatus;
  }

  async optimizeAgentPool(): Promise<void> {
    const healthStatus = this.getAgentHealthStatus();
    const criticalAgents = Object.values(healthStatus).filter(
      (s) => s.status === "critical",
    );

    if (criticalAgents.length > 0) {
      this.logger.warn(
        `Found ${criticalAgents.length} critical agents`,
        criticalAgents,
      );
      this.emit("optimization-needed", { criticalAgents });
    }
  }
}
