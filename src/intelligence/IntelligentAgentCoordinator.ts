import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { v4 as uuidv4 } from "uuid";

/**
 * Advanced Agent Coordination & Intelligence Layer
 * 
 * This layer provides intelligent coordination between multiple AI agents,
 * dynamic task allocation, learning capabilities, and emergent behavior.
 */

export interface AgentCapability {
  id: string;
  name: string;
  type: 'reasoning' | 'memory' | 'communication' | 'analysis' | 'planning' | 'execution' | 'monitoring';
  proficiency: number; // 0-1
  experience: number; // 0-1
  specialties: string[];
  resources: {
    cpu: number;
    memory: number;
    bandwidth: number;
  };
  availability: {
    active: boolean;
    lastUsed: Date;
    currentLoad: number;
    maxConcurrentTasks: number;
  };
  performance: {
    averageResponseTime: number;
    successRate: number;
    accuracy: number;
    efficiency: number;
  };
  learning: {
    adaptationRate: number;
    feedbackScore: number;
    improvementRate: number;
  };
}

export interface AgentProfile {
  id: string;
  name: string;
  description: string;
  personality: {
    openness: number;        // 0-1
    conscientiousness: number; // 0-1
    extraversion: number;     // 0-1
    agreeableness: number;    // 0-1
    neuroticism: number;      // 0-1
  };
  capabilities: AgentCapability[];
  preferences: {
    communicationStyle: 'formal' | 'casual' | 'technical' | 'creative';
    collaborationStyle: 'leader' | 'follower' | 'collaborator' | 'specialist';
    decisionMakingStyle: 'analytical' | 'intuitive' | 'systematic' | 'creative';
    problemSolvingStyle: 'direct' | 'systematic' | 'creative' | 'collaborative';
  };
  knowledge: {
    domains: Array<{
      name: string;
      proficiency: number;
      lastUpdated: Date;
      sources: string[];
    }>;
    skills: Array<{
      name: string;
      level: number;
      certified: boolean;
      experience: Date;
    }>;
    context: Record<string, any>;
  };
  relationships: {
    collaborators: string[];
    mentors: string[];
    mentees: string[];
    conflicts: string[];
    trustScores: Map<string, number>;
  };
  metadata: {
    version: string;
    createdAt: Date;
    updatedAt: Date;
    totalInteractions: number;
    successfulTasks: number;
    failedTasks: number;
  };
}

export interface IntelligentTask {
  id: string;
  type: 'analysis' | 'reasoning' | 'planning' | 'execution' | 'coordination' | 'learning' | 'monitoring';
  priority: 'critical' | 'high' | 'normal' | 'low';
  complexity: 'trivial' | 'simple' | 'moderate' | 'complex' | 'expert';
  domain: string;
  description: string;
  context: Record<string, any>;
  requirements: {
    capabilities: string[];
    proficiency: number;
    resources: {
      cpu: number;
      memory: number;
      bandwidth: number;
    };
    collaboration: {
      required: boolean;
      teamSize: number;
      coordination: number;
    };
  };
  constraints: {
    deadline?: Date;
    quality: number; // 0-1
    budget?: number;
    privacy: number; // 0-1
  };
  objectives: Array<{
    id: string;
    description: string;
    metric: string;
    target: number;
    weight: number;
  }>;
  dependencies: string[];
  deliverables: Array<{
    type: string;
    format: string;
    quality: number;
  }>;
  status: 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  assignments: TaskAssignment[];
  createdAt: Date;
  updatedAt: Date;
  startedAt?: Date;
  completedAt?: Date;
}

export interface TaskAssignment {
  id: string;
  taskId: string;
  agentId: string;
  role: 'primary' | 'secondary' | 'reviewer' | 'consultant';
  responsibilities: string[];
  allocation: {
    percentage: number; // 0-1
    estimatedTime: number; // milliseconds
    actualTime?: number;
  };
  performance: {
    quality: number;
    efficiency: number;
    collaboration: number;
    accuracy: number;
  };
  status: 'assigned' | 'accepted' | 'in_progress' | 'completed' | 'rejected';
  assignedAt: Date;
  acceptedAt?: Date;
  completedAt?: Date;
}

export interface AgentCollaboration {
  id: string;
  type: 'direct' | 'mediated' | 'hierarchical' | 'peer' | 'team';
  participants: string[];
  context: {
    taskId?: string;
    objective: string;
    rules: string[];
    tools: string[];
  };
  communication: {
    style: 'synchronous' | 'asynchronous' | 'mixed';
    frequency: number; // messages per hour
    protocol: string;
  };
  dynamics: {
    leadership: string;
    decisionMaking: 'consensus' | 'majority' | 'hierarchical' | 'expert';
    conflictResolution: 'collaborative' | 'authoritative' | 'mediated';
  };
  outcomes: {
    taskCompleted: boolean;
    quality: number;
    efficiency: number;
    collaborationScore: number;
    learningGained: number;
  };
  metrics: {
    duration: number;
    messages: number;
    conflicts: number;
    resolutions: number;
    satisfaction: number;
  };
  createdAt: Date;
  completedAt?: Date;
}

export interface CollectiveIntelligence {
  id: string;
  type: 'emergent' | 'coordinated' | 'distributed' | 'hybrid';
  agents: string[];
  focus: {
    domain: string;
    objective: string;
    timeframe: {
      start: Date;
      end: Date;
    };
  };
  capabilities: {
    reasoning: number;
    creativity: number;
    problemSolving: number;
    learning: number;
    adaptation: number;
  };
  knowledge: {
    shared: Record<string, any>;
    distributed: Map<string, any>;
    emergent: Record<string, any>;
  };
  behavior: {
    patterns: Array<{
      name: string;
      frequency: number;
      effectiveness: number;
      conditions: string[];
    }>;
    adaptations: Array<{
      trigger: string;
      change: string;
      result: string;
      timestamp: Date;
    }>;
  };
  metrics: {
    collectivePerformance: number;
    synergy: number;
    learningRate: number;
    adaptationSpeed: number;
  };
  createdAt: Date;
  updatedAt: Date;
}

export interface IntelligenceLayer {
  learning: {
    modelVersion: string;
    algorithms: string[];
    dataSources: string[];
    updateFrequency: number; // hours
    accuracy: number;
    confidence: number;
  };
  reasoning: {
    capabilities: string[];
    logicEngine: string;
    inference: string;
    explanation: string;
  };
  adaptation: {
    feedbackLoop: boolean;
    selfImprovement: boolean;
    evolution: boolean;
    knowledgeAcquisition: boolean;
  };
  prediction: {
    models: string[];
    accuracy: number;
    timeHorizon: number; // hours
    confidence: number;
  };
  optimization: {
    objectives: string[];
    algorithms: string[];
    constraints: string[];
    effectiveness: number;
  };
}

export interface CoordinationStrategy {
  id: string;
  name: string;
  description: string;
  type: 'centralized' | 'decentralized' | 'hybrid' | 'adaptive';
  algorithm: string;
  criteria: {
    efficiency: number;
    quality: number;
    collaboration: number;
    learning: number;
  };
  parameters: Record<string, any>;
  applicability: {
    taskTypes: string[];
    teamSizes: number[];
    complexities: string[];
    domains: string[];
  };
  performance: {
    successRate: number;
    averageDuration: number;
    resourceEfficiency: number;
    satisfaction: number;
  };
}

export class IntelligentAgentCoordinator extends EventEmitter {
  private logger: Logger;
  private agents: Map<string, AgentProfile>;
  private tasks: Map<string, IntelligentTask>;
  private collaborations: Map<string, AgentCollaboration>;
  private collectiveIntelligences: Map<string, CollectiveIntelligence>;
  private intelligenceLayer: IntelligenceLayer;
  private coordinationStrategies: Map<string, CoordinationStrategy>;
  private taskQueue: IntelligentTask[];
  private activeCollaborations: Map<string, AgentCollaboration>;
  private learningData: Array<{
    timestamp: Date;
    context: Record<string, any>;
    action: string;
    outcome: Record<string, any>;
    feedback: number;
  }>;
  private performanceMetrics: Map<string, any>;

  constructor() {
    super();
    this.logger = new Logger("IntelligentAgentCoordinator");
    
    this.agents = new Map();
    this.tasks = new Map();
    this.collaborations = new Map();
    this.collectiveIntelligences = new Map();
    this.taskQueue = [];
    this.activeCollaborations = new Map();
    this.learningData = [];
    this.performanceMetrics = new Map();
    
    this.intelligenceLayer = this.initializeIntelligenceLayer();
    this.coordinationStrategies = new Map();
    
    this.loadCoordinationStrategies();
    this.startIntelligenceProcessing();
    this.startLearningProcess();
    
    this.logger.info("Intelligent Agent Coordinator initialized");
  }

  private initializeIntelligenceLayer(): IntelligenceLayer {
    return {
      learning: {
        modelVersion: "2.0.0",
        algorithms: ["reinforcement_learning", "transfer_learning", "meta_learning"],
        dataSources: ["task_outcomes", "agent_performance", "collaboration_metrics"],
        updateFrequency: 6, // hours
        accuracy: 0.92,
        confidence: 0.87,
      },
      reasoning: {
        capabilities: ["logical_inference", "causal_reasoning", "analogical_reasoning", "bayesian_inference"],
        logicEngine: "hybrid_neural_symbolic",
        inference: "probabilistic_graphical_models",
        explanation: "attention_based_interpretability",
      },
      adaptation: {
        feedbackLoop: true,
        selfImprovement: true,
        evolution: true,
        knowledgeAcquisition: true,
      },
      prediction: {
        models: ["temporal_transformer", "graph_neural_network", "ensemble_method"],
        accuracy: 0.89,
        timeHorizon: 24, // hours
        confidence: 0.85,
      },
      optimization: {
        objectives: ["maximize_quality", "minimize_time", "optimize_resources", "enhance_learning"],
        algorithms: ["multi_objective_optimization", "genetic_algorithm", "simulated_annealing"],
        constraints: ["resource_limits", "quality_thresholds", "time_constraints"],
        effectiveness: 0.91,
      },
    };
  }

  private loadCoordinationStrategies(): void {
    const strategies: CoordinationStrategy[] = [
      {
        id: "centralized_hierarchy",
        name: "Centralized Hierarchy",
        description: "Central coordinator assigns tasks and monitors progress",
        type: "centralized",
        algorithm: "optimal_assignment",
        criteria: { efficiency: 0.85, quality: 0.80, collaboration: 0.60, learning: 0.70 },
        parameters: {
          optimizationObjective: "minimize_total_time",
          allowSplitting: false,
          loadBalancing: true,
        },
        applicability: {
          taskTypes: ["execution", "monitoring"],
          teamSizes: [1, 2, 3, 4],
          complexities: ["trivial", "simple", "moderate"],
          domains: ["all"],
        },
        performance: {
          successRate: 0.88,
          averageDuration: 45000,
          resourceEfficiency: 0.82,
          satisfaction: 0.75,
        },
      },
      {
        id: "decentralized_swarm",
        name: "Decentralized Swarm",
        description: "Self-organizing agents collaborate through local interactions",
        type: "decentralized",
        algorithm: "swarm_intelligence",
        criteria: { efficiency: 0.75, quality: 0.85, collaboration: 0.90, learning: 0.95 },
        parameters: {
          localRadius: 3,
          communicationRange: 2,
          adaptationRate: 0.1,
          emergentBehavior: true,
        },
        applicability: {
          taskTypes: ["analysis", "reasoning", "coordination"],
          teamSizes: [5, 6, 7, 8, 9, 10],
          complexities: ["moderate", "complex", "expert"],
          domains: ["research", "creative", "exploration"],
        },
        performance: {
          successRate: 0.91,
          averageDuration: 62000,
          resourceEfficiency: 0.88,
          satisfaction: 0.87,
        },
      },
      {
        id: "adaptive_hybrid",
        name: "Adaptive Hybrid",
        description: "Dynamically switches between coordination strategies",
        type: "hybrid",
        algorithm: "contextual_optimization",
        criteria: { efficiency: 0.90, quality: 0.88, collaboration: 0.85, learning: 0.90 },
        parameters: {
          strategySelectionModel: "multi_armed_bandit",
          adaptationThreshold: 0.15,
          evaluationPeriod: 1000, // tasks
          hybridMode: "sequential",
        },
        applicability: {
          taskTypes: ["all"],
          teamSizes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          complexities: ["all"],
          domains: ["all"],
        },
        performance: {
          successRate: 0.93,
          averageDuration: 48000,
          resourceEfficiency: 0.86,
          satisfaction: 0.82,
        },
      },
    ];

    for (const strategy of strategies) {
      this.coordinationStrategies.set(strategy.id, strategy);
    }

    this.logger.info(`Loaded ${strategies.length} coordination strategies`);
  }

  // Agent Management
  async registerAgent(agent: AgentProfile): Promise<void> {
    this.agents.set(agent.id, agent);
    
    // Initialize performance tracking
    this.performanceMetrics.set(agent.id, {
      totalTasks: 0,
      completedTasks: 0,
      failedTasks: 0,
      averageQuality: 0,
      averageEfficiency: 0,
      collaborationScore: 0,
      learningProgress: 0,
    });

    this.logger.info(`Agent registered: ${agent.name} (${agent.id})`);
    this.emit("agent-registered", { agentId: agent.id, name: agent.name });
  }

  async unregisterAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (agent) {
      // Clean up active assignments
      await this.reassignAgentTasks(agentId);
      
      this.agents.delete(agentId);
      this.performanceMetrics.delete(agentId);
      
      this.logger.info(`Agent unregistered: ${agent.name} (${agentId})`);
      this.emit("agent-unregistered", { agentId, name: agent.name });
    }
  }

  async updateAgentProfile(agentId: string, updates: Partial<AgentProfile>): Promise<void> {
    const agent = this.agents.get(agentId);
    if (agent) {
      Object.assign(agent, updates);
      agent.metadata.updatedAt = new Date();
      
      this.agents.set(agentId, agent);
      this.logger.info(`Agent profile updated: ${agent.name} (${agentId})`);
      this.emit("agent-profile-updated", { agentId, name: agent.name });
    }
  }

  // Task Management
  async submitTask(task: Omit<IntelligentTask, 'id' | 'status' | 'assignments' | 'createdAt' | 'updatedAt'>): Promise<string> {
    const taskId = uuidv4();
    const intelligentTask: IntelligentTask = {
      ...task,
      id: taskId,
      status: 'pending',
      assignments: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    this.tasks.set(taskId, intelligentTask);
    this.taskQueue.push(intelligentTask);

    // Process queue
    this.processTaskQueue();

    this.logger.info(`Task submitted: ${task.description} (${taskId})`);
    this.emit("task-submitted", { taskId, description: task.description });

    return taskId;
  }

  private async processTaskQueue(): Promise<void> {
    while (this.taskQueue.length > 0) {
      const task = this.taskQueue.shift();
      if (!task) continue;

      try {
        await this.assignTask(task);
      } catch (error) {
        this.logger.error(`Failed to assign task ${task.id}:`, error);
        task.status = 'failed';
        task.updatedAt = new Date();
      }
    }
  }

  private async assignTask(task: IntelligentTask): Promise<void> {
    task.status = 'assigned';
    task.updatedAt = new Date();

    // Analyze task requirements
    const taskAnalysis = this.analyzeTaskRequirements(task);
    
    // Select optimal coordination strategy
    const strategy = this.selectCoordinationStrategy(task, taskAnalysis);
    
    // Identify suitable agents
    const suitableAgents = this.findSuitableAgents(task, taskAnalysis);
    
    // Form team if collaboration required
    if (task.requirements.collaboration.required) {
      await this.formCollaborativeTeam(task, suitableAgents, strategy);
    } else {
      // Assign to single best agent
      const bestAgent = this.selectBestAgent(suitableAgents, task);
      if (bestAgent) {
        await this.assignTaskToAgent(task, bestAgent, 'primary');
      }
    }

    this.tasks.set(task.id, task);
    this.emit("task-assigned", { taskId: task.id, strategy: strategy.name });
  }

  private analyzeTaskRequirements(task: IntelligentTask): any {
    return {
      requiredCapabilities: this.deduceRequiredCapabilities(task),
      difficultyScore: this.calculateDifficultyScore(task),
      collaborationComplexity: this.estimateCollaborationComplexity(task),
      timeCriticality: this.assessTimeCriticality(task),
      resourceRequirements: task.requirements.resources,
    };
  }

  private selectCoordinationStrategy(task: IntelligentTask, analysis: any): CoordinationStrategy {
    const strategies = Array.from(this.coordinationStrategies.values());
    
    // Score strategies based on task characteristics
    const scoredStrategies = strategies.map(strategy => {
      let score = 0;
      
      // Task type compatibility
      if (strategy.applicability.taskTypes.includes(task.type) || strategy.applicability.taskTypes.includes("all")) {
        score += 0.3;
      }
      
      // Team size compatibility
      const teamSize = task.requirements.collaboration.teamSize || 1;
      if (strategy.applicability.teamSizes.includes(teamSize) || strategy.applicability.teamSizes.includes(10)) {
        score += 0.2;
      }
      
      // Complexity compatibility
      if (strategy.applicability.complexities.includes(task.complexity) || strategy.applicability.complexities.includes("all")) {
        score += 0.2;
      }
      
      // Performance weighting
      score *= (strategy.criteria.efficiency * 0.3 + 
                 strategy.criteria.quality * 0.3 + 
                 strategy.criteria.collaboration * 0.2 + 
                 strategy.criteria.learning * 0.2);
      
      // Adapt for specific task requirements
      if (analysis.timeCriticality > 0.8) {
        score *= strategy.criteria.efficiency;
      } else if (analysis.difficultyScore > 0.7) {
        score *= strategy.criteria.quality;
      }
      
      return { strategy, score };
    });

    // Select highest scoring strategy
    const best = scoredStrategies.reduce((prev, curr) => 
      curr.score > prev.score ? curr : prev
    );

    this.logger.debug(`Selected strategy ${best.strategy.name} with score ${best.score}`);
    return best.strategy;
  }

  private findSuitableAgents(task: IntelligentTask, analysis: any): AgentProfile[] {
    const agents = Array.from(this.agents.values());
    
    const suitableAgents = agents.filter(agent => {
      // Check capability match
      const capabilityMatch = this.evaluateCapabilityMatch(agent, task.requirements.capabilities);
      if (capabilityMatch < task.requirements.proficiency) return false;

      // Check resource availability
      const resourceMatch = this.evaluateResourceMatch(agent, task.requirements.resources);
      if (resourceMatch < 0.7) return false;

      // Check availability
      const availabilityMatch = this.evaluateAvailability(agent, task);
      if (availabilityMatch < 0.5) return false;

      // Check domain expertise
      const domainMatch = this.evaluateDomainMatch(agent, task.domain);
      if (domainMatch < 0.6) return false;

      return true;
    });

    // Sort by suitability score
    return suitableAgents.sort((a, b) => {
      const scoreA = this.calculateAgentSuitabilityScore(a, task, analysis);
      const scoreB = this.calculateAgentSuitabilityScore(b, task, analysis);
      return scoreB - scoreA;
    });
  }

  private evaluateCapabilityMatch(agent: AgentProfile, requiredCapabilities: string[]): number {
    const agentCapabilities = agent.capabilities.map(cap => cap.name);
    const matchCount = requiredCapabilities.filter(cap => 
      agentCapabilities.some(agentCap => agentCap.toLowerCase().includes(cap.toLowerCase()))
    ).length;

    return matchCount / requiredCapabilities.length;
  }

  private evaluateResourceMatch(agent: AgentProfile, requiredResources: any): number {
    let matchScore = 1;

    for (const [resource, amount] of Object.entries(requiredResources) as [string, number][]) {
      const agentResource = this.getAgentResource(agent, resource);
      if (agentResource < amount) {
        matchScore *= (agentResource / amount);
      }
    }

    return Math.min(matchScore, 1);
  }

  private getAgentResource(agent: AgentProfile, resource: string): number {
    // Map resource to agent capability
    const totalResources = agent.capabilities.reduce((sum, cap) => ({
      cpu: sum.cpu + cap.resources.cpu,
      memory: sum.memory + cap.resources.memory,
      bandwidth: sum.bandwidth + cap.resources.bandwidth,
    }), { cpu: 0, memory: 0, bandwidth: 0 });

    switch (resource) {
      case 'cpu': return totalResources.cpu * (1 - agent.capabilities[0].availability.currentLoad);
      case 'memory': return totalResources.memory * (1 - agent.capabilities[0].availability.currentLoad);
      case 'bandwidth': return totalResources.bandwidth * (1 - agent.capabilities[0].availability.currentLoad);
      default: return 0;
    }
  }

  private evaluateAvailability(agent: AgentProfile, task: IntelligentTask): number {
    const availability = 1 - agent.capabilities[0].availability.currentLoad;
    
    // Factor in deadline pressure
    if (task.constraints.deadline) {
      const timeToDeadline = task.constraints.deadline.getTime() - Date.now();
      const timeNeeded = this.estimateTaskDuration(task);
      if (timeToDeadline < timeNeeded * 2) {
        return Math.max(availability * 1.5, 1); // Prioritize time-critical tasks
      }
    }

    return availability;
  }

  private evaluateDomainMatch(agent: AgentProfile, domain: string): number {
    const domainExpertise = agent.knowledge.domains.find(d => 
      d.name.toLowerCase() === domain.toLowerCase()
    );
    
    return domainExpertise ? domainExpertise.proficiency : 0;
  }

  private calculateAgentSuitabilityScore(agent: AgentProfile, task: IntelligentTask, analysis: any): number {
    const capabilityScore = this.evaluateCapabilityMatch(agent, task.requirements.capabilities);
    const resourceScore = this.evaluateResourceMatch(agent, task.requirements.resources);
    const availabilityScore = this.evaluateAvailability(agent, task);
    const domainScore = this.evaluateDomainMatch(agent, task.domain);
    
    // Weight components
    const weights = {
      capability: 0.3,
      resource: 0.2,
      availability: 0.2,
      domain: 0.15,
      performance: 0.15,
    };

    const avgPerformance = (agent.capabilities[0].performance.successRate + 
                           agent.capabilities[0].performance.efficiency) / 2;

    return (
      capabilityScore * weights.capability +
      resourceScore * weights.resource +
      availabilityScore * weights.availability +
      domainScore * weights.domain +
      avgPerformance * weights.performance
    );
  }

  private async formCollaborativeTeam(task: IntelligentTask, agents: AgentProfile[], strategy: CoordinationStrategy): Promise<void> {
    const teamSize = Math.min(task.requirements.collaboration.teamSize, agents.length);
    const selectedAgents = agents.slice(0, teamSize);
    
    // Create collaboration
    const collaborationId = uuidv4();
    const collaboration: AgentCollaboration = {
      id: collaborationId,
      type: strategy.type === 'centralized' ? 'hierarchical' : 
             strategy.type === 'decentralized' ? 'peer' : 'team',
      participants: selectedAgents.map(a => a.id),
      context: {
        taskId: task.id,
        objective: task.description,
        rules: this.generateCollaborationRules(strategy),
        tools: this.determineRequiredTools(task),
      },
      communication: {
        style: strategy.id === 'decentralized_swarm' ? 'synchronous' : 'mixed',
        frequency: task.complexity === 'expert' ? 10 : 5,
        protocol: 'message_queue',
      },
      dynamics: {
        leadership: this.selectTeamLeader(selectedAgents, strategy),
        decisionMaking: strategy.parameters.decisionMaking || 'collaborative',
        conflictResolution: 'mediated',
      },
      outcomes: {
        taskCompleted: false,
        quality: 0,
        efficiency: 0,
        collaborationScore: 0,
        learningGained: 0,
      },
      metrics: {
        duration: 0,
        messages: 0,
        conflicts: 0,
        resolutions: 0,
        satisfaction: 0,
      },
      createdAt: new Date(),
    };

    this.collaborations.set(collaborationId, collaboration);
    this.activeCollaborations.set(collaborationId, collaboration);

    // Assign roles to team members
    await this.assignCollaborativeRoles(task, selectedAgents, collaboration);

    // Start collaboration
    await this.startCollaboration(collaboration, task);

    this.logger.info(`Formed collaborative team for task ${task.id} with ${teamSize} agents`);
    this.emit("collaboration-formed", { collaborationId, taskId: task.id, teamSize });
  }

  private async assignTaskToAgent(task: IntelligentTask, agent: AgentProfile, role: TaskAssignment['role']): Promise<void> {
    const assignment: TaskAssignment = {
      id: uuidv4(),
      taskId: task.id,
      agentId: agent.id,
      role,
      responsibilities: this.generateResponsibilities(task, role),
      allocation: {
        percentage: role === 'primary' ? 1.0 : 0.5,
        estimatedTime: this.estimateTaskDuration(task),
      },
      performance: {
        quality: 0,
        efficiency: 0,
        collaboration: 0,
        accuracy: 0,
      },
      status: 'assigned',
      assignedAt: new Date(),
    };

    task.assignments.push(assignment);
    task.status = 'in_progress';
    task.startedAt = new Date();
    task.updatedAt = new Date();

    // Update agent availability
    agent.capabilities[0].availability.currentLoad += allocation.percentage;

    this.logger.info(`Task ${task.id} assigned to agent ${agent.name} (${role})`);
    this.emit("task-assigned-to-agent", { taskId: task.id, agentId: agent.id, role });
  }

  // Intelligence Layer Processing
  private async startIntelligenceProcessing(): Promise<void> {
    setInterval(async () => {
      await this.processLearning();
      await this.updatePerformancePredictions();
      await this.optimizeCoordinationStrategies();
    }, 60000); // Process every minute
  }

  private async startLearningProcess(): Promise<void> {
    setInterval(async () => {
      await this.collectLearningData();
      await this.updateAgentModels();
      await this.identifyEmergentPatterns();
    }, 300000); // Process every 5 minutes
  }

  private async processLearning(): Promise<void> {
    try {
      // Analyze recent performance data
      const recentData = this.learningData.slice(-100);
      
      if (recentData.length > 10) {
        // Update intelligence layer models
        await this.updateIntelligenceModels(recentData);
        
        // Generate insights
        const insights = this.generatePerformanceInsights(recentData);
        
        // Apply optimizations
        if (insights.length > 0) {
          await this.applyLearningInsights(insights);
        }
      }
    } catch (error) {
      this.logger.error("Learning processing failed:", error);
    }
  }

  private async collectLearningData(): Promise<void> {
    // Collect data from completed tasks and collaborations
    const completedTasks = Array.from(this.tasks.values()).filter(t => t.status === 'completed');
    const completedCollaborations = Array.from(this.collaborations.values()).filter(c => c.completedAt);

    for (const task of completedTasks) {
      for (const assignment of task.assignments) {
        const agent = this.agents.get(assignment.agentId);
        if (agent) {
          this.learningData.push({
            timestamp: assignment.completedAt || new Date(),
            context: {
              taskId: task.id,
              agentId: agent.id,
              taskType: task.type,
              complexity: task.complexity,
              role: assignment.role,
            },
            action: 'task_completion',
            outcome: {
              duration: assignment.allocation.actualTime || assignment.allocation.estimatedTime,
              quality: assignment.performance.quality,
              efficiency: assignment.performance.efficiency,
            },
            feedback: this.calculateTaskFeedback(assignment),
          });
        }
      }
    }

    // Limit learning data size
    if (this.learningData.length > 10000) {
      this.learningData = this.learningData.slice(-5000);
    }
  }

  private async updateIntelligenceModels(data: any[]): Promise<void> {
    // Update learning models based on collected data
    const accuracyGain = this.calculateModelAccuracyGain(data);
    this.intelligenceLayer.learning.accuracy = Math.min(0.99, 
      this.intelligenceLayer.learning.accuracy + accuracyGain * 0.01
    );
    
    const confidenceGain = this.calculateModelConfidenceGain(data);
    this.intelligenceLayer.learning.confidence = Math.min(0.95, 
      this.intelligenceLayer.learning.confidence + confidenceGain * 0.01
    );

    this.logger.debug(`Updated intelligence models: accuracy=${this.intelligenceLayer.learning.accuracy}, confidence=${this.intelligenceLayer.learning.confidence}`);
  }

  private generatePerformanceInsights(data: any[]): string[] {
    const insights: string[] = [];

    // Analyze performance trends
    const recentPerformance = data.slice(-20);
    const avgPerformance = recentPerformance.reduce((sum, d) => sum + d.feedback, 0) / recentPerformance.length;
    
    if (avgPerformance > 0.9) {
      insights.push("High performance observed - consider increasing task complexity");
    } else if (avgPerformance < 0.7) {
      insights.push("Performance degradation detected - review agent assignments");
    }

    // Identify successful patterns
    const successfulTasks = data.filter(d => d.feedback > 0.8);
    if (successfulTasks.length > 0) {
      const commonFeatures = this.identifyCommonFeatures(successfulTasks);
      if (commonFeatures.length > 0) {
        insights.push(`Successful task patterns identified: ${commonFeatures.join(', ')}`);
      }
    }

    return insights;
  }

  private async applyLearningInsights(insights: string[]): Promise<void> {
    for (const insight of insights) {
      if (insight.includes("increasing task complexity")) {
        // Adjust task difficulty thresholds
        this.adjustTaskComplexityThresholds(0.1);
      } else if (insight.includes("review agent assignments")) {
        // Recalibrate agent suitability scoring
        this.recalibrateAgentSuitability();
      } else if (insight.includes("Successful task patterns")) {
        // Update coordination strategy preferences
        this.updateCoordinationPreferences();
      }
    }

    this.logger.info(`Applied ${insights.length} learning insights`);
    this.emit("learning-insights-applied", { insights });
  }

  // Public API Methods
  async getAgent(agentId: string): Promise<AgentProfile | null> {
    return this.agents.get(agentId) || null;
  }

  async getTask(taskId: string): Promise<IntelligentTask | null> {
    return this.tasks.get(taskId) || null;
  }

  async getCollaboration(collaborationId: string): Promise<AgentCollaboration | null> {
    return this.collaborations.get(collaborationId) || null;
  }

  async getCollectiveIntelligence(intelligenceId: string): Promise<CollectiveIntelligence | null> {
    return this.collectiveIntelligences.get(intelligenceId) || null;
  }

  async getSystemMetrics(): Promise<any> {
    return {
      agents: {
        total: this.agents.size,
        active: Array.from(this.agents.values()).filter(a => 
          a.capabilities[0].availability.currentLoad < 0.8
        ).length,
        averagePerformance: this.calculateAverageAgentPerformance(),
      },
      tasks: {
        total: this.tasks.size,
        pending: this.taskQueue.length,
        active: Array.from(this.tasks.values()).filter(t => t.status === 'in_progress').length,
        completed: Array.from(this.tasks.values()).filter(t => t.status === 'completed').length,
        successRate: this.calculateTaskSuccessRate(),
      },
      collaborations: {
        active: this.activeCollaborations.size,
        total: this.collaborations.size,
        averageSize: this.calculateAverageCollaborationSize(),
        effectiveness: this.calculateCollaborationEffectiveness(),
      },
      intelligence: {
        learningAccuracy: this.intelligenceLayer.learning.accuracy,
        modelConfidence: this.intelligenceLayer.learning.confidence,
        adaptationRate: this.calculateAdaptationRate(),
      },
    };
  }

  async createCollectiveIntelligence(config: {
    type: CollectiveIntelligence['type'];
    agents: string[];
    focus: {
      domain: string;
      objective: string;
      timeframe: { start: Date; end: Date };
    };
  }): Promise<string> {
    const intelligenceId = uuidv4();
    const collective: CollectiveIntelligence = {
      id: intelligenceId,
      ...config,
      capabilities: this.estimateCollectiveCapabilities(config.agents),
      knowledge: {
        shared: {},
        distributed: new Map(),
        emergent: {},
      },
      behavior: {
        patterns: [],
        adaptations: [],
      },
      metrics: {
        collectivePerformance: 0,
        synergy: 0,
        learningRate: 0,
        adaptationSpeed: 0,
      },
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    this.collectiveIntelligences.set(intelligenceId, collective);

    // Initialize collective learning
    await this.initializeCollectiveLearning(collective);

    this.logger.info(`Collective intelligence created: ${intelligenceId} (${config.type})`);
    this.emit("collective-intelligence-created", { intelligenceId, type: config.type });

    return intelligenceId;
  }

  // Utility Methods
  private deduceRequiredCapabilities(task: IntelligentTask): string[] {
    const capabilityMap: Record<string, string[]> = {
      analysis: ['reasoning', 'analysis', 'memory'],
      reasoning: ['reasoning', 'logic', 'inference'],
      planning: ['planning', 'reasoning', 'memory'],
      execution: ['execution', 'coordination', 'communication'],
      monitoring: ['monitoring', 'analysis', 'reasoning'],
      learning: ['learning', 'memory', 'adaptation'],
      coordination: ['coordination', 'communication', 'planning'],
    };

    return capabilityMap[task.type] || ['reasoning', 'execution'];
  }

  private calculateDifficultyScore(task: IntelligentTask): number {
    const complexityScore = {
      trivial: 0.1,
      simple: 0.3,
      moderate: 0.6,
      complex: 0.8,
      expert: 1.0,
    };

    let score = complexityScore[task.complexity];

    // Factor in domain complexity
    const domainComplexity = this.getDomainComplexity(task.domain);
    score = score * (0.7 + 0.3 * domainComplexity);

    return Math.min(score, 1);
  }

  private estimateTaskDuration(task: IntelligentTask): number {
    const baseDurations = {
      trivial: 30000,      // 30 seconds
      simple: 120000,      // 2 minutes
      moderate: 600000,    // 10 minutes
      complex: 1800000,    // 30 minutes
      expert: 3600000,     // 1 hour
    };

    let duration = baseDurations[task.complexity];

    // Adjust for collaboration overhead
    if (task.requirements.collaboration.required) {
      duration *= (1 + task.requirements.collaboration.teamSize * 0.2);
    }

    // Adjust for domain familiarity
    const domainMultiplier = this.getDomainDifficultyMultiplier(task.domain);
    duration *= domainMultiplier;

    return Math.round(duration);
  }

  private getDomainComplexity(domain: string): number {
    const complexities: Record<string, number> = {
      'general': 0.3,
      'technical': 0.6,
      'creative': 0.7,
      'research': 0.8,
      'strategic': 0.9,
    };

    return complexities[domain.toLowerCase()] || 0.5;
  }

  private getDomainDifficultyMultiplier(domain: string): number {
    const multipliers: Record<string, number> = {
      'general': 1.0,
      'technical': 1.2,
      'creative': 1.3,
      'research': 1.5,
      'strategic': 1.4,
    };

    return multipliers[domain.toLowerCase()] || 1.1;
  }

  private async startCollaboration(collaboration: AgentCollaboration, task: IntelligentTask): Promise<void> {
    // Initialize collaboration communication
    collaboration.metrics.duration = 0;
    collaboration.metrics.messages = 0;

    // Create collective intelligence for this collaboration
    const collectiveId = await this.createCollectiveIntelligence({
      type: collaboration.type === 'hierarchical' ? 'coordinated' : 'distributed',
      agents: collaboration.participants,
      focus: {
        domain: task.domain,
        objective: task.description,
        timeframe: {
          start: new Date(),
          end: task.constraints.deadline || new Date(Date.now() + 3600000),
        },
      },
    });

    this.emit("collaboration-started", { collaborationId: collaboration.id, collectiveId });
  }

  // Additional utility methods would be implemented here...
  private async updatePerformancePredictions(): Promise<void> { /* Implementation */ }
  private async optimizeCoordinationStrategies(): Promise<void> { /* Implementation */ }
  private async updateAgentModels(): Promise<void> { /* Implementation */ }
  private async identifyEmergentPatterns(): Promise<void> { /* Implementation */ }
  private calculateModelAccuracyGain(data: any[]): number { /* Implementation */ }
  private calculateModelConfidenceGain(data: any[]): number { /* Implementation */ }
  private identifyCommonFeatures(tasks: any[]): string[] { /* Implementation */ }
  private adjustTaskComplexityThresholds(factor: number): void { /* Implementation */ }
  private recalibrateAgentSuitability(): void { /* Implementation */ }
  private updateCoordinationPreferences(): void { /* Implementation */ }
  private calculateAverageAgentPerformance(): number { /* Implementation */ }
  private calculateTaskSuccessRate(): number { /* Implementation */ }
  private calculateAverageCollaborationSize(): number { /* Implementation */ }
  private calculateCollaborationEffectiveness(): number { /* Implementation */ }
  private calculateAdaptationRate(): number { /* Implementation */ }
  private async initializeCollectiveLearning(collective: CollectiveIntelligence): Promise<void> { /* Implementation */ }
  private async reassignAgentTasks(agentId: string): Promise<void> { /* Implementation */ }
  private estimateCollaborationComplexity(task: IntelligentTask): number { /* Implementation */ }
  private assessTimeCriticality(task: IntelligentTask): number { /* Implementation */ }
  private selectBestAgent(agents: AgentProfile[], task: IntelligentTask): AgentProfile | null { /* Implementation */ }
  private generateResponsibilities(task: IntelligentTask, role: TaskAssignment['role']): string[] { /* Implementation */ }
  private generateCollaborationRules(strategy: CoordinationStrategy): string[] { /* Implementation */ }
  private determineRequiredTools(task: IntelligentTask): string[] { /* Implementation */ }
  private selectTeamLeader(agents: AgentProfile[], strategy: CoordinationStrategy): string { /* Implementation */ }
  private async assignCollaborativeRoles(task: IntelligentTask, agents: AgentProfile[], collaboration: AgentCollaboration): Promise<void> { /* Implementation */ }
  private calculateTaskFeedback(assignment: TaskAssignment): number { /* Implementation */ }
  private estimateCollectiveCapabilities(agentIds: string[]): CollectiveIntelligence['capabilities'] { /* Implementation */ }

  // Public cleanup method
  async shutdown(): Promise<void> {
    this.logger.info("Shutting down Intelligent Agent Coordinator");
    
    // Complete all active tasks and collaborations
    const activeTasks = Array.from(this.tasks.values()).filter(t => t.status === 'in_progress');
    for (const task of activeTasks) {
      task.status = 'cancelled';
      task.updatedAt = new Date();
    }

    // Clear all data
    this.agents.clear();
    this.tasks.clear();
    this.collaborations.clear();
    this.collectiveIntelligences.clear();
    this.taskQueue.length = 0;
    this.activeCollaborations.clear();
    this.learningData.length = 0;
    this.performanceMetrics.clear();

    this.emit("shutdown-complete");
  }
}