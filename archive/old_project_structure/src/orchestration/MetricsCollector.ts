import { EventEmitter } from "events";
import { Logger } from "../utils/logger";

export interface TaskMetric {
  taskId: string;
  agentId: string;
  startTime: Date;
  completionTime?: Date;
  duration?: number;
  success: boolean;
  error?: string;
  skillUsed: string;
  complexity: number;
}

export interface SystemMetrics {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  successRate: number;
  averageDuration: number;
  peakAgents: number;
  queueLength: number;
  currentLoad: number;
  bottleneckIndicators: string[];
}

export class MetricsCollector extends EventEmitter {
  private logger: Logger;
  private taskMetrics: Map<string, TaskMetric> = new Map();
  private systemMetrics: SystemMetrics = {
    totalTasks: 0,
    completedTasks: 0,
    failedTasks: 0,
    successRate: 0,
    averageDuration: 0,
    peakAgents: 0,
    queueLength: 0,
    currentLoad: 0,
    bottleneckIndicators: [],
  };
  private lastUpdate: Date = new Date();

  constructor() {
    super();
    this.logger = new Logger("MetricsCollector");
  }

  recordTaskStart(
    taskId: string,
    agentId: string,
    skillUsed: string,
    complexity: number = 1,
  ): void {
    const metric: TaskMetric = {
      taskId,
      agentId,
      startTime: new Date(),
      skillUsed,
      complexity,
      success: true,
    };

    this.taskMetrics.set(taskId, metric);
    this.systemMetrics.totalTasks++;
    this.systemMetrics.queueLength = Math.max(
      0,
      this.systemMetrics.queueLength - 1,
    );
    this.logger.debug(`Task started: ${taskId} assigned to ${agentId}`);

    this.emit("task-started", {
      taskId,
      agentId,
      skillUsed,
      timestamp: metric.startTime,
    });
    this.updateSystemMetrics();
  }

  recordTaskComplete(taskId: string, duration?: number): void {
    const metric = this.taskMetrics.get(taskId);
    if (metric) {
      metric.completionTime = new Date();
      metric.duration =
        duration ||
        metric.startTime.getTime() - metric.completionTime.getTime();

      this.systemMetrics.completedTasks++;
      this.calculateSuccessRate();
      this.calculateAverageDuration();

      this.logger.debug(`Task completed: ${taskId} in ${metric.duration}ms`);
      this.emit("task-completed", {
        taskId,
        duration: metric.duration,
        timestamp: metric.completionTime,
      });
    }
    this.updateSystemMetrics();
  }

  recordTaskFailure(taskId: string, error?: string): void {
    const metric = this.taskMetrics.get(taskId);
    if (metric) {
      metric.success = false;
      metric.error = error;
      metric.completionTime = new Date();

      this.systemMetrics.failedTasks++;
      this.calculateSuccessRate();

      this.logger.warn(`Task failed: ${taskId}`, { error });
      this.emit("task-failed", {
        taskId,
        error,
        timestamp: metric.completionTime,
      });
    }
    this.updateSystemMetrics();
  }

  recordQueueLength(length: number): void {
    this.systemMetrics.queueLength = length;
    this.emit("queue-updated", { length, timestamp: new Date() });
  }

  recordAgentPeak(peak: number): void {
    if (peak > this.systemMetrics.peakAgents) {
      this.systemMetrics.peakAgents = peak;
    }
  }

  calculateSuccessRate(): void {
    const total = this.systemMetrics.totalTasks;
    const completed = this.systemMetrics.completedTasks;
    const failed = this.systemMetrics.failedTasks;

    this.systemMetrics.successRate =
      total > 0 ? (completed - failed) / total : 0;
  }

  calculateAverageDuration(): void {
    const completedTasks = Array.from(this.taskMetrics.values())
      .filter((m) => m.duration !== undefined && m.success)
      .map((m) => m.duration!);

    this.systemMetrics.averageDuration =
      completedTasks.length > 0
        ? completedTasks.reduce((sum, duration) => sum + duration, 0) /
          completedTasks.length
        : 0;
  }

  detectBottlenecks(): string[] {
    const indicators: string[] = [];
    const taskMetrics = Array.from(this.taskMetrics.values());

    // High failure rate
    if (this.systemMetrics.successRate < 0.7) {
      indicators.push(
        `High failure rate: ${(this.systemMetrics.successRate * 100).toFixed(1)}%`,
      );
    }

    // Long queue
    if (this.systemMetrics.queueLength > 10) {
      indicators.push(
        `Queue overflow: ${this.systemMetrics.queueLength} pending tasks`,
      );
    }

    // Slow tasks
    if (this.systemMetrics.averageDuration > 30000) {
      indicators.push(
        `Slow performance: ${this.systemMetrics.averageDuration.toFixed(0)}ms average task duration`,
      );
    }

    // Agent overload
    const agentTasks = new Map<string, number>();
    for (const metric of taskMetrics) {
      if (metric.success && metric.duration) {
        agentTasks.set(
          metric.agentId,
          (agentTasks.get(metric.agentId) || 0) + 1,
        );
      }
    }

    for (const [agentId, taskCount] of agentTasks.entries()) {
      if (taskCount > 20) {
        indicators.push(
          `Agent overload: ${agentId} handling ${taskCount} tasks`,
        );
      }
    }

    this.systemMetrics.bottleneckIndicators = indicators;
    return indicators;
  }

  updateSystemMetrics(): void {
    this.lastUpdate = new Date();
    this.detectBottlenecks();
    this.calculateSuccessRate();
    this.calculateAverageDuration();

    this.emit("metrics-updated", {
      metrics: this.getCurrentMetrics(),
      timestamp: this.lastUpdate,
    });
  }

  getCurrentMetrics(): SystemMetrics {
    return {
      ...this.systemMetrics,
      currentLoad: this.calculateCurrentLoad(),
    };
  }

  calculateCurrentLoad(): number {
    const activeTasks = Array.from(this.taskMetrics.values()).filter(
      (m) => !m.completionTime,
    ).length;

    return activeTasks / Math.max(1, this.systemMetrics.peakAgents);
  }

  getTaskMetrics(taskId: string): TaskMetric | undefined {
    return this.taskMetrics.get(taskId);
  }

  getAllTaskMetrics(): TaskMetric[] {
    return Array.from(this.taskMetrics.values());
  }

  clearMetrics(): void {
    this.taskMetrics.clear();
    this.systemMetrics = {
      totalTasks: 0,
      completedTasks: 0,
      failedTasks: 0,
      successRate: 0,
      averageDuration: 0,
      peakAgents: 0,
      queueLength: 0,
      currentLoad: 0,
      bottleneckIndicators: [],
    };
    this.logger.info("Metrics cleared");
  }

  exportMetrics(): any {
    return {
      systemMetrics: this.getCurrentMetrics(),
      taskMetrics: this.getAllTaskMetrics(),
      lastUpdate: this.lastUpdate,
      healthStatus: this.getHealthStatus(),
    };
  }

  getHealthStatus(): "healthy" | "degraded" | "critical" {
    const metrics = this.getCurrentMetrics();

    if (metrics.successRate > 0.9 && metrics.averageDuration < 10000) {
      return "healthy";
    } else if (metrics.successRate > 0.7 && metrics.averageDuration < 30000) {
      return "degraded";
    } else {
      return "critical";
    }
  }

  startMonitoring(): void {
    this.logger.info("Starting metrics monitoring");
    // Could implement periodic health checks here
  }

  stopMonitoring(): void {
    this.logger.info("Stopping metrics monitoring");
  }
}
