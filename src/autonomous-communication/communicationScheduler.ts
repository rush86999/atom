import { EventEmitter } from 'events';
import { ScheduledCommunication, AutonomousCommunications, CommunicationType, CommunicationPriority } from './types';

export class CommunicationScheduler extends EventEmitter {
  private queuedCommunications: Map<string, ScheduledCommunication> = new Map();
  private scheduledTimeouts: Map<string, NodeJS.Timeout> = new Map();
  private executionHistory: ScheduledCommunication[] = [];
  private retryPolicy = {
    maxRetries: 3,
    baseDelay: 60000, // 1 minute
    backoffMultiplier: 2
  };

  constructor() {
    super();
  }

  public async scheduleFromAnalysis(opportunities: AutonomousCommunications[]): Promise<void> {
    for (const opportunity of opportunities) {
      await this.scheduleCommunication(opportunity);
    }
  }

  public async scheduleCommunication(
    communication: AutonomousCommunications,
    options?: {
      replaceExisting?: boolean;
      skipCooldown?: boolean;
    }
  ): Promise<string> {
    const communicationId = this.generateId();

    // Check for conflicts
    if (!options?.replaceExisting) {
      const conflict = this.checkForConflict(communication);
      if (conflict) {
        throw new Error(`Communication conflict with existing scheduled item: ${conflict}`);
      }
    }

    // Apply scheduling rules
    const processedTime = await this.applySchedulingRules(communication.scheduledTime, communication);

    const scheduled: ScheduledCommunication = {
      ...communication,
      id: communicationId,
      createdAt: new Date(),
      scheduledFor: processedTime,
      retryCount: 0,
      dependencies: []
    };

    // Store the scheduled communication
    this.queuedCommunications.set(communicationId, scheduled);

    // Schedule the execution
    await this.scheduleExecution(scheduled);

    // Emit event
    this.emit('scheduled', scheduled);

    return communicationId;
  }

  private async scheduleExecution(communication: ScheduledCommunication): Promise<void> {
    const delay = Math.max(0, communication.scheduledFor.getTime() - Date.now());

    const timeout = setTimeout(async () => {
      await this.executeCommunication(communication);
    }, delay);

    this.scheduledTimeouts.set(communication.id, timeout);
  }

  private async executeCommunication(communication: ScheduledCommunication): Promise<void> {
    try {
      this.queuedCommunications.delete(communication.id);
      this.scheduledTimeouts.delete(communication.id);

      communication.executedAt = new Date();
      this.emit('communication-due', communication);

    } catch (error) {
      console.error('Failed to execute communication:', error);

      if (communication.retryCount < this.retryPolicy.maxRetries) {
        await this.scheduleRetry(communication);
      } else {
        this.executionHistory.push(communication);
        super.emit('execution-failed', { communication, error });
      }
    }
  }

  private async scheduleRetry(communication: ScheduledCommunication): Promise<void> {
    communication.retryCount++;

    const delay = this.retryPolicy.baseDelay * Math.pow(this.retryPolicy.backoffMultiplier, communication.retryCount - 1);
    const retryTime = new Date(Date.now() + delay);

    communication.scheduledFor = retryTime;

    const retryTimeout = setTimeout(async () => {
      await this.executeCommunication(communication);
    }, delay);

    this.scheduledTimeouts.set(communication.id, retryTimeout);
  }

  private checkForConflict(communication: AutonomousCommunications): string | null {
    // Check for same recipient + channel + similar time conflicts
    for (const [, scheduled] of this.queuedCommunications) {
      if (
        scheduled.recipient === communication.recipient &&
        scheduled.channel === communication.channel &&
        Math.abs(scheduled.scheduledFor.getTime() - communication.scheduledTime.getTime()) < 3600000 // 1 hour
      ) {
        return scheduled.id;
      }
    }

    return null;
  }

  private async applySchedulingRules(
    originalTime: Date,
    communication: AutonomousCommunications
  ): Promise<Date> {
    let adjustedTime = new Date(originalTime);

    // Apply priority-based adjustments
    adjustedTime = await this.applyPriorityRules(adjustedTime, communication);

    // Apply contact availability rules
    adjustedTime = await this.applyContactAvailabilityRules(adjustedTime, communication);

    // Apply channel rules
    adjustedTime = await this.applyChannelRules(adjustedTime, communication);

    // Apply user preferences rules
    adjustedTime = await this.applyUserPreferencesRules(adjustedTime, communication);

    // Apply business hour rules
    adjustedTime = this.applyBusinessHoursRules(adjustedTime);

    return adjustedTime;
  }

  private async applyPriorityRules(
    time: Date,
    communication: AutonomousCommunications
  ): Promise<Date> {
    const priorityWeightMap = {
      'urgent': 0.1,
      'high': 0.3,
      'medium': 0.7,
      'low': 1.0
    };

    const weight = priorityWeightMap[communication.priority] || 0.5;
    const delay = Math.max(0, time.getTime() - Date.now());
    const adjustedDelay = delay * weight;
    const adjustedTime = new Date(Date.now() + adjustedDelay);
    return adjustedTime;
  }

  private async applyContactAvailabilityRules(
    time: Date,
    communication: AutonomousCommunications
  ): Promise<Date> {
    // For now, place during business hours
    const hour = time.getHours();
    if (hour < 9) {
      time.setHours(9, 0, 0, 0);
    } else if (hour > 17) {
      time.setHours(9, 0, 0, 0);
      time.setDate(time.getDate() + 1);
    }
    return time;
  }

  private async applyChannelRules(
    time: Date,
    communication: AutonomousCommunications
  ): Promise<Date> {
    // Different channels have different optimal times
    const channelTimeMap: Record<string, Date> = {
      'email': time,
      'slack': time,
      'teams': new Date(time.getTime() + 2 * 60 * 60 * 1000), // 2 hours later for teams
      'sms': new Date(time.getTime() + (time.getHours() < 10 ? 3 : 0) * 60 * 60 * 1000),
      'phone': new Date(time.getTime() + (time.getHours() < 11 ? 4 : 0) * 60 * 60 * 1000)
    };

    return channelTimeMap[communication.channel] || time;
  }

  private async applyUserPreferencesRules(
    time: Date,
    communication: AutonomousCommunications
  ): Promise<Date> {
    // Space out high-priority communications
    if (communication.priority === 'high') {
      const randomOffset = Math.random() * 30 * 60 * 1000; // 0-30 minutes
      return new Date(time.getTime() + randomOffset);
    }
    return time;
  }

  private applyBusinessHoursRules(time: Date): Date {
    const day = time.getDay();
    // Skip weekends
    if (day === 0 || day === 6) {
      const nextMonday = new Date(time);
      nextMonday.setDate(time.getDate() + ((7 - day) % 7) + 1);
      nextMonday.setHours(9, 0, 0, 0);
      return nextMonday;
    }
    return time;
  }

  private generateId(): string {
    return `comm-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  public async cancelScheduledCommunication(id: string): Promise<void> {
    const communication = this.queuedCommunications.get(id);
    if (!communication) {
      throw new Error(`Communication ${id} not found`);
    }

    const timeout = this.scheduledTimeouts.get(id);
    if (timeout) {
      clearTimeout(timeout);
      this.scheduledTimeouts.delete(id);
    }

    this.queuedCommunications.delete(id);
    this.emit('canceled', communication);
  }

  public getScheduledCommunications(): ScheduledCommunication[] {
    return Array.from(this.queuedCommunications.values());
  }

  public getExecutionHistory(): ScheduledCommunication[] {
    return [...this.executionHistory];
  }

  public async updateScheduledTime(id: string, newTime: Date): Promise<void> {
    const communication = this.queuedCommunications.get(id);
    if (!communication) {
      throw new Error(`Communication ${id} not found`);
    }

    // Apply scheduling rules to the new time
    const processedTime = await this.applySchedulingRules(newTime, communication);

    // Clear existing timeout
    const existingTimeout = this.scheduledTimeouts.get(id);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
      this.scheduledTimeouts.delete(id);
    }

    // Update the scheduled time
    communication.scheduledFor = processedTime;

    // Reschedule the execution
    await this.scheduleExecution(communication);

    // Emit update event
    this.emit('updated', communication);
  }
}
