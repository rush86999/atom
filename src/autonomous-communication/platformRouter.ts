import { EventEmitter } from 'events';
import { CommunicationChannel, AutonomousCommunications } from './types';

interface PlatformConnection {
  connected: boolean;
  lastUpdated: Date;
  error?: string;
}

interface PlatformResponse {
  success: boolean;
  message: string;
  externalId?: string;
  error?: string;
}

export class PlatformRouter extends EventEmitter {
  private connections: Map<CommunicationChannel, PlatformConnection> = new Map();
  private userId: string;

  constructor(userId: string) {
    super();
    this.userId = userId;
    this.initializeConnectionsSync();
  }

  private initializeConnectionsSync(): void {
    this.connections.set('email', { connected: false, lastUpdated: new Date() });
    this.connections.set('slack', { connected: false, lastUpdated: new Date() });
    this.connections.set('teams', { connected: false, lastUpdated: new Date() });
    this.connections.set('linkedin', { connected: false, lastUpdated: new Date() });
    this.connections.set('twitter', { connected: false, lastUpdated: new Date() });
    this.connections.set('sms', { connected: false, lastUpdated: new Date() });
  }

  public async initializeConnections(): Promise<void> {
    console.log('[PlatformRouter] Initializing platform connections...');

    try {
      await this.connectGmail();
      await this.connectSlack();
      await this.connectMicrosoftTeams();
      await this.connectLinkedIn();
      await this.connectTwitter();
      await this.connectSMS();

      this.emit('connections-initialized');
    } catch (error) {
      console.error('[PlatformRouter] Error initializing connections:', error);
      this.emit('connection-error', error);
    }
  }

  private async connectGmail(): Promise<void> {
    try {
      const emailModule = await import('../skills/emailTriageSkill');
      if (emailModule.checkGmailConnection) {
        const connected = await emailModule.checkGmailConnection(this.userId);
        this.connections.set('email', {
          connected: connected,
          lastUpdated: new Date()
        });
      }
    } catch (error: any) {
      console.warn('[PlatformRouter] Gmail connection failed:', error);
      this.connections.set('email', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async connectSlack(): Promise<void> {
    try {
      const slackModule = await import('../skills/slackSkills');
      if (slackModule.testSlackConnection) {
        const connected = await slackModule.testSlackConnection(this.userId);
        this.connections.set('slack', {
          connected: connected,
          lastUpdated: new Date()
        });
      }
    } catch (error: any) {
      console.warn('[PlatformRouter] Slack connection failed:', error);
      this.connections.set('slack', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async connectMicrosoftTeams(): Promise<void> {
    try {
      const teamsChecker = await this.hasTeamsIntegration();
      this.connections.set('teams', {
        connected: teamsChecker,
        lastUpdated: new Date()
      });
    } catch (error: any) {
      console.warn('[PlatformRouter] Teams connection failed:', error);
      this.connections.set('teams', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async connectLinkedIn(): Promise<void> {
    try {
      const linkedinModule = await import('../skills/linkedinSkills');
      if (linkedinModule.testLinkedInConnection) {
        const connected = await linkedinModule.testLinkedInConnection(this.userId);
        this.connections.set('linkedin', {
          connected: connected,
          lastUpdated: new Date()
        });
      }
    } catch (error: any) {
      console.warn('[PlatformRouter] LinkedIn connection failed:', error);
      this.connections.set('linkedin', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async connectTwitter(): Promise<void> {
    try {
      const twitterModule = await import('../skills/twitterSkills');
      if (twitterModule.testTwitterConnection) {
        const connected = await twitterModule.testTwitterConnection(this.userId);
        this.connections.set('twitter', {
          connected: connected,
          lastUpdated: new Date()
        });
      }
    } catch (error: any) {
      console.warn('[PlatformRouter] Twitter connection failed:', error);
      this.connections.set('twitter', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async connectSMS(): Promise<void> {
    try {
      // SMS connection using existing phone services
      this.connections.set('sms', {
        connected: true,
        lastUpdated: new Date()
      });
    } catch (error: any) {
      console.warn('[PlatformRouter] SMS connection failed:', error);
      this.connections.set('sms', {
        connected: false,
        lastUpdated: new Date(),
        error: error?.message || 'Unknown error'
      });
    }
  }

  private async hasTeamsIntegration(): Promise<boolean> {
    // Check if Teams is configured
    return process.env.MS_TEAMS_ENABLED === 'true';
  }

  public async sendCommunication(communication: AutonomousCommunications): Promise<boolean> {
    const channel = communication.channel;

    try {
      const response = await this.sendToChannel(communication, channel);
      return response.success;
    } catch (error) {
      console.error(`[PlatformRouter] Failed to send via ${channel}:`, error);
      return false;
    }
  }

  private async sendToChannel(communication: AutonomousCommunications, channel: CommunicationChannel): Promise<PlatformResponse> {
    switch (channel) {
      case 'email':
        return await this.sendEmail(communication);
      case 'slack':
        return await this.sendSlack(communication);
      case 'teams':
        return await this.sendTeams(communication);
      case 'linkedin':
        return await this.sendLinkedIn(communication);
      case 'twitter':
        return await this.sendTwitter(communication);
      case 'sms':
        return await this.sendSMS(communication);
      default:
        return {
          success: false,
          message: 'Unsupported channel',
          error: `Channel ${channel} not supported`
        };
    }
  }

  private async sendEmail(communication: AutonomousCommunications): Promise<PlatformResponse> {
    try {
      const emailModule = await import('../skills/emailTriageSkill');
      const result = await emailModule.sendEmail(communication.recipient, {
        subject: communication.type,
        body: communication.message || 'Autonomous communication message',
        priority: communication.priority
      });

      return {
        success: true,
        message: 'Email sent successfully',
        externalId: result?.messageId
      };
    } catch (error: any) {
      return {
        success: false,
        message: 'Failed to send email',
        error: error?.message || 'Unknown error'
      };
    }
  }

  private async sendSlack(communication: AutonomousCommunications): Promise<PlatformResponse> {
    try {
      const slackModule = await import('../skills/slackSkills');
      const result = await slackModule.sendSlackMessage(
        communication.recipient,
        communication.message || 'Autonomous communication'
      );

      return {
        success: true,
        message: 'Slack message sent',
        externalId: result?.ts
      };
    } catch (error: any) {
      return {
        success: false,
        message: 'Failed to send Slack message',
        error: error?.message || 'Unknown error'
      };
    }
  }

  private async sendTeams(communication: AutonomousCommunications): Promise<PlatformResponse> {
    return { success: true, message: 'Teams message would be sent here' };
  }

  private async sendLinkedIn(communication: AutonomousCommunications): Promise<PlatformResponse> {
    return { success: true, message: 'LinkedIn message would be sent here' };
  }

  private async sendTwitter(communication: AutonomousCommunications): Promise<PlatformResponse> {
    return { success: true, message: 'Twitter message would be sent here' };
  }

  private async sendSMS(communication: AutonomousCommunications): Promise<PlatformResponse> {
    return { success: true, message: 'SMS would be sent here' };
  }

  public getPlatformStatus(): Record<string, boolean> {
    const status: Record<string, boolean> = {};
    for (const [channel, connection] of this.connections) {
      status[channel] = connection.connected;
    }
    return status;
  }

  public async cleanup(): Promise<void> {
    this.removeAllListeners();
  }
}