import { handleMessage } from './handler';
import * as hubspotSkills from './skills/hubspotSkills';
import * as slackSkills from './skills/slackSkills';
import * as constants from './_libs/constants';
import { CreateHubSpotContactResponse, HubSpotContact, HubSpotContactProperties } from '../types';

// Mock skills and constants
// It's better to mock specific functions from skills, not the entire module if other functions are tested elsewhere.
// However, for handler tests, mocking the entire skill module to control its behavior is common.
const mockCreateHubSpotContact = jest.fn();
const mockSendSlackMessage = jest.fn();

jest.mock('./skills/hubspotSkills', () => ({
  createHubSpotContact: mockCreateHubSpotContact,
  // Add other hubspotSkills exports here if they are used by the handler and need mocking
}));
jest.mock('./skills/slackSkills', () => ({
  sendSlackMessage: mockSendSlackMessage,
  // Add other slackSkills exports here if they are used by the handler and need mocking
}));

// Mock constants module
// Ensure all constants used by the handler are mocked here.
jest.mock('../_libs/constants', () => ({
  ATOM_HUBSPOT_PORTAL_ID: 'mock_portal_id_default',
  ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID: 'mock_slack_channel_id_default',
  ATOM_QB_TOKEN_FILE_PATH: './mock_qb_tokens.json', // Example, add others as needed
  // Default other constants that might be used by other parts of handler.ts
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'mock_google_client_id',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'mock_google_client_secret',
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI: 'mock_google_redirect_uri',
   // ... other constants used by handler
}));


describe('handleMessage - create hubspot contact command variations', () => {
  // let mockCreateHubSpotContact: jest.SpyInstance; // These are now module-level mocks
  // let mockSendSlackMessage: jest.SpyInstance;
  let consoleErrorSpy: jest.SpyInstance;
  let consoleLogSpy: jest.SpyInstance;

  const userId = "mock_user_id_from_handler"; // As used in handler
  const validContactDetails: HubSpotContactProperties = { email: 'test@example.com', firstname: 'TestF', lastname: 'UserL', company: 'TestCorp' };
  const validContactDetailsJson = JSON.stringify(validContactDetails);

  const mockSuccessfulHubSpotResponse: CreateHubSpotContactResponse = { // Renamed to avoid conflict
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
    // Reset mocks for skills
    mockCreateHubSpotContact.mockReset();
    mockSendSlackMessage.mockReset();

    // Spy on console methods
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    // Reset constants to their default mock values for each test
    // This requires the jest.mock('../_libs/constants') to be effective and allow modification,
    // or dynamic mocking using jest.spyOn for each constant.
    // For simplicity, we assume the module mock is fresh or re-evaluate if issues arise.
    // To ensure specific values for constants in tests, use jest.spyOn:
    jest.spyOn(constants, 'ATOM_HUBSPOT_PORTAL_ID', 'get').mockReturnValue('mock_portal_id_default');
    jest.spyOn(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', 'get').mockReturnValue('mock_slack_channel_id_default');

  });

  afterEach(() => {
    // Restore spied console methods and clear all mocks
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
    jest.clearAllMocks(); // This will also clear jest.spyOn mocks on constants
  });

  // Test suite for the original "create hubspot contact" command (notifications to a channel)
  describe('"create hubspot contact {JSON}" command', () => {
        const commandPrefix = 'create hubspot contact ';
        const mockContactResponse = { // A more complete mock for hubSpotContact
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
        };

        it('should create contact and send channel notification if ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID is set', async () => {
            jest.spyOn(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', 'get').mockReturnValue('C123GENERAL');
            jest.spyOn(constants, 'ATOM_HUBSPOT_PORTAL_ID', 'get').mockReturnValue('portal123');
            mockCreateHubSpotContact.mockResolvedValue({ success: true, contactId: 'hs-123', hubSpotContact: mockContactResponse });
            mockSendSlackMessage.mockResolvedValue({ ok: true });

            const result = await handleMessage(commandPrefix + validContactDetailsJson);

            expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, JSON.parse(validContactDetailsJson));
            expect(mockSendSlackMessage).toHaveBeenCalledWith(
                userId, // userId for the call context
                'C123GENERAL', // Channel ID for notification
                expect.stringContaining("🎉 New HubSpot Contact Created by Atom Agent! 🎉")
            );
            expect(result).toContain('HubSpot contact created successfully! ID: hs-123');
        });

        it('should create contact and NOT send channel notification if ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID is NOT set', async () => {
            jest.spyOn(constants, 'ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID', 'get').mockReturnValue(''); // Not set
            mockCreateHubSpotContact.mockResolvedValue({ success: true, contactId: 'hs-123', hubSpotContact: mockContactResponse });

            const result = await handleMessage(commandPrefix + validContactDetailsJson);

            expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, JSON.parse(validContactDetailsJson));
            expect(mockSendSlackMessage).not.toHaveBeenCalled();
            expect(result).toContain('HubSpot contact created successfully! ID: hs-123');
            expect(consoleLogSpy).toHaveBeenCalledWith('Slack notification channel ID for HubSpot not configured. Skipping notification.');
        });
    });


  // Test suite for the new "create hubspot contact and dm me details" command
  describe('"create hubspot contact and dm me details {JSON}" command', () => {
    const commandPrefixDM = 'create hubspot contact and dm me details ';
     const mockDmContactResponse = { // A more complete mock for hubSpotContact for DM case
            id: 'contact123',
            properties: {
                hs_object_id: 'contact123',
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
        };


    it('Success: HubSpot contact created & Slack DM sent (with Portal ID)', async () => {
      jest.spyOn(constants, 'ATOM_HUBSPOT_PORTAL_ID', 'get').mockReturnValue('mock_portal_id');
      mockCreateHubSpotContact.mockResolvedValue({ success: true, contactId: 'contact123', hubSpotContact: mockDmContactResponse });
      mockSendSlackMessage.mockResolvedValue({ ok: true });

      const result = await handleMessage(commandPrefixDM + validContactDetailsJson);
      expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, JSON.parse(validContactDetailsJson));
      const expectedSlackMsg =
        `🎉 HubSpot Contact Created!\n` +
        `ID: contact123\n` +
        `Name: ${validContactDetails.firstname} ${validContactDetails.lastname}\n` +
        `Email: ${validContactDetails.email}\n` +
        `Company: ${validContactDetails.company}\n` +
        `View in HubSpot: https://app.hubspot.com/contacts/mock_portal_id/contact/contact123\n`;
      expect(mockSendSlackMessage).toHaveBeenCalledWith(userId, userId, expectedSlackMsg); // userId as channel for DM
      expect(result).toBe("HubSpot contact created (ID: contact123). I've sent the details to your Slack DM!");
    });

    it('Success: HubSpot contact created & Slack DM sent (NO Portal ID)', async () => {
      jest.spyOn(constants, 'ATOM_HUBSPOT_PORTAL_ID', 'get').mockReturnValue(''); // Portal ID not set
      mockCreateHubSpotContact.mockResolvedValue({ success: true, contactId: 'contact123', hubSpotContact: mockDmContactResponse });
      mockSendSlackMessage.mockResolvedValue({ ok: true });

      const result = await handleMessage(commandPrefixDM + validContactDetailsJson);
      expect(mockCreateHubSpotContact).toHaveBeenCalledWith(userId, JSON.parse(validContactDetailsJson));
      const slackMessageSent = mockSendSlackMessage.mock.calls[0][2]; // Get the message string
      expect(slackMessageSent).toContain('HubSpot Contact Created!');
      expect(slackMessageSent).toContain('ID: contact123');
      expect(slackMessageSent).not.toContain('View in HubSpot:'); // Link should be absent
      expect(result).toBe("HubSpot contact created (ID: contact123). I've sent the details to your Slack DM!");
    });

    it('Failure: HubSpot success, Slack DM fails', async () => {
      mockCreateHubSpotContact.mockResolvedValue({ success: true, contactId: 'contact123', hubSpotContact: mockDmContactResponse });
      mockSendSlackMessage.mockResolvedValue({ ok: false, error: 'slack_dm_test_error' });

      const result = await handleMessage(commandPrefixDM + validContactDetailsJson);
      expect(result).toBe("HubSpot contact created (ID: contact123), but I couldn't send details to your Slack DM. Slack error: slack_dm_test_error");
      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to send Slack DM for new HubSpot contact:', 'slack_dm_test_error');
    });

    it('Failure: HubSpot contact creation fails', async () => {
      mockCreateHubSpotContact.mockResolvedValue({ success: false, message: 'Test HubSpot Error Message' });
      const result = await handleMessage(commandPrefixDM + validContactDetailsJson);
      expect(mockSendSlackMessage).not.toHaveBeenCalled();
      expect(result).toBe("Failed to create HubSpot contact: Test HubSpot Error Message");
    });

    it('Failure: Invalid JSON input', async () => {
      const result = await handleMessage(commandPrefixDM + '{"email":"test@example.com",'); // Malformed
      expect(result).toContain("Invalid JSON format for contact details.");
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error parsing contact JSON for HubSpot creation (DM flow):', expect.any(String));
    });

    it('Failure: No JSON input provided after command', async () => {
        const result = await handleMessage(commandPrefixDM);
        expect(result).toContain(`Please provide contact details in JSON format after "${commandPrefixDM.trim()}"`);
    });

    it('Failure: Missing email in JSON input', async () => {
      const jsonWithoutEmail = '{"firstname":"Test", "lastname":"User"}';
      const result = await handleMessage(commandPrefixDM + jsonWithoutEmail);
      expect(result).toBe("The 'email' property is required in the JSON details to create a HubSpot contact.");
    });
  });

});


describe('handleMessage - default fallback', () => {
    it('should return the help message for an unknown command', async () => {
        const message = "unknown command here";
        // Update this expected string if more commands are added to the handler's help message
        const expectedHelpMessage = `Atom received: "${message}". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", "trigger zap <ZapName> [with data {JSON_DATA}]", "create hubspot contact {JSON_DETAILS}", "create hubspot contact and dm me details {JSON_DETAILS}", "slack my agenda", "list calendly event types", "list calendly bookings [active|canceled] [count]", "list zoom meetings [live|upcoming|scheduled|upcoming_meetings|previous_meetings] [page_size] [next_page_token]", "get zoom meeting <meetingId>", "list google meet events [limit]", "get google meet event <eventId>", "list teams meetings [limit] [nextLink]", "get teams meeting <eventId>", "list stripe payments [limit=N] [starting_after=ID] [customer=ID]", "get stripe payment <paymentIntentId>", "qb get auth url", "list qb invoices [limit=N] [offset=N] [customer=ID]", or "get qb invoice <invoiceId>".`;
        const result = await handleMessage(message);
        expect(result).toBe(expectedHelpMessage);
    });
});
