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

// Typecast the mocked modules to access their methods with mock typings
const mockedCalendarSkills = calendarSkills as jest.Mocked<typeof calendarSkills>;
const mockedEmailSkills = emailSkills as jest.Mocked<typeof emailSkills>;
const mockedWebResearchSkills = webResearchSkills as jest.Mocked<typeof webResearchSkills>;
const mockedZapierSkills = zapierSkills as jest.Mocked<typeof zapierSkills>;

describe('Atom Agent handleMessage', () => {
  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();
  });

  // Calendar Skills Tests
  it('should list upcoming events', async () => {
    const mockEvents: CalendarEvent[] = [{ id: '1', summary: 'Event 1', startTime: '2024-01-01T10:00:00Z', endTime: '2024-01-01T11:00:00Z' }];
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue(mockEvents);
    const response = await handleMessage('list events');
    expect(mockedCalendarSkills.listUpcomingEvents).toHaveBeenCalledWith(10); // Default limit
    expect(response).toContain('Upcoming events:');
    expect(response).toContain('Event 1');
  });

  it('should list upcoming events with a limit', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue([]);
    await handleMessage('list events 5');
    expect(mockedCalendarSkills.listUpcomingEvents).toHaveBeenCalledWith(5);
  });

  it('should handle no upcoming events', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockResolvedValue([]);
    const response = await handleMessage('list events');
    expect(response).toBe('No upcoming events found.');
  });

  it('should create a calendar event', async () => {
    const mockResponse: CreateEventResponse = { success: true, eventId: 'newEvent1', message: 'Event created' };
    mockedCalendarSkills.createCalendarEvent.mockResolvedValue(mockResponse);
    const eventDetails = { summary: 'Test Event', startTime: '2024-01-01T14:00:00Z', endTime: '2024-01-01T15:00:00Z' };
    const response = await handleMessage(`create event ${JSON.stringify(eventDetails)}`);
    expect(mockedCalendarSkills.createCalendarEvent).toHaveBeenCalledWith(eventDetails);
    expect(response).toContain('Event created: Event created (ID: newEvent1)');
  });

  it('should handle missing details for create calendar event', async () => {
    const response = await handleMessage('create event {"summary":"Test"}');
    // Assuming createCalendarEvent in skills handles this and returns a specific message
    // For this test, we are testing handler's parsing. If JSON is valid but skill rejects, that's a skill test.
    // If JSON is invalid, it's handled by the handler's try-catch for JSON.parse.
    // Let's assume the skill itself would be called if JSON is valid.
    // If createCalendarEvent is robust, it will be called. If it throws, catch block in handler runs.
    // For now, let's assume it calls the skill.
    const mockResponse: CreateEventResponse = { success: false, message: 'Missing details' };
     mockedCalendarSkills.createCalendarEvent.mockResolvedValue(mockResponse);
    await handleMessage('create event {"summary":"Test Event"}'); // Partial valid JSON
    expect(mockedCalendarSkills.createCalendarEvent).toHaveBeenCalledWith({"summary":"Test Event"});
  });

   it('should handle invalid JSON for create calendar event', async () => {
    const response = await handleMessage('create event this is not json');
    expect(response).toContain("Invalid event details format.");
    expect(mockedCalendarSkills.createCalendarEvent).not.toHaveBeenCalled();
  });


  // Email Skills Tests
  it('should list recent emails', async () => {
    const mockEmailsData: Email[] = [{ id: 'e1', sender: 'test@example.com', recipient: 'me@example.com', subject: 'Test Email', body: '', timestamp: '2024-01-01T00:00:00Z', read: false }];
    mockedEmailSkills.listRecentEmails.mockResolvedValue(mockEmailsData);
    const response = await handleMessage('list emails');
    expect(mockedEmailSkills.listRecentEmails).toHaveBeenCalledWith(10);
    expect(response).toContain('Recent emails:');
    expect(response).toContain('Test Email');
  });

   it('should handle no recent emails', async () => {
    mockedEmailSkills.listRecentEmails.mockResolvedValue([]);
    const response = await handleMessage('list emails');
    expect(response).toBe('No recent emails found.');
  });

  it('should read an email', async () => {
    const mockEmail: Email = { id: 'e1', sender: 'test@example.com', recipient: 'me@example.com', subject: 'Test Email', body: 'Email body', timestamp: '2024-01-01T00:00:00Z', read: false };
    const mockResponse: ReadEmailResponse = { success: true, email: mockEmail };
    mockedEmailSkills.readEmail.mockResolvedValue(mockResponse);
    const response = await handleMessage('read email e1');
    expect(mockedEmailSkills.readEmail).toHaveBeenCalledWith('e1');
    expect(response).toContain('Email (ID: e1):');
    expect(response).toContain('Subject: Test Email');
    expect(response).toContain('Email body');
  });

  it('should handle reading a non-existent email', async () => {
    const mockResponse: ReadEmailResponse = { success: false, message: 'Email not found' };
    mockedEmailSkills.readEmail.mockResolvedValue(mockResponse);
    const response = await handleMessage('read email nonExistentId');
    expect(response).toBe('Email not found');
  });


  it('should send an email', async () => {
    const mockResponse: SendEmailResponse = { success: true, emailId: 'sentEmail1', message: 'Email sent' };
    mockedEmailSkills.sendEmail.mockResolvedValue(mockResponse);
    const emailDetails = { to: 'recipient@example.com', subject: 'Hello', body: 'Test body' };
    const response = await handleMessage(`send email ${JSON.stringify(emailDetails)}`);
    expect(mockedEmailSkills.sendEmail).toHaveBeenCalledWith(emailDetails);
    expect(response).toContain('Email sent: Email sent (ID: sentEmail1)');
  });

  // Web Research Skills Tests
  it('should search the web', async () => {
    const mockResults: SearchResult[] = [{ title: 'Result 1', link: 'http://example.com/1', snippet: 'Snippet 1' }];
    mockedWebResearchSkills.searchWeb.mockResolvedValue(mockResults);
    const response = await handleMessage('search web test query');
    expect(mockedWebResearchSkills.searchWeb).toHaveBeenCalledWith('test query');
    expect(response).toContain('Web search results for "test query":');
    expect(response).toContain('Result 1');
  });

  it('should handle no web results', async () => {
    mockedWebResearchSkills.searchWeb.mockResolvedValue([]);
    const response = await handleMessage('search web emptyQuery');
    expect(response).toBe('No web results found for "emptyQuery".');
  });


  // Zapier Skills Tests
  it('should trigger a Zap with data', async () => {
    const mockResponse: ZapTriggerResponse = { success: true, zapName: 'MyZap', runId: 'zapRun1', message: 'Zap triggered' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockResponse);
    const zapData = { key: 'value' };
    const response = await handleMessage(`trigger zap MyZap with data ${JSON.stringify(zapData)}`);
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith('MyZap', zapData);
    expect(response).toContain('Zap triggered: Zap triggered (Run ID: zapRun1)');
  });

  it('should trigger a Zap without data', async () => {
    const mockResponse: ZapTriggerResponse = { success: true, zapName: 'MyZapNoData', runId: 'zapRun2', message: 'Zap triggered' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockResponse);
    const response = await handleMessage('trigger zap MyZapNoData');
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith('MyZapNoData', {});
    expect(response).toContain('Zap triggered: Zap triggered (Run ID: zapRun2)');
  });

  it('should handle invalid JSON for trigger zap data', async () => {
    const response = await handleMessage('trigger zap MyZap with data this is not json');
    expect(response).toContain("Invalid JSON data format.");
    expect(mockedZapierSkills.triggerZap).not.toHaveBeenCalled();
  });


  // General Handler Logic
  it('should handle unknown commands gracefully', async () => {
    const response = await handleMessage('unknown command here');
    const expectedResponse = `Atom received: "unknown command here". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", or "trigger zap <ZapName> [with data {JSON_DATA}]".`;
    expect(response).toBe(expectedResponse);
  });

  it('should return error message if a skill throws an error', async () => {
    mockedCalendarSkills.listUpcomingEvents.mockRejectedValue(new Error('Skill failure'));
    const response = await handleMessage('list events');
    expect(response).toBe("Sorry, I couldn't fetch the upcoming events.");
  });
});
