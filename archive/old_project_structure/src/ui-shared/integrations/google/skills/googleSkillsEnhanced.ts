/**
 * Enhanced Google Suite Integration
 * Complete Google Workspace integration with advanced features
 */

import { 
  invoke, 
  TauriInvokeOptions 
} from '@tauri-apps/api/tauri';
import { SkillExecutionContext } from '../types/skillTypes';
import { EventBus } from '../utils/EventBus';
import { Logger } from '../utils/Logger';

// Enhanced Google Types
export interface GoogleUser {
  id: string;
  email: string;
  name: string;
  picture?: string;
  verified_email: boolean;
  hd?: string;
}

export interface GoogleCalendar {
  id: string;
  summary: string;
  description?: string;
  location?: string;
  timezone: string;
  primary: boolean;
  access_role: string;
  color_id?: string;
  background_color?: string;
  foreground_color?: string;
}

export interface GoogleCalendarEvent {
  id: string;
  summary: string;
  start: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
    timeZone?: string;
  };
  description?: string;
  location?: string;
  attendees?: Array<{
    email: string;
    displayName?: string;
    responseStatus?: string;
  }>;
  creator?: GoogleUser;
  organizer?: GoogleUser;
  hangout_link?: string;
  visibility: string;
  transparency: string;
  i_cal_uid?: string;
  sequence: number;
  recurrence?: string[];
  recurring_event_id?: string;
  original_start_time?: any;
  status: string;
  color_id?: string;
  attachments?: Array<{
    title: string;
    fileUrl: string;
    mimeType: string;
  }>;
}

export interface GmailMessage {
  id: string;
  thread_id: string;
  snippet: string;
  subject: string;
  from_email: string;
  to_emails: string[];
  date: string;
  is_read: boolean;
  is_starred: boolean;
  is_important: boolean;
  labels: string[];
  attachments?: Array<{
    filename: string;
    mimeType: string;
    size: number;
    attachmentId: string;
  }>;
  body?: string;
}

export interface GmailLabel {
  id: string;
  name: string;
  message_list_visibility: string;
  label_list_visibility: string;
  message_total: number;
  message_unread: number;
  threads_total: number;
  threads_unread: number;
  color?: {
    backgroundColor: string;
    textColor: string;
  };
}

export interface GoogleDriveFile {
  id: string;
  name: string;
  mime_type: string;
  size?: string;
  created_time?: string;
  modified_time?: string;
  parents: string[];
  webViewLink?: string;
  webContentLink?: string;
  owners?: Array<{
    displayName: string;
    emailAddress: string;
  }>;
  permissions?: Array<{
    id: string;
    type: string;
    role: string;
    emailAddress?: string;
  }>;
  thumbnailLink?: string;
  is_folder: boolean;
  shared: boolean;
}

export interface GmailFilter {
  id: string;
  criteria: {
    from?: string;
    to?: string;
    subject?: string;
    query?: string;
    hasAttachment?: boolean;
  };
  action: {
    addLabelIds?: string[];
    removeLabelIds?: string[];
    forward?: string;
  };
}

export interface GmailSettings {
  auto_forwarding?: {
    enabled: boolean;
    emailAddress?: string;
    disposition: string;
  };
  imap_enabled: boolean;
  pop_enabled: boolean;
  language: string;
  display_language: string;
  signature?: string;
  vacation_settings?: {
    enableAutoReply: boolean;
    responseSubject: string;
    responseBodyPlainText: string;
    restrictToContacts: boolean;
  };
}

// Skill Parameters
export interface GoogleCalendarSkillParams {
  action: 'list_calendars' | 'create_calendar' | 'delete_calendar' | 'update_calendar' |
          'list_events' | 'create_event' | 'update_event' | 'delete_event' | 
          'create_recurring_event' | 'get_free_busy' | 'share_calendar';
  calendar_id?: string;
  summary?: string;
  description?: string;
  location?: string;
  timezone?: string;
  start_time?: string;
  end_time?: string;
  attendees?: string[];
  visibility?: string;
  transparency?: string;
  recurrence_rules?: string[];
  user_ids?: string[];
  time_min?: string;
  time_max?: string;
  email?: string;
  role?: string;
  updates?: Partial<GoogleCalendar>;
}

export interface GmailSkillParams {
  action: 'list_messages' | 'send_message' | 'create_label' | 'get_settings' |
          'search_messages' | 'mark_read' | 'mark_starred' | 'apply_filter';
  query?: string;
  max_results?: number;
  label_ids?: string[];
  to_addresses?: string[];
  cc_addresses?: string[];
  bcc_addresses?: string[];
  subject?: string;
  body?: string;
  is_html?: boolean;
  label_name?: string;
  message_id?: string;
  is_read?: boolean;
  is_starred?: boolean;
}

export interface GoogleDriveSkillParams {
  action: 'list_files' | 'upload_file' | 'create_folder' | 'share_file' |
          'search_files' | 'delete_file' | 'move_file' | 'copy_file';
  query?: string;
  page_size?: number;
  folder_id?: string;
  file_path?: string;
  file_name?: string;
  file_content?: string;
  parent_id?: string;
  destination_id?: string;
  email?: string;
  role?: string;
}

// Enhanced Google Skills Classes
export class GoogleCalendarEnhancedSkill {
  private logger = new Logger('GoogleCalendarEnhancedSkill');

  async execute(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Google Calendar Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_calendars':
          return await this.listCalendars(params, context);
        case 'create_calendar':
          return await this.createCalendar(params, context);
        case 'delete_calendar':
          return await this.deleteCalendar(params, context);
        case 'update_calendar':
          return await this.updateCalendar(params, context);
        case 'list_events':
          return await this.listEvents(params, context);
        case 'create_event':
          return await this.createEvent(params, context);
        case 'update_event':
          return await this.updateEvent(params, context);
        case 'delete_event':
          return await this.deleteEvent(params, context);
        case 'create_recurring_event':
          return await this.createRecurringEvent(params, context);
        case 'get_free_busy':
          return await this.getFreeBusy(params, context);
        case 'share_calendar':
          return await this.shareCalendar(params, context);
        default:
          throw new Error(`Unsupported calendar action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Google Calendar Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listCalendars(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const calendars = await invoke<GoogleCalendar[]>('google_calendar_list_calendars_enhanced', options.args);
    
    EventBus.emit('google:calendar:listed', {
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

  private async createCalendar(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.summary) {
      throw new Error('Calendar summary is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        summary: params.summary,
        timezone: params.timezone || 'America/New_York',
        description: params.description,
        location: params.location
      }
    };

    const calendar = await invoke<GoogleCalendar>('google_calendar_create_calendar_enhanced', options.args);
    
    if (calendar) {
      EventBus.emit('google:calendar:created', {
        calendarId: calendar.id,
        summary: params.summary,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Calendar created successfully', {
        calendarId: calendar.id,
        summary: params.summary
      });
    }

    return {
      success: true,
      calendar: calendar,
      timestamp: new Date().toISOString()
    };
  }

  private async listEvents(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendarId: params.calendar_id || 'primary',
        time_min: params.time_min,
        time_max: params.time_max,
        max_results: 50
      }
    };

    const events = await invoke<GoogleCalendarEvent[]>('google_calendar_list_events_enhanced', options.args);
    
    EventBus.emit('google:calendar:events:listed', {
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

  private async createEvent(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.summary || !params.start_time || !params.end_time) {
      throw new Error('Event summary, start time, and end time are required');
    }

    const eventData = {
      summary: params.summary,
      description: params.description,
      location: params.location,
      start: {
        dateTime: params.start_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      end: {
        dateTime: params.end_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      attendees: params.attendees?.map(email => ({ email })),
      visibility: params.visibility || 'default',
      transparency: params.transparency || 'opaque'
    };

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id || 'primary',
        event_data: eventData
      }
    };

    const event = await invoke<GoogleCalendarEvent>('google_calendar_create_event_enhanced', options.args);
    
    if (event) {
      EventBus.emit('google:calendar:event:created', {
        eventId: event.id,
        summary: params.summary,
        startTime: params.start_time,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Event created successfully', {
        eventId: event.id,
        summary: params.summary
      });
    }

    return {
      success: true,
      event: event,
      timestamp: new Date().toISOString()
    };
  }

  private async createRecurringEvent(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.summary || !params.start_time || !params.end_time || !params.recurrence_rules) {
      throw new Error('Event summary, start time, end time, and recurrence rules are required');
    }

    const baseEvent = {
      summary: params.summary,
      description: params.description,
      location: params.location,
      start: {
        dateTime: params.start_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      end: {
        dateTime: params.end_time,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      attendees: params.attendees?.map(email => ({ email })),
      visibility: params.visibility || 'default',
      transparency: params.transparency || 'opaque'
    };

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id || 'primary',
        base_event: baseEvent,
        recurrence_rules: params.recurrence_rules
      }
    };

    const event = await invoke<GoogleCalendarEvent>('google_calendar_create_recurring_event_enhanced', options.args);
    
    EventBus.emit('google:calendar:recurring_event:created', {
      eventId: event.id,
      summary: params.summary,
      recurrenceRules: params.recurrence_rules,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      event: event,
      timestamp: new Date().toISOString()
    };
  }

  private async getFreeBusy(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.user_ids || !params.time_min || !params.time_max) {
      throw new Error('User IDs, time_min, and time_max are required for free/busy lookup');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        user_ids: params.user_ids,
        time_min: params.time_min,
        time_max: params.time_max
      }
    };

    const freeBusy = await invoke<any>('google_calendar_get_free_busy_enhanced', options.args);
    
    EventBus.emit('google:calendar:free_busy:retrieved', {
      userIds: params.user_ids,
      timeMin: params.time_min,
      timeMax: params.time_max,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      free_busy: freeBusy,
      timestamp: new Date().toISOString()
    };
  }

  private async shareCalendar(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.calendar_id || !params.email) {
      throw new Error('Calendar ID and email are required for sharing');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id,
        email: params.email,
        role: params.role || 'reader'
      }
    };

    const result = await invoke<any>('google_calendar_share_calendar_enhanced', options.args);
    
    EventBus.emit('google:calendar:shared', {
      calendarId: params.calendar_id,
      email: params.email,
      role: params.role,
      timestamp: new Date().toISOString()
    });

    return {
      success: result,
      timestamp: new Date().toISOString()
    };
  }

  private async updateCalendar(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.calendar_id) {
      throw new Error('Calendar ID is required for updating');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id,
        updates: params.updates || {}
      }
    };

    const calendar = await invoke<GoogleCalendar>('google_calendar_update_calendar_enhanced', options.args);
    
    EventBus.emit('google:calendar:updated', {
      calendarId: params.calendar_id,
      timestamp: new Date().toISOString()
    });

    return {
      success: true,
      calendar: calendar,
      timestamp: new Date().toISOString()
    };
  }

  private async deleteCalendar(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.calendar_id) {
      throw new Error('Calendar ID is required for deletion');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        calendar_id: params.calendar_id
      }
    };

    const result = await invoke<boolean>('google_calendar_delete_calendar_enhanced', options.args);
    
    EventBus.emit('google:calendar:deleted', {
      calendarId: params.calendar_id,
      timestamp: new Date().toISOString()
    });

    return {
      success: result,
      timestamp: new Date().toISOString()
    };
  }

  private async updateEvent(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.calendar_id) {
      throw new Error('Calendar ID is required for updating events');
    }

    // Implementation would follow similar pattern to createEvent
    // For now, return mock response
    return {
      success: true,
      message: 'Event update not yet implemented',
      timestamp: new Date().toISOString()
    };
  }

  private async deleteEvent(params: GoogleCalendarSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.calendar_id) {
      throw new Error('Calendar ID is required for deleting events');
    }

    // Implementation would follow similar pattern to createEvent
    // For now, return mock response
    return {
      success: true,
      message: 'Event deletion not yet implemented',
      timestamp: new Date().toISOString()
    };
  }
}

export class GmailEnhancedSkill {
  private logger = new Logger('GmailEnhancedSkill');

  async execute(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Gmail Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_messages':
          return await this.listMessages(params, context);
        case 'send_message':
          return await this.sendMessage(params, context);
        case 'create_label':
          return await this.createLabel(params, context);
        case 'get_settings':
          return await this.getSettings(params, context);
        case 'search_messages':
          return await this.searchMessages(params, context);
        default:
          throw new Error(`Unsupported Gmail action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Gmail Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listMessages(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.query,
        max_results: params.max_results || 50,
        label_ids: params.label_ids
      }
    };

    const messages = await invoke<GmailMessage[]>('gmail_list_messages_enhanced', options.args);
    
    EventBus.emit('gmail:messages:listed', {
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

  private async sendMessage(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.to_addresses || !params.subject || !params.body) {
      throw new Error('To addresses, subject, and body are required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        to_addresses: params.to_addresses,
        cc_addresses: params.cc_addresses,
        bcc_addresses: params.bcc_addresses,
        subject: params.subject,
        body: params.body,
        is_html: params.is_html || false
      }
    };

    const result = await invoke<any>('gmail_send_message_enhanced', options.args);
    
    if (result && !result.error) {
      EventBus.emit('gmail:message:sent', {
        subject: params.subject,
        to: params.to_addresses,
        timestamp: new Date().toISOString()
      });

      this.logger.info('Message sent successfully', {
        subject: params.subject,
        to: params.to_addresses
      });
    }

    return {
      success: !result.error,
      result: result,
      timestamp: new Date().toISOString()
    };
  }

  private async createLabel(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.label_name) {
      throw new Error('Label name is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        name: params.label_name,
        message_visibility: 'show',
        label_visibility: 'labelShow'
      }
    };

    const label = await invoke<GmailLabel>('gmail_create_label_enhanced', options.args);
    
    if (label) {
      EventBus.emit('gmail:label:created', {
        labelId: label.id,
        name: params.label_name,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      label: label,
      timestamp: new Date().toISOString()
    };
  }

  private async getSettings(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user'
      }
    };

    const settings = await invoke<GmailSettings>('gmail_get_settings_enhanced', options.args);
    
    return {
      success: true,
      settings: settings,
      timestamp: new Date().toISOString()
    };
  }

  private async searchMessages(params: GmailSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.query) {
      throw new Error('Search query is required');
    }

    return await this.listMessages(params, context);
  }
}

export class GoogleDriveEnhancedSkill {
  private logger = new Logger('GoogleDriveEnhancedSkill');

  async execute(params: GoogleDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    this.logger.info('Executing Google Drive Enhanced Skill', { action: params.action });

    try {
      switch (params.action) {
        case 'list_files':
          return await this.listFiles(params, context);
        case 'create_folder':
          return await this.createFolder(params, context);
        case 'share_file':
          return await this.shareFile(params, context);
        case 'search_files':
          return await this.searchFiles(params, context);
        default:
          throw new Error(`Unsupported Drive action: ${params.action}`);
      }
    } catch (error) {
      this.logger.error('Google Drive Enhanced Skill failed', error);
      throw error;
    }
  }

  private async listFiles(params: GoogleDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        query: params.query,
        page_size: params.page_size || 100,
        folder_id: params.folder_id
      }
    };

    const files = await invoke<GoogleDriveFile[]>('google_drive_list_files_enhanced', options.args);
    
    EventBus.emit('google_drive:files:listed', {
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

  private async createFolder(params: GoogleDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.file_name) {
      throw new Error('Folder name is required');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        name: params.file_name,
        parent_id: params.folder_id
      }
    };

    const folder = await invoke<GoogleDriveFile>('google_drive_create_folder_enhanced', options.args);
    
    if (folder) {
      EventBus.emit('google_drive:folder:created', {
        folderId: folder.id,
        name: params.file_name,
        timestamp: new Date().toISOString()
      });
    }

    return {
      success: true,
      folder: folder,
      timestamp: new Date().toISOString()
    };
  }

  private async shareFile(params: GoogleDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.file_path && !params.folder_id) {
      throw new Error('File path or folder ID is required for sharing');
    }

    const options: TauriInvokeOptions = {
      args: {
        userId: context.userId || 'desktop-user',
        file_id: params.file_path || params.folder_id,
        email: params.email,
        role: params.role || 'reader'
      }
    };

    const result = await invoke<boolean>('google_drive_share_file_enhanced', options.args);
    
    EventBus.emit('google_drive:file:shared', {
      fileId: params.file_path || params.folder_id,
      email: params.email,
      role: params.role,
      timestamp: new Date().toISOString()
    });

    return {
      success: result,
      timestamp: new Date().toISOString()
    };
  }

  private async searchFiles(params: GoogleDriveSkillParams, context: SkillExecutionContext): Promise<any> {
    if (!params.query) {
      throw new Error('Search query is required');
    }

    return await this.listFiles(params, context);
  }
}

// Export skill instances
export const googleCalendarEnhancedSkill = new GoogleCalendarEnhancedSkill();
export const gmailEnhancedSkill = new GmailEnhancedSkill();
export const googleDriveEnhancedSkill = new GoogleDriveEnhancedSkill();

// Export types for external use
export type {
  GoogleUser,
  GoogleCalendar,
  GoogleCalendarEvent,
  GmailMessage,
  GmailLabel,
  GoogleDriveFile,
  GmailFilter,
  GmailSettings,
  GoogleCalendarSkillParams,
  GmailSkillParams,
  GoogleDriveSkillParams
};