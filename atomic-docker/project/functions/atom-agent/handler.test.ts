import { handleMessage } from './handler';

import * as hubspotSkills from './skills/hubspotSkills';
import * as slackSkills from './skills/slackSkills';
import * as constants from './_libs/constants';
import { CreateHubSpotContactResponse, HubSpotContact, HubSpotContactProperties } from '../types';

// Mock skills and constants
jest.mock('./skills/hubspotSkills');
jest.mock('./skills/slackSkills');
jest.mock('./_libs/constants', () => ({
  ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID: '', // Default to not configured
  ATOM_HUBSPOT_PORTAL_ID: '', // Default to not configured
  // Add other constants if handler starts using them and they need default mocks
}));

describe('handleMessage - create hubspot contact', () => {
  let mockCreateHubSpotContact: jest.SpyInstance;
  let mockSendSlackMessage: jest.SpyInstance;
  let consoleErrorSpy: jest.SpyInstance;
  let consoleLogSpy: jest.SpyInstance;

  const userId = "mock_user_id_from_handler"; // As used in handler
  const validContactDetails: HubSpotContactProperties = { email: 'test@example.com', firstname: 'Test', lastname: 'User', company: 'Test Inc.' };
  const validContactDetailsJson = JSON.stringify(validContactDetails);

  const mockSuccessfulHubSpotResponse: CreateHubSpotContactResponse = {
    success: true,
    contactId: 'hs-123',
    message: 'Contact created',
    hubSpotContact: {
      id: 'hs-123',
      properties: {
        hs_object_id: 'hs-123',
        createdate: new Date().toISOString(),
        lastmodifieddate: new Date().toISOString(),
        email: validContactDetails.email,
        firstname: validContactDetails.firstname,
        lastname: validContactDetails.lastname,
        company: validContactDetails.company,
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      archived: false,
    },
  };

  beforeEach(() => {
    // Reset mocks and spies
    mockCreateHubSpotContact = jest.spyOn(hubspotSkills, 'createHubSpotContact');
    mockSendSlackMessage = jest.spyOn(slackSkills, 'sendSlackMessage');

    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    // Reset mocked constant values by re-assigning them through the imported module
    // This is a common way to handle module-level variable mocks in Jest
    Object.defineProperty(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', { value: '', writable: true, configurable: true });
    Object.defineProperty(constants, 'ATOM_HUBSPOT_PORTAL_ID', { value: '', writable: true, configurable: true });
  });

  afterEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  it('should successfully create contact and send Slack notification when all configs are present', async () => {
    Object.defineProperty(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', { value: 'slack-channel-123' });
    Object.defineProperty(constants, 'ATOM_HUBSPOT_PORTAL_ID', { value: 'portal-456' });
    mockCreateHubSpotContact.mockResolvedValue(mockSuccessfulHubSpotResponse);
    mockSendSlackMessage.mockResolvedValue({ ok: true });

    const message = `create hubspot contact ${validContactDetailsJson}`;
    const result = await handleMessage(message);

    expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, validContactDetails);
    expect(mockSendSlackMessage).toHaveBeenCalledTimes(1);
    const expectedSlackMessage =
      `🎉 New HubSpot Contact Created by Atom Agent! 🎉\n` +
      `ID: ${mockSuccessfulHubSpotResponse.contactId}\n` +
      `Name: ${mockSuccessfulHubSpotResponse.hubSpotContact!.properties.firstname} ${mockSuccessfulHubSpotResponse.hubSpotContact!.properties.lastname}\n` +
      `Email: ${mockSuccessfulHubSpotResponse.hubSpotContact!.properties.email}\n` +
      `Company: ${mockSuccessfulHubSpotResponse.hubSpotContact!.properties.company}\n` +
      `View in HubSpot: https://app.hubspot.com/contacts/portal-456/contact/${mockSuccessfulHubSpotResponse.contactId}\n` +
      `Created by User: ${userId}`;
    expect(mockSendSlackMessage).toHaveBeenCalledWith(userId, 'slack-channel-123', expectedSlackMessage);
    expect(result).toContain('HubSpot contact created successfully!');
    expect(result).toContain(`ID: ${mockSuccessfulHubSpotResponse.contactId}`);
  });

  it('should create contact but not send Slack notification if channel ID is not configured', async () => {
    Object.defineProperty(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', { value: '' }); // Ensure it's empty
    Object.defineProperty(constants, 'ATOM_HUBSPOT_PORTAL_ID', { value: 'portal-456' });
    mockCreateHubSpotContact.mockResolvedValue(mockSuccessfulHubSpotResponse);

    const message = `create hubspot contact ${validContactDetailsJson}`;
    const result = await handleMessage(message);

    expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, validContactDetails);
    expect(mockSendSlackMessage).not.toHaveBeenCalled();
    expect(result).toContain('HubSpot contact created successfully!');
    expect(consoleLogSpy).toHaveBeenCalledWith('Slack notification channel ID for HubSpot not configured. Skipping notification.');
  });

  it('should create contact and send Slack notification without full link if Portal ID is not configured', async () => {
    Object.defineProperty(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', { value: 'slack-channel-123' });
    Object.defineProperty(constants, 'ATOM_HUBSPOT_PORTAL_ID', { value: '' }); // Ensure it's empty
    mockCreateHubSpotContact.mockResolvedValue(mockSuccessfulHubSpotResponse);
    mockSendSlackMessage.mockResolvedValue({ ok: true });

    const message = `create hubspot contact ${validContactDetailsJson}`;
    await handleMessage(message);

    expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, validContactDetails);
    expect(mockSendSlackMessage).toHaveBeenCalledTimes(1);
    const slackCallArgs = mockSendSlackMessage.mock.calls[0];
    expect(slackCallArgs[2]).not.toContain('View in HubSpot:'); // Check that the link part is absent
    expect(slackCallArgs[2]).toContain(`ID: ${mockSuccessfulHubSpotResponse.contactId}`); // Ensure other details are there
  });

  it('should handle HubSpot contact creation failure', async () => {
    const hubspotFailureResponse: CreateHubSpotContactResponse = {
      success: false,
      message: 'HubSpot is down',
    };
    mockCreateHubSpotContact.mockResolvedValue(hubspotFailureResponse);

    const message = `create hubspot contact ${validContactDetailsJson}`;
    const result = await handleMessage(message);

    expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, validContactDetails);
    expect(mockSendSlackMessage).not.toHaveBeenCalled();
    expect(result).toBe(`Failed to create HubSpot contact: ${hubspotFailureResponse.message}`);
  });

  it('should handle invalid JSON for contact details', async () => {
    const invalidJson = '{"email":"test@example.com", "firstname": Test" }'; // Missing quote
    const message = `create hubspot contact ${invalidJson}`;
    const result = await handleMessage(message);

    expect(mockCreateHubSpotContact).not.toHaveBeenCalled();
    expect(mockSendSlackMessage).not.toHaveBeenCalled();
    expect(result).toContain('Invalid JSON format for contact details:');
  });

  it('should return error if no JSON details provided', async () => {
    const message = `create hubspot contact`;
    const result = await handleMessage(message);
    expect(result).toBe("Please provide contact details in JSON format. Usage: create hubspot contact {\"email\":\"test@example.com\",\"firstname\":\"Test\"}");
    expect(mockCreateHubSpotContact).not.toHaveBeenCalled();
  });

  it('should return error if email is missing in JSON details', async () => {
    const detailsWithoutEmail = JSON.stringify({ firstname: "Test" });
    const message = `create hubspot contact ${detailsWithoutEmail}`;
    const result = await handleMessage(message);
    expect(result).toBe("The 'email' property is required in the JSON details to create a HubSpot contact.");
    expect(mockCreateHubSpotContact).not.toHaveBeenCalled();
  });

   it('should log error if Slack notification fails but still return success for HubSpot creation', async () => {
    Object.defineProperty(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', { value: 'slack-channel-123' });
    Object.defineProperty(constants, 'ATOM_HUBSPOT_PORTAL_ID', { value: 'portal-456' });
    mockCreateHubSpotContact.mockResolvedValue(mockSuccessfulHubSpotResponse);
    mockSendSlackMessage.mockResolvedValue({ ok: false, error: 'slack_is_down' }); // Slack send fails

    const message = `create hubspot contact ${validContactDetailsJson}`;
    const result = await handleMessage(message);

    expect(mockCreateHubSpotContact).toHaveBeenCalledTimes(1);
    expect(mockSendSlackMessage).toHaveBeenCalledTimes(1);
    expect(result).toContain('HubSpot contact created successfully!'); // User message should still be success
    expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to send Slack notification for HubSpot contact creation:', 'slack_is_down');
  });

});

// Add other test suites for other commands in handler.ts if they exist or are added later.
// For example, describe('handleMessage - list events', () => { ... });
// This helps keep tests organized by command/feature.
describe('handleMessage - default fallback', () => {
    it('should return the help message for an unknown command', async () => {
        const message = "unknown command here";
        const result = await handleMessage(message);
        expect(result).toBe(`Atom received: "${message}". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", "trigger zap <ZapName> [with data {JSON_DATA}]", or "create hubspot contact {JSON_DETAILS}".`);
    });
=======
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

  // Web Research Skills Tests
  it('should search the web and format results', async () => {
    const mockSearchResults: SearchResult[] = [
      { title: 'Test Result 1', link: 'http://example.com/1', snippet: 'This is snippet 1.' },
      { title: 'Test Result 2', link: 'http://example.com/2', snippet: 'This is snippet 2.' },
    ];
    mockedWebResearchSkills.searchWeb.mockResolvedValue(mockSearchResults);
    const response = await handleMessage('search web test query', mockUserId);
    expect(mockedWebResearchSkills.searchWeb).toHaveBeenCalledWith('test query', mockUserId);
    expect(response).toBe(
      'Here are the web search results for "test query":\n\n' +
      '1. Test Result 1\n   Snippet: This is snippet 1.\n   Link: http://example.com/1\n\n' +
      '2. Test Result 2\n   Snippet: This is snippet 2.\n   Link: http://example.com/2'
    );
  });

  it('should handle no web results from skill with a user-friendly message', async () => {
    mockedWebResearchSkills.searchWeb.mockResolvedValue([]);
    const response = await handleMessage('search web specific query', mockUserId);
    expect(mockedWebResearchSkills.searchWeb).toHaveBeenCalledWith('specific query', mockUserId);
    expect(response).toBe('I couldn\'t find any web results for "specific query", or there might be an issue with the web search service configuration.');
  });

  it('should ask for a query if "search web" is called with no query', async () => {
    const response = await handleMessage('search web', mockUserId);
    expect(response).toBe("Please provide a term to search for after 'search web'.");
    expect(mockedWebResearchSkills.searchWeb).not.toHaveBeenCalled();
  });

  it('should ask for a query if "search web" is called with only whitespace', async () => {
    const response = await handleMessage('search web    ', mockUserId);
    expect(response).toBe("Please provide a term to search for after 'search web'.");
    expect(mockedWebResearchSkills.searchWeb).not.toHaveBeenCalled();
  });

  // Zapier Skills Tests
  it('should trigger a Zap with data and format success response with message and runId', async () => {
    const zapName = 'MyDataZap';
    const mockApiResponse: ZapTriggerResponse = { success: true, zapName, message: 'Custom Zap success!', runId: 'zapRunXYZ' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockApiResponse);
    const zapData = { item: 'testData' };
    const response = await handleMessage(`trigger zap ${zapName} with data ${JSON.stringify(zapData)}`, mockUserId);
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith(mockUserId, zapName, zapData);
    expect(response).toBe(`Successfully triggered Zap: "${zapName}". Custom Zap success! (Run ID: zapRunXYZ)`);
  });

  it('should trigger a Zap without data and format success response with default message from skill', async () => {
    const zapName = 'MySimpleZap';
    // Skill returns a default-like message which handler should ideally not repeat if it's the exact default.
    // Current handler logic will append it if it's not identical to `Zap "${zapName}" triggered successfully.`
    const skillMessage = `Zap "${zapName}" triggered successfully.`;
    const mockApiResponse: ZapTriggerResponse = { success: true, zapName, message: skillMessage, runId: 'zapRunABC' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockApiResponse);
    const response = await handleMessage(`trigger zap ${zapName}`, mockUserId);
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith(mockUserId, zapName, {});
    // Based on current handler logic, if skill message is exactly the default, it's omitted.
    expect(response).toBe(`Successfully triggered Zap: "${zapName}". (Run ID: zapRunABC)`);
  });

  it('should trigger a Zap and format success response if only runId is present from skill', async () => {
    const zapName = 'MyRunIdOnlyZap';
    const mockApiResponse: ZapTriggerResponse = { success: true, zapName, runId: 'zapRunOnly123' }; // No message from skill
    mockedZapierSkills.triggerZap.mockResolvedValue(mockApiResponse);
    const response = await handleMessage(`trigger zap ${zapName}`, mockUserId);
    expect(mockedZapierSkills.triggerZap).toHaveBeenCalledWith(mockUserId, zapName, {});
    expect(response).toBe(`Successfully triggered Zap: "${zapName}". (Run ID: zapRunOnly123)`);
  });

  it('should handle trigger Zap failure with a specific message from skill', async () => {
    const zapName = 'MyFailedZap';
    const mockApiResponse: ZapTriggerResponse = { success: false, zapName, message: 'Zap webhook returned 400 Bad Request.' };
    mockedZapierSkills.triggerZap.mockResolvedValue(mockApiResponse);
    const response = await handleMessage(`trigger zap ${zapName} with data {"info":"test"}`, mockUserId);
    expect(response).toBe(`Failed to trigger Zap: "${zapName}". Error: Zap webhook returned 400 Bad Request.`);
  });

  it('should handle trigger Zap failure with a generic message if none from skill', async () => {
    const zapName = 'AnotherFailedZap';
    const mockApiResponse: ZapTriggerResponse = { success: false, zapName }; // No message from skill
    mockedZapierSkills.triggerZap.mockResolvedValue(mockApiResponse);
    const response = await handleMessage(`trigger zap ${zapName}`, mockUserId);
    expect(response).toBe(`Failed to trigger Zap: "${zapName}". Error: An unknown error occurred.`);
  });

  it('should return error if zap name is missing for trigger zap', async () => {
    const response = await handleMessage('trigger zap  ', mockUserId);
    expect(response).toBe("Please specify the Zap name to trigger. Usage: trigger zap <ZapName> [with data {\"key\":\"value\"}]");
    expect(mockedZapierSkills.triggerZap).not.toHaveBeenCalled();
  });

  it('should return error for malformed JSON data for trigger zap', async () => {
    const response = await handleMessage('trigger zap TestZap with data {malformed}', mockUserId);
    expect(response).toBe("Invalid JSON data provided for the Zap. Please check the format. Example: {\"key\":\"value\"}");
    expect(mockedZapierSkills.triggerZap).not.toHaveBeenCalled();
  });

  it('should return error for empty JSON data string for trigger zap', async () => {
    const response = await handleMessage('trigger zap TestZap with data ', mockUserId);
    expect(response).toBe("Data part is empty. Please provide valid JSON data or omit the 'with data' part.");
    expect(mockedZapierSkills.triggerZap).not.toHaveBeenCalled();
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
