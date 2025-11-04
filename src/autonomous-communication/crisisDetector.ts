import { EventEmitter } from 'events';
import { CommunicationContext, CommunicationRecord } from './types';

export interface CrisisIndicator {
  severity: 'low' | 'medium' | 'high' | 'critical';
  type: 'urgent-request' | 'negative-feedback' | 'service-issue' | 'relationship-damage' | 'time-sensitive';
  description: string;
  recommendedAction: string;
  urgency: number; // 0-100
}

export class CrisisDetector extends EventEmitter {
  private crisisKeywords = {
    critical: ['urgent', 'emergency', 'asap', 'immediately', 'critical', 'crisis'],
    high: ['problem', 'issue', 'error', 'failed', 'broken', 'down', 'outage'],
    medium: ['concern', 'worry', 'disappointed', 'unhappy', 'frustrated'],
    low: ['question', 'help', 'support', 'assistance']
  };

  public async detectCrisis(context: CommunicationContext): Promise<CrisisIndicator | null> {
    const recentComms = context.recentCommunications.slice(-10);
    
    for (const comm of recentComms) {
      const indicator = await this.analyzeCommunication(comm);
      if (indicator && indicator.severity !== 'low') {
        this.emit('crisis-detected', context);
        return indicator;
      }
    }
    
    return null;
  }

  private async analyzeCommunication(comm: CommunicationRecord): Promise<CrisisIndicator | null> {
    const message = comm.message.toLowerCase();
    let severity: CrisisIndicator['severity'] = 'low';
    let type: CrisisIndicator['type'] = 'urgent-request';
    
    // Check for critical keywords
    if (this.crisisKeywords.critical.some(kw => message.includes(kw))) {
      severity = 'critical';
      type = 'urgent-request';
    } else if (this.crisisKeywords.high.some(kw => message.includes(kw))) {
      severity = 'high';
      type = 'service-issue';
    } else if (this.crisisKeywords.medium.some(kw => message.includes(kw))) {
      severity = 'medium';
      type = 'negative-feedback';
    } else {
      return null;
    }
    
    const urgency = severity === 'critical' ? 100 : severity === 'high' ? 75 : severity === 'medium' ? 50 : 25;
    
    return {
      severity,
      type,
      description: `Detected ${severity} level issue in communication`,
      recommendedAction: this.getRecommendedAction(severity, type),
      urgency
    };
  }

  private getRecommendedAction(severity: CrisisIndicator['severity'], type: CrisisIndicator['type']): string {
    if (severity === 'critical') {
      return 'Immediate response required - escalate to human if needed';
    } else if (severity === 'high') {
      return 'Respond within 1 hour with acknowledgment and solution timeline';
    } else {
      return 'Respond within 24 hours with empathetic acknowledgment';
    }
  }
}
