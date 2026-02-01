import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Google Suite Enhanced Skills
 * Complete Google ecosystem integration: Gmail, Calendar, Drive, Docs, Sheets, Slides
 */

// Gmail Skills
export class GoogleSendEmailSkill implements Skill {
  id = 'google_send_email';
  name = 'Send Gmail';
  description = 'Send an email via Gmail';
  category = 'communication';
  examples = [
    'Send email to team@company.com about project update',
    'Email john@example.com with the meeting notes',
    'Send Gmail to sarah with the quarterly report'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract recipient and subject
      const recipient = this.extractRecipient(intent) ||
                       entities.find((e: any) => e.type === 'email')?.value;
      
      const subject = this.extractSubject(intent) ||
                     entities.find((e: any) => e.type === 'subject')?.value ||
                     'Message from ATOM Platform';
      
      const body = this.extractBody(intent) ||
                   entities.find((e: any) => e.type === 'body')?.value ||
                   intent;
      
      if (!recipient) {
        return {
          success: false,
          message: 'Email recipient is required',
          error: 'Missing recipient'
        };
      }

      // Call Google Gmail API
      const response = await fetch('/api/integrations/google/gmail/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'send',
          data: {
            to: recipient,
            subject: subject,
            body: body,
            cc: this.extractCC(intent),
            bcc: this.extractBCC(intent),
            attachments: []
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Email sent successfully to ${recipient}`,
          data: {
            message: result.data.message,
            id: result.data.id,
            thread_id: result.data.thread_id,
            url: result.data.url,
            recipient: recipient,
            subject: subject
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Gmail',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to send email: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error sending email: ${error}`,
        error: error as any
      };
    }
  }

  private extractRecipient(intent: string): string | null {
    const patterns = [
      /send (?:email|gmail) to (.+?)(?: about|with|:|$)/i,
      /email (.+?)(?: about|with|:|$)/i,
      /send (.+?)(?: an email| a gmail)(?: about|with|:|$)/i,
      /to (.+?)(?: send|about|with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractSubject(intent: string): string | null {
    const patterns = [
      /about (.+?)(?: with|:|$)/i,
      /subject(?:[:])? (.+?)(?: with|:|$)/i,
      /regarding (.+?)(?: with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractBody(intent: string): string {
    // The body is typically the entire intent after extracting recipient and subject
    return intent;
  }

  private extractCC(intent: string): string[] {
    // Extract CC recipients
    const ccMatch = intent.match(/cc:? (.+?)(?: to|bcc|:|$)/i);
    return ccMatch ? ccMatch[1].split(',').map((e: string) => e.trim()) : [];
  }

  private extractBCC(intent: string): string[] {
    // Extract BCC recipients
    const bccMatch = intent.match(/bcc:? (.+?)(?: to|cc|:|$)/i);
    return bccMatch ? bccMatch[1].split(',').map((e: string) => e.trim()) : [];
  }
}

export class GoogleSearchEmailsSkill implements Skill {
  id = 'google_search_emails';
  name = 'Search Gmail';
  description = 'Search emails in Gmail';
  category = 'communication';
  examples = [
    'Search Gmail for messages from boss',
    'Find emails about project deadline',
    'Search Gmail inbox for urgent messages'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const maxResults = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Google Gmail API
      const response = await fetch('/api/integrations/google/gmail/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          query: query,
          max_results: maxResults,
          label_ids: ['INBOX']
        })
      });

      const result = await response.json();

      if (result.ok) {
        const messages = result.data.messages || [];
        const messageCount = messages.length;

        return {
          success: true,
          message: `Found ${messageCount} email${messageCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            messages: messages,
            total_count: result.data.total_count,
            query: query
          },
          actions: messages.map((msg: any) => ({
            type: 'open_url',
            label: `Open ${msg.subject}`,
            url: msg.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search emails: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching emails: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:gmail|emails?) for (.+)/i,
      /find emails? about (.+)/i,
      /search (?:gmail|inbox) for (.+)/i,
      /emails? about (.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// Calendar Skills
export class GoogleCreateEventSkill implements Skill {
  id = 'google_create_event';
  name = 'Create Calendar Event';
  description = 'Create an event in Google Calendar';
  category = 'scheduling';
  examples = [
    'Create calendar event for team meeting tomorrow at 2pm',
    'Schedule meeting with John next Monday at 10am',
    'Add calendar event for project deadline due next Friday'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract event details
      const summary = this.extractSummary(intent) ||
                     entities.find((e: any) => e.type === 'title')?.value ||
                     'New Event';
      
      const startDateTime = this.extractDateTime(intent, 'start') ||
                          entities.find((e: any) => e.type === 'start_time')?.value;
      
      const endDateTime = this.extractDateTime(intent, 'end') ||
                        entities.find((e: any) => e.type === 'end_time')?.value;
      
      const location = this.extractLocation(intent) ||
                      entities.find((e: any) => e.type === 'location')?.value;
      
      const description = this.extractDescription(intent) ||
                        entities.find((e: any) => e.type === 'description')?.value;

      if (!summary) {
        return {
          success: false,
          message: 'Event title is required',
          error: 'Missing event title'
        };
      }

      // Call Google Calendar API
      const response = await fetch('/api/integrations/google/calendar/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            summary: summary,
            start: this.formatDateTime(startDateTime),
            end: this.formatDateTime(endDateTime || startDateTime),
            location: location,
            description: description,
            attendees: this.extractAttendees(intent)
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Calendar event "${summary}" created successfully`,
          data: {
            event: result.data.event,
            url: result.data.url,
            id: result.data.event?.id,
            summary: summary
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Calendar',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create event: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating calendar event: ${error}`,
        error: error as any
      };
    }
  }

  private extractSummary(intent: string): string | null {
    const patterns = [
      /create (?:calendar )?event for (.+?)(?: tomorrow|next|at|on|:|$)/i,
      /schedule (?:meeting|event) (.+?)(?: tomorrow|next|at|on|:|$)/i,
      /add calendar event (.+?)(?: due|tomorrow|next|at|on|:|$)/i,
      /(?:meeting|event) (.+?)(?: tomorrow|next|at|on|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDateTime(intent: string, type: 'start' | 'end'): Date | null {
    // This is a simplified implementation - in production, use a proper date parsing library
    const patterns = type === 'start' ? [
      /tomorrow at (\d{1,2})(?::(\d{2}))?\s*(am|pm)/i,
      /next (\w+) at (\d{1,2})(?::(\d{2}))?\s*(am|pm)/i,
      /at (\d{1,2})(?::(\d{2}))?\s*(am|pm) (?:tomorrow|next \w+)/i,
      /(\d{1,2})(?::(\d{2}))?\s*(am|pm) (?:tomorrow|next \w+)/i
    ] : [
      /(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?=\s*(?:to|-|–))/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        // Simple date parsing - should use proper date library in production
        const date = new Date();
        return date;
      }
    }

    return null;
  }

  private extractLocation(intent: string): string | null {
    const patterns = [
      /(?:in|at) (.+?)(?: at|on|:|$)/i,
      /location:? (.+?)(?: at|on|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:about|for) (.+?)(?: at|in|:|$)/i,
      /description:? (.+?)(?: at|in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractAttendees(intent: string): Array<{email: string, displayName?: string}> {
    const patterns = [
      /with (.+?)(?: at|on|tomorrow|next|:|$)/i,
      /invite (.+?)(?: to|at|on|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        const attendeeText = match[1].trim();
        // Simple extraction - should parse emails properly in production
        return attendeeText.split(',').map((name: string) => ({
          email: `${name.toLowerCase().replace(/\s+/g, '.')}@example.com`,
          displayName: name.trim()
        }));
      }
    }

    return [];
  }

  private formatDateTime(date: Date | null): any {
    if (!date) {
      // Default to 1 hour from now
      const defaultDate = new Date();
      defaultDate.setHours(defaultDate.getHours() + 1);
      date = defaultDate;
    }

    return {
      dateTime: date.toISOString(),
      timeZone: 'UTC'
    };
  }
}

export class GoogleSearchEventsSkill implements Skill {
  id = 'google_search_events';
  name = 'Search Calendar';
  description = 'Search events in Google Calendar';
  category = 'scheduling';
  examples = [
    'Search calendar for meetings tomorrow',
    'Find events about project review',
    'Show my calendar for next week'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value;
      
      const timeMin = this.extractTimeRange(intent, 'start');
      const timeMax = this.extractTimeRange(intent, 'end');
      const maxResults = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Google Calendar API
      const response = await fetch('/api/integrations/google/calendar/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          q: query,
          time_min: timeMin,
          time_max: timeMax,
          max_results: maxResults
        })
      });

      const result = await response.json();

      if (result.ok) {
        const events = result.data.events || [];
        const eventCount = events.length;

        return {
          success: true,
          message: `Found ${eventCount} event${eventCount !== 1 ? 's' : ''}${query ? ` matching "${query}"` : ''}`,
          data: {
            events: events,
            total_count: result.data.total_count,
            query: query,
            time_range: { start: timeMin, end: timeMax }
          },
          actions: events.map((event: any) => ({
            type: 'open_url',
            label: `View ${event.summary}`,
            url: event.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search events: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching events: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:calendar|events?) for (.+)/i,
      /find events? about (.+)/i,
      /show (?:my )?calendar for (.+)/i,
      /events? about (.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractTimeRange(intent: string, type: 'start' | 'end'): string | null {
    // Simplified time range extraction - should use proper date parsing
    if (type === 'start') {
      if (intent.includes('tomorrow')) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(0, 0, 0, 0);
        return tomorrow.toISOString();
      }
      if (intent.includes('next week')) {
        const nextWeek = new Date();
        nextWeek.setDate(nextWeek.getDate() + 7);
        nextWeek.setHours(0, 0, 0, 0);
        return nextWeek.toISOString();
      }
    }

    return null;
  }
}

// Drive Skills
export class GoogleCreateDocumentSkill implements Skill {
  id = 'google_create_document';
  name = 'Create Document';
  description = 'Create a new Google Doc';
  category = 'productivity';
  examples = [
    'Create Google Doc for meeting notes',
    'Make new document called Project Proposal',
    'Create document for quarterly report'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract document name
      const name = this.extractDocumentName(intent) ||
                 entities.find((e: any) => e.type === 'document_name')?.value ||
                 'New Document';
      
      const content = this.extractContent(intent) ||
                     entities.find((e: any) => e.type === 'content')?.value ||
                     '';
      
      const folder = entities.find((e: any) => e.type === 'folder')?.value;

      // Call Google Drive API to create document
      const response = await fetch('/api/integrations/google/drive/files', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: name,
            mimeType: 'application/vnd.google-apps.document',
            parents: folder ? [folder] : [],
            content: content
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Google Doc "${name}" created successfully`,
          data: {
            file: result.data.file,
            url: result.data.url,
            id: result.data.file?.id,
            name: name
          },
          actions: [
            {
              type: 'open_url',
              label: 'Open Document',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create document: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating document: ${error}`,
        error: error as any
      };
    }
  }

  private extractDocumentName(intent: string): string | null {
    const patterns = [
      /create (?:google )?doc(?:ument)? (?:called|for) (.+?)(?: with|:|$)/i,
      /make new document (.+?)(?: for|with|:|$)/i,
      /document (.+?)(?: for|with|:|$)/i,
      /google doc (.+?)(?: for|with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractContent(intent: string): string | null {
    const patterns = [
      /(?:called|for) (.+?)(?: with|:|$)/i,
      /with content (.+)/i,
      /containing (.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

export class GoogleSearchDriveSkill implements Skill {
  id = 'google_search_drive';
  name = 'Search Drive';
  description = 'Search files in Google Drive';
  category = 'productivity';
  examples = [
    'Search Drive for quarterly report',
    'Find files about project proposal',
    'Look for presentation slides in Google Drive'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const mimeType = this.extractMimeType(intent);
      const maxResults = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Google Drive API
      const response = await fetch('/api/integrations/google/drive/files', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          q: query + (mimeType ? ` mimeType='${mimeType}'` : ''),
          page_size: maxResults,
          order_by: 'modifiedTime desc'
        })
      });

      const result = await response.json();

      if (result.ok) {
        const files = result.data.files || [];
        const fileCount = files.length;

        return {
          success: true,
          message: `Found ${fileCount} file${fileCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            files: files,
            total_count: result.data.total_count,
            query: query,
            mime_type: mimeType
          },
          actions: files.map((file: any) => ({
            type: 'open_url',
            label: `Open ${file.name}`,
            url: file.url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Drive: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Drive: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:drive|google drive) for (.+)/i,
      /find files? about (.+)/i,
      /look for (.+?) in google drive/i,
      /files? about (.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractMimeType(intent: string): string | null {
    const mimeTypes: { [key: string]: string } = {
      'document': 'application/vnd.google-apps.document',
      'doc': 'application/vnd.google-apps.document',
      'spreadsheet': 'application/vnd.google-apps.spreadsheet',
      'sheet': 'application/vnd.google-apps.spreadsheet',
      'presentation': 'application/vnd.google-apps.presentation',
      'slides': 'application/vnd.google-apps.presentation',
      'folder': 'application/vnd.google-apps.folder',
      'pdf': 'application/pdf',
      'image': 'image/',
      'video': 'video/'
    };

    for (const [key, mimeType] of Object.entries(mimeTypes)) {
      if (intent.toLowerCase().includes(key)) {
        return mimeType;
      }
    }

    return null;
  }
}

// Export all Google skills
export const GOOGLE_SKILLS = [
  new GoogleSendEmailSkill(),
  new GoogleSearchEmailsSkill(),
  new GoogleCreateEventSkill(),
  new GoogleSearchEventsSkill(),
  new GoogleCreateDocumentSkill(),
  new GoogleSearchDriveSkill()
];

// Export skills registry
export const GOOGLE_SKILLS_REGISTRY = {
  'google_send_email': GoogleSendEmailSkill,
  'google_search_emails': GoogleSearchEmailsSkill,
  'google_create_event': GoogleCreateEventSkill,
  'google_search_events': GoogleSearchEventsSkill,
  'google_create_document': GoogleCreateDocumentSkill,
  'google_search_drive': GoogleSearchDriveSkill
};