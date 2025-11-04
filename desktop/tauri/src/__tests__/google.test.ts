// Test Suite for Google Workspace Skills
import { GmailSkill, GoogleCalendarSkill, GoogleDriveSkill } from '../src/skills/googleSkills';
import type { 
  GmailListAction,
  GmailSendAction,
  GmailSearchAction,
  GoogleCalendarListAction,
  GoogleCalendarCreateAction,
  GoogleCalendarEventsAction,
  GoogleDriveListAction,
  GoogleDriveCreateAction,
  GoogleDriveSearchAction
} from '../src/skills/googleSkills';

describe('Google Workspace Skills', () => {
  // Test context
  const mockContext = {
    userId: 'test-user-123',
    sessionId: 'test-session-456',
    environment: 'test'
  };

  describe('Gmail Skill', () => {
    const gmailSkill = new GmailSkill();

    it('should be properly initialized', () => {
      expect(gmailSkill.name).toBe('google_gmail');
      expect(gmailSkill.displayName).toBe('Gmail');
      expect(gmailSkill.icon).toBe('📧');
      expect(gmailSkill.category).toBe('productivity');
      expect(gmailSkill.supportedActions).toContain('list_emails');
      expect(gmailSkill.supportedActions).toContain('send_email');
      expect(gmailSkill.supportedActions).toContain('search_emails');
    });

    it('should list emails', async () => {
      const action: GmailListAction = {
        action: 'list_emails',
        params: {
          maxResults: 5,
          includeAttachments: true
        }
      };

      // Mock the Tauri invoke call
      const mockInvoke = jest.fn().mockResolvedValue([
        {
          id: 'msg123',
          threadId: 'thread123',
          from: 'sender@example.com',
          to: ['user@gmail.com'],
          subject: 'Test Email',
          body: 'This is a test email',
          timestamp: '2025-11-02T10:30:00Z',
          isRead: false,
          isImportant: true,
          isStarred: false,
          hasAttachments: true,
          labels: ['INBOX']
        }
      ]);

      global.__TAURI__ = {
        invoke: mockInvoke
      };

      const result = await gmailSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_gmail_list_emails', {
        userId: mockContext.userId,
        maxResults: 5,
        includeAttachments: true,
        includeSpam: undefined,
        includeTrash: undefined,
        query: undefined
      });
      expect(Array.isArray(result)).toBe(true);
      expect(result[0].subject).toBe('Test Email');
    });

    it('should send email', async () => {
      const action: GmailSendAction = {
        action: 'send_email',
        params: {
          to: ['recipient@example.com'],
          subject: 'Test Subject',
          body: 'Test email body'
        }
      };

      const mockResult = {
        success: true,
        messageId: 'msg-456'
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await gmailSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_gmail_send_email', {
        userId: mockContext.userId,
        to: ['recipient@example.com'],
        subject: 'Test Subject',
        body: 'Test email body',
        cc: undefined,
        bcc: undefined,
        htmlBody: undefined,
        attachments: undefined
      });
      expect(result.success).toBe(true);
      expect(result.messageId).toBe('msg-456');
    });

    it('should search emails', async () => {
      const action: GmailSearchAction = {
        action: 'search_emails',
        params: {
          query: 'meeting',
          maxResults: 10
        }
      };

      const mockResult = {
        emails: [
          {
            id: 'msg123',
            subject: 'Meeting Tomorrow',
            snippet: 'Reminder about meeting'
          }
        ],
        totalResults: 1
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await gmailSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_gmail_search_emails', {
        userId: mockContext.userId,
        query: 'meeting',
        maxResults: 10,
        pageToken: undefined
      });
      expect(result.emails).toBeDefined();
      expect(result.totalResults).toBe(1);
    });

    it('should handle invalid email format', async () => {
      const action: GmailSendAction = {
        action: 'send_email',
        params: {
          to: ['invalid-email'],
          subject: 'Test',
          body: 'Test body'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Invalid email address: invalid-email'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(gmailSkill.execute(action, mockContext)).rejects.toThrow('Gmail skill execution failed');
    });
  });

  describe('Google Calendar Skill', () => {
    const calendarSkill = new GoogleCalendarSkill();

    it('should be properly initialized', () => {
      expect(calendarSkill.name).toBe('google_calendar');
      expect(calendarSkill.displayName).toBe('Google Calendar');
      expect(calendarSkill.icon).toBe('📅');
      expect(calendarSkill.category).toBe('productivity');
      expect(calendarSkill.supportedActions).toContain('list_calendars');
      expect(calendarSkill.supportedActions).toContain('create_event');
    });

    it('should list calendars', async () => {
      const action: GoogleCalendarListAction = {
        action: 'list_calendars',
        params: {}
      };

      const mockResult = {
        calendars: [
          {
            id: 'cal123',
            summary: 'Personal',
            primary: true,
            accessRole: 'owner'
          }
        ]
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await calendarSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_calendar_list_calendars', {
        userId: mockContext.userId
      });
      expect(result.calendars).toBeDefined();
      expect(result.calendars[0].summary).toBe('Personal');
    });

    it('should create calendar event', async () => {
      const action: GoogleCalendarCreateAction = {
        action: 'create_event',
        params: {
          summary: 'Team Meeting',
          startTime: '2025-11-03T14:00:00Z',
          endTime: '2025-11-03T15:00:00Z',
          description: 'Weekly team sync',
          location: 'Conference Room A'
        }
      };

      const mockResult = {
        success: true,
        eventId: 'evt-123'
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await calendarSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_calendar_create_event', {
        userId: mockContext.userId,
        calendarId: 'primary',
        summary: 'Team Meeting',
        startTime: '2025-11-03T14:00:00Z',
        endTime: '2025-11-03T15:00:00Z',
        description: 'Weekly team sync',
        location: 'Conference Room A',
        allDay: false,
        attendees: ['user@example.com'], // This should match the implementation
        visibility: 'default',
        transparency: 'opaque'
      });
      expect(result.success).toBe(true);
      expect(result.eventId).toBe('evt-123');
    });

    it('should list events', async () => {
      const action: GoogleCalendarEventsAction = {
        action: 'list_events',
        params: {
          timeMin: '2025-11-01T00:00:00Z',
          timeMax: '2025-11-07T23:59:59Z',
          maxResults: 10
        }
      };

      const mockResult = {
        events: [
          {
            id: 'evt123',
            summary: 'Team Meeting',
            startTime: '2025-11-03T14:00:00Z',
            endTime: '2025-11-03T15:00:00Z'
          }
        ]
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await calendarSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_calendar_list_events', {
        userId: mockContext.userId,
        calendarId: undefined,
        timeMin: '2025-11-01T00:00:00Z',
        timeMax: '2025-11-07T23:59:59Z',
        q: undefined,
        maxResults: 10,
        singleEvents: true,
        orderBy: 'startTime'
      });
      expect(result.events).toBeDefined();
      expect(result.events[0].summary).toBe('Team Meeting');
    });

    it('should validate event creation parameters', async () => {
      const action: GoogleCalendarCreateAction = {
        action: 'create_event',
        params: {
          summary: '', // Empty summary should fail validation
          startTime: '2025-11-03T14:00:00Z',
          endTime: '2025-11-03T15:00:00Z'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Event summary is required'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(calendarSkill.execute(action, mockContext)).rejects.toThrow('Google Calendar skill execution failed');
    });
  });

  describe('Google Drive Skill', () => {
    const driveSkill = new GoogleDriveSkill();

    it('should be properly initialized', () => {
      expect(driveSkill.name).toBe('google_drive');
      expect(driveSkill.displayName).toBe('Google Drive');
      expect(driveSkill.icon).toBe('📁');
      expect(driveSkill.category).toBe('productivity');
      expect(driveSkill.supportedActions).toContain('list_files');
      expect(driveSkill.supportedActions).toContain('create_file');
    });

    it('should list files', async () => {
      const action: GoogleDriveListAction = {
        action: 'list_files',
        params: {
          pageSize: 10,
          orderBy: 'modifiedTime desc'
        }
      };

      const mockResult = {
        files: [
          {
            id: 'file123',
            name: 'Document.pdf',
            mimeType: 'application/pdf',
            size: '1048576',
            createdTime: '2025-10-28T10:00:00Z',
            modifiedTime: '2025-11-01T15:30:00Z',
            webViewLink: 'https://docs.google.com/file/d/file123'
          }
        ]
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await driveSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_drive_list_files', {
        userId: mockContext.userId,
        pageSize: 10,
        orderBy: 'modifiedTime desc',
        pageToken: undefined,
        q: undefined,
        spaces: 'drive'
      });
      expect(result.files).toBeDefined();
      expect(result.files[0].name).toBe('Document.pdf');
    });

    it('should create file', async () => {
      const action: GoogleDriveCreateAction = {
        action: 'create_file',
        params: {
          name: 'Test Document.txt',
          content: 'This is test content',
          mimeType: 'text/plain'
        }
      };

      const mockResult = {
        success: true,
        id: 'file-456',
        name: 'Test Document.txt',
        mimeType: 'text/plain'
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await driveSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_drive_create_file', {
        userId: mockContext.userId,
        name: 'Test Document.txt',
        content: 'This is test content',
        mimeType: 'text/plain',
        parents: []
      });
      expect(result.success).toBe(true);
      expect(result.name).toBe('Test Document.txt');
    });

    it('should search files', async () => {
      const action: GoogleDriveSearchAction = {
        action: 'search_files',
        params: {
          q: 'presentation',
          pageSize: 20
        }
      };

      const mockResult = {
        files: [
          {
            id: 'file789',
            name: 'Sales Presentation.pptx',
            mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            size: '2097152'
          }
        ],
        totalResults: 1
      };

      const mockInvoke = jest.fn().mockResolvedValue(mockResult);
      global.__TAURI__ = { invoke: mockInvoke };

      const result = await driveSkill.execute(action, mockContext);
      
      expect(mockInvoke).toHaveBeenCalledWith('google_drive_search_files', {
        userId: mockContext.userId,
        q: 'presentation',
        pageSize: 20,
        orderBy: undefined,
        pageToken: undefined,
        spaces: 'drive'
      });
      expect(result.files).toBeDefined();
      expect(result.totalResults).toBe(1);
      expect(result.files[0].name).toBe('Sales Presentation.pptx');
    });

    it('should validate file creation parameters', async () => {
      const action: GoogleDriveCreateAction = {
        action: 'create_file',
        params: {
          name: '', // Empty name should fail validation
          content: 'test'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('File name is required'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(driveSkill.execute(action, mockContext)).rejects.toThrow('Google Drive skill execution failed');
    });

    it('should validate search parameters', async () => {
      const action: GoogleDriveSearchAction = {
        action: 'search_files',
        params: {
          q: '', // Empty query should fail validation
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Search query is required'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(driveSkill.execute(action, mockContext)).rejects.toThrow('Google Drive skill execution failed');
    });
  });

  describe('Google Skills Integration', () => {
    it('should work together for cross-service operations', async () => {
      // Test scenario: Find meeting attachment in email and save to Drive
      const gmailSkill = new GmailSkill();
      const driveSkill = new GoogleDriveSkill();

      // Mock Gmail search for meeting
      const mockGmailResult = {
        emails: [
          {
            id: 'msg123',
            subject: 'Meeting Tomorrow',
            attachments: [
              {
                id: 'att123',
                filename: 'agenda.pdf',
                content: 'mock PDF content'
              }
            ]
          }
        ]
      };

      // Mock Drive create
      const mockDriveResult = {
        success: true,
        id: 'file-456',
        name: 'agenda.pdf'
      };

      const mockInvoke = jest.fn()
        .mockResolvedValueOnce(mockGmailResult) // Gmail search
        .mockResolvedValueOnce(mockDriveResult); // Drive create

      global.__TAURI__ = { invoke: mockInvoke };

      // Search for meeting email
      const searchAction: GmailSearchAction = {
        action: 'search_emails',
        params: { query: 'meeting' }
      };

      const gmailResult = await gmailSkill.execute(searchAction, mockContext);
      
      expect(gmailResult.emails).toBeDefined();
      expect(gmailResult.emails[0].attachments).toBeDefined();

      // Save attachment to Drive
      const createAction: GoogleDriveCreateAction = {
        action: 'create_file',
        params: {
          name: 'agenda.pdf',
          content: 'mock PDF content'
        }
      };

      const driveResult = await driveSkill.execute(createAction, mockContext);
      
      expect(driveResult.success).toBe(true);
      expect(driveResult.name).toBe('agenda.pdf');
    });
  });

  describe('Error Handling', () => {
    it('should handle unknown Gmail actions gracefully', async () => {
      const gmailSkill = new GmailSkill();
      const invalidAction = {
        action: 'unknown_gmail_action',
        params: {}
      } as any;

      await expect(gmailSkill.execute(invalidAction, mockContext))
        .rejects.toThrow('Unknown Gmail action: unknown_gmail_action');
    });

    it('should handle unknown Calendar actions gracefully', async () => {
      const calendarSkill = new GoogleCalendarSkill();
      const invalidAction = {
        action: 'unknown_calendar_action',
        params: {}
      } as any;

      await expect(calendarSkill.execute(invalidAction, mockContext))
        .rejects.toThrow('Unknown Google Calendar action: unknown_calendar_action');
    });

    it('should handle unknown Drive actions gracefully', async () => {
      const driveSkill = new GoogleDriveSkill();
      const invalidAction = {
        action: 'unknown_drive_action',
        params: {}
      } as any;

      await expect(driveSkill.execute(invalidAction, mockContext))
        .rejects.toThrow('Unknown Google Drive action: unknown_drive_action');
    });

    it('should handle Tauri invoke errors', async () => {
      const gmailSkill = new GmailSkill();
      const action: GmailListAction = {
        action: 'list_emails',
        params: {}
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Tauri invoke error'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(gmailSkill.execute(action, mockContext))
        .rejects.toThrow('Gmail skill execution failed');
    });
  });

  describe('Data Validation', () => {
    it('should validate Gmail action parameters', async () => {
      const gmailSkill = new GmailSkill();
      
      // Test email validation
      const sendAction: GmailSendAction = {
        action: 'send_email',
        params: {
          to: [], // Empty to list should fail
          subject: 'Test',
          body: 'Test body'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('At least one recipient is required'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(gmailSkill.execute(sendAction, mockContext))
        .rejects.toThrow('Gmail skill execution failed');
    });

    it('should validate Calendar action parameters', async () => {
      const calendarSkill = new GoogleCalendarSkill();
      
      // Test event time validation
      const createAction: GoogleCalendarCreateAction = {
        action: 'create_event',
        params: {
          summary: 'Test Event',
          startTime: '2025-11-03', // Invalid time format
          endTime: '2025-11-03'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('Invalid start time format'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(calendarSkill.execute(createAction, mockContext))
        .rejects.toThrow('Google Calendar skill execution failed');
    });

    it('should validate Drive action parameters', async () => {
      const driveSkill = new GoogleDriveSkill();
      
      // Test file name validation
      const createAction: GoogleDriveCreateAction = {
        action: 'create_file',
        params: {
          name: '<invalidfilename>', // Invalid characters
          content: 'test'
        }
      };

      const mockInvoke = jest.fn().mockRejectedValue(new Error('File name contains invalid characters'));
      global.__TAURI__ = { invoke: mockInvoke };

      await expect(driveSkill.execute(createAction, mockContext))
        .rejects.toThrow('Google Drive skill execution failed');
    });
  });
});