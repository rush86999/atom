/**
 * Outlook Skills Testing Suite
 * Unit tests for all Outlook automation skills
 */

import { 
  outlookEmailSkill, 
  outlookCalendarSkill,
  OutlookEmailSkillParams,
  OutlookCalendarSkillParams 
} from '../skills/outlookSkills';
import { SkillExecutionContext } from '../types/skillTypes';

// Mock Tauri invoke function for testing
const mockInvoke = jest.fn();
jest.mock('@tauri-apps/api/tauri', () => ({
  invoke: mockInvoke
}));

describe('Outlook Email Skills', () => {
  let context: SkillExecutionContext;

  beforeEach(() => {
    jest.clearAllMocks();
    context = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: new Date().toISOString(),
      intent: 'outlook_send_email',
      entities: [],
      confidence: 0.9
    };
  });

  describe('sendEmail', () => {
    it('should send email successfully with valid parameters', async () => {
      mockInvoke.mockResolvedValue({ success: true, message: 'Email sent' });

      const params: OutlookEmailSkillParams = {
        action: 'send',
        to: ['test@example.com'],
        subject: 'Test Subject',
        body: 'Test Body'
      };

      const result = await outlookEmailSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.message).toContain('Email sent successfully');
      expect(mockInvoke).toHaveBeenCalledWith('send_outlook_email', {
        userId: 'test-user',
        to: ['test@example.com'],
        subject: 'Test Subject',
        body: 'Test Body',
        cc: undefined,
        bcc: undefined
      });
    });

    it('should fail with missing required parameters', async () => {
      const params: OutlookEmailSkillParams = {
        action: 'send',
        to: ['test@example.com'],
        subject: '',
        body: 'Test Body'
      };

      await expect(outlookEmailSkill.execute(params, context))
        .rejects.toThrow('To address, subject, and body are required');
    });

    it('should handle CC and BCC recipients', async () => {
      mockInvoke.mockResolvedValue({ success: true });

      const params: OutlookEmailSkillParams = {
        action: 'send',
        to: ['test@example.com'],
        cc: ['cc@example.com'],
        bcc: ['bcc@example.com'],
        subject: 'Test Subject',
        body: 'Test Body'
      };

      await outlookEmailSkill.execute(params, context);

      expect(mockInvoke).toHaveBeenCalledWith('send_outlook_email', {
        userId: 'test-user',
        to: ['test@example.com'],
        cc: ['cc@example.com'],
        bcc: ['bcc@example.com'],
        subject: 'Test Subject',
        body: 'Test Body'
      });
    });
  });

  describe('getEmails', () => {
    it('should retrieve emails with default limit', async () => {
      const mockEmails = [
        {
          id: '1',
          subject: 'Test Email',
          from: { name: 'Test', address: 'test@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Test body',
          receivedDateTime: '2025-11-02T10:00:00Z',
          isRead: false,
          importance: 'normal'
        }
      ];

      mockInvoke.mockResolvedValue(mockEmails);

      const params: OutlookEmailSkillParams = {
        action: 'get'
      };

      const result = await outlookEmailSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.emails).toEqual(mockEmails);
      expect(result.count).toBe(1);
      expect(mockInvoke).toHaveBeenCalledWith('get_outlook_emails', {
        userId: 'test-user',
        limit: 10,
        unread: undefined
      });
    });

    it('should apply limit parameter', async () => {
      mockInvoke.mockResolvedValue([]);

      const params: OutlookEmailSkillParams = {
        action: 'get',
        limit: 5
      };

      await outlookEmailSkill.execute(params, context);

      expect(mockInvoke).toHaveBeenCalledWith('get_outlook_emails', {
        userId: 'test-user',
        limit: 5,
        unread: undefined
      });
    });

    it('should filter unread emails', async () => {
      mockInvoke.mockResolvedValue([]);

      const params: OutlookEmailSkillParams = {
        action: 'get',
        unread: true
      };

      await outlookEmailSkill.execute(params, context);

      expect(mockInvoke).toHaveBeenCalledWith('get_outlook_emails', {
        userId: 'test-user',
        limit: 10,
        unread: true
      });
    });
  });

  describe('searchEmails', () => {
    it('should search emails with query', async () => {
      const mockSearchResults = [
        {
          id: '1',
          subject: 'Project Update',
          from: { name: 'Team', address: 'team@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Latest project update',
          receivedDateTime: '2025-11-02T10:00:00Z',
          isRead: false,
          importance: 'high'
        }
      ];

      mockInvoke.mockResolvedValue(mockSearchResults);

      const params: OutlookEmailSkillParams = {
        action: 'search',
        searchQuery: 'project update'
      };

      const result = await outlookEmailSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.emails).toEqual(mockSearchResults);
      expect(result.searchQuery).toBe('project update');
      expect(mockInvoke).toHaveBeenCalledWith('search_outlook_emails', {
        userId: 'test-user',
        query: 'project update',
        limit: 10
      });
    });

    it('should fail without search query', async () => {
      const params: OutlookEmailSkillParams = {
        action: 'search'
      };

      await expect(outlookEmailSkill.execute(params, context))
        .rejects.toThrow('Search query is required for email search');
    });
  });

  describe('triageEmails', () => {
    it('should triage emails correctly', async () => {
      const mockUnreadEmails = [
        {
          id: '1',
          subject: 'URGENT: Security Alert',
          from: { name: 'Security Team', address: 'security@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Immediate attention required',
          receivedDateTime: '2025-11-02T10:00:00Z',
          isRead: false,
          importance: 'high'
        },
        {
          id: '2',
          subject: 'Team Meeting Tomorrow',
          from: { name: 'Manager', address: 'manager@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Please review the agenda',
          receivedDateTime: '2025-11-02T09:00:00Z',
          isRead: false,
          importance: 'normal'
        }
      ];

      mockInvoke.mockResolvedValue(mockUnreadEmails);

      const params: OutlookEmailSkillParams = {
        action: 'triage'
      };

      const result = await outlookEmailSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.emails).toHaveLength(2);
      expect(result.categorized).toBeDefined();
      expect(result.summary).toBeDefined();
      
      // Check priority detection
      const triagedEmails = result.emails as any[];
      const urgentEmail = triagedEmails.find(e => e.subject.includes('URGENT'));
      expect(urgentEmail.priority).toBe('high');
      
      // Check category detection
      expect(urgentEmail.category).toBe('security');
    });
  });
});

describe('Outlook Calendar Skills', () => {
  let context: SkillExecutionContext;

  beforeEach(() => {
    jest.clearAllMocks();
    context = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: new Date().toISOString(),
      intent: 'outlook_create_event',
      entities: [],
      confidence: 0.9
    };
  });

  describe('createEvent', () => {
    it('should create event successfully with valid parameters', async () => {
      mockInvoke.mockResolvedValue({ 
        success: true, 
        message: 'Event created',
        eventId: 'event-123'
      });

      const params: OutlookCalendarSkillParams = {
        action: 'create',
        subject: 'Team Meeting',
        startTime: '2025-11-03T14:00:00',
        endTime: '2025-11-03T15:00:00'
      };

      const result = await outlookCalendarSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.eventId).toBe('event-123');
      expect(mockInvoke).toHaveBeenCalledWith('create_outlook_calendar_event', {
        userId: 'test-user',
        subject: 'Team Meeting',
        start_time: '2025-11-03T14:00:00',
        end_time: '2025-11-03T15:00:00',
        body: undefined,
        location: undefined,
        attendees: undefined
      });
    });

    it('should fail with missing required parameters', async () => {
      const params: OutlookCalendarSkillParams = {
        action: 'create',
        subject: 'Team Meeting',
        startTime: '2025-11-03T14:00:00',
        endTime: '' // Missing end time
      };

      await expect(outlookCalendarSkill.execute(params, context))
        .rejects.toThrow('Subject, start time, and end time are required');
    });

    it('should create event with all optional parameters', async () => {
      mockInvoke.mockResolvedValue({ success: true, eventId: 'event-456' });

      const params: OutlookCalendarSkillParams = {
        action: 'create',
        subject: 'Project Review',
        startTime: '2025-11-04T10:00:00',
        endTime: '2025-11-04T11:30:00',
        body: 'Quarterly project review meeting',
        location: 'Conference Room A',
        attendees: ['john@example.com', 'jane@example.com']
      };

      await outlookCalendarSkill.execute(params, context);

      expect(mockInvoke).toHaveBeenCalledWith('create_outlook_calendar_event', {
        userId: 'test-user',
        subject: 'Project Review',
        start_time: '2025-11-04T10:00:00',
        end_time: '2025-11-04T11:30:00',
        body: 'Quarterly project review meeting',
        location: 'Conference Room A',
        attendees: ['john@example.com', 'jane@example.com']
      });
    });
  });

  describe('getEvents', () => {
    it('should retrieve calendar events', async () => {
      const mockEvents = [
        {
          id: '1',
          subject: 'Team Meeting',
          start: { dateTime: '2025-11-03T14:00:00', timeZone: 'UTC' },
          end: { dateTime: '2025-11-03T15:00:00', timeZone: 'UTC' },
          location: { displayName: 'Conference Room' },
          body: { content: 'Weekly team sync', contentType: 'text' }
        }
      ];

      mockInvoke.mockResolvedValue(mockEvents);

      const params: OutlookCalendarSkillParams = {
        action: 'get'
      };

      const result = await outlookCalendarSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.events).toEqual(mockEvents);
      expect(result.count).toBe(1);
      expect(mockInvoke).toHaveBeenCalledWith('get_outlook_calendar_events', {
        userId: 'test-user',
        limit: 10
      });
    });

    it('should apply limit parameter', async () => {
      mockInvoke.mockResolvedValue([]);

      const params: OutlookCalendarSkillParams = {
        action: 'get',
        limit: 5
      };

      await outlookCalendarSkill.execute(params, context);

      expect(mockInvoke).toHaveBeenCalledWith('get_outlook_calendar_events', {
        userId: 'test-user',
        limit: 5
      });
    });
  });

  describe('updateEvent', () => {
    it('should update existing event', async () => {
      mockInvoke.mockResolvedValue({ 
        success: true, 
        message: 'Event updated' 
      });

      const params: OutlookCalendarSkillParams = {
        action: 'update',
        eventId: 'event-123',
        subject: 'Updated Team Meeting',
        startTime: '2025-11-03T15:00:00',
        endTime: '2025-11-03T16:00:00'
      };

      const result = await outlookCalendarSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(mockInvoke).toHaveBeenCalledWith('update_outlook_calendar_event', {
        userId: 'test-user',
        eventId: 'event-123',
        subject: 'Updated Team Meeting',
        start_time: '2025-11-03T15:00:00',
        end_time: '2025-11-03T16:00:00',
        body: undefined,
        location: undefined,
        attendees: undefined
      });
    });

    it('should fail without event ID', async () => {
      const params: OutlookCalendarSkillParams = {
        action: 'update',
        subject: 'Updated Meeting'
      };

      await expect(outlookCalendarSkill.execute(params, context))
        .rejects.toThrow('Event ID is required for updating events');
    });
  });

  describe('searchEvents', () => {
    it('should search calendar events', async () => {
      const mockSearchResults = [
        {
          id: '1',
          subject: 'Client Project Discussion',
          start: { dateTime: '2025-11-05T10:00:00', timeZone: 'UTC' },
          end: { dateTime: '2025-11-05T11:00:00', timeZone: 'UTC' },
          location: { displayName: 'Client Office' }
        }
      ];

      mockInvoke.mockResolvedValue(mockSearchResults);

      const params: OutlookCalendarSkillParams = {
        action: 'search',
        searchQuery: 'client meeting'
      };

      const result = await outlookCalendarSkill.execute(params, context);

      expect(result.success).toBe(true);
      expect(result.events).toEqual(mockSearchResults);
      expect(result.searchQuery).toBe('client meeting');
      expect(mockInvoke).toHaveBeenCalledWith('search_outlook_calendar_events', {
        userId: 'test-user',
        query: 'client meeting',
        limit: 10
      });
    });

    it('should fail without search query', async () => {
      const params: OutlookCalendarSkillParams = {
        action: 'search'
      };

      await expect(outlookCalendarSkill.execute(params, context))
        .rejects.toThrow('Search query is required for event search');
    });
  });
});