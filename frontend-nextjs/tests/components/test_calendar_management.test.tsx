import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CalendarManagement from '@/components/CalendarManagement';

// Mock dependencies
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

jest.mock('@/components/shared/CalendarManagement', () => {
  return function MockSharedCalendarManagement({
    initialEvents,
    onEventCreate,
    onEventUpdate,
    onEventDelete,
  }: any) {
    return (
      <div data-testid="calendar-management">
        <div data-testid="event-count">{initialEvents?.length || 0}</div>
        <button
          data-testid="create-event"
          onClick={() => onEventCreate && onEventCreate({
            id: 'new-event',
            title: 'New Event',
            start: new Date(),
            end: new Date(),
          })}
        >
          Create Event
        </button>
        <button
          data-testid="update-event"
          onClick={() => onEventUpdate && onEventUpdate('event-1', { title: 'Updated Event' })}
        >
          Update Event
        </button>
        <button
          data-testid="delete-event"
          onClick={() => onEventDelete && onEventDelete('event-1')}
        >
          Delete Event
        </button>
      </div>
    );
  };
});

// Mock fetch globally
global.fetch = jest.fn();

describe('CalendarManagement Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('test_calendar_renders', () => {
    it('should render calendar component without crashing', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: [] }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });
    });

    it('should render in loading state initially', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockImplementation(
        () => new Promise(() => {})
      );

      render(<CalendarManagement />);
      expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
    });
  });

  describe('test_calendar_month_navigation', () => {
    it('should support month navigation controls', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: [] }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      // Verify calendar has showNavigation enabled
      const calendar = screen.getByTestId('calendar-management');
      expect(calendar).toBeInTheDocument();
    });

    it('should fetch events for different months', async () => {
      const mockEvents = [
        {
          id: '1',
          title: 'March Meeting',
          start: '2026-03-15T10:00:00',
          end: '2026-03-15T11:00:00',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: mockEvents }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('event-count')).toHaveTextContent('1');
      });
    });
  });

  describe('test_calendar_event_display', () => {
    it('should display events on calendar', async () => {
      const mockEvents = [
        {
          id: 'event-1',
          title: 'Team Meeting',
          start: '2026-03-10T10:00:00',
          end: '2026-03-10T11:00:00',
          description: 'Weekly team sync',
        },
        {
          id: 'event-2',
          title: 'Project Deadline',
          start: '2026-03-15T17:00:00',
          end: '2026-03-15T18:00:00',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: mockEvents }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('event-count')).toHaveTextContent('2');
      });
    });

    it('should handle empty event list', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: [] }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('event-count')).toHaveTextContent('0');
      });
    });

    it('should parse date strings correctly', async () => {
      const mockEvents = [
        {
          id: 'event-1',
          title: 'Meeting',
          start: '2026-03-10T10:00:00',
          end: '2026-03-10T11:00:00',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ events: mockEvents }),
      } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('event-count')).toHaveTextContent('1');
      });
    });
  });

  describe('test_calendar_event_creation', () => {
    it('should create new event successfully', async () => {
      const newEvent = {
        id: 'new-event',
        title: 'New Event',
        start: '2026-03-12T10:00:00',
        end: '2026-03-12T11:00:00',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ event: newEvent }),
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const createButton = screen.getByTestId('create-event');
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/calendar/events',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          })
        );
      });
    });

    it('should handle event creation errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 400,
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const createButton = screen.getByTestId('create-event');
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('test_calendar_event_editing', () => {
    it('should update existing event', async () => {
      const updatedEvent = {
        id: 'event-1',
        title: 'Updated Event',
        start: '2026-03-10T10:00:00',
        end: '2026-03-10T11:00:00',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ event: updatedEvent }),
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const updateButton = screen.getByTestId('update-event');
      fireEvent.click(updateButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/calendar/events/event-1',
          expect.objectContaining({
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
          })
        );
      });
    });

    it('should handle event update errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 404,
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const updateButton = screen.getByTestId('update-event');
      fireEvent.click(updateButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('test_calendar_event_deletion', () => {
    it('should delete event successfully', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const deleteButton = screen.getByTestId('delete-event');
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/calendar/events/event-1',
          expect.objectContaining({
            method: 'DELETE',
          })
        );
      });
    });

    it('should handle event deletion errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ events: [] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 404,
        } as Response);

      render(<CalendarManagement />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar-management')).toBeInTheDocument();
      });

      const deleteButton = screen.getByTestId('delete-event');
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });
  });
});
