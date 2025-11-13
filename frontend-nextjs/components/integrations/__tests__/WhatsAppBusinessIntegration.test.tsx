/**
 * WhatsApp Business Integration Tests
 * 
 * Comprehensive test suite for WhatsApp Business integration functionality
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import { ThemeProvider } from '@emotion/react';
import WhatsAppBusinessIntegration from '../components/integrations/WhatsAppBusinessIntegration';

// Mock fetch API
global.fetch = jest.fn();

// Test data
const mockConversations = [
  {
    id: '1',
    conversation_id: 'conv_123_20240115',
    whatsapp_id: '+1234567890',
    status: 'active',
    last_message_at: '2024-01-15T10:30:00Z',
    name: 'John Doe',
    phone_number: '+1234567890',
    message_count: 5,
    last_message_time: '2024-01-15T10:30:00Z'
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
    last_message_time: '2024-01-15T09:45:00Z'
  }
];

const mockMessages = [
  {
    id: '1',
    message_id: 'msg_123',
    whatsapp_id: '+1234567890',
    message_type: 'text',
    content: { body: 'Hello, I need help with my order' },
    direction: 'inbound',
    status: 'received',
    timestamp: '2024-01-15T10:30:00Z'
  },
  {
    id: '2',
    message_id: 'msg_124',
    whatsapp_id: '+1234567890',
    message_type: 'text',
    content: { body: 'I\'d be happy to help you with your order!' },
    direction: 'outbound',
    status: 'sent',
    timestamp: '2024-01-15T10:31:00Z'
  }
];

const mockAnalytics = {
  message_statistics: [
    {
      direction: 'inbound',
      message_type: 'text',
      status: 'received',
      count: 25
    },
    {
      direction: 'outbound',
      message_type: 'text',
      status: 'sent',
      count: 20
    }
  ],
  conversation_statistics: {
    total_conversations: 50,
    active_conversations: 12
  },
  contact_growth: [
    {
      date: '2024-01-15',
      new_contacts: 3
    }
  ]
};

// Helper function to render component with providers
const renderComponent = () => {
  return render(
    <ChakraProvider>
      <ThemeProvider theme={{}}>
        <WhatsAppBusinessIntegration />
      </ThemeProvider>
    </ChakraProvider>
  );
};

describe('WhatsAppBusinessIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock successful health check
    (fetch as jest.Mock).mockImplementation((url) => {
      if (url === '/api/whatsapp/health') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'healthy',
            service: 'WhatsApp Business API',
            timestamp: new Date().toISOString()
          })
        });
      }
      
      if (url === '/api/whatsapp/conversations') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            conversations: mockConversations
          })
        });
      }
      
      if (url.startsWith('/api/whatsapp/messages/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            messages: mockMessages
          })
        });
      }
      
      if (url === '/api/whatsapp/analytics') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            analytics: mockAnalytics
          })
        });
      }
      
      if (url === '/api/whatsapp/send') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            message_id: 'msg_new_123',
            status: 'sent'
          })
        });
      }
      
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: 'Not found' })
      });
    });
  });

  test('renders WhatsApp Business integration component', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('WhatsApp Business Integration')).toBeInTheDocument();
      expect(screen.getByText('Manage customer communications through WhatsApp Business API')).toBeInTheDocument();
    });
  });

  test('displays connection status correctly', async () => {
    renderComponent();
    
    await waitFor(() => {
      const statusBadge = screen.getByText('Connected');
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveClass('chakra-badge');
    });
  });

  test('displays analytics overview when connected', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Analytics Overview')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument(); // Total conversations
      expect(screen.getByText('12')).toBeInTheDocument(); // Active conversations
    });
  });

  test('displays conversations in conversations tab', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
    });
    
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getByText('+1234567890')).toBeInTheDocument();
      expect(screen.getByText('+9876543210')).toBeInTheDocument();
    });
  });

  test('opens compose message modal', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument();
    });
    
    const composeButton = screen.getByText('New Message');
    fireEvent.click(composeButton);
    
    await waitFor(() => {
      expect(screen.getByText('Compose New Message')).toBeInTheDocument();
      expect(screen.getByText('Recipient Phone Number')).toBeInTheDocument();
      expect(screen.getByText('Message Type')).toBeInTheDocument();
      expect(screen.getByText('Message Content')).toBeInTheDocument();
    });
  });

  test('opens configuration modal', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Configure')).toBeInTheDocument();
    });
    
    const configButton = screen.getByText('Configure');
    fireEvent.click(configButton);
    
    await waitFor(() => {
      expect(screen.getByText('WhatsApp Business Configuration')).toBeInTheDocument();
      expect(screen.getByText('Access Token')).toBeInTheDocument();
      expect(screen.getByText('Phone Number ID')).toBeInTheDocument();
      expect(screen.getByText('Webhook Verify Token')).toBeInTheDocument();
    });
  });

  test('sends a message successfully', async () => {
    renderComponent();
    
    // Open compose modal
    await waitFor(() => {
      const composeButton = screen.getByText('New Message');
      fireEvent.click(composeButton);
    });
    
    await waitFor(() => {
      expect(screen.getByText('Recipient Phone Number')).toBeInTheDocument();
    });
    
    // Fill form
    const recipientInput = screen.getByPlaceholderText('+1234567890');
    const messageInput = screen.getByPlaceholderText('Type your message here...');
    
    fireEvent.change(recipientInput, { target: { value: '+1234567890' } });
    fireEvent.change(messageInput, { target: { value: 'Test message' } });
    
    // Send message
    const sendButton = screen.getByText('Send Message');
    fireEvent.click(sendButton);
    
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/whatsapp/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          to: '+1234567890',
          type: 'text',
          content: { body: 'Test message' }
        })
      });
    });
  });

  test('displays messages when conversation is selected', async () => {
    renderComponent();
    
    // Wait for conversations to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
    
    // Click on conversation
    const conversationCard = screen.getByText('John Doe').closest('[role="button"]');
    fireEvent.click(conversationCard);
    
    await waitFor(() => {
      expect(screen.getByText('Messages with John Doe')).toBeInTheDocument();
      expect(screen.getByText('Hello, I need help with my order')).toBeInTheDocument();
      expect(screen.getByText('I\'d be happy to help you with your order!')).toBeInTheDocument();
    });
  });

  test('handles disconnected state correctly', async () => {
    // Mock disconnected health response
    (fetch as jest.Mock).mockImplementation((url) => {
      if (url === '/api/whatsapp/health') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'not_configured',
            service: 'WhatsApp Business API'
          })
        });
      }
      
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: 'Not found' })
      });
    });
    
    renderComponent();
    
    await waitFor(() => {
      const statusBadge = screen.getByText('Disconnected');
      expect(statusBadge).toBeInTheDocument();
    });
    
    await waitFor(() => {
      expect(screen.getByText('WhatsApp Not Connected')).toBeInTheDocument();
      expect(screen.getByText('Please configure your WhatsApp Business API settings to start managing conversations.')).toBeInTheDocument();
    });
  });

  test('displays templates tab content', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Templates')).toBeInTheDocument();
    });
    
    const templatesTab = screen.getByText('Templates');
    fireEvent.click(templatesTab);
    
    await waitFor(() => {
      expect(screen.getByText('Message Templates')).toBeInTheDocument();
      expect(screen.getByText('Create Template')).toBeInTheDocument();
    });
  });

  test('displays analytics tab content', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Analytics')).toBeInTheDocument();
    });
    
    const analyticsTab = screen.getByText('Analytics');
    fireEvent.click(analyticsTab);
    
    await waitFor(() => {
      expect(screen.getByText('WhatsApp Analytics')).toBeInTheDocument();
      expect(screen.getByText('Message Statistics')).toBeInTheDocument();
      expect(screen.getByText('Contact Growth')).toBeInTheDocument();
    });
  });

  test('handles API errors gracefully', async () => {
    // Mock error response
    (fetch as jest.Mock).mockImplementation((url) => {
      if (url === '/api/whatsapp/send') {
        return Promise.resolve({
          ok: false,
          json: () => Promise.resolve({
            success: false,
            error: 'Failed to send message'
          })
        });
      }
      
      // Default successful responses
      if (url === '/api/whatsapp/health') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'healthy',
            service: 'WhatsApp Business API',
            timestamp: new Date().toISOString()
          })
        });
      }
      
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, data: [] })
      });
    });
    
    renderComponent();
    
    // Try to send a message
    await waitFor(() => {
      const composeButton = screen.getByText('New Message');
      fireEvent.click(composeButton);
    });
    
    await waitFor(() => {
      const recipientInput = screen.getByPlaceholderText('+1234567890');
      const messageInput = screen.getByPlaceholderText('Type your message here...');
      
      fireEvent.change(recipientInput, { target: { value: '+1234567890' } });
      fireEvent.change(messageInput, { target: { value: 'Test message' } });
      
      const sendButton = screen.getByText('Send Message');
      fireEvent.click(sendButton);
    });
    
    // Error toast should appear
    await waitFor(() => {
      expect(screen.getByText('Send Failed')).toBeInTheDocument();
    });
  });
});

export {};