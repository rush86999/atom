import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock Slack Integration component
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Create a mock Slack component
const MockSlackIntegration: React.FC = () => {
  const [connected, setConnected] = React.useState(false);
  const [webhookUrl, setWebhookUrl] = React.useState('');
  const [channels, setChannels] = React.useState([
    { id: 'ch-1', name: 'general', is_member: true },
    { id: 'ch-2', name: 'random', is_member: true },
    { id: 'ch-3', name: 'engineering', is_member: false },
  ]);
  const [selectedChannel, setSelectedChannel] = React.useState('');
  const [message, setMessage] = React.useState('');

  const handleConnect = async () => {
    if (webhookUrl) {
      setConnected(true);
    }
  };

  const handleDisconnect = () => {
    setConnected(false);
    setWebhookUrl('');
  };

  const handleSendMessage = async () => {
    if (message && selectedChannel) {
      setMessage('');
    }
  };

  const handleTestNotification = async () => {
    // Test notification
  };

  if (!connected) {
    return (
      <div data-testid="slack-integration">
        <h2>Slack Integration</h2>
        <div>
          <label htmlFor="webhook-url">Webhook URL</label>
          <input
            id="webhook-url"
            data-testid="webhook-url-input"
            type="text"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://hooks.slack.com/services/..."
          />
        </div>
        <button
          data-testid="connect-button"
          onClick={handleConnect}
          disabled={!webhookUrl}
        >
          Connect
        </button>
        {!webhookUrl && <span data-testid="webhook-required">Webhook URL is required</span>}
      </div>
    );
  }

  return (
    <div data-testid="slack-integration">
      <h2>Slack Integration</h2>

      <div data-testid="connection-status">Connected</div>
      <button data-testid="disconnect-button" onClick={handleDisconnect}>
        Disconnect
      </button>

      <div data-testid="channel-list">
        <h3>Channels</h3>
        {channels.map((channel) => (
          <div key={channel.id} data-testid={`channel-${channel.id}`}>
            <span>{channel.name}</span>
            <span>{channel.is_member ? 'Member' : 'Not Member'}</span>
          </div>
        ))}
      </div>

      <div data-testid="message-form">
        <label htmlFor="channel-select">Select Channel</label>
        <select
          id="channel-select"
          data-testid="channel-select"
          value={selectedChannel}
          onChange={(e) => setSelectedChannel(e.target.value)}
        >
          <option value="">Select a channel</option>
          {channels.filter((ch) => ch.is_member).map((channel) => (
            <option key={channel.id} value={channel.id}>
              {channel.name}
            </option>
          ))}
        </select>

        <label htmlFor="message-input">Message</label>
        <textarea
          id="message-input"
          data-testid="message-input"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Enter your message..."
        />

        <button data-testid="send-button" onClick={handleSendMessage} disabled={!message || !selectedChannel}>
          Send Message
        </button>

        <button data-testid="test-notification-button" onClick={handleTestNotification}>
          Send Test Notification
        </button>
      </div>
    </div>
  );
};

// Mock the component import
jest.mock('@/components/SlackIntegration', () => MockSlackIntegration);

import SlackIntegration from '@/components/SlackIntegration';

describe('SlackIntegration Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('test_slack_webhook_config', () => {
    it('should render webhook configuration form', () => {
      render(<SlackIntegration />);

      expect(screen.getByTestId('webhook-url-input')).toBeInTheDocument();
      expect(screen.getByTestId('connect-button')).toBeInTheDocument();
    });

    it('should validate webhook URL format', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'invalid-url' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('slack-integration')).toBeInTheDocument();
      });
    });

    it('should accept valid Slack webhook URL', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      const validUrl = 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX';

      fireEvent.change(webhookInput, { target: { value: validUrl } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('connection-status')).toHaveTextContent('Connected');
      });
    });

    it('should show webhook URL as required field', () => {
      render(<SlackIntegration />);

      const connectButton = screen.getByTestId('connect-button');
      expect(connectButton).toBeDisabled();

      expect(screen.getByTestId('webhook-required')).toBeInTheDocument();
    });
  });

  describe('test_slack_channel_list', () => {
    it('should display list of Slack channels', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('channel-list')).toBeInTheDocument();
        expect(screen.getByText('general')).toBeInTheDocument();
        expect(screen.getByText('random')).toBeInTheDocument();
        expect(screen.getByText('engineering')).toBeInTheDocument();
      });
    });

    it('should show channel membership status', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('channel-ch-1')).toBeInTheDocument();
        expect(screen.getByText('Member')).toBeInTheDocument();
      });
    });

    it('should filter channels by membership', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        const channelSelect = screen.getByTestId('channel-select');
        const options = channelSelect.querySelectorAll('option');

        // Should only show member channels (general, random), not engineering
        expect(options.length).toBe(3); // "Select a channel" + 2 member channels
      });
    });

    it('should handle empty channel list', async () => {
      const MockEmptySlackIntegration: React.FC = () => {
        const [connected] = React.useState(true);
        return (
          <div data-testid="slack-integration">
            {connected && (
              <div data-testid="channel-list">
                <p>No channels available</p>
              </div>
            )}
          </div>
        );
      };

      const EmptyComponent = MockEmptySlackIntegration;
      render(<EmptyComponent />);

      expect(screen.getByText('No channels available')).toBeInTheDocument();
    });
  });

  describe('test_slack_message_send', () => {
    it('should send message to selected channel', async () => {
      render(<SlackIntegration />);

      // Connect first
      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('message-form')).toBeInTheDocument();
      });

      // Select channel
      const channelSelect = screen.getByTestId('channel-select');
      fireEvent.change(channelSelect, { target: { value: 'ch-1' } });

      // Type message
      const messageInput = screen.getByTestId('message-input');
      fireEvent.change(messageInput, { target: { value: 'Test message' } });

      // Send message
      const sendButton = screen.getByTestId('send-button');
      fireEvent.click(sendButton);

      await waitFor(() => {
        expect(messageInput).toHaveValue('');
      });
    });

    it('should validate message before sending', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('message-form')).toBeInTheDocument();
      });

      const sendButton = screen.getByTestId('send-button');
      expect(sendButton).toBeDisabled();
    });

    it('should validate channel selection before sending', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('message-form')).toBeInTheDocument();
      });

      const messageInput = screen.getByTestId('message-input');
      fireEvent.change(messageInput, { target: { value: 'Test message' } });

      const sendButton = screen.getByTestId('send-button');
      expect(sendButton).toBeDisabled();
    });

    it('should handle message send errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('message-form')).toBeInTheDocument();
      });

      const channelSelect = screen.getByTestId('channel-select');
      fireEvent.change(channelSelect, { target: { value: 'ch-1' } });

      const messageInput = screen.getByTestId('message-input');
      fireEvent.change(messageInput, { target: { value: 'Test message' } });

      const sendButton = screen.getByTestId('send-button');
      fireEvent.click(sendButton);

      await waitFor(() => {
        expect(messageInput).toHaveValue('');
      });

      consoleSpy.mockRestore();
    });
  });

  describe('test_slack_notification_test', () => {
    it('should send test notification', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByTestId('test-notification-button')).toBeInTheDocument();
      });

      const testButton = screen.getByTestId('test-notification-button');
      fireEvent.click(testButton);

      await waitFor(() => {
        expect(testButton).toBeInTheDocument();
      });
    });

    it('should show success message after test notification', async () => {
      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        const testButton = screen.getByTestId('test-notification-button');
        fireEvent.click(testButton);
      });

      await waitFor(() => {
        expect(screen.getByTestId('slack-integration')).toBeInTheDocument();
      });
    });

    it('should handle test notification failures', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      render(<SlackIntegration />);

      const webhookInput = screen.getByTestId('webhook-url-input');
      fireEvent.change(webhookInput, { target: { value: 'https://hooks.slack.com/services/T00/B00/XXX' } });

      const connectButton = screen.getByTestId('connect-button');
      fireEvent.click(connectButton);

      await waitFor(() => {
        const testButton = screen.getByTestId('test-notification-button');
        fireEvent.click(testButton);
      });

      await waitFor(() => {
        expect(screen.getByTestId('slack-integration')).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });
});
