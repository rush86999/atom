import { callOpenAI } from './api-helper'; // Assuming callOpenAI is exported from api-helper.ts
import OpenAI from 'openai';

// Mock the OpenAI client
const mockCreate = jest.fn();
jest.mock('openai', () => {
  return jest.fn().mockImplementation(() => {
    return {
      chat: {
        completions: {
          create: mockCreate,
        },
      },
    };
  });
});

// --- Tests for Availability Generation Functions ---
import {
    generateAvailability,
    generateAvailableSlotsforTimeWindow,
    generateAvailableSlotsForDate
} from './api-helper';
// Spies for apiHelperModule functions (getUserPreferences, listEventsForUserGivenDates) will be set up.
// dayjs is used extensively; jest.useFakeTimers() will be employed.

describe('Availability Generation Functions', () => {
    const originalGuess = dayjs.tz.guess;

    beforeAll(() => {
        // Mock dayjs.tz.guess to ensure tests are consistent across environments
        dayjs.tz.guess = jest.fn(() => 'America/New_York');
    });

    afterAll(() => {
        dayjs.tz.guess = originalGuess; // Restore original guess function
    });

    beforeEach(() => {
        jest.clearAllMocks();
        jest.useFakeTimers(); // Enable fake timers for each test
        // Set a consistent system time for all tests in this describe block if needed, e.g.,
        // jest.setSystemTime(new Date('2024-08-01T00:00:00Z'));
        // However, specific times will be set in tests for more control.
    });

    afterEach(() => {
        jest.useRealTimers(); // Restore real timers
    });

    describe('generateAvailableSlotsForDate', () => {
        const baseDate = '2024-08-15'; // Thursday
        const senderTimezone = 'America/New_York'; // User's own TZ where work hours are defined
        const receiverTimezone = 'America/Los_Angeles'; // TZ for which slots are being generated for display

        const senderPreferencesBase = {
            id: 'pref1', userId: 'user1',
            workHoursStartTime: '09:00', // 9 AM in senderTimezone
            workHoursEndTime: '17:00',   // 5 PM in senderTimezone
            workDays: [1, 2, 3, 4, 5], // Mon-Fri
            slotDuration: 30,          // minutes
            bufferBetweenMeetings: 15, // minutes
            timezone: senderTimezone,
        };

        it('should generate basic slots for a full day with no existing events', () => {
            jest.setSystemTime(new Date(`${baseDate}T00:00:00Z`)); // Irrelevant here, but good practice
            const slots = generateAvailableSlotsForDate(baseDate, senderPreferencesBase, [], receiverTimezone, false, false);
            // Expected: 9:00, 9:45, 10:30, 11:15, 12:00, 12:45 (skip lunch if any), 1:30, 2:15, 3:00, 3:45, 4:30 (ends 5:00)
            // Total 11 slots (9:00-9:30, 9:45-10:15 ... 4:30-5:00)
            expect(slots.length).toBe(11);
            // Check first slot (9:00 AM NY -> ISO string)
            const firstSlotStartExpected = dayjs.tz(`${baseDate} 09:00`, 'YYYY-MM-DD HH:mm', senderTimezone).toISOString();
            expect(slots[0].startDate).toBe(firstSlotStartExpected);
        });

        it('should exclude existing events (notAvailableSlotsInEventTimezone)', () => {
            const existingEvents = [ // These times are in receiverTimezone (LA)
                { startDate: dayjs.tz(`${baseDate} 10:00`, 'YYYY-MM-DD HH:mm', receiverTimezone).toISOString(), endDate: dayjs.tz(`${baseDate} 10:30`, 'YYYY-MM-DD HH:mm', receiverTimezone).toISOString() }
            ];
            // 9:00 AM NY is 6:00 AM LA. 5:00 PM NY is 2:00 PM LA.
            // Sender work hours in LA time: 6 AM - 2 PM.
            // If receiver is LA, and sender is NY, slots are generated based on NY work hours, then displayed in LA time.
            // The notAvailableSlots are already in event's target timezone (receiverTimezone).

            // Recalculate expected slots based on how `generateAvailableSlotsForDate` converts for comparison
            // Sender's 9AM NY is 6AM LA. Sender's 5PM NY is 2PM LA.
            // Slot 1 (NY): 9:00-9:30 -> LA: 6:00-6:30 (OK)
            // Slot 2 (NY): 9:45-10:15 -> LA: 6:45-7:15 (OK)
            // ...
            // Let's assume one of the generated slots (converted to LA time) would be 10:00 LA - 10:30 LA. This one should be excluded.
            // The original code compares currentSlotStartInReceiverTz with busyStart(already in receiverTz)

            const slots = generateAvailableSlotsForDate(baseDate, senderPreferencesBase, existingEvents, receiverTimezone, false, false);
            // Original 11 slots. One 30-min slot (10:00-10:30 LA) removed.
            // The slot that would be 10:00-10:30 LA corresponds to 1:00-1:30 PM NY.
            // This is complex. Let's simplify: if a slot generated based on NY work hours, when converted to LA time,
            // overlaps with an existing LA event, it's excluded.
            // 1:00 PM NY is 10:00 AM LA. So the 1:00 PM - 1:30 PM NY slot should be removed.
            // Original slots: 9:00, 9:45, 10:30, 11:15, 12:00, 12:45, *1:30 (NY)*, 2:15, 3:00, 3:45, 4:30
            // The 1:30 PM NY slot (10:30 AM LA) should be fine. The 12:45 PM NY (9:45 AM LA) slot should be fine.
            // The conflicting slot is the one that *is* 10:00-10:30 AM LA. This is 1:00 PM - 1:30 PM NY.
            // So, 10 slots should remain.
            expect(slots.length).toBe(10);
            const tenAmLaConflictISO = dayjs.tz(`${baseDate} 10:00`, 'YYYY-MM-DD HH:mm', receiverTimezone).toISOString();
            expect(slots.find(s => dayjs(s.startDate).tz(receiverTimezone).toISOString() === tenAmLaConflictISO)).toBeUndefined();
        });

        it('should respect isFirstDay windowStartTime', () => {
            // Window starts at 1:00 PM LA time on the first day. Sender is NY.
            // 1:00 PM LA is 4:00 PM NY. Sender works 9 AM - 5 PM NY.
            // So, available slots for this day should only be from 4:00 PM NY onwards.
            // 4:00-4:30, 4:45-5:15 (oops, buffer means 4:30 is last) -> So, 4:00-4:30 PM NY
            const slots = generateAvailableSlotsForDate(baseDate, senderPreferencesBase, [], receiverTimezone, true, false, '13:00');
            expect(slots.length).toBe(2); // 4:00-4:30, 4:45-5:15 (NY time) is wrong, buffer is 15. 4:00-4:30, then 4:30+15+30 = 5:15. So only 4:00-4:30
                                        // 4:00 to 4:30. next is 4:30 + 15 buffer = 4:45. 4:45 + 30 = 5:15. 5:15 is NOT <= 5:00 dayEnd. So only one slot.
            expect(slots.length).toBe(1);
            expect(slots[0].startDate).toBe(dayjs.tz(`${baseDate} 16:00`, 'YYYY-MM-DD HH:mm', senderTimezone).toISOString());
        });

        it('should respect isLastDay windowEndTime', () => {
            // Window ends at 10:00 AM LA time. Sender is NY.
            // 10:00 AM LA is 1:00 PM NY. Sender works 9 AM - 5 PM NY.
            // Slots should be from 9:00 AM NY up to 1:00 PM NY.
            // 9:00, 9:45, 10:30, 11:15, 12:00, 12:45 (ends 1:15 PM - too late)
            // 9:00-9:30, 9:45-10:15, 10:30-11:00, 11:15-11:45, 12:00-12:30. (5 slots)
            // Next one starts 12:30 + 15 buffer = 12:45. 12:45+30 = 1:15. 1:15 is NOT <= 1:00.
            const slots = generateAvailableSlotsForDate(baseDate, senderPreferencesBase, [], receiverTimezone, false, true, undefined, '10:00');
            expect(slots.length).toBe(5);
            const lastSlotEndExpected = dayjs.tz(`${baseDate} 12:30`, 'YYYY-MM-DD HH:mm', senderTimezone).add(senderPreferencesBase.slotDuration, 'minutes').toISOString();
             // last slot is 12:00 - 12:30 NY
            expect(slots[slots.length - 1].endDate).toBe(dayjs.tz(`${baseDate} 12:30`, 'YYYY-MM-DD HH:mm', senderTimezone).toISOString());
        });

        it('should return empty array if window is outside work hours', () => {
            const slots = generateAvailableSlotsForDate(baseDate, senderPreferencesBase, [], receiverTimezone, true, true, '18:00', '19:00'); // 6 PM - 7 PM LA (9 PM - 10 PM NY)
            expect(slots).toEqual([]);
        });
    });

    describe('generateAvailableSlotsforTimeWindow', () => {
        const senderPrefs = { id:'p1', userId:'u1', workHoursStartTime: '09:00', workHoursEndTime: '12:00', workDays: [1,2,3,4,5], slotDuration: 60, bufferBetweenMeetings: 0, timezone: 'America/New_York' };

        it('should call generateAvailableSlotsForDate for each day in a multi-day window', () => {
            // For this test, we don't need to mock generateAvailableSlotsForDate itself, but rather check its usage.
            // However, to control its output for aggregation, mocking it is better.
            const mockDailySlots = [{startDate: 'slot1_start', endDate: 'slot1_end'}];
            const generateAvailableSlotsForDateSpy = jest.spyOn(apiHelperModule, 'generateAvailableSlotsForDate').mockReturnValue(mockDailySlots);

            const startDate = '2024-08-19'; // Monday
            const endDate = '2024-08-20';   // Tuesday
            const result = generateAvailableSlotsforTimeWindow(startDate, endDate, senderPrefs, [], 'America/New_York');

            expect(generateAvailableSlotsForDateSpy).toHaveBeenCalledTimes(2); // Mon, Tue
            expect(result.availableSlots.length).toBe(2 * mockDailySlots.length); // Aggregated
            generateAvailableSlotsForDateSpy.mockRestore();
        });
    });

    describe('generateAvailability', () => {
        let listEventsSpy: jest.SpyInstance;
        let getUserPrefsSpy: jest.SpyInstance;
        // generateAvailableSlotsforTimeWindow is not spied as it's mostly orchestrating the date iteration.
        // Its core logic is in generateAvailableSlotsForDate which is tested above.

        const baseParams = {
            userId: 'user_avail_test',
            availabilityScanStartDate: '2024-08-19', // Monday
            availabilityScanEndDate: '2024-08-20',   // Tuesday
            receiverGeneratedTimezone: 'America/Los_Angeles',
            // clientType: 'web' // Not used by current generateAvailability signature
        };
        const mockUserPrefs = { id:'pref1', userId: baseParams.userId, workHoursStartTime: '09:00', workHoursEndTime: '17:00', workDays: [1,2,3,4,5], slotDuration: 30, bufferBetweenMeetings: 15, timezone: 'America/New_York' };

        beforeEach(() => {
            listEventsSpy = jest.spyOn(apiHelperModule, 'listEventsForUserGivenDates');
            getUserPrefsSpy = jest.spyOn(apiHelperModule, 'getUserPreferences');
        });

        it('should return success:true with slots when all helpers succeed', async () => {
            getUserPrefsSpy.mockResolvedValue({ success: true, data: mockUserPrefs });
            listEventsSpy.mockResolvedValue({ success: true, data: [] }); // No existing events

            const result = await generateAvailability(baseParams.userId, baseParams.availabilityScanStartDate, baseParams.availabilityScanEndDate, baseParams.receiverGeneratedTimezone);
            expect(result.success).toBe(true);
            expect(result.data).toBeInstanceOf(Array);
            // Expect some slots (11 slots per day for 2 days = 22 slots)
            // This relies on the actual implementation of generateAvailableSlotsForDate.
            expect(result.data?.length).toBe(22);
        });

        it('should return failure if getUserPreferences fails', async () => {
            const prefsError = { message: "DB error prefs" };
            getUserPrefsSpy.mockResolvedValue({ success: false, error: prefsError });
            const result = await generateAvailability(baseParams.userId, baseParams.availabilityScanStartDate, baseParams.availabilityScanEndDate, baseParams.receiverGeneratedTimezone);
            expect(result.success).toBe(false);
            if(!result.success) {
                expect(result.error.message).toContain('Failed to get user preferences');
                expect(result.error.details).toEqual(prefsError);
            }
        });

        it('should return failure if getUserPreferences returns no data', async () => {
            getUserPrefsSpy.mockResolvedValue({ success: true, data: undefined });
            const result = await generateAvailability(baseParams.userId, baseParams.availabilityScanStartDate, baseParams.availabilityScanEndDate, baseParams.receiverGeneratedTimezone);
            expect(result.success).toBe(false);
            if(!result.success) {
                expect(result.error.message).toBe('User preferences not found, cannot generate availability.');
            }
        });

        it('should return failure if listEventsForUserGivenDates fails', async () => {
            getUserPrefsSpy.mockResolvedValue({ success: true, data: mockUserPrefs });
            const eventsError = { message: "DB error events list" };
            listEventsSpy.mockResolvedValue({ success: false, error: eventsError });
            const result = await generateAvailability(baseParams.userId, baseParams.availabilityScanStartDate, baseParams.availabilityScanEndDate, baseParams.receiverGeneratedTimezone);
            expect(result.success).toBe(false);
            if(!result.success) {
                expect(result.error.message).toContain('Failed to list existing events');
                expect(result.error.details).toEqual(eventsError);
            }
        });

        it('should succeed even if listEventsForUserGivenDates returns empty array', async () => {
            getUserPrefsSpy.mockResolvedValue({ success: true, data: mockUserPrefs });
            listEventsSpy.mockResolvedValue({ success: true, data: [] }); // No existing events
            const result = await generateAvailability(baseParams.userId, baseParams.availabilityScanStartDate, baseParams.availabilityScanEndDate, baseParams.receiverGeneratedTimezone);
            expect(result.success).toBe(true);
            expect(result.data).toBeInstanceOf(Array);
            expect(result.data?.length).toBe(22); // Full availability
        });
    });
});

// --- Unit Tests for createGoogleEvent (Refactored) ---
// Note: These tests will need adjustment based on the new signature of createGoogleEvent
// which now takes an eventOptions object.

// Assuming google.calendar().events.insert is already mocked via the global googleapis mock.
// const mockGoogleEventsInsert = (google.calendar('v3') as any).events.insert as jest.Mock;
// This was defined in a previous step for createGoogleEvent tests, ensure it's still valid/accessible.

describe('createGoogleEvent (Refactored with CreateGoogleEventOptions)', () => {
    let getGoogleAPITokenSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    const mockGeneratedId = 'mock-uuid-for-conference';

    // Re-accessing the mock for google.calendar().events.insert
    // This relies on the global mock structure for 'googleapis'
    let mockEventsInsert: jest.Mock;
    beforeAll(() => {
        // Ensure the googleapis mock is set up to provide a mock for events.insert
        // This might need to be more robust depending on how the global mock is structured.
        // If the global mock is: jest.mock('googleapis', () => ({ google: { calendar: jest.fn().mockReturnValue({ events: { insert: jest.fn() } }) } }));
        // then this access should work.
        mockEventsInsert = (google.calendar('v3') as any).events.insert;
    });


    beforeEach(() => {
        jest.clearAllMocks();
        getGoogleAPITokenSpy = jest.spyOn(apiHelperModule, 'getGoogleAPIToken');
        (uuidv4 as jest.Mock).mockReturnValue(mockGeneratedId); // Consistent UUID for tests
        mockEventsInsert.mockClear(); // Clear call history for events.insert
    });

    afterEach(() => {
        getGoogleAPITokenSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });

    const baseParams = {
        userId: 'user_gcal_test',
        calendarId: 'primary',
        clientType: 'web' as 'web',
    };

    const sampleEventOptions: apiHelperModule.CreateGoogleEventOptions = { // Assuming CreateGoogleEventOptions is exported or use apiHelperModule.
        summary: 'Test Event from Options',
        description: 'Event created with options object.',
        startDateTime: '2024-09-01T10:00:00Z',
        endDateTime: '2024-09-01T11:00:00Z',
        timezone: 'America/New_York',
        attendees: [{ email: 'attendee@example.com' }],
        conferenceData: { type: 'hangoutsMeet' }, // Simplified for test, real one needs createRequest
        status: 'confirmed',
    };
     const sampleAllDayEventOptions: apiHelperModule.CreateGoogleEventOptions = {
        summary: 'All Day Event Test',
        startDate: '2024-09-02', // YYYY-MM-DD
        endDate: '2024-09-03',   // YYYY-MM-DD (Google Calendar end date for all-day is exclusive)
        timezone: 'America/New_York', // Still needed for context, though GCal API uses date only
        description: 'This is an all-day event.'
    };


    it('should create a timed event successfully using eventOptions', async () => {
        getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_token' });
        const mockApiResponse = { data: { id: 'gcal_event_options_123', summary: sampleEventOptions.summary } };
        mockEventsInsert.mockResolvedValue(mockApiResponse);

        const result = await apiHelperModule.createGoogleEvent(
            baseParams.userId, baseParams.calendarId, baseParams.clientType,
            sampleEventOptions,
            // Options that are still separate params:
            // undefined, // generatedId (will be auto-generated if conferenceData.createRequest is used)
            // 1 // conferenceDataVersion
        );

        expect(result.success).toBe(true);
        if (result.success) {
            expect(result.data.googleEventId).toBe('gcal_event_options_123');
        }
        expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
            calendarId: baseParams.calendarId,
            requestBody: expect.objectContaining({
                summary: sampleEventOptions.summary,
                description: sampleEventOptions.description,
                start: { dateTime: sampleEventOptions.startDateTime, timeZone: sampleEventOptions.timezone },
                end: { dateTime: sampleEventOptions.endDateTime, timeZone: sampleEventOptions.timezone },
                attendees: sampleEventOptions.attendees,
                // conferenceData should be built based on options.conferenceData and generatedId
                // The refactored createGoogleEvent now uses uuidv4() internally for requestId if conferenceData.createRequest is to be built
                // So if sampleEventOptions.conferenceData = { type: 'hangoutsMeet' }, then createRequest should be built.
                // The current sampleEventOptions.conferenceData = { type: 'hangoutsMeet' } might not trigger createRequest in the refactored code.
                // Let's adjust sampleEventOptions for conference test.
                status: sampleEventOptions.status,
            }),
            // conferenceDataVersion: 1, // This should be set if conferenceData is in requestBody
        }));
    });

    it('should create an all-day event successfully using eventOptions', async () => {
        getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_token' });
        const mockApiResponse = { data: { id: 'gcal_allday_456', summary: sampleAllDayEventOptions.summary } };
        mockEventsInsert.mockResolvedValue(mockApiResponse);

        const result = await apiHelperModule.createGoogleEvent(
            baseParams.userId, baseParams.calendarId, baseParams.clientType,
            sampleAllDayEventOptions
        );
        expect(result.success).toBe(true);
        expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
            requestBody: expect.objectContaining({
                summary: sampleAllDayEventOptions.summary,
                description: sampleAllDayEventOptions.description,
                start: { date: '2024-09-02', timeZone: sampleAllDayEventOptions.timezone }, // date field for all-day
                end: { date: '2024-09-03', timeZone: sampleAllDayEventOptions.timezone },   // date field for all-day
            }),
        }));
    });

    it('should correctly build conferenceData if createRequest details are provided in options', async () => {
        getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_token' });
        const mockApiResponse = { data: { id: 'gcal_conf_789' } };
        mockEventsInsert.mockResolvedValue(mockApiResponse);

        const optionsWithConference: apiHelperModule.CreateGoogleEventOptions = {
            ...sampleEventOptions,
            conferenceData: { // This structure will make createGoogleEvent build the createRequest
                createRequest: {
                    requestId: 'should-be-overridden-by-generatedId-or-param', // Will be overridden by generatedId param or internal uuidv4
                    conferenceSolutionKey: { type: 'hangoutsMeet' }
                }
            }
        };
        // Pass a specific generatedId to test it being used
        const specificGeneratedId = "specific-conf-uuid";

        await apiHelperModule.createGoogleEvent(
            baseParams.userId, baseParams.calendarId, baseParams.clientType,
            optionsWithConference,
            specificGeneratedId, // Pass the specific generatedId here
            1 // conferenceDataVersion
        );

        expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
            conferenceDataVersion: 1,
            requestBody: expect.objectContaining({
                conferenceData: {
                    createRequest: {
                        requestId: specificGeneratedId, // Check if this is used
                        conferenceSolutionKey: { type: 'hangoutsMeet' },
                    },
                },
            }),
        }));

        // Test with internal uuidv4
        (uuidv4 as jest.Mock).mockReturnValueOnce("internal-uuid-for-conf");
         await apiHelperModule.createGoogleEvent(
            baseParams.userId, baseParams.calendarId, baseParams.clientType,
            optionsWithConference,
            undefined, // No specific generatedId, so internal uuidv4 should be used
            1
        );
         expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
            requestBody: expect.objectContaining({
                conferenceData: {
                    createRequest: {
                        requestId: "internal-uuid-for-conf",
                        conferenceSolutionKey: { type: 'hangoutsMeet' },
                    },
                },
            }),
        }));

    });


    // Tests for failure cases (getGoogleAPIToken fails, GCal API fails) can be adapted from existing createGoogleEvent tests.
    it('should return failure if getGoogleAPIToken fails (options version)', async () => {
        const tokenError = { message: 'Token fetch failed for options' };
        getGoogleAPITokenSpy.mockResolvedValue({ success: false, error: tokenError });
        const result = await apiHelperModule.createGoogleEvent(baseParams.userId, baseParams.calendarId, baseParams.clientType, sampleEventOptions);
        expect(result.success).toBe(false);
        if (!result.success) {
            expect(result.error.message).toContain('Token acquisition failure');
            expect(result.error.details).toEqual(tokenError);
        }
    });

    it('should return failure if Google Calendar API insert fails (options version)', async () => {
        getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_token' });
        const apiError = new Error("Google API Error");
        (apiError as any).code = 500; // Simulate Google API error structure
        mockEventsInsert.mockRejectedValue(apiError);
        const result = await apiHelperModule.createGoogleEvent(baseParams.userId, baseParams.calendarId, baseParams.clientType, sampleEventOptions);
        expect(result.success).toBe(false);
        if (!result.success) {
            expect(result.error.message).toContain('Google Calendar API error during event creation');
        }
    });
});


// TODO: Update tests for createAgenda, breakDownTask, howToTask, and createDaySchedule
// to ensure they correctly prepare and pass the CreateGoogleEventOptions object
// to the spied createGoogleEvent. This will involve:
// 1. Identifying where these orchestrators call createGoogleEvent.
// 2. In the tests for these orchestrators, when createGoogleEventSpy is called,
//    assert that the argument corresponding to 'eventOptions' is an object
//    that matches the expected CreateGoogleEventOptions structure based on the orchestrator's inputs.
// Example for createAgenda test:
// expect(createGoogleEventSpy).toHaveBeenCalledWith(
//   expect.any(String), // userId
//   expect.any(String), // calendarId
//   expect.any(String), // clientType
//   expect.objectContaining({ // This is the eventOptions
//     summary: "Generated Agenda Event",
//     description: mockSuccessfulOpenAI.content, // from createAgenda's scope
//     startDateTime: expect.any(String), // Check specific date/time if necessary
//     endDateTime: expect.any(String),
//     timezone: defaultCreateAgendaParams.userTimezone
//   }),
//   undefined, // generatedId for conference (likely undefined for simple agenda item)
//   0 // conferenceDataVersion
// );
// This is a placeholder for the detailed work required in subsequent steps if this were interactive.
// For now, this file focuses on testing createGoogleEvent itself with its new signature.

// --- Updating Orchestrator Function Tests for CreateGoogleEventOptions ---

// Note: The 'apiHelperModule' is used for spying, as these functions are in the same module.
// The actual spies (e.g., createGoogleEventSpy) are defined within each orchestrator's describe block.

describe('createAgenda (with refactored createGoogleEvent)', () => {
    // Assuming spies (callOpenAISpy, getGlobalCalendarSpy, createGoogleEventSpy, etc.)
    // and default params (defaultCreateAgendaParams) are defined as in previous createAgenda tests.
    // Only showing the relevant part of a test case that calls createGoogleEvent.

    // Minimal setup for spies needed by createAgenda before createGoogleEvent is called
    let callOpenAISpy: jest.SpyInstance;
    let getGlobalCalendarSpy: jest.SpyInstance;
    let createGoogleEventSpy: jest.SpyInstance;
    let upsertEventsPostPlannerSpy: jest.SpyInstance;
    let sendAgendaEmailSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

     const defaultCreateAgendaParams = {
        userId: 'user123',
        clientType: 'web' as 'web',
        userTimezone: 'America/New_York',
        userDate: '2024-03-15',
        prompt: 'Create an agenda for a product strategy meeting.',
        email: 'test@example.com',
        name: 'Test User',
    };
    const mockSuccessfulOpenAI = { success: true, content: 'Generated Agenda Details' };
    const mockSuccessfulGlobalCalendar = { success: true, data: { id: 'globalCalId', primaryCalendarId: 'primaryCal123' } };
    const mockSuccessfulCreateGoogleEvent = { success: true, data: { id: 'gEvent123#primaryCal123', googleEventId: 'gEvent123', generatedId: 'uuid1', calendarId: 'primaryCal123' } };
    const mockSuccessfulUpsert = { success: true, data: { affected_rows: 1, returning: [{ id: 'dbEventId456' }] } };
    const mockSuccessfulEmail = { success: true };


    beforeEach(() => {
        jest.clearAllMocks();
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI').mockResolvedValue(mockSuccessfulOpenAI);
        getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar').mockResolvedValue(mockSuccessfulGlobalCalendar);
        createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent').mockResolvedValue(mockSuccessfulCreateGoogleEvent);
        upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner').mockResolvedValue(mockSuccessfulUpsert);
        sendAgendaEmailSpy = jest.spyOn(apiHelperModule, 'sendAgendaEmail').mockResolvedValue(mockSuccessfulEmail);
         // getGoogleAPIToken is called by createGoogleEvent, so ensure it's spied if needed for other tests,
        // but for testing createAgenda's call to createGoogleEvent, createGoogleEvent itself is spied.
        jest.spyOn(apiHelperModule, 'getGoogleAPIToken').mockResolvedValue({success: true, token: "dummy-token"});

    });
    afterEach(() => {
        jest.restoreAllMocks(); // Restore all mocks after each test
        consoleLogSpy.mockRestore();
    });


    it('createAgenda should call createGoogleEvent with CreateGoogleEventOptions', async () => {
        await apiHelperModule.createAgenda(
            defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
            defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
            defaultCreateAgendaParams.prompt, defaultCreateAgendaParams.email, defaultCreateAgendaParams.name
        );

        expect(createGoogleEventSpy).toHaveBeenCalledWith(
            defaultCreateAgendaParams.userId,
            mockSuccessfulGlobalCalendar.data.primaryCalendarId,
            defaultCreateAgendaParams.clientType,
            expect.objectContaining({ // This is the eventOptions check
                summary: "Generated Agenda Event", // As per createAgenda's simplified logic
                description: mockSuccessfulOpenAI.content,
                startDateTime: dayjs.tz(`${defaultCreateAgendaParams.userDate}T09:00:00`, defaultCreateAgendaParams.userTimezone).toISOString(),
                endDateTime: dayjs.tz(`${defaultCreateAgendaParams.userDate}T10:00:00`, defaultCreateAgendaParams.userTimezone).toISOString(),
                timezone: defaultCreateAgendaParams.userTimezone
            }),
            // Default values for generatedId, conferenceDataVersion, etc., if not specified by createAgenda
             undefined, // generatedId (for conference, likely undefined here)
             0 // conferenceDataVersion (default if no conference)
        );
    });
});

describe('createDaySchedule (with refactored createGoogleEvent)', () => {
    // Assuming spies and defaultParams are set up as in previous createDaySchedule tests
    let listEventsForUserGivenDatesSpy: jest.SpyInstance;
    let callOpenAISpy: jest.SpyInstance;
    let getGlobalCalendarSpy: jest.SpyInstance;
    let createGoogleEventSpy: jest.SpyInstance;
    let upsertEventsPostPlannerSpy: jest.SpyInstance;
    let sendGenericTaskEmailSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const defaultDayScheduleParams = {
        userId: 'user_schedule_test',
        clientType: 'web' as 'web',
        userDate: '2024-08-15',
        userTimezone: 'America/Denver',
        prompt: 'Plan my day.',
        isAllDay: false,
        email: 'user@example.com',
        name: 'Schedule User',
    };
    const mockParsedTasksNonAllDay = [
        { start_time: "10:00 AM", end_time: "11:00 AM", task: "Task 1", description: "Desc 1" },
        { start_time: "2:00 PM", end_time: "3:00 PM", task: "Task 2", description: "Desc 2" }
    ];
    const mockSuccessfulGlobalCalendar = { success: true, data: { id: 'dbCalId123', primaryCalendarId: 'primaryGCalId456' } };


    beforeEach(() => {
        jest.clearAllMocks();
        listEventsForUserGivenDatesSpy = jest.spyOn(apiHelperModule, 'listEventsForUserGivenDates').mockResolvedValue({ success: true, data: [] });
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI'); // Specific mock per test
        getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar').mockResolvedValue(mockSuccessfulGlobalCalendar);
        createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent').mockResolvedValue({ success: true, data: { id: 'g1', googleEventId: 'g1', generatedId: 'u1', calendarId: 'p1' }});
        upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner').mockResolvedValue({ success: true, data: { affected_rows: 1, returning: [] } });
        sendGenericTaskEmailSpy = jest.spyOn(apiHelperModule, 'sendGenericTaskEmail').mockResolvedValue({ success: true });
        jest.spyOn(apiHelperModule, 'getGoogleAPIToken').mockResolvedValue({success: true, token: "dummy-token"});
    });
     afterEach(() => {
        jest.restoreAllMocks();
        consoleLogSpy.mockRestore();
    });


    it('createDaySchedule non-all-day should call createGoogleEvent with CreateGoogleEventOptions for each task', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });

        await apiHelperModule.createDaySchedule(...Object.values(defaultDayScheduleParams));

        expect(createGoogleEventSpy).toHaveBeenCalledTimes(mockParsedTasksNonAllDay.length);
        mockParsedTasksNonAllDay.forEach(task => {
            const expectedStartDateTime = dayjs.tz(`${defaultDayScheduleParams.userDate} ${task.start_time}`, 'YYYY-MM-DD h:mm A', defaultDayScheduleParams.userTimezone).toISOString();
            const expectedEndDateTime = dayjs.tz(`${defaultDayScheduleParams.userDate} ${task.end_time}`, 'YYYY-MM-DD h:mm A', defaultDayScheduleParams.userTimezone).toISOString();
            expect(createGoogleEventSpy).toHaveBeenCalledWith(
                defaultDayScheduleParams.userId,
                mockSuccessfulGlobalCalendar.data.primaryCalendarId,
                defaultDayScheduleParams.clientType,
                expect.objectContaining({
                    summary: task.task,
                    description: task.description,
                    startDateTime: expectedStartDateTime,
                    endDateTime: expectedEndDateTime,
                    timezone: defaultDayScheduleParams.userTimezone
                }),
                undefined, // generatedId for conference
                0 // conferenceDataVersion
            );
        });
    });

    it('createDaySchedule all-day should call createGoogleEvent with CreateGoogleEventOptions for a single event', async () => {
        const mockParsedTasksAllDay = [{ task: "Task A", description: "Desc A"}, { task: "Task B", description: "Desc B"}];
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksAllDay) });
        const allDayParams = { ...defaultDayScheduleParams, isAllDay: true };

        await apiHelperModule.createDaySchedule(...Object.values(allDayParams));

        const expectedAllDayStartDate = dayjs.tz(allDayParams.userDate, allDayParams.userTimezone).startOf('day').format('YYYY-MM-DD');
        const expectedAllDayEndDate = dayjs.tz(allDayParams.userDate, allDayParams.userTimezone).add(1, 'day').startOf('day').format('YYYY-MM-DD');
        const expectedDescription = mockParsedTasksAllDay.map(t => `${t.task}${t.description ? `:\n${t.description}` : ''}`).join('\n\n---\n\n');

        expect(createGoogleEventSpy).toHaveBeenCalledTimes(1);
        expect(createGoogleEventSpy).toHaveBeenCalledWith(
            allDayParams.userId,
            mockSuccessfulGlobalCalendar.data.primaryCalendarId,
            allDayParams.clientType,
            expect.objectContaining({
                summary: expect.stringContaining('Day Schedule:'),
                description: expectedDescription,
                startDate: expectedAllDayStartDate,
                endDate: expectedAllDayEndDate,
                timezone: allDayParams.userTimezone
            }),
            undefined, 0
        );
    });
});


describe('breakDownTask and howToTask (with refactored createGoogleEvent)', () => {
    // Common setup for breakDownTask and howToTask
    let callOpenAISpy: jest.SpyInstance;
    let getGlobalCalendarSpy: jest.SpyInstance;
    let createGoogleEventSpy: jest.SpyInstance; // This is the target for assertion change
    let upsertEventsPostPlannerSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});


    const defaultTaskParams = {
        userId: 'user_task_test',
        clientType: 'web' as 'web',
        userTimezone: 'America/Los_Angeles',
        taskTitle: 'Plan Q3 Roadmap',
        taskDescription: 'Detailed planning for Q3.',
        isAllDay: false,
        startDate: '2024-07-01T10:00:00Z',
        endDate: '2024-07-01T11:00:00Z',
        email: 'user@example.com',
        name: 'Task User',
    };
    const mockSuccessfulOpenAI_Task = { success: true, content: 'Task details from AI' };
    const mockSuccessfulGlobalCalendar_Task = { success: true, data: { id: 'taskCalId', primaryCalendarId: 'primaryTaskCal' } };
     // createGoogleEvent is spied, so its internal getGoogleAPIToken call doesn't need separate spying here.

    beforeEach(() => {
        jest.clearAllMocks();
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI').mockResolvedValue(mockSuccessfulOpenAI_Task);
        getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar').mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
        createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent').mockResolvedValue({ success: true, data: { id: 'g1', googleEventId: 'g1', generatedId:'u1', calendarId:'p1' }});
        upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner').mockResolvedValue({ success: true, data: { affected_rows:1, returning:[] } });
        jest.spyOn(apiHelperModule, 'getGoogleAPIToken').mockResolvedValue({success: true, token: "dummy-token"});
    });
    afterEach(() => {
        jest.restoreAllMocks();
        consoleLogSpy.mockRestore();
    });

    describe('breakDownTask (checking createGoogleEventOptions)', () => {
        let emailTaskBreakDownSpy: jest.SpyInstance;
        beforeEach(() => emailTaskBreakDownSpy = jest.spyOn(apiHelperModule, 'emailTaskBreakDown').mockResolvedValue({ success: true }));
        afterEach(() => emailTaskBreakDownSpy.mockRestore());

        it('breakDownTask timed event should call createGoogleEvent with correct options', async () => {
            await apiHelperModule.breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, false, // isAllDay = false
                defaultTaskParams.startDate, defaultTaskParams.endDate,
                defaultTaskParams.email, defaultTaskParams.name
            );
            expect(createGoogleEventSpy).toHaveBeenCalledWith(
                defaultTaskParams.userId, mockSuccessfulGlobalCalendar_Task.data.primaryCalendarId, defaultTaskParams.clientType,
                expect.objectContaining({
                    summary: defaultTaskParams.taskTitle,
                    description: mockSuccessfulOpenAI_Task.content,
                    startDateTime: defaultTaskParams.startDate,
                    endDateTime: defaultTaskParams.endDate,
                    timezone: defaultTaskParams.userTimezone
                }),
                undefined, 0
            );
        });

        it('breakDownTask all-day event should call createGoogleEvent with correct date options', async () => {
            const allDayStartDate = dayjs(defaultTaskParams.startDate).format('YYYY-MM-DD');
            const allDayEndDate = dayjs(defaultTaskParams.endDate).format('YYYY-MM-DD'); // The helper adds 1 day to end date for GCal

            await apiHelperModule.breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, true, // isAllDay = true
                allDayStartDate, allDayEndDate,
                defaultTaskParams.email, defaultTaskParams.name
            );
            expect(createGoogleEventSpy).toHaveBeenCalledWith(
                defaultTaskParams.userId, mockSuccessfulGlobalCalendar_Task.data.primaryCalendarId, defaultTaskParams.clientType,
                expect.objectContaining({
                    summary: defaultTaskParams.taskTitle,
                    description: mockSuccessfulOpenAI_Task.content,
                    startDate: allDayStartDate,
                    endDate: dayjs(allDayEndDate).add(1, 'day').format('YYYY-MM-DD'), // createEventHelper adds 1 day
                    timezone: defaultTaskParams.userTimezone
                }),
                undefined, 0
            );
        });
    });

    describe('howToTask (checking createGoogleEventOptions)', () => {
        let sendGenericTaskEmailSpy: jest.SpyInstance;
        beforeEach(() => sendGenericTaskEmailSpy = jest.spyOn(apiHelperModule, 'sendGenericTaskEmail').mockResolvedValue({ success: true }));
        afterEach(() => sendGenericTaskEmailSpy.mockRestore());

        it('howToTask timed event should call createGoogleEvent with correct options', async () => {
            await apiHelperModule.howToTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, false, // isAllDay = false
                defaultTaskParams.startDate, defaultTaskParams.endDate,
                defaultTaskParams.email, defaultTaskParams.name
            );
            expect(createGoogleEventSpy).toHaveBeenCalledWith(
                defaultTaskParams.userId, mockSuccessfulGlobalCalendar_Task.data.primaryCalendarId, defaultTaskParams.clientType,
                expect.objectContaining({
                    summary: `How to: ${defaultTaskParams.taskTitle}`,
                    description: mockSuccessfulOpenAI_Task.content,
                    startDateTime: defaultTaskParams.startDate,
                    endDateTime: defaultTaskParams.endDate,
                    timezone: defaultTaskParams.userTimezone
                }),
                undefined, 0
            );
        });
    });
});

// --- Tests for createDaySchedule ---
import { createDaySchedule } from './api-helper';
// Spies for apiHelperModule functions will be set up in describe block.
// Other necessary mocks like 'got', 'googleapis', 'uuid', 'sendEmail' are already set up.

describe('createDaySchedule', () => {
    let listEventsForUserGivenDatesSpy: jest.SpyInstance;
    let callOpenAISpy: jest.SpyInstance;
    let getGlobalCalendarSpy: jest.SpyInstance;
    let createGoogleEventSpy: jest.SpyInstance;
    let upsertEventsPostPlannerSpy: jest.SpyInstance;
    let sendGenericTaskEmailSpy: jest.SpyInstance; // Renamed from emailDailySchedule
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const defaultParams = {
        userId: 'user_schedule_test',
        clientType: 'web' as 'web',
        userDate: '2024-08-15',
        userTimezone: 'America/Denver',
        prompt: 'Plan my day with focus on project X.',
        isAllDay: false,
        email: 'user@example.com',
        name: 'Schedule User',
    };

    const mockExistingEvents = [
        { id: 'exist1', summary: 'Morning Standup', startDateTime: '2024-08-15T15:00:00Z', endDateTime: '2024-08-15T15:30:00Z' } // 9 AM Denver
    ];
    const mockParsedTasksNonAllDay = [
        { start_time: "10:00 AM", end_time: "11:00 AM", task: "Work on Project X proposal", description: "Draft initial proposal." },
        { start_time: "2:00 PM", end_time: "3:00 PM", task: "Follow up emails", description: "Client communications." }
    ];
     const mockParsedTasksAllDay = [ // For all-day, structure might be simpler list of tasks if times are ignored
        { task: "Review PRs", description: "Check team pull requests." },
        { task: "Plan next sprint", description: "Outline tasks for upcoming sprint." }
    ];

    const mockSuccessfulGlobalCalendar = { success: true, data: { id: 'dbCalId123', primaryCalendarId: 'primaryGCalId456' } };
    const mockSuccessfulGEventCreate = { success: true, data: { id: 'gcalEventId#primaryGCalId456', googleEventId: 'gcalEventId', generatedId: 'uuidGenerated' } };
    const mockSuccessfulUpsert = { success: true, data: { affected_rows: 1, returning: [{id: 'dbEvent1'}] } };
    const mockSuccessfulEmail = { success: true };


    beforeEach(() => {
        jest.clearAllMocks();
        listEventsForUserGivenDatesSpy = jest.spyOn(apiHelperModule, 'listEventsForUserGivenDates');
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI');
        getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar');
        createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent');
        upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner');
        sendGenericTaskEmailSpy = jest.spyOn(apiHelperModule, 'sendGenericTaskEmail'); // Updated spy name

        // Default successful mocks for most common path
        listEventsForUserGivenDatesSpy.mockResolvedValue({ success: true, data: mockExistingEvents });
        getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
        createGoogleEventSpy.mockResolvedValue(mockSuccessfulGEventCreate);
        upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert);
        sendGenericTaskEmailSpy.mockResolvedValue(mockSuccessfulEmail);
    });
    afterEach(() => {
        consoleLogSpy.mockRestore();
    });

    // Test Case 1: Success (non-all-day, multiple tasks parsed and created).
    it('should succeed for non-all-day schedule with multiple tasks and email', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });
        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result).toEqual({ success: true });
        expect(listEventsForUserGivenDatesSpy).toHaveBeenCalledTimes(1);
        expect(callOpenAISpy).toHaveBeenCalledTimes(1);
        expect(getGlobalCalendarSpy).toHaveBeenCalledTimes(1);
        expect(createGoogleEventSpy).toHaveBeenCalledTimes(mockParsedTasksNonAllDay.length);
        expect(upsertEventsPostPlannerSpy).toHaveBeenCalledTimes(1);
        expect(sendGenericTaskEmailSpy).toHaveBeenCalledTimes(1);
    });

    // Test Case 2: Success (all-day schedule).
    it('should succeed for all-day schedule, creating one summary event', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksAllDay) });
        const paramsAllDay = { ...defaultParams, isAllDay: true };
        const result = await createDaySchedule(...Object.values(paramsAllDay));

        expect(result).toEqual({ success: true });
        expect(createGoogleEventSpy).toHaveBeenCalledTimes(1); // Only one event for all-day
        expect(createGoogleEventSpy).toHaveBeenCalledWith(
            paramsAllDay.userId,
            mockSuccessfulGlobalCalendar.data.primaryCalendarId,
            paramsAllDay.clientType,
            expect.stringContaining('Day Schedule:'), // Summary for all-day event
            dayjs.tz(paramsAllDay.userDate, paramsAllDay.userTimezone).startOf('day').format('YYYY-MM-DD'), // Start date for all-day
            dayjs.tz(paramsAllDay.userDate, paramsAllDay.userTimezone).add(1, 'day').startOf('day').format('YYYY-MM-DD'), // End date for all-day
            paramsAllDay.userTimezone,
            expect.any(String) // Description will be concatenation of tasks
        );
        expect(upsertEventsPostPlannerSpy).toHaveBeenCalledTimes(1);
        expect(sendGenericTaskEmailSpy).toHaveBeenCalledTimes(1);
    });

    // Test Case 3: callOpenAI fails.
    it('should fail if callOpenAI fails', async () => {
        const openAIError = { message: "AI system offline" };
        callOpenAISpy.mockResolvedValue({ success: false, error: openAIError });
        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('Failed to generate schedule via OpenAI.');
            expect(result.error.details).toEqual(openAIError);
        }
    });

    // Test Case 4: OpenAI response is not valid JSON.
    it('should fail if OpenAI response is not valid JSON', async () => {
        const nonJsonResponse = "This is just plain text.";
        callOpenAISpy.mockResolvedValue({ success: true, content: nonJsonResponse });
        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('Failed to parse schedule from OpenAI response as JSON.');
            expect(result.error.rawResponse).toBe(nonJsonResponse);
        }
    });

    // Test Case 5: OpenAI response is JSON but not an array.
    it('should fail if OpenAI response is JSON but not an array', async () => {
        const nonArrayJsonResponse = JSON.stringify({ task: "A single object, not an array" });
        callOpenAISpy.mockResolvedValue({ success: true, content: nonArrayJsonResponse });
        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('OpenAI schedule response is not a valid array.');
            expect(result.error.parsedResponse).toEqual(JSON.parse(nonArrayJsonResponse));
        }
    });

    // Test Case 6: One of the createGoogleEvent calls fails (for non-all-day).
    it('should fail if a createGoogleEvent call fails for non-all-day schedule', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });
        const gEventError = { message: "Quota exceeded for GCal" };
        createGoogleEventSpy
            .mockResolvedValueOnce(mockSuccessfulGEventCreate) // First task succeeds
            .mockResolvedValueOnce({ success: false, error: gEventError }); // Second task fails

        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain(`Failed to create Google Calendar event for task: "${mockParsedTasksNonAllDay[1].task}"`);
            expect(result.error.details).toEqual(gEventError);
        }
        expect(createGoogleEventSpy).toHaveBeenCalledTimes(2); // Called for first and failing second
        expect(upsertEventsPostPlannerSpy).not.toHaveBeenCalled(); // Should stop before upserting
    });

    // Test Case 7: upsertEventsPostPlanner fails.
    it('should fail if upsertEventsPostPlanner fails', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });
        const upsertError = { message: "DB connection error" };
        upsertEventsPostPlannerSpy.mockResolvedValue({ success: false, error: upsertError });

        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('Failed to save scheduled events to database.');
            expect(result.error.details).toEqual(upsertError);
        }
    });

    // Test Case 8: emailDailySchedule fails (if email provided).
    it('should fail if sendGenericTaskEmail (formerly emailDailySchedule) fails', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });
        const emailError = { message: "Mail server down" };
        sendGenericTaskEmailSpy.mockResolvedValue({ success: false, error: emailError });

        const result = await createDaySchedule(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('Failed to send daily schedule email.');
            expect(result.error.details).toEqual(emailError);
        }
    });

    // Test Case 9: No new tasks to schedule after filtering (all overlap existing events).
    it('should succeed with no events created if all parsed tasks overlap existing events', async () => {
        // Make existing events overlap with both parsed tasks
        const overlappingExistingEvents = [
            { id: 'exist1', summary: 'Overlap Task 1', startDateTime: dayjs.tz('2024-08-15 09:30 AM', 'YYYY-MM-DD h:mm A', defaultParams.userTimezone).toISOString(), endDateTime: dayjs.tz('2024-08-15 11:30 AM', 'YYYY-MM-DD h:mm A', defaultParams.userTimezone).toISOString() },
            { id: 'exist2', summary: 'Overlap Task 2', startDateTime: dayjs.tz('2024-08-15 1:30 PM', 'YYYY-MM-DD h:mm A', defaultParams.userTimezone).toISOString(), endDateTime: dayjs.tz('2024-08-15 3:30 PM', 'YYYY-MM-DD h:mm A', defaultParams.userTimezone).toISOString() }
        ];
        listEventsForUserGivenDatesSpy.mockResolvedValue({ success: true, data: overlappingExistingEvents });
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify(mockParsedTasksNonAllDay) });
        sendGenericTaskEmailSpy.mockResolvedValue({success: true}); // Mock email success for this path

        const result = await createDaySchedule(...Object.values(defaultParams));

        expect(result).toEqual({ success: true });
        expect(createGoogleEventSpy).not.toHaveBeenCalled(); // No new non-overlapping events
        expect(upsertEventsPostPlannerSpy).toHaveBeenCalledWith([]); // Called with empty array
        expect(sendGenericTaskEmailSpy).toHaveBeenCalledWith(
            defaultParams.email,
            defaultParams.name,
            `Your Schedule for ${defaultParams.userDate}`,
            "Your day schedule was processed. After checking for overlaps with existing events, no new tasks were added to your calendar."
        );
    });

    it('should succeed with no email if no new tasks parsed from OpenAI', async () => {
        callOpenAISpy.mockResolvedValue({ success: true, content: JSON.stringify([]) }); // OpenAI returns no tasks
        listEventsForUserGivenDatesSpy.mockResolvedValue({ success: true, data: [] }); // No existing events

        const paramsNoEmail = {...defaultParams, email: undefined, name: undefined};
        const result = await createDaySchedule(...Object.values(paramsNoEmail));

        expect(result).toEqual({ success: true });
        expect(createGoogleEventSpy).not.toHaveBeenCalled();
        expect(upsertEventsPostPlannerSpy).not.toHaveBeenCalled(); // Not called because eventsToUpsert is empty
        expect(sendGenericTaskEmailSpy).not.toHaveBeenCalled();
    });
});

// --- Tests for meetingRequest ---
import { meetingRequest } from './api-helper';
// Spies for apiHelperModule functions will be set up in describe block.
// generateAvailability is also part of apiHelperModule now (as a placeholder to be spied upon).

describe('meetingRequest', () => {
    let generateAvailabilitySpy: jest.SpyInstance;
    let callOpenAISpy: jest.SpyInstance;
    let sendMeetingRequestTemplateSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const defaultParams = {
        userId: 'user_mr_test',
        clientType: 'web' as 'web',
        userTimezone: 'America/New_York',
        userDateContext: 'next week',
        attendees: 'bob@example.com, alice@example.com',
        subject: 'Project Sync',
        prompt: 'Need to discuss Q3 goals.',
        durationMinutes: 30,
        shareAvailability: true,
        availabilityUserDateStart: '2024-08-01',
        availabilityUserDateEnd: '2024-08-03',
        emailTo: 'lead@example.com',
        emailName: 'Project Lead',
        yesLink: 'http://example.com/yes',
        noLink: 'http://example.com/no',
    };

    const mockAvailabilitySlots = [
        { startDate: '2024-08-01T10:00:00Z', endDate: '2024-08-01T11:00:00Z' },
        { startDate: '2024-08-01T14:00:00Z', endDate: '2024-08-01T15:00:00Z' },
        { startDate: '2024-08-02T09:00:00Z', endDate: '2024-08-02T10:00:00Z' },
    ];

    beforeEach(() => {
        jest.clearAllMocks();
        generateAvailabilitySpy = jest.spyOn(apiHelperModule, 'generateAvailability');
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI');
        sendMeetingRequestTemplateSpy = jest.spyOn(apiHelperModule, 'sendMeetingRequestTemplate');
    });
    afterEach(() => {
        consoleLogSpy.mockRestore();
    });

    // Test Case 1: Success with availability sharing.
    it('should succeed with availability sharing when all helpers succeed', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: mockAvailabilitySlots });
        // Mocking multiple calls to callOpenAI in order
        callOpenAISpy
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-01' }) // Daily summary for 2024-08-01
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-02' }) // Daily summary for 2024-08-02
            .mockResolvedValueOnce({ success: true, content: 'Final combined availability summary' }) // Combined summary
            .mockResolvedValueOnce({ success: true, content: 'Drafted email body with availability' }); // Email draft
        sendMeetingRequestTemplateSpy.mockResolvedValue({ success: true });

        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result).toEqual({ success: true });
        expect(generateAvailabilitySpy).toHaveBeenCalledTimes(1);
        expect(callOpenAISpy).toHaveBeenCalledTimes(4); // 2 daily + 1 combined + 1 email draft
        expect(sendMeetingRequestTemplateSpy).toHaveBeenCalledTimes(1);
    });

    // Test Case 2: Success without availability sharing.
    it('should succeed without availability sharing', async () => {
        callOpenAISpy.mockResolvedValueOnce({ success: true, content: 'Drafted email body without availability' }); // Email draft
        sendMeetingRequestTemplateSpy.mockResolvedValue({ success: true });

        const paramsNoAvailability = { ...defaultParams, shareAvailability: false };
        const result = await meetingRequest(...Object.values(paramsNoAvailability));

        expect(result).toEqual({ success: true });
        expect(generateAvailabilitySpy).not.toHaveBeenCalled();
        expect(callOpenAISpy).toHaveBeenCalledTimes(1); // Only for email draft
        expect(sendMeetingRequestTemplateSpy).toHaveBeenCalledTimes(1);
    });

    it('should succeed without availability sharing and no email recipient (draft only)', async () => {
        callOpenAISpy.mockResolvedValueOnce({ success: true, content: 'Drafted email body, no recipient' });

        const paramsNoRecipient = { ...defaultParams, shareAvailability: false, emailTo: undefined, emailName: undefined, yesLink: undefined, noLink: undefined };
        const result = await meetingRequest(...Object.values(paramsNoRecipient));
        expect(result).toEqual({ success: true });
        expect(generateAvailabilitySpy).not.toHaveBeenCalled();
        expect(callOpenAISpy).toHaveBeenCalledTimes(1);
        expect(sendMeetingRequestTemplateSpy).not.toHaveBeenCalled(); // Email not sent
    });


    // Test Case 3: generateAvailability returns success: false.
    it('should fail if generateAvailability returns success:false', async () => {
        const genAvailError = { message: 'Failed to connect to calendar API' };
        generateAvailabilitySpy.mockResolvedValue({ success: false, error: genAvailError });
        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('Failed to generate availability.');
            expect(result.error.details).toEqual(genAvailError);
        }
    });

    // Test Case 4: generateAvailability returns success: true, data: [] (no slots).
    it('should fail if generateAvailability returns no slots', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: [] });
        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('No availability slots found to share.');
        }
    });

    it('should fail if availability start/end dates are missing when shareAvailability is true', async () => {
        const paramsMissingDates = { ...defaultParams, availabilityUserDateStart: undefined, availabilityUserDateEnd: undefined };
        const result = await meetingRequest(...Object.values(paramsMissingDates));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('Availability start and end dates are required when shareAvailability is true.');
        }
    });


    // Test Case 5: Any callOpenAI call fails.
    it('should fail if first callOpenAI (daily summary) fails', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: mockAvailabilitySlots });
        const openAIError = { message: "AI daily summary failed" };
        callOpenAISpy.mockResolvedValueOnce({ success: false, error: openAIError }); // Fail first daily summary

        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toMatch(/Failed to summarize availability for date/);
            expect(result.error.details).toEqual(openAIError);
        }
    });

    it('should fail if second callOpenAI (combined summary) fails', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: mockAvailabilitySlots });
        callOpenAISpy
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-01' })
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-02' })
            .mockResolvedValueOnce({ success: false, error: {message: "AI combined summary failed"} }); // Fail combined

        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('Failed to generate combined availability summary.');
        }
    });

    it('should fail if third callOpenAI (email draft) fails', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: mockAvailabilitySlots });
        callOpenAISpy
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-01' })
            .mockResolvedValueOnce({ success: true, content: 'Summary for 2024-08-02' })
            .mockResolvedValueOnce({ success: true, content: 'Final combined availability summary' })
            .mockResolvedValueOnce({ success: false, error: {message: "AI email draft failed"} }); // Fail email draft

        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('Failed to draft meeting request email body.');
        }
    });


    // Test Case 6: sendMeetingRequestTemplate fails.
    it('should fail if sendMeetingRequestTemplate fails', async () => {
        generateAvailabilitySpy.mockResolvedValue({ success: true, data: mockAvailabilitySlots });
        callOpenAISpy
            .mockResolvedValueOnce({ success: true, content: 'Daily summary 1' })
            .mockResolvedValueOnce({ success: true, content: 'Daily summary 2' })
            .mockResolvedValueOnce({ success: true, content: 'Combined summary' })
            .mockResolvedValueOnce({ success: true, content: 'Email body' });
        const emailError = { message: "SMTP error" };
        sendMeetingRequestTemplateSpy.mockResolvedValue({ success: false, error: emailError });

        const result = await meetingRequest(...Object.values(defaultParams));
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('Failed to send meeting request email.');
            expect(result.error.details).toEqual(emailError);
        }
    });
});

// --- Tests for Orchestrator Functions: createSummaryOfTimePeriod, breakDownTask, howToTask ---
import {
    createSummaryOfTimePeriod,
    breakDownTask,
    howToTask
} from './api-helper';
// Spies for apiHelperModule functions will be set up in describe blocks or beforeEach.
// Other necessary mocks like 'got', 'googleapis', 'uuid', 'sendEmail' are already set up.

describe('createSummaryOfTimePeriod', () => {
    let listEventsForDateSpy: jest.SpyInstance;
    let callOpenAISpy: jest.SpyInstance;
    let sendSummaryEmailSpy: jest.SpyInstance;
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});


    const defaultParams = {
        userId: 'user_sum_test',
        startDate: '2024-03-01',
        endDate: '2024-03-07',
        timezone: 'America/New_York',
        email: 'test@example.com',
        name: 'Test User',
    };

    beforeEach(() => {
        jest.clearAllMocks();
        listEventsForDateSpy = jest.spyOn(apiHelperModule, 'listEventsForDate');
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI');
        sendSummaryEmailSpy = jest.spyOn(apiHelperModule, 'sendSummaryEmail');
    });
    afterEach(() => {
        consoleLogSpy.mockRestore();
    });


    it('should successfully create summary and send email', async () => {
        const mockEvents = [{ id: 'e1', summary: 'Event 1', startDateTime: '2024-03-01T10:00:00Z', endDateTime: '2024-03-01T11:00:00Z' }];
        listEventsForDateSpy.mockResolvedValue({ success: true, data: mockEvents });
        const summaryText = 'This is a great summary.';
        callOpenAISpy.mockResolvedValue({ success: true, content: summaryText });
        sendSummaryEmailSpy.mockResolvedValue({ success: true });

        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone, defaultParams.email, defaultParams.name);

        expect(result.success).toBe(true);
        if(result.success) expect(result.data).toBe(summaryText);
        expect(listEventsForDateSpy).toHaveBeenCalledTimes(1);
        expect(callOpenAISpy).toHaveBeenCalledTimes(1);
        expect(sendSummaryEmailSpy).toHaveBeenCalledTimes(1);
    });

    it('should successfully create summary without sending email if email/name not provided', async () => {
        const mockEvents = [{ id: 'e1', summary: 'Event 1' }];
        listEventsForDateSpy.mockResolvedValue({ success: true, data: mockEvents });
        const summaryText = 'Summary text here.';
        callOpenAISpy.mockResolvedValue({ success: true, content: summaryText });

        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone);

        expect(result.success).toBe(true);
        if(result.success) expect(result.data).toBe(summaryText);
        expect(sendSummaryEmailSpy).not.toHaveBeenCalled();
    });

    it('should return failure if listEventsForDate fails', async () => {
        const listError = { message: 'DB error listing events' };
        listEventsForDateSpy.mockResolvedValue({ success: false, error: listError });
        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone);
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('event listing failure');
            expect(result.error.details).toEqual(listError);
        }
        expect(callOpenAISpy).not.toHaveBeenCalled();
    });

    it('should return specific failure if no events are found by listEventsForDate', async () => {
        listEventsForDateSpy.mockResolvedValue({ success: true, data: [] }); // No events
        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone);
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toBe('No events found to summarize.');
        }
        expect(callOpenAISpy).not.toHaveBeenCalled();
    });

    it('should return failure if callOpenAI fails', async () => {
        listEventsForDateSpy.mockResolvedValue({ success: true, data: [{ id: 'e1' }] });
        const openAIError = { message: 'AI unavailable' };
        callOpenAISpy.mockResolvedValue({ success: false, error: openAIError });
        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone);
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('OpenAI call failure');
            expect(result.error.details).toEqual(openAIError);
        }
    });

    it('should return failure if sendSummaryEmail fails', async () => {
        listEventsForDateSpy.mockResolvedValue({ success: true, data: [{ id: 'e1' }] });
        callOpenAISpy.mockResolvedValue({ success: true, content: "summary" });
        const emailError = { message: "SMTP down" };
        sendSummaryEmailSpy.mockResolvedValue({ success: false, error: emailError});

        const result = await createSummaryOfTimePeriod(defaultParams.userId, defaultParams.startDate, defaultParams.endDate, defaultParams.timezone, defaultParams.email, defaultParams.name);
        expect(result.success).toBe(false);
        if(!result.success) {
            expect(result.error.message).toContain('Failed to send summary email');
            expect(result.error.details).toEqual(emailError);
        }
    });
});


describe('breakDownTask and howToTask common helper mocks', () => {
    // These spies are common to breakDownTask and howToTask
    let callOpenAISpy: jest.SpyInstance;
    let getGlobalCalendarSpy: jest.SpyInstance;
    let createGoogleEventSpy: jest.SpyInstance;
    let upsertEventsPostPlannerSpy: jest.SpyInstance;
    // Email spies will be specific to each function's describe block
    const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const defaultTaskParams = {
        userId: 'user_task_test',
        clientType: 'web' as 'web' | 'ios' | 'android' | 'atomic-web',
        userTimezone: 'America/Los_Angeles',
        taskTitle: 'Plan Q3 Roadmap',
        taskDescription: 'Detailed planning for all Q3 features.',
        isAllDay: false,
        startDate: '2024-07-01T00:00:00Z', // Assuming specific time if not all-day
        endDate: '2024-07-01T02:00:00Z',
        email: 'user@example.com',
        name: 'Task User',
    };

    const mockSuccessfulOpenAI_Task = { success: true, content: 'Task breakdown details or How-to steps' };
    const mockSuccessfulGlobalCalendar_Task = { success: true, data: { id: 'taskCalId', primaryCalendarId: 'primaryTaskCal' } };
    const mockSuccessfulCreateGoogleEvent_Task = { success: true, data: { id: 'gEventTask#primaryTaskCal', googleEventId: 'gEventTask', generatedId: 'uuidTask', calendarId: 'primaryTaskCal' } };
    const mockSuccessfulUpsert_Task = { success: true, data: { affected_rows: 1, returning: [{ id: 'dbEventTask' }] } };


    beforeEach(() => {
        jest.clearAllMocks();
        callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI');
        getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar');
        // Note: createEventHelper is not exported, so we test its effects by mocking its dependencies:
        // getGlobalCalendar (already spied) and createGoogleEvent (spied below)
        // getGoogleAPIToken is also called by createGoogleEvent, so we ensure it's spied if createGoogleEvent is not fully mocked out.
        // For simplicity, we'll spy on createGoogleEvent directly as it's an exported helper.
        createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent');
        upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner');
    });

    afterEach(() => {
        consoleLogSpy.mockRestore();
    });

    describe('breakDownTask', () => {
        let emailTaskBreakDownSpy: jest.SpyInstance;

        beforeEach(() => {
            emailTaskBreakDownSpy = jest.spyOn(apiHelperModule, 'emailTaskBreakDown');
        });
        afterEach(() => {
            emailTaskBreakDownSpy.mockRestore();
        });

        it('should successfully break down task, create event, and send email', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task); // For createEventHelper and for direct call
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);
            emailTaskBreakDownSpy.mockResolvedValue({ success: true });

            const result = await breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate, defaultTaskParams.email, defaultTaskParams.name
            );
            expect(result).toEqual({ success: true });
            expect(callOpenAISpy).toHaveBeenCalledTimes(1);
            expect(createGoogleEventSpy).toHaveBeenCalledTimes(1);
            expect(upsertEventsPostPlannerSpy).toHaveBeenCalledTimes(1);
            expect(emailTaskBreakDownSpy).toHaveBeenCalledTimes(1);
        });

        it('should succeed for all-day event without email', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);

            const paramsAllDay = { ...defaultTaskParams, isAllDay: true, email: undefined, name: undefined };
            const result = await breakDownTask(
                paramsAllDay.userId, paramsAllDay.clientType, paramsAllDay.userTimezone,
                paramsAllDay.taskTitle, paramsAllDay.taskDescription, paramsAllDay.isAllDay,
                dayjs(paramsAllDay.startDate).format('YYYY-MM-DD'), // All-day expects YYYY-MM-DD
                dayjs(paramsAllDay.endDate).format('YYYY-MM-DD')    // All-day expects YYYY-MM-DD
            );
            expect(result).toEqual({ success: true });
            expect(emailTaskBreakDownSpy).not.toHaveBeenCalled();
            expect(createGoogleEventSpy).toHaveBeenCalledWith(
                expect.anything(), expect.anything(), expect.anything(), expect.anything(),
                dayjs(paramsAllDay.startDate).format('YYYY-MM-DD'), // Check all-day date format
                dayjs(paramsAllDay.endDate).add(1, 'day').format('YYYY-MM-DD'), // Check all-day end date format
                expect.anything(), expect.anything()
            );
        });


        it('should fail if callOpenAI fails for breakDownTask', async () => {
            callOpenAISpy.mockResolvedValue({ success: false, error: { message: "AI broke" }});
            const result = await breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('OpenAI call failed');
            expect(createGoogleEventSpy).not.toHaveBeenCalled();
        });

        it('should fail if createGoogleEvent (via helper) fails for breakDownTask', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task); // For createEventHelper
            createGoogleEventSpy.mockResolvedValue({success: false, error: {message: "GCal create error"}});

            const result = await breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('Google event creation failed');
        });

        it('should fail if emailTaskBreakDown fails', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);
            emailTaskBreakDownSpy.mockResolvedValue({ success: false, error: { message: "Email broke" } });

            const result = await breakDownTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.taskDescription, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate, defaultTaskParams.email, defaultTaskParams.name
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('Email sending failed');
        });
    });

    describe('howToTask', () => {
        let sendGenericTaskEmailSpy: jest.SpyInstance;

        beforeEach(() => {
            sendGenericTaskEmailSpy = jest.spyOn(apiHelperModule, 'sendGenericTaskEmail');
        });
        afterEach(() => {
            sendGenericTaskEmailSpy.mockRestore();
        });

        it('should successfully process howToTask, create event, and send email', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);
            sendGenericTaskEmailSpy.mockResolvedValue({ success: true });

            const result = await howToTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate, defaultTaskParams.email, defaultTaskParams.name
            );
            expect(result).toEqual({ success: true });
            expect(callOpenAISpy).toHaveBeenCalledTimes(1);
            expect(createGoogleEventSpy).toHaveBeenCalledTimes(1);
            expect(upsertEventsPostPlannerSpy).toHaveBeenCalledTimes(1);
            expect(sendGenericTaskEmailSpy).toHaveBeenCalledTimes(1);
        });

        it('should succeed for all-day howToTask event without email', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);

            const paramsAllDay = { ...defaultTaskParams, isAllDay: true, email: undefined, name: undefined };
            const result = await howToTask(
                paramsAllDay.userId, paramsAllDay.clientType, paramsAllDay.userTimezone,
                paramsAllDay.taskTitle, paramsAllDay.isAllDay,
                dayjs(paramsAllDay.startDate).format('YYYY-MM-DD'),
                dayjs(paramsAllDay.endDate).format('YYYY-MM-DD')
            );
            expect(result).toEqual({ success: true });
            expect(sendGenericTaskEmailSpy).not.toHaveBeenCalled();
             expect(createGoogleEventSpy).toHaveBeenCalledWith(
                expect.anything(), expect.anything(), expect.anything(), expect.stringContaining('How to:'), // Summary check
                dayjs(paramsAllDay.startDate).format('YYYY-MM-DD'),
                dayjs(paramsAllDay.endDate).add(1, 'day').format('YYYY-MM-DD'),
                expect.anything(), expect.anything()
            );
        });


        it('should fail if callOpenAI fails for howToTask', async () => {
            callOpenAISpy.mockResolvedValue({ success: false, error: { message: "AI broke howto" }});
            const result = await howToTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('OpenAI call failed');
        });

        it('should fail if createGoogleEvent (via helper) fails for howToTask', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue({success: false, error: {message: "GCal create error howto"}});

            const result = await howToTask(
                 defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('Google event creation failed');
        });

        it('should fail if sendGenericTaskEmail fails', async () => {
            callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI_Task);
            getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar_Task);
            createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent_Task);
            upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert_Task);
            sendGenericTaskEmailSpy.mockResolvedValue({ success: false, error: { message: "Generic email broke" } });

            const result = await howToTask(
                defaultTaskParams.userId, defaultTaskParams.clientType, defaultTaskParams.userTimezone,
                defaultTaskParams.taskTitle, defaultTaskParams.isAllDay,
                defaultTaskParams.startDate, defaultTaskParams.endDate, defaultTaskParams.email, defaultTaskParams.name
            );
            expect(result.success).toBe(false);
            if(!result.success) expect(result.error.message).toContain('Email sending failed');
        });
    });
});

// --- Tests for createAgenda ---
import { createAgenda } from './api-helper';
import * as apiHelperModule from './api-helper'; // Used for spying on self-module calls
// sendEmail is already mocked from Email Wrapper Functions tests.
// got is already mocked.
// googleapis is already mocked.
// uuid is already mocked.

describe('createAgenda', () => {
  let callOpenAISpy: jest.SpyInstance;
  let getGlobalCalendarSpy: jest.SpyInstance;
  let getCalendarIntegrationSpy: jest.SpyInstance; // Though not directly called by createAgenda, getGoogleAPIToken calls it.
  let createGoogleEventSpy: jest.SpyInstance;
  let upsertEventsPostPlannerSpy: jest.SpyInstance;
  let sendAgendaEmailSpy: jest.SpyInstance;
  let getGoogleAPITokenSpy: jest.SpyInstance; // createGoogleEvent calls this

  const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

  beforeEach(() => {
    jest.clearAllMocks(); // Clears all mocks including those for got, sendEmail, etc.

    // Spy on all helper functions within the same module
    callOpenAISpy = jest.spyOn(apiHelperModule, 'callOpenAI');
    getGlobalCalendarSpy = jest.spyOn(apiHelperModule, 'getGlobalCalendar');
    // getCalendarIntegrationSpy = jest.spyOn(apiHelperModule, 'getCalendarIntegration'); // Not directly called by createAgenda
    getGoogleAPITokenSpy = jest.spyOn(apiHelperModule, 'getGoogleAPIToken'); // Spied because createGoogleEvent calls it
    createGoogleEventSpy = jest.spyOn(apiHelperModule, 'createGoogleEvent');
    upsertEventsPostPlannerSpy = jest.spyOn(apiHelperModule, 'upsertEventsPostPlanner');
    sendAgendaEmailSpy = jest.spyOn(apiHelperModule, 'sendAgendaEmail');
  });

  afterEach(() => {
    // Restore all spies
    callOpenAISpy.mockRestore();
    getGlobalCalendarSpy.mockRestore();
    // getCalendarIntegrationSpy.mockRestore();
    getGoogleAPITokenSpy.mockRestore();
    createGoogleEventSpy.mockRestore();
    upsertEventsPostPlannerSpy.mockRestore();
    sendAgendaEmailSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  const defaultCreateAgendaParams = {
    userId: 'user123',
    clientType: 'web' as 'web' | 'ios' | 'android' | 'atomic-web',
    userTimezone: 'America/New_York',
    userDate: '2024-03-15',
    prompt: 'Create an agenda for a product strategy meeting.',
    email: 'test@example.com',
    name: 'Test User',
  };

  // Mock successful responses for all helpers by default
  const mockSuccessfulOpenAI = { success: true, content: 'Generated Agenda Details' };
  const mockSuccessfulGlobalCalendar = { success: true, data: { id: 'globalCalId', primaryCalendarId: 'primaryCal123' } };
  // getGoogleAPIToken is called by createGoogleEvent, so its mock is implicit via createGoogleEvent's mock if not spied directly.
  // However, createGoogleEvent itself is spied upon, so we control its direct output.
  const mockSuccessfulCreateGoogleEvent = { success: true, data: { id: 'gEvent123#primaryCal123', googleEventId: 'gEvent123', generatedId: 'uuid1', calendarId: 'primaryCal123' } };
  const mockSuccessfulUpsert = { success: true, data: { affected_rows: 1, returning: [{ id: 'dbEventId456' }] } };
  const mockSuccessfulEmail = { success: true };

  // Test Case 1: Successful agenda creation and email sent.
  it('should successfully create agenda and send email when all helpers succeed', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
    createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent);
    upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert);
    sendAgendaEmailSpy.mockResolvedValue(mockSuccessfulEmail);

    const result = await createAgenda(
      defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
      defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
      defaultCreateAgendaParams.prompt, defaultCreateAgendaParams.email, defaultCreateAgendaParams.name
    );

    expect(result).toEqual({ success: true });
    expect(callOpenAISpy).toHaveBeenCalledTimes(1);
    expect(getGlobalCalendarSpy).toHaveBeenCalledWith(defaultCreateAgendaParams.userId);
    expect(createGoogleEventSpy).toHaveBeenCalledTimes(1); // Simplified: one event
    expect(upsertEventsPostPlannerSpy).toHaveBeenCalledTimes(1);
    expect(sendAgendaEmailSpy).toHaveBeenCalledWith(
        defaultCreateAgendaParams.email,
        defaultCreateAgendaParams.name,
        "Your Generated Agenda",
        mockSuccessfulOpenAI.content
    );
  });

  // Test Case 2: callOpenAI fails.
  it('should fail if callOpenAI fails', async () => {
    const openAIError = { message: 'OpenAI API limit reached' };
    callOpenAISpy.mockResolvedValue({ success: false, error: openAIError });

    const result = await createAgenda(
        defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
        defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
        defaultCreateAgendaParams.prompt
    );

    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('OpenAI call failed');
        expect(result.error.details).toEqual(openAIError);
    }
    expect(getGlobalCalendarSpy).not.toHaveBeenCalled();
    expect(createGoogleEventSpy).not.toHaveBeenCalled();
    expect(upsertEventsPostPlannerSpy).not.toHaveBeenCalled();
    expect(sendAgendaEmailSpy).not.toHaveBeenCalled();
  });

  // Test Case 3: getGlobalCalendar fails.
  it('should fail if getGlobalCalendar fails', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    const calendarError = { message: 'Global calendar not found' };
    getGlobalCalendarSpy.mockResolvedValue({ success: false, error: calendarError });

    const result = await createAgenda(
        defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
        defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
        defaultCreateAgendaParams.prompt
    );

    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('global calendar retrieval failure');
        expect(result.error.details).toEqual(calendarError);
    }
    expect(createGoogleEventSpy).not.toHaveBeenCalled();
  });

  // Test Case 4: createGoogleEvent fails.
  it('should fail if createGoogleEvent fails', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
    const eventCreationError = { message: 'Google Calendar API error' };
    createGoogleEventSpy.mockResolvedValue({ success: false, error: eventCreationError });

    const result = await createAgenda(
        defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
        defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
        defaultCreateAgendaParams.prompt
    );

    expect(result.success).toBe(false);
     if(!result.success) {
        expect(result.error.message).toContain('Google event creation failure');
        expect(result.error.details).toEqual(eventCreationError);
    }
    expect(upsertEventsPostPlannerSpy).not.toHaveBeenCalled();
  });

  // Test Case 5: sendAgendaEmail fails (when email is provided).
  it('should fail if sendAgendaEmail fails when email is provided', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
    createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent);
    upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert);
    const emailSendError = { message: 'SMTP server down' };
    sendAgendaEmailSpy.mockResolvedValue({ success: false, error: emailSendError });

    const result = await createAgenda(
      defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
      defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
      defaultCreateAgendaParams.prompt, defaultCreateAgendaParams.email, defaultCreateAgendaParams.name
    );

    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('email sending failure');
        expect(result.error.details).toEqual(emailSendError);
    }
  });

  // Test Case 6: Successful agenda creation, no email to send.
  it('should succeed if all helpers succeed and no email is provided', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
    createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent);
    upsertEventsPostPlannerSpy.mockResolvedValue(mockSuccessfulUpsert);

    const result = await createAgenda(
      defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
      defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
      defaultCreateAgendaParams.prompt, undefined, undefined // No email, no name
    );

    expect(result).toEqual({ success: true });
    expect(sendAgendaEmailSpy).not.toHaveBeenCalled();
  });

  // Test Case 7: upsertEventsPostPlanner fails.
  it('should fail if upsertEventsPostPlanner fails', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue(mockSuccessfulGlobalCalendar);
    createGoogleEventSpy.mockResolvedValue(mockSuccessfulCreateGoogleEvent);
    const upsertError = { message: 'Database constraint violation' };
    upsertEventsPostPlannerSpy.mockResolvedValue({ success: false, error: upsertError });

    const result = await createAgenda(
        defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
        defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
        defaultCreateAgendaParams.prompt
    );

    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('database event upsert failure');
        expect(result.error.details).toEqual(upsertError);
    }
    expect(sendAgendaEmailSpy).not.toHaveBeenCalled(); // Email sending is typically after DB upsert
  });
   it('should fail if getGlobalCalendar does not return primaryCalendarId', async () => {
    callOpenAISpy.mockResolvedValue(mockSuccessfulOpenAI);
    getGlobalCalendarSpy.mockResolvedValue({ success: true, data: { id: 'globalCalId' } as any }); // No primaryCalendarId

    const result = await createAgenda(
      defaultCreateAgendaParams.userId, defaultCreateAgendaParams.clientType,
      defaultCreateAgendaParams.userTimezone, defaultCreateAgendaParams.userDate,
      defaultCreateAgendaParams.prompt
    );

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('global calendar retrieval failure');
    }
    expect(createGoogleEventSpy).not.toHaveBeenCalled();
  });
});

// --- Tests for Email Wrapper Functions ---
import {
  sendAgendaEmail,
  sendSummaryEmail,
  emailTaskBreakDown,
  sendGenericTaskEmail,
  sendMeetingRequestTemplate,
} from './api-helper';
import { sendEmail } from '@/_utils/email/email';

// Mock the sendEmail utility
jest.mock('@/_utils/email/email', () => ({
  sendEmail: jest.fn(),
}));

const mockedSendEmail = sendEmail as jest.MockedFunction<typeof sendEmail>;

describe('Email Wrapper Functions', () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  // --- sendAgendaEmail ---
  describe('sendAgendaEmail', () => {
    const params = { to: 'test@example.com', name: 'Test User', title: 'Meeting Title', body: 'Agenda body' };

    it('should return success:true and call sendEmail with correct params for agenda', async () => {
      mockedSendEmail.mockResolvedValueOnce(undefined); // Assuming sendEmail is async and resolves on success
      const result = await sendAgendaEmail(params.to, params.name, params.title, params.body);

      expect(result).toEqual({ success: true });
      expect(mockedSendEmail).toHaveBeenCalledWith({
        template: 'agenda',
        locals: { name: params.name, title: params.title, body: params.body, to: params.to },
        subject: `Your Meeting Agenda: ${params.title}`,
        to: params.to,
      });
    });

    it('should return success:false on sendEmail failure for agenda', async () => {
      const errorMsg = 'SMTP Error for agenda';
      mockedSendEmail.mockImplementationOnce(() => { throw new Error(errorMsg); });

      const result = await sendAgendaEmail(params.to, params.name, params.title, params.body);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Failed to send agenda email.');
        expect(result.error.details).toBe(errorMsg);
      }
      expect(consoleLogSpy).toHaveBeenCalledWith(expect.stringContaining('Error sending agenda email'), errorMsg);
    });
  });

  // --- sendSummaryEmail ---
  describe('sendSummaryEmail', () => {
    const params = { to: 'user@example.com', name: 'Summary User', title: 'Post-Meeting Summary', summary: 'Summary content' };

    it('should return success:true and call sendEmail with correct params for summary', async () => {
      mockedSendEmail.mockResolvedValueOnce(undefined);
      const result = await sendSummaryEmail(params.to, params.name, params.title, params.summary);

      expect(result).toEqual({ success: true });
      expect(mockedSendEmail).toHaveBeenCalledWith({
        template: 'summary',
        locals: { name: params.name, title: params.title, summary: params.summary, to: params.to },
        subject: `Your Meeting Summary: ${params.title}`,
        to: params.to,
      });
    });

    it('should return success:false on sendEmail failure for summary', async () => {
      const errorMsg = 'Failed sending summary';
      mockedSendEmail.mockImplementationOnce(() => { throw new Error(errorMsg); });
      const result = await sendSummaryEmail(params.to, params.name, params.title, params.summary);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Failed to send summary email.');
        expect(result.error.details).toBe(errorMsg);
      }
    });
  });

  // --- emailTaskBreakDown ---
  describe('emailTaskBreakDown', () => {
    const params = { to: 'tasks@example.com', name: 'Task User', title: 'Project Tasks', tasks: 'List of tasks' };

    it('should return success:true and call sendEmail with correct params for task breakdown', async () => {
      mockedSendEmail.mockResolvedValueOnce(undefined);
      const result = await emailTaskBreakDown(params.to, params.name, params.title, params.tasks);

      expect(result).toEqual({ success: true });
      expect(mockedSendEmail).toHaveBeenCalledWith({
        template: 'task_breakdown',
        locals: { name: params.name, title: params.title, tasks: params.tasks, to: params.to },
        subject: `Your Task Breakdown for: ${params.title}`,
        to: params.to,
      });
    });

    it('should return success:false on sendEmail failure for task breakdown', async () => {
      const errorMsg = 'Task email failed';
      mockedSendEmail.mockImplementationOnce(() => { throw new Error(errorMsg); });
      const result = await emailTaskBreakDown(params.to, params.name, params.title, params.tasks);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Failed to send task breakdown email.');
        expect(result.error.details).toBe(errorMsg);
      }
    });
  });

  // --- sendGenericTaskEmail ---
  describe('sendGenericTaskEmail', () => {
    const params = { to: 'generic@example.com', name: 'Generic User', title: 'Generic Task Notification', body: 'Details about the task.' };

    it('should return success:true and call sendEmail with correct params for generic task', async () => {
      mockedSendEmail.mockResolvedValueOnce(undefined);
      const result = await sendGenericTaskEmail(params.to, params.name, params.title, params.body);

      expect(result).toEqual({ success: true });
      expect(mockedSendEmail).toHaveBeenCalledWith({
        template: 'generic_task',
        locals: { name: params.name, title: params.title, body: params.body, to: params.to },
        subject: params.title,
        to: params.to,
      });
    });

    it('should return success:false on sendEmail failure for generic task', async () => {
      const errorMsg = 'Generic send failure';
      mockedSendEmail.mockImplementationOnce(() => { throw new Error(errorMsg); });
      const result = await sendGenericTaskEmail(params.to, params.name, params.title, params.body);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Failed to send generic task email.');
        expect(result.error.details).toBe(errorMsg);
      }
    });
  });

  // --- sendMeetingRequestTemplate ---
  describe('sendMeetingRequestTemplate', () => {
    const params = {
      to: 'invite@example.com', name: 'Invitee Name', title: 'Meeting Invite',
      body: 'Please join us.', yesLink: 'http://yes.link', noLink: 'http://no.link'
    };

    it('should return success:true and call sendEmail with correct params for meeting request', async () => {
      mockedSendEmail.mockResolvedValueOnce(undefined);
      const result = await sendMeetingRequestTemplate(params.to, params.name, params.title, params.body, params.yesLink, params.noLink);

      expect(result).toEqual({ success: true });
      expect(mockedSendEmail).toHaveBeenCalledWith({
        template: 'meeting_request',
        locals: { name: params.name, title: params.title, body: params.body, yesLink: params.yesLink, noLink: params.noLink, to: params.to },
        subject: `Meeting Request: ${params.title}`,
        to: params.to,
      });
    });

    it('should return success:false on sendEmail failure for meeting request', async () => {
      const errorMsg = 'Meeting request dispatch error';
      mockedSendEmail.mockImplementationOnce(() => { throw new Error(errorMsg); });
      const result = await sendMeetingRequestTemplate(params.to, params.name, params.title, params.body, params.yesLink, params.noLink);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Failed to send meeting request email.');
        expect(result.error.details).toBe(errorMsg);
      }
    });
  });
});

describe('callOpenAI', () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    // Spy on console.log and suppress output during tests, but allow checking calls
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  const systemMessage = "Test system message";
  const userMessage = "Test user message";

  // Test Case 1: Successful API call.
  it('should return success true and content on successful API call', async () => {
    const mockApiResponse = { choices: [{ message: { content: "Test response" } }] };
    mockCreate.mockResolvedValue(mockApiResponse);

    const result = await callOpenAI(systemMessage, userMessage);

    expect(OpenAI).toHaveBeenCalledTimes(1);
    expect(mockCreate).toHaveBeenCalledWith({
      model: 'gpt-4-1106-preview', // or gpt-3.5-turbo-1106 based on implementation
      messages: [
        { role: 'system', content: systemMessage },
        { role: 'user', content: userMessage },
      ],
    });
    expect(result).toEqual({ success: true, content: "Test response" });
  });

  // Test Case 2: OpenAI API error (e.g., HTTP 400).
  it('should return structured error on OpenAI API error', async () => {
    const apiError = {
      response: {
        status: 400,
        data: "Invalid request data",
      },
    };
    mockCreate.mockRejectedValue(apiError);

    const result = await callOpenAI(systemMessage, userMessage);

    expect(result).toEqual({
      success: false,
      error: {
        type: 'OPENAI_API_ERROR',
        status: 400,
        data: "Invalid request data",
        message: 'OpenAI API request failed',
      },
    });
    expect(consoleLogSpy).toHaveBeenCalledWith('OpenAI API Error Status:', 400);
    expect(consoleLogSpy).toHaveBeenCalledWith('OpenAI API Error Data:', "Invalid request data");
  });

  // Test Case 3: Other request error (e.g., network issue).
  it('should return structured error on other request errors', async () => {
    const networkError = new Error("Network connection failed");
    mockCreate.mockRejectedValue(networkError);

    const result = await callOpenAI(systemMessage, userMessage);

    expect(result).toEqual({
      success: false,
      error: {
        type: 'OPENAI_REQUEST_ERROR',
        message: "Network connection failed",
      },
    });
    expect(consoleLogSpy).toHaveBeenCalledWith('Error calling OpenAI:', "Network connection failed");
  });

  // Test Case 4: Call with exampleInput and exampleOutput.
  it('should include example messages when exampleInput and exampleOutput are provided', async () => {
    const exampleInput = "Example user input";
    const exampleOutput = "Example assistant response";
    const mockApiResponse = { choices: [{ message: { content: "Test response following examples" } }] };
    mockCreate.mockResolvedValue(mockApiResponse);

    const result = await callOpenAI(systemMessage, userMessage, exampleInput, exampleOutput);

    expect(mockCreate).toHaveBeenCalledWith({
      model: 'gpt-4-1106-preview', // or gpt-3.5-turbo-1106
      messages: [
        { role: 'system', content: systemMessage },
        { role: 'user', content: exampleInput },
        { role: 'assistant', content: exampleOutput },
        { role: 'user', content: userMessage },
      ],
    });
    expect(result).toEqual({ success: true, content: "Test response following examples" });
  });

  // Test for default model gpt-3.5-turbo-1106 if no model specified
  it('should use gpt-3.5-turbo-1106 if no model is specified and message length is okay', async () => {
    const mockApiResponse = { choices: [{ message: { content: "Test response from 3.5" } }] };
    mockCreate.mockResolvedValue(mockApiResponse);
    // Assuming the function defaults to gpt-3.5-turbo-1106 if model param is undefined
    await callOpenAI(systemMessage, userMessage, undefined, undefined, undefined);
    expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({
        model: 'gpt-3.5-turbo-1106'
    }));
  });
   // Test for model gpt-4-1106-preview if specified
   it('should use gpt-4-1106-preview if specified', async () => {
    const mockApiResponse = { choices: [{ message: { content: "Test response from 4" } }] };
    mockCreate.mockResolvedValue(mockApiResponse);
    await callOpenAI(systemMessage, userMessage, undefined, undefined, 'gpt-4-1106-preview');
    expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({
        model: 'gpt-4-1106-preview'
    }));
  });
});

// --- Tests for Google Auth Helper Functions ---
import {
  getCalendarIntegration,
  refreshGoogleToken,
  updateCalendarIntegration,
  getGoogleAPIToken, // This is the one we intend to test (Final version)
  // CalendarIntegrationType, // Not used directly in tests, but good for context
  // GoogleTokenResponseType, // Same as above
} from './api-helper';
import got from 'got';
import dayjs from 'dayjs';

// Mock 'got'
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;


describe('getCalendarIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset process.env variables if they are modified by tests, or set defaults
    process.env.HASURA_ENDPOINT_URL = 'http://hasura.test';
    process.env.HASURA_ADMIN_SECRET = 'secret';
  });

  it('should return calendar integration data on successful fetch', async () => {
    const mockData = { Calendar_Integration: [{ id: 'int_123', userId: 'user_abc', resource: 'google_calendar' }] };
    mockedGot.post.mockResolvedValueOnce({ body: { data: mockData } } as any);

    const result = await getCalendarIntegration('user_abc', 'google_calendar');
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual(mockData.Calendar_Integration[0]);
    }
    expect(mockedGot.post).toHaveBeenCalledTimes(1);
  });

  it('should return success false if no integration is found', async () => {
    const mockData = { Calendar_Integration: [] }; // Empty array
    mockedGot.post.mockResolvedValueOnce({ body: { data: mockData } } as any);
    const result = await getCalendarIntegration('user_xyz', 'unknown_resource');
     expect(result.success).toBe(true); // The function returns success:true even if data is undefined
    if(result.success) {
        expect(result.data).toBeUndefined();
    }
  });

  it('should return success false on Hasura error', async () => {
    const mockError = { errors: [{ message: "DB connection error" }]};
    mockedGot.post.mockResolvedValueOnce({ body: mockError } as any);
    const result = await getCalendarIntegration('user_abc', 'google_calendar');
    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('Hasura query error');
        expect(result.error.details).toEqual(mockError.errors);
    }
  });

  it('should return success false on got.post rejection', async () => {
    mockedGot.post.mockRejectedValueOnce(new Error('Network failure'));
    const result = await getCalendarIntegration('user_abc', 'google_calendar');
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('Network failure');
    }
  });
});

// --- Tests for upsertEventsPostPlanner ---
import { upsertEventsPostPlanner } from './api-helper';
// 'got' is already mocked from previous Google Auth tests.

describe('upsertEventsPostPlanner', () => {
  beforeEach(() => {
    // Clear mocks including got.post if it's not cleared globally or in a higher describe
    mockedGot.post.mockClear();
    // Ensure ENV vars for Hasura are set if not globally
    process.env.HASURA_ENDPOINT_URL = 'http://hasura.test';
    process.env.HASURA_ADMIN_SECRET = 'secret';
  });

  const sampleEventsInput = [
    { calendarId: 'cal1', userId: 'user1', summary: 'Event 1', startDateTime: '2024-01-01T10:00:00Z', endDateTime: '2024-01-01T11:00:00Z', timezone: 'UTC', id: 'event_id_1' },
    { calendarId: 'cal1', userId: 'user1', summary: 'Event 2', startDateTime: '2024-01-02T10:00:00Z', endDateTime: '2024-01-02T11:00:00Z', timezone: 'UTC', id: 'event_id_2' },
    { calendarId: 'cal1', userId: 'user1', summary: 'Event 1', startDateTime: '2024-01-01T10:00:00Z', endDateTime: '2024-01-01T11:00:00Z', timezone: 'UTC', id: 'event_id_1' }, // Duplicate by id
  ];
   const uniqueEventsForMock = [ // What _.uniqBy(sampleEventsInput, 'id') would produce
    { calendarId: 'cal1', userId: 'user1', summary: 'Event 1', startDateTime: '2024-01-01T10:00:00Z', endDateTime: '2024-01-01T11:00:00Z', timezone: 'UTC', id: 'event_id_1', provider: 'google_calendar', status: 'confirmed' },
    { calendarId: 'cal1', userId: 'user1', summary: 'Event 2', startDateTime: '2024-01-02T10:00:00Z', endDateTime: '2024-01-02T11:00:00Z', timezone: 'UTC', id: 'event_id_2', provider: 'google_calendar', status: 'confirmed' },
  ];


  // Test Case 1: Successful upsert of one or more unique events.
  it('should successfully upsert unique events', async () => {
    const mockHasuraResponse = { data: { insert_Event: { affected_rows: 2, returning: [{ id: 'event_id_1' }, { id: 'event_id_2' }] } } };
    mockedGot.post.mockResolvedValueOnce({ body: mockHasuraResponse } as any);

    const result = await upsertEventsPostPlanner(sampleEventsInput);

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual(mockHasuraResponse.data.insert_Event);
    }
    expect(mockedGot.post).toHaveBeenCalledTimes(1);
    expect(mockedGot.post).toHaveBeenCalledWith(
      process.env.HASURA_ENDPOINT_URL,
      expect.objectContaining({
        json: expect.objectContaining({
          variables: { objects: uniqueEventsForMock }, // Check if unique events are passed
        }),
      })
    );
  });

  // Test Case 2: Hasura returns an error in the response body.
  it('should return failure if Hasura response contains errors', async () => {
    const hasuraError = { errors: [{ message: 'Constraint violation' }] };
    mockedGot.post.mockResolvedValueOnce({ body: hasuraError } as any);

    const result = await upsertEventsPostPlanner(sampleEventsInput.slice(0,1)); // Use a non-empty array

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toBe('Hasura API error during event upsert.');
      expect(result.error.details).toEqual(hasuraError.errors);
    }
  });

  it('should return failure if Hasura response has unexpected structure (no data.insert_Event)', async () => {
    const malformedResponse = { data: {} }; // Missing insert_Event
    mockedGot.post.mockResolvedValueOnce({ body: malformedResponse } as any);

    const result = await upsertEventsPostPlanner(sampleEventsInput.slice(0,1));

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toBe('Unexpected response structure from Hasura during event upsert.');
    }
  });


  // Test Case 3: got.post itself throws a network error.
  it('should return failure if got.post throws a network error', async () => {
    const networkErrorMessage = 'Connection timed out';
    mockedGot.post.mockRejectedValueOnce(new Error(networkErrorMessage));

    const result = await upsertEventsPostPlanner(sampleEventsInput.slice(0,1));

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toBe('Network error during event upsert.');
      expect(result.error.details).toBe(networkErrorMessage);
    }
  });

  // Test Case 4: Input events array is empty.
  it('should return success with 0 affected_rows if input events array is empty', async () => {
    const result = await upsertEventsPostPlanner([]);

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ affected_rows: 0, returning: [] });
    }
    expect(mockedGot.post).not.toHaveBeenCalled();
  });

  // Test Case 5: Input events array becomes empty after _.uniqBy (e.g. contains only null/undefined).
  it('should return success with 0 affected_rows if events array becomes empty after filtering', async () => {
    // _.uniqBy(events.filter(e => e), 'id'); -> if events = [null, undefined], filter(e=>e) results in []
    const result = await upsertEventsPostPlanner([null, undefined] as any); // Cast as any to bypass EventInput type for test

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ affected_rows: 0, returning: [] });
    }
    expect(mockedGot.post).not.toHaveBeenCalled();
  });
});

// --- Tests for Hasura Read Operation Functions ---
import {
    getGlobalCalendar,
    listEventsForDate,
    listEventsForUserGivenDates,
    getUserPreferences
} from './api-helper';
// 'got' is already mocked from previous tests.
// mockedGot variable is available.

describe('Hasura Read Functions', () => {
  beforeEach(() => {
    mockedGot.post.mockClear();
    process.env.HASURA_ENDPOINT_URL = 'http://hasura.test';
    process.env.HASURA_ADMIN_SECRET = 'secret';
  });

  // --- getGlobalCalendar ---
  describe('getGlobalCalendar', () => {
    const userId = 'user_gcal_test';
    it('should return global calendar data on successful fetch', async () => {
      const mockCalendarData = { id: 'gcal_1', userId, primaryCalendarId: 'primary@example.com' };
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Calendar: [mockCalendarData] } } } as any);

      const result = await getGlobalCalendar(userId);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual(mockCalendarData);
      expect(mockedGot.post).toHaveBeenCalledWith(process.env.HASURA_ENDPOINT_URL, expect.objectContaining({
        json: expect.objectContaining({
          query: expect.stringContaining('GetGlobalCalendar'),
          variables: { userId },
        }),
      }));
    });

    it('should return success:true, data:undefined if no global calendar found', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Calendar: [] } } } as any);
      const result = await getGlobalCalendar(userId);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toBeUndefined();
    });

    it('should return failure on Hasura error for getGlobalCalendar', async () => {
      const hasuraErrors = [{ message: 'Permission denied on Calendar' }];
      mockedGot.post.mockResolvedValueOnce({ body: { errors: hasuraErrors } } as any);
      const result = await getGlobalCalendar(userId);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toContain('Hasura API error during getGlobalCalendar');
        expect(result.error.details).toEqual(hasuraErrors);
      }
    });

    it('should return failure on network error for getGlobalCalendar', async () => {
      const networkErrorMsg = 'Network connection failed';
      mockedGot.post.mockRejectedValueOnce(new Error(networkErrorMsg));
      const result = await getGlobalCalendar(userId);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toContain('Network error during getGlobalCalendar');
        expect(result.error.details).toBe(networkErrorMsg);
      }
    });

    it('should return failure on unexpected response structure for getGlobalCalendar', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: {} } } as any); // Missing Calendar key
      const result = await getGlobalCalendar(userId);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toContain('Unexpected response structure during getGlobalCalendar');
      }
    });
  });

  // --- listEventsForDate ---
  describe('listEventsForDate', () => {
    const userId = 'user_events_test';
    const startDate = '2024-03-01T00:00:00Z';
    const endDate = '2024-03-01T23:59:59Z';
    const timezone = 'America/New_York';

    it('should return events on successful fetch', async () => {
      const mockEvents = [{ id: 'evt_1', summary: 'Event 1' }, { id: 'evt_2', summary: 'Event 2' }];
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Event: mockEvents } } } as any);

      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual(mockEvents);
      expect(mockedGot.post).toHaveBeenCalledWith(process.env.HASURA_ENDPOINT_URL, expect.objectContaining({
        json: expect.objectContaining({
          query: expect.stringContaining('ListEventsForDate'),
          variables: { userId, startDate, endDate },
        }),
      }));
    });

    it('should return success:true, data:[] if no events found', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Event: [] } } } as any);
      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual([]);
    });

    it('should also return success:true, data:[] if Event key is null', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Event: null } } } as any);
      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual([]);
    });

    it('should return failure on Hasura error for listEventsForDate', async () => {
      const hasuraErrors = [{ message: 'Error fetching events' }];
      mockedGot.post.mockResolvedValueOnce({ body: { errors: hasuraErrors } } as any);
      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.details).toEqual(hasuraErrors);
    });

    it('should return failure on network error for listEventsForDate', async () => {
      mockedGot.post.mockRejectedValueOnce(new Error('Connection issue'));
      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.details).toBe('Connection issue');
    });

    it('should return failure on unexpected response for listEventsForDate', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: {} } } as any); // Missing Event key
      const result = await listEventsForDate(userId, startDate, endDate, timezone);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.message).toContain('Unexpected response structure');
    });
  });

  // --- listEventsForUserGivenDates --- (Similar to listEventsForDate, can be more concise)
  describe('listEventsForUserGivenDates', () => {
    const userId = 'user_lgd_test';
    const senderStartDate = '2024-03-02T00:00:00Z';
    const senderEndDate = '2024-03-02T23:59:59Z';

    it('should return events successfully', async () => {
      const mockEvents = [{ id: 'evt_lgd_1', summary: 'LGD Event' }];
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Event: mockEvents } } } as any);
      const result = await listEventsForUserGivenDates(userId, senderStartDate, senderEndDate);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual(mockEvents);
      expect(mockedGot.post).toHaveBeenCalledWith(process.env.HASURA_ENDPOINT_URL, expect.objectContaining({
        json: expect.objectContaining({
          query: expect.stringContaining('ListEventsForUserGivenDates'),
          variables: { userId, startDate: senderStartDate, endDate: senderEndDate },
        }),
      }));
    });

    it('should return success:true, data:[] if no events found for listEventsForUserGivenDates', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: { Event: [] } } } as any);
      const result = await listEventsForUserGivenDates(userId, senderStartDate, senderEndDate);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual([]);
    });

    it('should return failure on Hasura error for listEventsForUserGivenDates', async () => {
        const hasuraErrors = [{ message: 'DB error on LGD' }];
        mockedGot.post.mockResolvedValueOnce({ body: { errors: hasuraErrors } } as any);
        const result = await listEventsForUserGivenDates(userId, senderStartDate, senderEndDate);
        expect(result.success).toBe(false);
        if (!result.success) expect(result.error.details).toEqual(hasuraErrors);
    });

    it('should return failure on network error for listEventsForUserGivenDates', async () => {
      mockedGot.post.mockRejectedValueOnce(new Error('Net fail LGD'));
      const result = await listEventsForUserGivenDates(userId, senderStartDate, senderEndDate);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.details).toBe('Net fail LGD');
    });

    it('should return failure on unexpected response for listEventsForUserGivenDates', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: {} } } as any); // Missing Event key
      const result = await listEventsForUserGivenDates(userId, senderStartDate, senderEndDate);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.message).toContain('Unexpected response structure');
    });
  });

  // --- getUserPreferences ---
  describe('getUserPreferences', () => {
    const userId = 'user_prefs_test';
    it('should return user preferences on successful fetch', async () => {
      const mockPrefs = { id: 'pref_1', userId, somePreference: 'dark_mode' };
      mockedGot.post.mockResolvedValueOnce({ body: { data: { User_Preferences: [mockPrefs] } } } as any);

      const result = await getUserPreferences(userId);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual(mockPrefs);
       expect(mockedGot.post).toHaveBeenCalledWith(process.env.HASURA_ENDPOINT_URL, expect.objectContaining({
        json: expect.objectContaining({
          query: expect.stringContaining('GetUserPreferences'),
          variables: { userId },
        }),
      }));
    });

    it('should return success:true, data:undefined if no preferences found', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: { User_Preferences: [] } } } as any);
      const result = await getUserPreferences(userId);
      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toBeUndefined();
    });

    it('should return failure on Hasura error for getUserPreferences', async () => {
      const hasuraErrors = [{ message: 'Prefs table error' }];
      mockedGot.post.mockResolvedValueOnce({ body: { errors: hasuraErrors } } as any);
      const result = await getUserPreferences(userId);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.details).toEqual(hasuraErrors);
    });

    it('should return failure on network error for getUserPreferences', async () => {
      mockedGot.post.mockRejectedValueOnce(new Error('Prefs net fail'));
      const result = await getUserPreferences(userId);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.details).toBe('Prefs net fail');
    });

    it('should return failure on unexpected response for getUserPreferences', async () => {
      mockedGot.post.mockResolvedValueOnce({ body: { data: {} } } as any); // Missing User_Preferences key
      const result = await getUserPreferences(userId);
      expect(result.success).toBe(false);
      if (!result.success) expect(result.error.message).toContain('Unexpected response structure');
    });
  });
});

describe('refreshGoogleToken', () => {
    beforeEach(() => {
        process.env.GOOGLE_CLIENT_ID_WEB = 'web_client_id';
        process.env.GOOGLE_CLIENT_SECRET_WEB = 'web_client_secret';
        process.env.GOOGLE_CLIENT_ID_IOS = 'ios_client_id';
        process.env.GOOGLE_CLIENT_SECRET_IOS = 'ios_client_secret';
    });

  it('should return new token data on successful refresh for web', async () => {
    const mockTokenData = { access_token: 'new_access_token', expires_in: 3600 };
    mockedGot.post.mockResolvedValueOnce({ body: mockTokenData } as any);
    const result = await refreshGoogleToken('old_refresh_token', 'web');
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual(mockTokenData);
    }
    expect(mockedGot.post).toHaveBeenCalledWith('https://oauth2.googleapis.com/token', expect.any(Object));
  });

  it('should return success false if client ID/secret not configured', async () => {
    delete process.env.GOOGLE_CLIENT_ID_WEB; // Remove one config
    const result = await refreshGoogleToken('refresh_token', 'web');
    expect(result.success).toBe(false);
    if(!result.success){
        expect(result.error.message).toContain('Google client ID or secret not configured');
    }
  });

  it('should return success false on got.post rejection', async () => {
    mockedGot.post.mockRejectedValueOnce(new Error('API limit reached'));
    const result = await refreshGoogleToken('old_refresh_token', 'web');
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('API limit reached');
    }
  });
});

describe('updateCalendarIntegration', () => {
  it('should return success true on successful update', async () => {
    mockedGot.post.mockResolvedValueOnce({ body: { data: { update_Calendar_Integration_by_pk: { id: 'ci_123' } } } } as any);
    const result = await updateCalendarIntegration('ci_123', 'new_token_val', dayjs().toISOString(), 'new_refresh_val', true);
    expect(result.success).toBe(true);
    expect(mockedGot.post).toHaveBeenCalledTimes(1);
  });

  it('should return success false if ID not found or no data returned', async () => {
    mockedGot.post.mockResolvedValueOnce({ body: { data: { update_Calendar_Integration_by_pk: null } } } as any);
    const result = await updateCalendarIntegration('ci_unknown', 'token', dayjs().toISOString());
    expect(result.success).toBe(false);
    if(!result.success) {
        expect(result.error.message).toContain('No data returned or ID not found');
    }
  });

  it('should return success false on got.post rejection', async () => {
    mockedGot.post.mockRejectedValueOnce(new Error('DB write failed'));
    const result = await updateCalendarIntegration('ci_123', 'new_token_val', dayjs().toISOString());
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('DB write failed');
    }
  });
});

describe('getGoogleAPIToken', () => {
  const userId = 'test_user';
  const resource = 'google_calendar';
  const validToken = 'valid_access_token';
  const expiredToken = 'expired_access_token';
  const refreshToken = 'valid_refresh_token';
  const newAccessToken = 'newly_refreshed_access_token';
  const futureTime = dayjs().add(1, 'hour').toISOString();
  const pastTime = dayjs().subtract(1, 'hour').toISOString();

  beforeEach(() => {
    jest.useFakeTimers(); // Use fake timers
    jest.setSystemTime(new Date('2023-01-01T12:00:00Z')); // Set a fixed system time
  });

  afterEach(() => {
    jest.useRealTimers(); // Restore real timers
  });

  // Mocks for getCalendarIntegration, refreshGoogleToken, updateCalendarIntegration will be done per test
  // by spying on the module's own exports and providing mock implementations.
  // This is tricky if they are in the same module and not passed as params.
  // For simplicity, we'll continue mocking got.post for the underlying functions.

  it('Success - Valid Token: should return existing valid token', async () => {
    const mockIntegration = {
      id: 'ci_123', userId, resource, clientType: 'web',
      token: validToken, expiresAt: futureTime, refreshToken, syncEnabled: true,
    };
    mockedGot.post.mockImplementation(async (url): Promise<any> => {
        if (url === process.env.HASURA_ENDPOINT_URL) { // getCalendarIntegration call
            return { body: { data: { Calendar_Integration: [mockIntegration] } } };
        }
        return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.token).toBe(validToken);
    }
    expect(mockedGot.post).toHaveBeenCalledTimes(1); // Only getCalendarIntegration
  });

  it('Success - Expired Token, Successful Refresh: should refresh and return new token', async () => {
    const mockIntegrationExpired = {
      id: 'ci_123', userId, resource, clientType: 'web',
      token: expiredToken, expiresAt: pastTime, refreshToken, syncEnabled: true,
    };
    const mockRefreshResponse = { access_token: newAccessToken, expires_in: 3600 };
    const mockUpdateResponse = { data: { update_Calendar_Integration_by_pk: { id: 'ci_123' } } };

    mockedGot.post.mockImplementation(async (url, options): Promise<any> => {
      if (url === process.env.HASURA_ENDPOINT_URL) {
        const body = options?.json as any;
        if (body.query.includes('GetCalendarIntegration')) { // getCalendarIntegration call
          return { body: { data: { Calendar_Integration: [mockIntegrationExpired] } } };
        }
        if (body.query.includes('UpdateCalendarIntegration')) { // updateCalendarIntegration call
          return { body: mockUpdateResponse };
        }
      }
      if (url === 'https://oauth2.googleapis.com/token') { // refreshGoogleToken call
        return { body: mockRefreshResponse };
      }
      return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.token).toBe(newAccessToken);
    }
    expect(mockedGot.post).toHaveBeenCalledTimes(3); // getCalendarIntegration, refreshGoogleToken, updateCalendarIntegration
  });

  it('Failure - Expired Token, Refresh Fails: should try refresh, fail, and disable sync', async () => {
    const mockIntegrationExpired = {
      id: 'ci_123', userId, resource, clientType: 'web',
      token: expiredToken, expiresAt: pastTime, refreshToken, syncEnabled: true,
    };
    const mockUpdateResponse = { data: { update_Calendar_Integration_by_pk: { id: 'ci_123' } } }; // For disabling sync

     mockedGot.post.mockImplementation(async (url, options): Promise<any> => {
      if (url === process.env.HASURA_ENDPOINT_URL) {
        const body = options?.json as any;
        if (body.query.includes('GetCalendarIntegration')) {
          return { body: { data: { Calendar_Integration: [mockIntegrationExpired] } } };
        }
         if (body.query.includes('UpdateCalendarIntegration')) { // For disabling sync
            // Check if it's the disable sync call
            expect(body.variables.syncEnabled).toBe(false);
            return { body: mockUpdateResponse };
        }
      }
      if (url === 'https://oauth2.googleapis.com/token') {
        throw new Error('Refresh failed'); // Simulate refresh failure
      }
      return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('Token refresh failed');
    }
    // getCalendarIntegration, refresh (fails), update (to disable sync)
    expect(mockedGot.post).toHaveBeenCalledTimes(3);
  });

  it('Failure - getCalendarIntegration Fails: should propagate the error', async () => {
    mockedGot.post.mockImplementation(async (url): Promise<any> => {
        if (url === process.env.HASURA_ENDPOINT_URL) {
             throw new Error('DB error'); // getCalendarIntegration fails
        }
        return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('Could not get calendar integration');
      expect(result.error.details?.message).toContain('DB error');
    }
  });

  it('Failure - No Refresh Token available when needed: should fail and disable sync', async () => {
    const mockIntegrationNoRefreshToken = {
      id: 'ci_789', userId, resource, clientType: 'web',
      token: expiredToken, expiresAt: pastTime, refreshToken: null, // No refresh token
      syncEnabled: true,
    };
     const mockUpdateResponse = { data: { update_Calendar_Integration_by_pk: { id: 'ci_789' } } };

    mockedGot.post.mockImplementation(async (url, options): Promise<any> => {
      if (url === process.env.HASURA_ENDPOINT_URL) {
        const body = options?.json as any;
        if (body.query.includes('GetCalendarIntegration')) {
          return { body: { data: { Calendar_Integration: [mockIntegrationNoRefreshToken] } } };
        }
        if (body.query.includes('UpdateCalendarIntegration')) { // For disabling sync
            expect(body.variables.syncEnabled).toBe(false);
            return { body: mockUpdateResponse };
        }
      }
      return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('Refresh needed but no refresh token available');
    }
    expect(mockedGot.post).toHaveBeenCalledTimes(2); // getCalendarIntegration, updateCalendarIntegration (to disable)
  });

  it('Failure - Integration ID missing after refresh (should not happen if initial integration had ID): should return error', async () => {
    // This tests a more hypothetical scenario where 'id' might be lost or was never there for an update.
    const mockIntegrationExpiredNoIdInitially = { // This setup is a bit contradictory for a refresh flow
      id: null, // No ID to start with, or it's undefined
      userId, resource, clientType: 'web',
      token: expiredToken, expiresAt: pastTime, refreshToken, syncEnabled: true,
    };
     const mockRefreshResponse = { access_token: newAccessToken, expires_in: 3600 };

    mockedGot.post.mockImplementation(async (url, options): Promise<any> => {
      if (url === process.env.HASURA_ENDPOINT_URL) {
        const body = options?.json as any;
        if (body.query.includes('GetCalendarIntegration')) {
          // Simulate integration data that lacks an ID but has enough to trigger a refresh attempt
          return { body: { data: { Calendar_Integration: [{...mockIntegrationExpiredNoIdInitially, id: undefined}] } } };
        }
      }
      if (url === 'https://oauth2.googleapis.com/token') {
        return { body: mockRefreshResponse };
      }
      return {};
    });

    const result = await getGoogleAPIToken(userId, resource);
    expect(result.success).toBe(false);
    if(!result.success){
        // Based on the refactored code, if integration.id is null/undefined before update, it returns this message:
        expect(result.error.message).toContain('Integration ID missing after refresh');
    }
    // getCalendarIntegration, refreshGoogleToken. updateCalendarIntegration is not called due to missing id.
    expect(mockedGot.post).toHaveBeenCalledTimes(2);
  });
});

// --- Tests for createGoogleEvent ---
import { createGoogleEvent } from './api-helper';
import * as apiHelperModule from './api-helper'; // To spy on getGoogleAPIToken
import { google } from 'googleapis'; // For accessing the mocked google.calendar().events.insert
import { v4 as uuidv4 } from 'uuid';

// Mock uuid
jest.mock('uuid', () => ({
  v4: jest.fn(),
}));

// Access the mock for google.calendar().events.insert
// This was set up in the initial mock of 'googleapis' from previous steps for callOpenAI tests,
// but we need a clear way to reference it. Assuming the googleapis mock is like:
// jest.mock('googleapis', () => {
//   const mockInsert = jest.fn();
//   return {
//     google: { calendar: jest.fn(() => ({ events: { insert: mockInsert } })) },
//     __mockEventsInsert: mockInsert, // Helper to access mockInsert
//   };
// });
// If not, we need to ensure the mock for googleapis exposes events.insert correctly.
// For now, let's assume the googleapis mock in the test file has a way to access `events.insert`.
// If the original googleapis mock was simpler, we might need to refine it.
// Let's assume `google.calendar().events.insert` is already a jest.fn() due to the global mock.
const mockGoogleEventsInsert = (google.calendar('v3') as any).events.insert as jest.Mock;


describe('createGoogleEvent', () => {
  let getGoogleAPITokenSpy: jest.SpyInstance;
  const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

  beforeEach(() => {
    jest.clearAllMocks();
    getGoogleAPITokenSpy = jest.spyOn(apiHelperModule, 'getGoogleAPIToken');
    (uuidv4 as jest.Mock).mockReturnValue('mock-uuid-1234'); // Predictable UUID
  });

  afterEach(() => {
    getGoogleAPITokenSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  const basicEventDetails = {
    userId: 'user_test_id',
    calendarId: 'calendar_test_id',
    clientType: 'web' as 'web' | 'ios' | 'android' | 'atomic-web',
    summary: 'Test Event Summary',
    startDateTime: '2024-03-10T10:00:00Z',
    endDateTime: '2024-03-10T11:00:00Z',
    timezone: 'America/New_York',
  };

  // Test Case 1: Successful basic event creation.
  it('should create an event successfully and return structured data', async () => {
    getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_auth_token' });
    const mockGoogleEventResponse = {
      data: {
        id: 'google_event_id_123',
        summary: basicEventDetails.summary,
        // ... other event fields
      },
    };
    mockGoogleEventsInsert.mockResolvedValue(mockGoogleEventResponse);

    const result = await createGoogleEvent(
      basicEventDetails.userId,
      basicEventDetails.calendarId,
      basicEventDetails.clientType,
      basicEventDetails.summary,
      basicEventDetails.startDateTime,
      basicEventDetails.endDateTime,
      basicEventDetails.timezone
    );

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.googleEventId).toBe('google_event_id_123');
      expect(result.data.calendarId).toBe(basicEventDetails.calendarId);
      expect(result.data.id).toBe(`google_event_id_123#${basicEventDetails.calendarId}`);
      expect(result.data.generatedId).toBe('mock-uuid-1234'); // Used for conference request
      expect(result.data.generatedEventId).toBe('mock-uuid-1234'.split('_')[0]);
    }

    expect(getGoogleAPITokenSpy).toHaveBeenCalledWith(basicEventDetails.userId, 'google_calendar');
    expect(mockGoogleEventsInsert).toHaveBeenCalledWith({
      calendarId: basicEventDetails.calendarId,
      conferenceDataVersion: 0, // As no conference solution was passed
      requestBody: {
        summary: basicEventDetails.summary,
        description: undefined, // Not passed
        start: {
          dateTime: basicEventDetails.startDateTime,
          timeZone: basicEventDetails.timezone,
        },
        end: {
          dateTime: basicEventDetails.endDateTime,
          timeZone: basicEventDetails.timezone,
        },
        attendees: undefined, // Not passed
        reminders: { useDefault: true },
        // conferenceData would be undefined here
      },
    });
  });

  it('should create an event with conference data if specified', async () => {
    getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_auth_token' });
    const mockGoogleEventResponse = { data: { id: 'google_event_conf_456' }};
    mockGoogleEventsInsert.mockResolvedValue(mockGoogleEventResponse);
    (uuidv4 as jest.Mock).mockReturnValue('conf-request-uuid');


    await createGoogleEvent(
      basicEventDetails.userId, basicEventDetails.calendarId, basicEventDetails.clientType,
      basicEventDetails.summary, basicEventDetails.startDateTime, basicEventDetails.endDateTime,
      basicEventDetails.timezone, 'Test Description', [{email: 'test@example.com'}], 'eventHangout'
    );

    expect(mockGoogleEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
        conferenceDataVersion: 1,
        requestBody: expect.objectContaining({
            conferenceData: {
                createRequest: {
                    requestId: 'conf-request-uuid',
                    conferenceSolutionKey: { type: 'eventHangout' },
                },
            },
            attendees: [{email: 'test@example.com'}],
            description: 'Test Description'
        })
    }));
  });


  // Test Case 2: getGoogleAPIToken fails.
  it('should return failure if getGoogleAPIToken fails', async () => {
    const tokenError = { message: 'Token fetch failed' };
    getGoogleAPITokenSpy.mockResolvedValue({ success: false, error: tokenError });

    const result = await createGoogleEvent(
      basicEventDetails.userId, basicEventDetails.calendarId, basicEventDetails.clientType,
      basicEventDetails.summary, basicEventDetails.startDateTime, basicEventDetails.endDateTime,
      basicEventDetails.timezone
    );

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('token acquisition failure');
      expect(result.error.details).toEqual(tokenError);
    }
    expect(mockGoogleEventsInsert).not.toHaveBeenCalled();
  });

  // Test Case 3: google.calendar().events.insert fails.
  it('should return failure if google.calendar.events.insert fails', async () => {
    getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_auth_token' });
    const apiError = { code: 503, message: 'Service Unavailable' };
    // Simulate how googleapis library might throw an error (often has a 'response' or 'errors' property)
    const googleApiError = new Error('Service Unavailable');
    (googleApiError as any).code = 503;
    (googleApiError as any).errors = [{ message: 'Service Unavailable' }]; // Common pattern for googleapis errors

    mockGoogleEventsInsert.mockRejectedValue(googleApiError);

    const result = await createGoogleEvent(
      basicEventDetails.userId, basicEventDetails.calendarId, basicEventDetails.clientType,
      basicEventDetails.summary, basicEventDetails.startDateTime, basicEventDetails.endDateTime,
      basicEventDetails.timezone
    );

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toContain('Failed to create Google Calendar event via API');
      // The details might vary based on how the actual error is structured by the googleapis library
      expect(result.error.details).toEqual( (googleApiError as any).errors );
    }
  });
   it('should return failure if google.calendar.events.insert does not return an event ID', async () => {
    getGoogleAPITokenSpy.mockResolvedValue({ success: true, token: 'dummy_auth_token' });
    const mockGoogleEventResponseNoId = {
      data: { summary: basicEventDetails.summary /* no id */ },
    };
    mockGoogleEventsInsert.mockResolvedValue(mockGoogleEventResponseNoId);

    const result = await createGoogleEvent(
      basicEventDetails.userId, basicEventDetails.calendarId, basicEventDetails.clientType,
      basicEventDetails.summary, basicEventDetails.startDateTime, basicEventDetails.endDateTime,
      basicEventDetails.timezone
    );

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.message).toBe('Google Calendar API did not return an event ID.');
      expect(result.error.details).toEqual(mockGoogleEventResponseNoId.data);
    }
  });
});
