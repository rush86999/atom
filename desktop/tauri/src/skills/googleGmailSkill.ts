import { Skill, SkillAction, SkillContext } from '../../types/skillTypes';
import { invoke } from '@tauri-apps/api/tauri';

// Google API Types
export interface GoogleUser {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  verified: boolean;
}

export interface GoogleEmail {
  id: string;
  threadId: string;
  from: string;
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  body: string;
  htmlBody?: string;
  snippet: string;
  timestamp: string;
  isRead: boolean;
  isImportant: boolean;
  isStarred: boolean;
  hasAttachments: boolean;
  attachments?: GoogleEmailAttachment[];
  labels: string[];
}

export interface GoogleEmailAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  url?: string;
}

export interface GoogleCalendar {
  id: string;
  summary: string;
  description?: string;
  location?: string;
  color?: string;
  timezone?: string;
  primary: boolean;
  accessRole: string;
  selected: boolean;
}

export interface GoogleCalendarEvent {
  id: string;
  calendarId: string;
  summary: string;
  description?: string;
  location?: string;
  startTime: string;
  endTime: string;
  allDay: boolean;
  attendees?: GoogleEventAttendee[];
  organizer?: GoogleEventOrganizer;
  attachments?: GoogleEventAttachment[];
  recurrence?: string[];
  visibility?: string;
  transparency?: string;
  status: string;
  created: string;
  updated: string;
  htmlLink: string;
}

export interface GoogleEventAttendee {
  email: string;
  displayName?: string;
  responseStatus: 'accepted' | 'declined' | 'tentative' | 'needsAction';
  isSelf?: boolean;
  isOrganizer?: boolean;
  isOptional?: boolean;
}

export interface GoogleEventOrganizer {
  email: string;
  displayName?: string;
  isSelf?: boolean;
}

export interface GoogleEventAttachment {
  id: string;
  title: string;
  mimeType: string;
  iconLink?: string;
  fileUrl?: string;
}

export interface GoogleDriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  createdTime: string;
  modifiedTime: string;
  viewedByMeTime?: string;
  parents?: string[];
  webViewLink?: string;
  webContentLink?: string;
  iconLink: string;
  thumbnailLink?: string;
  ownedByMe: boolean;
  permissions?: GoogleDrivePermission[];
  spaces: string[];
  folderColorRgb?: string;
}

export interface GoogleDrivePermission {
  id: string;
  type: 'user' | 'group' | 'domain' | 'anyone';
  role: 'owner' | 'organizer' | 'fileOrganizer' | 'writer' | 'commenter' | 'reader';
  emailAddress?: string;
  domain?: string;
  displayName?: string;
}

export interface GoogleSearchResult {
  emails?: GoogleEmail[];
  calendarEvents?: GoogleCalendarEvent[];
  driveFiles?: GoogleDriveFile[];
  nextPageToken?: string;
  totalResults?: number;
}

// Gmail Skill Actions
export interface GmailListAction extends SkillAction {
  action: 'list_emails';
  params: {
    query?: string;
    maxResults?: number;
    includeAttachments?: boolean;
    includeSpam?: boolean;
    includeTrash?: boolean;
  };
}

export interface GmailSearchAction extends SkillAction {
  action: 'search_emails';
  params: {
    query: string;
    maxResults?: number;
    pageToken?: string;
  };
}

export interface GmailSendAction extends SkillAction {
  action: 'send_email';
  params: {
    to: string[];
    cc?: string[];
    bcc?: string[];
    subject: string;
    body: string;
    htmlBody?: string;
    attachments?: Array<{
      filename: string;
      content: string;
      mimeType?: string;
    }>;
  };
}

export interface GmailReadAction extends SkillAction {
  action: 'read_email';
  params: {
    emailId: string;
    threadId?: string;
    markAsRead?: boolean;
  };
}

export interface GmailMarkAction extends SkillAction {
  action: 'mark_email';
  params: {
    emailId: string;
    threadId?: string;
    action: 'read' | 'unread' | 'starred' | 'unstarred' | 'important' | 'unimportant';
  };
}

export interface GmailDeleteAction extends SkillAction {
  action: 'delete_email';
  params: {
    emailId: string;
    threadId?: string;
    permanently?: boolean;
  };
}

export interface GmailReplyAction extends SkillAction {
  action: 'reply_email';
  params: {
    emailId: string;
    threadId?: string;
    body: string;
    htmlBody?: string;
    toAll?: boolean;
    attachments?: Array<{
      filename: string;
      content: string;
      mimeType?: string;
    }>;
  };
}

// Google Calendar Skill Actions
export interface GoogleCalendarListAction extends SkillAction {
  action: 'list_calendars';
  params?: {};
}

export interface GoogleCalendarEventsAction extends SkillAction {
  action: 'list_events';
  params: {
    calendarId?: string;
    timeMin?: string;
    timeMax?: string;
    q?: string;
    maxResults?: number;
    singleEvents?: boolean;
    orderBy?: 'startTime' | 'updated';
  };
}

export interface GoogleCalendarCreateAction extends SkillAction {
  action: 'create_event';
  params: {
    calendarId?: string;
    summary: string;
    description?: string;
    location?: string;
    startTime: string;
    endTime: string;
    allDay?: boolean;
    attendees?: string[];
    visibility?: 'default' | 'public' | 'private' | 'confidential';
    transparency?: 'opaque' | 'transparent';
    reminder?: {
      method: 'email' | 'popup';
      minutes: number;
    }[];
  };
}

export interface GoogleCalendarUpdateAction extends SkillAction {
  action: 'update_event';
  params: {
    calendarId?: string;
    eventId: string;
    summary?: string;
    description?: string;
    location?: string;
    startTime?: string;
    endTime?: string;
    attendees?: string[];
    visibility?: 'default' | 'public' | 'private' | 'confidential';
    transparency?: 'opaque' | 'transparent';
  };
}

export interface GoogleCalendarDeleteAction extends SkillAction {
  action: 'delete_event';
  params: {
    calendarId?: string;
    eventId: string;
    sendUpdates?: 'all' | 'externalOnly' | 'none';
  };
}

// Google Drive Skill Actions
export interface GoogleDriveListAction extends SkillAction {
  action: 'list_files';
  params: {
    q?: string;
    pageSize?: number;
    orderBy?: 'createdTime' | 'folder' | 'modifiedByMeTime' | 'modifiedTime' | 'name' | 'name_natural' | 'quotaBytesUsed' | 'recency' | 'sharedWithMeTime' | 'starred' | 'viewedByMeTime';
    pageToken?: string;
    spaces?: 'drive' | 'appDataFolder' | 'photos';
  };
}

export interface GoogleDriveSearchAction extends SkillAction {
  action: 'search_files';
  params: {
    q: string;
    pageSize?: number;
    orderBy?: string;
    pageToken?: string;
    spaces?: 'drive' | 'appDataFolder' | 'photos';
  };
}

export interface GoogleDriveCreateAction extends SkillAction {
  action: 'create_file';
  params: {
    name: string;
    content?: string;
    mimeType?: string;
    parents?: string[];
  };
}

export interface GoogleDriveCreateFolderAction extends SkillAction {
  action: 'create_folder';
  params: {
    name: string;
    parents?: string[];
  };
}

export interface GoogleDriveDeleteAction extends SkillAction {
  action: 'delete_file';
  params: {
    fileId: string;
  };
}

export interface GoogleDriveShareAction extends SkillAction {
  action: 'share_file';
  params: {
    fileId: string;
    role: 'owner' | 'organizer' | 'fileOrganizer' | 'writer' | 'commenter' | 'reader';
    type: 'user' | 'group' | 'domain' | 'anyone';
    emailAddress?: string;
    domain?: string;
    sendNotificationEmail?: boolean;
  };
}

// Gmail Skill
export class GmailSkill implements Skill {
  name = 'google_gmail';
  displayName = 'Gmail';
  description = 'Manage Gmail emails, search, send, and organize messages';
  icon = '📧';
  category = 'productivity';
  supportedActions = [
    'list_emails',
    'search_emails',
    'send_email',
    'read_email',
    'mark_email',
    'reply_email',
    'delete_email'
  ];

  async execute(action: SkillAction, context: SkillContext): Promise<any> {
    try {
      switch (action.action) {
        case 'list_emails':
          return await this.listEmails(action as GmailListAction, context);
        case 'search_emails':
          return await this.searchEmails(action as GmailSearchAction, context);
        case 'send_email':
          return await this.sendEmail(action as GmailSendAction, context);
        case 'read_email':
          return await this.readEmail(action as GmailReadAction, context);
        case 'mark_email':
          return await this.markEmail(action as GmailMarkAction, context);
        case 'reply_email':
          return await this.replyEmail(action as GmailReplyAction, context);
        case 'delete_email':
          return await this.deleteEmail(action as GmailDeleteAction, context);
        default:
          throw new Error(`Unknown Gmail action: ${action.action}`);
      }
    } catch (error) {
      console.error('Gmail skill execution failed:', error);
      throw new Error(`Gmail skill execution failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async listEmails(action: GmailListAction, context: SkillContext): Promise<GoogleEmail[]> {
    const result = await invoke('google_gmail_list_emails', {
      userId: context.userId,
      ...action.params
    });
    return result as GoogleEmail[];
  }

  private async searchEmails(action: GmailSearchAction, context: SkillContext): Promise<GoogleSearchResult> {
    const result = await invoke('google_gmail_search_emails', {
      userId: context.userId,
      ...action.params
    });
    return result as GoogleSearchResult;
  }

  private async sendEmail(action: GmailSendAction, context: SkillContext): Promise<{ success: boolean; messageId?: string; error?: string }> {
    const result = await invoke('google_gmail_send_email', {
      userId: context.userId,
      ...action.params
    });
    return result as { success: boolean; messageId?: string; error?: string };
  }

  private async readEmail(action: GmailReadAction, context: SkillContext): Promise<GoogleEmail> {
    const result = await invoke('google_gmail_read_email', {
      userId: context.userId,
      ...action.params
    });
    return result as GoogleEmail;
  }

  private async markEmail(action: GmailMarkAction, context: SkillContext): Promise<{ success: boolean; error?: string }> {
    const result = await invoke('google_gmail_mark_email', {
      userId: context.userId,
      ...action.params
    });
    return result as { success: boolean; error?: string };
  }

  private async replyEmail(action: GmailReplyAction, context: SkillContext): Promise<{ success: boolean; messageId?: string; error?: string }> {
    const result = await invoke('google_gmail_reply_email', {
      userId: context.userId,
      ...action.params
    });
    return result as { success: boolean; messageId?: string; error?: string };
  }

  private async deleteEmail(action: GmailDeleteAction, context: SkillContext): Promise<{ success: boolean; error?: string }> {
    const result = await invoke('google_gmail_delete_email', {
      userId: context.userId,
      ...action.params
    });
    return result as { success: boolean; error?: string };
  }
}