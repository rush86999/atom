// Test file for productivitySkills.ts

import { handlePrepareForMeeting } from '../productivitySkills';
// Import findTargetMeeting if it's exported and needs direct testing,
// otherwise it's tested via handlePrepareForMeeting.
// For this example, let's assume findTargetMeeting is not directly exported for testing.

import * as calendarSkills from '../calendarSkills';
import * as notionSkills from '../notionAndResearchSkills';
import * as emailSkills from '../emailSkills';
import {
  CalendarEvent,
  PrepareForMeetingResponse,
  NotionPageContext,
  EmailContext,
  TaskContext,
  MeetingPreparationData,
  NotionTask,
  Email,
  NotionSearchResultData,
  SkillResponse,
  TaskQueryResponse,
} from '../../../types';

// Mocking the dependent skill modules
jest.mock('../calendarSkills');
jest.mock('../notionAndResearchSkills');
jest.mock('../emailSkills');

const mockListUpcomingEvents = calendarSkills.listUpcomingEvents as jest.MockedFunction<typeof calendarSkills.listUpcomingEvents>;
const mockSearchNotionRaw = notionSkills.searchNotionRaw as jest.MockedFunction<typeof notionSkills.searchNotionRaw>;
const mockQueryNotionTasks = notionSkills.queryNotionTasks as jest.MockedFunction<typeof notionSkills.queryNotionTasks>;
const mockSearchEmailsNLU = emailSkills.searchEmailsNLU as jest.MockedFunction<typeof emailSkills.searchEmailsNLU>;

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
    mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [], message: 'Tasks fetched' });
    mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: [] });

    // Mock process.env
    process.env.ATOM_NOTION_TASKS_DATABASE_ID = mockNotionTasksDbId;
  });

  afterEach(() => {
    delete process.env.ATOM_NOTION_TASKS_DATABASE_ID;
  });

  describe('handlePrepareForMeeting', () => {
    const upcomingEvent1: CalendarEvent = {
      id: 'event1',
      summary: 'Team Sync Q3 Planning',
      startTime: new Date(Date.now() + 1000 * 60 * 60).toISOString(), // In 1 hour
      endTime: new Date(Date.now() + 1000 * 60 * 120).toISOString(), // In 2 hours
      attendees: [{ email: 'user1@example.com', displayName: 'User One' }, { email: 'user2@example.com' }],
      description: 'Discuss Q3 goals and roadmap',
    };
    const upcomingEvent2: CalendarEvent = {
      id: 'event2',
      summary: 'Client Call - Project Alpha',
      startTime: new Date(Date.now() + 1000 * 60 * 60 * 24).toISOString(), // Tomorrow
      endTime: new Date(Date.now() + 1000 * 60 * 60 * 25).toISOString(),
      attendees: [{ email: 'client@example.com', displayName: 'Client Contact' }],
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
      mockListUpcomingEvents.mockResolvedValue([upcomingEvent1, upcomingEvent2].sort((a,b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime()));
      const response = await handlePrepareForMeeting(mockUserId, 'next meeting');
      expect(response.ok).toBe(true);
      expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
    });

    it('should pick the next upcoming meeting if no identifier is provided', async () => {
        mockListUpcomingEvents.mockResolvedValue([upcomingEvent1, upcomingEvent2].sort((a,b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime()));
        const response = await handlePrepareForMeeting(mockUserId); // No identifier
        expect(response.ok).toBe(true);
        expect(response.data?.targetMeeting.id).toBe(upcomingEvent1.id);
      });

    it('should successfully prepare for a meeting with data from all sources', async () => {
      mockListUpcomingEvents.mockResolvedValue([upcomingEvent1]);

      const mockNotionPages: NotionSearchResultData[] = [
        { id: 'notion1', title: 'Q3 Planning Notes', url: 'http://notion.so/q3planning', content_preview: 'Key points from last sync...' },
      ];
      mockSearchNotionRaw.mockResolvedValue({ ok: true, data: mockNotionPages });

      const mockEmails: Email[] = [
        { id: 'email1', subject: 'Prep for Q3 Sync', sender: 'user1@example.com', recipient: '', body: 'See attached doc', timestamp: new Date().toISOString(), read: false },
      ];
      mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: mockEmails });

      const mockTasks: NotionTask[] = [
        { id: 'task1', description: 'Draft Q3 roadmap', dueDate: '2024-08-01', status: 'In Progress', createdDate: '', url: 'http://notion.so/task1' },
      ];
      mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: mockTasks });

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
      mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: [] });   // No Emails
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
      mockSearchNotionRaw.mockResolvedValue({ ok: false, error: { code: 'NOTION_API_ERROR', message: 'Notion API timeout' } });

      const mockEmails: Email[] = [
        { id: 'email1', subject: 'Prep for Q3 Sync', sender: 'user1@example.com', recipient: '', body: 'See attached doc', timestamp: new Date().toISOString(), read: false },
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

        const manyNotionPages: NotionSearchResultData[] = Array(5).fill(null).map((_, i) => ({ id: `notion${i}`, title: `Page ${i}` }));
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: manyNotionPages });

        const manyEmails: Email[] = Array(5).fill(null).map((_, i) => ({ id: `email${i}`, subject: `Email ${i}`, sender: '', recipient: '', body: '', timestamp: '', read: false }));
        mockSearchEmailsNLU.mockResolvedValue({ ok: true, data: manyEmails });

        const manyTasks: NotionTask[] = Array(5).fill(null).map((_, i) => ({ id: `task${i}`, description: `Task ${i}`, status: 'To Do', createdDate: '', url: '' }));
        mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: manyTasks });


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
      const { startDate, endDate, displayRange, nextPeriodStartDate, nextPeriodEndDate } = determineDateRange("this week");
      // Expected: Mon, Jul 22, 2024 to Wed, Jul 24, 2024
      expect(startDate.getFullYear()).toBe(2024);
      expect(startDate.getMonth()).toBe(6); // July
      expect(startDate.getDate()).toBe(22); // Monday

      expect(endDate.getFullYear()).toBe(2024);
      expect(endDate.getMonth()).toBe(6); // July
      expect(endDate.getDate()).toBe(24); // Wednesday (today)
      expect(endDate.getHours()).toBe(23); // End of day

      expect(displayRange).toContain("This Week (Jul 22 - Jul 24)");

      // Next period starts Jul 25 (Thu) and ends Jul 31 (Wed)
      expect(nextPeriodStartDate.getDate()).toBe(25);
      expect(nextPeriodEndDate.getDate()).toBe(31);
    });

    it('should correctly determine "this week" as Mon-Fri if current day is past Friday 5pm or weekend', () => {
        jest.useFakeTimers().setSystemTime(new Date(2024, 6, 26, 18, 0, 0)); // Friday 6 PM
        const { startDate, endDate, displayRange } = determineDateRange("this week");
        // Expected: Mon, Jul 22, 2024 to Fri, Jul 26, 2024
        expect(startDate.getDate()).toBe(22);
        expect(endDate.getDate()).toBe(26); // Friday
        expect(displayRange).toContain("This Week (Jul 22 - Jul 26)");

        jest.useFakeTimers().setSystemTime(new Date(2024, 6, 27)); // Saturday
        const { startDate: satStart, endDate: satEnd } = determineDateRange("this week");
        expect(satStart.getDate()).toBe(22);
        expect(satEnd.getDate()).toBe(26); // Still shows Mon-Fri
    });


    it('should correctly determine "last week" (Mon to Sun)', () => {
      // Today is Wed, Jul 24, 2024
      const { startDate, endDate, displayRange, nextPeriodStartDate, nextPeriodEndDate } = determineDateRange("last week");
      // Expected: Mon, Jul 15, 2024 to Sun, Jul 21, 2024
      expect(startDate.getFullYear()).toBe(2024);
      expect(startDate.getMonth()).toBe(6);
      expect(startDate.getDate()).toBe(15);

      expect(endDate.getFullYear()).toBe(2024);
      expect(endDate.getMonth()).toBe(6);
      expect(endDate.getDate()).toBe(21);
      expect(endDate.getHours()).toBe(23);
      expect(displayRange).toContain("Last Week (Jul 15 - Jul 21)");

      // Next period starts Jul 22 (Mon) and ends Jul 28 (Sun)
      expect(nextPeriodStartDate.getDate()).toBe(22);
      expect(nextPeriodEndDate.getDate()).toBe(28);
    });

    it('should default to "this week" if no timePeriod is provided', () => {
        const defaultRange = determineDateRange();
        const thisWeekRange = determineDateRange("this week");
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

    const mockCompletedTask: NotionTask = { id: 'ct1', description: 'Finished major report', status: 'Done', createdDate: '2024-07-23T10:00:00Z', last_edited_time: '2024-07-23T10:00:00Z', url: '' };
    const mockAttendedMeeting: CalendarEvent = { id: 'am1', summary: 'Budget Review', startTime: '2024-07-24T14:00:00Z', endTime: '2024-07-24T15:00:00Z' };
    const mockUpcomingTask: NotionTask = { id: 'ut1', description: 'Prepare Q4 Presentation', status: 'To Do', priority: 'High', dueDate: '2024-07-30T10:00:00Z', createdDate: '', url: '' };
    const mockUpcomingMeeting: CalendarEvent = { id: 'um1', summary: 'Client Strategy Session', startTime: '2024-07-29T09:00:00Z', endTime: '2024-07-29T10:30:00Z' };

    it('should generate a digest for "this week" successfully', async () => {
      mockQueryNotionTasks
        .mockImplementationOnce(async (userId, params) => { // Completed tasks
            if(params.status === "Done") return { success: true, tasks: [mockCompletedTask] };
            return { success: true, tasks: [] };
        })
        .mockImplementationOnce(async (userId, params) => { // Upcoming critical tasks
            if(params.priority === "High") return { success: true, tasks: [mockUpcomingTask] };
            return { success: true, tasks: [] };
        });

      mockListUpcomingEvents
        .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => { // Attended meetings
            // Check if timeMin is around July 22-26
            if (timeMin && new Date(timeMin).getDate() >= 22 && new Date(timeMin).getDate() <= 26) {
                 return [mockAttendedMeeting];
            }
            return [];
        })
        .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => { // Upcoming meetings
            // Check if timeMin is around July 27 onwards
            if (timeMin && new Date(timeMin).getDate() >= 27) {
                return [mockUpcomingMeeting];
            }
            return [];
        });

      const response = await handleGenerateWeeklyDigest(mockUserId, "this week");
      expect(response.ok).toBe(true);
      const digest = response.data?.digest;
      expect(digest).toBeDefined();
      expect(digest?.completedTasks).toEqual([mockCompletedTask]);
      expect(digest?.attendedMeetings).toEqual([mockAttendedMeeting]);
      expect(digest?.upcomingCriticalTasks).toEqual([mockUpcomingTask]);
      expect(digest?.upcomingCriticalMeetings).toEqual([mockUpcomingMeeting]);
      expect(digest?.errorMessage).toBeFalsy();
      // Check if periodStart and periodEnd match "this week" based on mocked date
      expect(new Date(digest!.periodStart).getDate()).toBe(22); // Mon, July 22
      expect(new Date(digest!.periodEnd).getDate()).toBe(26);   // Fri, July 26
    });

    it('should generate a digest for "last week"', async () => {
        // Similar setup as above, but adjust mock implementations to return data for "last week" (July 15-21)
        // and "next period" (starting July 22)
        mockQueryNotionTasks
        .mockResolvedValueOnce({ success: true, tasks: [{...mockCompletedTask, id: 'lw_ct1', last_edited_time: '2024-07-18T10:00:00Z'}] }) // Completed last week
        .mockResolvedValueOnce({ success: true, tasks: [{...mockUpcomingTask, id: 'lw_ut1', dueDate: '2024-07-24T10:00:00Z'}] });   // Upcoming this week (relative to last week's digest)

      mockListUpcomingEvents
        .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => { // Attended meetings last week
            if (timeMin && new Date(timeMin).getDate() === 15) { // Mon July 15
                 return [{...mockAttendedMeeting, id: 'lw_am1', startTime: '2024-07-17T14:00:00Z', endTime: '2024-07-17T15:00:00Z'}];
            }
            return [];
        })
        .mockImplementationOnce(async (userId, limit, timeMin, timeMax) => { // Upcoming meetings this week
            if (timeMin && new Date(timeMin).getDate() === 22) { // Mon July 22
                return [{...mockUpcomingMeeting, id: 'lw_um1', startTime: '2024-07-23T09:00:00Z', endTime: '2024-07-23T10:30:00Z'}];
            }
            return [];
        });

        const response = await handleGenerateWeeklyDigest(mockUserId, "last week");
        expect(response.ok).toBe(true);
        const digest = response.data?.digest;
        expect(digest).toBeDefined();
        expect(digest?.completedTasks[0].id).toBe('lw_ct1');
        expect(digest?.attendedMeetings[0].id).toBe('lw_am1');
        expect(digest?.upcomingCriticalTasks[0].id).toBe('lw_ut1');
        expect(digest?.upcomingCriticalMeetings[0].id).toBe('lw_um1');
        // Check period dates for "last week"
        expect(new Date(digest!.periodStart).getDate()).toBe(15); // Mon, July 15
        expect(new Date(digest!.periodEnd).getDate()).toBe(21);   // Sun, July 21
    });

    it('should handle missing ATOM_NOTION_TASKS_DATABASE_ID gracefully', async () => {
        delete process.env.ATOM_NOTION_TASKS_DATABASE_ID;
        // Mocks for calendar will return empty
        mockListUpcomingEvents.mockResolvedValue([]);

        const response = await handleGenerateWeeklyDigest(mockUserId, "this week");
        expect(response.ok).toBe(true);
        const digest = response.data?.digest;
        expect(digest?.completedTasks).toEqual([]);
        expect(digest?.upcomingCriticalTasks).toEqual([]);
        expect(digest?.errorMessage).toContain('Notion tasks database ID not configured');
        process.env.ATOM_NOTION_TASKS_DATABASE_ID = mockNotionTasksDbId; // Reset
    });

    it('should handle errors from underlying services and report them', async () => {
        mockQueryNotionTasks.mockResolvedValueOnce({ success: false, tasks: [], error: 'Notion API error for completed' });
        // other mocks can be default (empty) or also error
        mockListUpcomingEvents.mockRejectedValue(new Error("Calendar service down"));

        const response = await handleGenerateWeeklyDigest(mockUserId, "this week");
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
    let originalLlmUtilities: any;

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
        mockSearchNotionRaw.mockResolvedValue({ok: true, data: []});
        mockQueryNotionTasks.mockResolvedValue({success: true, tasks: []});
        mockAnalyzeTextForFollowUps.mockResolvedValue({ extractedItems: { action_items: [], decisions: [], questions: [] } });
    });

    const mockMeetingContext: CalendarEvent = {
        id: 'meeting123',
        summary: 'Project Phoenix Q1 Review',
        startTime: '2024-07-20T10:00:00Z',
        endTime: '2024-07-20T11:00:00Z',
        description: 'Review of Q1 progress for Project Phoenix.'
    };

    const mockNotionDoc: NotionSearchResultData = {
        id: 'notionDoc1',
        title: 'Project Phoenix Q1 Review Notes',
        content: 'Action Item: Alice to update roadmap. Decision: Q2 budget approved. Question: When is Phase 2 starting?',
        url: 'http://notion.so/phoenixq1notes'
    };

    it('should return CONTEXT_NOT_FOUND if no meeting or project document is found', async () => {
        mockListUpcomingEvents.mockResolvedValue([]); // No meetings found
        mockSearchNotionRaw.mockResolvedValue({ok: true, data: []}); // No notion doc for generic search

        const response = await handleSuggestFollowUps(mockUserId, 'Unknown Context');
        expect(response.ok).toBe(false);
        expect(response.error?.code).toBe('CONTEXT_NOT_FOUND');
    });

    it('should return error if source document is too short for analysis', async () => {
        mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
        mockSearchNotionRaw.mockResolvedValue({ok: true, data: [{...mockNotionDoc, content: "Too short."}] });

        const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
        expect(response.ok).toBe(true); // Skill is "ok" but data contains error
        expect(response.data?.errorMessage).toContain('too short or empty for useful analysis');
        expect(response.data?.suggestions).toEqual([]);
    });

    it('should process meeting context, call LLM, and suggest follow-ups', async () => {
        mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [mockNotionDoc] }); // Notion notes for the meeting
        mockAnalyzeTextForFollowUps.mockResolvedValue({
            extractedItems: {
                action_items: [{ description: 'Alice to update roadmap', assignee: 'Alice' }],
                decisions: [{ description: 'Q2 budget approved' }],
                questions: [{ description: 'When is Phase 2 starting?' }]
            }
        });
        // Assume no existing tasks are found by queryNotionTasks for "Alice to update roadmap"
        mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [] });

        const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
        expect(response.ok).toBe(true);
        expect(mockAnalyzeTextForFollowUps).toHaveBeenCalledWith(mockNotionDoc.content, mockNotionDoc.title);
        expect(response.data?.suggestions).toHaveLength(3);
        expect(response.data?.suggestions.find(s => s.type === 'action_item')?.description).toBe('Alice to update roadmap');
        expect(response.data?.suggestions.find(s => s.type === 'action_item')?.existingTaskFound).toBe(false);
        expect(response.data?.suggestions.find(s => s.type === 'decision')?.description).toBe('Q2 budget approved');
        expect(response.data?.suggestions.find(s => s.type === 'question')?.description).toBe('When is Phase 2 starting?');
        expect(response.data?.contextName).toBe(`Meeting: ${mockNotionDoc.title} on ${new Date(mockMeetingContext.startTime).toLocaleDateString()}`);
    });

    it('should identify an existing task for a suggested action item', async () => {
        mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [mockNotionDoc] });
        mockAnalyzeTextForFollowUps.mockResolvedValue({
            extractedItems: {
                action_items: [{ description: 'Alice to update roadmap', assignee: 'Alice' }],
                decisions: [],
                questions: []
            }
        });
        const existingTask: NotionTask = { id: 'task-roadmap', description: 'Update roadmap for Alice', status: 'To Do', url: 'http://notion/task-roadmap', createdDate: ''};
        mockQueryNotionTasks.mockResolvedValue({ success: true, tasks: [existingTask] }); // Task found

        const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
        expect(response.ok).toBe(true);
        const actionItem = response.data?.suggestions.find(s => s.type === 'action_item');
        expect(actionItem).toBeDefined();
        expect(actionItem?.existingTaskFound).toBe(true);
        expect(actionItem?.existingTaskId).toBe('task-roadmap');
        expect(actionItem?.existingTaskUrl).toBe('http://notion/task-roadmap');
    });

    it('should handle LLM analysis failure gracefully', async () => {
        mockListUpcomingEvents.mockResolvedValue([mockMeetingContext]);
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [mockNotionDoc] });
        mockAnalyzeTextForFollowUps.mockResolvedValue({
            extractedItems: { action_items: [], decisions: [], questions: [] },
            error: "LLM API unavailable"
        });

        const response = await handleSuggestFollowUps(mockUserId, 'Project Phoenix Q1 Review', 'meeting');
        expect(response.ok).toBe(true); // Skill is ok, but data has error
        expect(response.data?.errorMessage).toContain('LLM analysis failed: LLM API unavailable');
        expect(response.data?.suggestions).toEqual([]);
    });

    it('should process project context if specified', async () => {
        const projectNotionDoc: NotionSearchResultData = {
            id: 'projectDoc1',
            title: 'Client Onboarding Project Plan',
            content: 'Action: Schedule kickoff with client. Decision: Use standard template. Question: Who is main PoC?',
            url: 'http://notion.so/clientonboarding'
        };
        mockSearchNotionRaw.mockResolvedValue({ ok: true, data: [projectNotionDoc] }); // Mock for project search
        mockAnalyzeTextForFollowUps.mockResolvedValue({
            extractedItems: {
                action_items: [{ description: 'Schedule kickoff with client' }],
                decisions: [{ description: 'Use standard template' }],
                questions: [{ description: 'Who is main PoC?' }]
            }
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
