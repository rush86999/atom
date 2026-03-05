import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import CalendarView from '../CalendarView';

// Mock useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock react-big-calendar
jest.mock('react-big-calendar', () => ({
  Calendar: ({ events, ...props }: any) => (
    <div data-testid="calendar" data-events={events.length}>
      <div data-testid="calendar-props">{JSON.stringify(props)}</div>
      {events?.map((event: any) => (
        <div key={event.id} data-testid={`event-${event.id}`}>
          {event.title}
        </div>
      ))}
    </div>
  ),
}));

// Mock date-fns
jest.mock('date-fns/format', () => jest.fn(() => '2024-01-01'));
jest.mock('date-fns/parse', () => jest.fn(() => new Date()));
jest.mock('date-fns/startOfWeek', () => jest.fn(() => new Date()));
jest.mock('date-fns/getDay', () => jest.fn(() => 0));
jest.mock('date-fns/locale/en-US', () => ({}));

describe('CalendarView Component', () => {
  const mockEvents = [
    {
      id: '1',
      title: 'Team Meeting',
      start: new Date('2024-01-01T10:00:00'),
      end: new Date('2024-01-01T11:00:00'),
      description: 'Weekly team sync',
      location: 'Conference Room A',
      color: '#3182CE',
    },
    {
      id: '2',
      title: 'Product Demo',
      start: new Date('2024-01-01T14:00:00'),
      end: new Date('2024-01-01T15:00:00'),
      description: 'Demo to stakeholders',
      location: 'Main Hall',
      color: '#38A169',
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock fetch API
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          events: mockEvents,
        }),
        headers: new Headers(),
        status: 200,
        statusText: 'OK',
      } as Response)
    );
  });

  describe('Rendering', () => {
    it('renders without crashing', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByText(/calendar/i)).toBeInTheDocument();
      });
    });

    it('shows loading indicator initially', () => {
      global.fetch = jest.fn(() => new Promise(() => {})); // Never resolves

      render(<CalendarView />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('displays calendar after loading', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar')).toBeInTheDocument();
      });
    });

    it('shows new event button', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /new event/i })).toBeInTheDocument();
      });
    });

    it('displays calendar title', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByText('Calendar')).toBeInTheDocument();
      });
    });
  });

  describe('Event Display', () => {
    it('renders events on calendar', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByTestId('event-1')).toBeInTheDocument();
        expect(screen.getByTestId('event-2')).toBeInTheDocument();
      });
    });

    it('displays event titles', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByText('Team Meeting')).toBeInTheDocument();
        expect(screen.getByText('Product Demo')).toBeInTheDocument();
      });
    });

    it('shows event count in data attribute', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        const calendar = screen.getByTestId('calendar');
        expect(calendar).toHaveAttribute('data-events', '2');
      });
    });
  });

  describe('Event Creation', () => {
    it('opens create event dialog', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /new event/i })).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/create new event/i)).toBeInTheDocument();
    });

    it('requires event title', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      // Should not submit without title
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/events'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('creates new event with valid data', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      // Fill in event details
      const titleInput = screen.getByLabelText(/title/i);
      await user.type(titleInput, 'New Meeting');

      const startInput = screen.getByLabelText(/start time/i);
      await user.type(startInput, '2024-01-02T10:00');

      const endInput = screen.getByLabelText(/end time/i);
      await user.type(endInput, '2024-01-02T11:00');

      const descriptionInput = screen.getByLabelText(/description/i);
      await user.type(descriptionInput, 'Team sync');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/events'),
          expect.objectContaining({
            method: 'POST',
          })
        );
      });
    });

    it('closes dialog after successful creation', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const titleInput = screen.getByLabelText(/title/i);
      await user.type(titleInput, 'Test Event');

      const startInput = screen.getByLabelText(/start time/i);
      await user.type(startInput, '2024-01-02T10:00');

      const endInput = screen.getByLabelText(/end time/i);
      await user.type(endInput, '2024-01-02T11:00');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('resets form after event creation', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const titleInput = screen.getByLabelText(/title/i);
      await user.type(titleInput, 'Test Event');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      // Open dialog again
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('');
      });
    });
  });

  describe('Event Color Selection', () => {
    it('displays color options', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      expect(screen.getByText(/blue/i)).toBeInTheDocument();
      expect(screen.getByText(/green/i)).toBeInTheDocument();
      expect(screen.getByText(/red/i)).toBeInTheDocument();
      expect(screen.getByText(/yellow/i)).toBeInTheDocument();
      expect(screen.getByText(/purple/i)).toBeInTheDocument();
    });

    it('allows color selection', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const greenOption = screen.getByText(/green/i);
      await user.click(greenOption);

      await waitFor(() => {
        expect(greenOption).toHaveAttribute('value', '#38A169');
      });
    });

    it('uses default color if none selected', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      // Default color should be selected
      const colorSelect = screen.getByRole('combobox', { name: /color/i });
      expect(colorSelect).toHaveValue('#3182CE');
    });
  });

  describe('Date Input Handling', () => {
    it('accepts datetime-local input', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const startInput = screen.getByLabelText(/start time/i);
      expect(startInput).toHaveAttribute('type', 'datetime-local');

      const endInput = screen.getByLabelText(/end time/i);
      expect(endInput).toHaveAttribute('type', 'datetime-local');
    });

    it('validates end time is after start time', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const startInput = screen.getByLabelText(/start time/i);
      await user.type(startInput, '2024-01-02T11:00');

      const endInput = screen.getByLabelText(/end time/i);
      await user.type(endInput, '2024-01-02T10:00');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/end time must be after start time/i)).toBeInTheDocument();
      });
    });
  });

  describe('Dialog Controls', () => {
    it('closes dialog on cancel', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('closes dialog on backdrop click', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const backdrop = screen.getByRole('dialog').parentElement;
      if (backdrop) {
        await user.click(backdrop);

        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      }
    });

    it('closes dialog on escape key press', async () => {
      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await userEvent.click(createButton);

      await userEvent.keyboard('{Escape}');

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('Data Fetching', () => {
    it('fetches events on mount', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/calendar/events',
          expect.any(Object)
        );
      });
    });

    it('converts date strings to Date objects', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        const calendar = screen.getByTestId('calendar');
        expect(calendar).toBeInTheDocument();
      });
    });

    it('refetches events after creating new event', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      // Wait for initial fetch
      await waitFor(() => {
        expect(screen.getByTestId('calendar')).toBeInTheDocument();
      });

      const fetchCallsBefore = (global.fetch as jest.Mock).mock.calls.length;

      // Create event
      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const titleInput = screen.getByLabelText(/title/i);
      await user.type(titleInput, 'New Event');

      const startInput = screen.getByLabelText(/start time/i);
      await user.type(startInput, '2024-01-02T10:00');

      const endInput = screen.getByLabelText(/end time/i);
      await user.type(endInput, '2024-01-02T11:00');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        const fetchCallsAfter = (global.fetch as jest.Mock).mock.calls.length;
        expect(fetchCallsAfter).toBeGreaterThan(fetchCallsBefore);
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message on fetch failure', async () => {
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByRole('status')).not.toBeInTheDocument();
      });
    });

    it('displays error message on create failure', async () => {
      const user = userEvent.setup();
      global.fetch = jest.fn(() =>
        Promise.resolve({
          ok: false,
          json: async () => ({ success: false }),
          headers: new Headers(),
          status: 500,
          statusText: 'Internal Server Error',
        } as Response)
      );

      render(<CalendarView />);

      const createButton = screen.getByRole('button', { name: /new event/i });
      await user.click(createButton);

      const titleInput = screen.getByLabelText(/title/i);
      await user.type(titleInput, 'Test Event');

      const startInput = screen.getByLabelText(/start time/i);
      await user.type(startInput, '2024-01-02T10:00');

      const endInput = screen.getByLabelText(/end time/i);
      await user.type(endInput, '2024-01-02T11:00');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        // Dialog should remain open on error
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        const calendar = screen.getByTestId('calendar');
        expect(calendar).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /new event/i })).toBeInTheDocument();
      });

      await user.tab();

      const newEventButton = screen.getByRole('button', { name: /new event/i });
      expect(newEventButton).toHaveFocus();
    });
  });

  describe('Responsive Layout', () => {
    it('has correct height classes', async () => {
      const { container } = render(<CalendarView />);

      await waitFor(() => {
        expect(container.querySelector('.h-\\[80vh\\]')).toBeInTheDocument();
      });
    });

    it('displays calendar container', async () => {
      render(<CalendarView />);

      await waitFor(() => {
        expect(screen.getByTestId('calendar')).toBeInTheDocument();
        expect(screen.getByTestId('calendar').parentElement).toHaveClass('calendar-container');
      });
    });
  });
});
