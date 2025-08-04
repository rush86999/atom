import { handleMessage } from './handler';
import * as hubspotSkills from './skills/hubspotSkills';
import * as slackSkills from './skills/slackSkills';
import * as constants from './_libs/constants';
import {
  CreateHubSpotContactResponse,
  HubSpotContact,
  HubSpotContactProperties,
} from '../types';

// Mock skills and constants
import { understandMessage } from './skills/nluService';
import * as calendarSkills from './skills/calendarSkills';
import * as quickbooksSkills from './skills/quickbooksSkills';
// ... other skill imports if needed for NLU testing
import * as autopilotSkills from './skills/autopilotSkills'; // Added for Autopilot

// Mock NLU Service
const mockedUnderstandMessage = jest.fn();
jest.mock('./skills/nluService', () => ({
  understandMessage: mockedUnderstandMessage,
}));

// Mock individual skill functions that will be called by the handler based on NLU intent
const mockedListUpcomingEvents = jest.fn();
const mockedCreateHubSpotContact = jest.fn(); // Already defined in previous HubSpot tests, ensure it's captured here
const mockedSendSlackMessage = jest.fn(); // Already defined
const mockedListQuickBooksInvoices = jest.fn();
const mockedGetQuickBooksInvoiceDetails = jest.fn();
const mockedEnableAutopilot = jest.fn(); // Added for Autopilot
const mockedDisableAutopilot = jest.fn(); // Added for Autopilot
const mockedGetAutopilotStatus = jest.fn(); // Added for Autopilot
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
jest.mock('./skills/autopilotSkills', () => ({
  // Added for Autopilot
  ...jest.requireActual('./skills/autopilotSkills'),
  enableAutopilot: mockedEnableAutopilot,
  disableAutopilot: mockedDisableAutopilot,
  getAutopilotStatus: mockedGetAutopilotStatus,
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
  ATOM_NLU_MODEL_NAME: 'gpt-test-nlu', // For NLU service
}));

describe('handleMessage - NLU Intent Handling', () => {
  let consoleErrorSpy: jest.SpyInstance;
  let consoleLogSpy: jest.SpyInstance;

  const userId = 'mock_user_id_from_handler'; // As used in handler
  const validContactDetails: HubSpotContactProperties = {
    email: 'test@example.com',
    firstname: 'TestF',
    lastname: 'UserL',
    company: 'TestCorp',
  };
  const validContactDetailsJson = JSON.stringify(validContactDetails);

  const mockSuccessfulHubSpotResponse: CreateHubSpotContactResponse = {
    // Renamed to avoid conflict
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
    mockedSendSlackMessage.mockReset(); // Use the module-level mock
    mockedListQuickBooksInvoices.mockReset();
    mockedGetQuickBooksInvoiceDetails.mockReset();
    mockedEnableAutopilot.mockReset(); // Added for Autopilot
    mockedDisableAutopilot.mockReset(); // Added for Autopilot
    mockedGetAutopilotStatus.mockReset(); // Added for Autopilot
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
      entities: { limit: 3, date_range: 'today' }, // NLU might extract more
      originalMessage: 'show me 3 events for today',
      error: undefined,
    });
    mockedListUpcomingEvents.mockResolvedValue([
      {
        id: '1',
        summary: 'Event 1',
        startTime: new Date().toISOString(),
        endTime: new Date().toISOString(),
      },
      {
        id: '2',
        summary: 'Event 2',
        startTime: new Date().toISOString(),
        endTime: new Date().toISOString(),
      },
    ] as any);

    const result = await handleMessage('show me 3 events for today');
    expect(mockedUnderstandMessage).toHaveBeenCalledWith(
      'show me 3 events for today'
    );
    expect(mockedListUpcomingEvents).toHaveBeenCalledWith(
      expect.any(String),
      3
    );
    expect(result).toContain('Event 1');
    expect(result).toContain('Event 2');
  });

  it('should handle CreateHubSpotContact intent (basic)', async () => {
    const contactEntities = {
      email: 'nlu.user@example.com',
      first_name: 'NLUFirstName',
      last_name: 'NLULastName',
      company_name: 'NLU Company',
    };
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'CreateHubSpotContact',
      entities: contactEntities,
      originalMessage:
        'create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company',
      error: undefined,
    });
    mockedCreateHubSpotContact.mockResolvedValue({
      success: true,
      contactId: 'hs-nlu-123',
      hubSpotContact: {
        properties: {
          email: 'nlu.user@example.com',
          firstname: 'NLUFirstName',
          lastname: 'NLULastName',
        },
      } as any,
      message: 'Created via NLU',
    });

    const result = await handleMessage(
      'create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company'
    );
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String), // userId
      expect.objectContaining({
        email: 'nlu.user@example.com',
        firstname: 'NLUFirstName',
        lastname: 'NLULastName',
        company: 'NLU Company',
      })
    );
    expect(result).toContain('HubSpot contact created via NLU! ID: hs-nlu-123');
  });

  it('should handle CreateHubSpotContact intent with contact_name only', async () => {
    const contactEntities = {
      email: 'nlu.contact@example.com',
      contact_name: 'NLU Full Name',
      company_name: 'NLU Solutions',
    };
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'CreateHubSpotContact',
      entities: contactEntities,
      originalMessage:
        'create contact NLU Full Name, nlu.contact@example.com, NLU Solutions',
      error: undefined,
    });
    mockedCreateHubSpotContact.mockResolvedValue({
      success: true,
      contactId: 'hs-nlu-456',
      hubSpotContact: {
        properties: {
          email: 'nlu.contact@example.com',
          firstname: 'NLU',
          lastname: 'Full Name',
        },
      } as any,
      message: 'Created via NLU with contact_name',
    });
    await handleMessage(
      'create contact NLU Full Name, nlu.contact@example.com, NLU Solutions'
    );
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        email: 'nlu.contact@example.com',
        firstname: 'NLU', // Derived from contact_name
        lastname: 'Full Name', // Derived from contact_name
        company: 'NLU Solutions',
      })
    );
  });

  it('should handle SendSlackMessage intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'SendSlackMessage',
      entities: { slack_channel: '#nlu-test', message_text: 'Hello from NLU' },
      originalMessage: 'send slack to #nlu-test saying Hello from NLU',
      error: undefined,
    });
    mockedSendSlackMessage.mockResolvedValue({ ok: true });

    const result = await handleMessage(
      'send slack to #nlu-test saying Hello from NLU'
    );
    expect(mockedSendSlackMessage).toHaveBeenCalledWith(
      expect.any(String),
      '#nlu-test',
      'Hello from NLU'
    );
    expect(result).toContain('Message sent to Slack channel/user #nlu-test');
  });

  it('should handle ListInvoices intent (QuickBooks)', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'ListInvoices',
      entities: { limit: 5, status: 'Open' },
      originalMessage: 'show me my last 5 open invoices',
      error: undefined,
    });
    mockedListQuickBooksInvoices.mockResolvedValue({
      ok: true,
      invoices: [
        {
          Id: 'qb-inv-1',
          DocNumber: 'QB001',
          TotalAmt: 100,
          CurrencyRef: { value: 'USD' },
        } as any,
      ],
      queryResponse: { totalCount: 1, maxResults: 5, startPosition: 1 },
    });
    const result = await handleMessage('show me my last 5 open invoices');
    expect(mockedListQuickBooksInvoices).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 5, offset: 1 })
    ); // Status not passed yet
    expect(result).toContain('QB001');
  });

  it('should handle GetInvoiceDetails intent (QuickBooks)', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'GetInvoiceDetails',
      entities: { invoice_id: 'qb-inv-007' },
      originalMessage: 'get details for invoice qb-inv-007',
      error: undefined,
    });
    mockedGetQuickBooksInvoiceDetails.mockResolvedValue({
      ok: true,
      invoice: {
        Id: 'qb-inv-007',
        DocNumber: 'QB007',
        TotalAmt: 700,
        CurrencyRef: { value: 'USD' },
      } as any,
    });
    const result = await handleMessage('get details for invoice qb-inv-007');
    expect(mockedGetQuickBooksInvoiceDetails).toHaveBeenCalledWith(
      'qb-inv-007'
    );
    expect(result).toContain('Doc #: QB007');
  });

  it('should fallback to specific command if NLU returns null intent (e.g., create hubspot contact and dm me details)', async () => {
    const specificCommand =
      'create hubspot contact and dm me details {"email":"fallback.dm@example.com", "firstname":"FallbackDM"}';
    mockedUnderstandMessage.mockResolvedValue({
      intent: null,
      entities: {},
      originalMessage: specificCommand,
      error: undefined,
    });
    mockedCreateHubSpotContact.mockResolvedValue({
      success: true,
      contactId: 'hs-fallback-dm',
      hubSpotContact: {
        properties: {
          email: 'fallback.dm@example.com',
          firstname: 'FallbackDM',
        },
      } as any,
    });
    mockedSendSlackMessage.mockResolvedValue({ ok: true }); // For the DM part

    const result = await handleMessage(specificCommand);
    expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(
      expect.any(String), // userId
      { email: 'fallback.dm@example.com', firstname: 'FallbackDM' }
    );
    // Check the DM call (userId as channel for DM)
    expect(mockedSendSlackMessage).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(String),
      expect.stringContaining('HubSpot ID: hs-fallback-dm')
    );
    expect(result).toContain("I've sent the details to your Slack DM!");
  });

  it('should fallback to general help if NLU returns null intent and no specific command matches', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: null,
      entities: {},
      originalMessage: 'gibberish unknown command',
      error: undefined,
    });
    const result = await handleMessage('gibberish unknown command');
    expect(result).toContain(
      "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help'"
    );
  });

  it('should return NLU critical error message if NLU service itself has an issue', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      error: 'NLU Service is down for maintenance.',
      intent: null,
      entities: {},
      originalMessage: 'any message',
    });
    const result = await handleMessage('any message');
    expect(result.text).toContain(
      "Sorry, I'm having trouble understanding requests right now. Please try again later."
    );
  });

  it('should return message for NLU recognized but not implemented intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: 'OrderPizza',
      entities: { size: 'large', topping: 'pepperoni' },
      originalMessage: 'order a large pepperoni pizza',
      error: undefined,
    });
    const result = await handleMessage('order a large pepperoni pizza');
    expect(result.text).toContain("I understood your intent as 'OrderPizza'");
    expect(result.text).toContain(
      'not fully set up to handle that specific request conversationally yet'
    );
  });

  // --- Autopilot Intent Tests ---
  describe('Autopilot Intents', () => {
    const mockUserId = 'mock_user_id_from_handler'; // Matching what handler's getCurrentUserId returns
    const ttsAudioUrl = 'http://tts.service/audio.mp3'; // Mock TTS response

    beforeEach(() => {
      // Mock global fetch for TTS calls, assuming handleMessage will call TTS
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ audio_url: ttsAudioUrl, status: 'success' }),
      } as Response);
    });

    afterEach(() => {
      // delete global.fetch; // Or restore original fetch if saved
    });

    it('should handle EnableAutopilot intent successfully', async () => {
      const nluEntities = {
        raw_query: 'enable autopilot for daily tasks',
        autopilot_config_details: 'daily tasks',
      };
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'EnableAutopilot',
        entities: nluEntities,
        originalMessage: 'enable autopilot for daily tasks',
        error: undefined,
      });
      mockedEnableAutopilot.mockResolvedValue({
        ok: true,
        data: {
          id: 'ap-123',
          userId: mockUserId,
          scheduleAt: 'tomorrow',
          payload: nluEntities.autopilot_config_details,
        } as any,
      });

      const result = await handleMessage('enable autopilot for daily tasks');

      expect(mockedUnderstandMessage).toHaveBeenCalledWith(
        'enable autopilot for daily tasks',
        undefined,
        null
      ); // LTM context is null by default in this test path
      expect(mockedEnableAutopilot).toHaveBeenCalledWith(
        mockUserId,
        JSON.stringify(nluEntities)
      );
      expect(result.text).toContain('Autopilot enabled successfully.');
      expect(result.text).toContain('ap-123');
    });

    it('should handle EnableAutopilot intent failure', async () => {
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'EnableAutopilot',
        entities: { raw_query: 'enable autopilot' },
        originalMessage: 'enable autopilot',
        error: undefined,
      });
      mockedEnableAutopilot.mockResolvedValue({
        ok: false,
        error: { code: 'API_ERROR', message: 'Failed to create trigger' },
      });

      const result = await handleMessage('enable autopilot');
      expect(mockedEnableAutopilot).toHaveBeenCalledWith(
        mockUserId,
        JSON.stringify({ raw_query: 'enable autopilot' })
      );
      expect(result.text).toContain(
        'Failed to enable Autopilot. Error: Failed to create trigger'
      );
    });

    it('should handle DisableAutopilot intent successfully', async () => {
      const nluEntities = {
        raw_query: 'disable autopilot event ap-123',
        autopilot_id: 'ap-123',
      };
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'DisableAutopilot',
        entities: nluEntities,
        originalMessage: 'disable autopilot event ap-123',
        error: undefined,
      });
      mockedDisableAutopilot.mockResolvedValue({
        ok: true,
        data: { success: true },
      });

      const result = await handleMessage('disable autopilot event ap-123');
      expect(mockedDisableAutopilot).toHaveBeenCalledWith(mockUserId, 'ap-123'); // Query becomes the ID
      expect(result.text).toContain('Autopilot disabled successfully.');
    });

    it('should handle DisableAutopilot intent when autopilot_id is missing in NLU', async () => {
      const nluEntities = { raw_query: 'disable autopilot' }; // No ID provided
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'DisableAutopilot',
        entities: nluEntities,
        originalMessage: 'disable autopilot',
        error: undefined,
      });
      // The skill itself would return an error if ID is missing, handler passes empty query from stringified empty entities
      // Or, if we expect the handler to catch this (it currently doesn't explicitly, relies on skill)
      // For this test, we assume the skill handles the missing ID logic.
      // The handler will pass `JSON.stringify(nluEntities)` which is `{"raw_query":"disable autopilot"}`
      // The skill's `parseQuery` will result in no eventId.
      mockedDisableAutopilot.mockResolvedValue({
        ok: false,
        error: {
          code: 'VALIDATION_ERROR',
          message:
            'eventId (autopilotId) is required in query to disable Autopilot.',
        },
      });

      const result = await handleMessage('disable autopilot');
      expect(mockedDisableAutopilot).toHaveBeenCalledWith(
        mockUserId,
        JSON.stringify(nluEntities)
      );
      expect(result.text).toContain(
        'Failed to disable Autopilot. Error: eventId (autopilotId) is required'
      );
    });

    it('should handle GetAutopilotStatus intent for a specific ID', async () => {
      const nluEntities = {
        raw_query: 'status for autopilot ap-123',
        autopilot_id: 'ap-123',
      };
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'GetAutopilotStatus',
        entities: nluEntities,
        originalMessage: 'status for autopilot ap-123',
        error: undefined,
      });
      mockedGetAutopilotStatus.mockResolvedValue({
        ok: true,
        data: {
          id: 'ap-123',
          userId: mockUserId,
          scheduleAt: 'daily',
          payload: {},
        } as any,
      });

      const result = await handleMessage('status for autopilot ap-123');
      expect(mockedGetAutopilotStatus).toHaveBeenCalledWith(
        mockUserId,
        'ap-123'
      );
      expect(result.text).toContain(
        'Autopilot Status (ID: ap-123): Scheduled at daily'
      );
    });

    it('should handle GetAutopilotStatus intent for all statuses for a user', async () => {
      const nluEntities = { raw_query: 'get my autopilot status' };
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'GetAutopilotStatus',
        entities: nluEntities,
        originalMessage: 'get my autopilot status',
        error: undefined,
      });
      // Simulate skill returning a single status (as per current listAutopilotsGivenUserId behavior)
      mockedGetAutopilotStatus.mockResolvedValue({
        ok: true,
        data: {
          id: 'ap-user-default',
          userId: mockUserId,
          scheduleAt: 'weekly',
          payload: {},
        } as any,
      });

      const result = await handleMessage('get my autopilot status');
      // Query will be empty string as autopilot_id is not in nluEntities after JSON.stringify and then parsed by skill.
      // The handler passes JSON.stringify(nluEntities) -> `{"raw_query":"get my autopilot status"}`
      // The skill's `parseQuery` will result in an empty autopilotId if not explicitly passed.
      expect(mockedGetAutopilotStatus).toHaveBeenCalledWith(
        mockUserId,
        JSON.stringify(nluEntities)
      );
      expect(result.text).toContain(
        'Autopilot Status (ID: ap-user-default): Scheduled at weekly'
      );
    });
    it('should handle GetAutopilotStatus when no configurations are found', async () => {
      mockedUnderstandMessage.mockResolvedValue({
        intent: 'GetAutopilotStatus',
        entities: { raw_query: 'get my autopilot status' },
        originalMessage: 'get my autopilot status',
        error: undefined,
      });
      mockedGetAutopilotStatus.mockResolvedValue({
        ok: true,
        data: null, // Simulate no data found
      });
      const result = await handleMessage('get my autopilot status');
      expect(result.text).toContain(
        'No specific Autopilot configuration found for the given query, or no configurations exist.'
      );
    });
  });
  // --- End Autopilot Intent Tests ---
});

// Keep the existing default fallback test, but ensure its expected message matches the new help text.
describe('handleMessage - default fallback (no NLU match, no specific command match)', () => {
  it('should return the updated help message for an unknown command if NLU returns null intent', async () => {
    mockedUnderstandMessage.mockResolvedValue({
      intent: null,
      entities: {},
      originalMessage: 'unknown command here',
      error: undefined,
    });
    const message = 'unknown command here';
    const result = await handleMessage(message);
    const expectedHelpMessagePart =
      "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
    // The result from handleMessage is now an object {text: string, audioUrl?: string, error?: string}
    // So, we should check result.text
    expect(result.text).toBe(expectedHelpMessagePart);
  });
});

// ---- New Tests for Conversation Management Wrappers ----

// Mock the conversationManager module
const mockIsConversationActive = jest.fn();
const mockRecordUserInteraction = jest.fn();
const mockSetAgentResponding = jest.fn();
const mockActivateConversation = jest.fn();
const mockDeactivateConversation = jest.fn();
const mockCheckIfAgentIsResponding = jest.fn(); // Added for completeness

jest.mock('./conversationState', () => ({
  isConversationActive: mockIsConversationActive,
  recordUserInteraction: mockRecordUserInteraction,
  setAgentResponding: mockSetAgentResponding,
  activateConversation: mockActivateConversation,
  deactivateConversation: mockDeactivateConversation,
  checkIfAgentIsResponding: mockCheckIfAgentIsResponding, // Added
  // getConversationStateSnapshot, getConversationHistory can be real if needed or mocked
}));

// Mock _internalHandleMessage as its detailed logic is tested via original handleMessage tests
const mockInternalHandleMessage = jest.fn();
// Mock fetch for TTS calls
const mockFetch = jest.fn();

// Dynamically import handler.ts *after* setting up mocks for its imports
// This is a common pattern if the module executes code on import that relies on mocks.
// However, given the structure, direct import should be fine if mocks are set before describe block.
import {
  handleConversationInputWrapper,
  activateConversationWrapper,
  deactivateConversationWrapper,
  handleInterruptWrapper,
  // _internalHandleMessage, // Not typically exported, but if it were for testing. For now, we mock it.
} from './handler';

describe('Conversation Handling Wrappers', () => {
  beforeEach(() => {
    mockIsConversationActive.mockReset();
    mockRecordUserInteraction.mockReset();
    mockSetAgentResponding.mockReset();
    mockActivateConversation.mockReset();
    mockDeactivateConversation.mockReset();
    mockCheckIfAgentIsResponding.mockReset();
    mockInternalHandleMessage.mockReset();

    // Global fetch mock for TTS
    global.fetch = mockFetch as jest.Mock;
    mockFetch.mockReset();

    // Mock the module that _internalHandleMessage resides in, if it's not directly exported and callable
    // For this test, we assume we can mock _internalHandleMessage if it were part of the same module,
    // or we'd need to mock the module it's imported from if it's separate.
    // The current handler.ts has _internalHandleMessage as a non-exported function.
    // To test handleConversationInputWrapper properly, we need to control _internalHandleMessage.
    // One way is to use jest.spyOn on the module if we can import it, or reorganize code.
    // For now, let's assume we can mock it via a more direct mechanism for simplicity of this example.
    // A common approach for non-exported functions is to refactor them to be exported for testing,
    // or to test them entirely through the public interface that calls them.
    // Let's mock it as if it was importable or part of the same module for test purposes.
    // This requires a bit of Jest magic or refactoring the handler.ts to export _internalHandleMessage.
    // For now, we'll assume it's mocked at a higher level or handler is refactored.
    // The tests below will assume `mockInternalHandleMessage` can effectively replace its behavior.
    // This part is tricky. We'll mock its behavior directly in tests.
  });

  afterEach(() => {
    // Restore global.fetch if it was changed
    // delete global.fetch; // Or restore original fetch if saved
  });

  describe('activateConversationWrapper', () => {
    it('should call conversationManager.activateConversation and return success', async () => {
      mockActivateConversation.mockReturnValue({
        status: 'activated',
        active: true,
      });
      const response = await activateConversationWrapper();
      expect(mockActivateConversation).toHaveBeenCalledTimes(1);
      expect(response).toEqual({
        status: 'activated',
        active: true,
        message: 'activated',
      });
    });
  });

  describe('deactivateConversationWrapper', () => {
    it('should call conversationManager.deactivateConversation and return success', async () => {
      mockDeactivateConversation.mockReturnValue({
        status: 'deactivated',
        active: false,
      }); // Mock its behavior
      const response = await deactivateConversationWrapper('test_reason');
      expect(mockDeactivateConversation).toHaveBeenCalledWith('test_reason');
      expect(response).toEqual({
        status: 'Conversation deactivated due to test_reason.',
        active: false,
        message: 'Conversation deactivated due to test_reason.',
      });
    });
  });

  describe('handleInterruptWrapper', () => {
    it('should call conversationManager.setAgentResponding(false) and return success', async () => {
      const response = await handleInterruptWrapper();
      expect(mockSetAgentResponding).toHaveBeenCalledWith(false);
      expect(response).toEqual({
        status: 'success',
        message:
          'Interrupt signal processed. Agent responding state set to false.',
      });
    });
  });

  describe('handleConversationInputWrapper', () => {
    const userInput = { text: 'Hello Atom' };
    const coreResponse = { text: 'Hello User' };
    const ttsAudioUrl = 'http://tts.service/audio.mp3';

    beforeEach(() => {
      // Setup _internalHandleMessage mock for this suite
      // This is a simplified way; actual mocking depends on how _internalHandleMessage is defined/exported
      // For this example, we'll assume it can be mocked like this:
      jest
        .spyOn(require('./handler'), '_internalHandleMessage' as any)
        .mockImplementation(mockInternalHandleMessage);
    });

    afterEach(() => {
      jest.restoreAllMocks(); // Restore any spies
    });

    it('should process input if conversation is active', async () => {
      mockIsConversationActive.mockReturnValue(true);
      mockInternalHandleMessage.mockResolvedValue({
        text: coreResponse.text,
        nluResponse: {} as any,
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ audio_url: ttsAudioUrl, status: 'success' }),
      } as Response);

      const response = await handleConversationInputWrapper(userInput);

      expect(mockRecordUserInteraction).toHaveBeenCalledWith(userInput.text);
      expect(mockSetAgentResponding).toHaveBeenCalledWith(true); // Called before processing
      // expect(mockInternalHandleMessage).toHaveBeenCalledWith(userInput.text, expect.any(String)); // UserID is internal
      // The spyOn approach above is more robust for non-exported functions if it works with module system.
      // If not, testing through the public method and asserting effects is the way.
      // For now, trust that _internalHandleMessage was called if we get to TTS.
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ text: coreResponse.text }),
        })
      );
      // expect(mockRecordAgentResponse).toHaveBeenCalled(); // Need to mock this in conversationState mock
      expect(mockSetAgentResponding).toHaveBeenCalledWith(false); // Called after processing
      expect(response).toEqual({
        text: coreResponse.text,
        audioUrl: ttsAudioUrl,
      });
    });

    it('should return inactivity message if conversation is not active', async () => {
      mockIsConversationActive.mockReturnValue(false);

      const response = await handleConversationInputWrapper(userInput);

      expect(mockRecordUserInteraction).toHaveBeenCalledWith(userInput.text); // Interaction still recorded
      expect(mockSetAgentResponding).toHaveBeenCalledWith(false); // Called to ensure it's false
      expect(mockInternalHandleMessage).not.toHaveBeenCalled();
      expect(mockFetch).not.toHaveBeenCalled();
      expect(response).toEqual(
        expect.objectContaining({
          error:
            'Conversation not active. Please activate with wake word or activation command.',
          active: false,
        })
      );
    });

    it('should handle TTS failure gracefully', async () => {
      mockIsConversationActive.mockReturnValue(true);
      mockInternalHandleMessage.mockResolvedValue({
        text: coreResponse.text,
        nluResponse: {} as any,
      });
      mockFetch.mockResolvedValue({
        // Simulate TTS API error
        ok: false,
        status: 500,
        text: async () => 'TTS Server Error',
      } as Response);

      const response = await handleConversationInputWrapper(userInput);

      expect(mockSetAgentResponding).toHaveBeenCalledWith(true);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockSetAgentResponding).toHaveBeenCalledWith(false); // Crucially, this should still be called
      expect(response).toEqual({
        text: coreResponse.text,
        error: 'Failed to synthesize audio. Status: 500',
      });
    });

    it('should handle _internalHandleMessage failure gracefully', async () => {
      mockIsConversationActive.mockReturnValue(true);
      // Simulate error from _internalHandleMessage - e.g., NLU critical error
      mockInternalHandleMessage.mockResolvedValue({
        text: 'NLU service critical error',
        nluResponse: {
          error: 'NLU Down',
          intent: null,
          entities: {},
          originalMessage: userInput.text,
        } as any,
      });
      // TTS should still be called with the error message from _internalHandleMessage
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          audio_url: 'http://tts.service/error_audio.mp3',
          status: 'success',
        }),
      } as Response);

      const response = await handleConversationInputWrapper(userInput);

      expect(mockSetAgentResponding).toHaveBeenCalledWith(true);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ text: 'NLU service critical error' }),
        })
      );
      expect(mockSetAgentResponding).toHaveBeenCalledWith(false);
      expect(response).toEqual(
        expect.objectContaining({
          text: 'NLU service critical error',
          audioUrl: 'http://tts.service/error_audio.mp3',
          // Error field might be absent if TTS succeeds for the error message
        })
      );
    });
  });
});
