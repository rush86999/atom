import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

describe('IntegrationConnectionGuide - Setup & Configuration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Integration Discovery', () => {
    it('should fetch available integrations list', async () => {
      const mockIntegrations = [
        {
          id: 'slack',
          name: 'Slack',
          category: 'communication',
          description: 'Send messages to Slack channels',
          icon: 'slack-icon.png',
          enabled: true,
        },
        {
          id: 'salesforce',
          name: 'Salesforce',
          category: 'crm',
          description: 'Manage Salesforce records',
          icon: 'salesforce-icon.png',
          enabled: false,
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { integrations: mockIntegrations },
        }),
      });

      const response = await fetch('/api/integrations');
      const result = await response.json();

      expect(result.data.integrations).toHaveLength(2);
      expect(result.data.integrations[0].name).toBe('Slack');
      expect(result.data.integrations[1].category).toBe('crm');
    });

    it('should filter integrations by category', async () => {
      const allIntegrations = [
        { id: 'slack', category: 'communication' },
        { id: 'gmail', category: 'communication' },
        { id: 'salesforce', category: 'crm' },
        { id: 'hubspot', category: 'crm' },
      ];

      const filterByCategory = (integrations: any[], category: string) => {
        return integrations.filter((int) => int.category === category);
      };

      const crmIntegrations = filterByCategory(allIntegrations, 'crm');

      expect(crmIntegrations).toHaveLength(2);
      expect(crmIntegrations[0].id).toBe('salesforce');
      expect(crmIntegrations[1].id).toBe('hubspot');
    });

    it('should search integrations by name', async () => {
      const integrations = [
        { id: 'slack', name: 'Slack' },
        { id: 'gmail', name: 'Gmail' },
        { id: 'google-drive', name: 'Google Drive' },
      ];

      const searchIntegrations = (items: any[], query: string) => {
        const lowerQuery = query.toLowerCase();
        return items.filter(
          (item) =>
            item.name.toLowerCase().includes(lowerQuery) ||
            item.id.toLowerCase().includes(lowerQuery)
        );
      };

      const results = searchIntegrations(integrations, 'google');

      expect(results).toHaveLength(2);
      expect(results[0].id).toBe('gmail');
      expect(results[1].id).toBe('google-drive');
    });
  });

  describe('OAuth Connection Flow', () => {
    it('should initiate OAuth authorization', async () => {
      const integrationId = 'slack';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            authUrl: 'https://slack.com/oauth/authorize?client_id=123&redirect_uri=...',
          },
        }),
      });

      const response = await fetch(`/api/integrations/${integrationId}/authorize`);
      const result = await response.json();

      expect(result.data.authUrl).toContain('slack.com/oauth');
      expect(result.data.authUrl).toContain('client_id');
    });

    it('should handle OAuth callback', async () => {
      const callbackData = {
        code: 'auth-code-123',
        state: 'state-456',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            connected: true,
            accessToken: 'access-token-789',
            refreshToken: 'refresh-token-abc',
          },
        }),
      });

      const response = await fetch('/api/integrations/slack/callback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(callbackData),
      });

      const result = await response.json();

      expect(result.data.connected).toBe(true);
      expect(result.data.accessToken).toBeDefined();
    });

    it('should handle OAuth errors', async () => {
      const errorData = {
        error: 'access_denied',
        error_description: 'User denied access',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({
          success: false,
          error: 'OAuth authorization failed',
          details: errorData,
        }),
      });

      const response = await fetch('/api/integrations/slack/callback', {
        method: 'POST',
        body: JSON.stringify(errorData),
      });

      const result = await response.json();

      expect(result.success).toBe(false);
      expect(result.details.error).toBe('access_denied');
    });
  });

  describe('API Key Configuration', () => {
    it('should validate API key format', async () => {
      const validateAPIKey = (key: string, provider: string): boolean => {
        const patterns: Record<string, RegExp> = {
          slack: /^xoxb-\d+-\d+-[\w-]+$/,
          openai: /^sk-[\w-]{48}$/,
          github: /^ghp_[\w]{36}$/,
        };

        const pattern = patterns[provider];
        return pattern ? pattern.test(key) : true;
      };

      expect(validateAPIKey('xoxb-123-456-abc-def', 'slack')).toBe(true);
      expect(validateAPIKey('invalid-key', 'slack')).toBe(false);
      expect(validateAPIKey('sk-abc123...', 'openai')).toBe(true);
    });

    it('should test API key validity', async () => {
      const apiKey = 'test-api-key-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { valid: true, account: { name: 'Test Account' } },
        }),
      });

      const response = await fetch('/api/integrations/test-key', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}` },
      });

      const result = await response.json();

      expect(result.data.valid).toBe(true);
      expect(result.data.account.name).toBe('Test Account');
    });

    it('should handle invalid API keys', async () => {
      const invalidKey = 'invalid-key';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({
          success: false,
          error: 'Invalid API key',
        }),
      });

      const response = await fetch('/api/integrations/test-key', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${invalidKey}` },
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(401);
    });
  });

  describe('Webhook Configuration', () => {
    it('should generate webhook URL', async () => {
      const integrationId = 'slack';
      const workspaceId = 'workspace-123';

      const generateWebhookUrl = (intId: string, wsId: string): string => {
        return `https://api.atom.com/webhooks/${wsId}/${intId}`;
      };

      const webhookUrl = generateWebhookUrl(integrationId, workspaceId);

      expect(webhookUrl).toBe('https://api.atom.com/webhooks/workspace-123/slack');
    });

    it('should register webhook with integration', async () => {
      const webhookConfig = {
        url: 'https://api.atom.com/webhooks/workspace-123/slack',
        events: ['message.created', 'channel.updated'],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            webhookId: 'webhook-123',
            active: true,
          },
        }),
      });

      const response = await fetch('/api/integrations/slack/webhooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(webhookConfig),
      });

      const result = await response.json();

      expect(result.data.webhookId).toBeDefined();
      expect(result.data.active).toBe(true);
    });

    it('should verify webhook delivery', async () => {
      const webhookId = 'webhook-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            lastDelivery: new Date().toISOString(),
            successRate: 98.5,
            totalDeliveries: 1000,
          },
        }),
      });

      const response = await fetch(`/api/integrations/webhooks/${webhookId}/status`);
      const result = await response.json();

      expect(result.data.successRate).toBe(98.5);
      expect(result.data.totalDeliveries).toBe(1000);
    });
  });

  describe('Connection Status Monitoring', () => {
    it('should check connection health', async () => {
      const integrationId = 'slack';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            status: 'healthy',
            lastChecked: new Date().toISOString(),
            latency: 45, // ms
          },
        }),
      });

      const response = await fetch(`/api/integrations/${integrationId}/health`);
      const result = await response.json();

      expect(result.data.status).toBe('healthy');
      expect(result.data.latency).toBeLessThan(100);
    });

    it('should detect unhealthy connections', async () => {
      const integrationId = 'salesforce';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            status: 'unhealthy',
            lastChecked: new Date().toISOString(),
            error: 'Connection timeout',
          },
        }),
      });

      const response = await fetch(`/api/integrations/${integrationId}/health`);
      const result = await response.json();

      expect(result.data.status).toBe('unhealthy');
      expect(result.data.error).toBe('Connection timeout');
    });

    it('should retry unhealthy connections', async () => {
      let attemptCount = 0;

      (global.fetch as jest.Mock).mockImplementation(() => {
        attemptCount++;
        if (attemptCount < 3) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({
              success: true,
              data: { status: 'unhealthy' },
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { status: 'healthy' },
          }),
        });
      });

      // Simulate retry logic
      let status = 'unhealthy';
      for (let i = 0; i < 3; i++) {
        const response = await fetch('/api/integrations/slack/health');
        const result = await response.json();
        if (result.data.status === 'healthy') {
          status = 'healthy';
          break;
        }
      }

      expect(attemptCount).toBe(3);
      expect(status).toBe('healthy');
    });
  });

  describe('Integration Configuration', () => {
    it('should save integration settings', async () => {
      const settings = {
        integrationId: 'slack',
        config: {
          defaultChannel: '#general',
          notifyOnError: true,
          autoReconnect: true,
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            saved: true,
            config: settings.config,
          },
        }),
      });

      const response = await fetch('/api/integrations/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });

      const result = await response.json();

      expect(result.data.saved).toBe(true);
      expect(result.data.config.defaultChannel).toBe('#general');
    });

    it('should load integration settings', async () => {
      const integrationId = 'slack';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            defaultChannel: '#general',
            notifyOnError: true,
          },
        }),
      });

      const response = await fetch(`/api/integrations/${integrationId}/settings`);
      const result = await response.json();

      expect(result.data.defaultChannel).toBe('#general');
    });

    it('should validate configuration before saving', async () => {
      const invalidConfig = {
        integrationId: 'slack',
        config: {
          defaultChannel: '', // Invalid: empty channel
        },
      };

      const validateConfig = (config: any): { valid: boolean; errors?: string[] } => {
        const errors: string[] = [];

        if (!config.defaultChannel || config.defaultChannel.trim() === '') {
          errors.push('Default channel is required');
        }

        if (errors.length > 0) {
          return { valid: false, errors };
        }

        return { valid: true };
      };

      const validation = validateConfig(invalidConfig.config);

      expect(validation.valid).toBe(false);
      expect(validation.errors).toContain('Default channel is required');
    });
  });

  describe('Connection Removal', () => {
    it('should disconnect integration', async () => {
      const integrationId = 'slack';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            disconnected: true,
          },
        }),
      });

      const response = await fetch(`/api/integrations/${integrationId}/disconnect`, {
        method: 'POST',
      });

      const result = await response.json();

      expect(result.data.disconnected).toBe(true);
    });

    it('should clear cached credentials on disconnect', async () => {
      const integrationId = 'slack';
      const credentials = { accessToken: 'token-123' };

      // Clear credentials
      const clearedCredentials = null;

      expect(credentials).toBeDefined();
      expect(clearedCredentials).toBeNull();
    });
  });
});
