import { Skill, SkillAction, SkillContext } from '../../types/skillTypes';
import { invoke } from '@tauri-apps/api/tauri';

// Re-export Google types from Gmail skill
export type {
  GoogleUser,
  GoogleCalendar,
  GoogleCalendarEvent,
  GoogleEventAttendee,
  GoogleEventOrganizer,
  GoogleEventAttachment,
  GoogleSearchResult
} from './googleGmailSkill';

// Google Calendar Specific Types
export interface GoogleCalendarAclRule {
  id: string;
  role: 'none' | 'freeBusyReader' | 'reader' | 'writer' | 'owner';
  scope: {
    type: 'default' | 'user' | 'group' | 'domain';
    value?: string;
  };
}

export interface GoogleCalendarColor {
  id: string;
  background: string;
  foreground: string;
}

export interface GoogleCalendarList {
  calendars: GoogleCalendar[];
  nextPageToken?: string;
}

export interface GoogleEventsList {
  events: GoogleCalendarEvent[];
  nextPageToken?: string;
  timeZone?: string;
  defaultReminders?: Array<{
    method: 'email' | 'popup';
    minutes: number;
  }>;
}

export interface GoogleEventReminder {
  method: 'email' | 'popup' | 'sms';
  minutes: number;
}

// Google Calendar Skill Implementation
export class GoogleCalendarSkill implements Skill {
  name = 'google_calendar';
  displayName = 'Google Calendar';
  description = 'Manage Google Calendar events, schedules, and appointments';
  icon = '📅';
  category = 'productivity';
  supportedActions = [
    'list_calendars',
    'list_events',
    'create_event',
    'update_event',
    'delete_event'
  ];

  async execute(action: SkillAction, context: SkillContext): Promise<any> {
    try {
      switch (action.action) {
        case 'list_calendars':
          return await this.listCalendars(action as GoogleCalendarListAction, context);
        case 'list_events':
          return await this.listEvents(action as GoogleCalendarEventsAction, context);
        case 'create_event':
          return await this.createEvent(action as GoogleCalendarCreateAction, context);
        case 'update_event':
          return await this.updateEvent(action as GoogleCalendarUpdateAction, context);
        case 'delete_event':
          return await this.deleteEvent(action as GoogleCalendarDeleteAction, context);
        default:
          throw new Error(`Unknown Google Calendar action: ${action.action}`);
      }
    } catch (error) {
      console.error('Google Calendar skill execution failed:', error);
      throw new Error(`Google Calendar skill execution failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async listCalendars(action: GoogleCalendarListAction, context: SkillContext): Promise<GoogleCalendarList> {
    const result = await invoke('google_calendar_list_calendars', {
      userId: context.userId
    });
    return result as GoogleCalendarList;
  }

  private async listEvents(action: GoogleCalendarEventsAction, context: SkillContext): Promise<GoogleEventsList> {
    const result = await invoke('google_calendar_list_events', {
      userId: context.userId,
      calendarId: action.params.calendarId || 'primary',
      timeMin: action.params.timeMin,
      timeMax: action.params.timeMax,
      q: action.params.q,
      maxResults: action.params.maxResults,
      singleEvents: action.params.singleEvents !== false,
      orderBy: action.params.orderBy || 'startTime'
    });
    return result as GoogleEventsList;
  }

  private async createEvent(action: GoogleCalendarCreateAction, context: SkillContext): Promise<{ success: boolean; eventId?: string; error?: string }> {
    const eventData = {
      calendarId: action.params.calendarId || 'primary',
      summary: action.params.summary,
      description: action.params.description,
      location: action.params.location,
      start: action.params.allDay ? {
        date: action.params.startTime.split('T')[0]
      } : {
        dateTime: action.params.startTime,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      end: action.params.allDay ? {
        date: action.params.endTime.split('T')[0]
      } : {
        dateTime: action.params.endTime,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      },
      attendees: action.params.attendees?.map(email => ({ email })),
      visibility: action.params.visibility || 'default',
      transparency: action.params.transparency || 'opaque',
      reminders: {
        useDefault: false,
        overrides: action.params.reminder || [
          { method: 'email' as const, minutes: 24 * 60 }, // 24 hours before
          { method: 'popup' as const, minutes: 10 } // 10 minutes before
        ]
      }
    };

    const result = await invoke('google_calendar_create_event', {
      userId: context.userId,
      ...eventData
    });
    return result as { success: boolean; eventId?: string; error?: string };
  }

  private async updateEvent(action: GoogleCalendarUpdateAction, context: SkillContext): Promise<{ success: boolean; eventId?: string; error?: string }> {
    const eventData = {
      calendarId: action.params.calendarId || 'primary',
      eventId: action.params.eventId,
      summary: action.params.summary,
      description: action.params.description,
      location: action.params.location,
      attendees: action.params.attendees?.map(email => ({ email })),
      visibility: action.params.visibility,
      transparency: action.params.transparency
    };

    const result = await invoke('google_calendar_update_event', {
      userId: context.userId,
      ...eventData
    });
    return result as { success: boolean; eventId?: string; error?: string };
  }

  private async deleteEvent(action: GoogleCalendarDeleteAction, context: SkillContext): Promise<{ success: boolean; error?: string }> {
    const result = await invoke('google_calendar_delete_event', {
      userId: context.userId,
      calendarId: action.params.calendarId || 'primary',
      eventId: action.params.eventId,
      sendUpdates: action.params.sendUpdates || 'externalOnly'
    });
    return result as { success: boolean; error?: string };
  }
}

// Re-export calendar action types
export type {
  GoogleCalendarListAction,
  GoogleCalendarEventsAction,
  GoogleCalendarCreateAction,
  GoogleCalendarUpdateAction,
  GoogleCalendarDeleteAction
} from './googleGmailSkill';