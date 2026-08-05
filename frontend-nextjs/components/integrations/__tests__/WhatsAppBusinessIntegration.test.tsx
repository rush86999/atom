/**
 * WhatsAppBusinessIntegration Component Tests
 *
 * Tests verify the real WhatsAppBusinessIntegration component
 * (components/integrations/WhatsAppBusinessIntegration.tsx):
 * - Health check (GET /api/whatsapp/health)
 * - Connected / disconnected states
 * - Analytics overview cards
 * - Conversations list on the default tab
 * - Conversation selection loading messages
 * - Compose message dialog
 * - Sending a message (POST /api/whatsapp/send)
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import WhatsAppBusinessIntegration from '../WhatsAppBusinessIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// Stable useToast mock so handler/toast identities never churn between renders.
const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const conversations = [
  {
    id: '1',
    conversation_id: 'conv_123_20240115',
    whatsapp_id: '+1234567890',
    status: 'active',
    last_message_at: '2024-01-15T10:30:00Z',
    name: 'John Doe',
    phone_number: '+1234567890',
    message_count: 5,
  },
  {
    id: '2',
    conversation_id: 'conv_456_20240115',
    whatsapp_id: '+9876543210',
    status: 'active',
    last_message_at: '2024-01-15T09:45:00Z',
    name: 'Jane Smith',
    phone_number: '+9876543210',
    message_count: 3,
  },
];

const messages = [
  {
    id: '1',
    message_id: 'msg_123',
    whatsapp_id: '+1234567890',
    message_type: 'text',
    content: { body: 'Hello, I need help with my order' },
    direction: 'inbound',
    status: 'received',
    timestamp: '2024-01-15T10:30:00Z',
  },
  {
    id: '2',
    message_id: 'msg_124',
    whatsapp_id: '+1234567890',
    message_type: 'text',
    content: { body: 'I\'d be happy to help you with your order!' },
    direction: 'outbound',
    status: 'sent',
    timestamp: '2024-01-15T10:31:00Z',
  },
];

const analytics = {
  message_statistics: [
    { direction: 'inbound', message_type: 'text', status: 'received', count: 25 },
    { direction: 'outbound', message_type: 'text', status: 'sent', count: 20 },
  ],
  conversation_statistics: {
    total_conversations: 50,
    active_conversations: 12,
  },
  contact_growth: [{ date: '2024-01-15', new_contacts: 3 }],
};

const whatsappHandlers = [
  rest.get('/api/whatsapp/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.get('/api/whatsapp/conversations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, conversations }));
  }),

  rest.get('/api/whatsapp/messages/:whatsappId', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, messages }));
  }),

  rest.get('/api/whatsapp/analytics', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, analytics }));
  }),

  rest.post('/api/whatsapp/send', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, message_id: 'msg_new_123' }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/whatsapp/health', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ status: 'not_configured' }));
    })
  );
};

// Icon-only buttons (e.g. the send button in the Messages tab) have no text.
const getIconButtons = () =>
  screen
    .getAllByRole('button')
    .filter((b) => b.querySelector('svg') && !(b.textContent || '').trim());

describe('WhatsAppBusinessIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...whatsappHandlers);
  });

  // Test 1: renders the component header
  test('renders WhatsApp Business integration component', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /whatsapp business integration/i })
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /Manage customer communications through WhatsApp Business API/i
        )
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows Connected status when health check passes
  test('displays connection status correctly', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 3: shows analytics overview cards when connected
  test('displays analytics overview when connected', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Total Conversations')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument();
      expect(screen.getByText('Active Conversations')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('Messages Sent Today')).toBeInTheDocument();
      expect(screen.getByText('20')).toBeInTheDocument();
      expect(screen.getByText('Messages Received Today')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    });
  });

  // Test 4: displays conversations on the default tab
  test('displays conversations in conversations tab', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getByText('+1234567890')).toBeInTheDocument();
      expect(screen.getByText('+9876543210')).toBeInTheDocument();
    });
  });

  // Test 5: opens the compose message dialog
  test('opens compose message modal', async () => {
    render(<WhatsAppBusinessIntegration />);

    const composeButton = await screen.findByRole('button', {
      name: /new message/i,
    });
    fireEvent.click(composeButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /compose new message/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Recipient Phone Number')).toBeInTheDocument();
      expect(screen.getByText('Message Type')).toBeInTheDocument();
      expect(screen.getByText('Message Content')).toBeInTheDocument();
    });
  });

  // Test 6: displays the three tabs
  test('displays tabs correctly', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Conversations' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Messages' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Analytics' })).toBeInTheDocument();
    });
  });

  // Test 7: selecting a conversation loads and shows messages
  test('selecting a conversation loads messages', async () => {
    render(<WhatsAppBusinessIntegration />);

    await screen.findByText('John Doe');
    fireEvent.click(screen.getByText('John Doe'));
    fireEvent.click(screen.getByRole('button', { name: 'Messages' }));

    await waitFor(() => {
      expect(
        screen.getByText(/Messages with John Doe/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText('Hello, I need help with my order')
      ).toBeInTheDocument();
      expect(
        screen.getByText('I\'d be happy to help you with your order!')
      ).toBeInTheDocument();
    });
  });

  // Test 8: shows disconnected state when health check reports not configured
  test('handles disconnected state correctly', async () => {
    setDisconnected();

    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
      expect(screen.getByText('WhatsApp Not Connected')).toBeInTheDocument();
      expect(
        screen.getByText(
          /Please configure your WhatsApp Business API settings/i
        )
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /connect with meta/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: sending a message posts to /api/whatsapp/send
  test('sends a message via the Messages tab', async () => {
    let sendBody: any = null;
    server.use(
      rest.post('/api/whatsapp/send', (req, res, ctx) => {
        sendBody = req.body as any;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<WhatsAppBusinessIntegration />);

    await screen.findByText('John Doe');
    fireEvent.click(screen.getByText('John Doe'));
    fireEvent.click(screen.getByRole('button', { name: 'Messages' }));

    await screen.findByText('Hello, I need help with my order');

    const input = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(input, { target: { value: 'Thanks!' } });

    fireEvent.click(getIconButtons()[0]);

    await waitFor(() => {
      expect(sendBody).toEqual(
        expect.objectContaining({
          to: '+1234567890',
          type: 'text',
          content: { body: 'Thanks!' },
        })
      );
    });
  });

  // Test 10: handles API errors gracefully (still renders header when downstream fails)
  test('handles API errors gracefully', async () => {
    server.use(
      rest.get('/api/whatsapp/conversations', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      }),
      rest.get('/api/whatsapp/analytics', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /whatsapp business integration/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 11: shows the Configure button
  test('shows the Configure button', async () => {
    render(<WhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /configure/i })
      ).toBeInTheDocument();
    });
  });
});
