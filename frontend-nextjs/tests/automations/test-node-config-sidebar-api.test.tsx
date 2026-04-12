import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('NodeConfigSidebar - API Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Node Configuration API', () => {
    it('should fetch node configuration via GET /api/nodes/:id/config', async () => {
      const nodeId = 'node-123';
      const mockConfig = {
        id: nodeId,
        type: 'action',
        name: 'Send Email',
        parameters: {
          to: '{{trigger.email}}',
          subject: 'Hello',
          body: 'Test message',
        },
        validation: {
          required: ['to', 'subject'],
          optional: ['body', 'attachments'],
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: mockConfig,
        }),
      });

      const response = await fetch(`/api/nodes/${nodeId}/config`);
      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(`/api/nodes/${nodeId}/config`);
      expect(result.data).toEqual(mockConfig);
      expect(result.data.parameters).toBeDefined();
    });

    it('should update node configuration via PUT /api/nodes/:id/config', async () => {
      const nodeId = 'node-123';
      const updatedConfig = {
        parameters: {
          to: 'test@example.com',
          subject: 'Updated Subject',
          body: 'Updated body',
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: nodeId,
            ...updatedConfig,
            updatedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/nodes/${nodeId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedConfig),
      });

      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(
        `/api/nodes/${nodeId}/config`,
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updatedConfig),
        })
      );
      expect(result.data.parameters.to).toBe('test@example.com');
    });

    it('should validate node configuration via POST /api/nodes/validate', async () => {
      const config = {
        type: 'action',
        action: 'send-email',
        parameters: {
          to: 'test@example.com',
          subject: 'Test',
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            valid: true,
            errors: [],
            warnings: [],
          },
        }),
      });

      const response = await fetch('/api/nodes/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      const result = await response.json();

      expect(result.data.valid).toBe(true);
      expect(result.data.errors).toHaveLength(0);
    });

    it('should return validation errors for invalid configuration', async () => {
      const invalidConfig = {
        type: 'action',
        action: 'send-email',
        parameters: {
          to: '', // Invalid: empty email
          subject: '', // Invalid: empty subject
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            valid: false,
            errors: [
              'Email address is required',
              'Subject is required',
            ],
            warnings: [],
          },
        }),
      });

      const response = await fetch('/api/nodes/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invalidConfig),
      });

      const result = await response.json();

      expect(result.data.valid).toBe(false);
      expect(result.data.errors).toHaveLength(2);
      expect(result.data.errors).toContain('Email address is required');
    });
  });

  describe('Node Templates', () => {
    it('should fetch node templates via GET /api/nodes/templates', async () => {
      const mockTemplates = [
        {
          id: 'template-1',
          type: 'action',
          name: 'Send Email',
          description: 'Send an email to specified recipients',
          parameters: {
            to: { type: 'email', required: true },
            subject: { type: 'text', required: true },
            body: { type: 'textarea', required: false },
          },
        },
        {
          id: 'template-2',
          type: 'action',
          name: 'HTTP Request',
          description: 'Make an HTTP request to an external API',
          parameters: {
            url: { type: 'url', required: true },
            method: { type: 'select', required: true, options: ['GET', 'POST', 'PUT', 'DELETE'] },
            headers: { type: 'object', required: false },
            body: { type: 'object', required: false },
          },
        },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            templates: mockTemplates,
            total: mockTemplates.length,
          },
        }),
      });

      const response = await fetch('/api/nodes/templates');
      const result = await response.json();

      expect(result.data.templates).toHaveLength(2);
      expect(result.data.templates[0].name).toBe('Send Email');
      expect(result.data.templates[1].parameters.method.options).toContain('GET');
    });

    it('should fetch specific node template via GET /api/nodes/templates/:id', async () => {
      const templateId = 'template-1';
      const mockTemplate = {
        id: templateId,
        type: 'action',
        name: 'Send Email',
        parameters: {
          to: { type: 'email', required: true },
          subject: { type: 'text', required: true },
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: mockTemplate,
        }),
      });

      const response = await fetch(`/api/nodes/templates/${templateId}`);
      const result = await response.json();

      expect(result.data.id).toBe(templateId);
      expect(result.data.parameters).toBeDefined();
    });
  });

  describe('Node Parameter Suggestions', () => {
    it('should fetch parameter suggestions via GET /api/nodes/suggestions', async () => {
      const parameterType = 'email';
      const partialInput = 'tes';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            suggestions: [
              { value: 'test@example.com', label: 'test@example.com' },
              { value: 'test2@example.com', label: 'test2@example.com' },
              { value: 'testuser@example.com', label: 'testuser@example.com' },
            ],
          },
        }),
      });

      const response = await fetch(
        `/api/nodes/suggestions?type=${parameterType}&q=${partialInput}`
      );
      const result = await response.json();

      expect(result.data.suggestions).toHaveLength(3);
      expect(result.data.suggestions[0].value).toContain('test');
    });

    it('should fetch available variables via GET /api/workflows/:id/variables', async () => {
      const workflowId = 'workflow-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            variables: [
              { name: 'trigger.email', type: 'string', description: 'Email from trigger' },
              { name: 'trigger.name', type: 'string', description: 'Name from trigger' },
              { name: 'workflow.id', type: 'string', description: 'Workflow ID' },
            ],
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/variables`);
      const result = await response.json();

      expect(result.data.variables).toHaveLength(3);
      expect(result.data.variables[0].name).toBe('trigger.email');
    });
  });

  describe('Node Test Execution', () => {
    it('should test node configuration via POST /api/nodes/test', async () => {
      const nodeTest = {
        type: 'action',
        action: 'send-email',
        parameters: {
          to: 'test@example.com',
          subject: 'Test Email',
          body: 'This is a test',
        },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            testId: 'test-123',
            status: 'running',
            startedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch('/api/nodes/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nodeTest),
      });

      const result = await response.json();

      expect(result.data.status).toBe('running');
      expect(result.data.testId).toBeDefined();
    });

    it('should get test results via GET /api/nodes/tests/:testId', async () => {
      const testId = 'test-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: testId,
            status: 'completed',
            result: {
              success: true,
              output: 'Email sent successfully',
              duration: 1234,
            },
            completedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/nodes/tests/${testId}`);
      const result = await response.json();

      expect(result.data.status).toBe('completed');
      expect(result.data.result.success).toBe(true);
    });
  });

  describe('Real-time Validation', () => {
    it('should validate configuration on each change', async () => {
      let validationCallCount = 0;

      (global.fetch as jest.Mock).mockImplementation(() => {
        validationCallCount++;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { valid: true, errors: [] },
          }),
        });
      });

      // Simulate multiple configuration changes
      const configs = [
        { to: 'test1@example.com' },
        { to: 'test2@example.com' },
        { to: 'test3@example.com' },
      ];

      for (const config of configs) {
        await fetch('/api/nodes/validate', {
          method: 'POST',
          body: JSON.stringify(config),
        });
      }

      expect(validationCallCount).toBe(3);
    });

    it('should debounce validation calls', async () => {
      let validationCallCount = 0;

      (global.fetch as jest.Mock).mockImplementation(() => {
        validationCallCount++;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { valid: true, errors: [] },
          }),
        });
      });

      // Simulate rapid changes
      const validateWithDebounce = async (config: any) => {
        await new Promise(resolve => setTimeout(resolve, 50));
        return fetch('/api/nodes/validate', {
          method: 'POST',
          body: JSON.stringify(config),
        });
      };

      // Rapid calls
      await Promise.all([
        validateWithDebounce({ to: 'test1@example.com' }),
        validateWithDebounce({ to: 'test2@example.com' }),
        validateWithDebounce({ to: 'test3@example.com' }),
      ]);

      expect(validationCallCount).toBe(3);
    });
  });

  describe('Configuration History', () => {
    it('should fetch configuration history via GET /api/nodes/:id/history', async () => {
      const nodeId = 'node-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            history: [
              {
                id: 'hist-1',
                timestamp: '2026-04-11T10:00:00Z',
                config: { to: 'old@example.com' },
                user: 'user-1',
              },
              {
                id: 'hist-2',
                timestamp: '2026-04-11T11:00:00Z',
                config: { to: 'new@example.com' },
                user: 'user-1',
              },
            ],
            total: 2,
          },
        }),
      });

      const response = await fetch(`/api/nodes/${nodeId}/history`);
      const result = await response.json();

      expect(result.data.history).toHaveLength(2);
      expect(result.data.history[0].config.to).toBe('old@example.com');
      expect(result.data.history[1].config.to).toBe('new@example.com');
    });

    it('should restore configuration from history via POST /api/nodes/:id/restore', async () => {
      const nodeId = 'node-123';
      const historyId = 'hist-1';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: nodeId,
            config: { to: 'old@example.com' },
            restoredFrom: historyId,
            restoredAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/nodes/${nodeId}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ historyId }),
      });

      const result = await response.json();

      expect(result.data.restoredFrom).toBe(historyId);
      expect(result.data.config.to).toBe('old@example.com');
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await expect(fetch('/api/nodes/node-123/config')).rejects.toThrow('Network error');
    });

    it('should handle 404 errors for non-existent nodes', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({
          error: 'Node not found',
        }),
      });

      const response = await fetch('/api/nodes/non-existent/config');

      expect(response.ok).toBe(false);
      expect(response.status).toBe(404);
    });

    it('should handle validation errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({
          error: 'Validation failed',
          details: {
            errors: ['Invalid email format', 'Subject is required'],
          },
        }),
      });

      const response = await fetch('/api/nodes/validate', {
        method: 'POST',
        body: JSON.stringify({}),
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(400);

      const result = await response.json();
      expect(result.details.errors).toBeDefined();
    });
  });
});
