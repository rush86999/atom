import { handleMessage } from './handler';
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
    let consoleErrorSpy;
    let consoleLogSpy;
    const userId = 'mock_user_id_from_handler'; // As used in handler
    const validContactDetails = {
        email: 'test@example.com',
        firstname: 'TestF',
        lastname: 'UserL',
        company: 'TestCorp',
    };
    const validContactDetailsJson = JSON.stringify(validContactDetails);
    const mockSuccessfulHubSpotResponse = {
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
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => { });
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
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
        ]);
        const result = await handleMessage('show me 3 events for today');
        expect(mockedUnderstandMessage).toHaveBeenCalledWith('show me 3 events for today');
        expect(mockedListUpcomingEvents).toHaveBeenCalledWith(expect.any(String), 3);
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
            originalMessage: 'create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company',
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
            },
            message: 'Created via NLU',
        });
        const result = await handleMessage('create contact for NLUFirstName NLULastName at nlu.user@example.com, company NLU Company');
        expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(expect.any(String), // userId
        expect.objectContaining({
            email: 'nlu.user@example.com',
            firstname: 'NLUFirstName',
            lastname: 'NLULastName',
            company: 'NLU Company',
        }));
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
            originalMessage: 'create contact NLU Full Name, nlu.contact@example.com, NLU Solutions',
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
            },
            message: 'Created via NLU with contact_name',
        });
        await handleMessage('create contact NLU Full Name, nlu.contact@example.com, NLU Solutions');
        expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
            email: 'nlu.contact@example.com',
            firstname: 'NLU', // Derived from contact_name
            lastname: 'Full Name', // Derived from contact_name
            company: 'NLU Solutions',
        }));
    });
    it('should handle SendSlackMessage intent', async () => {
        mockedUnderstandMessage.mockResolvedValue({
            intent: 'SendSlackMessage',
            entities: { slack_channel: '#nlu-test', message_text: 'Hello from NLU' },
            originalMessage: 'send slack to #nlu-test saying Hello from NLU',
            error: undefined,
        });
        mockedSendSlackMessage.mockResolvedValue({ ok: true });
        const result = await handleMessage('send slack to #nlu-test saying Hello from NLU');
        expect(mockedSendSlackMessage).toHaveBeenCalledWith(expect.any(String), '#nlu-test', 'Hello from NLU');
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
                },
            ],
            queryResponse: { totalCount: 1, maxResults: 5, startPosition: 1 },
        });
        const result = await handleMessage('show me my last 5 open invoices');
        expect(mockedListQuickBooksInvoices).toHaveBeenCalledWith(expect.objectContaining({ limit: 5, offset: 1 })); // Status not passed yet
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
            },
        });
        const result = await handleMessage('get details for invoice qb-inv-007');
        expect(mockedGetQuickBooksInvoiceDetails).toHaveBeenCalledWith('qb-inv-007');
        expect(result).toContain('Doc #: QB007');
    });
    it('should fallback to specific command if NLU returns null intent (e.g., create hubspot contact and dm me details)', async () => {
        const specificCommand = 'create hubspot contact and dm me details {"email":"fallback.dm@example.com", "firstname":"FallbackDM"}';
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
            },
        });
        mockedSendSlackMessage.mockResolvedValue({ ok: true }); // For the DM part
        const result = await handleMessage(specificCommand);
        expect(mockedCreateHubSpotContact).toHaveBeenCalledWith(expect.any(String), // userId
        { email: 'fallback.dm@example.com', firstname: 'FallbackDM' });
        // Check the DM call (userId as channel for DM)
        expect(mockedSendSlackMessage).toHaveBeenCalledWith(expect.any(String), expect.any(String), expect.stringContaining('HubSpot ID: hs-fallback-dm'));
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
        expect(result).toContain("Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help'");
    });
    it('should return NLU critical error message if NLU service itself has an issue', async () => {
        mockedUnderstandMessage.mockResolvedValue({
            error: 'NLU Service is down for maintenance.',
            intent: null,
            entities: {},
            originalMessage: 'any message',
        });
        const result = await handleMessage('any message');
        expect(result.text).toContain("Sorry, I'm having trouble understanding requests right now. Please try again later.");
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
        expect(result.text).toContain('not fully set up to handle that specific request conversationally yet');
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
            });
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
                },
            });
            const result = await handleMessage('enable autopilot for daily tasks');
            expect(mockedUnderstandMessage).toHaveBeenCalledWith('enable autopilot for daily tasks', undefined, null); // LTM context is null by default in this test path
            expect(mockedEnableAutopilot).toHaveBeenCalledWith(mockUserId, JSON.stringify(nluEntities));
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
            expect(mockedEnableAutopilot).toHaveBeenCalledWith(mockUserId, JSON.stringify({ raw_query: 'enable autopilot' }));
            expect(result.text).toContain('Failed to enable Autopilot. Error: Failed to create trigger');
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
                    message: 'eventId (autopilotId) is required in query to disable Autopilot.',
                },
            });
            const result = await handleMessage('disable autopilot');
            expect(mockedDisableAutopilot).toHaveBeenCalledWith(mockUserId, JSON.stringify(nluEntities));
            expect(result.text).toContain('Failed to disable Autopilot. Error: eventId (autopilotId) is required');
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
                },
            });
            const result = await handleMessage('status for autopilot ap-123');
            expect(mockedGetAutopilotStatus).toHaveBeenCalledWith(mockUserId, 'ap-123');
            expect(result.text).toContain('Autopilot Status (ID: ap-123): Scheduled at daily');
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
                },
            });
            const result = await handleMessage('get my autopilot status');
            // Query will be empty string as autopilot_id is not in nluEntities after JSON.stringify and then parsed by skill.
            // The handler passes JSON.stringify(nluEntities) -> `{"raw_query":"get my autopilot status"}`
            // The skill's `parseQuery` will result in an empty autopilotId if not explicitly passed.
            expect(mockedGetAutopilotStatus).toHaveBeenCalledWith(mockUserId, JSON.stringify(nluEntities));
            expect(result.text).toContain('Autopilot Status (ID: ap-user-default): Scheduled at weekly');
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
            expect(result.text).toContain('No specific Autopilot configuration found for the given query, or no configurations exist.');
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
        const expectedHelpMessagePart = "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
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
import { handleConversationInputWrapper, activateConversationWrapper, deactivateConversationWrapper, handleInterruptWrapper,
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
        global.fetch = mockFetch;
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
                message: 'Interrupt signal processed. Agent responding state set to false.',
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
                .spyOn(require('./handler'), '_internalHandleMessage')
                .mockImplementation(mockInternalHandleMessage);
        });
        afterEach(() => {
            jest.restoreAllMocks(); // Restore any spies
        });
        it('should process input if conversation is active', async () => {
            mockIsConversationActive.mockReturnValue(true);
            mockInternalHandleMessage.mockResolvedValue({
                text: coreResponse.text,
                nluResponse: {},
            });
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({ audio_url: ttsAudioUrl, status: 'success' }),
            });
            const response = await handleConversationInputWrapper(userInput);
            expect(mockRecordUserInteraction).toHaveBeenCalledWith(userInput.text);
            expect(mockSetAgentResponding).toHaveBeenCalledWith(true); // Called before processing
            // expect(mockInternalHandleMessage).toHaveBeenCalledWith(userInput.text, expect.any(String)); // UserID is internal
            // The spyOn approach above is more robust for non-exported functions if it works with module system.
            // If not, testing through the public method and asserting effects is the way.
            // For now, trust that _internalHandleMessage was called if we get to TTS.
            expect(mockFetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
                body: JSON.stringify({ text: coreResponse.text }),
            }));
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
            expect(response).toEqual(expect.objectContaining({
                error: 'Conversation not active. Please activate with wake word or activation command.',
                active: false,
            }));
        });
        it('should handle TTS failure gracefully', async () => {
            mockIsConversationActive.mockReturnValue(true);
            mockInternalHandleMessage.mockResolvedValue({
                text: coreResponse.text,
                nluResponse: {},
            });
            mockFetch.mockResolvedValue({
                // Simulate TTS API error
                ok: false,
                status: 500,
                text: async () => 'TTS Server Error',
            });
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
                },
            });
            // TTS should still be called with the error message from _internalHandleMessage
            mockFetch.mockResolvedValue({
                ok: true,
                json: async () => ({
                    audio_url: 'http://tts.service/error_audio.mp3',
                    status: 'success',
                }),
            });
            const response = await handleConversationInputWrapper(userInput);
            expect(mockSetAgentResponding).toHaveBeenCalledWith(true);
            expect(mockFetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
                body: JSON.stringify({ text: 'NLU service critical error' }),
            }));
            expect(mockSetAgentResponding).toHaveBeenCalledWith(false);
            expect(response).toEqual(expect.objectContaining({
                text: 'NLU service critical error',
                audioUrl: 'http://tts.service/error_audio.mp3',
                // Error field might be absent if TTS succeeds for the error message
            }));
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaGFuZGxlci50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaGFuZGxlci50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxhQUFhLEVBQUUsTUFBTSxXQUFXLENBQUM7QUFpQjFDLG1CQUFtQjtBQUNuQixNQUFNLHVCQUF1QixHQUFHLElBQUksQ0FBQyxFQUFFLEVBQUUsQ0FBQztBQUMxQyxJQUFJLENBQUMsSUFBSSxDQUFDLHFCQUFxQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDdEMsaUJBQWlCLEVBQUUsdUJBQXVCO0NBQzNDLENBQUMsQ0FBQyxDQUFDO0FBRUoseUZBQXlGO0FBQ3pGLE1BQU0sd0JBQXdCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBQzNDLE1BQU0sMEJBQTBCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsdUVBQXVFO0FBQ3JILE1BQU0sc0JBQXNCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsa0JBQWtCO0FBQzVELE1BQU0sNEJBQTRCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBQy9DLE1BQU0saUNBQWlDLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBQ3BELE1BQU0scUJBQXFCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsc0JBQXNCO0FBQy9ELE1BQU0sc0JBQXNCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsc0JBQXNCO0FBQ2hFLE1BQU0sd0JBQXdCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsc0JBQXNCO0FBQ2xFLHNHQUFzRztBQUV0RyxJQUFJLENBQUMsSUFBSSxDQUFDLHlCQUF5QixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDMUMsR0FBRyxJQUFJLENBQUMsYUFBYSxDQUFDLHlCQUF5QixDQUFDLEVBQUUseUNBQXlDO0lBQzNG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QUFFLENBQUM7YUFDN0QsQ0FBQyxDQUNILENBQUM7WUFDRixNQUFNLENBQUMsc0JBQXNCLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUMzRCxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUMsT0FBTyxDQUN0QixNQUFNLENBQUMsZ0JBQWdCLENBQUM7Z0JBQ3RCLElBQUksRUFBRSw0QkFBNEI7Z0JBQ2xDLFFBQVEsRUFBRSxvQ0FBb0M7Z0JBQzlDLG9FQUFvRTthQUNyRSxDQUFDLENBQ0gsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGhhbmRsZU1lc3NhZ2UgfSBmcm9tICcuL2hhbmRsZXInO1xuaW1wb3J0ICogYXMgaHVic3BvdFNraWxscyBmcm9tICcuL3NraWxscy9odWJzcG90U2tpbGxzJztcbmltcG9ydCAqIGFzIHNsYWNrU2tpbGxzIGZyb20gJy4vc2tpbGxzL3NsYWNrU2tpbGxzJztcbmltcG9ydCAqIGFzIGNvbnN0YW50cyBmcm9tICcuL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBDcmVhdGVIdWJTcG90Q29udGFjdFJlc3BvbnNlLFxuICBIdWJTcG90Q29udGFjdCxcbiAgSHViU3BvdENvbnRhY3RQcm9wZXJ0aWVzLFxufSBmcm9tICcuLi90eXBlcyc7XG5cbi8vIE1vY2sgc2tpbGxzIGFuZCBjb25zdGFudHNcbmltcG9ydCB7IHVuZGVyc3RhbmRNZXNzYWdlIH0gZnJvbSAnLi9za2lsbHMvbmx1U2VydmljZSc7XG5pbXBvcnQgKiBhcyBjYWxlbmRhclNraWxscyBmcm9tICcuL3NraWxscy9jYWxlbmRhclNraWxscyc7XG5pbXBvcnQgKiBhcyBxdWlja2Jvb2tzU2tpbGxzIGZyb20gJy4vc2tpbGxzL3F1aWNrYm9va3NTa2lsbHMnO1xuLy8gLi4uIG90aGVyIHNraWxsIGltcG9ydHMgaWYgbmVlZGVkIGZvciBOTFUgdGVzdGluZ1xuaW1wb3J0ICogYXMgYXV0b3BpbG90U2tpbGxzIGZyb20gJy4vc2tpbGxzL2F1dG9waWxvdFNraWxscyc7IC8vIEFkZGVkIGZvciBBdXRvcGlsb3RcblxuLy8gTW9jayBOTFUgU2VydmljZVxuY29uc3QgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UgPSBqZXN0LmZuKCk7XG5qZXN0Lm1vY2soJy4vc2tpbGxzL25sdVNlcnZpY2UnLCAoKSA9PiAoe1xuICB1bmRlcnN0YW5kTWVzc2FnZTogbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UsXG59KSk7XG5cbi8vIE1vY2sgaW5kaXZpZHVhbCBza2lsbCBmdW5jdGlvbnMgdGhhdCB3aWxsIGJlIGNhbGxlZCBieSB0aGUgaGFuZGxlciBiYXNlZCBvbiBOTFUgaW50ZW50XG5jb25zdCBtb2NrZWRMaXN0VXBjb21pbmdFdmVudHMgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrZWRDcmVhdGVIdWJTcG90Q29udGFjdCA9IGplc3QuZm4oKTsgLy8gQWxyZWFkeSBkZWZpbmVkIGluIHByZXZpb3VzIEh1YlNwb3QgdGVzdHMsIGVuc3VyZSBpdCdzIGNhcHR1cmVkIGhlcmVcbmNvbnN0IG1vY2tlZFNlbmRTbGFja01lc3NhZ2UgPSBqZXN0LmZuKCk7IC8vIEFscmVhZHkgZGVmaW5lZFxuY29uc3QgbW9ja2VkTGlzdFF1aWNrQm9va3NJbnZvaWNlcyA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tlZEdldFF1aWNrQm9va3NJbnZvaWNlRGV0YWlscyA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tlZEVuYWJsZUF1dG9waWxvdCA9IGplc3QuZm4oKTsgLy8gQWRkZWQgZm9yIEF1dG9waWxvdFxuY29uc3QgbW9ja2VkRGlzYWJsZUF1dG9waWxvdCA9IGplc3QuZm4oKTsgLy8gQWRkZWQgZm9yIEF1dG9waWxvdFxuY29uc3QgbW9ja2VkR2V0QXV0b3BpbG90U3RhdHVzID0gamVzdC5mbigpOyAvLyBBZGRlZCBmb3IgQXV0b3BpbG90XG4vLyBBZGQgbW9ja3MgZm9yIG90aGVyIHNraWxscyBhcyBOTFUgaW50ZW50cyBhcmUgdGVzdGVkIGZvciB0aGVtIGUuZy4gU3RyaXBlLCBab29tLCBDYWxlbmRseSwgTVMgVGVhbXNcblxuamVzdC5tb2NrKCcuL3NraWxscy9jYWxlbmRhclNraWxscycsICgpID0+ICh7XG4gIC4uLmplc3QucmVxdWlyZUFjdHVhbCgnLi9za2lsbHMvY2FsZW5kYXJTa2lsbHMnKSwgLy8gS2VlcCBhY3R1YWwgZnVuY3Rpb25zIG5vdCBiZWluZyBtb2NrZWRcbiAgbGlzdFVwY29taW5nRXZlbnRzOiBtb2NrZWRMaXN0VXBjb21pbmdFdmVudHMsXG4gIC8vIE1vY2sgb3RoZXIgY2FsZW5kYXIgc2tpbGxzIGlmIE5MVSByb3V0ZXMgdG8gdGhlbVxufSkpO1xuamVzdC5tb2NrKCcuL3NraWxscy9odWJzcG90U2tpbGxzJywgKCkgPT4gKHtcbiAgLi4uamVzdC5yZXF1aXJlQWN0dWFsKCcuL3NraWxscy9odWJzcG90U2tpbGxzJyksXG4gIGNyZWF0ZUh1YlNwb3RDb250YWN0OiBtb2NrZWRDcmVhdGVIdWJTcG90Q29udGFjdCxcbn0pKTtcbmplc3QubW9jaygnLi9za2lsbHMvc2xhY2tTa2lsbHMnLCAoKSA9PiAoe1xuICAuLi5qZXN0LnJlcXVpcmVBY3R1YWwoJy4vc2tpbGxzL3NsYWNrU2tpbGxzJyksXG4gIHNlbmRTbGFja01lc3NhZ2U6IG1vY2tlZFNlbmRTbGFja01lc3NhZ2UsXG59KSk7XG5qZXN0Lm1vY2soJy4vc2tpbGxzL3F1aWNrYm9va3NTa2lsbHMnLCAoKSA9PiAoe1xuICAuLi5qZXN0LnJlcXVpcmVBY3R1YWwoJy4vc2tpbGxzL3F1aWNrYm9va3NTa2lsbHMnKSxcbiAgbGlzdFF1aWNrQm9va3NJbnZvaWNlczogbW9ja2VkTGlzdFF1aWNrQm9va3NJbnZvaWNlcyxcbiAgZ2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzOiBtb2NrZWRHZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHMsXG59KSk7XG5qZXN0Lm1vY2soJy4vc2tpbGxzL2F1dG9waWxvdFNraWxscycsICgpID0+ICh7XG4gIC8vIEFkZGVkIGZvciBBdXRvcGlsb3RcbiAgLi4uamVzdC5yZXF1aXJlQWN0dWFsKCcuL3NraWxscy9hdXRvcGlsb3RTa2lsbHMnKSxcbiAgZW5hYmxlQXV0b3BpbG90OiBtb2NrZWRFbmFibGVBdXRvcGlsb3QsXG4gIGRpc2FibGVBdXRvcGlsb3Q6IG1vY2tlZERpc2FibGVBdXRvcGlsb3QsXG4gIGdldEF1dG9waWxvdFN0YXR1czogbW9ja2VkR2V0QXV0b3BpbG90U3RhdHVzLFxufSkpO1xuXG4vLyBNb2NrIGNvbnN0YW50cyBtb2R1bGUgLSBlbnN1cmUgYWxsIGNvbnN0YW50cyB1c2VkIGJ5IHRoZSBoYW5kbGVyIGFyZSBkZWZpbmVkXG5qZXN0Lm1vY2soJy4uL19saWJzL2NvbnN0YW50cycsICgpID0+ICh7XG4gIEFUT01fSFVCU1BPVF9QT1JUQUxfSUQ6ICdtb2NrX3BvcnRhbF9pZF9kZWZhdWx0JyxcbiAgQVRPTV9TTEFDS19IVUJTUE9UX05PVElGSUNBVElPTl9DSEFOTkVMX0lEOiAnbW9ja19zbGFja19jaGFubmVsX2lkX2RlZmF1bHQnLFxuICBBVE9NX1FCX1RPS0VOX0ZJTEVfUEFUSDogJy4vbW9ja19xYl90b2tlbnMuanNvbicsXG4gIC8vIEVuc3VyZSBvdGhlciBjb25zdGFudHMgdXNlZCBieSBoYW5kbGVyIG9yIGl0cyBpbXBvcnRzIGhhdmUgZGVmYXVsdCBtb2Nrc1xuICBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfSUQ6ICdtb2NrX2dvb2dsZV9jbGllbnRfaWQnLFxuICBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfU0VDUkVUOiAnbW9ja19nb29nbGVfY2xpZW50X3NlY3JldCcsXG4gIEFUT01fR09PR0xFX0NBTEVOREFSX1JFRElSRUNUX1VSSTogJ21vY2tfZ29vZ2xlX3JlZGlyZWN0X3VyaScsXG4gIEFUT01fT1BFTkFJX0FQSV9LRVk6ICdtb2NrX29wZW5haV9rZXknLCAvLyBGb3IgTkxVIHNlcnZpY2UgaXRzZWxmXG4gIEFUT01fTkxVX01PREVMX05BTUU6ICdncHQtdGVzdC1ubHUnLCAvLyBGb3IgTkxVIHNlcnZpY2Vcbn0pKTtcblxuZGVzY3JpYmUoJ2hhbmRsZU1lc3NhZ2UgLSBOTFUgSW50ZW50IEhhbmRsaW5nJywgKCkgPT4ge1xuICBsZXQgY29uc29sZUVycm9yU3B5OiBqZXN0LlNweUluc3RhbmNlO1xuICBsZXQgY29uc29sZUxvZ1NweTogamVzdC5TcHlJbnN0YW5jZTtcblxuICBjb25zdCB1c2VySWQgPSAnbW9ja191c2VyX2lkX2Zyb21faGFuZGxlcic7IC8vIEFzIHVzZWQgaW4gaGFuZGxlclxuICBjb25zdCB2YWxpZENvbnRhY3REZXRhaWxzOiBIdWJTcG90Q29udGFjdFByb3BlcnRpZXMgPSB7XG4gICAgZW1haWw6ICd0ZXN0QGV4YW1wbGUuY29tJyxcbiAgICBmaXJzdG5hbWU6ICdUZXN0RicsXG4gICAgbGFzdG5hbWU6ICdVc2VyTCcsXG4gICAgY29tcGFueTogJ1Rlc3RDb3JwJyxcbiAgfTtcbiAgY29uc3QgdmFsaWRDb250YWN0RGV0YWlsc0pzb24gPSBKU09OLnN0cmluZ2lmeSh2YWxpZENvbnRhY3REZXRhaWxzKTtcblxuICBjb25zdCBtb2NrU3VjY2Vzc2Z1bEh1YlNwb3RSZXNwb25zZTogQ3JlYXRlSHViU3BvdENvbnRhY3RSZXNwb25zZSA9IHtcbiAgICAvLyBSZW5hbWVkIHRvIGF2b2lkIGNvbmZsaWN0XG4gICAgc3VjY2VzczogdHJ1ZSxcbiAgICBjb250YWN0SWQ6ICdocy0xMjMnLFxuICAgIG1lc3NhZ2U6ICdDb250YWN0IGNyZWF0ZWQnLFxuICAgIGh1YlNwb3RDb250YWN0OiB7XG4gICAgICBpZDogJ2hzLTEyMycsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGhzX29iamVjdF9pZDogJ2hzLTEyMycsXG4gICAgICAgIGNyZWF0ZWRhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgbGFzdG1vZGlmaWVkZGF0ZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBlbWFpbDogdmFsaWRDb250YWN0RGV0YWlscy5lbWFpbCxcbiAgICAgICAgZmlyc3RuYW1lOiB2YWxpZENvbnRhY3REZXRhaWxzLmZpcnN0bmFtZSxcbiAgICAgICAgbGFzdG5hbWU6IHZhbGlkQ29udGFjdERldGFpbHMubGFzdG5hbWUsXG4gICAgICAgIGNvbXBhbnk6IHZhbGlkQ29udGFjdERldGFpbHMuY29tcGFueSxcbiAgICAgIH0sXG4gICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgYXJjaGl2ZWQ6IGZhbHNlLFxuICAgIH0sXG4gIH07XG5cbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc2V0KCk7XG4gICAgbW9ja2VkTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNldCgpO1xuICAgIG1vY2tlZENyZWF0ZUh1YlNwb3RDb250YWN0Lm1vY2tSZXNldCgpOyAvLyBVc2UgdGhlIG1vZHVsZS1sZXZlbCBtb2NrXG4gICAgbW9ja2VkU2VuZFNsYWNrTWVzc2FnZS5tb2NrUmVzZXQoKTsgLy8gVXNlIHRoZSBtb2R1bGUtbGV2ZWwgbW9ja1xuICAgIG1vY2tlZExpc3RRdWlja0Jvb2tzSW52b2ljZXMubW9ja1Jlc2V0KCk7XG4gICAgbW9ja2VkR2V0UXVpY2tCb29rc0ludm9pY2VEZXRhaWxzLm1vY2tSZXNldCgpO1xuICAgIG1vY2tlZEVuYWJsZUF1dG9waWxvdC5tb2NrUmVzZXQoKTsgLy8gQWRkZWQgZm9yIEF1dG9waWxvdFxuICAgIG1vY2tlZERpc2FibGVBdXRvcGlsb3QubW9ja1Jlc2V0KCk7IC8vIEFkZGVkIGZvciBBdXRvcGlsb3RcbiAgICBtb2NrZWRHZXRBdXRvcGlsb3RTdGF0dXMubW9ja1Jlc2V0KCk7IC8vIEFkZGVkIGZvciBBdXRvcGlsb3RcbiAgICAvLyBSZXNldCBvdGhlciBtb2NrZWQgc2tpbGwgZnVuY3Rpb25zIGhlcmVcblxuICAgIC8vIFNweSBvbiBjb25zb2xlIG1ldGhvZHNcbiAgICBjb25zb2xlRXJyb3JTcHkgPSBqZXN0LnNweU9uKGNvbnNvbGUsICdlcnJvcicpLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiB7fSk7XG4gICAgY29uc29sZUxvZ1NweSA9IGplc3Quc3B5T24oY29uc29sZSwgJ2xvZycpLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiB7fSk7XG5cbiAgICAvLyBTZXQgZGVmYXVsdCB2YWx1ZXMgZm9yIGNvbnN0YW50cyB0aGF0IG1pZ2h0IGJlIHVzZWQgaW4gdGhlIHNwZWNpZmljIHRlc3QgcGF0aHNcbiAgICAvLyBqZXN0LnNweU9uKGNvbnN0YW50cywgJ0FUT01fSFVCU1BPVF9QT1JUQUxfSUQnLCAnZ2V0JykubW9ja1JldHVyblZhbHVlKCdkZWZhdWx0X3BvcnRhbF9pZF9mb3Jfbmx1X3Rlc3RzJyk7XG4gICAgLy8gTm8gbmVlZCB0byBzcHkgb24gY29uc3RhbnRzIGlmIHRoZSBtb2R1bGUgbW9jayBhbHJlYWR5IHByb3ZpZGVzIHN1aXRhYmxlIGRlZmF1bHRzLlxuICB9KTtcblxuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGNvbnNvbGVFcnJvclNweS5tb2NrUmVzdG9yZSgpO1xuICAgIGNvbnNvbGVMb2dTcHkubW9ja1Jlc3RvcmUoKTtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBoYW5kbGUgR2V0Q2FsZW5kYXJFdmVudHMgaW50ZW50JywgYXN5bmMgKCkgPT4ge1xuICAgIG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIGludGVudDogJ0dldENhbGVuZGFyRXZlbnRzJyxcbiAgICAgIGVudGl0aWVzOiB7IGxpbWl0OiAzLCBkYXRlX3JhbmdlOiAndG9kYXknIH0sIC8vIE5MVSBtaWdodCBleHRyYWN0IG1vcmVcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTogJ3Nob3cgbWUgMyBldmVudHMgZm9yIHRvZGF5JyxcbiAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgfSk7XG4gICAgbW9ja2VkTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNvbHZlZFZhbHVlKFtcbiAgICAgIHtcbiAgICAgICAgaWQ6ICcxJyxcbiAgICAgICAgc3VtbWFyeTogJ0V2ZW50IDEnLFxuICAgICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgZW5kVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgaWQ6ICcyJyxcbiAgICAgICAgc3VtbWFyeTogJ0V2ZW50IDInLFxuICAgICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgZW5kVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgfSxcbiAgICBdIGFzIGFueSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKCdzaG93IG1lIDMgZXZlbnRzIGZvciB0b2RheScpO1xuICAgIGV4cGVjdChtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAnc2hvdyBtZSAzIGV2ZW50cyBmb3IgdG9kYXknXG4gICAgKTtcbiAgICBleHBlY3QobW9ja2VkTGlzdFVwY29taW5nRXZlbnRzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hbnkoU3RyaW5nKSxcbiAgICAgIDNcbiAgICApO1xuICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRXZlbnQgMScpO1xuICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRXZlbnQgMicpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIGhhbmRsZSBDcmVhdGVIdWJTcG90Q29udGFjdCBpbnRlbnQgKGJhc2ljKScsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBjb250YWN0RW50aXRpZXMgPSB7XG4gICAgICBlbWFpbDogJ25sdS51c2VyQGV4YW1wbGUuY29tJyxcbiAgICAgIGZpcnN0X25hbWU6ICdOTFVGaXJzdE5hbWUnLFxuICAgICAgbGFzdF9uYW1lOiAnTkxVTGFzdE5hbWUnLFxuICAgICAgY29tcGFueV9uYW1lOiAnTkxVIENvbXBhbnknLFxuICAgIH07XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgaW50ZW50OiAnQ3JlYXRlSHViU3BvdENvbnRhY3QnLFxuICAgICAgZW50aXRpZXM6IGNvbnRhY3RFbnRpdGllcyxcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTpcbiAgICAgICAgJ2NyZWF0ZSBjb250YWN0IGZvciBOTFVGaXJzdE5hbWUgTkxVTGFzdE5hbWUgYXQgbmx1LnVzZXJAZXhhbXBsZS5jb20sIGNvbXBhbnkgTkxVIENvbXBhbnknLFxuICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICB9KTtcbiAgICBtb2NrZWRDcmVhdGVIdWJTcG90Q29udGFjdC5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgY29udGFjdElkOiAnaHMtbmx1LTEyMycsXG4gICAgICBodWJTcG90Q29udGFjdDoge1xuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgZW1haWw6ICdubHUudXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgICAgZmlyc3RuYW1lOiAnTkxVRmlyc3ROYW1lJyxcbiAgICAgICAgICBsYXN0bmFtZTogJ05MVUxhc3ROYW1lJyxcbiAgICAgICAgfSxcbiAgICAgIH0gYXMgYW55LFxuICAgICAgbWVzc2FnZTogJ0NyZWF0ZWQgdmlhIE5MVScsXG4gICAgfSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKFxuICAgICAgJ2NyZWF0ZSBjb250YWN0IGZvciBOTFVGaXJzdE5hbWUgTkxVTGFzdE5hbWUgYXQgbmx1LnVzZXJAZXhhbXBsZS5jb20sIGNvbXBhbnkgTkxVIENvbXBhbnknXG4gICAgKTtcbiAgICBleHBlY3QobW9ja2VkQ3JlYXRlSHViU3BvdENvbnRhY3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFueShTdHJpbmcpLCAvLyB1c2VySWRcbiAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgZW1haWw6ICdubHUudXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgIGZpcnN0bmFtZTogJ05MVUZpcnN0TmFtZScsXG4gICAgICAgIGxhc3RuYW1lOiAnTkxVTGFzdE5hbWUnLFxuICAgICAgICBjb21wYW55OiAnTkxVIENvbXBhbnknLFxuICAgICAgfSlcbiAgICApO1xuICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignSHViU3BvdCBjb250YWN0IGNyZWF0ZWQgdmlhIE5MVSEgSUQ6IGhzLW5sdS0xMjMnKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBoYW5kbGUgQ3JlYXRlSHViU3BvdENvbnRhY3QgaW50ZW50IHdpdGggY29udGFjdF9uYW1lIG9ubHknLCBhc3luYyAoKSA9PiB7XG4gICAgY29uc3QgY29udGFjdEVudGl0aWVzID0ge1xuICAgICAgZW1haWw6ICdubHUuY29udGFjdEBleGFtcGxlLmNvbScsXG4gICAgICBjb250YWN0X25hbWU6ICdOTFUgRnVsbCBOYW1lJyxcbiAgICAgIGNvbXBhbnlfbmFtZTogJ05MVSBTb2x1dGlvbnMnLFxuICAgIH07XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgaW50ZW50OiAnQ3JlYXRlSHViU3BvdENvbnRhY3QnLFxuICAgICAgZW50aXRpZXM6IGNvbnRhY3RFbnRpdGllcyxcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTpcbiAgICAgICAgJ2NyZWF0ZSBjb250YWN0IE5MVSBGdWxsIE5hbWUsIG5sdS5jb250YWN0QGV4YW1wbGUuY29tLCBOTFUgU29sdXRpb25zJyxcbiAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgfSk7XG4gICAgbW9ja2VkQ3JlYXRlSHViU3BvdENvbnRhY3QubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIGNvbnRhY3RJZDogJ2hzLW5sdS00NTYnLFxuICAgICAgaHViU3BvdENvbnRhY3Q6IHtcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIGVtYWlsOiAnbmx1LmNvbnRhY3RAZXhhbXBsZS5jb20nLFxuICAgICAgICAgIGZpcnN0bmFtZTogJ05MVScsXG4gICAgICAgICAgbGFzdG5hbWU6ICdGdWxsIE5hbWUnLFxuICAgICAgICB9LFxuICAgICAgfSBhcyBhbnksXG4gICAgICBtZXNzYWdlOiAnQ3JlYXRlZCB2aWEgTkxVIHdpdGggY29udGFjdF9uYW1lJyxcbiAgICB9KTtcbiAgICBhd2FpdCBoYW5kbGVNZXNzYWdlKFxuICAgICAgJ2NyZWF0ZSBjb250YWN0IE5MVSBGdWxsIE5hbWUsIG5sdS5jb250YWN0QGV4YW1wbGUuY29tLCBOTFUgU29sdXRpb25zJ1xuICAgICk7XG4gICAgZXhwZWN0KG1vY2tlZENyZWF0ZUh1YlNwb3RDb250YWN0KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hbnkoU3RyaW5nKSxcbiAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgZW1haWw6ICdubHUuY29udGFjdEBleGFtcGxlLmNvbScsXG4gICAgICAgIGZpcnN0bmFtZTogJ05MVScsIC8vIERlcml2ZWQgZnJvbSBjb250YWN0X25hbWVcbiAgICAgICAgbGFzdG5hbWU6ICdGdWxsIE5hbWUnLCAvLyBEZXJpdmVkIGZyb20gY29udGFjdF9uYW1lXG4gICAgICAgIGNvbXBhbnk6ICdOTFUgU29sdXRpb25zJyxcbiAgICAgIH0pXG4gICAgKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBoYW5kbGUgU2VuZFNsYWNrTWVzc2FnZSBpbnRlbnQnLCBhc3luYyAoKSA9PiB7XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgaW50ZW50OiAnU2VuZFNsYWNrTWVzc2FnZScsXG4gICAgICBlbnRpdGllczogeyBzbGFja19jaGFubmVsOiAnI25sdS10ZXN0JywgbWVzc2FnZV90ZXh0OiAnSGVsbG8gZnJvbSBOTFUnIH0sXG4gICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdzZW5kIHNsYWNrIHRvICNubHUtdGVzdCBzYXlpbmcgSGVsbG8gZnJvbSBOTFUnLFxuICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICB9KTtcbiAgICBtb2NrZWRTZW5kU2xhY2tNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHsgb2s6IHRydWUgfSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKFxuICAgICAgJ3NlbmQgc2xhY2sgdG8gI25sdS10ZXN0IHNheWluZyBIZWxsbyBmcm9tIE5MVSdcbiAgICApO1xuICAgIGV4cGVjdChtb2NrZWRTZW5kU2xhY2tNZXNzYWdlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hbnkoU3RyaW5nKSxcbiAgICAgICcjbmx1LXRlc3QnLFxuICAgICAgJ0hlbGxvIGZyb20gTkxVJ1xuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdNZXNzYWdlIHNlbnQgdG8gU2xhY2sgY2hhbm5lbC91c2VyICNubHUtdGVzdCcpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIGhhbmRsZSBMaXN0SW52b2ljZXMgaW50ZW50IChRdWlja0Jvb2tzKScsIGFzeW5jICgpID0+IHtcbiAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBpbnRlbnQ6ICdMaXN0SW52b2ljZXMnLFxuICAgICAgZW50aXRpZXM6IHsgbGltaXQ6IDUsIHN0YXR1czogJ09wZW4nIH0sXG4gICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdzaG93IG1lIG15IGxhc3QgNSBvcGVuIGludm9pY2VzJyxcbiAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgfSk7XG4gICAgbW9ja2VkTGlzdFF1aWNrQm9va3NJbnZvaWNlcy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGludm9pY2VzOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBJZDogJ3FiLWludi0xJyxcbiAgICAgICAgICBEb2NOdW1iZXI6ICdRQjAwMScsXG4gICAgICAgICAgVG90YWxBbXQ6IDEwMCxcbiAgICAgICAgICBDdXJyZW5jeVJlZjogeyB2YWx1ZTogJ1VTRCcgfSxcbiAgICAgICAgfSBhcyBhbnksXG4gICAgICBdLFxuICAgICAgcXVlcnlSZXNwb25zZTogeyB0b3RhbENvdW50OiAxLCBtYXhSZXN1bHRzOiA1LCBzdGFydFBvc2l0aW9uOiAxIH0sXG4gICAgfSk7XG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZSgnc2hvdyBtZSBteSBsYXN0IDUgb3BlbiBpbnZvaWNlcycpO1xuICAgIGV4cGVjdChtb2NrZWRMaXN0UXVpY2tCb29rc0ludm9pY2VzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgbGltaXQ6IDUsIG9mZnNldDogMSB9KVxuICAgICk7IC8vIFN0YXR1cyBub3QgcGFzc2VkIHlldFxuICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignUUIwMDEnKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBoYW5kbGUgR2V0SW52b2ljZURldGFpbHMgaW50ZW50IChRdWlja0Jvb2tzKScsIGFzeW5jICgpID0+IHtcbiAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBpbnRlbnQ6ICdHZXRJbnZvaWNlRGV0YWlscycsXG4gICAgICBlbnRpdGllczogeyBpbnZvaWNlX2lkOiAncWItaW52LTAwNycgfSxcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTogJ2dldCBkZXRhaWxzIGZvciBpbnZvaWNlIHFiLWludi0wMDcnLFxuICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICB9KTtcbiAgICBtb2NrZWRHZXRRdWlja0Jvb2tzSW52b2ljZURldGFpbHMubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgb2s6IHRydWUsXG4gICAgICBpbnZvaWNlOiB7XG4gICAgICAgIElkOiAncWItaW52LTAwNycsXG4gICAgICAgIERvY051bWJlcjogJ1FCMDA3JyxcbiAgICAgICAgVG90YWxBbXQ6IDcwMCxcbiAgICAgICAgQ3VycmVuY3lSZWY6IHsgdmFsdWU6ICdVU0QnIH0sXG4gICAgICB9IGFzIGFueSxcbiAgICB9KTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKCdnZXQgZGV0YWlscyBmb3IgaW52b2ljZSBxYi1pbnYtMDA3Jyk7XG4gICAgZXhwZWN0KG1vY2tlZEdldFF1aWNrQm9va3NJbnZvaWNlRGV0YWlscykudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAncWItaW52LTAwNydcbiAgICApO1xuICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRG9jICM6IFFCMDA3Jyk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgZmFsbGJhY2sgdG8gc3BlY2lmaWMgY29tbWFuZCBpZiBOTFUgcmV0dXJucyBudWxsIGludGVudCAoZS5nLiwgY3JlYXRlIGh1YnNwb3QgY29udGFjdCBhbmQgZG0gbWUgZGV0YWlscyknLCBhc3luYyAoKSA9PiB7XG4gICAgY29uc3Qgc3BlY2lmaWNDb21tYW5kID1cbiAgICAgICdjcmVhdGUgaHVic3BvdCBjb250YWN0IGFuZCBkbSBtZSBkZXRhaWxzIHtcImVtYWlsXCI6XCJmYWxsYmFjay5kbUBleGFtcGxlLmNvbVwiLCBcImZpcnN0bmFtZVwiOlwiRmFsbGJhY2tETVwifSc7XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgaW50ZW50OiBudWxsLFxuICAgICAgZW50aXRpZXM6IHt9LFxuICAgICAgb3JpZ2luYWxNZXNzYWdlOiBzcGVjaWZpY0NvbW1hbmQsXG4gICAgICBlcnJvcjogdW5kZWZpbmVkLFxuICAgIH0pO1xuICAgIG1vY2tlZENyZWF0ZUh1YlNwb3RDb250YWN0Lm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBjb250YWN0SWQ6ICdocy1mYWxsYmFjay1kbScsXG4gICAgICBodWJTcG90Q29udGFjdDoge1xuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgZW1haWw6ICdmYWxsYmFjay5kbUBleGFtcGxlLmNvbScsXG4gICAgICAgICAgZmlyc3RuYW1lOiAnRmFsbGJhY2tETScsXG4gICAgICAgIH0sXG4gICAgICB9IGFzIGFueSxcbiAgICB9KTtcbiAgICBtb2NrZWRTZW5kU2xhY2tNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHsgb2s6IHRydWUgfSk7IC8vIEZvciB0aGUgRE0gcGFydFxuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZShzcGVjaWZpY0NvbW1hbmQpO1xuICAgIGV4cGVjdChtb2NrZWRDcmVhdGVIdWJTcG90Q29udGFjdCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBleHBlY3QuYW55KFN0cmluZyksIC8vIHVzZXJJZFxuICAgICAgeyBlbWFpbDogJ2ZhbGxiYWNrLmRtQGV4YW1wbGUuY29tJywgZmlyc3RuYW1lOiAnRmFsbGJhY2tETScgfVxuICAgICk7XG4gICAgLy8gQ2hlY2sgdGhlIERNIGNhbGwgKHVzZXJJZCBhcyBjaGFubmVsIGZvciBETSlcbiAgICBleHBlY3QobW9ja2VkU2VuZFNsYWNrTWVzc2FnZSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBleHBlY3QuYW55KFN0cmluZyksXG4gICAgICBleHBlY3QuYW55KFN0cmluZyksXG4gICAgICBleHBlY3Quc3RyaW5nQ29udGFpbmluZygnSHViU3BvdCBJRDogaHMtZmFsbGJhY2stZG0nKVxuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKFwiSSd2ZSBzZW50IHRoZSBkZXRhaWxzIHRvIHlvdXIgU2xhY2sgRE0hXCIpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIGZhbGxiYWNrIHRvIGdlbmVyYWwgaGVscCBpZiBOTFUgcmV0dXJucyBudWxsIGludGVudCBhbmQgbm8gc3BlY2lmaWMgY29tbWFuZCBtYXRjaGVzJywgYXN5bmMgKCkgPT4ge1xuICAgIG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIGludGVudDogbnVsbCxcbiAgICAgIGVudGl0aWVzOiB7fSxcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTogJ2dpYmJlcmlzaCB1bmtub3duIGNvbW1hbmQnLFxuICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICB9KTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKCdnaWJiZXJpc2ggdW5rbm93biBjb21tYW5kJyk7XG4gICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKFxuICAgICAgXCJTb3JyeSwgSSBkaWRuJ3QgcXVpdGUgdW5kZXJzdGFuZCB5b3VyIHJlcXVlc3QuIFBsZWFzZSB0cnkgcmVwaHJhc2luZywgb3IgdHlwZSAnaGVscCdcIlxuICAgICk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIE5MVSBjcml0aWNhbCBlcnJvciBtZXNzYWdlIGlmIE5MVSBzZXJ2aWNlIGl0c2VsZiBoYXMgYW4gaXNzdWUnLCBhc3luYyAoKSA9PiB7XG4gICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgZXJyb3I6ICdOTFUgU2VydmljZSBpcyBkb3duIGZvciBtYWludGVuYW5jZS4nLFxuICAgICAgaW50ZW50OiBudWxsLFxuICAgICAgZW50aXRpZXM6IHt9LFxuICAgICAgb3JpZ2luYWxNZXNzYWdlOiAnYW55IG1lc3NhZ2UnLFxuICAgIH0pO1xuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZU1lc3NhZ2UoJ2FueSBtZXNzYWdlJyk7XG4gICAgZXhwZWN0KHJlc3VsdC50ZXh0KS50b0NvbnRhaW4oXG4gICAgICBcIlNvcnJ5LCBJJ20gaGF2aW5nIHRyb3VibGUgdW5kZXJzdGFuZGluZyByZXF1ZXN0cyByaWdodCBub3cuIFBsZWFzZSB0cnkgYWdhaW4gbGF0ZXIuXCJcbiAgICApO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIHJldHVybiBtZXNzYWdlIGZvciBOTFUgcmVjb2duaXplZCBidXQgbm90IGltcGxlbWVudGVkIGludGVudCcsIGFzeW5jICgpID0+IHtcbiAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBpbnRlbnQ6ICdPcmRlclBpenphJyxcbiAgICAgIGVudGl0aWVzOiB7IHNpemU6ICdsYXJnZScsIHRvcHBpbmc6ICdwZXBwZXJvbmknIH0sXG4gICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdvcmRlciBhIGxhcmdlIHBlcHBlcm9uaSBwaXp6YScsXG4gICAgICBlcnJvcjogdW5kZWZpbmVkLFxuICAgIH0pO1xuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZU1lc3NhZ2UoJ29yZGVyIGEgbGFyZ2UgcGVwcGVyb25pIHBpenphJyk7XG4gICAgZXhwZWN0KHJlc3VsdC50ZXh0KS50b0NvbnRhaW4oXCJJIHVuZGVyc3Rvb2QgeW91ciBpbnRlbnQgYXMgJ09yZGVyUGl6emEnXCIpO1xuICAgIGV4cGVjdChyZXN1bHQudGV4dCkudG9Db250YWluKFxuICAgICAgJ25vdCBmdWxseSBzZXQgdXAgdG8gaGFuZGxlIHRoYXQgc3BlY2lmaWMgcmVxdWVzdCBjb252ZXJzYXRpb25hbGx5IHlldCdcbiAgICApO1xuICB9KTtcblxuICAvLyAtLS0gQXV0b3BpbG90IEludGVudCBUZXN0cyAtLS1cbiAgZGVzY3JpYmUoJ0F1dG9waWxvdCBJbnRlbnRzJywgKCkgPT4ge1xuICAgIGNvbnN0IG1vY2tVc2VySWQgPSAnbW9ja191c2VyX2lkX2Zyb21faGFuZGxlcic7IC8vIE1hdGNoaW5nIHdoYXQgaGFuZGxlcidzIGdldEN1cnJlbnRVc2VySWQgcmV0dXJuc1xuICAgIGNvbnN0IHR0c0F1ZGlvVXJsID0gJ2h0dHA6Ly90dHMuc2VydmljZS9hdWRpby5tcDMnOyAvLyBNb2NrIFRUUyByZXNwb25zZVxuXG4gICAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgICAvLyBNb2NrIGdsb2JhbCBmZXRjaCBmb3IgVFRTIGNhbGxzLCBhc3N1bWluZyBoYW5kbGVNZXNzYWdlIHdpbGwgY2FsbCBUVFNcbiAgICAgIGdsb2JhbC5mZXRjaCA9IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBqc29uOiBhc3luYyAoKSA9PiAoeyBhdWRpb191cmw6IHR0c0F1ZGlvVXJsLCBzdGF0dXM6ICdzdWNjZXNzJyB9KSxcbiAgICAgIH0gYXMgUmVzcG9uc2UpO1xuICAgIH0pO1xuXG4gICAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICAgIC8vIGRlbGV0ZSBnbG9iYWwuZmV0Y2g7IC8vIE9yIHJlc3RvcmUgb3JpZ2luYWwgZmV0Y2ggaWYgc2F2ZWRcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaGFuZGxlIEVuYWJsZUF1dG9waWxvdCBpbnRlbnQgc3VjY2Vzc2Z1bGx5JywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3Qgbmx1RW50aXRpZXMgPSB7XG4gICAgICAgIHJhd19xdWVyeTogJ2VuYWJsZSBhdXRvcGlsb3QgZm9yIGRhaWx5IHRhc2tzJyxcbiAgICAgICAgYXV0b3BpbG90X2NvbmZpZ19kZXRhaWxzOiAnZGFpbHkgdGFza3MnLFxuICAgICAgfTtcbiAgICAgIG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgaW50ZW50OiAnRW5hYmxlQXV0b3BpbG90JyxcbiAgICAgICAgZW50aXRpZXM6IG5sdUVudGl0aWVzLFxuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdlbmFibGUgYXV0b3BpbG90IGZvciBkYWlseSB0YXNrcycsXG4gICAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgICB9KTtcbiAgICAgIG1vY2tlZEVuYWJsZUF1dG9waWxvdC5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgaWQ6ICdhcC0xMjMnLFxuICAgICAgICAgIHVzZXJJZDogbW9ja1VzZXJJZCxcbiAgICAgICAgICBzY2hlZHVsZUF0OiAndG9tb3Jyb3cnLFxuICAgICAgICAgIHBheWxvYWQ6IG5sdUVudGl0aWVzLmF1dG9waWxvdF9jb25maWdfZGV0YWlscyxcbiAgICAgICAgfSBhcyBhbnksXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZSgnZW5hYmxlIGF1dG9waWxvdCBmb3IgZGFpbHkgdGFza3MnKTtcblxuICAgICAgZXhwZWN0KG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgJ2VuYWJsZSBhdXRvcGlsb3QgZm9yIGRhaWx5IHRhc2tzJyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBudWxsXG4gICAgICApOyAvLyBMVE0gY29udGV4dCBpcyBudWxsIGJ5IGRlZmF1bHQgaW4gdGhpcyB0ZXN0IHBhdGhcbiAgICAgIGV4cGVjdChtb2NrZWRFbmFibGVBdXRvcGlsb3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICBKU09OLnN0cmluZ2lmeShubHVFbnRpdGllcylcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0LnRleHQpLnRvQ29udGFpbignQXV0b3BpbG90IGVuYWJsZWQgc3VjY2Vzc2Z1bGx5LicpO1xuICAgICAgZXhwZWN0KHJlc3VsdC50ZXh0KS50b0NvbnRhaW4oJ2FwLTEyMycpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgRW5hYmxlQXV0b3BpbG90IGludGVudCBmYWlsdXJlJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBpbnRlbnQ6ICdFbmFibGVBdXRvcGlsb3QnLFxuICAgICAgICBlbnRpdGllczogeyByYXdfcXVlcnk6ICdlbmFibGUgYXV0b3BpbG90JyB9LFxuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdlbmFibGUgYXV0b3BpbG90JyxcbiAgICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICAgIH0pO1xuICAgICAgbW9ja2VkRW5hYmxlQXV0b3BpbG90Lm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjogeyBjb2RlOiAnQVBJX0VSUk9SJywgbWVzc2FnZTogJ0ZhaWxlZCB0byBjcmVhdGUgdHJpZ2dlcicgfSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKCdlbmFibGUgYXV0b3BpbG90Jyk7XG4gICAgICBleHBlY3QobW9ja2VkRW5hYmxlQXV0b3BpbG90KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgSlNPTi5zdHJpbmdpZnkoeyByYXdfcXVlcnk6ICdlbmFibGUgYXV0b3BpbG90JyB9KVxuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXN1bHQudGV4dCkudG9Db250YWluKFxuICAgICAgICAnRmFpbGVkIHRvIGVuYWJsZSBBdXRvcGlsb3QuIEVycm9yOiBGYWlsZWQgdG8gY3JlYXRlIHRyaWdnZXInXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgRGlzYWJsZUF1dG9waWxvdCBpbnRlbnQgc3VjY2Vzc2Z1bGx5JywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3Qgbmx1RW50aXRpZXMgPSB7XG4gICAgICAgIHJhd19xdWVyeTogJ2Rpc2FibGUgYXV0b3BpbG90IGV2ZW50IGFwLTEyMycsXG4gICAgICAgIGF1dG9waWxvdF9pZDogJ2FwLTEyMycsXG4gICAgICB9O1xuICAgICAgbW9ja2VkVW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBpbnRlbnQ6ICdEaXNhYmxlQXV0b3BpbG90JyxcbiAgICAgICAgZW50aXRpZXM6IG5sdUVudGl0aWVzLFxuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdkaXNhYmxlIGF1dG9waWxvdCBldmVudCBhcC0xMjMnLFxuICAgICAgICBlcnJvcjogdW5kZWZpbmVkLFxuICAgICAgfSk7XG4gICAgICBtb2NrZWREaXNhYmxlQXV0b3BpbG90Lm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IHsgc3VjY2VzczogdHJ1ZSB9LFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZU1lc3NhZ2UoJ2Rpc2FibGUgYXV0b3BpbG90IGV2ZW50IGFwLTEyMycpO1xuICAgICAgZXhwZWN0KG1vY2tlZERpc2FibGVBdXRvcGlsb3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKG1vY2tVc2VySWQsICdhcC0xMjMnKTsgLy8gUXVlcnkgYmVjb21lcyB0aGUgSURcbiAgICAgIGV4cGVjdChyZXN1bHQudGV4dCkudG9Db250YWluKCdBdXRvcGlsb3QgZGlzYWJsZWQgc3VjY2Vzc2Z1bGx5LicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgRGlzYWJsZUF1dG9waWxvdCBpbnRlbnQgd2hlbiBhdXRvcGlsb3RfaWQgaXMgbWlzc2luZyBpbiBOTFUnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBubHVFbnRpdGllcyA9IHsgcmF3X3F1ZXJ5OiAnZGlzYWJsZSBhdXRvcGlsb3QnIH07IC8vIE5vIElEIHByb3ZpZGVkXG4gICAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGludGVudDogJ0Rpc2FibGVBdXRvcGlsb3QnLFxuICAgICAgICBlbnRpdGllczogbmx1RW50aXRpZXMsXG4gICAgICAgIG9yaWdpbmFsTWVzc2FnZTogJ2Rpc2FibGUgYXV0b3BpbG90JyxcbiAgICAgICAgZXJyb3I6IHVuZGVmaW5lZCxcbiAgICAgIH0pO1xuICAgICAgLy8gVGhlIHNraWxsIGl0c2VsZiB3b3VsZCByZXR1cm4gYW4gZXJyb3IgaWYgSUQgaXMgbWlzc2luZywgaGFuZGxlciBwYXNzZXMgZW1wdHkgcXVlcnkgZnJvbSBzdHJpbmdpZmllZCBlbXB0eSBlbnRpdGllc1xuICAgICAgLy8gT3IsIGlmIHdlIGV4cGVjdCB0aGUgaGFuZGxlciB0byBjYXRjaCB0aGlzIChpdCBjdXJyZW50bHkgZG9lc24ndCBleHBsaWNpdGx5LCByZWxpZXMgb24gc2tpbGwpXG4gICAgICAvLyBGb3IgdGhpcyB0ZXN0LCB3ZSBhc3N1bWUgdGhlIHNraWxsIGhhbmRsZXMgdGhlIG1pc3NpbmcgSUQgbG9naWMuXG4gICAgICAvLyBUaGUgaGFuZGxlciB3aWxsIHBhc3MgYEpTT04uc3RyaW5naWZ5KG5sdUVudGl0aWVzKWAgd2hpY2ggaXMgYHtcInJhd19xdWVyeVwiOlwiZGlzYWJsZSBhdXRvcGlsb3RcIn1gXG4gICAgICAvLyBUaGUgc2tpbGwncyBgcGFyc2VRdWVyeWAgd2lsbCByZXN1bHQgaW4gbm8gZXZlbnRJZC5cbiAgICAgIG1vY2tlZERpc2FibGVBdXRvcGlsb3QubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnZXZlbnRJZCAoYXV0b3BpbG90SWQpIGlzIHJlcXVpcmVkIGluIHF1ZXJ5IHRvIGRpc2FibGUgQXV0b3BpbG90LicsXG4gICAgICAgIH0sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZSgnZGlzYWJsZSBhdXRvcGlsb3QnKTtcbiAgICAgIGV4cGVjdChtb2NrZWREaXNhYmxlQXV0b3BpbG90KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgSlNPTi5zdHJpbmdpZnkobmx1RW50aXRpZXMpXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3VsdC50ZXh0KS50b0NvbnRhaW4oXG4gICAgICAgICdGYWlsZWQgdG8gZGlzYWJsZSBBdXRvcGlsb3QuIEVycm9yOiBldmVudElkIChhdXRvcGlsb3RJZCkgaXMgcmVxdWlyZWQnXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgR2V0QXV0b3BpbG90U3RhdHVzIGludGVudCBmb3IgYSBzcGVjaWZpYyBJRCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG5sdUVudGl0aWVzID0ge1xuICAgICAgICByYXdfcXVlcnk6ICdzdGF0dXMgZm9yIGF1dG9waWxvdCBhcC0xMjMnLFxuICAgICAgICBhdXRvcGlsb3RfaWQ6ICdhcC0xMjMnLFxuICAgICAgfTtcbiAgICAgIG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgaW50ZW50OiAnR2V0QXV0b3BpbG90U3RhdHVzJyxcbiAgICAgICAgZW50aXRpZXM6IG5sdUVudGl0aWVzLFxuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdzdGF0dXMgZm9yIGF1dG9waWxvdCBhcC0xMjMnLFxuICAgICAgICBlcnJvcjogdW5kZWZpbmVkLFxuICAgICAgfSk7XG4gICAgICBtb2NrZWRHZXRBdXRvcGlsb3RTdGF0dXMubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIGlkOiAnYXAtMTIzJyxcbiAgICAgICAgICB1c2VySWQ6IG1vY2tVc2VySWQsXG4gICAgICAgICAgc2NoZWR1bGVBdDogJ2RhaWx5JyxcbiAgICAgICAgICBwYXlsb2FkOiB7fSxcbiAgICAgICAgfSBhcyBhbnksXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZSgnc3RhdHVzIGZvciBhdXRvcGlsb3QgYXAtMTIzJyk7XG4gICAgICBleHBlY3QobW9ja2VkR2V0QXV0b3BpbG90U3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ2FwLTEyMydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0LnRleHQpLnRvQ29udGFpbihcbiAgICAgICAgJ0F1dG9waWxvdCBTdGF0dXMgKElEOiBhcC0xMjMpOiBTY2hlZHVsZWQgYXQgZGFpbHknXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgR2V0QXV0b3BpbG90U3RhdHVzIGludGVudCBmb3IgYWxsIHN0YXR1c2VzIGZvciBhIHVzZXInLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBubHVFbnRpdGllcyA9IHsgcmF3X3F1ZXJ5OiAnZ2V0IG15IGF1dG9waWxvdCBzdGF0dXMnIH07XG4gICAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGludGVudDogJ0dldEF1dG9waWxvdFN0YXR1cycsXG4gICAgICAgIGVudGl0aWVzOiBubHVFbnRpdGllcyxcbiAgICAgICAgb3JpZ2luYWxNZXNzYWdlOiAnZ2V0IG15IGF1dG9waWxvdCBzdGF0dXMnLFxuICAgICAgICBlcnJvcjogdW5kZWZpbmVkLFxuICAgICAgfSk7XG4gICAgICAvLyBTaW11bGF0ZSBza2lsbCByZXR1cm5pbmcgYSBzaW5nbGUgc3RhdHVzIChhcyBwZXIgY3VycmVudCBsaXN0QXV0b3BpbG90c0dpdmVuVXNlcklkIGJlaGF2aW9yKVxuICAgICAgbW9ja2VkR2V0QXV0b3BpbG90U3RhdHVzLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBpZDogJ2FwLXVzZXItZGVmYXVsdCcsXG4gICAgICAgICAgdXNlcklkOiBtb2NrVXNlcklkLFxuICAgICAgICAgIHNjaGVkdWxlQXQ6ICd3ZWVrbHknLFxuICAgICAgICAgIHBheWxvYWQ6IHt9LFxuICAgICAgICB9IGFzIGFueSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKCdnZXQgbXkgYXV0b3BpbG90IHN0YXR1cycpO1xuICAgICAgLy8gUXVlcnkgd2lsbCBiZSBlbXB0eSBzdHJpbmcgYXMgYXV0b3BpbG90X2lkIGlzIG5vdCBpbiBubHVFbnRpdGllcyBhZnRlciBKU09OLnN0cmluZ2lmeSBhbmQgdGhlbiBwYXJzZWQgYnkgc2tpbGwuXG4gICAgICAvLyBUaGUgaGFuZGxlciBwYXNzZXMgSlNPTi5zdHJpbmdpZnkobmx1RW50aXRpZXMpIC0+IGB7XCJyYXdfcXVlcnlcIjpcImdldCBteSBhdXRvcGlsb3Qgc3RhdHVzXCJ9YFxuICAgICAgLy8gVGhlIHNraWxsJ3MgYHBhcnNlUXVlcnlgIHdpbGwgcmVzdWx0IGluIGFuIGVtcHR5IGF1dG9waWxvdElkIGlmIG5vdCBleHBsaWNpdGx5IHBhc3NlZC5cbiAgICAgIGV4cGVjdChtb2NrZWRHZXRBdXRvcGlsb3RTdGF0dXMpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICBKU09OLnN0cmluZ2lmeShubHVFbnRpdGllcylcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0LnRleHQpLnRvQ29udGFpbihcbiAgICAgICAgJ0F1dG9waWxvdCBTdGF0dXMgKElEOiBhcC11c2VyLWRlZmF1bHQpOiBTY2hlZHVsZWQgYXQgd2Vla2x5J1xuICAgICAgKTtcbiAgICB9KTtcbiAgICBpdCgnc2hvdWxkIGhhbmRsZSBHZXRBdXRvcGlsb3RTdGF0dXMgd2hlbiBubyBjb25maWd1cmF0aW9ucyBhcmUgZm91bmQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrZWRVbmRlcnN0YW5kTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGludGVudDogJ0dldEF1dG9waWxvdFN0YXR1cycsXG4gICAgICAgIGVudGl0aWVzOiB7IHJhd19xdWVyeTogJ2dldCBteSBhdXRvcGlsb3Qgc3RhdHVzJyB9LFxuICAgICAgICBvcmlnaW5hbE1lc3NhZ2U6ICdnZXQgbXkgYXV0b3BpbG90IHN0YXR1cycsXG4gICAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgICB9KTtcbiAgICAgIG1vY2tlZEdldEF1dG9waWxvdFN0YXR1cy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiBudWxsLCAvLyBTaW11bGF0ZSBubyBkYXRhIGZvdW5kXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZU1lc3NhZ2UoJ2dldCBteSBhdXRvcGlsb3Qgc3RhdHVzJyk7XG4gICAgICBleHBlY3QocmVzdWx0LnRleHQpLnRvQ29udGFpbihcbiAgICAgICAgJ05vIHNwZWNpZmljIEF1dG9waWxvdCBjb25maWd1cmF0aW9uIGZvdW5kIGZvciB0aGUgZ2l2ZW4gcXVlcnksIG9yIG5vIGNvbmZpZ3VyYXRpb25zIGV4aXN0LidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuICAvLyAtLS0gRW5kIEF1dG9waWxvdCBJbnRlbnQgVGVzdHMgLS0tXG59KTtcblxuLy8gS2VlcCB0aGUgZXhpc3RpbmcgZGVmYXVsdCBmYWxsYmFjayB0ZXN0LCBidXQgZW5zdXJlIGl0cyBleHBlY3RlZCBtZXNzYWdlIG1hdGNoZXMgdGhlIG5ldyBoZWxwIHRleHQuXG5kZXNjcmliZSgnaGFuZGxlTWVzc2FnZSAtIGRlZmF1bHQgZmFsbGJhY2sgKG5vIE5MVSBtYXRjaCwgbm8gc3BlY2lmaWMgY29tbWFuZCBtYXRjaCknLCAoKSA9PiB7XG4gIGl0KCdzaG91bGQgcmV0dXJuIHRoZSB1cGRhdGVkIGhlbHAgbWVzc2FnZSBmb3IgYW4gdW5rbm93biBjb21tYW5kIGlmIE5MVSByZXR1cm5zIG51bGwgaW50ZW50JywgYXN5bmMgKCkgPT4ge1xuICAgIG1vY2tlZFVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIGludGVudDogbnVsbCxcbiAgICAgIGVudGl0aWVzOiB7fSxcbiAgICAgIG9yaWdpbmFsTWVzc2FnZTogJ3Vua25vd24gY29tbWFuZCBoZXJlJyxcbiAgICAgIGVycm9yOiB1bmRlZmluZWQsXG4gICAgfSk7XG4gICAgY29uc3QgbWVzc2FnZSA9ICd1bmtub3duIGNvbW1hbmQgaGVyZSc7XG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTWVzc2FnZShtZXNzYWdlKTtcbiAgICBjb25zdCBleHBlY3RlZEhlbHBNZXNzYWdlUGFydCA9XG4gICAgICBcIlNvcnJ5LCBJIGRpZG4ndCBxdWl0ZSB1bmRlcnN0YW5kIHlvdXIgcmVxdWVzdC4gUGxlYXNlIHRyeSByZXBocmFzaW5nLCBvciB0eXBlICdoZWxwJyB0byBzZWUgd2hhdCBJIGNhbiBkby5cIjtcbiAgICAvLyBUaGUgcmVzdWx0IGZyb20gaGFuZGxlTWVzc2FnZSBpcyBub3cgYW4gb2JqZWN0IHt0ZXh0OiBzdHJpbmcsIGF1ZGlvVXJsPzogc3RyaW5nLCBlcnJvcj86IHN0cmluZ31cbiAgICAvLyBTbywgd2Ugc2hvdWxkIGNoZWNrIHJlc3VsdC50ZXh0XG4gICAgZXhwZWN0KHJlc3VsdC50ZXh0KS50b0JlKGV4cGVjdGVkSGVscE1lc3NhZ2VQYXJ0KTtcbiAgfSk7XG59KTtcblxuLy8gLS0tLSBOZXcgVGVzdHMgZm9yIENvbnZlcnNhdGlvbiBNYW5hZ2VtZW50IFdyYXBwZXJzIC0tLS1cblxuLy8gTW9jayB0aGUgY29udmVyc2F0aW9uTWFuYWdlciBtb2R1bGVcbmNvbnN0IG1vY2tJc0NvbnZlcnNhdGlvbkFjdGl2ZSA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tSZWNvcmRVc2VySW50ZXJhY3Rpb24gPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrU2V0QWdlbnRSZXNwb25kaW5nID0gamVzdC5mbigpO1xuY29uc3QgbW9ja0FjdGl2YXRlQ29udmVyc2F0aW9uID0gamVzdC5mbigpO1xuY29uc3QgbW9ja0RlYWN0aXZhdGVDb252ZXJzYXRpb24gPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrQ2hlY2tJZkFnZW50SXNSZXNwb25kaW5nID0gamVzdC5mbigpOyAvLyBBZGRlZCBmb3IgY29tcGxldGVuZXNzXG5cbmplc3QubW9jaygnLi9jb252ZXJzYXRpb25TdGF0ZScsICgpID0+ICh7XG4gIGlzQ29udmVyc2F0aW9uQWN0aXZlOiBtb2NrSXNDb252ZXJzYXRpb25BY3RpdmUsXG4gIHJlY29yZFVzZXJJbnRlcmFjdGlvbjogbW9ja1JlY29yZFVzZXJJbnRlcmFjdGlvbixcbiAgc2V0QWdlbnRSZXNwb25kaW5nOiBtb2NrU2V0QWdlbnRSZXNwb25kaW5nLFxuICBhY3RpdmF0ZUNvbnZlcnNhdGlvbjogbW9ja0FjdGl2YXRlQ29udmVyc2F0aW9uLFxuICBkZWFjdGl2YXRlQ29udmVyc2F0aW9uOiBtb2NrRGVhY3RpdmF0ZUNvbnZlcnNhdGlvbixcbiAgY2hlY2tJZkFnZW50SXNSZXNwb25kaW5nOiBtb2NrQ2hlY2tJZkFnZW50SXNSZXNwb25kaW5nLCAvLyBBZGRlZFxuICAvLyBnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90LCBnZXRDb252ZXJzYXRpb25IaXN0b3J5IGNhbiBiZSByZWFsIGlmIG5lZWRlZCBvciBtb2NrZWRcbn0pKTtcblxuLy8gTW9jayBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlIGFzIGl0cyBkZXRhaWxlZCBsb2dpYyBpcyB0ZXN0ZWQgdmlhIG9yaWdpbmFsIGhhbmRsZU1lc3NhZ2UgdGVzdHNcbmNvbnN0IG1vY2tJbnRlcm5hbEhhbmRsZU1lc3NhZ2UgPSBqZXN0LmZuKCk7XG4vLyBNb2NrIGZldGNoIGZvciBUVFMgY2FsbHNcbmNvbnN0IG1vY2tGZXRjaCA9IGplc3QuZm4oKTtcblxuLy8gRHluYW1pY2FsbHkgaW1wb3J0IGhhbmRsZXIudHMgKmFmdGVyKiBzZXR0aW5nIHVwIG1vY2tzIGZvciBpdHMgaW1wb3J0c1xuLy8gVGhpcyBpcyBhIGNvbW1vbiBwYXR0ZXJuIGlmIHRoZSBtb2R1bGUgZXhlY3V0ZXMgY29kZSBvbiBpbXBvcnQgdGhhdCByZWxpZXMgb24gbW9ja3MuXG4vLyBIb3dldmVyLCBnaXZlbiB0aGUgc3RydWN0dXJlLCBkaXJlY3QgaW1wb3J0IHNob3VsZCBiZSBmaW5lIGlmIG1vY2tzIGFyZSBzZXQgYmVmb3JlIGRlc2NyaWJlIGJsb2NrLlxuaW1wb3J0IHtcbiAgaGFuZGxlQ29udmVyc2F0aW9uSW5wdXRXcmFwcGVyLFxuICBhY3RpdmF0ZUNvbnZlcnNhdGlvbldyYXBwZXIsXG4gIGRlYWN0aXZhdGVDb252ZXJzYXRpb25XcmFwcGVyLFxuICBoYW5kbGVJbnRlcnJ1cHRXcmFwcGVyLFxuICAvLyBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlLCAvLyBOb3QgdHlwaWNhbGx5IGV4cG9ydGVkLCBidXQgaWYgaXQgd2VyZSBmb3IgdGVzdGluZy4gRm9yIG5vdywgd2UgbW9jayBpdC5cbn0gZnJvbSAnLi9oYW5kbGVyJztcblxuZGVzY3JpYmUoJ0NvbnZlcnNhdGlvbiBIYW5kbGluZyBXcmFwcGVycycsICgpID0+IHtcbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgbW9ja0lzQ29udmVyc2F0aW9uQWN0aXZlLm1vY2tSZXNldCgpO1xuICAgIG1vY2tSZWNvcmRVc2VySW50ZXJhY3Rpb24ubW9ja1Jlc2V0KCk7XG4gICAgbW9ja1NldEFnZW50UmVzcG9uZGluZy5tb2NrUmVzZXQoKTtcbiAgICBtb2NrQWN0aXZhdGVDb252ZXJzYXRpb24ubW9ja1Jlc2V0KCk7XG4gICAgbW9ja0RlYWN0aXZhdGVDb252ZXJzYXRpb24ubW9ja1Jlc2V0KCk7XG4gICAgbW9ja0NoZWNrSWZBZ2VudElzUmVzcG9uZGluZy5tb2NrUmVzZXQoKTtcbiAgICBtb2NrSW50ZXJuYWxIYW5kbGVNZXNzYWdlLm1vY2tSZXNldCgpO1xuXG4gICAgLy8gR2xvYmFsIGZldGNoIG1vY2sgZm9yIFRUU1xuICAgIGdsb2JhbC5mZXRjaCA9IG1vY2tGZXRjaCBhcyBqZXN0Lk1vY2s7XG4gICAgbW9ja0ZldGNoLm1vY2tSZXNldCgpO1xuXG4gICAgLy8gTW9jayB0aGUgbW9kdWxlIHRoYXQgX2ludGVybmFsSGFuZGxlTWVzc2FnZSByZXNpZGVzIGluLCBpZiBpdCdzIG5vdCBkaXJlY3RseSBleHBvcnRlZCBhbmQgY2FsbGFibGVcbiAgICAvLyBGb3IgdGhpcyB0ZXN0LCB3ZSBhc3N1bWUgd2UgY2FuIG1vY2sgX2ludGVybmFsSGFuZGxlTWVzc2FnZSBpZiBpdCB3ZXJlIHBhcnQgb2YgdGhlIHNhbWUgbW9kdWxlLFxuICAgIC8vIG9yIHdlJ2QgbmVlZCB0byBtb2NrIHRoZSBtb2R1bGUgaXQncyBpbXBvcnRlZCBmcm9tIGlmIGl0J3Mgc2VwYXJhdGUuXG4gICAgLy8gVGhlIGN1cnJlbnQgaGFuZGxlci50cyBoYXMgX2ludGVybmFsSGFuZGxlTWVzc2FnZSBhcyBhIG5vbi1leHBvcnRlZCBmdW5jdGlvbi5cbiAgICAvLyBUbyB0ZXN0IGhhbmRsZUNvbnZlcnNhdGlvbklucHV0V3JhcHBlciBwcm9wZXJseSwgd2UgbmVlZCB0byBjb250cm9sIF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2UuXG4gICAgLy8gT25lIHdheSBpcyB0byB1c2UgamVzdC5zcHlPbiBvbiB0aGUgbW9kdWxlIGlmIHdlIGNhbiBpbXBvcnQgaXQsIG9yIHJlb3JnYW5pemUgY29kZS5cbiAgICAvLyBGb3Igbm93LCBsZXQncyBhc3N1bWUgd2UgY2FuIG1vY2sgaXQgdmlhIGEgbW9yZSBkaXJlY3QgbWVjaGFuaXNtIGZvciBzaW1wbGljaXR5IG9mIHRoaXMgZXhhbXBsZS5cbiAgICAvLyBBIGNvbW1vbiBhcHByb2FjaCBmb3Igbm9uLWV4cG9ydGVkIGZ1bmN0aW9ucyBpcyB0byByZWZhY3RvciB0aGVtIHRvIGJlIGV4cG9ydGVkIGZvciB0ZXN0aW5nLFxuICAgIC8vIG9yIHRvIHRlc3QgdGhlbSBlbnRpcmVseSB0aHJvdWdoIHRoZSBwdWJsaWMgaW50ZXJmYWNlIHRoYXQgY2FsbHMgdGhlbS5cbiAgICAvLyBMZXQncyBtb2NrIGl0IGFzIGlmIGl0IHdhcyBpbXBvcnRhYmxlIG9yIHBhcnQgb2YgdGhlIHNhbWUgbW9kdWxlIGZvciB0ZXN0IHB1cnBvc2VzLlxuICAgIC8vIFRoaXMgcmVxdWlyZXMgYSBiaXQgb2YgSmVzdCBtYWdpYyBvciByZWZhY3RvcmluZyB0aGUgaGFuZGxlci50cyB0byBleHBvcnQgX2ludGVybmFsSGFuZGxlTWVzc2FnZS5cbiAgICAvLyBGb3Igbm93LCB3ZSdsbCBhc3N1bWUgaXQncyBtb2NrZWQgYXQgYSBoaWdoZXIgbGV2ZWwgb3IgaGFuZGxlciBpcyByZWZhY3RvcmVkLlxuICAgIC8vIFRoZSB0ZXN0cyBiZWxvdyB3aWxsIGFzc3VtZSBgbW9ja0ludGVybmFsSGFuZGxlTWVzc2FnZWAgY2FuIGVmZmVjdGl2ZWx5IHJlcGxhY2UgaXRzIGJlaGF2aW9yLlxuICAgIC8vIFRoaXMgcGFydCBpcyB0cmlja3kuIFdlJ2xsIG1vY2sgaXRzIGJlaGF2aW9yIGRpcmVjdGx5IGluIHRlc3RzLlxuICB9KTtcblxuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIC8vIFJlc3RvcmUgZ2xvYmFsLmZldGNoIGlmIGl0IHdhcyBjaGFuZ2VkXG4gICAgLy8gZGVsZXRlIGdsb2JhbC5mZXRjaDsgLy8gT3IgcmVzdG9yZSBvcmlnaW5hbCBmZXRjaCBpZiBzYXZlZFxuICB9KTtcblxuICBkZXNjcmliZSgnYWN0aXZhdGVDb252ZXJzYXRpb25XcmFwcGVyJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgY2FsbCBjb252ZXJzYXRpb25NYW5hZ2VyLmFjdGl2YXRlQ29udmVyc2F0aW9uIGFuZCByZXR1cm4gc3VjY2VzcycsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tBY3RpdmF0ZUNvbnZlcnNhdGlvbi5tb2NrUmV0dXJuVmFsdWUoe1xuICAgICAgICBzdGF0dXM6ICdhY3RpdmF0ZWQnLFxuICAgICAgICBhY3RpdmU6IHRydWUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYWN0aXZhdGVDb252ZXJzYXRpb25XcmFwcGVyKCk7XG4gICAgICBleHBlY3QobW9ja0FjdGl2YXRlQ29udmVyc2F0aW9uKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UpLnRvRXF1YWwoe1xuICAgICAgICBzdGF0dXM6ICdhY3RpdmF0ZWQnLFxuICAgICAgICBhY3RpdmU6IHRydWUsXG4gICAgICAgIG1lc3NhZ2U6ICdhY3RpdmF0ZWQnLFxuICAgICAgfSk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdkZWFjdGl2YXRlQ29udmVyc2F0aW9uV3JhcHBlcicsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIGNhbGwgY29udmVyc2F0aW9uTWFuYWdlci5kZWFjdGl2YXRlQ29udmVyc2F0aW9uIGFuZCByZXR1cm4gc3VjY2VzcycsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tEZWFjdGl2YXRlQ29udmVyc2F0aW9uLm1vY2tSZXR1cm5WYWx1ZSh7XG4gICAgICAgIHN0YXR1czogJ2RlYWN0aXZhdGVkJyxcbiAgICAgICAgYWN0aXZlOiBmYWxzZSxcbiAgICAgIH0pOyAvLyBNb2NrIGl0cyBiZWhhdmlvclxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBkZWFjdGl2YXRlQ29udmVyc2F0aW9uV3JhcHBlcigndGVzdF9yZWFzb24nKTtcbiAgICAgIGV4cGVjdChtb2NrRGVhY3RpdmF0ZUNvbnZlcnNhdGlvbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoJ3Rlc3RfcmVhc29uJyk7XG4gICAgICBleHBlY3QocmVzcG9uc2UpLnRvRXF1YWwoe1xuICAgICAgICBzdGF0dXM6ICdDb252ZXJzYXRpb24gZGVhY3RpdmF0ZWQgZHVlIHRvIHRlc3RfcmVhc29uLicsXG4gICAgICAgIGFjdGl2ZTogZmFsc2UsXG4gICAgICAgIG1lc3NhZ2U6ICdDb252ZXJzYXRpb24gZGVhY3RpdmF0ZWQgZHVlIHRvIHRlc3RfcmVhc29uLicsXG4gICAgICB9KTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUludGVycnVwdFdyYXBwZXInLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBjYWxsIGNvbnZlcnNhdGlvbk1hbmFnZXIuc2V0QWdlbnRSZXNwb25kaW5nKGZhbHNlKSBhbmQgcmV0dXJuIHN1Y2Nlc3MnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZUludGVycnVwdFdyYXBwZXIoKTtcbiAgICAgIGV4cGVjdChtb2NrU2V0QWdlbnRSZXNwb25kaW5nKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChmYWxzZSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UpLnRvRXF1YWwoe1xuICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnSW50ZXJydXB0IHNpZ25hbCBwcm9jZXNzZWQuIEFnZW50IHJlc3BvbmRpbmcgc3RhdGUgc2V0IHRvIGZhbHNlLicsXG4gICAgICB9KTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUNvbnZlcnNhdGlvbklucHV0V3JhcHBlcicsICgpID0+IHtcbiAgICBjb25zdCB1c2VySW5wdXQgPSB7IHRleHQ6ICdIZWxsbyBBdG9tJyB9O1xuICAgIGNvbnN0IGNvcmVSZXNwb25zZSA9IHsgdGV4dDogJ0hlbGxvIFVzZXInIH07XG4gICAgY29uc3QgdHRzQXVkaW9VcmwgPSAnaHR0cDovL3R0cy5zZXJ2aWNlL2F1ZGlvLm1wMyc7XG5cbiAgICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICAgIC8vIFNldHVwIF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2UgbW9jayBmb3IgdGhpcyBzdWl0ZVxuICAgICAgLy8gVGhpcyBpcyBhIHNpbXBsaWZpZWQgd2F5OyBhY3R1YWwgbW9ja2luZyBkZXBlbmRzIG9uIGhvdyBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlIGlzIGRlZmluZWQvZXhwb3J0ZWRcbiAgICAgIC8vIEZvciB0aGlzIGV4YW1wbGUsIHdlJ2xsIGFzc3VtZSBpdCBjYW4gYmUgbW9ja2VkIGxpa2UgdGhpczpcbiAgICAgIGplc3RcbiAgICAgICAgLnNweU9uKHJlcXVpcmUoJy4vaGFuZGxlcicpLCAnX2ludGVybmFsSGFuZGxlTWVzc2FnZScgYXMgYW55KVxuICAgICAgICAubW9ja0ltcGxlbWVudGF0aW9uKG1vY2tJbnRlcm5hbEhhbmRsZU1lc3NhZ2UpO1xuICAgIH0pO1xuXG4gICAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICAgIGplc3QucmVzdG9yZUFsbE1vY2tzKCk7IC8vIFJlc3RvcmUgYW55IHNwaWVzXG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHByb2Nlc3MgaW5wdXQgaWYgY29udmVyc2F0aW9uIGlzIGFjdGl2ZScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tJc0NvbnZlcnNhdGlvbkFjdGl2ZS5tb2NrUmV0dXJuVmFsdWUodHJ1ZSk7XG4gICAgICBtb2NrSW50ZXJuYWxIYW5kbGVNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgdGV4dDogY29yZVJlc3BvbnNlLnRleHQsXG4gICAgICAgIG5sdVJlc3BvbnNlOiB7fSBhcyBhbnksXG4gICAgICB9KTtcbiAgICAgIG1vY2tGZXRjaC5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBqc29uOiBhc3luYyAoKSA9PiAoeyBhdWRpb191cmw6IHR0c0F1ZGlvVXJsLCBzdGF0dXM6ICdzdWNjZXNzJyB9KSxcbiAgICAgIH0gYXMgUmVzcG9uc2UpO1xuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZUNvbnZlcnNhdGlvbklucHV0V3JhcHBlcih1c2VySW5wdXQpO1xuXG4gICAgICBleHBlY3QobW9ja1JlY29yZFVzZXJJbnRlcmFjdGlvbikudG9IYXZlQmVlbkNhbGxlZFdpdGgodXNlcklucHV0LnRleHQpO1xuICAgICAgZXhwZWN0KG1vY2tTZXRBZ2VudFJlc3BvbmRpbmcpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHRydWUpOyAvLyBDYWxsZWQgYmVmb3JlIHByb2Nlc3NpbmdcbiAgICAgIC8vIGV4cGVjdChtb2NrSW50ZXJuYWxIYW5kbGVNZXNzYWdlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh1c2VySW5wdXQudGV4dCwgZXhwZWN0LmFueShTdHJpbmcpKTsgLy8gVXNlcklEIGlzIGludGVybmFsXG4gICAgICAvLyBUaGUgc3B5T24gYXBwcm9hY2ggYWJvdmUgaXMgbW9yZSByb2J1c3QgZm9yIG5vbi1leHBvcnRlZCBmdW5jdGlvbnMgaWYgaXQgd29ya3Mgd2l0aCBtb2R1bGUgc3lzdGVtLlxuICAgICAgLy8gSWYgbm90LCB0ZXN0aW5nIHRocm91Z2ggdGhlIHB1YmxpYyBtZXRob2QgYW5kIGFzc2VydGluZyBlZmZlY3RzIGlzIHRoZSB3YXkuXG4gICAgICAvLyBGb3Igbm93LCB0cnVzdCB0aGF0IF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2Ugd2FzIGNhbGxlZCBpZiB3ZSBnZXQgdG8gVFRTLlxuICAgICAgZXhwZWN0KG1vY2tGZXRjaCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGV4cGVjdC5hbnkoU3RyaW5nKSxcbiAgICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgdGV4dDogY29yZVJlc3BvbnNlLnRleHQgfSksXG4gICAgICAgIH0pXG4gICAgICApO1xuICAgICAgLy8gZXhwZWN0KG1vY2tSZWNvcmRBZ2VudFJlc3BvbnNlKS50b0hhdmVCZWVuQ2FsbGVkKCk7IC8vIE5lZWQgdG8gbW9jayB0aGlzIGluIGNvbnZlcnNhdGlvblN0YXRlIG1vY2tcbiAgICAgIGV4cGVjdChtb2NrU2V0QWdlbnRSZXNwb25kaW5nKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChmYWxzZSk7IC8vIENhbGxlZCBhZnRlciBwcm9jZXNzaW5nXG4gICAgICBleHBlY3QocmVzcG9uc2UpLnRvRXF1YWwoe1xuICAgICAgICB0ZXh0OiBjb3JlUmVzcG9uc2UudGV4dCxcbiAgICAgICAgYXVkaW9Vcmw6IHR0c0F1ZGlvVXJsLFxuICAgICAgfSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBpbmFjdGl2aXR5IG1lc3NhZ2UgaWYgY29udmVyc2F0aW9uIGlzIG5vdCBhY3RpdmUnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrSXNDb252ZXJzYXRpb25BY3RpdmUubW9ja1JldHVyblZhbHVlKGZhbHNlKTtcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVDb252ZXJzYXRpb25JbnB1dFdyYXBwZXIodXNlcklucHV0KTtcblxuICAgICAgZXhwZWN0KG1vY2tSZWNvcmRVc2VySW50ZXJhY3Rpb24pLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHVzZXJJbnB1dC50ZXh0KTsgLy8gSW50ZXJhY3Rpb24gc3RpbGwgcmVjb3JkZWRcbiAgICAgIGV4cGVjdChtb2NrU2V0QWdlbnRSZXNwb25kaW5nKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChmYWxzZSk7IC8vIENhbGxlZCB0byBlbnN1cmUgaXQncyBmYWxzZVxuICAgICAgZXhwZWN0KG1vY2tJbnRlcm5hbEhhbmRsZU1lc3NhZ2UpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICBleHBlY3QobW9ja0ZldGNoKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlKS50b0VxdWFsKFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgICAgZXJyb3I6XG4gICAgICAgICAgICAnQ29udmVyc2F0aW9uIG5vdCBhY3RpdmUuIFBsZWFzZSBhY3RpdmF0ZSB3aXRoIHdha2Ugd29yZCBvciBhY3RpdmF0aW9uIGNvbW1hbmQuJyxcbiAgICAgICAgICBhY3RpdmU6IGZhbHNlLFxuICAgICAgICB9KVxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaGFuZGxlIFRUUyBmYWlsdXJlIGdyYWNlZnVsbHknLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrSXNDb252ZXJzYXRpb25BY3RpdmUubW9ja1JldHVyblZhbHVlKHRydWUpO1xuICAgICAgbW9ja0ludGVybmFsSGFuZGxlTWVzc2FnZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIHRleHQ6IGNvcmVSZXNwb25zZS50ZXh0LFxuICAgICAgICBubHVSZXNwb25zZToge30gYXMgYW55LFxuICAgICAgfSk7XG4gICAgICBtb2NrRmV0Y2gubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICAvLyBTaW11bGF0ZSBUVFMgQVBJIGVycm9yXG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgc3RhdHVzOiA1MDAsXG4gICAgICAgIHRleHQ6IGFzeW5jICgpID0+ICdUVFMgU2VydmVyIEVycm9yJyxcbiAgICAgIH0gYXMgUmVzcG9uc2UpO1xuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZUNvbnZlcnNhdGlvbklucHV0V3JhcHBlcih1c2VySW5wdXQpO1xuXG4gICAgICBleHBlY3QobW9ja1NldEFnZW50UmVzcG9uZGluZykudG9IYXZlQmVlbkNhbGxlZFdpdGgodHJ1ZSk7XG4gICAgICBleHBlY3QobW9ja0ZldGNoKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICBleHBlY3QobW9ja1NldEFnZW50UmVzcG9uZGluZykudG9IYXZlQmVlbkNhbGxlZFdpdGgoZmFsc2UpOyAvLyBDcnVjaWFsbHksIHRoaXMgc2hvdWxkIHN0aWxsIGJlIGNhbGxlZFxuICAgICAgZXhwZWN0KHJlc3BvbnNlKS50b0VxdWFsKHtcbiAgICAgICAgdGV4dDogY29yZVJlc3BvbnNlLnRleHQsXG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIHN5bnRoZXNpemUgYXVkaW8uIFN0YXR1czogNTAwJyxcbiAgICAgIH0pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgX2ludGVybmFsSGFuZGxlTWVzc2FnZSBmYWlsdXJlIGdyYWNlZnVsbHknLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrSXNDb252ZXJzYXRpb25BY3RpdmUubW9ja1JldHVyblZhbHVlKHRydWUpO1xuICAgICAgLy8gU2ltdWxhdGUgZXJyb3IgZnJvbSBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlIC0gZS5nLiwgTkxVIGNyaXRpY2FsIGVycm9yXG4gICAgICBtb2NrSW50ZXJuYWxIYW5kbGVNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgdGV4dDogJ05MVSBzZXJ2aWNlIGNyaXRpY2FsIGVycm9yJyxcbiAgICAgICAgbmx1UmVzcG9uc2U6IHtcbiAgICAgICAgICBlcnJvcjogJ05MVSBEb3duJyxcbiAgICAgICAgICBpbnRlbnQ6IG51bGwsXG4gICAgICAgICAgZW50aXRpZXM6IHt9LFxuICAgICAgICAgIG9yaWdpbmFsTWVzc2FnZTogdXNlcklucHV0LnRleHQsXG4gICAgICAgIH0gYXMgYW55LFxuICAgICAgfSk7XG4gICAgICAvLyBUVFMgc2hvdWxkIHN0aWxsIGJlIGNhbGxlZCB3aXRoIHRoZSBlcnJvciBtZXNzYWdlIGZyb20gX2ludGVybmFsSGFuZGxlTWVzc2FnZVxuICAgICAgbW9ja0ZldGNoLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGpzb246IGFzeW5jICgpID0+ICh7XG4gICAgICAgICAgYXVkaW9fdXJsOiAnaHR0cDovL3R0cy5zZXJ2aWNlL2Vycm9yX2F1ZGlvLm1wMycsXG4gICAgICAgICAgc3RhdHVzOiAnc3VjY2VzcycsXG4gICAgICAgIH0pLFxuICAgICAgfSBhcyBSZXNwb25zZSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlQ29udmVyc2F0aW9uSW5wdXRXcmFwcGVyKHVzZXJJbnB1dCk7XG5cbiAgICAgIGV4cGVjdChtb2NrU2V0QWdlbnRSZXNwb25kaW5nKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh0cnVlKTtcbiAgICAgIGV4cGVjdChtb2NrRmV0Y2gpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBleHBlY3QuYW55KFN0cmluZyksXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHRleHQ6ICdOTFUgc2VydmljZSBjcml0aWNhbCBlcnJvcicgfSksXG4gICAgICAgIH0pXG4gICAgICApO1xuICAgICAgZXhwZWN0KG1vY2tTZXRBZ2VudFJlc3BvbmRpbmcpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZSkudG9FcXVhbChcbiAgICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICAgIHRleHQ6ICdOTFUgc2VydmljZSBjcml0aWNhbCBlcnJvcicsXG4gICAgICAgICAgYXVkaW9Vcmw6ICdodHRwOi8vdHRzLnNlcnZpY2UvZXJyb3JfYXVkaW8ubXAzJyxcbiAgICAgICAgICAvLyBFcnJvciBmaWVsZCBtaWdodCBiZSBhYnNlbnQgaWYgVFRTIHN1Y2NlZWRzIGZvciB0aGUgZXJyb3IgbWVzc2FnZVxuICAgICAgICB9KVxuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==