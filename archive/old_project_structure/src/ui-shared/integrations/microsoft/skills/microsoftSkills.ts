import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * Microsoft Suite Enhanced Skills
 * Complete Microsoft ecosystem integration: Outlook, Calendar, OneDrive, Teams, SharePoint
 */

// Outlook Skills
export class MicrosoftSendEmailSkill implements Skill {
  id = 'microsoft_send_email';
  name = 'Send Outlook Email';
  description = 'Send an email via Microsoft Outlook';
  category = 'communication';
  examples = [
    'Send Outlook email to team@company.com about project update',
    'Email john@example.com with the meeting notes via Outlook',
    'Send Microsoft email to sarah with the quarterly report'
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

      // Call Microsoft Outlook API
      const response = await fetch('/api/integrations/microsoft/outlook/messages', {
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
          message: `Outlook email sent successfully to ${recipient}`,
          data: {
            message: result.data.message,
            id: result.data.id,
            web_link: result.data.web_link,
            recipient: recipient,
            subject: subject
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Outlook',
              url: result.data.web_link
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to send Outlook email: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error sending Outlook email: ${error}`,
        error: error as any
      };
    }
  }

  private extractRecipient(intent: string): string | null {
    const patterns = [
      /send (?:outlook|email|microsoft email) to (.+?)(?: about|with|:|$)/i,
      /email (.+?)(?: about|with|:|$)/i,
      /send (.+?)(?: an| a) (?:outlook|microsoft) email(?: about|with|:|$)/i,
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

export class MicrosoftSearchEmailsSkill implements Skill {
  id = 'microsoft_search_emails';
  name = 'Search Outlook';
  description = 'Search emails in Microsoft Outlook';
  category = 'communication';
  examples = [
    'Search Outlook for messages from boss',
    'Find Outlook emails about project deadline',
    'Search Microsoft inbox for urgent messages'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const top = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Microsoft Outlook API
      const response = await fetch('/api/integrations/microsoft/outlook/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          query: query,
          top: top,
          select: 'id,subject,from,toRecipients,bodyPreview,receivedDateTime,hasAttachments,isRead,importance'
        })
      });

      const result = await response.json();

      if (result.ok) {
        const messages = result.data.messages || [];
        const messageCount = messages.length;

        return {
          success: true,
          message: `Found ${messageCount} Outlook email${messageCount !== 1 ? 's' : ''} matching "${query}"`,
          data: {
            messages: messages,
            total_count: result.data.total_count,
            query: query
          },
          actions: messages.map((msg: any) => ({
            type: 'open_url',
            label: `Open ${msg.subject}`,
            url: msg.web_link
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search Outlook emails: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching Outlook emails: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:outlook|microsoft|emails?) for (.+)/i,
      /find (?:outlook|microsoft )?emails? about (.+)/i,
      /search (?:outlook|microsoft )?inbox for (.+)/i,
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
export class MicrosoftCreateEventSkill implements Skill {
  id = 'microsoft_create_event';
  name = 'Create Calendar Event';
  description = 'Create an event in Microsoft Calendar';
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

      // Call Microsoft Calendar API
      const response = await fetch('/api/integrations/microsoft/calendar/events', {
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
            body: description,
            attendees: this.extractAttendees(intent),
            importance: 'normal',
            showAs: 'busy'
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
            web_link: result.data.web_link,
            id: result.data.event?.id,
            summary: summary
          },
          actions: [
            {
              type: 'open_url',
              label: 'View in Calendar',
              url: result.data.web_link
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create calendar event: ${result.error?.message || 'Unknown error'}`,
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

export class MicrosoftSearchEventsSkill implements Skill {
  id = 'microsoft_search_events';
  name = 'Search Calendar';
  description = 'Search events in Microsoft Calendar';
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
      
      const startDateTime = this.extractTimeRange(intent, 'start');
      const endDateTime = this.extractTimeRange(intent, 'end');
      const top = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Microsoft Calendar API
      const response = await fetch('/api/integrations/microsoft/calendar/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          q: query,
          start_datetime: startDateTime,
          end_datetime: endDateTime,
          top: top,
          select: 'id,subject,start,end,location,bodyPreview,attendees,importance,showAs'
        })
      });

      const result = await response.json();

      if (result.ok) {
        const events = result.data.events || [];
        const eventCount = events.length;

        return {
          success: true,
          message: `Found ${eventCount} calendar event${eventCount !== 1 ? 's' : ''}${query ? ` matching "${query}"` : ''}`,
          data: {
            events: events,
            total_count: result.data.total_count,
            query: query,
            time_range: { start: startDateTime, end: endDateTime }
          },
          actions: events.map((event: any) => ({
            type: 'open_url',
            label: `View ${event.subject}`,
            url: event.web_link
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search calendar events: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching calendar events: ${error}`,
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

// OneDrive Skills
export class MicrosoftCreateDocumentSkill implements Skill {
  id = 'microsoft_create_document';
  name = 'Create OneDrive Document';
  description = 'Create a new document in OneDrive';
  category = 'productivity';
  examples = [
    'Create OneDrive document for meeting notes',
    'Make new document called Project Proposal',
    'Create document for quarterly report in OneDrive'
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

      // Call Microsoft OneDrive API to create document
      const response = await fetch('/api/integrations/microsoft/onedrive/files', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: name,
            content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            parents: folder ? [folder] : []
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `OneDrive document "${name}" created successfully`,
          data: {
            file: result.data.file,
            web_url: result.data.web_url,
            id: result.data.file?.id,
            name: name
          },
          actions: [
            {
              type: 'open_url',
              label: 'Open Document',
              url: result.data.web_url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create OneDrive document: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating OneDrive document: ${error}`,
        error: error as any
      };
    }
  }

  private extractDocumentName(intent: string): string | null {
    const patterns = [
      /create (?:onedrive )?document (?:called|for) (.+?)(?: with|:|$)/i,
      /make new document (.+?)(?: for|with|:|$)/i,
      /document (.+?)(?: for|with|:|$)/i,
      /onedrive document (.+?)(?: for|with|:|$)/i
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

export class MicrosoftSearchOneDriveSkill implements Skill {
  id = 'microsoft_search_onedrive';
  name = 'Search OneDrive';
  description = 'Search files in OneDrive';
  category = 'productivity';
  examples = [
    'Search OneDrive for quarterly report',
    'Find files about project proposal',
    'Look for presentation slides in OneDrive'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                  entities.find((e: any) => e.type === 'query')?.value ||
                  intent;
      
      const mimeType = this.extractMimeType(intent);
      const top = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Call Microsoft OneDrive API
      const response = await fetch('/api/integrations/microsoft/onedrive/files', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'list',
          q: query + (mimeType ? ` and file_type='${mimeType}'` : ''),
          top: top,
          select: 'id,name,size,lastModifiedDateTime,parentReference,webUrl,file,folder',
          order_by: 'lastModifiedDateTime desc'
        })
      });

      const result = await response.json();

      if (result.ok) {
        const files = result.data.files || [];
        const fileCount = files.length;

        return {
          success: true,
          message: `Found ${fileCount} file${fileCount !== 1 ? 's' : ''} matching "${query}" in OneDrive`,
          data: {
            files: files,
            total_count: result.data.total_count,
            query: query,
            mime_type: mimeType
          },
          actions: files.map((file: any) => ({
            type: 'open_url',
            label: `Open ${file.name}`,
            url: file.web_url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search OneDrive: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching OneDrive: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:onedrive|microsoft onedrive) for (.+)/i,
      /find files? about (.+)/i,
      /look for (.+?) in (?:microsoft )?onedrive/i,
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
      'document': 'docx',
      'doc': 'docx',
      'spreadsheet': 'xlsx',
      'sheet': 'xlsx',
      'presentation': 'pptx',
      'slides': 'pptx',
      'folder': 'folder',
      'pdf': 'pdf',
      'image': 'jpg',
      'video': 'mp4'
    };

    for (const [key, mimeType] of Object.entries(mimeTypes)) {
      if (intent.toLowerCase().includes(key)) {
        return mimeType;
      }
    }

    return null;
  }
}

// Teams Skills
export class MicrosoftSendTeamsMessageSkill implements Skill {
  id = 'microsoft_send_teams_message';
  name = 'Send Teams Message';
  description = 'Send a message in Microsoft Teams';
  category = 'communication';
  examples = [
    'Send Teams message to development channel about deployment',
    'Message the project team about the upcoming deadline',
    'Send Microsoft Teams message to general channel'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract channel and message
      const channel = this.extractChannel(intent) ||
                     entities.find((e: any) => e.type === 'channel')?.value;
      
      const content = this.extractContent(intent) ||
                      entities.find((e: any) => e.type === 'content')?.value ||
                      intent;
      
      if (!channel) {
        return {
          success: false,
          message: 'Teams channel is required',
          error: 'Missing channel'
        };
      }

      // Call Microsoft Teams API
      const response = await fetch('/api/integrations/microsoft/teams/channels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'send_message',
          channel_id: channel,
          data: {
            content: content
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `Teams message sent successfully to ${channel}`,
          data: {
            message: result.data.message,
            id: result.data.id,
            channel_id: channel,
            content: content
          }
        };
      } else {
        return {
          success: false,
          message: `Failed to send Teams message: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error sending Teams message: ${error}`,
        error: error as any
      };
    }
  }

  private extractChannel(intent: string): string | null {
    const patterns = [
      /send (?:teams|microsoft teams) message to (.+?)(?: about|with|:|$)/i,
      /message (.+?)(?: about|with|:|$)/i,
      /teams message to (.+?)(?: about|with|:|$)/i,
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

  private extractContent(intent: string): string {
    const patterns = [
      /(?:about|with) (.+?)(?: in|:|$)/i,
      /message:? (.+)/i,
      /content:? (.+)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return intent;
  }
}

// Export all Microsoft skills
export const MICROSOFT_SKILLS = [
  new MicrosoftSendEmailSkill(),
  new MicrosoftSearchEmailsSkill(),
  new MicrosoftCreateEventSkill(),
  new MicrosoftSearchEventsSkill(),
  new MicrosoftCreateDocumentSkill(),
  new MicrosoftSearchOneDriveSkill(),
  new MicrosoftSendTeamsMessageSkill()
];

// Export skills registry
export const MICROSOFT_SKILLS_REGISTRY = {
  'microsoft_send_email': MicrosoftSendEmailSkill,
  'microsoft_search_emails': MicrosoftSearchEmailsSkill,
  'microsoft_create_event': MicrosoftCreateEventSkill,
  'microsoft_search_events': MicrosoftSearchEventsSkill,
  'microsoft_create_document': MicrosoftCreateDocumentSkill,
  'microsoft_search_onedrive': MicrosoftSearchOneDriveSkill,
  'microsoft_send_teams_message': MicrosoftSendTeamsMessageSkill
};