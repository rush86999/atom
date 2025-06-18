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
});
