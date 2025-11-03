/**
 * Outlook Skills - Email and Calendar Automation
 * Following GitLab pattern for consistency
 */

import { 
  invoke, 
  TauriInvokeOptions 
} from '@tauri-apps/api/tauri';
import { SkillExecutionContext } from '../types/skillTypes';
import { EventBus } from '../utils/EventBus';
import { Logger } from '../utils/Logger';

export interface OutlookEmailSkillParams {
  action: 'send' | 'get' | 'search' | 'triage';
  to?: string[];
  cc?: string[];
  bcc?: string[];
  subject?: string;
  body?: string;
  searchQuery?: string;
  limit?: number;
  unread?: boolean;
}

export interface OutlookCalendarSkillParams {
  action: 'create' | 'get' | 'update' | 'delete' | 'search';
  subject: string;
  startTime: string;
  endTime: string;
  body?: string;
  location?: string;
  attendees?: string[];
  eventId?: string;
  searchQuery?: string;
  limit?: number;
}

export interface OutlookUserInfo {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle?: string;
  officeLocation?: string;
}

export interface OutlookEmail {
  id: string;
  subject: string;
  from: { name: string; address: string };
  to: Array<{ name: string; address: string }>;
  cc?: Array<{ name: string; address: string }>;
  bcc?: Array<{ name: string; address: string }>;
  body: string;
  receivedDateTime: string;
  isRead: boolean;
  importance: 'low' | 'normal' | 'high';
  hasAttachments: boolean;
}

export interface OutlookCalendarEvent {
  id: string;
  subject: string;
  start: { dateTime: string; timeZone: string };
  end: { dateTime: string; timeZone: string };
  location?: { displayName: string };
  body?: { content: string; contentType: string };
  attendees?: Array<{ email: { name: string; address: string } }>;
  isAllDay?: boolean;
  showAs?: 'free' | 'tentative' | 'busy' | 'oof' | 'workingElsewhere';
}

export class OutlookEmailSkill {
  private logger = new Logger('OutlookEmailSkill');

  async execute(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Outlook Email Skill', { action: params.action, params });

    try {
      switch (params.action) {
        case 'send':
          return await this.sendEmail(params, context);
        case 'get':
          return await this.getEmails(params, context);
        case 'search':
          return await this.searchEmails(params, context);
        case 'triage':
          return await this.triageEmails(params, context);
        default:
          throw new Error(`Unsupported email action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Outlook Email Skill failed', error);
      throw error;
    }
  }

  private async sendEmail(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.to || !params.subject || !params.body) {
      throw new Error('To address, subject, and body are required for sending emails');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        to: params.to,
        subject: params.subject,
        body: params.body,
        cc: params.cc,
        bcc: params.bcc
      }
    };

    const result = await invoke<any>('send_outlook_email', options.args);
    
    if (result.success) {
      EventBus.emit('outlook:email:sent', {
        subject: params.subject,
        to: params.to,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Email sent successfully', {
        subject: params.subject,
        to: params.to
      });
    }

    return {
      success: result.success,
      message: result.message,
      emailId: result.emailId,
      timestamp: new Date().toISOString()
    };
  }

  private async getEmails(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        limit: params.limit || 10,
        unread: params.unread
      }
    };

    const emails = await invoke<OutlookEmail[]>('get_outlook_emails', options.args);
    
    EventBus.emit('outlook:emails:retrieved', {
      count: emails.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      emails: emails,
      count: emails.length,
      timestamp: new Date().toISOString()
    };
  }

  private async searchEmails(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.searchQuery) {
      throw new Error('Search query is required for email search');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.searchQuery,
        limit: params.limit || 10
      }
    };

    const emails = await invoke<OutlookEmail[]>('search_outlook_emails', options.args);
    
    EventBus.emit('outlook:emails:searched', {
      query: params.searchQuery,
      count: emails.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      emails: emails,
      count: emails.length,
      searchQuery: params.searchQuery,
      timestamp: new Date().toISOString()
    };
  }

  private async triageEmails(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    // Get unread emails first
    const unreadResult = await this.getEmails({ ...params, unread: true }, context);
    const emails = unreadResult.emails;

    // Basic triage logic based on content
    const triagedEmails = emails.map(email => {
      const priority = this.determineEmailPriority(email);
      const category = this.determineEmailCategory(email);
      
      return {
        ...email,
        priority,
        category,
        requiresAction: this.requiresAction(email)
      };
    });

    // Group by category
    const categorized = triagedEmails.reduce((acc, email) => {
      const category = email.category || 'other';
      if (!acc[category]) acc[category] = [];
      acc[category].push(email);
      return acc;
    }, {} as Record<string, any[]>);

    EventBus.emit('outlook:emails:triaged', {
      total: triagedEmails.length,
      categories: Object.keys(categorized),
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      emails: triagedEmails,
      categorized,
      summary: {
        total: triagedEmails.length,
        highPriority: triagedEmails.filter(e => e.priority === 'high').length,
        requiresAction: triagedEmails.filter(e => e.requiresAction).length
      },
      timestamp: new Date().toISOString()
    };
  }

  private determineEmailPriority(email: OutlookEmail): 'high' | 'medium' | 'low' {
    const subject = email.subject.toLowerCase();
    const body = email.body.toLowerCase();
    const sender = email.from.address.toLowerCase();

    // High priority keywords
    const highKeywords = ['urgent', 'asap', 'important', 'emergency', 'critical'];
    // Medium priority keywords  
    const mediumKeywords = ['reminder', 'follow up', 'review', 'approval'];

    // Check for high priority indicators
    if (highKeywords.some(keyword => subject.includes(keyword) || body.includes(keyword))) {
      return 'high';
    }

    // Check for medium priority indicators
    if (mediumKeywords.some(keyword => subject.includes(keyword) || body.includes(keyword))) {
      return 'medium';
    }

    // Check sender importance (executives, management, etc.)
    const importantSenders = ['ceo', 'cto', 'director', 'manager', 'lead'];
    if (importantSenders.some(imp => sender.includes(imp))) {
      return 'high';
    }

    return 'low';
  }

  private determineEmailCategory(email: OutlookEmail): string {
    const subject = email.subject.toLowerCase();
    const body = email.body.toLowerCase();

    // Category keywords
    const categories = {
      'meeting': ['meeting', 'appointment', 'schedule', 'calendar', 'call'],
      'project': ['project', 'task', 'milestone', 'deadline', 'deliverable'],
      'finance': ['invoice', 'payment', 'budget', 'cost', 'expense', 'bill'],
      'support': ['ticket', 'issue', 'bug', 'error', 'help', 'support'],
      'marketing': ['campaign', 'newsletter', 'promotion', 'marketing', 'advert'],
      'hr': ['recruiting', 'interview', 'hiring', 'onboarding', 'training'],
      'legal': ['contract', 'agreement', 'legal', 'nda', 'compliance'],
      'security': ['security', 'alert', 'warning', 'risk', 'vulnerability']
    };

    for (const [category, keywords] of Object.entries(categories)) {
      if (keywords.some(keyword => subject.includes(keyword) || body.includes(keyword))) {
        return category;
      }
    }

    return 'other';
  }

  private requiresAction(email: OutlookEmail): boolean {
    const subject = email.subject.toLowerCase();
    const body = email.body.toLowerCase();

    const actionKeywords = [
      'please', 'request', 'need', 'required', 'review', 'approve', 
      'sign', 'confirm', 'respond', 'reply', 'action'
    ];

    return actionKeywords.some(keyword => subject.includes(keyword) || body.includes(keyword));
  }
}

export class OutlookCalendarSkill {
  private logger = new Logger('OutlookCalendarSkill');

  async execute(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Outlook Calendar Skill', { action: params.action, params });

    try {
      switch (params.action) {
        case 'create':
          return await this.createEvent(params, context);
        case 'get':
          return await this.getEvents(params, context);
        case 'update':
          return await this.updateEvent(params, context);
        case 'delete':
          return await this.deleteEvent(params, context);
        case 'search':
          return await this.searchEvents(params, context);
        default:
          throw new Error(`Unsupported calendar action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Outlook Calendar Skill failed', error);
      throw error;
    }
  }

  private async createEvent(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.subject || !params.startTime || !params.endTime) {
      throw new Error('Subject, start time, and end time are required for creating events');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        subject: params.subject,
        start_time: params.startTime,
        end_time: params.endTime,
        body: params.body,
        location: params.location,
        attendees: params.attendees
      }
    };

    const result = await invoke<any>('create_outlook_calendar_event', options.args);
    
    if (result.success) {
      EventBus.emit('outlook:calendar:event:created', {
        eventId: result.eventId,
        subject: params.subject,
        startTime: params.startTime,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Calendar event created successfully', {
        subject: params.subject,
        startTime: params.startTime
      });
    }

    return {
      success: result.success,
      message: result.message,
      eventId: result.eventId,
      timestamp: new Date().toISOString()
    };
  }

  private async getEvents(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        limit: params.limit || 10
      }
    };

    const events = await invoke<OutlookCalendarEvent[]>('get_outlook_calendar_events', options.args);
    
    EventBus.emit('outlook:calendar:events:retrieved', {
      count: events.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      events: events,
      count: events.length,
      timestamp: new Date().toISOString()
    };
  }

  private async updateEvent(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.eventId) {
      throw new Error('Event ID is required for updating events');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        eventId: params.eventId,
        subject: params.subject,
        start_time: params.startTime,
        end_time: params.endTime,
        body: params.body,
        location: params.location,
        attendees: params.attendees
      }
    };

    const result = await invoke<any>('update_outlook_calendar_event', options.args);
    
    if (result.success) {
      EventBus.emit('outlook:calendar:event:updated', {
        eventId: params.eventId,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: result.success,
      message: result.message,
      timestamp: new Date().toISOString()
    };
  }

  private async deleteEvent(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.eventId) {
      throw new Error('Event ID is required for deleting events');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        eventId: params.eventId
      }
    };

    const result = await invoke<any>('delete_outlook_calendar_event', options.args);
    
    if (result.success) {
      EventBus.emit('outlook:calendar:event:deleted', {
        eventId: params.eventId,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: result.success,
      message: result.message,
      timestamp: new Date().toISOString()
    };
  }

  private async searchEvents(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.searchQuery) {
      throw new Error('Search query is required for event search');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.searchQuery,
        limit: params.limit || 10
      }
    };

    const events = await invoke<OutlookCalendarEvent[]>('search_outlook_calendar_events', options.args);
    
    EventBus.emit('outlook:calendar:events:searched', {
      query: params.searchQuery,
      count: events.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      events: events,
      count: events.length,
      searchQuery: params.searchQuery,
      timestamp: new Date().toISOString()
    };
  }
}

// Export skill instances
export const outlookEmailSkill = new OutlookEmailSkill();
export const outlookCalendarSkill = new OutlookCalendarSkill();

// Export types for external use
export type {
  OutlookEmailSkillParams,
  OutlookCalendarSkillParams,
  OutlookUserInfo,
  OutlookEmail,
  OutlookCalendarEvent
};