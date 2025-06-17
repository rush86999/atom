import { listUpcomingEvents, createCalendarEvent, CalendarEvent, CreateEventResponse } from './calendarSkills'; // Adjust import if types are from '../types'

// If types are indeed from '../types', the import would look like:
// import { listUpcomingEvents, createCalendarEvent } from './calendarSkills';
// import { CalendarEvent, CreateEventResponse } from '../types';
// For this test, assuming types are co-located or exported from calendarSkills.ts for simplicity of the skill file itself.
// However, the main handler.test.ts correctly assumes they are in ../types.
// Let's stick to the established pattern: types are in ../types.ts
// Therefore, the first line should be:
// import { listUpcomingEvents, createCalendarEvent } from './calendarSkills';
// import { CalendarEvent, CreateEventResponse } from '../types';
// Correcting the import based on prior setup:
import * as calendarSkills from './calendarSkills';
import { CalendarEvent, CreateEventResponse } from '../types';


describe('Calendar Skills', () => {
  describe('listUpcomingEvents', () => {
    it('should return an array of calendar events', async () => {
      const events = await calendarSkills.listUpcomingEvents();
      expect(Array.isArray(events)).toBe(true);
      if (events.length > 0) {
        expect(events[0]).toHaveProperty('id');
        expect(events[0]).toHaveProperty('summary');
        expect(events[0]).toHaveProperty('startTime');
        expect(events[0]).toHaveProperty('endTime');
      }
    });

    it('should limit the number of events returned', async () => {
      const limitedEvents = await calendarSkills.listUpcomingEvents(1);
      expect(limitedEvents.length).toBeLessThanOrEqual(1);
      // Check against the mock data used in calendarSkills.ts
      const fullMockEvents = [
        { id: 'event1', summary: 'Team Meeting', startTime: '2024-03-15T10:00:00Z', endTime: '2024-03-15T11:00:00Z', description: 'Weekly sync-up' },
        { id: 'event2', summary: 'Project Deadline', startTime: '2024-03-15T17:00:00Z', endTime: '2024-03-15T17:00:00Z', description: 'Final submission for Project X' },
        { id: 'event3', summary: 'Lunch with Client', startTime: '2024-03-16T12:30:00Z', endTime: '2024-03-16T13:30:00Z' },
      ];
      expect(await calendarSkills.listUpcomingEvents(0)).toHaveLength(0);
      expect(await calendarSkills.listUpcomingEvents(1)).toHaveLength(1);
      expect(await calendarSkills.listUpcomingEvents(2)).toHaveLength(2);
      expect(await calendarSkills.listUpcomingEvents(3)).toHaveLength(3);
      expect(await calendarSkills.listUpcomingEvents(4)).toHaveLength(3); // Max of mock data
    });
  });

  describe('createCalendarEvent', () => {
    it('should return a success response for valid event details', async () => {
      const eventDetails: Partial<CalendarEvent> = {
        summary: 'New Test Event',
        startTime: '2024-03-25T10:00:00Z',
        endTime: '2024-03-25T11:00:00Z',
      };
      const response = await calendarSkills.createCalendarEvent(eventDetails);
      expect(response.success).toBe(true);
      expect(response.eventId).toBeDefined();
      expect(response.message).toContain('Calendar event created successfully (mock).');
    });

    it('should return a failure response if required details are missing', async () => {
      const eventDetails: Partial<CalendarEvent> = { summary: 'Missing times' };
      const response = await calendarSkills.createCalendarEvent(eventDetails);
      expect(response.success).toBe(false);
      expect(response.eventId).toBeUndefined();
      expect(response.message).toContain('Missing required event details');
    });
  });
});
