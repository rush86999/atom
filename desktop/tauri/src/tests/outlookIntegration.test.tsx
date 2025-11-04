/**
 * Integration Tests for Outlook Skills
 * End-to-end testing of Outlook automation workflows
 */

import { EnhancedChat } from '../EnhancedChat';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { invoke } from '@tauri-apps/api/tauri';

// Mock Tauri invoke
jest.mock('@tauri-apps/api/tauri', () => ({
  invoke: jest.fn()
}));

const mockInvoke = invoke as jest.MockedFunction<typeof invoke>;

// Mock console methods to avoid test noise
global.console = {
  ...console,
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn()
};

describe('Outlook Integration - End-to-End Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock initial connection status
    mockInvoke.mockResolvedValue({
      valid: true,
      expired: false,
      message: 'Tokens valid'
    });
  });

  describe('Email Automation Workflow', () => {
    it('should complete full email send workflow', async () => {
      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Mock successful email send
      mockInvoke.mockResolvedValue({
        success: true,
        message: 'Email sent successfully',
        emailId: 'email-123'
      });

      // Type and send email command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Send an email to john@example.com with subject 'Test Email' and message 'This is a test'");
      
      await user.click(screen.getByText('Send'));

      // Wait for skill execution
      await waitFor(() => {
        expect(screen.getByText(/Email sent successfully/)).toBeInTheDocument();
      });

      // Verify the Tauri command was called
      expect(mockInvoke).toHaveBeenCalledWith('send_outlook_email', {
        userId: 'desktop-user',
        to: ['john@example.com'],
        subject: 'Test Email',
        body: 'This is a test',
        cc: undefined,
        bcc: undefined
      });
    });

    it('should handle email triage workflow', async () => {
      // Mock unread emails for triage
      const mockEmails = [
        {
          id: '1',
          subject: 'URGENT: Server Down',
          from: { name: 'IT Support', address: 'it@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Server is down, immediate attention required',
          receivedDateTime: '2025-11-02T10:00:00Z',
          isRead: false,
          importance: 'high'
        },
        {
          id: '2',
          subject: 'Team Meeting Tomorrow',
          from: { name: 'Manager', address: 'manager@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Reminder about tomorrow\'s meeting',
          receivedDateTime: '2025-11-02T09:00:00Z',
          isRead: false,
          importance: 'normal'
        }
      ];

      mockInvoke.mockResolvedValue(mockEmails);

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type triage command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Triage my emails by priority");
      await user.click(screen.getByText('Send'));

      // Wait for triage completion
      await waitFor(() => {
        expect(screen.getByText(/Email triage complete/)).toBeInTheDocument();
      });

      // Should show triage summary
      expect(screen.getByText(/Total emails: 2/)).toBeInTheDocument();
      expect(screen.getByText(/High priority: 1/)).toBeInTheDocument();
      expect(screen.getByText(/Requires action: 2/)).toBeInTheDocument();
    });

    it('should search emails and display results', async () => {
      // Mock search results
      const mockSearchResults = [
        {
          id: '1',
          subject: 'Project Update - Q4',
          from: { name: 'Project Lead', address: 'lead@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Q4 project progress update',
          receivedDateTime: '2025-11-01T15:00:00Z',
          isRead: true,
          importance: 'normal'
        }
      ];

      mockInvoke.mockResolvedValue(mockSearchResults);

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type search command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Search emails for 'project update'");
      await user.click(screen.getByText('Send'));

      // Wait for search results
      await waitFor(() => {
        expect(screen.getByText(/Found 1 emails matching/)).toBeInTheDocument();
      });

      expect(screen.getByText(/Project Update - Q4/)).toBeInTheDocument();
      expect(screen.getByText(/Project Lead/)).toBeInTheDocument();
    });
  });

  describe('Calendar Automation Workflow', () => {
    it('should complete calendar event creation workflow', async () => {
      // Mock successful event creation
      mockInvoke.mockResolvedValue({
        success: true,
        message: 'Calendar event created successfully',
        eventId: 'event-123'
      });

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type event creation command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Create a calendar event 'Team Meeting' tomorrow at 2 PM in Conference Room A");
      await user.click(screen.getByText('Send'));

      // Wait for event creation confirmation
      await waitFor(() => {
        expect(screen.getByText(/Calendar event \"Team Meeting\" created successfully/)).toBeInTheDocument();
      });

      // Verify the Tauri command was called
      expect(mockInvoke).toHaveBeenCalledWith('create_outlook_calendar_event', {
        userId: 'desktop-user',
        subject: 'Team Meeting',
        start_time: expect.stringContaining('2 PM'),
        end_time: '',
        body: undefined,
        location: 'Conference Room A',
        attendees: undefined
      });
    });

    it('should display calendar events', async () => {
      // Mock calendar events
      const mockEvents = [
        {
          id: '1',
          subject: 'Team Standup',
          start: { dateTime: '2025-11-03T09:00:00', timeZone: 'UTC' },
          end: { dateTime: '2025-11-03T09:30:00', timeZone: 'UTC' },
          location: { displayName: 'Virtual' },
          body: { content: 'Daily team standup', contentType: 'text' }
        },
        {
          id: '2',
          subject: 'Client Call',
          start: { dateTime: '2025-11-03T14:00:00', timeZone: 'UTC' },
          end: { dateTime: '2025-11-03T15:00:00', timeZone: 'UTC' },
          location: { displayName: 'Client Office' }
        }
      ];

      mockInvoke.mockResolvedValue(mockEvents);

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type get events command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Show me my upcoming events");
      await user.click(screen.getByText('Send'));

      // Wait for events display
      await waitFor(() => {
        expect(screen.getByText(/Your upcoming events:/)).toBeInTheDocument();
      });

      expect(screen.getByText(/Team Standup at/)).toBeInTheDocument();
      expect(screen.getByText(/Client Call at/)).toBeInTheDocument();
    });

    it('should search calendar events', async () => {
      // Mock search results
      const mockSearchResults = [
        {
          id: '1',
          subject: 'Client Project Review',
          start: { dateTime: '2025-11-05T10:00:00', timeZone: 'UTC' },
          end: { dateTime: '2025-11-05T11:30:00', timeZone: 'UTC' },
          location: { displayName: 'Client Office' }
        }
      ];

      mockInvoke.mockResolvedValue(mockSearchResults);

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type search command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Search calendar for 'client meeting'");
      await user.click(screen.getByText('Send'));

      // Wait for search results
      await waitFor(() => {
        expect(screen.getByText(/Found 1 events matching/)).toBeInTheDocument();
      });

      expect(screen.getByText(/Client Project Review/)).toBeInTheDocument();
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle Outlook disconnected state', async () => {
      // Mock disconnected state
      mockInvoke.mockResolvedValue({
        valid: false,
        expired: true,
        message: 'No valid tokens'
      });

      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Should show disconnected status
      expect(screen.getByText(/Outlook Disconnected/)).toBeInTheDocument();
      expect(screen.getByText(/Connect your Outlook account in Settings first/)).toBeInTheDocument();

      // Try to send email
      const input = screen.getByPlaceholderText(/Connect Outlook in Settings to use email/);
      expect(input).toBeDisabled();
    });

    it('should handle API errors gracefully', async () => {
      // Mock API error
      mockInvoke.mockRejectedValue(new Error('API Error: Failed to send email'));

      render(<EnhancedChat />);
      const user = userEvent.setup();

      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Send an email to test@example.com");
      await user.click(screen.getByText('Send'));

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(/Sorry, I encountered an error processing your request/)).toBeInTheDocument();
      });
    });

    it('should handle validation errors', async () => {
      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Try to send email without required parameters
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Send an email");
      await user.click(screen.getByText('Send'));

      // Wait for validation message
      await waitFor(() => {
        expect(screen.getByText(/I need recipient\(s\), subject, and message content to send an email/)).toBeInTheDocument();
      });
    });

    it('should provide help information', async () => {
      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Type help command
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Outlook help");
      await user.click(screen.getByText('Send'));

      // Wait for help message
      await waitFor(() => {
        expect(screen.getByText(/Outlook Help/)).toBeInTheDocument();
        expect(screen.getByText(/Email Management:/)).toBeInTheDocument();
        expect(screen.getByText(/Calendar Management:/)).toBeInTheDocument();
      });
    });
  });

  describe('UI Interactions', () => {
    it('should use quick action buttons', async () => {
      render(<EnhancedChat />);
      const user = userEvent.setup();

      // Mock get emails
      mockInvoke.mockResolvedValue([
        {
          id: '1',
          subject: 'Test Email',
          from: { name: 'Test', address: 'test@example.com' },
          to: [{ name: 'User', address: 'user@example.com' }],
          body: 'Test email body',
          receivedDateTime: '2025-11-02T10:00:00Z',
          isRead: false,
          importance: 'normal'
        }
      ]);

      // Click quick action button
      const quickAction = screen.getByText('📧 Recent Emails');
      await user.click(quickAction);

      // Should populate input
      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      expect(input).toHaveValue('Show me my recent emails');

      // Auto-send the command
      await user.click(screen.getByText('Send'));

      // Wait for results
      await waitFor(() => {
        expect(screen.getByText(/Found 1 emails:/)).toBeInTheDocument();
      });
    });

    it('should show typing indicator during processing', async () => {
      // Mock slow response
      mockInvoke.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          success: true,
          emailId: 'email-123'
        }), 1000))
      );

      render(<EnhancedChat />);
      const user = userEvent.setup();

      const input = screen.getByPlaceholderText(/Ask me to send emails/);
      await user.type(input, "Send an email to test@example.com with subject 'Test' and message 'Test'");
      await user.click(screen.getByText('Send'));

      // Should show typing indicator
      expect(screen.getByText(/🤔 Processing your request.../)).toBeInTheDocument();
    });
  });
});