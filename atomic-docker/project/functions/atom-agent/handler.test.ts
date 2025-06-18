import { handleMessage } from './handler';
import * as calendarSkills from './skills/calendarSkills';
import * as emailSkills from './skills/emailSkills';
import * as webResearchSkills from './skills/webResearchSkills';
import * as zapierSkills from './skills/zapierSkills';
import { CalendarEvent, CreateEventResponse, Email, ReadEmailResponse, SendEmailResponse, SearchResult, ZapTriggerResponse } from '../types';

// Mock the skills modules
jest.mock('./skills/calendarSkills');
jest.mock('./skills/emailSkills');
jest.mock('./skills/webResearchSkills');
jest.mock('./skills/zapierSkills');

// Typecast the mocked modules
const mockedCalendarSkills = calendarSkills as jest.Mocked<typeof calendarSkills>;
const mockedEmailSkills = emailSkills as jest.Mocked<typeof emailSkills>;
const mockedWebResearchSkills = webResearchSkills as jest.Mocked<typeof webResearchSkills>;
const mockedZapierSkills = zapierSkills as jest.Mocked<typeof zapierSkills>;

const mockUserId = "test_user_123";

describe('Atom Agent handleMessage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Calendar Skills Tests
  it('should list upcoming events', async () => {
    const mockEvents: CalendarEvent[] = [{ id: '1', summary: 'Event 1', startTime: '2024-01-01T10:00:00Z', endTime: '2024-01-01T11:00:00Z', htmlLink: 'link1' }];
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue(mockEvents);
    const response = await handleMessage('list events', mockUserId);
    expect(mockedCalendarSkills.listUpcomingEvents).toHaveBeenCalledWith(mockUserId, 10);
    expect(response).toContain('Upcoming events:');
    expect(response).toContain('Event 1');
    expect(response).toContain('[Link: link1]');
  });

  it('should list upcoming events with a limit', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue([]);
    await handleMessage('list events 5', mockUserId);
    expect(mockedCalendarSkills.listUpcomingEvents).toHaveBeenCalledWith(mockUserId, 5);
  });

  it('should handle no upcoming events with a user-friendly message', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue([]);
    const response = await handleMessage('list events', mockUserId);
    expect(response).toBe("Could not retrieve calendar events. Please ensure your Google Calendar is connected in settings and try again, or there might be no upcoming events.");
  });

  it('should create a calendar event and include htmlLink', async () => {
    const mockResponse: CreateEventResponse = { success: true, eventId: 'newEvent1', message: 'Event created', htmlLink: 'http://google.com/event1' };
    mockedCalendarSkills.createCalendarEvent.mockResolvedValue(mockResponse);
    const eventDetails = { summary: 'Test Event', startTime: '2024-01-01T14:00:00Z', endTime: '2024-01-01T15:00:00Z' };
    const response = await handleMessage(`create event ${JSON.stringify(eventDetails)}`, mockUserId);
    expect(mockedCalendarSkills.createCalendarEvent).toHaveBeenCalledWith(mockUserId, eventDetails);
    expect(response).toBe('Event created: Event created (ID: newEvent1) Link: http://google.com/event1');
  });

  it('should handle create calendar event failure with a specific message from skill', async () => {
    const mockFailureResponse: CreateEventResponse = { success: false, message: 'Specific error from skill.' };
    mockedCalendarSkills.createCalendarEvent.mockResolvedValue(mockFailureResponse);
    const eventDetails = { summary: 'Bad Event', startTime: '2024-01-01T14:00:00Z', endTime: '2024-01-01T15:00:00Z' };
    const response = await handleMessage(`create event ${JSON.stringify(eventDetails)}`, mockUserId);
    expect(response).toBe('Failed to create calendar event. Specific error from skill.');
  });

  it('should handle create calendar event failure with a generic message if skill provides none', async () => {
    const mockFailureResponse: CreateEventResponse = { success: false };
    mockedCalendarSkills.createCalendarEvent.mockResolvedValue(mockFailureResponse);
    const eventDetails = { summary: 'Another Bad Event', startTime: '2024-01-01T14:00:00Z', endTime: '2024-01-01T15:00:00Z' };
    const response = await handleMessage(`create event ${JSON.stringify(eventDetails)}`, mockUserId);
    expect(response).toBe('Failed to create calendar event. Please check your connection or try again.');
  });

   it('should handle invalid JSON for create calendar event', async () => {
    const response = await handleMessage('create event this is not json', mockUserId);
    expect(response).toContain("Invalid event details format.");
    expect(mockedCalendarSkills.createCalendarEvent).not.toHaveBeenCalled();
  });

  // Email Skills Tests
  it('should list recent emails with formatted output', async () => {
    const mockTimestamp = new Date().toISOString();
    const mockEmailsData: Email[] = [
      { id: 'e1', sender: 'sender1@example.com', recipient: 'me@example.com', subject: 'Subject 1', body: 'Snippet1', timestamp: mockTimestamp, read: false },
      { id: 'e2', sender: 'sender2@example.com', recipient: 'me@example.com', subject: 'Subject 2', body: 'Snippet2', timestamp: mockTimestamp, read: true },
    ];
    mockedEmailSkills.listRecentEmails.mockResolvedValue(mockEmailsData);
    const response = await handleMessage('list emails', mockUserId);
    expect(mockedEmailSkills.listRecentEmails).toHaveBeenCalledWith(mockUserId, 10);
    expect(response).toContain('Here are your recent emails:');
    expect(response).toContain(`1. Subject: Subject 1\n   From: sender1@example.com\n   Date: ${new Date(mockTimestamp).toLocaleString()}\n   ID: e1`);
    expect(response).toContain(`2. Subject: Subject 2\n   From: sender2@example.com\n   Date: ${new Date(mockTimestamp).toLocaleString()}\n   ID: e2`);
    expect(response).toContain("Use 'read email <ID>' to read a specific email.");
  });

   it('should handle no recent emails with specific message', async () => {
    mockedEmailSkills.listRecentEmails.mockResolvedValue([]);
    const response = await handleMessage('list emails', mockUserId);
    expect(response).toBe('No recent emails found. This could also indicate an issue with your Gmail connection; please check settings if you expected emails.');
  });

  it('should read an email with formatted output', async () => {
    const mockTimestamp = new Date().toISOString();
    const mockEmail: Email = { id: 'e1', sender: 'sender@example.com', recipient: 'receiver@example.com', subject: 'Full Email Subject', body: 'This is the full email body.', timestamp: mockTimestamp, read: false };
    const mockResponse: ReadEmailResponse = { success: true, email: mockEmail };
    mockedEmailSkills.readEmail.mockResolvedValue(mockResponse);
    const response = await handleMessage('read email e1', mockUserId);
    expect(mockedEmailSkills.readEmail).toHaveBeenCalledWith(mockUserId, 'e1');
    expect(response).toBe(`Subject: Full Email Subject\nFrom: sender@example.com\nTo: receiver@example.com\nDate: ${new Date(mockTimestamp).toLocaleString()}\n\nBody:\nThis is the full email body.`);
  });

  it('should handle reading a non-existent email with user-friendly message', async () => {
    const mockResponse: ReadEmailResponse = { success: false, message: 'Email not found in system.' };
    mockedEmailSkills.readEmail.mockResolvedValue(mockResponse);
    const response = await handleMessage('read email nonExistentId', mockUserId);
    expect(response).toBe('Could not read email. Email not found in system.');
  });

  it('should send an email and confirm with ID', async () => {
    const mockResponse: SendEmailResponse = { success: true, emailId: 'sentEmail123', message: 'Message delivered.' };
    mockedEmailSkills.sendEmail.mockResolvedValue(mockResponse);
    const emailDetails = { to: 'recipient@example.com', subject: 'Hello', body: 'Test body' };
    const response = await handleMessage(`send email ${JSON.stringify(emailDetails)}`, mockUserId);
    expect(mockedEmailSkills.sendEmail).toHaveBeenCalledWith(mockUserId, emailDetails);
    expect(response).toBe('Email sent successfully! Message delivered. (Message ID: sentEmail123)');
  });

  it('should handle send email failure with specific message from skill', async () => {
    const mockResponse: SendEmailResponse = { success: false, message: 'Specific send failure.' };
    mockedEmailSkills.sendEmail.mockResolvedValue(mockResponse);
    const emailDetails = { to: 'recipient@example.com', subject: 'Hello', body: 'Test body' };
    const response = await handleMessage(`send email ${JSON.stringify(emailDetails)}`, mockUserId);
    expect(response).toBe('Failed to send email. Specific send failure.');
  });

  it('should handle send email failure with generic message if none from skill', async () => {
    const mockResponse: SendEmailResponse = { success: false }; // No message
    mockedEmailSkills.sendEmail.mockResolvedValue(mockResponse);
    const emailDetails = { to: 'recipient@example.com', subject: 'Hello', body: 'Test body' };
    const response = await handleMessage(`send email ${JSON.stringify(emailDetails)}`, mockUserId);
    expect(response).toBe('Failed to send email. Please try again or check your connection.');
  });

  // Web Research Skills Tests (confirming mockUserId pass-through)
  it('should search the web', async () => {
    const mockResults: SearchResult[] = [{ title: 'Result 1', link: 'http://example.com/1', snippet: 'Snippet 1' }];
    mockedWebResearchSkills.searchWeb.mockResolvedValue(mockResults);
    const response = await handleMessage('search web test query', mockUserId);
    expect(mockedWebResearchSkills.searchWeb).toHaveBeenCalledWith('test query'); // No userId for this skill
    expect(response).toContain('Web search results for "test query":');
  });

  // Zapier Skills Tests (confirming mockUserId pass-through)
  it('should trigger a Zap with data', async () => {
    const mockResponse: ZapTriggerResponse = { success: true, zapName: 'MyZap', runId: 'zapRun1', message: 'Zap triggered' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockResponse);
    const zapData = { key: 'value' };
    const response = await handleMessage(`trigger zap MyZap with data ${JSON.stringify(zapData)}`, mockUserId);
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith('MyZap', zapData); // No userId for this skill
    expect(response).toContain('Zap triggered: Zap triggered (Run ID: zapRun1)');
  });

  // General Handler Logic
  it('should handle unknown commands gracefully', async () => {
    const response = await handleMessage('unknown command here', mockUserId);
    const expectedResponse = `Atom received: "unknown command here". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", or "trigger zap <ZapName> [with data {JSON_DATA}]".`;
    expect(response).toBe(expectedResponse);
  });

  it('should return error message if a skill throws an error (e.g. calendar skill)', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockRejectedValue(new Error('Calendar Skill failure'));
    const response = await handleMessage('list events', mockUserId);
    expect(response).toBe("Sorry, I couldn't fetch the upcoming events.");
  });

  it('should return error message if email skill throws an error', async () => {
    mockedEmailSkills.listRecentEmails.mockRejectedValue(new Error('Email Skill catastrophic failure'));
    const response = await handleMessage('list emails', mockUserId);
    expect(response).toBe("Sorry, I couldn't fetch recent emails. Error: Email Skill catastrophic failure");
  });
});
