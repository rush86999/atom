import { handleMessage } from './handler';
import * as hubspotSkills from './skills/hubspotSkills';
import * as slackSkills from './skills/slackSkills';
import * as constants from './_libs/constants';
import { CreateHubSpotContactResponse, HubSpotContact, HubSpotContactProperties } from '../types';

// Mock skills and constants
import { understandMessage } from './skills/nluService';
import * as calendarSkills from './skills/calendarSkills';
import * as quickbooksSkills from './skills/quickbooksSkills';
// ... other skill imports if needed for NLU testing

// Mock NLU Service
const mockedUnderstandMessage = jest.fn();
jest.mock('./skills/nluService', () => ({
  understandMessage: mockedUnderstandMessage,
}));

// Mock individual skill functions that will be called by the handler based on NLU intent
const mockedListUpcomingEvents = jest.fn();
const mockedCreateHubSpotContact = jest.fn(); // Already defined in previous HubSpot tests, ensure it's captured here
const mockedSendSlackMessage = jest.fn();   // Already defined
const mockedListQuickBooksInvoices = jest.fn();
const mockedGetQuickBooksInvoiceDetails = jest.fn();
// Add mocks for other skills as NLU intents are tested for them e.g. Stripe, Zoom, Calendly, MS Teams

jest.mock('./skills/calendarSkills', () => ({
  ...jest.requireActual('./skills/calendarSkills'), // Keep actual functions not being mocked
  listUpcomingEvents: mockedListUpcomingEvents,
  // Mock other calendar skills if NLU routes to them
}));
jest.mock('./skills/hubspotSkills', () => ({
  ...jest.requireActual('./skills/hubspotSkills'),
  createHubSpotContact: mockedCreateHubSpotContact,
}));
jest.mock('./skills/slackSkills', () => ({
  ...jest.requireActual('./skills/slackSkills'),
  sendSlackMessage: mockedSendSlackMessage,
}));
jest.mock('./skills/quickbooksSkills', () => ({
  ...jest.requireActual('./skills/quickbooksSkills'),
  listQuickBooksInvoices: mockedListQuickBooksInvoices,
  getQuickBooksInvoiceDetails: mockedGetQuickBooksInvoiceDetails,
}));

// Mock constants module - ensure all constants used by the handler are defined
jest.mock('../_libs/constants', () => ({
  ATOM_HUBSPOT_PORTAL_ID: 'mock_portal_id_default',
  ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID: 'mock_slack_channel_id_default',
  ATOM_QB_TOKEN_FILE_PATH: './mock_qb_tokens.json',
  // Ensure other constants used by handler or its imports have default mocks
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'mock_google_client_id',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'mock_google_client_secret',
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI: 'mock_google_redirect_uri',
  ATOM_OPENAI_API_KEY: 'mock_openai_key', // For NLU service itself
  ATOM_NLU_MODEL_NAME: 'gpt-test-nlu',   // For NLU service
}));


describe('handleMessage - NLU Intent Handling', () => {
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
    mockedUnderstandMessage.mockReset();
    mockedListUpcomingEvents.mockReset();
    mockedCreateHubSpotContact.mockReset(); // Use the module-level mock
    mockedSendSlackMessage.mockReset();   // Use the module-level mock
    mockedListQuickBooksInvoices.mockReset();
    mockedGetQuickBooksInvoiceDetails.mockReset();
    // Reset other mocked skill functions here

    // Spy on console methods
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    // Set default values for constants that might be used in the specific test paths
    // jest.spyOn(constants, 'ATOM_HUBSPOT_PORTAL_ID', 'get').mockReturnValue('default_portal_id_for_nlu_tests');
    // No need to spy on constants if the module mock already provides suitable defaults.
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
    jest.clearAllMocks();
  });

  it('should handle GetCalendarEvents intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'GetCalendarEvents',
      entities: { limit: 3, date_range: "today" }, // NLU might extract more
      originalMessage: "show me 3 events for today",
      error: undefined
    });
    mockedListUpcomingEvents.mockResolvedValue([
      { id: '1', summary: 'Event 1', startTime: new Date().toISOString(), endTime: new Date().toISOString() },
      { id: '2', summary: 'Event 2', startTime: new Date().toISOString(), endTime: new Date().toISOString() },
    ] as any);

    const result = await handleMessage("show me 3 events for today");
    expect(mockedUnderstandMessage).toHaveBeenCalledWith("show me 3 events for today");
    expect(mockedListUpcomingEvents).toHaveBeenCalledWith(expect.any(String), 3);
    expect(result).toContain('Event 1');
    expect(result).toContain('Event 2');
  });

  it('should handle CreateHubSpotContact intent (basic)', async () => {
    const contactEntities = { email: 'nlu.user@example.com', first_name: 'NLUFirstName', last_name: 'NLULastName', company_name: 'NLU Company' };
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'CreateHubSpotContact',
      entities: contactEntities,
      originalMessage: "create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company",
      error: undefined
    });
    mockedCreateHubSpotContact.mockResolvedValue({
      success: true,
      contactId: 'hs-nlu-123',
      hubSpotContact: { properties: { email: 'nlu.user@example.com', firstname: 'NLUFirstName', lastname: 'NLULastName' } } as any,
      message: 'Created via NLU'
    });

    const result = await handleMessage("create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company");
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String), // userId
      expect.objectContaining({
        email: 'nlu.user@example.com',
        firstname: 'NLUFirstName',
        lastname: 'NLULastName',
        company: 'NLU Company'
      })
    );
    expect(result).toContain('HubSpot contact created via NLU! ID: hs-nlu-123');
  });

   it('should handle CreateHubSpotContact intent with contact_name only', async () => {
    const contactEntities = { email: 'nlu.contact@example.com', contact_name: 'NLU Full Name', company_name: 'NLU Solutions' };
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'CreateHubSpotContact',
      entities: contactEntities,
      originalMessage: "create contact NLU Full Name, nlu.contact@example.com, NLU Solutions",
      error: undefined
    });
     mockedCreateHubSpotContact.mockResolvedValue({
      success: true,
      contactId: 'hs-nlu-456',
      hubSpotContact: { properties: { email: 'nlu.contact@example.com', firstname: 'NLU', lastname: 'Full Name' } } as any,
      message: 'Created via NLU with contact_name'
    });
    await handleMessage("create contact NLU Full Name, nlu.contact@example.com, NLU Solutions");
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        email: 'nlu.contact@example.com',
        firstname: 'NLU', // Derived from contact_name
        lastname: 'Full Name', // Derived from contact_name
        company: 'NLU Solutions'
      })
    );
  });


  it('should handle SendSlackMessage intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'SendSlackMessage',
      entities: { slack_channel: '#nlu-test', message_text: 'Hello from NLU' },
      originalMessage: "send slack to #nlu-test saying Hello from NLU",
      error: undefined
    });
    mockedSendSlackMessage.mockResolvedValue({ ok: true });

    const result = await handleMessage("send slack to #nlu-test saying Hello from NLU");
    expect(mockedSendSlackMessage).toHaveBeenCalledWith(expect.any(String), '#nlu-test', 'Hello from NLU');
    expect(result).toContain('Message sent to Slack channel/user #nlu-test');
  });

  it('should handle ListInvoices intent (QuickBooks)', async () => {
    mockedUnderstandMessage.mockResolvedValue({
        intent: 'ListInvoices',
        entities: { limit: 5, status: "Open" },
        originalMessage: "show me my last 5 open invoices",
        error: undefined
    });
    mockedListQuickBooksInvoices.mockResolvedValue({
        ok: true,
        invoices: [{ Id: 'qb-inv-1', DocNumber: 'QB001', TotalAmt: 100, CurrencyRef: { value: 'USD' } } as any],
        queryResponse: { totalCount: 1, maxResults: 5, startPosition: 1}
    });
    const result = await handleMessage("show me my last 5 open invoices");
    expect(mockedListQuickBooksInvoices).toHaveBeenCalledWith(expect.objectContaining({ limit: 5, offset:1 })); // Status not passed yet
    expect(result).toContain("QB001");
  });

  it('should handle GetInvoiceDetails intent (QuickBooks)', async () => {
    mockedUnderstandMessage.mockResolvedValue({
        intent: 'GetInvoiceDetails',
        entities: { invoice_id: "qb-inv-007" },
        originalMessage: "get details for invoice qb-inv-007",
        error: undefined
    });
    mockedGetQuickBooksInvoiceDetails.mockResolvedValue({
        ok: true,
        invoice: { Id: 'qb-inv-007', DocNumber: 'QB007', TotalAmt: 700, CurrencyRef: {value: 'USD'} } as any
    });
    const result = await handleMessage("get details for invoice qb-inv-007");
    expect(mockedGetQuickBooksInvoiceDetails).toHaveBeenCalledWith("qb-inv-007");
    expect(result).toContain("Doc #: QB007");
  });


  it('should fallback to specific command if NLU returns null intent (e.g., create hubspot contact and dm me details)', async () => {
    const specificCommand = 'create hubspot contact and dm me details {"email":"fallback.dm@example.com", "firstname":"FallbackDM"}';
    mockedUnderstandMessage.mockResolvedValue({
      intent: null, entities: {}, originalMessage: specificCommand, error: undefined
    });
    mockedCreateHubSpotContact.mockResolvedValue({
      success: true, contactId: 'hs-fallback-dm',
      hubSpotContact: { properties: { email: 'fallback.dm@example.com', firstname: 'FallbackDM' } } as any
    });
    mockedSendSlackMessage.mockResolvedValue({ ok: true }); // For the DM part

    const result = await handleMessage(specificCommand);
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String), // userId
      { email: 'fallback.dm@example.com', firstname: 'FallbackDM' }
    );
    // Check the DM call (userId as channel for DM)
    expect(mockedSendSlackMessage).toHaveBeenCalledWith(expect.any(String), expect.any(String), expect.stringContaining('HubSpot ID: hs-fallback-dm'));
    expect(result).toContain("I've sent the details to your Slack DM!");
  });

  it('should fallback to general help if NLU returns null intent and no specific command matches', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: null, entities: {}, originalMessage: "gibberish unknown command", error: undefined
    });
    const result = await handleMessage("gibberish unknown command");
    expect(result).toContain("Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help'");
  });

  it('should return NLU critical error message if NLU service itself has an issue', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      error: 'NLU Service is down for maintenance.', intent: null, entities: {}, originalMessage: "any message"
    });
    const result = await handleMessage("any message");
    expect(result).toContain("Sorry, I'm having trouble understanding requests right now. Please try again later.");
  });

  it('should return message for NLU recognized but not implemented intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'OrderPizza', entities: { size: 'large', topping: 'pepperoni' }, originalMessage: "order a large pepperoni pizza", error: undefined
    });
    const result = await handleMessage("order a large pepperoni pizza");
    expect(result).toContain("I understood your intent as 'OrderPizza'");
    expect(result).toContain("not fully set up to handle that specific request conversationally yet");
  });
});

// Keep the existing default fallback test, but ensure its expected message matches the new help text.
describe('handleMessage - default fallback (no NLU match, no specific command match)', () => {
    it('should return the updated help message for an unknown command if NLU returns null intent', async () => {
        mockedUnderstandMessage.mockResolvedValue({ intent: null, entities: {}, originalMessage: "unknown command here", error: undefined });
        const message = "unknown command here";
        const result = await handleMessage(message);
        const expectedHelpMessagePart = "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
        expect(result).toBe(expectedHelpMessagePart);
    });
});
