/**
 * Enhanced Microsoft 365 Integration
 * Complete Microsoft ecosystem integration with advanced features
 */

import { 
  invoke, 
  TauriInvokeOptions 
} from '@tauri-apps/api/tauri';
import { SkillExecutionContext } from '../types/skillTypes';
import { EventBus } from '../utils/EventBus';
import { Logger } from '../utils/Logger';

// Enhanced Microsoft Types
export interface MicrosoftUser {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle?: string;
  officeLocation?: string;
  businessPhones: string[];
  mobilePhone?: string;
}

export interface OutlookEmail {
  id: string;
  subject: string;
  from_address: {
    emailAddress: {
      address: string;
      name?: string;
    };
  };
  to_addresses: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
  }>;
  cc_addresses?: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
  }>;
  bcc_addresses?: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
  }>;
  body: string;
  bodyContentType: 'text' | 'html';
  receivedDateTime: string;
  sentDateTime?: string;
  isRead: boolean;
  isDraft: boolean;
  hasAttachments: boolean;
  importance: 'low' | 'normal' | 'high';
  conversationId?: string;
  webLink?: string;
  attachments?: Array<{
    id: string;
    name: string;
    contentType: string;
    size: number;
    isInline: boolean;
  }>;
}

export interface OutlookCalendar {
  id: string;
  name: string;
  owner: {
    address: string;
    name?: string;
  };
  canEdit: boolean;
  canView: boolean;
  isShared: boolean;
  isDefaultCalendar: boolean;
  color?: string;
  changeKey?: string;
}

export interface OutlookEvent {
  id: string;
  subject: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  body?: string;
  bodyContentType: 'text' | 'html';
  location?: {
    displayName: string;
    address?: any;
  };
  attendees?: Array<{
    emailAddress: {
      address: string;
      name?: string;
    };
    type: 'required' | 'optional' | 'resource';
    status?: {
      response: 'none' | 'organizer' | 'tentativelyAccepted' | 'accepted' | 'declined';
      time?: string;
    };
  }>;
  organizer?: {
    emailAddress: {
      address: string;
      name?: string;
    };
  };
  isAllDay: boolean;
  sensitivity: 'normal' | 'personal' | 'private' | 'confidential';
  showAs: 'free' | 'tentative' | 'busy' | 'oof' | 'workingElsewhere' | 'unknown';
  responseStatus?: {
    response: string;
    time?: string;
  };
  recurrence?: {
    pattern: {
      type: 'daily' | 'weekly' | 'absoluteMonthly' | 'relativeMonthly' | 'absoluteYearly' | 'relativeYearly';
      interval: number;
      month?: number;
      dayOfMonth?: number;
      daysOfWeek?: string[];
      firstDayOfWeek?: string;
      index?: 'first' | 'second' | 'third' | 'fourth' | 'last';
    };
    range: {
      type: 'endDate' | 'noEnd' | 'numbered';
      startDate: string;
      endDate?: string;
      numberOfOccurrences?: number;
    };
  };
  seriesMasterId?: string;
  occurrenceId?: string;
  isCancelled: boolean;
  isOrganizer: boolean;
  onlineMeetingUrl?: string;
}

export interface OutlookContact {
  id: string;
  displayName: string;
  givenName?: string;
  surname?: string;
  emailAddresses: Array<{
    address: string;
    name?: string;
  }>;
  businessPhones: string[];
  mobilePhone?: string;
  homePhones: string[];
  company_name?: string;
  department?: string;
  jobTitle?: string;
  officeLocation?: string;
  addresses?: Array<{
    street: string;
    city: string;
    state: string;
    postalCode: string;
    countryOrRegion: string;
    type: 'home' | 'business' | 'other';
  }>;
}

export interface OneDriveFile {
  id: string;
  name: string;
  webUrl: string;
  size: number;
  createdDateTime?: string;
  lastModifiedDateTime?: string;
  parentReference?: {
    driveId?: string;
    driveType?: string;
    id?: string;
    path?: string;
  };
  file?: {
    mimeType: string;
    hashes?: any;
  };
  folder?: {
    childCount?: number;
    view?: any;
  };
  mimeType?: string;
  shared: boolean;
  createdBy?: {
    user?: {
      displayName: string;
      id: string;
    };
  };
  lastModifiedBy?: {
    user?: {
      displayName: string;
      id: string;
    };
  };
  '@odata.type'?: string;
}

export interface OneDriveFolder {
  id: string;
  name: string;
  webUrl: string;
  childCount: number;
  createdDateTime?: string;
  lastModifiedDateTime?: string;
  parentReference?: {
    driveId?: string;
    driveType?: string;
    id?: string;
    path?: string;
  };
  shared: boolean;
  createdBy?: {
    user?: {
      displayName: string;
      id: string;
    };
  };
  lastModifiedBy?: {
    user?: {
      displayName: string;
      id: string;
    };
  };
}

export interface TeamsChannel {
  id: string;
  displayName: string;
  description?: string;
  isFavoriteByDefault: boolean;
  membershipType: 'standard' | 'private' | 'shared' | 'unknown';
  email?: string;
  webUrl: string;
  tenantId?: string;
  createdDateTime?: string;
  lastModifiedDateTime?: string;
}

export interface TeamsMessage {
  id: string;
  messageType: 'message' | 'systemEventMessage' | 'undefined';
  createdDateTime?: string;
  lastModifiedDateTime?: string;
  subject?: string;
  summary?: string;
  importance: 'low' | 'normal' | 'high';
  locale: string;
  webUrl?: string;
  from_user?: {
    user: {
      displayName: string;
      id: string;
    };
  };
  body?: {
    contentType: 'text' | 'html';
    content: string;
  };
  attachments?: Array<{
    id: string;
    contentType: string;
    name: string;
    contentUrl?: string;
  }>;
  mentions?: Array<{
    id: number;
    mentionText: string;
    mentioned: {
      user?: {
        displayName: string;
        id: string;
      };
    };
  }>;
  replies?: TeamsMessage[];
}

// Skill Parameters
export interface OutlookCalendarSkillParams {
  action: 'list_calendars' | 'create_calendar' | 'delete_calendar' | 'update_calendar' |
          'list_events' | 'create_event' | 'update_event' | 'delete_event' | 
          'create_recurring_event' | 'get_user_info';
  calendar_id?: string;
  name?: string;
  subject: string;
  start_time: string;
  end_time: string;
  body?: string;
  bodyContentType?: 'text' | 'html';
  location?: string;
  attendees?: Array<{
    email: string;
    name?: string;
    type?: 'required' | 'optional' | 'resource';
  }>;
  isAllDay?: boolean;
  sensitivity?: 'normal' | 'personal' | 'private' | 'confidential';
  showAs?: 'free' | 'tentative' | 'busy' | 'oof' | 'workingElsewhere' | 'unknown';
  eventId?: string;
  updates?: Partial<OutlookEvent>;
  recurrence_pattern?: {
    pattern: any;
    range: any;
  };
}

export interface OutlookEmailSkillParams {
  action: 'send' | 'get' | 'search' | 'reply' | 'forward' | 'get_user_info';
  to?: string[];
  cc?: string[];
  bcc?: string[];
  subject?: string;
  body?: string;
  bodyContentType?: 'text' | 'html';
  searchQuery?: string;
  limit?: number;
  folder_id?: string;
  message_id?: string;
  is_read?: boolean;
  importance?: 'low' | 'normal' | 'high';
  has_attachments?: boolean;
}

export interface OneDriveSkillParams {
  action: 'list_files' | 'list_folders' | 'create_folder' | 'upload_file' | 
          'share_file' | 'search_files' | 'get_user_info';
  folder_id?: string;
  name?: string;
  parent_folder_id?: string;
  file_content?: string;
  file_name?: string;
  query?: string;
  file_id?: string;
  recipients?: string[];
  role?: 'view' | 'edit' | 'owner';
}

export interface TeamsSkillParams {
  action: 'list_teams' | 'list_channels' | 'get_messages' | 'send_message' | 'get_user_info';
  team_id?: string;
  channel_id?: string;
  content?: string;
  contentType?: 'text' | 'html';
  limit?: number;
}

export interface ContactsSkillParams {
  action: 'list_contacts' | 'create_contact' | 'update_contact' | 'delete_contact' | 'get_user_info';
  displayName?: string;
  givenName?: string;
  surname?: string;
  emailAddresses?: Array<{
    address: string;
    name?: string;
  }>;
  businessPhones?: string[];
  mobilePhone?: string;
  homePhones?: string[];
  company_name?: string;
  department?: string;
  jobTitle?: string;
  officeLocation?: string;
  addresses?: Array<{
    street: string;
    city: string;
    state: string;
    postalCode: string;
    countryOrRegion: string;
    type: 'home' | 'business' | 'other';
  }>;
  contact_id?: string;
  updates?: Partial<OutlookContact>;
}

// Enhanced Microsoft Skills Classes
export class OutlookCalendarEnhancedSkill {
  private logger = new Logger('OutlookCalendarEnhancedSkill');

  async execute(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Outlook Calendar Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_calendars':
          return await this.listCalendars(params, context);
        case 'create_calendar':
          return await this.createCalendar(params, context);
        case 'list_events':
          return await this.listEvents(params, context);
        case 'create_event':
          return await this.createEvent(params, context);
        case 'create_recurring_event':
          return await this.createRecurringEvent(params, context);
        case 'get_user_info':
          return await this.getUserInfo(params, context);
        default:
          throw new Error(`Unsupported Outlook Calendar action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Outlook Calendar Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listCalendars(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const calendars = await invoke<OutlookCalendar[]>('microsoft_calendar_list_calendars_enhanced', options.args);
    
    EventBus.emit('microsoft:calendar:listed', {
      count: calendars.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      calendars: calendars,
      count: calendars.length,
      timestamp: new Date().toISOString()
    };
  }

  private async createCalendar(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.name) {
      throw new Error('Calendar name is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        name: params.name
      }
    };

    const calendar = await invoke<OutlookCalendar>('microsoft_calendar_create_calendar_enhanced', options.args);
    
    if (calendar) {
      EventBus.emit('microsoft:calendar:created', {
        calendarId: calendar.id,
        name: params.name,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Calendar created successfully', {
        calendarId: calendar.id,
        name: params.name
      });
    }

    return {
      success: true,
      calendar: calendar,
      timestamp: new Date().toISOString()
    };
  }

  private async listEvents(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id,
        start_date: params.start_time,
        end_date: params.end_time
      }
    };

    const events = await invoke<OutlookEvent[]>('microsoft_calendar_list_events_enhanced', options.args);
    
    EventBus.emit('microsoft:calendar:events:listed', {
      calendarId: params.calendar_id || 'primary',
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

  private async createEvent(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.subject || !params.start_time || !params.end_time) {
      throw new Error('Subject, start time, and end time are required');
    }

    const eventData = {
      subject: params.subject,
      body: {
        contentType: params.bodyContentType || 'text',
        content: params.body || ''
      },
      start: {
        dateTime: params.start_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      end: {
        dateTime: params.end_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      location: params.location ? {
        displayName: params.location
      } : undefined,
      attendees: params.attendees?.map(attendee => ({
        emailAddress: {
          address: attendee.email,
          name: attendee.name
        },
        type: attendee.type || 'required'
      })),
      isAllDay: params.isAllDay || false,
      sensitivity: params.sensitivity || 'normal',
      showAs: params.showAs || 'busy'
    };

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id,
        event_data: eventData
      }
    };

    const event = await invoke<OutlookEvent>('microsoft_calendar_create_event_enhanced', options.args);
    
    if (event) {
      EventBus.emit('microsoft:calendar:event:created', {
        eventId: event.id,
        subject: params.subject,
        startTime: params.start_time,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Event created successfully', {
        eventId: event.id,
        subject: params.subject
      });
    }

    return {
      success: true,
      event: event,
      timestamp: new Date().toISOString()
    };
  }

  private async createRecurringEvent(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.subject || !params.start_time || !params.end_time || !params.recurrence_pattern) {
      throw new Error('Subject, start time, end time, and recurrence pattern are required');
    }

    const baseEvent = {
      subject: params.subject,
      body: {
        contentType: params.bodyContentType || 'text',
        content: params.body || ''
      },
      start: {
        dateTime: params.start_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      end: {
        dateTime: params.end_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      location: params.location ? {
        displayName: params.location
      } : undefined,
      attendees: params.attendees?.map(attendee => ({
        emailAddress: {
          address: attendee.email,
          name: attendee.name
        },
        type: attendee.type || 'required'
      })),
      isAllDay: params.isAllDay || false,
      sensitivity: params.sensitivity || 'normal',
      showAs: params.showAs || 'busy'
    };

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id,
        base_event: baseEvent,
        recurrence_pattern: params.recurrence_pattern
      }
    };

    const event = await invoke<OutlookEvent>('microsoft_calendar_create_recurring_event_enhanced', options.args);
    
    EventBus.emit('microsoft:calendar:recurring_event:created', {
      eventId: event.id,
      subject: params.subject,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      event: event,
      timestamp: new Date().toISOString()
    };
  }

  private async getUserInfo(params: OutlookCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const user = await invoke<MicrosoftUser>('microsoft_get_user_info_enhanced', options.args);
    
    return {
      success: true,
      user: user,
      timestamp: new Date().toISOString()
    };
  }
}

export class OutlookEmailEnhancedSkill {
  private logger = new Logger('OutlookEmailEnhancedSkill');

  async execute(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Outlook Email Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'send':
          return await this.sendEmail(params, context);
        case 'get':
          return await this.getEmails(params, context);
        case 'search':
          return await this.searchEmails(params, context);
        case 'reply':
          return await this.replyToEmail(params, context);
        case 'get_user_info':
          return await this.getUserInfo(params, context);
        default:
          throw new Error(`Unsupported Outlook Email action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Outlook Email Enhanced Skill failed', error);
      throw error;
    }
  }

  private async sendEmail(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.to || !params.subject || !params.body) {
      throw new Error('To addresses, subject, and body are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        to_addresses: params.to,
        cc_addresses: params.cc,
        bcc_addresses: params.bcc,
        subject: params.subject,
        body: params.body,
        is_html: params.bodyContentType === 'html'
      }
    };

    const result = await invoke<any>('microsoft_email_send_message_enhanced', options.args);
    
    if (result && !result.error) {
      EventBus.emit('microsoft:email:sent', {
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
      success: !result.error,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async getEmails(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        folder_id: params.folder_id,
        limit: params.limit || 50
      }
    };

    const emails = await invoke<OutlookEmail[]>('microsoft_email_list_messages_enhanced', options.args);
    
    EventBus.emit('microsoft:email:retrieved', {
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
      throw new Error('Search query is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.searchQuery,
        limit: params.limit || 50
      }
    };

    const emails = await invoke<OutlookEmail[]>('microsoft_email_search_messages_enhanced', options.args);
    
    EventBus.emit('microsoft:email:searched', {
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

  private async replyToEmail(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.message_id || !params.body) {
      throw new Error('Message ID and body are required for reply');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        message_id: params.message_id,
        body: params.body,
        is_html: params.bodyContentType === 'html'
      }
    };

    const result = await invoke<any>('microsoft_email_reply_to_message_enhanced', options.args);
    
    EventBus.emit('microsoft:email:replied', {
      messageId: params.message_id,
      timestamp: new Date().toISOString()
    });

    return {
      success: !result.error,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async getUserInfo(params: OutlookEmailSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const user = await invoke<MicrosoftUser>('microsoft_get_user_info_enhanced', options.args);
    
    return {
      success: true,
      user: user,
      timestamp: new Date().toISOString()
    };
  }
}

export class OneDriveEnhancedSkill {
  private logger = new Logger('OneDriveEnhancedSkill');

  async execute(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing OneDrive Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_files':
          return await this.listFiles(params, context);
        case 'list_folders':
          return await this.listFolders(params, context);
        case 'create_folder':
          return await this.createFolder(params, context);
        case 'upload_file':
          return await this.uploadFile(params, context);
        case 'share_file':
          return await this.shareFile(params, context);
        case 'search_files':
          return await this.searchFiles(params, context);
        case 'get_user_info':
          return await this.getUserInfo(params, context);
        default:
          throw new Error(`Unsupported OneDrive action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('OneDrive Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listFiles(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        folder_id: params.folder_id,
        query: params.query
      }
    };

    const files = await invoke<OneDriveFile[]>('microsoft_onedrive_list_files_enhanced', options.args);
    
    EventBus.emit('microsoft:onedrive:files:listed', {
      count: files.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      files: files,
      count: files.length,
      timestamp: new Date().toISOString()
    };
  }

  private async listFolders(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        parent_folder_id: params.folder_id
      }
    };

    const folders = await invoke<OneDriveFolder[]>('microsoft_onedrive_list_folders_enhanced', options.args);
    
    EventBus.emit('microsoft:onedrive:folders:listed', {
      count: folders.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      folders: folders,
      count: folders.length,
      timestamp: new Date().toISOString()
    };
  }

  private async createFolder(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.name) {
      throw new Error('Folder name is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        name: params.name,
        parent_folder_id: params.parent_folder_id
      }
    };

    const folder = await invoke<OneDriveFolder>('microsoft_onedrive_create_folder_enhanced', options.args);
    
    if (folder) {
      EventBus.emit('microsoft:onedrive:folder:created', {
        folderId: folder.id,
        name: params.name,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      folder: folder,
      timestamp: new Date().toISOString()
    };
  }

  private async shareFile(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.file_id && !params.folder_id) {
      throw new Error('File ID or folder ID is required for sharing');
    }

    if (!params.recipients) {
      throw new Error('Recipients are required for sharing');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        item_id: params.file_id || params.folder_id,
        recipients: params.recipients,
        role: params.role || 'view'
      }
    };

    const result = await invoke<any>('microsoft_onedrive_share_item_enhanced', options.args);
    
    EventBus.emit('microsoft:onedrive:item:shared', {
      itemId: params.file_id || params.folder_id,
      recipients: params.recipients,
      role: params.role,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async searchFiles(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.query) {
      throw new Error('Search query is required');
    }

    return await this.listFiles(params, context);
  }

  private async uploadFile(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.file_content || !params.file_name) {
      throw new Error('File content and file name are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        file_content: params.file_content,
        file_name: params.file_name,
        folder_id: params.folder_id
      }
    };

    const file = await invoke<OneDriveFile>('microsoft_onedrive_upload_file_enhanced', options.args);
    
    if (file) {
      EventBus.emit('microsoft:onedrive:file:uploaded', {
        fileId: file.id,
        name: params.file_name,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      file: file,
      timestamp: new Date().toISOString()
    };
  }

  private async getUserInfo(params: OneDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const user = await invoke<MicrosoftUser>('microsoft_get_user_info_enhanced', options.args);
    
    return {
      success: true,
      user: user,
      timestamp: new Date().toISOString()
    };
  }
}

export class TeamsEnhancedSkill {
  private logger = new Logger('TeamsEnhancedSkill');

  async execute(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Teams Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_teams':
          return await this.listTeams(params, context);
        case 'list_channels':
          return await this.listChannels(params, context);
        case 'get_messages':
          return await this.getMessages(params, context);
        case 'send_message':
          return await this.sendMessage(params, context);
        case 'get_user_info':
          return await this.getUserInfo(params, context);
        default:
          throw new Error(`Unsupported Teams action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Teams Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listTeams(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const teams = await invoke<any[]>('microsoft_teams_list_teams_enhanced', options.args);
    
    EventBus.emit('microsoft:teams:listed', {
      count: teams.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      teams: teams,
      count: teams.length,
      timestamp: new Date().toISOString()
    };
  }

  private async listChannels(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.team_id) {
      throw new Error('Team ID is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        team_id: params.team_id
      }
    };

    const channels = await invoke<TeamsChannel[]>('microsoft_teams_list_channels_enhanced', options.args);
    
    EventBus.emit('microsoft:teams:channels:listed', {
      teamId: params.team_id,
      count: channels.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      channels: channels,
      count: channels.length,
      timestamp: new Date().toISOString()
    };
  }

  private async getMessages(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.team_id || !params.channel_id) {
      throw new Error('Team ID and Channel ID are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        team_id: params.team_id,
        channel_id: params.channel_id,
        limit: params.limit || 50
      }
    };

    const messages = await invoke<TeamsMessage[]>('microsoft_teams_get_messages_enhanced', options.args);
    
    EventBus.emit('microsoft:teams:messages:retrieved', {
      teamId: params.team_id,
      channelId: params.channel_id,
      count: messages.length,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      messages: messages,
      count: messages.length,
      timestamp: new Date().toISOString()
    };
  }

  private async sendMessage(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.team_id || !params.channel_id || !params.content) {
      throw new Error('Team ID, Channel ID, and content are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        team_id: params.team_id,
        channel_id: params.channel_id,
        content: params.content,
        content_type: params.contentType || 'text'
      }
    };

    const result = await invoke<any>('microsoft_teams_send_message_enhanced', options.args);
    
    EventBus.emit('microsoft:teams:message:sent', {
      teamId: params.team_id,
      channelId: params.channel_id,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async getUserInfo(params: TeamsSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const user = await invoke<MicrosoftUser>('microsoft_get_user_info_enhanced', options.args);
    
    return {
      success: true,
      user: user,
      timestamp: new Date().toISOString()
    };
  }
}

// Export skill instances
export const outlookCalendarEnhancedSkill = new OutlookCalendarEnhancedSkill();
export const outlookEmailEnhancedSkill = new OutlookEmailEnhancedSkill();
export const oneDriveEnhancedSkill = new OneDriveEnhancedSkill();
export const teamsEnhancedSkill = new TeamsEnhancedSkill();

// Export types for external use
export type {
  MicrosoftUser,
  OutlookEmail,
  OutlookCalendar,
  OutlookEvent,
  OutlookContact,
  OneDriveFile,
  OneDriveFolder,
  TeamsChannel,
  TeamsMessage,
  OutlookCalendarSkillParams,
  OutlookEmailSkillParams,
  OneDriveSkillParams,
  TeamsSkillParams,
  ContactsSkillParams
};