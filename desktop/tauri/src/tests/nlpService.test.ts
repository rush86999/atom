/**
 * NLP Service Testing Suite
 * Tests for intent recognition and entity extraction
 */

import { nlpService, NLPResult } from '../services/nlpService';

describe('NLP Service', () => {
  describe('Email Intents', () => {
    it('should recognize send email intent', async () => {
      const message = "Send an email to john@example.com";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_send_email');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize get emails intent', async () => {
      const message = "Show me my recent emails";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_get_emails');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize search emails intent', async () => {
      const message = "Search emails for project update";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_search_emails');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize triage emails intent', async () => {
      const message = "Triage my emails by priority";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_triage_emails');
      expect(result.confidence).toBeGreaterThan(0.5);
    });
  });

  describe('Calendar Intents', () => {
    it('should recognize create event intent', async () => {
      const message = "Create a calendar event 'Team Meeting' tomorrow at 2 PM";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_create_event');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize get events intent', async () => {
      const message = "Show me my upcoming events";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_get_calendar');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize search events intent', async () => {
      const message = "Search calendar for client meeting";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_search_events');
      expect(result.confidence).toBeGreaterThan(0.5);
    });
  });

  describe('Utility Intents', () => {
    it('should recognize help intent', async () => {
      const message = "Outlook help";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_help');
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should recognize status intent', async () => {
      const message = "Is Outlook connected?";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_status');
      expect(result.confidence).toBeGreaterThan(0.5);
    });
  });

  describe('Entity Extraction', () => {
    it('should extract email recipient', async () => {
      const message = "Send an email to john@example.com";
      const result = await nlpService.processMessage(message);

      const recipient = result.entities.find(e => e.type === 'recipient');
      expect(recipient).toBeDefined();
      expect(recipient?.value).toBe('john@example.com');
    });

    it('should extract email subject', async () => {
      const message = "Send an email with subject 'Meeting Update'";
      const result = await nlpService.processMessage(message);

      const subject = result.entities.find(e => e.type === 'subject');
      expect(subject).toBeDefined();
      expect(subject?.value).toBe('Meeting Update');
    });

    it('should extract email message body', async () => {
      const message = "Send an email with message 'The meeting has been rescheduled'";
      const result = await nlpService.processMessage(message);

      const messageBody = result.entities.find(e => e.type === 'message');
      expect(messageBody).toBeDefined();
      expect(messageBody?.value).toBe('The meeting has been rescheduled');
    });

    it('should extract search query', async () => {
      const message = "Search emails for 'project update'";
      const result = await nlpService.processMessage(message);

      const searchQuery = result.entities.find(e => e.type === 'search_query');
      expect(searchQuery).toBeDefined();
      expect(searchQuery?.value).toBe('project update');
    });

    it('should extract event subject', async () => {
      const message = "Create a calendar event 'Team Meeting'";
      const result = await nlpService.processMessage(message);

      const subject = result.entities.find(e => e.type === 'subject');
      expect(subject).toBeDefined();
      expect(subject?.value).toBe('Team Meeting');
    });

    it('should extract event time', async () => {
      const message = "Create a calendar event 'Team Meeting' tomorrow at 2 PM";
      const result = await nlpService.processMessage(message);

      const startTime = result.entities.find(e => e.type === 'start_time');
      expect(startTime).toBeDefined();
      expect(startTime?.value).toContain('2 PM');
    });

    it('should extract event location', async () => {
      const message = "Create a calendar event in 'Conference Room A'";
      const result = await nlpService.processMessage(message);

      const location = result.entities.find(e => e.type === 'location');
      expect(location).toBeDefined();
      expect(location?.value).toBe('Conference Room A');
    });

    it('should extract count', async () => {
      const message = "Show me 5 recent emails";
      const result = await nlpService.processMessage(message);

      const count = result.entities.find(e => e.type === 'count');
      expect(count).toBeDefined();
      expect(count?.value).toBe(5);
    });

    it('should extract unread flag', async () => {
      const message = "Get unread emails";
      const result = await nlpService.processMessage(message);

      const unread = result.entities.find(e => e.type === 'unread');
      expect(unread).toBeDefined();
      expect(unread?.value).toBe(true);
    });
  });

  describe('Complex Message Processing', () => {
    it('should handle multiple entities in one message', async () => {
      const message = "Send an email to john@example.com with subject 'Project Update' and message 'The deadline has been moved to Friday'";
      const result = await nlpService.processMessage(message);

      const recipient = result.entities.find(e => e.type === 'recipient');
      const subject = result.entities.find(e => e.type === 'subject');
      const messageBody = result.entities.find(e => e.type === 'message');

      expect(recipient?.value).toBe('john@example.com');
      expect(subject?.value).toBe('Project Update');
      expect(messageBody?.value).toBe('The deadline has been moved to Friday');
    });

    it('should handle calendar event with all details', async () => {
      const message = "Create a calendar event 'Project Review' tomorrow at 2 PM until 3 PM in 'Conference Room B' with team members";
      const result = await nlpService.processMessage(message);

      const subject = result.entities.find(e => e.type === 'subject');
      const startTime = result.entities.find(e => e.type === 'start_time');
      const endTime = result.entities.find(e => e.type === 'end_time');
      const location = result.entities.find(e => e.type === 'location');

      expect(subject?.value).toBe('Project Review');
      expect(startTime?.value).toContain('2 PM');
      expect(endTime?.value).toContain('3 PM');
      expect(location?.value).toBe('Conference Room B');
    });
  });

  describe('Edge Cases', () => {
    it('should handle ambiguous input', async () => {
      const message = "Email thing";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('general');
      expect(result.confidence).toBeLessThan(0.5);
    });

    it('should handle empty message', async () => {
      const message = "";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('general');
      expect(result.entities).toHaveLength(0);
    });

    it('should handle partial matches', async () => {
      const message = "I want to email someone";
      const result = await nlpService.processMessage(message);

      // Should still recognize the intent even without specific entities
      expect(result.intent.name).toBe('outlook_send_email');
      expect(result.confidence).toBeGreaterThan(0);
    });

    it('should handle malformed input', async () => {
      const message = "send email to @#$%";
      const result = await nlpService.processMessage(message);

      expect(result.intent.name).toBe('outlook_send_email');
      expect(result.confidence).toBeGreaterThan(0);
      // Should not extract malformed email
      const recipient = result.entities.find(e => e.type === 'recipient');
      expect(recipient?.value).not.toContain('@#$%');
    });
  });
});