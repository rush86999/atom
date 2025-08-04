// Test file for productivitySkills.ts
import { handlePrepareForMeeting } from '../productivitySkills';
// Import findTargetMeeting if it's exported and needs direct testing,
// otherwise it's tested via handlePrepareForMeeting.
// For this example, let's assume findTargetMeeting is not directly exported for testing.
import * as calendarSkills from '../calendarSkills';
import * as notionSkills from '../notionAndResearchSkills';
import * as emailSkills from '../emailSkills';
// Mocking the dependent skill modules
jest.mock('../calendarSkills');
jest.mock('../notionAndResearchSkills');
jest.mock('../emailSkills');
const mockListUpcomingEvents = calendarSkills.listUpcomingEvents;
const mockSearchNotionRaw = notionSkills.searchNotionRaw;
const mockQueryNotionTasks = notionSkills.queryNotionTasks;
const mockSearchEmailsNLU = emailSkills.searchEmailsNLU;
describe('productivitySkills', () => {
    const mockUserId = 'test-user-123';
    const mockNotionTasksDbId = 'mock-notion-db-id';
    beforeEach(() => {
        // Reset mocks before each test
        mockListUpcomingEvents.mockReset();
        mockSearchNotionRaw.mockReset();
        mockQueryNotionTasks.mockReset();
        mockSearchEmailsNLU.mockReset();
        // Setup default successful responses for mocks (can be overridden in specific tests)
        mockListUpcomingEvents.mockResolvedValue([]);
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [] });
        mockQueryNotionTasks.mockResolvedValue({
            success: true,
            tasks: [],
            message: 'Tasks fetched',
        });
        mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: [] });
        // Mock process.env
        process.env.ATOM_NOTION_TASKS_DATABASE_ID = mockNotionTasksDbId;
    });
    afterEach(() => {
        delete process.env.ATOM_NOTION_TASKS_DATABASE_ID;
    });
    describe('handlePrepareForMeeting', () => {
        const upcomingEvent1 = {
            id: 'event1',
            summary: 'Team Sync Q3 Planning',
            startTime: new Date(Date.now() + 1000 * 60 * 60).toISOString(), // In 1 hour
            endTime: new Date(Date.now() + 1000 * 60 * 120).toISOString(), // In 2 hours
            attendees: [
                { email: 'user1@example.com', displayName: 'User One' },
                { email: 'user2@example.com' },
            ],
            description: 'Discuss Q3 goals and roadmap',
        };
        const upcomingEvent2 = {
            id: 'event2',
            summary: 'Client Call - Project Alpha',
            startTime: new Date(Date.now() + 1000 * 60 * 60 * 24).toISOString(), // Tomorrow
            endTime: new Date(Date.now() + 1000 * 60 * 60 * 25).toISOString(),
            attendees: [
                { email: 'client@example.com', displayName: 'Client Contact' },
            ],
        };
        it('should return MEETING_NOT_FOUND if no meeting matches the identifier', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            const response = await handlePrepareForMeeting(mockUserId, 'NonExistent Meeting');
            expect(response.ok).toBe(false);
            expect(response.error?.code).toBe('MEETING_NOT_FOUND');
            expect(response.error?.message).toContain('Could not find the specified meeting');
        });
        it('should return MEETING_NOT_FOUND if listUpcomingEvents returns no events', async () => {
            mockListUpcomingEvents.mockResolvedValue([]);
            const response = await handlePrepareForMeeting(mockUserId, 'Any Meeting');
            expect(response.ok).toBe(false);
            expect(response.error?.code).toBe('MEETING_NOT_FOUND');
        });
        it('should pick the next upcoming meeting if identifier is "next meeting"', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1, upcomingEvent2].sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime()));
            const response = await handlePrepareForMeeting(mockUserId, 'next meeting');
            expect(response.ok).toBe(true);
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
        });
        it('should pick the next upcoming meeting if no identifier is provided', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1, upcomingEvent2].sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime()));
            const response = await handlePrepareForMeeting(mockUserId); // No identifier
            expect(response.ok).toBe(true);
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
        });
        it('should successfully prepare for a meeting with data from all sources', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            const mockNotionPages = [
                {
                    id: 'notion1',
                    title: 'Q3 Planning Notes',
                    url: 'http://notion.so/q3planning',
                    content_preview: 'Key points from last sync...',
                },
            ];
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: mockNotionPages,
            });
            const mockEmails = [
                {
                    id: 'email1',
                    subject: 'Prep for Q3 Sync',
                    sender: 'user1@example.com',
                    recipient: '',
                    body: 'See attached doc',
                    timestamp: new Date().toISOString(),
                    read: false,
                },
            ];
            mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: mockEmails });
            const mockTasks = [
                {
                    id: 'task1',
                    description: 'Draft Q3 roadmap',
                    dueDate: '2024-08-01',
                    status: 'In Progress',
                    createdDate: '',
                    url: 'http://notion.so/task1',
                },
            ];
            mockQueryNotionTasks.mockResolvedValue({
                success: true,
                tasks: mockTasks,
            });
            const response = await handlePrepareForMeeting(mockUserId, 'Team Sync Q3 Planning');
            expect(response.ok).toBe(true);
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
            expect(response.data?.relatedNotionPages).toHaveLength(1);
            expect(response.data?.relatedNotionPages?.[0].title).toBe('Q3 Planning Notes');
            expect(response.data?.relatedEmails).toHaveLength(1);
            expect(response.data?.relatedEmails?.[0].subject).toBe('Prep for Q3 Sync');
            expect(response.data?.relatedTasks).toHaveLength(1);
            expect(response.data?.relatedTasks?.[0].description).toBe('Draft Q3 roadmap');
            expect(response.data?.errorMessage).toBeFalsy();
        });
        it('should handle cases where some data sources return no results', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [] }); // No Notion pages
            mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: [] }); // No Emails
            // Tasks will be fetched by default mock (empty array)
            const response = await handlePrepareForMeeting(mockUserId, 'Team Sync Q3 Planning');
            expect(response.ok).toBe(true);
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
            expect(response.data?.relatedNotionPages).toHaveLength(0);
            expect(response.data?.relatedEmails).toHaveLength(0);
            expect(response.data?.relatedTasks).toHaveLength(0);
            expect(response.data?.errorMessage).toBeFalsy(); // Not an error, just no data
        });
        it('should include error messages if a data source fetch fails, but still return overall OK with partial data', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            mockSearchNotionRaw.mockResolvedValue({
                ok: false,
                error: { code: 'NOTION_API_ERROR', message: 'Notion API timeout' },
            });
            const mockEmails = [
                {
                    id: 'email1',
                    subject: 'Prep for Q3 Sync',
                    sender: 'user1@example.com',
                    recipient: '',
                    body: 'See attached doc',
                    timestamp: new Date().toISOString(),
                    read: false,
                },
            ];
            mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: mockEmails });
            // Tasks will be fetched by default mock (empty array)
            const response = await handlePrepareForMeeting(mockUserId, 'Team Sync Q3 Planning');
            expect(response.ok).toBe(true); // Overall skill is ok, but with partial data
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
            expect(response.data?.relatedNotionPages).toBeUndefined(); // Or empty array, depending on implementation
            expect(response.data?.relatedEmails).toHaveLength(1);
            expect(response.data?.errorMessage).toContain('Could not fetch Notion documents: Notion API timeout.');
        });
        it('should handle ATOM_NOTION_TASKS_DATABASE_ID not being set', async () => {
            delete process.env.ATOM_NOTION_TASKS_DATABASE_ID; // Unset the env var
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            // Other mocks as default (empty results)
            const response = await handlePrepareForMeeting(mockUserId, 'Team Sync Q3 Planning');
            expect(response.ok).toBe(true);
            expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
            expect(response.data?.relatedTasks).toBeUndefined(); // Or empty array
            expect(response.data?.errorMessage).toContain('Notion tasks database ID not configured.');
            process.env.ATOM_NOTION_TASKS_DATABASE_ID = mockNotionTasksDbId; // Reset for other tests
        });
        it('should limit the number of results for each context type to MAX_RESULTS_PER_CONTEXT', async () => {
            mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);
            const manyNotionPages = Array(5)
                .fill(null)
                .map((_, i) => ({ id: `notion${i}`, title: `Page ${i}` }));
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: manyNotionPages,
            });
            const manyEmails = Array(5)
                .fill(null)
                .map((_, i) => ({
                id: `email${i}`,
                subject: `Email ${i}`,
                sender: '',
                recipient: '',
                body: '',
                timestamp: '',
                read: false,
            }));
            mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: manyEmails });
            const manyTasks = Array(5)
                .fill(null)
                .map((_, i) => ({
                id: `task${i}`,
                description: `Task ${i}`,
                status: 'To Do',
                createdDate: '',
                url: '',
            }));
            mockQueryNotionTasks.mockResolvedValue({
                success: true,
                tasks: manyTasks,
            });
            const response = await handlePrepareForMeeting(mockUserId, 'Team Sync Q3 Planning');
            expect(response.ok).toBe(true);
            // MAX_RESULTS_PER_CONTEXT is 3 in productivitySkills.ts
            expect(response.data?.relatedNotionPages).toHaveLength(3);
            expect(response.data?.relatedEmails).toHaveLength(3);
            expect(response.data?.relatedTasks).toHaveLength(3);
        });
    });
    // --- Tests for Automated Weekly Digest ---
    describe('determineDateRange', () => {
        // To make these tests deterministic, we need to mock Date constructor or use a date utility library.
        // For conceptual tests, we'll describe the expected logic based on a fixed "today".
        // Let's assume "today" is Wednesday, July 24, 2024, for these conceptual calculations.
        const WEDNESDAY_JUL_24_2024 = new Date(2024, 6, 24); // Month is 0-indexed
        beforeEach(() => {
            jest.useFakeTimers().setSystemTime(WEDNESDAY_JUL_24_2024);
        });
        afterEach(() => {
            jest.useRealTimers();
        });
        it('should correctly determine "this week" (Mon to current day if before Fri 5pm)', () => {
            const { startDate, endDate, displayRange, nextPeriodStartDate, nextPeriodEndDate, } = determineDateRange('this week');
            // Expected: Mon, Jul 22, 2024 to Wed, Jul 24, 2024
            expect(startDate.getFullYear()).toBe(2024);
            expect(startDate.getMonth()).toBe(6); // July
            expect(startDate.getDate()).toBe(22); // Monday
            expect(endDate.getFullYear()).toBe(2024);
            expect(endDate.getMonth()).toBe(6); // July
            expect(endDate.getDate()).toBe(24); // Wednesday (today)
            expect(endDate.getHours()).toBe(23); // End of day
            expect(displayRange).toContain('This Week (Jul 22 - Jul 24)');
            // Next period starts Jul 25 (Thu) and ends Jul 31 (Wed)
            expect(nextPeriodStartDate.getDate()).toBe(25);
            expect(nextPeriodEndDate.getDate()).toBe(31);
        });
        it('should correctly determine "this week" as Mon-Fri if current day is past Friday 5pm or weekend', () => {
            jest.useFakeTimers().setSystemTime(new Date(2024, 6, 26, 18, 0, 0)); // Friday 6 PM
            const { startDate, endDate, displayRange } = determineDateRange('this week');
            // Expected: Mon, Jul 22, 2024 to Fri, Jul 26, 2024
            expect(startDate.getDate()).toBe(22);
            expect(endDate.getDate()).toBe(26); // Friday
            expect(displayRange).toContain('This Week (Jul 22 - Jul 26)');
            jest.useFakeTimers().setSystemTime(new Date(2024, 6, 27)); // Saturday
            const { startDate: satStart, endDate: satEnd } = determineDateRange('this week');
            expect(satStart.getDate()).toBe(22);
            expect(satEnd.getDate()).toBe(26); // Still shows Mon-Fri
        });
        it('should correctly determine "last week" (Mon to Sun)', () => {
            // Today is Wed, Jul 24, 2024
            const { startDate, endDate, displayRange, nextPeriodStartDate, nextPeriodEndDate, } = determineDateRange('last week');
            // Expected: Mon, Jul 15, 2024 to Sun, Jul 21, 2024
            expect(startDate.getFullYear()).toBe(2024);
            expect(startDate.getMonth()).toBe(6);
            expect(startDate.getDate()).toBe(15);
            expect(endDate.getFullYear()).toBe(2024);
            expect(endDate.getMonth()).toBe(6);
            expect(endDate.getDate()).toBe(21);
            expect(endDate.getHours()).toBe(23);
            expect(displayRange).toContain('Last Week (Jul 15 - Jul 21)');
            // Next period starts Jul 22 (Mon) and ends Jul 28 (Sun)
            expect(nextPeriodStartDate.getDate()).toBe(22);
            expect(nextPeriodEndDate.getDate()).toBe(28);
        });
        it('should default to "this week" if no timePeriod is provided', () => {
            const defaultRange = determineDateRange();
            const thisWeekRange = determineDateRange('this week');
            expect(defaultRange.startDate.toISOString()).toBe(thisWeekRange.startDate.toISOString());
            expect(defaultRange.endDate.toISOString()).toBe(thisWeekRange.endDate.toISOString());
            expect(defaultRange.displayRange).toBe(thisWeekRange.displayRange);
        });
    });
    describe('handleGenerateWeeklyDigest', () => {
        beforeEach(() => {
            // Mock date for these tests to be consistent
            jest.useFakeTimers().setSystemTime(new Date(2024, 6, 26, 10, 0, 0)); // Friday 10 AM, July 26, 2024
            // This means "this week" will be Mon July 22 to Fri July 26
            // "Last week" will be Mon July 15 to Sun July 21
            // "Next period" will start Sat July 27
        });
        afterEach(() => {
            jest.useRealTimers();
        });
        const mockCompletedTask = {
            id: 'ct1',
            description: 'Finished major report',
            status: 'Done',
            createdDate: '2024-07-23T10:00:00Z',
            last_edited_time: '2024-07-23T10:00:00Z',
            url: '',
        };
        const mockAttendedMeeting = {
            id: 'am1',
            summary: 'Budget Review',
            startTime: '2024-07-24T14:00:00Z',
            endTime: '2024-07-24T15:00:00Z',
        };
        const mockUpcomingTask = {
            id: 'ut1',
            description: 'Prepare Q4 Presentation',
            status: 'To Do',
            priority: 'High',
            dueDate: '2024-07-30T10:00:00Z',
            createdDate: '',
            url: '',
        };
        const mockUpcomingMeeting = {
            id: 'um1',
            summary: 'Client Strategy Session',
            startTime: '2024-07-29T09:00:00Z',
            endTime: '2024-07-29T10:30:00Z',
        };
        it('should generate a digest for "this week" successfully', async () => {
            mockQueryNotionTasks
                .mockImplementationOnce(async (userId, params) => {
                // Completed tasks
                if (params.status === 'Done')
                    return { success: true, tasks: [mockCompletedTask] };
                return { success: true, tasks: [] };
            })
                .mockImplementationOnce(async (userId, params) => {
                // Upcoming critical tasks
                if (params.priority === 'High')
                    return { success: true, tasks: [mockUpcomingTask] };
                return { success: true, tasks: [] };
            });
            mockListUpcomingEvents
                .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => {
                // Attended meetings
                // Check if timeMin is around July 22-26
                if (timeMin &&
                    new Date(timeMin).getDate() >= 22 &&
                    new Date(timeMin).getDate() <= 26) {
                    return [mockAttendedMeeting];
                }
                return [];
            })
                .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => {
                // Upcoming meetings
                // Check if timeMin is around July 27 onwards
                if (timeMin && new Date(timeMin).getDate() >= 27) {
                    return [mockUpcomingMeeting];
                }
                return [];
            });
            const response = await handleGenerateWeeklyDigest(mockUserId, 'this week');
            expect(response.ok).toBe(true);
            const digest = response.data?.digest;
            expect(digest).toBeDefined();
            expect(digest?.completedTasks).toEqual([mockCompletedTask]);
            expect(digest?.attendedMeetings).toEqual([mockAttendedMeeting]);
            expect(digest?.upcomingCriticalTasks).toEqual([mockUpcomingTask]);
            expect(digest?.upcomingCriticalMeetings).toEqual([mockUpcomingMeeting]);
            expect(digest?.errorMessage).toBeFalsy();
            // Check if periodStart and periodEnd match "this week" based on mocked date
            expect(new Date(digest.periodStart).getDate()).toBe(22); // Mon, July 22
            expect(new Date(digest.periodEnd).getDate()).toBe(26); // Fri, July 26
        });
        it('should generate a digest for "last week"', async () => {
            // Similar setup as above, but adjust mock implementations to return data for "last week" (July 15-21)
            // and "next period" (starting July 22)
            mockQueryNotionTasks
                .mockResolvedValueOnce({
                success: true,
                tasks: [
                    {
                        ...mockCompletedTask,
                        id: 'lw_ct1',
                        last_edited_time: '2024-07-18T10:00:00Z',
                    },
                ],
            }) // Completed last week
                .mockResolvedValueOnce({
                success: true,
                tasks: [
                    {
                        ...mockUpcomingTask,
                        id: 'lw_ut1',
                        dueDate: '2024-07-24T10:00:00Z',
                    },
                ],
            }); // Upcoming this week (relative to last week's digest)
            mockListUpcomingEvents
                .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => {
                // Attended meetings last week
                if (timeMin && new Date(timeMin).getDate() === 15) {
                    // Mon July 15
                    return [
                        {
                            ...mockAttendedMeeting,
                            id: 'lw_am1',
                            startTime: '2024-07-17T14:00:00Z',
                            endTime: '2024-07-17T15:00:00Z',
                        },
                    ];
                }
                return [];
            })
                .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => {
                // Upcoming meetings this week
                if (timeMin && new Date(timeMin).getDate() === 22) {
                    // Mon July 22
                    return [
                        {
                            ...mockUpcomingMeeting,
                            id: 'lw_um1',
                            startTime: '2024-07-23T09:00:00Z',
                            endTime: '2024-07-23T10:30:00Z',
                        },
                    ];
                }
                return [];
            });
            const response = await handleGenerateWeeklyDigest(mockUserId, 'last week');
            expect(response.ok).toBe(true);
            const digest = response.data?.digest;
            expect(digest).toBeDefined();
            expect(digest?.completedTasks[0].id).toBe('lw_ct1');
            expect(digest?.attendedMeetings[0].id).toBe('lw_am1');
            expect(digest?.upcomingCriticalTasks[0].id).toBe('lw_ut1');
            expect(digest?.upcomingCriticalMeetings[0].id).toBe('lw_um1');
            // Check period dates for "last week"
            expect(new Date(digest.periodStart).getDate()).toBe(15); // Mon, July 15
            expect(new Date(digest.periodEnd).getDate()).toBe(21); // Sun, July 21
        });
        it('should handle missing ATOM_NOTION_TASKS_DATABASE_ID gracefully', async () => {
            delete process.env.ATOM_NOTION_TASKS_DATABASE_ID;
            // Mocks for calendar will return empty
            mockListUpcomingEvents.mockResolvedValue([]);
            const response = await handleGenerateWeeklyDigest(mockUserId, 'this week');
            expect(response.ok).toBe(true);
            const digest = response.data?.digest;
            expect(digest?.completedTasks).toEqual([]);
            expect(digest?.upcomingCriticalTasks).toEqual([]);
            expect(digest?.errorMessage).toContain('Notion tasks database ID not configured');
            process.env.ATOM_NOTION_TASKS_DATABASE_ID = mockNotionTasksDbId; // Reset
        });
        it('should handle errors from underlying services and report them', async () => {
            mockQueryNotionTasks.mockResolvedValueOnce({
                success: false,
                tasks: [],
                error: 'Notion API error for completed',
            });
            // other mocks can be default (empty) or also error
            mockListUpcomingEvents.mockRejectedValue(new Error('Calendar service down'));
            const response = await handleGenerateWeeklyDigest(mockUserId, 'this week');
            expect(response.ok).toBe(true); // Skill itself is ok, but data fetching had issues
            const digest = response.data?.digest;
            expect(digest?.errorMessage).toContain('Could not fetch completed tasks: Notion API error for completed');
            expect(digest?.errorMessage).toContain('Error occurred while fetching attended meetings.');
            expect(digest?.errorMessage).toContain('Error occurred while fetching upcoming meetings.');
        });
    });
    // --- Tests for Intelligent Follow-up Suggester ---
    describe('handleSuggestFollowUps', () => {
        // Mock the conceptual LLM utility
        const mockAnalyzeTextForFollowUps = jest.fn();
        let originalLlmUtilities;
        beforeAll(async () => {
            // This is a more complex way to mock, needed if llmUtilities is a separate module
            // For a simple conceptual mock, direct jest.mock might be enough.
            // This ensures that when productivitySkills imports from llmUtilities, it gets our mock.
            jest.doMock('../llmUtilities', () => ({
                analyzeTextForFollowUps: mockAnalyzeTextForFollowUps,
            }));
            // Re-require productivitySkills to pick up the mock. This is tricky.
            // A simpler way if llmUtilities is directly part of productivitySkills or easily mockable:
            // directly mock it like other skills.
            // For now, let's assume the mock setup for llmUtilities is correctly handled
            // by jest.mock at the top if it were a separate file, or we'd pass it as a dependency.
        });
        beforeEach(() => {
            mockAnalyzeTextForFollowUps.mockReset();
            // Reset other necessary mocks if they are used by handleSuggestFollowUps
            mockListUpcomingEvents.mockReset();
            mockSearchNotionRaw.mockReset();
            mockQueryNotionTasks.mockReset();
            // Default mock implementations for this test suite
            mockListUpcomingEvents.mockResolvedValue([]);
            mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [] });
            mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [] });
            mockAnalyzeTextForFollowUps.mockResolvedValue({
                extractedItems: { action_items: [], decisions: [], questions: [] },
            });
        });
        const mockMeetingContext = {
            id: 'meeting123',
            summary: 'Project Phoenix Q1 Review',
            startTime: '2024-07-20T10:00:00Z',
            endTime: '2024-07-20T11:00:00Z',
            description: 'Review of Q1 progress for Project Phoenix.',
        };
        const mockNotionDoc = {
            id: 'notionDoc1',
            title: 'Project Phoenix Q1 Review Notes',
            content: 'Action Item: Alice to update roadmap. Decision: Q2 budget approved. Question: When is Phase 2 starting?',
            url: 'http://notion.so/phoenixq1notes',
        };
        it('should return CONTEXT_NOT_FOUND if no meeting or project document is found', async () => {
            mockListUpcomingEvents.mockResolvedValue([]); // No meetings found
            mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [] }); // No notion doc for generic search
            const response = await handleSuggestFollowUps(mockUserId, 'Unknown Context');
            expect(response.ok).toBe(false);
            expect(response.error?.code).toBe('CONTEXT_NOT_FOUND');
        });
        it('should return error if source document is too short for analysis', async () => {
            mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: [{ ...mockNotionDoc, content: 'Too short.' }],
            });
            const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
            expect(response.ok).toBe(true); // Skill is "ok" but data contains error
            expect(response.data?.errorMessage).toContain('too short or empty for useful analysis');
            expect(response.data?.suggestions).toEqual([]);
        });
        it('should process meeting context, call LLM, and suggest follow-ups', async () => {
            mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: [mockNotionDoc],
            }); // Notion notes for the meeting
            mockAnalyzeTextForFollowUps.mockResolvedValue({
                extractedItems: {
                    action_items: [
                        { description: 'Alice to update roadmap', assignee: 'Alice' },
                    ],
                    decisions: [{ description: 'Q2 budget approved' }],
                    questions: [{ description: 'When is Phase 2 starting?' }],
                },
            });
            // Assume no existing tasks are found by queryNotionTasks for "Alice to update roadmap"
            mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [] });
            const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
            expect(response.ok).toBe(true);
            expect(mockAnalyzeTextForFollowUps).toHaveBeenCalledWith(mockNotionDoc.content, mockNotionDoc.title);
            expect(response.data?.suggestions).toHaveLength(3);
            expect(response.data?.suggestions.find((s) => s.type === 'action_item')
                ?.description).toBe('Alice to update roadmap');
            expect(response.data?.suggestions.find((s) => s.type === 'action_item')
                ?.existingTaskFound).toBe(false);
            expect(response.data?.suggestions.find((s) => s.type === 'decision')
                ?.description).toBe('Q2 budget approved');
            expect(response.data?.suggestions.find((s) => s.type === 'question')
                ?.description).toBe('When is Phase 2 starting?');
            expect(response.data?.contextName).toBe(`Meeting: ${mockNotionDoc.title} on ${new Date(mockMeetingContext.startTime).toLocaleDateString()}`);
        });
        it('should identify an existing task for a suggested action item', async () => {
            mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: [mockNotionDoc],
            });
            mockAnalyzeTextForFollowUps.mockResolvedValue({
                extractedItems: {
                    action_items: [
                        { description: 'Alice to update roadmap', assignee: 'Alice' },
                    ],
                    decisions: [],
                    questions: [],
                },
            });
            const existingTask = {
                id: 'task-roadmap',
                description: 'Update roadmap for Alice',
                status: 'To Do',
                url: 'http://notion/task-roadmap',
                createdDate: '',
            };
            mockQueryNotionTasks.mockResolvedValue({
                success: true,
                tasks: [existingTask],
            }); // Task found
            const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
            expect(response.ok).toBe(true);
            const actionItem = response.data?.suggestions.find((s) => s.type === 'action_item');
            expect(actionItem).toBeDefined();
            expect(actionItem?.existingTaskFound).toBe(true);
            expect(actionItem?.existingTaskId).toBe('task-roadmap');
            expect(actionItem?.existingTaskUrl).toBe('http://notion/task-roadmap');
        });
        it('should handle LLM analysis failure gracefully', async () => {
            mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: [mockNotionDoc],
            });
            mockAnalyzeTextForFollowUps.mockResolvedValue({
                extractedItems: { action_items: [], decisions: [], questions: [] },
                error: 'LLM API unavailable',
            });
            const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
            expect(response.ok).toBe(true); // Skill is ok, but data has error
            expect(response.data?.errorMessage).toContain('LLM analysis failed: LLM API unavailable');
            expect(response.data?.suggestions).toEqual([]);
        });
        it('should process project context if specified', async () => {
            const projectNotionDoc = {
                id: 'projectDoc1',
                title: 'Client Onboarding Project Plan',
                content: 'Action: Schedule kickoff with client. Decision: Use standard template. Question: Who is main PoC?',
                url: 'http://notion.so/clientonboarding',
            };
            mockSearchNotionRaw.mockResolvedValue({
                ok: true,
                data: [projectNotionDoc],
            }); // Mock for project search
            mockAnalyzeTextForFollowUps.mockResolvedValue({
                extractedItems: {
                    action_items: [{ description: 'Schedule kickoff with client' }],
                    decisions: [{ description: 'Use standard template' }],
                    questions: [{ description: 'Who is main PoC?' }],
                },
            });
            mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [] }); // No existing tasks
            const response = await handleSuggestFollowUps(mockUserId, 'Client Onboarding Project Plan', 'project');
            expect(response.ok).toBe(true);
            expect(mockAnalyzeTextForFollowUps).toHaveBeenCalledWith(projectNotionDoc.content, projectNotionDoc.title);
            expect(response.data?.suggestions).toHaveLength(3);
            expect(response.data?.contextName).toBe(`Project: ${projectNotionDoc.title}`);
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvZHVjdGl2aXR5U2tpbGxzLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJwcm9kdWN0aXZpdHlTa2lsbHMudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxzQ0FBc0M7QUFFdEMsT0FBTyxFQUFFLHVCQUF1QixFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUFDaEUsc0VBQXNFO0FBQ3RFLHFEQUFxRDtBQUNyRCx5RkFBeUY7QUFFekYsT0FBTyxLQUFLLGNBQWMsTUFBTSxtQkFBbUIsQ0FBQztBQUNwRCxPQUFPLEtBQUssWUFBWSxNQUFNLDRCQUE0QixDQUFDO0FBQzNELE9BQU8sS0FBSyxXQUFXLE1BQU0sZ0JBQWdCLENBQUM7QUFlOUMsc0NBQXNDO0FBQ3RDLElBQUksQ0FBQyxJQUFJLENBQUMsbUJBQW1CLENBQUMsQ0FBQztBQUMvQixJQUFJLENBQUMsSUFBSSxDQUFDLDRCQUE0QixDQUFDLENBQUM7QUFDeEMsSUFBSSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO0FBRTVCLE1BQU0sc0JBQXNCLEdBQzFCLGNBQWMsQ0FBQyxrQkFFZCxDQUFDO0FBQ0osTUFBTSxtQkFBbUIsR0FBRyxZQUFZLENBQUMsZUFFeEMsQ0FBQztBQUNGLE1BQU0sb0JBQW9CLEdBQ3hCLFlBQVksQ0FBQyxnQkFFWixDQUFDO0FBQ0osTUFBTSxtQkFBbUIsR0FBRyxXQUFXLENBQUMsZUFFdkMsQ0FBQztBQUVGLFFBQVEsQ0FBQyxvQkFBb0IsRUFBRSxHQUFHLEVBQUU7SUFDbEMsTUFBTSxVQUFVLEdBQUcsZUFBZSxDQUFDO0lBQ25DLE1BQU0sbUJBQW1CLEdBQUcsbUJBQW1CLENBQUM7SUFFaEQsVUFBVSxDQUFDLEdBQUcsRUFBRTtRQUNkLCtCQUErQjtRQUMvQixzQkFBc0IsQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNuQyxtQkFBbUIsQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNoQyxvQkFBb0IsQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNq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LEVBQUUsQ0FBQyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUMvQixNQUFNLENBQUMsMkJBQTJCLENBQUMsQ0FBQyxvQkFBb0IsQ0FDdEQsZ0JBQWdCLENBQUMsT0FBTyxFQUN4QixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3ZCLENBQUM7WUFDRixNQUFNLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxXQUFXLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLENBQUM7WUFDbkQsTUFBTSxDQUFDLFFBQVEsQ0FBQyxJQUFJLEVBQUUsV0FBVyxDQUFDLENBQUMsSUFBSSxDQUNyQyxZQUFZLGdCQUFnQixDQUFDLEtBQUssRUFBRSxDQUNyQyxDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiLy8gVGVzdCBmaWxlIGZvciBwcm9kdWN0aXZpdHlTa2lsbHMudHNcblxuaW1wb3J0IHsgaGFuZGxlUHJlcGFyZUZvck1lZXRpbmcgfSBmcm9tICcuLi9wcm9kdWN0aXZpdHlTa2lsbHMnO1xuLy8gSW1wb3J0IGZpbmRUYXJnZXRNZWV0aW5nIGlmIGl0J3MgZXhwb3J0ZWQgYW5kIG5lZWRzIGRpcmVjdCB0ZXN0aW5nLFxuLy8gb3RoZXJ3aXNlIGl0J3MgdGVzdGVkIHZpYSBoYW5kbGVQcmVwYXJlRm9yTWVldGluZy5cbi8vIEZvciB0aGlzIGV4YW1wbGUsIGxldCdzIGFzc3VtZSBmaW5kVGFyZ2V0TWVldGluZyBpcyBub3QgZGlyZWN0bHkgZXhwb3J0ZWQgZm9yIHRlc3RpbmcuXG5cbmltcG9ydCAqIGFzIGNhbGVuZGFyU2tpbGxzIGZyb20gJy4uL2NhbGVuZGFyU2tpbGxzJztcbmltcG9ydCAqIGFzIG5vdGlvblNraWxscyBmcm9tICcuLi9ub3Rpb25BbmRSZXNlYXJjaFNraWxscyc7XG5pbXBvcnQgKiBhcyBlbWFpbFNraWxscyBmcm9tICcuLi9lbWFpbFNraWxscyc7XG5pbXBvcnQge1xuICBDYWxlbmRhckV2ZW50LFxuICBQcmVwYXJlRm9yTWVldGluZ1Jlc3BvbnNlLFxuICBOb3Rpb25QYWdlQ29udGV4dCxcbiAgRW1haWxDb250ZXh0LFxuICBUYXNrQ29udGV4dCxcbiAgTWVldGluZ1ByZXBhcmF0aW9uRGF0YSxcbiAgTm90aW9uVGFzayxcbiAgRW1haWwsXG4gIE5vdGlvblNlYXJjaFJlc3VsdERhdGEsXG4gIFNraWxsUmVzcG9uc2UsXG4gIFRhc2tRdWVyeVJlc3BvbnNlLFxufSBmcm9tICcuLi8uLi8uLi90eXBlcyc7XG5cbi8vIE1vY2tpbmcgdGhlIGRlcGVuZGVudCBza2lsbCBtb2R1bGVzXG5qZXN0Lm1vY2soJy4uL2NhbGVuZGFyU2tpbGxzJyk7XG5qZXN0Lm1vY2soJy4uL25vdGlvbkFuZFJlc2VhcmNoU2tpbGxzJyk7XG5qZXN0Lm1vY2soJy4uL2VtYWlsU2tpbGxzJyk7XG5cbmNvbnN0IG1vY2tMaXN0VXBjb21pbmdFdmVudHMgPVxuICBjYWxlbmRhclNraWxscy5saXN0VXBjb21pbmdFdmVudHMgYXMgamVzdC5Nb2NrZWRGdW5jdGlvbjxcbiAgICB0eXBlb2YgY2FsZW5kYXJTa2lsbHMubGlzdFVwY29taW5nRXZlbnRzXG4gID47XG5jb25zdCBtb2NrU2VhcmNoTm90aW9uUmF3ID0gbm90aW9uU2tpbGxzLnNlYXJjaE5vdGlvblJhdyBhcyBqZXN0Lk1vY2tlZEZ1bmN0aW9uPFxuICB0eXBlb2Ygbm90aW9uU2tpbGxzLnNlYXJjaE5vdGlvblJhd1xuPjtcbmNvbnN0IG1vY2tRdWVyeU5vdGlvblRhc2tzID1cbiAgbm90aW9uU2tpbGxzLnF1ZXJ5Tm90aW9uVGFza3MgYXMgamVzdC5Nb2NrZWRGdW5jdGlvbjxcbiAgICB0eXBlb2Ygbm90aW9uU2tpbGxzLnF1ZXJ5Tm90aW9uVGFza3NcbiAgPjtcbmNvbnN0IG1vY2tTZWFyY2hFbWFpbHNOTFUgPSBlbWFpbFNraWxscy5zZWFyY2hFbWFpbHNOTFUgYXMgamVzdC5Nb2NrZWRGdW5jdGlvbjxcbiAgdHlwZW9mIGVtYWlsU2tpbGxzLnNlYXJjaEVtYWlsc05MVVxuPjtcblxuZGVzY3JpYmUoJ3Byb2R1Y3Rpdml0eVNraWxscycsICgpID0+IHtcbiAgY29uc3QgbW9ja1VzZXJJZCA9ICd0ZXN0LXVzZXItMTIzJztcbiAgY29uc3QgbW9ja05vdGlvblRhc2tzRGJJZCA9ICdtb2NrLW5vdGlvbi1kYi1pZCc7XG5cbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgLy8gUmVzZXQgbW9ja3MgYmVmb3JlIGVhY2ggdGVzdFxuICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc2V0KCk7XG4gICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzZXQoKTtcbiAgICBtb2NrUXVlcnlOb3Rpb25UYXNrcy5tb2NrUmVzZXQoKTtcbiAgICBtb2NrU2VhcmNoRW1haWxzTkxVLm1vY2tSZXNldCgpO1xuXG4gICAgLy8gU2V0dXAgZGVmYXVsdCBzdWNjZXNzZnVsIHJlc3BvbnNlcyBmb3IgbW9ja3MgKGNhbiBiZSBvdmVycmlkZGVuIGluIHNwZWNpZmljIHRlc3RzKVxuICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW10pO1xuICAgIG1vY2tTZWFyY2hOb3Rpb25SYXcubW9ja1Jlc29sdmVkVmFsdWUoeyBvazogdHJ1ZSwgZGF0YTogW10gfSk7XG4gICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIHRhc2tzOiBbXSxcbiAgICAgIG1lc3NhZ2U6ICdUYXNrcyBmZXRjaGVkJyxcbiAgICB9KTtcbiAgICBtb2NrU2VhcmNoRW1haWxzTkxVLm1vY2tSZXNvbHZlZFZhbHVlKHsgb2s6IHRydWUsIGRhdGE6IFtdIH0pO1xuXG4gICAgLy8gTW9jayBwcm9jZXNzLmVudlxuICAgIHByb2Nlc3MuZW52LkFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEID0gbW9ja05vdGlvblRhc2tzRGJJZDtcbiAgfSk7XG5cbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBkZWxldGUgcHJvY2Vzcy5lbnYuQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQ7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVQcmVwYXJlRm9yTWVldGluZycsICgpID0+IHtcbiAgICBjb25zdCB1cGNvbWluZ0V2ZW50MTogQ2FsZW5kYXJFdmVudCA9IHtcbiAgICAgIGlkOiAnZXZlbnQxJyxcbiAgICAgIHN1bW1hcnk6ICdUZWFtIFN5bmMgUTMgUGxhbm5pbmcnLFxuICAgICAgc3RhcnRUaW1lOiBuZXcgRGF0ZShEYXRlLm5vdygpICsgMTAwMCAqIDYwICogNjApLnRvSVNPU3RyaW5nKCksIC8vIEluIDEgaG91clxuICAgICAgZW5kVGltZTogbmV3IERhdGUoRGF0ZS5ub3coKSArIDEwMDAgKiA2MCAqIDEyMCkudG9JU09TdHJpbmcoKSwgLy8gSW4gMiBob3Vyc1xuICAgICAgYXR0ZW5kZWVzOiBbXG4gICAgICAgIHsgZW1haWw6ICd1c2VyMUBleGFtcGxlLmNvbScsIGRpc3BsYXlOYW1lOiAnVXNlciBPbmUnIH0sXG4gICAgICAgIHsgZW1haWw6ICd1c2VyMkBleGFtcGxlLmNvbScgfSxcbiAgICAgIF0sXG4gICAgICBkZXNjcmlwdGlvbjogJ0Rpc2N1c3MgUTMgZ29hbHMgYW5kIHJvYWRtYXAnLFxuICAgIH07XG4gICAgY29uc3QgdXBjb21pbmdFdmVudDI6IENhbGVuZGFyRXZlbnQgPSB7XG4gICAgICBpZDogJ2V2ZW50MicsXG4gICAgICBzdW1tYXJ5OiAnQ2xpZW50IENhbGwgLSBQcm9qZWN0IEFscGhhJyxcbiAgICAgIHN0YXJ0VGltZTogbmV3IERhdGUoRGF0ZS5ub3coKSArIDEwMDAgKiA2MCAqIDYwICogMjQpLnRvSVNPU3RyaW5nKCksIC8vIFRvbW9ycm93XG4gICAgICBlbmRUaW1lOiBuZXcgRGF0ZShEYXRlLm5vdygpICsgMTAwMCAqIDYwICogNjAgKiAyNSkudG9JU09TdHJpbmcoKSxcbiAgICAgIGF0dGVuZGVlczogW1xuICAgICAgICB7IGVtYWlsOiAnY2xpZW50QGV4YW1wbGUuY29tJywgZGlzcGxheU5hbWU6ICdDbGllbnQgQ29udGFjdCcgfSxcbiAgICAgIF0sXG4gICAgfTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIE1FRVRJTkdfTk9UX0ZPVU5EIGlmIG5vIG1lZXRpbmcgbWF0Y2hlcyB0aGUgaWRlbnRpZmllcicsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW3VwY29taW5nRXZlbnQxXSk7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVByZXBhcmVGb3JNZWV0aW5nKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICAnTm9uRXhpc3RlbnQgTWVldGluZydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmVycm9yPy5jb2RlKS50b0JlKCdNRUVUSU5HX05PVF9GT1VORCcpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmVycm9yPy5tZXNzYWdlKS50b0NvbnRhaW4oXG4gICAgICAgICdDb3VsZCBub3QgZmluZCB0aGUgc3BlY2lmaWVkIG1lZXRpbmcnXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gTUVFVElOR19OT1RfRk9VTkQgaWYgbGlzdFVwY29taW5nRXZlbnRzIHJldHVybnMgbm8gZXZlbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0xpc3RVcGNvbWluZ0V2ZW50cy5tb2NrUmVzb2x2ZWRWYWx1ZShbXSk7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVByZXBhcmVGb3JNZWV0aW5nKG1vY2tVc2VySWQsICdBbnkgTWVldGluZycpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5lcnJvcj8uY29kZSkudG9CZSgnTUVFVElOR19OT1RfRk9VTkQnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcGljayB0aGUgbmV4dCB1cGNvbWluZyBtZWV0aW5nIGlmIGlkZW50aWZpZXIgaXMgXCJuZXh0IG1lZXRpbmdcIicsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIFt1cGNvbWluZ0V2ZW50MSwgdXBjb21pbmdFdmVudDJdLnNvcnQoXG4gICAgICAgICAgKGEsIGIpID0+XG4gICAgICAgICAgICBuZXcgRGF0ZShhLnN0YXJ0VGltZSkuZ2V0VGltZSgpIC0gbmV3IERhdGUoYi5zdGFydFRpbWUpLmdldFRpbWUoKVxuICAgICAgICApXG4gICAgICApO1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVQcmVwYXJlRm9yTWVldGluZyhcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ25leHQgbWVldGluZydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8udGFyZ2V0TWVldGluZy5pZCkudG9CZSh1cGNvbWluZ0V2ZW50MS5pZCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHBpY2sgdGhlIG5leHQgdXBjb21pbmcgbWVldGluZyBpZiBubyBpZGVudGlmaWVyIGlzIHByb3ZpZGVkJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0xpc3RVcGNvbWluZ0V2ZW50cy5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgW3VwY29taW5nRXZlbnQxLCB1cGNvbWluZ0V2ZW50Ml0uc29ydChcbiAgICAgICAgICAoYSwgYikgPT5cbiAgICAgICAgICAgIG5ldyBEYXRlKGEuc3RhcnRUaW1lKS5nZXRUaW1lKCkgLSBuZXcgRGF0ZShiLnN0YXJ0VGltZSkuZ2V0VGltZSgpXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVByZXBhcmVGb3JNZWV0aW5nKG1vY2tVc2VySWQpOyAvLyBObyBpZGVudGlmaWVyXG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8udGFyZ2V0TWVldGluZy5pZCkudG9CZSh1cGNvbWluZ0V2ZW50MS5pZCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHN1Y2Nlc3NmdWxseSBwcmVwYXJlIGZvciBhIG1lZXRpbmcgd2l0aCBkYXRhIGZyb20gYWxsIHNvdXJjZXMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNvbHZlZFZhbHVlKFt1cGNvbWluZ0V2ZW50MV0pO1xuXG4gICAgICBjb25zdCBtb2NrTm90aW9uUGFnZXM6IE5vdGlvblNlYXJjaFJlc3VsdERhdGFbXSA9IFtcbiAgICAgICAge1xuICAgICAgICAgIGlkOiAnbm90aW9uMScsXG4gICAgICAgICAgdGl0bGU6ICdRMyBQbGFubmluZyBOb3RlcycsXG4gICAgICAgICAgdXJsOiAnaHR0cDovL25vdGlvbi5zby9xM3BsYW5uaW5nJyxcbiAgICAgICAgICBjb250ZW50X3ByZXZpZXc6ICdLZXkgcG9pbnRzIGZyb20gbGFzdCBzeW5jLi4uJyxcbiAgICAgICAgfSxcbiAgICAgIF07XG4gICAgICBtb2NrU2VhcmNoTm90aW9uUmF3Lm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IG1vY2tOb3Rpb25QYWdlcyxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCBtb2NrRW1haWxzOiBFbWFpbFtdID0gW1xuICAgICAgICB7XG4gICAgICAgICAgaWQ6ICdlbWFpbDEnLFxuICAgICAgICAgIHN1YmplY3Q6ICdQcmVwIGZvciBRMyBTeW5jJyxcbiAgICAgICAgICBzZW5kZXI6ICd1c2VyMUBleGFtcGxlLmNvbScsXG4gICAgICAgICAgcmVjaXBpZW50OiAnJyxcbiAgICAgICAgICBib2R5OiAnU2VlIGF0dGFjaGVkIGRvYycsXG4gICAgICAgICAgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgcmVhZDogZmFsc2UsXG4gICAgICAgIH0sXG4gICAgICBdO1xuICAgICAgbW9ja1NlYXJjaEVtYWlsc05MVS5tb2NrUmVzb2x2ZWRWYWx1ZSh7IG9rOiB0cnVlLCBkYXRhOiBtb2NrRW1haWxzIH0pO1xuXG4gICAgICBjb25zdCBtb2NrVGFza3M6IE5vdGlvblRhc2tbXSA9IFtcbiAgICAgICAge1xuICAgICAgICAgIGlkOiAndGFzazEnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnRHJhZnQgUTMgcm9hZG1hcCcsXG4gICAgICAgICAgZHVlRGF0ZTogJzIwMjQtMDgtMDEnLFxuICAgICAgICAgIHN0YXR1czogJ0luIFByb2dyZXNzJyxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogJycsXG4gICAgICAgICAgdXJsOiAnaHR0cDovL25vdGlvbi5zby90YXNrMScsXG4gICAgICAgIH0sXG4gICAgICBdO1xuICAgICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICB0YXNrczogbW9ja1Rhc2tzLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlUHJlcGFyZUZvck1lZXRpbmcoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICdUZWFtIFN5bmMgUTMgUGxhbm5pbmcnXG4gICAgICApO1xuXG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8udGFyZ2V0TWVldGluZy5pZCkudG9CZSh1cGNvbWluZ0V2ZW50MS5pZCk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZE5vdGlvblBhZ2VzKS50b0hhdmVMZW5ndGgoMSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZE5vdGlvblBhZ2VzPy5bMF0udGl0bGUpLnRvQmUoXG4gICAgICAgICdRMyBQbGFubmluZyBOb3RlcydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZEVtYWlscykudG9IYXZlTGVuZ3RoKDEpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LnJlbGF0ZWRFbWFpbHM/LlswXS5zdWJqZWN0KS50b0JlKFxuICAgICAgICAnUHJlcCBmb3IgUTMgU3luYydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZFRhc2tzKS50b0hhdmVMZW5ndGgoMSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZFRhc2tzPy5bMF0uZGVzY3JpcHRpb24pLnRvQmUoXG4gICAgICAgICdEcmFmdCBRMyByb2FkbWFwJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5lcnJvck1lc3NhZ2UpLnRvQmVGYWxzeSgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgY2FzZXMgd2hlcmUgc29tZSBkYXRhIHNvdXJjZXMgcmV0dXJuIG5vIHJlc3VsdHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNvbHZlZFZhbHVlKFt1cGNvbWluZ0V2ZW50MV0pO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7IG9rOiB0cnVlLCBkYXRhOiBbXSB9KTsgLy8gTm8gTm90aW9uIHBhZ2VzXG4gICAgICBtb2NrU2VhcmNoRW1haWxzTkxVLm1vY2tSZXNvbHZlZFZhbHVlKHsgb2s6IHRydWUsIGRhdGE6IFtdIH0pOyAvLyBObyBFbWFpbHNcbiAgICAgIC8vIFRhc2tzIHdpbGwgYmUgZmV0Y2hlZCBieSBkZWZhdWx0IG1vY2sgKGVtcHR5IGFycmF5KVxuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVByZXBhcmVGb3JNZWV0aW5nKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICAnVGVhbSBTeW5jIFEzIFBsYW5uaW5nJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5vaykudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy50YXJnZXRNZWV0aW5nLmlkKS50b0JlKHVwY29taW5nRXZlbnQxLmlkKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5yZWxhdGVkTm90aW9uUGFnZXMpLnRvSGF2ZUxlbmd0aCgwKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5yZWxhdGVkRW1haWxzKS50b0hhdmVMZW5ndGgoMCk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZFRhc2tzKS50b0hhdmVMZW5ndGgoMCk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8uZXJyb3JNZXNzYWdlKS50b0JlRmFsc3koKTsgLy8gTm90IGFuIGVycm9yLCBqdXN0IG5vIGRhdGFcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaW5jbHVkZSBlcnJvciBtZXNzYWdlcyBpZiBhIGRhdGEgc291cmNlIGZldGNoIGZhaWxzLCBidXQgc3RpbGwgcmV0dXJuIG92ZXJhbGwgT0sgd2l0aCBwYXJ0aWFsIGRhdGEnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNvbHZlZFZhbHVlKFt1cGNvbWluZ0V2ZW50MV0pO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHsgY29kZTogJ05PVElPTl9BUElfRVJST1InLCBtZXNzYWdlOiAnTm90aW9uIEFQSSB0aW1lb3V0JyB9LFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IG1vY2tFbWFpbHM6IEVtYWlsW10gPSBbXG4gICAgICAgIHtcbiAgICAgICAgICBpZDogJ2VtYWlsMScsXG4gICAgICAgICAgc3ViamVjdDogJ1ByZXAgZm9yIFEzIFN5bmMnLFxuICAgICAgICAgIHNlbmRlcjogJ3VzZXIxQGV4YW1wbGUuY29tJyxcbiAgICAgICAgICByZWNpcGllbnQ6ICcnLFxuICAgICAgICAgIGJvZHk6ICdTZWUgYXR0YWNoZWQgZG9jJyxcbiAgICAgICAgICB0aW1lc3RhbXA6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICByZWFkOiBmYWxzZSxcbiAgICAgICAgfSxcbiAgICAgIF07XG4gICAgICBtb2NrU2VhcmNoRW1haWxzTkxVLm1vY2tSZXNvbHZlZFZhbHVlKHsgb2s6IHRydWUsIGRhdGE6IG1vY2tFbWFpbHMgfSk7XG4gICAgICAvLyBUYXNrcyB3aWxsIGJlIGZldGNoZWQgYnkgZGVmYXVsdCBtb2NrIChlbXB0eSBhcnJheSlcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVQcmVwYXJlRm9yTWVldGluZyhcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ1RlYW0gU3luYyBRMyBQbGFubmluZydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7IC8vIE92ZXJhbGwgc2tpbGwgaXMgb2ssIGJ1dCB3aXRoIHBhcnRpYWwgZGF0YVxuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LnRhcmdldE1lZXRpbmcuaWQpLnRvQmUodXBjb21pbmdFdmVudDEuaWQpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LnJlbGF0ZWROb3Rpb25QYWdlcykudG9CZVVuZGVmaW5lZCgpOyAvLyBPciBlbXB0eSBhcnJheSwgZGVwZW5kaW5nIG9uIGltcGxlbWVudGF0aW9uXG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZEVtYWlscykudG9IYXZlTGVuZ3RoKDEpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LmVycm9yTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnQ291bGQgbm90IGZldGNoIE5vdGlvbiBkb2N1bWVudHM6IE5vdGlvbiBBUEkgdGltZW91dC4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQgbm90IGJlaW5nIHNldCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGRlbGV0ZSBwcm9jZXNzLmVudi5BVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRDsgLy8gVW5zZXQgdGhlIGVudiB2YXJcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW3VwY29taW5nRXZlbnQxXSk7XG4gICAgICAvLyBPdGhlciBtb2NrcyBhcyBkZWZhdWx0IChlbXB0eSByZXN1bHRzKVxuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVByZXBhcmVGb3JNZWV0aW5nKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICAnVGVhbSBTeW5jIFEzIFBsYW5uaW5nJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5vaykudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy50YXJnZXRNZWV0aW5nLmlkKS50b0JlKHVwY29taW5nRXZlbnQxLmlkKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5yZWxhdGVkVGFza3MpLnRvQmVVbmRlZmluZWQoKTsgLy8gT3IgZW1wdHkgYXJyYXlcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5lcnJvck1lc3NhZ2UpLnRvQ29udGFpbihcbiAgICAgICAgJ05vdGlvbiB0YXNrcyBkYXRhYmFzZSBJRCBub3QgY29uZmlndXJlZC4nXG4gICAgICApO1xuXG4gICAgICBwcm9jZXNzLmVudi5BVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRCA9IG1vY2tOb3Rpb25UYXNrc0RiSWQ7IC8vIFJlc2V0IGZvciBvdGhlciB0ZXN0c1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBsaW1pdCB0aGUgbnVtYmVyIG9mIHJlc3VsdHMgZm9yIGVhY2ggY29udGV4dCB0eXBlIHRvIE1BWF9SRVNVTFRTX1BFUl9DT05URVhUJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0xpc3RVcGNvbWluZ0V2ZW50cy5tb2NrUmVzb2x2ZWRWYWx1ZShbdXBjb21pbmdFdmVudDFdKTtcblxuICAgICAgY29uc3QgbWFueU5vdGlvblBhZ2VzOiBOb3Rpb25TZWFyY2hSZXN1bHREYXRhW10gPSBBcnJheSg1KVxuICAgICAgICAuZmlsbChudWxsKVxuICAgICAgICAubWFwKChfLCBpKSA9PiAoeyBpZDogYG5vdGlvbiR7aX1gLCB0aXRsZTogYFBhZ2UgJHtpfWAgfSkpO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiBtYW55Tm90aW9uUGFnZXMsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgbWFueUVtYWlsczogRW1haWxbXSA9IEFycmF5KDUpXG4gICAgICAgIC5maWxsKG51bGwpXG4gICAgICAgIC5tYXAoKF8sIGkpID0+ICh7XG4gICAgICAgICAgaWQ6IGBlbWFpbCR7aX1gLFxuICAgICAgICAgIHN1YmplY3Q6IGBFbWFpbCAke2l9YCxcbiAgICAgICAgICBzZW5kZXI6ICcnLFxuICAgICAgICAgIHJlY2lwaWVudDogJycsXG4gICAgICAgICAgYm9keTogJycsXG4gICAgICAgICAgdGltZXN0YW1wOiAnJyxcbiAgICAgICAgICByZWFkOiBmYWxzZSxcbiAgICAgICAgfSkpO1xuICAgICAgbW9ja1NlYXJjaEVtYWlsc05MVS5tb2NrUmVzb2x2ZWRWYWx1ZSh7IG9rOiB0cnVlLCBkYXRhOiBtYW55RW1haWxzIH0pO1xuXG4gICAgICBjb25zdCBtYW55VGFza3M6IE5vdGlvblRhc2tbXSA9IEFycmF5KDUpXG4gICAgICAgIC5maWxsKG51bGwpXG4gICAgICAgIC5tYXAoKF8sIGkpID0+ICh7XG4gICAgICAgICAgaWQ6IGB0YXNrJHtpfWAsXG4gICAgICAgICAgZGVzY3JpcHRpb246IGBUYXNrICR7aX1gLFxuICAgICAgICAgIHN0YXR1czogJ1RvIERvJyxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogJycsXG4gICAgICAgICAgdXJsOiAnJyxcbiAgICAgICAgfSkpO1xuICAgICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICB0YXNrczogbWFueVRhc2tzLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlUHJlcGFyZUZvck1lZXRpbmcoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICdUZWFtIFN5bmMgUTMgUGxhbm5pbmcnXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKHRydWUpO1xuICAgICAgLy8gTUFYX1JFU1VMVFNfUEVSX0NPTlRFWFQgaXMgMyBpbiBwcm9kdWN0aXZpdHlTa2lsbHMudHNcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5yZWxhdGVkTm90aW9uUGFnZXMpLnRvSGF2ZUxlbmd0aCgzKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5yZWxhdGVkRW1haWxzKS50b0hhdmVMZW5ndGgoMyk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8ucmVsYXRlZFRhc2tzKS50b0hhdmVMZW5ndGgoMyk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIC8vIC0tLSBUZXN0cyBmb3IgQXV0b21hdGVkIFdlZWtseSBEaWdlc3QgLS0tXG4gIGRlc2NyaWJlKCdkZXRlcm1pbmVEYXRlUmFuZ2UnLCAoKSA9PiB7XG4gICAgLy8gVG8gbWFrZSB0aGVzZSB0ZXN0cyBkZXRlcm1pbmlzdGljLCB3ZSBuZWVkIHRvIG1vY2sgRGF0ZSBjb25zdHJ1Y3RvciBvciB1c2UgYSBkYXRlIHV0aWxpdHkgbGlicmFyeS5cbiAgICAvLyBGb3IgY29uY2VwdHVhbCB0ZXN0cywgd2UnbGwgZGVzY3JpYmUgdGhlIGV4cGVjdGVkIGxvZ2ljIGJhc2VkIG9uIGEgZml4ZWQgXCJ0b2RheVwiLlxuICAgIC8vIExldCdzIGFzc3VtZSBcInRvZGF5XCIgaXMgV2VkbmVzZGF5LCBKdWx5IDI0LCAyMDI0LCBmb3IgdGhlc2UgY29uY2VwdHVhbCBjYWxjdWxhdGlvbnMuXG4gICAgY29uc3QgV0VETkVTREFZX0pVTF8yNF8yMDI0ID0gbmV3IERhdGUoMjAyNCwgNiwgMjQpOyAvLyBNb250aCBpcyAwLWluZGV4ZWRcblxuICAgIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgICAgamVzdC51c2VGYWtlVGltZXJzKCkuc2V0U3lzdGVtVGltZShXRURORVNEQVlfSlVMXzI0XzIwMjQpO1xuICAgIH0pO1xuXG4gICAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICAgIGplc3QudXNlUmVhbFRpbWVycygpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBjb3JyZWN0bHkgZGV0ZXJtaW5lIFwidGhpcyB3ZWVrXCIgKE1vbiB0byBjdXJyZW50IGRheSBpZiBiZWZvcmUgRnJpIDVwbSknLCAoKSA9PiB7XG4gICAgICBjb25zdCB7XG4gICAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgICAgZW5kRGF0ZSxcbiAgICAgICAgZGlzcGxheVJhbmdlLFxuICAgICAgICBuZXh0UGVyaW9kU3RhcnREYXRlLFxuICAgICAgICBuZXh0UGVyaW9kRW5kRGF0ZSxcbiAgICAgIH0gPSBkZXRlcm1pbmVEYXRlUmFuZ2UoJ3RoaXMgd2VlaycpO1xuICAgICAgLy8gRXhwZWN0ZWQ6IE1vbiwgSnVsIDIyLCAyMDI0IHRvIFdlZCwgSnVsIDI0LCAyMDI0XG4gICAgICBleHBlY3Qoc3RhcnREYXRlLmdldEZ1bGxZZWFyKCkpLnRvQmUoMjAyNCk7XG4gICAgICBleHBlY3Qoc3RhcnREYXRlLmdldE1vbnRoKCkpLnRvQmUoNik7IC8vIEp1bHlcbiAgICAgIGV4cGVjdChzdGFydERhdGUuZ2V0RGF0ZSgpKS50b0JlKDIyKTsgLy8gTW9uZGF5XG5cbiAgICAgIGV4cGVjdChlbmREYXRlLmdldEZ1bGxZZWFyKCkpLnRvQmUoMjAyNCk7XG4gICAgICBleHBlY3QoZW5kRGF0ZS5nZXRNb250aCgpKS50b0JlKDYpOyAvLyBKdWx5XG4gICAgICBleHBlY3QoZW5kRGF0ZS5nZXREYXRlKCkpLnRvQmUoMjQpOyAvLyBXZWRuZXNkYXkgKHRvZGF5KVxuICAgICAgZXhwZWN0KGVuZERhdGUuZ2V0SG91cnMoKSkudG9CZSgyMyk7IC8vIEVuZCBvZiBkYXlcblxuICAgICAgZXhwZWN0KGRpc3BsYXlSYW5nZSkudG9Db250YWluKCdUaGlzIFdlZWsgKEp1bCAyMiAtIEp1bCAyNCknKTtcblxuICAgICAgLy8gTmV4dCBwZXJpb2Qgc3RhcnRzIEp1bCAyNSAoVGh1KSBhbmQgZW5kcyBKdWwgMzEgKFdlZClcbiAgICAgIGV4cGVjdChuZXh0UGVyaW9kU3RhcnREYXRlLmdldERhdGUoKSkudG9CZSgyNSk7XG4gICAgICBleHBlY3QobmV4dFBlcmlvZEVuZERhdGUuZ2V0RGF0ZSgpKS50b0JlKDMxKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgY29ycmVjdGx5IGRldGVybWluZSBcInRoaXMgd2Vla1wiIGFzIE1vbi1GcmkgaWYgY3VycmVudCBkYXkgaXMgcGFzdCBGcmlkYXkgNXBtIG9yIHdlZWtlbmQnLCAoKSA9PiB7XG4gICAgICBqZXN0LnVzZUZha2VUaW1lcnMoKS5zZXRTeXN0ZW1UaW1lKG5ldyBEYXRlKDIwMjQsIDYsIDI2LCAxOCwgMCwgMCkpOyAvLyBGcmlkYXkgNiBQTVxuICAgICAgY29uc3QgeyBzdGFydERhdGUsIGVuZERhdGUsIGRpc3BsYXlSYW5nZSB9ID1cbiAgICAgICAgZGV0ZXJtaW5lRGF0ZVJhbmdlKCd0aGlzIHdlZWsnKTtcbiAgICAgIC8vIEV4cGVjdGVkOiBNb24sIEp1bCAyMiwgMjAyNCB0byBGcmksIEp1bCAyNiwgMjAyNFxuICAgICAgZXhwZWN0KHN0YXJ0RGF0ZS5nZXREYXRlKCkpLnRvQmUoMjIpO1xuICAgICAgZXhwZWN0KGVuZERhdGUuZ2V0RGF0ZSgpKS50b0JlKDI2KTsgLy8gRnJpZGF5XG4gICAgICBleHBlY3QoZGlzcGxheVJhbmdlKS50b0NvbnRhaW4oJ1RoaXMgV2VlayAoSnVsIDIyIC0gSnVsIDI2KScpO1xuXG4gICAgICBqZXN0LnVzZUZha2VUaW1lcnMoKS5zZXRTeXN0ZW1UaW1lKG5ldyBEYXRlKDIwMjQsIDYsIDI3KSk7IC8vIFNhdHVyZGF5XG4gICAgICBjb25zdCB7IHN0YXJ0RGF0ZTogc2F0U3RhcnQsIGVuZERhdGU6IHNhdEVuZCB9ID1cbiAgICAgICAgZGV0ZXJtaW5lRGF0ZVJhbmdlKCd0aGlzIHdlZWsnKTtcbiAgICAgIGV4cGVjdChzYXRTdGFydC5nZXREYXRlKCkpLnRvQmUoMjIpO1xuICAgICAgZXhwZWN0KHNhdEVuZC5nZXREYXRlKCkpLnRvQmUoMjYpOyAvLyBTdGlsbCBzaG93cyBNb24tRnJpXG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGNvcnJlY3RseSBkZXRlcm1pbmUgXCJsYXN0IHdlZWtcIiAoTW9uIHRvIFN1biknLCAoKSA9PiB7XG4gICAgICAvLyBUb2RheSBpcyBXZWQsIEp1bCAyNCwgMjAyNFxuICAgICAgY29uc3Qge1xuICAgICAgICBzdGFydERhdGUsXG4gICAgICAgIGVuZERhdGUsXG4gICAgICAgIGRpc3BsYXlSYW5nZSxcbiAgICAgICAgbmV4dFBlcmlvZFN0YXJ0RGF0ZSxcbiAgICAgICAgbmV4dFBlcmlvZEVuZERhdGUsXG4gICAgICB9ID0gZGV0ZXJtaW5lRGF0ZVJhbmdlKCdsYXN0IHdlZWsnKTtcbiAgICAgIC8vIEV4cGVjdGVkOiBNb24sIEp1bCAxNSwgMjAyNCB0byBTdW4sIEp1bCAyMSwgMjAyNFxuICAgICAgZXhwZWN0KHN0YXJ0RGF0ZS5nZXRGdWxsWWVhcigpKS50b0JlKDIwMjQpO1xuICAgICAgZXhwZWN0KHN0YXJ0RGF0ZS5nZXRNb250aCgpKS50b0JlKDYpO1xuICAgICAgZXhwZWN0KHN0YXJ0RGF0ZS5nZXREYXRlKCkpLnRvQmUoMTUpO1xuXG4gICAgICBleHBlY3QoZW5kRGF0ZS5nZXRGdWxsWWVhcigpKS50b0JlKDIwMjQpO1xuICAgICAgZXhwZWN0KGVuZERhdGUuZ2V0TW9udGgoKSkudG9CZSg2KTtcbiAgICAgIGV4cGVjdChlbmREYXRlLmdldERhdGUoKSkudG9CZSgyMSk7XG4gICAgICBleHBlY3QoZW5kRGF0ZS5nZXRIb3VycygpKS50b0JlKDIzKTtcbiAgICAgIGV4cGVjdChkaXNwbGF5UmFuZ2UpLnRvQ29udGFpbignTGFzdCBXZWVrIChKdWwgMTUgLSBKdWwgMjEpJyk7XG5cbiAgICAgIC8vIE5leHQgcGVyaW9kIHN0YXJ0cyBKdWwgMjIgKE1vbikgYW5kIGVuZHMgSnVsIDI4IChTdW4pXG4gICAgICBleHBlY3QobmV4dFBlcmlvZFN0YXJ0RGF0ZS5nZXREYXRlKCkpLnRvQmUoMjIpO1xuICAgICAgZXhwZWN0KG5leHRQZXJpb2RFbmREYXRlLmdldERhdGUoKSkudG9CZSgyOCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGRlZmF1bHQgdG8gXCJ0aGlzIHdlZWtcIiBpZiBubyB0aW1lUGVyaW9kIGlzIHByb3ZpZGVkJywgKCkgPT4ge1xuICAgICAgY29uc3QgZGVmYXVsdFJhbmdlID0gZGV0ZXJtaW5lRGF0ZVJhbmdlKCk7XG4gICAgICBjb25zdCB0aGlzV2Vla1JhbmdlID0gZGV0ZXJtaW5lRGF0ZVJhbmdlKCd0aGlzIHdlZWsnKTtcbiAgICAgIGV4cGVjdChkZWZhdWx0UmFuZ2Uuc3RhcnREYXRlLnRvSVNPU3RyaW5nKCkpLnRvQmUoXG4gICAgICAgIHRoaXNXZWVrUmFuZ2Uuc3RhcnREYXRlLnRvSVNPU3RyaW5nKClcbiAgICAgICk7XG4gICAgICBleHBlY3QoZGVmYXVsdFJhbmdlLmVuZERhdGUudG9JU09TdHJpbmcoKSkudG9CZShcbiAgICAgICAgdGhpc1dlZWtSYW5nZS5lbmREYXRlLnRvSVNPU3RyaW5nKClcbiAgICAgICk7XG4gICAgICBleHBlY3QoZGVmYXVsdFJhbmdlLmRpc3BsYXlSYW5nZSkudG9CZSh0aGlzV2Vla1JhbmdlLmRpc3BsYXlSYW5nZSk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdCcsICgpID0+IHtcbiAgICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICAgIC8vIE1vY2sgZGF0ZSBmb3IgdGhlc2UgdGVzdHMgdG8gYmUgY29uc2lzdGVudFxuICAgICAgamVzdC51c2VGYWtlVGltZXJzKCkuc2V0U3lzdGVtVGltZShuZXcgRGF0ZSgyMDI0LCA2LCAyNiwgMTAsIDAsIDApKTsgLy8gRnJpZGF5IDEwIEFNLCBKdWx5IDI2LCAyMDI0XG4gICAgICAvLyBUaGlzIG1lYW5zIFwidGhpcyB3ZWVrXCIgd2lsbCBiZSBNb24gSnVseSAyMiB0byBGcmkgSnVseSAyNlxuICAgICAgLy8gXCJMYXN0IHdlZWtcIiB3aWxsIGJlIE1vbiBKdWx5IDE1IHRvIFN1biBKdWx5IDIxXG4gICAgICAvLyBcIk5leHQgcGVyaW9kXCIgd2lsbCBzdGFydCBTYXQgSnVseSAyN1xuICAgIH0pO1xuXG4gICAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICAgIGplc3QudXNlUmVhbFRpbWVycygpO1xuICAgIH0pO1xuXG4gICAgY29uc3QgbW9ja0NvbXBsZXRlZFRhc2s6IE5vdGlvblRhc2sgPSB7XG4gICAgICBpZDogJ2N0MScsXG4gICAgICBkZXNjcmlwdGlvbjogJ0ZpbmlzaGVkIG1ham9yIHJlcG9ydCcsXG4gICAgICBzdGF0dXM6ICdEb25lJyxcbiAgICAgIGNyZWF0ZWREYXRlOiAnMjAyNC0wNy0yM1QxMDowMDowMFonLFxuICAgICAgbGFzdF9lZGl0ZWRfdGltZTogJzIwMjQtMDctMjNUMTA6MDA6MDBaJyxcbiAgICAgIHVybDogJycsXG4gICAgfTtcbiAgICBjb25zdCBtb2NrQXR0ZW5kZWRNZWV0aW5nOiBDYWxlbmRhckV2ZW50ID0ge1xuICAgICAgaWQ6ICdhbTEnLFxuICAgICAgc3VtbWFyeTogJ0J1ZGdldCBSZXZpZXcnLFxuICAgICAgc3RhcnRUaW1lOiAnMjAyNC0wNy0yNFQxNDowMDowMFonLFxuICAgICAgZW5kVGltZTogJzIwMjQtMDctMjRUMTU6MDA6MDBaJyxcbiAgICB9O1xuICAgIGNvbnN0IG1vY2tVcGNvbWluZ1Rhc2s6IE5vdGlvblRhc2sgPSB7XG4gICAgICBpZDogJ3V0MScsXG4gICAgICBkZXNjcmlwdGlvbjogJ1ByZXBhcmUgUTQgUHJlc2VudGF0aW9uJyxcbiAgICAgIHN0YXR1czogJ1RvIERvJyxcbiAgICAgIHByaW9yaXR5OiAnSGlnaCcsXG4gICAgICBkdWVEYXRlOiAnMjAyNC0wNy0zMFQxMDowMDowMFonLFxuICAgICAgY3JlYXRlZERhdGU6ICcnLFxuICAgICAgdXJsOiAnJyxcbiAgICB9O1xuICAgIGNvbnN0IG1vY2tVcGNvbWluZ01lZXRpbmc6IENhbGVuZGFyRXZlbnQgPSB7XG4gICAgICBpZDogJ3VtMScsXG4gICAgICBzdW1tYXJ5OiAnQ2xpZW50IFN0cmF0ZWd5IFNlc3Npb24nLFxuICAgICAgc3RhcnRUaW1lOiAnMjAyNC0wNy0yOVQwOTowMDowMFonLFxuICAgICAgZW5kVGltZTogJzIwMjQtMDctMjlUMTA6MzA6MDBaJyxcbiAgICB9O1xuXG4gICAgaXQoJ3Nob3VsZCBnZW5lcmF0ZSBhIGRpZ2VzdCBmb3IgXCJ0aGlzIHdlZWtcIiBzdWNjZXNzZnVsbHknLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrUXVlcnlOb3Rpb25UYXNrc1xuICAgICAgICAubW9ja0ltcGxlbWVudGF0aW9uT25jZShhc3luYyAodXNlcklkLCBwYXJhbXMpID0+IHtcbiAgICAgICAgICAvLyBDb21wbGV0ZWQgdGFza3NcbiAgICAgICAgICBpZiAocGFyYW1zLnN0YXR1cyA9PT0gJ0RvbmUnKVxuICAgICAgICAgICAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSwgdGFza3M6IFttb2NrQ29tcGxldGVkVGFza10gfTtcbiAgICAgICAgICByZXR1cm4geyBzdWNjZXNzOiB0cnVlLCB0YXNrczogW10gfTtcbiAgICAgICAgfSlcbiAgICAgICAgLm1vY2tJbXBsZW1lbnRhdGlvbk9uY2UoYXN5bmMgKHVzZXJJZCwgcGFyYW1zKSA9PiB7XG4gICAgICAgICAgLy8gVXBjb21pbmcgY3JpdGljYWwgdGFza3NcbiAgICAgICAgICBpZiAocGFyYW1zLnByaW9yaXR5ID09PSAnSGlnaCcpXG4gICAgICAgICAgICByZXR1cm4geyBzdWNjZXNzOiB0cnVlLCB0YXNrczogW21vY2tVcGNvbWluZ1Rhc2tdIH07XG4gICAgICAgICAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSwgdGFza3M6IFtdIH07XG4gICAgICAgIH0pO1xuXG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzXG4gICAgICAgIC5tb2NrSW1wbGVtZW50YXRpb25PbmNlKGFzeW5jICh1c2VySWQsIGxpbWl0LCB0aW1lTWluLCB0aW1lTWF4KSA9PiB7XG4gICAgICAgICAgLy8gQXR0ZW5kZWQgbWVldGluZ3NcbiAgICAgICAgICAvLyBDaGVjayBpZiB0aW1lTWluIGlzIGFyb3VuZCBKdWx5IDIyLTI2XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgdGltZU1pbiAmJlxuICAgICAgICAgICAgbmV3IERhdGUodGltZU1pbikuZ2V0RGF0ZSgpID49IDIyICYmXG4gICAgICAgICAgICBuZXcgRGF0ZSh0aW1lTWluKS5nZXREYXRlKCkgPD0gMjZcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIHJldHVybiBbbW9ja0F0dGVuZGVkTWVldGluZ107XG4gICAgICAgICAgfVxuICAgICAgICAgIHJldHVybiBbXTtcbiAgICAgICAgfSlcbiAgICAgICAgLm1vY2tJbXBsZW1lbnRhdGlvbk9uY2UoYXN5bmMgKHVzZXJJZCwgbGltaXQsIHRpbWVNaW4sIHRpbWVNYXgpID0+IHtcbiAgICAgICAgICAvLyBVcGNvbWluZyBtZWV0aW5nc1xuICAgICAgICAgIC8vIENoZWNrIGlmIHRpbWVNaW4gaXMgYXJvdW5kIEp1bHkgMjcgb253YXJkc1xuICAgICAgICAgIGlmICh0aW1lTWluICYmIG5ldyBEYXRlKHRpbWVNaW4pLmdldERhdGUoKSA+PSAyNykge1xuICAgICAgICAgICAgcmV0dXJuIFttb2NrVXBjb21pbmdNZWV0aW5nXTtcbiAgICAgICAgICB9XG4gICAgICAgICAgcmV0dXJuIFtdO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdChcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ3RoaXMgd2VlaydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBjb25zdCBkaWdlc3QgPSByZXNwb25zZS5kYXRhPy5kaWdlc3Q7XG4gICAgICBleHBlY3QoZGlnZXN0KS50b0JlRGVmaW5lZCgpO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8uY29tcGxldGVkVGFza3MpLnRvRXF1YWwoW21vY2tDb21wbGV0ZWRUYXNrXSk7XG4gICAgICBleHBlY3QoZGlnZXN0Py5hdHRlbmRlZE1lZXRpbmdzKS50b0VxdWFsKFttb2NrQXR0ZW5kZWRNZWV0aW5nXSk7XG4gICAgICBleHBlY3QoZGlnZXN0Py51cGNvbWluZ0NyaXRpY2FsVGFza3MpLnRvRXF1YWwoW21vY2tVcGNvbWluZ1Rhc2tdKTtcbiAgICAgIGV4cGVjdChkaWdlc3Q/LnVwY29taW5nQ3JpdGljYWxNZWV0aW5ncykudG9FcXVhbChbbW9ja1VwY29taW5nTWVldGluZ10pO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8uZXJyb3JNZXNzYWdlKS50b0JlRmFsc3koKTtcbiAgICAgIC8vIENoZWNrIGlmIHBlcmlvZFN0YXJ0IGFuZCBwZXJpb2RFbmQgbWF0Y2ggXCJ0aGlzIHdlZWtcIiBiYXNlZCBvbiBtb2NrZWQgZGF0ZVxuICAgICAgZXhwZWN0KG5ldyBEYXRlKGRpZ2VzdCEucGVyaW9kU3RhcnQpLmdldERhdGUoKSkudG9CZSgyMik7IC8vIE1vbiwgSnVseSAyMlxuICAgICAgZXhwZWN0KG5ldyBEYXRlKGRpZ2VzdCEucGVyaW9kRW5kKS5nZXREYXRlKCkpLnRvQmUoMjYpOyAvLyBGcmksIEp1bHkgMjZcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgZ2VuZXJhdGUgYSBkaWdlc3QgZm9yIFwibGFzdCB3ZWVrXCInLCBhc3luYyAoKSA9PiB7XG4gICAgICAvLyBTaW1pbGFyIHNldHVwIGFzIGFib3ZlLCBidXQgYWRqdXN0IG1vY2sgaW1wbGVtZW50YXRpb25zIHRvIHJldHVybiBkYXRhIGZvciBcImxhc3Qgd2Vla1wiIChKdWx5IDE1LTIxKVxuICAgICAgLy8gYW5kIFwibmV4dCBwZXJpb2RcIiAoc3RhcnRpbmcgSnVseSAyMilcbiAgICAgIG1vY2tRdWVyeU5vdGlvblRhc2tzXG4gICAgICAgIC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICAgICAgdGFza3M6IFtcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgLi4ubW9ja0NvbXBsZXRlZFRhc2ssXG4gICAgICAgICAgICAgIGlkOiAnbHdfY3QxJyxcbiAgICAgICAgICAgICAgbGFzdF9lZGl0ZWRfdGltZTogJzIwMjQtMDctMThUMTA6MDA6MDBaJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgXSxcbiAgICAgICAgfSkgLy8gQ29tcGxldGVkIGxhc3Qgd2Vla1xuICAgICAgICAubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICAgIHRhc2tzOiBbXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgIC4uLm1vY2tVcGNvbWluZ1Rhc2ssXG4gICAgICAgICAgICAgIGlkOiAnbHdfdXQxJyxcbiAgICAgICAgICAgICAgZHVlRGF0ZTogJzIwMjQtMDctMjRUMTA6MDA6MDBaJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgXSxcbiAgICAgICAgfSk7IC8vIFVwY29taW5nIHRoaXMgd2VlayAocmVsYXRpdmUgdG8gbGFzdCB3ZWVrJ3MgZGlnZXN0KVxuXG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzXG4gICAgICAgIC5tb2NrSW1wbGVtZW50YXRpb25PbmNlKGFzeW5jICh1c2VySWQsIGxpbWl0LCB0aW1lTWluLCB0aW1lTWF4KSA9PiB7XG4gICAgICAgICAgLy8gQXR0ZW5kZWQgbWVldGluZ3MgbGFzdCB3ZWVrXG4gICAgICAgICAgaWYgKHRpbWVNaW4gJiYgbmV3IERhdGUodGltZU1pbikuZ2V0RGF0ZSgpID09PSAxNSkge1xuICAgICAgICAgICAgLy8gTW9uIEp1bHkgMTVcbiAgICAgICAgICAgIHJldHVybiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAuLi5tb2NrQXR0ZW5kZWRNZWV0aW5nLFxuICAgICAgICAgICAgICAgIGlkOiAnbHdfYW0xJyxcbiAgICAgICAgICAgICAgICBzdGFydFRpbWU6ICcyMDI0LTA3LTE3VDE0OjAwOjAwWicsXG4gICAgICAgICAgICAgICAgZW5kVGltZTogJzIwMjQtMDctMTdUMTU6MDA6MDBaJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF07XG4gICAgICAgICAgfVxuICAgICAgICAgIHJldHVybiBbXTtcbiAgICAgICAgfSlcbiAgICAgICAgLm1vY2tJbXBsZW1lbnRhdGlvbk9uY2UoYXN5bmMgKHVzZXJJZCwgbGltaXQsIHRpbWVNaW4sIHRpbWVNYXgpID0+IHtcbiAgICAgICAgICAvLyBVcGNvbWluZyBtZWV0aW5ncyB0aGlzIHdlZWtcbiAgICAgICAgICBpZiAodGltZU1pbiAmJiBuZXcgRGF0ZSh0aW1lTWluKS5nZXREYXRlKCkgPT09IDIyKSB7XG4gICAgICAgICAgICAvLyBNb24gSnVseSAyMlxuICAgICAgICAgICAgcmV0dXJuIFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIC4uLm1vY2tVcGNvbWluZ01lZXRpbmcsXG4gICAgICAgICAgICAgICAgaWQ6ICdsd191bTEnLFxuICAgICAgICAgICAgICAgIHN0YXJ0VGltZTogJzIwMjQtMDctMjNUMDk6MDA6MDBaJyxcbiAgICAgICAgICAgICAgICBlbmRUaW1lOiAnMjAyNC0wNy0yM1QxMDozMDowMFonLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXTtcbiAgICAgICAgICB9XG4gICAgICAgICAgcmV0dXJuIFtdO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVHZW5lcmF0ZVdlZWtseURpZ2VzdChcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ2xhc3Qgd2VlaydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBjb25zdCBkaWdlc3QgPSByZXNwb25zZS5kYXRhPy5kaWdlc3Q7XG4gICAgICBleHBlY3QoZGlnZXN0KS50b0JlRGVmaW5lZCgpO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8uY29tcGxldGVkVGFza3NbMF0uaWQpLnRvQmUoJ2x3X2N0MScpO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8uYXR0ZW5kZWRNZWV0aW5nc1swXS5pZCkudG9CZSgnbHdfYW0xJyk7XG4gICAgICBleHBlY3QoZGlnZXN0Py51cGNvbWluZ0NyaXRpY2FsVGFza3NbMF0uaWQpLnRvQmUoJ2x3X3V0MScpO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8udXBjb21pbmdDcml0aWNhbE1lZXRpbmdzWzBdLmlkKS50b0JlKCdsd191bTEnKTtcbiAgICAgIC8vIENoZWNrIHBlcmlvZCBkYXRlcyBmb3IgXCJsYXN0IHdlZWtcIlxuICAgICAgZXhwZWN0KG5ldyBEYXRlKGRpZ2VzdCEucGVyaW9kU3RhcnQpLmdldERhdGUoKSkudG9CZSgxNSk7IC8vIE1vbiwgSnVseSAxNVxuICAgICAgZXhwZWN0KG5ldyBEYXRlKGRpZ2VzdCEucGVyaW9kRW5kKS5nZXREYXRlKCkpLnRvQmUoMjEpOyAvLyBTdW4sIEp1bHkgMjFcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaGFuZGxlIG1pc3NpbmcgQVRPTV9OT1RJT05fVEFTS1NfREFUQUJBU0VfSUQgZ3JhY2VmdWxseScsIGFzeW5jICgpID0+IHtcbiAgICAgIGRlbGV0ZSBwcm9jZXNzLmVudi5BVE9NX05PVElPTl9UQVNLU19EQVRBQkFTRV9JRDtcbiAgICAgIC8vIE1vY2tzIGZvciBjYWxlbmRhciB3aWxsIHJldHVybiBlbXB0eVxuICAgICAgbW9ja0xpc3RVcGNvbWluZ0V2ZW50cy5tb2NrUmVzb2x2ZWRWYWx1ZShbXSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3QoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICd0aGlzIHdlZWsnXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKHRydWUpO1xuICAgICAgY29uc3QgZGlnZXN0ID0gcmVzcG9uc2UuZGF0YT8uZGlnZXN0O1xuICAgICAgZXhwZWN0KGRpZ2VzdD8uY29tcGxldGVkVGFza3MpLnRvRXF1YWwoW10pO1xuICAgICAgZXhwZWN0KGRpZ2VzdD8udXBjb21pbmdDcml0aWNhbFRhc2tzKS50b0VxdWFsKFtdKTtcbiAgICAgIGV4cGVjdChkaWdlc3Q/LmVycm9yTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnTm90aW9uIHRhc2tzIGRhdGFiYXNlIElEIG5vdCBjb25maWd1cmVkJ1xuICAgICAgKTtcbiAgICAgIHByb2Nlc3MuZW52LkFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lEID0gbW9ja05vdGlvblRhc2tzRGJJZDsgLy8gUmVzZXRcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaGFuZGxlIGVycm9ycyBmcm9tIHVuZGVybHlpbmcgc2VydmljZXMgYW5kIHJlcG9ydCB0aGVtJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIHRhc2tzOiBbXSxcbiAgICAgICAgZXJyb3I6ICdOb3Rpb24gQVBJIGVycm9yIGZvciBjb21wbGV0ZWQnLFxuICAgICAgfSk7XG4gICAgICAvLyBvdGhlciBtb2NrcyBjYW4gYmUgZGVmYXVsdCAoZW1wdHkpIG9yIGFsc28gZXJyb3JcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignQ2FsZW5kYXIgc2VydmljZSBkb3duJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlR2VuZXJhdGVXZWVrbHlEaWdlc3QoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICd0aGlzIHdlZWsnXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKHRydWUpOyAvLyBTa2lsbCBpdHNlbGYgaXMgb2ssIGJ1dCBkYXRhIGZldGNoaW5nIGhhZCBpc3N1ZXNcbiAgICAgIGNvbnN0IGRpZ2VzdCA9IHJlc3BvbnNlLmRhdGE/LmRpZ2VzdDtcbiAgICAgIGV4cGVjdChkaWdlc3Q/LmVycm9yTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnQ291bGQgbm90IGZldGNoIGNvbXBsZXRlZCB0YXNrczogTm90aW9uIEFQSSBlcnJvciBmb3IgY29tcGxldGVkJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChkaWdlc3Q/LmVycm9yTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnRXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgYXR0ZW5kZWQgbWVldGluZ3MuJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChkaWdlc3Q/LmVycm9yTWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnRXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgdXBjb21pbmcgbWVldGluZ3MuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgLy8gLS0tIFRlc3RzIGZvciBJbnRlbGxpZ2VudCBGb2xsb3ctdXAgU3VnZ2VzdGVyIC0tLVxuICBkZXNjcmliZSgnaGFuZGxlU3VnZ2VzdEZvbGxvd1VwcycsICgpID0+IHtcbiAgICAvLyBNb2NrIHRoZSBjb25jZXB0dWFsIExMTSB1dGlsaXR5XG4gICAgY29uc3QgbW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzID0gamVzdC5mbigpO1xuICAgIGxldCBvcmlnaW5hbExsbVV0aWxpdGllczogYW55O1xuXG4gICAgYmVmb3JlQWxsKGFzeW5jICgpID0+IHtcbiAgICAgIC8vIFRoaXMgaXMgYSBtb3JlIGNvbXBsZXggd2F5IHRvIG1vY2ssIG5lZWRlZCBpZiBsbG1VdGlsaXRpZXMgaXMgYSBzZXBhcmF0ZSBtb2R1bGVcbiAgICAgIC8vIEZvciBhIHNpbXBsZSBjb25jZXB0dWFsIG1vY2ssIGRpcmVjdCBqZXN0Lm1vY2sgbWlnaHQgYmUgZW5vdWdoLlxuICAgICAgLy8gVGhpcyBlbnN1cmVzIHRoYXQgd2hlbiBwcm9kdWN0aXZpdHlTa2lsbHMgaW1wb3J0cyBmcm9tIGxsbVV0aWxpdGllcywgaXQgZ2V0cyBvdXIgbW9jay5cbiAgICAgIGplc3QuZG9Nb2NrKCcuLi9sbG1VdGlsaXRpZXMnLCAoKSA9PiAoe1xuICAgICAgICBhbmFseXplVGV4dEZvckZvbGxvd1VwczogbW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzLFxuICAgICAgfSkpO1xuICAgICAgLy8gUmUtcmVxdWlyZSBwcm9kdWN0aXZpdHlTa2lsbHMgdG8gcGljayB1cCB0aGUgbW9jay4gVGhpcyBpcyB0cmlja3kuXG4gICAgICAvLyBBIHNpbXBsZXIgd2F5IGlmIGxsbVV0aWxpdGllcyBpcyBkaXJlY3RseSBwYXJ0IG9mIHByb2R1Y3Rpdml0eVNraWxscyBvciBlYXNpbHkgbW9ja2FibGU6XG4gICAgICAvLyBkaXJlY3RseSBtb2NrIGl0IGxpa2Ugb3RoZXIgc2tpbGxzLlxuICAgICAgLy8gRm9yIG5vdywgbGV0J3MgYXNzdW1lIHRoZSBtb2NrIHNldHVwIGZvciBsbG1VdGlsaXRpZXMgaXMgY29ycmVjdGx5IGhhbmRsZWRcbiAgICAgIC8vIGJ5IGplc3QubW9jayBhdCB0aGUgdG9wIGlmIGl0IHdlcmUgYSBzZXBhcmF0ZSBmaWxlLCBvciB3ZSdkIHBhc3MgaXQgYXMgYSBkZXBlbmRlbmN5LlxuICAgIH0pO1xuXG4gICAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgICBtb2NrQW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMubW9ja1Jlc2V0KCk7XG4gICAgICAvLyBSZXNldCBvdGhlciBuZWNlc3NhcnkgbW9ja3MgaWYgdGhleSBhcmUgdXNlZCBieSBoYW5kbGVTdWdnZXN0Rm9sbG93VXBzXG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNldCgpO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzZXQoKTtcbiAgICAgIG1vY2tRdWVyeU5vdGlvblRhc2tzLm1vY2tSZXNldCgpO1xuXG4gICAgICAvLyBEZWZhdWx0IG1vY2sgaW1wbGVtZW50YXRpb25zIGZvciB0aGlzIHRlc3Qgc3VpdGVcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW10pO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7IG9rOiB0cnVlLCBkYXRhOiBbXSB9KTtcbiAgICAgIG1vY2tRdWVyeU5vdGlvblRhc2tzLm1vY2tSZXNvbHZlZFZhbHVlKHsgc3VjY2VzczogdHJ1ZSwgdGFza3M6IFtdIH0pO1xuICAgICAgbW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgZXh0cmFjdGVkSXRlbXM6IHsgYWN0aW9uX2l0ZW1zOiBbXSwgZGVjaXNpb25zOiBbXSwgcXVlc3Rpb25zOiBbXSB9LFxuICAgICAgfSk7XG4gICAgfSk7XG5cbiAgICBjb25zdCBtb2NrTWVldGluZ0NvbnRleHQ6IENhbGVuZGFyRXZlbnQgPSB7XG4gICAgICBpZDogJ21lZXRpbmcxMjMnLFxuICAgICAgc3VtbWFyeTogJ1Byb2plY3QgUGhvZW5peCBRMSBSZXZpZXcnLFxuICAgICAgc3RhcnRUaW1lOiAnMjAyNC0wNy0yMFQxMDowMDowMFonLFxuICAgICAgZW5kVGltZTogJzIwMjQtMDctMjBUMTE6MDA6MDBaJyxcbiAgICAgIGRlc2NyaXB0aW9uOiAnUmV2aWV3IG9mIFExIHByb2dyZXNzIGZvciBQcm9qZWN0IFBob2VuaXguJyxcbiAgICB9O1xuXG4gICAgY29uc3QgbW9ja05vdGlvbkRvYzogTm90aW9uU2VhcmNoUmVzdWx0RGF0YSA9IHtcbiAgICAgIGlkOiAnbm90aW9uRG9jMScsXG4gICAgICB0aXRsZTogJ1Byb2plY3QgUGhvZW5peCBRMSBSZXZpZXcgTm90ZXMnLFxuICAgICAgY29udGVudDpcbiAgICAgICAgJ0FjdGlvbiBJdGVtOiBBbGljZSB0byB1cGRhdGUgcm9hZG1hcC4gRGVjaXNpb246IFEyIGJ1ZGdldCBhcHByb3ZlZC4gUXVlc3Rpb246IFdoZW4gaXMgUGhhc2UgMiBzdGFydGluZz8nLFxuICAgICAgdXJsOiAnaHR0cDovL25vdGlvbi5zby9waG9lbml4cTFub3RlcycsXG4gICAgfTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIENPTlRFWFRfTk9UX0ZPVU5EIGlmIG5vIG1lZXRpbmcgb3IgcHJvamVjdCBkb2N1bWVudCBpcyBmb3VuZCcsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW10pOyAvLyBObyBtZWV0aW5ncyBmb3VuZFxuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7IG9rOiB0cnVlLCBkYXRhOiBbXSB9KTsgLy8gTm8gbm90aW9uIGRvYyBmb3IgZ2VuZXJpYyBzZWFyY2hcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVTdWdnZXN0Rm9sbG93VXBzKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICAnVW5rbm93biBDb250ZXh0J1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZXJyb3I/LmNvZGUpLnRvQmUoJ0NPTlRFWFRfTk9UX0ZPVU5EJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBzb3VyY2UgZG9jdW1lbnQgaXMgdG9vIHNob3J0IGZvciBhbmFseXNpcycsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW21vY2tNZWV0aW5nQ29udGV4dF0pO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiBbeyAuLi5tb2NrTm90aW9uRG9jLCBjb250ZW50OiAnVG9vIHNob3J0LicgfV0sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVTdWdnZXN0Rm9sbG93VXBzKFxuICAgICAgICBtb2NrVXNlcklkLFxuICAgICAgICAnUHJvamVjdCBQaG9lbml4IFExIFJldmlldycsXG4gICAgICAgICdtZWV0aW5nJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5vaykudG9CZSh0cnVlKTsgLy8gU2tpbGwgaXMgXCJva1wiIGJ1dCBkYXRhIGNvbnRhaW5zIGVycm9yXG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8uZXJyb3JNZXNzYWdlKS50b0NvbnRhaW4oXG4gICAgICAgICd0b28gc2hvcnQgb3IgZW1wdHkgZm9yIHVzZWZ1bCBhbmFseXNpcydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8uc3VnZ2VzdGlvbnMpLnRvRXF1YWwoW10pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBwcm9jZXNzIG1lZXRpbmcgY29udGV4dCwgY2FsbCBMTE0sIGFuZCBzdWdnZXN0IGZvbGxvdy11cHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrTGlzdFVwY29taW5nRXZlbnRzLm1vY2tSZXNvbHZlZFZhbHVlKFttb2NrTWVldGluZ0NvbnRleHRdKTtcbiAgICAgIG1vY2tTZWFyY2hOb3Rpb25SYXcubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgZGF0YTogW21vY2tOb3Rpb25Eb2NdLFxuICAgICAgfSk7IC8vIE5vdGlvbiBub3RlcyBmb3IgdGhlIG1lZXRpbmdcbiAgICAgIG1vY2tBbmFseXplVGV4dEZvckZvbGxvd1Vwcy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGV4dHJhY3RlZEl0ZW1zOiB7XG4gICAgICAgICAgYWN0aW9uX2l0ZW1zOiBbXG4gICAgICAgICAgICB7IGRlc2NyaXB0aW9uOiAnQWxpY2UgdG8gdXBkYXRlIHJvYWRtYXAnLCBhc3NpZ25lZTogJ0FsaWNlJyB9LFxuICAgICAgICAgIF0sXG4gICAgICAgICAgZGVjaXNpb25zOiBbeyBkZXNjcmlwdGlvbjogJ1EyIGJ1ZGdldCBhcHByb3ZlZCcgfV0sXG4gICAgICAgICAgcXVlc3Rpb25zOiBbeyBkZXNjcmlwdGlvbjogJ1doZW4gaXMgUGhhc2UgMiBzdGFydGluZz8nIH1dLFxuICAgICAgICB9LFxuICAgICAgfSk7XG4gICAgICAvLyBBc3N1bWUgbm8gZXhpc3RpbmcgdGFza3MgYXJlIGZvdW5kIGJ5IHF1ZXJ5Tm90aW9uVGFza3MgZm9yIFwiQWxpY2UgdG8gdXBkYXRlIHJvYWRtYXBcIlxuICAgICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWUoeyBzdWNjZXNzOiB0cnVlLCB0YXNrczogW10gfSk7XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaGFuZGxlU3VnZ2VzdEZvbGxvd1VwcyhcbiAgICAgICAgbW9ja1VzZXJJZCxcbiAgICAgICAgJ1Byb2plY3QgUGhvZW5peCBRMSBSZXZpZXcnLFxuICAgICAgICAnbWVldGluZydcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QobW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgbW9ja05vdGlvbkRvYy5jb250ZW50LFxuICAgICAgICBtb2NrTm90aW9uRG9jLnRpdGxlXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LnN1Z2dlc3Rpb25zKS50b0hhdmVMZW5ndGgoMyk7XG4gICAgICBleHBlY3QoXG4gICAgICAgIHJlc3BvbnNlLmRhdGE/LnN1Z2dlc3Rpb25zLmZpbmQoKHMpID0+IHMudHlwZSA9PT0gJ2FjdGlvbl9pdGVtJylcbiAgICAgICAgICA/LmRlc2NyaXB0aW9uXG4gICAgICApLnRvQmUoJ0FsaWNlIHRvIHVwZGF0ZSByb2FkbWFwJyk7XG4gICAgICBleHBlY3QoXG4gICAgICAgIHJlc3BvbnNlLmRhdGE/LnN1Z2dlc3Rpb25zLmZpbmQoKHMpID0+IHMudHlwZSA9PT0gJ2FjdGlvbl9pdGVtJylcbiAgICAgICAgICA/LmV4aXN0aW5nVGFza0ZvdW5kXG4gICAgICApLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KFxuICAgICAgICByZXNwb25zZS5kYXRhPy5zdWdnZXN0aW9ucy5maW5kKChzKSA9PiBzLnR5cGUgPT09ICdkZWNpc2lvbicpXG4gICAgICAgICAgPy5kZXNjcmlwdGlvblxuICAgICAgKS50b0JlKCdRMiBidWRnZXQgYXBwcm92ZWQnKTtcbiAgICAgIGV4cGVjdChcbiAgICAgICAgcmVzcG9uc2UuZGF0YT8uc3VnZ2VzdGlvbnMuZmluZCgocykgPT4gcy50eXBlID09PSAncXVlc3Rpb24nKVxuICAgICAgICAgID8uZGVzY3JpcHRpb25cbiAgICAgICkudG9CZSgnV2hlbiBpcyBQaGFzZSAyIHN0YXJ0aW5nPycpO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LmNvbnRleHROYW1lKS50b0JlKFxuICAgICAgICBgTWVldGluZzogJHttb2NrTm90aW9uRG9jLnRpdGxlfSBvbiAke25ldyBEYXRlKG1vY2tNZWV0aW5nQ29udGV4dC5zdGFydFRpbWUpLnRvTG9jYWxlRGF0ZVN0cmluZygpfWBcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGlkZW50aWZ5IGFuIGV4aXN0aW5nIHRhc2sgZm9yIGEgc3VnZ2VzdGVkIGFjdGlvbiBpdGVtJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0xpc3RVcGNvbWluZ0V2ZW50cy5tb2NrUmVzb2x2ZWRWYWx1ZShbbW9ja01lZXRpbmdDb250ZXh0XSk7XG4gICAgICBtb2NrU2VhcmNoTm90aW9uUmF3Lm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IFttb2NrTm90aW9uRG9jXSxcbiAgICAgIH0pO1xuICAgICAgbW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgZXh0cmFjdGVkSXRlbXM6IHtcbiAgICAgICAgICBhY3Rpb25faXRlbXM6IFtcbiAgICAgICAgICAgIHsgZGVzY3JpcHRpb246ICdBbGljZSB0byB1cGRhdGUgcm9hZG1hcCcsIGFzc2lnbmVlOiAnQWxpY2UnIH0sXG4gICAgICAgICAgXSxcbiAgICAgICAgICBkZWNpc2lvbnM6IFtdLFxuICAgICAgICAgIHF1ZXN0aW9uczogW10sXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGV4aXN0aW5nVGFzazogTm90aW9uVGFzayA9IHtcbiAgICAgICAgaWQ6ICd0YXNrLXJvYWRtYXAnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ1VwZGF0ZSByb2FkbWFwIGZvciBBbGljZScsXG4gICAgICAgIHN0YXR1czogJ1RvIERvJyxcbiAgICAgICAgdXJsOiAnaHR0cDovL25vdGlvbi90YXNrLXJvYWRtYXAnLFxuICAgICAgICBjcmVhdGVkRGF0ZTogJycsXG4gICAgICB9O1xuICAgICAgbW9ja1F1ZXJ5Tm90aW9uVGFza3MubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICB0YXNrczogW2V4aXN0aW5nVGFza10sXG4gICAgICB9KTsgLy8gVGFzayBmb3VuZFxuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVN1Z2dlc3RGb2xsb3dVcHMoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICdQcm9qZWN0IFBob2VuaXggUTEgUmV2aWV3JyxcbiAgICAgICAgJ21lZXRpbmcnXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKHRydWUpO1xuICAgICAgY29uc3QgYWN0aW9uSXRlbSA9IHJlc3BvbnNlLmRhdGE/LnN1Z2dlc3Rpb25zLmZpbmQoXG4gICAgICAgIChzKSA9PiBzLnR5cGUgPT09ICdhY3Rpb25faXRlbSdcbiAgICAgICk7XG4gICAgICBleHBlY3QoYWN0aW9uSXRlbSkudG9CZURlZmluZWQoKTtcbiAgICAgIGV4cGVjdChhY3Rpb25JdGVtPy5leGlzdGluZ1Rhc2tGb3VuZCkudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChhY3Rpb25JdGVtPy5leGlzdGluZ1Rhc2tJZCkudG9CZSgndGFzay1yb2FkbWFwJyk7XG4gICAgICBleHBlY3QoYWN0aW9uSXRlbT8uZXhpc3RpbmdUYXNrVXJsKS50b0JlKCdodHRwOi8vbm90aW9uL3Rhc2stcm9hZG1hcCcpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgTExNIGFuYWx5c2lzIGZhaWx1cmUgZ3JhY2VmdWxseScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tMaXN0VXBjb21pbmdFdmVudHMubW9ja1Jlc29sdmVkVmFsdWUoW21vY2tNZWV0aW5nQ29udGV4dF0pO1xuICAgICAgbW9ja1NlYXJjaE5vdGlvblJhdy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBkYXRhOiBbbW9ja05vdGlvbkRvY10sXG4gICAgICB9KTtcbiAgICAgIG1vY2tBbmFseXplVGV4dEZvckZvbGxvd1Vwcy5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGV4dHJhY3RlZEl0ZW1zOiB7IGFjdGlvbl9pdGVtczogW10sIGRlY2lzaW9uczogW10sIHF1ZXN0aW9uczogW10gfSxcbiAgICAgICAgZXJyb3I6ICdMTE0gQVBJIHVuYXZhaWxhYmxlJyxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVN1Z2dlc3RGb2xsb3dVcHMoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICdQcm9qZWN0IFBob2VuaXggUTEgUmV2aWV3JyxcbiAgICAgICAgJ21lZXRpbmcnXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLm9rKS50b0JlKHRydWUpOyAvLyBTa2lsbCBpcyBvaywgYnV0IGRhdGEgaGFzIGVycm9yXG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8uZXJyb3JNZXNzYWdlKS50b0NvbnRhaW4oXG4gICAgICAgICdMTE0gYW5hbHlzaXMgZmFpbGVkOiBMTE0gQVBJIHVuYXZhaWxhYmxlJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXNwb25zZS5kYXRhPy5zdWdnZXN0aW9ucykudG9FcXVhbChbXSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHByb2Nlc3MgcHJvamVjdCBjb250ZXh0IGlmIHNwZWNpZmllZCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHByb2plY3ROb3Rpb25Eb2M6IE5vdGlvblNlYXJjaFJlc3VsdERhdGEgPSB7XG4gICAgICAgIGlkOiAncHJvamVjdERvYzEnLFxuICAgICAgICB0aXRsZTogJ0NsaWVudCBPbmJvYXJkaW5nIFByb2plY3QgUGxhbicsXG4gICAgICAgIGNvbnRlbnQ6XG4gICAgICAgICAgJ0FjdGlvbjogU2NoZWR1bGUga2lja29mZiB3aXRoIGNsaWVudC4gRGVjaXNpb246IFVzZSBzdGFuZGFyZCB0ZW1wbGF0ZS4gUXVlc3Rpb246IFdobyBpcyBtYWluIFBvQz8nLFxuICAgICAgICB1cmw6ICdodHRwOi8vbm90aW9uLnNvL2NsaWVudG9uYm9hcmRpbmcnLFxuICAgICAgfTtcbiAgICAgIG1vY2tTZWFyY2hOb3Rpb25SYXcubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgZGF0YTogW3Byb2plY3ROb3Rpb25Eb2NdLFxuICAgICAgfSk7IC8vIE1vY2sgZm9yIHByb2plY3Qgc2VhcmNoXG4gICAgICBtb2NrQW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBleHRyYWN0ZWRJdGVtczoge1xuICAgICAgICAgIGFjdGlvbl9pdGVtczogW3sgZGVzY3JpcHRpb246ICdTY2hlZHVsZSBraWNrb2ZmIHdpdGggY2xpZW50JyB9XSxcbiAgICAgICAgICBkZWNpc2lvbnM6IFt7IGRlc2NyaXB0aW9uOiAnVXNlIHN0YW5kYXJkIHRlbXBsYXRlJyB9XSxcbiAgICAgICAgICBxdWVzdGlvbnM6IFt7IGRlc2NyaXB0aW9uOiAnV2hvIGlzIG1haW4gUG9DPycgfV0sXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgICAgIG1vY2tRdWVyeU5vdGlvblRhc2tzLm1vY2tSZXNvbHZlZFZhbHVlKHsgc3VjY2VzczogdHJ1ZSwgdGFza3M6IFtdIH0pOyAvLyBObyBleGlzdGluZyB0YXNrc1xuXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGhhbmRsZVN1Z2dlc3RGb2xsb3dVcHMoXG4gICAgICAgIG1vY2tVc2VySWQsXG4gICAgICAgICdDbGllbnQgT25ib2FyZGluZyBQcm9qZWN0IFBsYW4nLFxuICAgICAgICAncHJvamVjdCdcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzcG9uc2Uub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QobW9ja0FuYWx5emVUZXh0Rm9yRm9sbG93VXBzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgcHJvamVjdE5vdGlvbkRvYy5jb250ZW50LFxuICAgICAgICBwcm9qZWN0Tm90aW9uRG9jLnRpdGxlXG4gICAgICApO1xuICAgICAgZXhwZWN0KHJlc3BvbnNlLmRhdGE/LnN1Z2dlc3Rpb25zKS50b0hhdmVMZW5ndGgoMyk7XG4gICAgICBleHBlY3QocmVzcG9uc2UuZGF0YT8uY29udGV4dE5hbWUpLnRvQmUoXG4gICAgICAgIGBQcm9qZWN0OiAke3Byb2plY3ROb3Rpb25Eb2MudGl0bGV9YFxuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==