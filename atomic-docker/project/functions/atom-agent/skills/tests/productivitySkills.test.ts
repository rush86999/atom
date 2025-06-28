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
});
