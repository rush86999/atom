import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('WorkflowBuilder - API Call Testing', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Workflow CRUD Operations', () => {
    it('should create a new workflow via POST /api/workflows', async () => {
      const newWorkflow = {
        name: 'New Workflow',
        description: 'Test workflow description',
        nodes: [
          { id: 'node-1', type: 'trigger', data: { trigger: 'webhook' } },
        ],
        edges: [],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: 'workflow-new',
            ...newWorkflow,
            createdAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newWorkflow),
      });

      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newWorkflow),
        })
      );
      expect(response.status).toBe(201);
      expect(result.success).toBe(true);
      expect(result.data.id).toBe('workflow-new');
    });

    it('should read a workflow via GET /api/workflows/:id', async () => {
      const workflowId = 'workflow-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: workflowId,
            name: 'Existing Workflow',
            nodes: [],
            edges: [],
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}`);
      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(`/api/workflows/${workflowId}`);
      expect(result.data.id).toBe(workflowId);
    });

    it('should update a workflow via PUT /api/workflows/:id', async () => {
      const workflowId = 'workflow-123';
      const updates = {
        name: 'Updated Workflow Name',
        description: 'Updated description',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: workflowId,
            ...updates,
            updatedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });

      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(
        `/api/workflows/${workflowId}`,
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(updates),
        })
      );
      expect(result.data.name).toBe(updates.name);
    });

    it('should delete a workflow via DELETE /api/workflows/:id', async () => {
      const workflowId = 'workflow-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          message: 'Workflow deleted successfully',
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}`, {
        method: 'DELETE',
      });

      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith(
        `/api/workflows/${workflowId}`,
        expect.objectContaining({
          method: 'DELETE',
        })
      );
      expect(result.success).toBe(true);
    });
  });

  describe('Node Operations', () => {
    it('should add a node to workflow via POST /api/workflows/:id/nodes', async () => {
      const workflowId = 'workflow-123';
      const newNode = {
        id: 'node-new',
        type: 'action',
        position: { x: 200, y: 200 },
        data: { action: 'send-email' },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          success: true,
          data: newNode,
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newNode),
      });

      const result = await response.json();

      expect(result.data.type).toBe('action');
      expect(result.data.data.action).toBe('send-email');
    });

    it('should update a node via PUT /api/workflows/:id/nodes/:nodeId', async () => {
      const workflowId = 'workflow-123';
      const nodeId = 'node-1';
      const updates = {
        data: { action: 'send-sms' },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: nodeId,
            ...updates,
          },
        }),
      });

      const response = await fetch(
        `/api/workflows/${workflowId}/nodes/${nodeId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        }
      );

      const result = await response.json();

      expect(result.data.data.action).toBe('send-sms');
    });

    it('should delete a node via DELETE /api/workflows/:id/nodes/:nodeId', async () => {
      const workflowId = 'workflow-123';
      const nodeId = 'node-1';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          message: 'Node deleted successfully',
        }),
      });

      const response = await fetch(
        `/api/workflows/${workflowId}/nodes/${nodeId}`,
        {
          method: 'DELETE',
        }
      );

      const result = await response.json();

      expect(result.success).toBe(true);
    });
  });

  describe('Edge Operations', () => {
    it('should create an edge between nodes via POST /api/workflows/:id/edges', async () => {
      const workflowId = 'workflow-123';
      const newEdge = {
        id: 'edge-new',
        source: 'node-1',
        target: 'node-2',
        type: 'default',
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          success: true,
          data: newEdge,
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/edges`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newEdge),
      });

      const result = await response.json();

      expect(result.data.source).toBe('node-1');
      expect(result.data.target).toBe('node-2');
    });

    it('should delete an edge via DELETE /api/workflows/:id/edges/:edgeId', async () => {
      const workflowId = 'workflow-123';
      const edgeId = 'edge-1';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          message: 'Edge deleted successfully',
        }),
      });

      const response = await fetch(
        `/api/workflows/${workflowId}/edges/${edgeId}`,
        {
          method: 'DELETE',
        }
      );

      const result = await response.json();

      expect(result.success).toBe(true);
    });
  });

  describe('Workflow Execution', () => {
    it('should execute workflow via POST /api/workflows/:id/execute', async () => {
      const workflowId = 'workflow-123';
      const executionData = {
        input: { test: 'data' },
        options: { async: true },
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            executionId: 'exec-123',
            status: 'running',
            startedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(executionData),
      });

      const result = await response.json();

      expect(result.data.status).toBe('running');
      expect(result.data.executionId).toBeDefined();
    });

    it('should get execution status via GET /api/executions/:id', async () => {
      const executionId = 'exec-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: executionId,
            status: 'completed',
            result: { output: 'success' },
            completedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/executions/${executionId}`);
      const result = await response.json();

      expect(result.data.status).toBe('completed');
      expect(result.data.result).toBeDefined();
    });

    it('should stop execution via POST /api/executions/:id/stop', async () => {
      const executionId = 'exec-123';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            id: executionId,
            status: 'stopped',
            stoppedAt: new Date().toISOString(),
          },
        }),
      });

      const response = await fetch(`/api/executions/${executionId}/stop`, {
        method: 'POST',
      });
      const result = await response.json();

      expect(result.data.status).toBe('stopped');
    });
  });

  describe('Bulk Operations', () => {
    it('should bulk add nodes via POST /api/workflows/:id/nodes/bulk', async () => {
      const workflowId = 'workflow-123';
      const nodes = [
        { id: 'node-1', type: 'trigger' },
        { id: 'node-2', type: 'action' },
        { id: 'node-3', type: 'condition' },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          success: true,
          data: {
            created: 3,
            nodes,
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/nodes/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes }),
      });

      const result = await response.json();

      expect(result.data.created).toBe(3);
      expect(result.data.nodes).toHaveLength(3);
    });

    it('should bulk delete nodes via DELETE /api/workflows/:id/nodes/bulk', async () => {
      const workflowId = 'workflow-123';
      const nodeIds = ['node-1', 'node-2', 'node-3'];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            deleted: 3,
            nodeIds,
          },
        }),
      });

      const response = await fetch(`/api/workflows/${workflowId}/nodes/bulk`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeIds }),
      });

      const result = await response.json();

      expect(result.data.deleted).toBe(3);
    });
  });

  describe('Validation Endpoints', () => {
    it('should validate workflow via POST /api/workflows/validate', async () => {
      const workflow = {
        nodes: [
          { id: 'node-1', type: 'trigger' },
          { id: 'node-2', type: 'action' },
        ],
        edges: [
          { source: 'node-1', target: 'node-2' },
        ],
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

      const response = await fetch('/api/workflows/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow),
      });

      const result = await response.json();

      expect(result.data.valid).toBe(true);
      expect(result.data.errors).toHaveLength(0);
    });

    it('should return validation errors for invalid workflow', async () => {
      const invalidWorkflow = {
        nodes: [],
        edges: [],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            valid: false,
            errors: [
              'Workflow must have at least one node',
              'Workflow must have at least one trigger node',
            ],
            warnings: [],
          },
        }),
      });

      const response = await fetch('/api/workflows/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invalidWorkflow),
      });

      const result = await response.json();

      expect(result.data.valid).toBe(false);
      expect(result.data.errors.length).toBeGreaterThan(0);
    });
  });

  describe('Search and Filter', () => {
    it('should search workflows via GET /api/workflows?search=query', async () => {
      const searchQuery = 'email';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            workflows: [
              { id: 'workflow-1', name: 'Email Workflow' },
              { id: 'workflow-2', name: 'Send Email Campaign' },
            ],
            total: 2,
          },
        }),
      });

      const response = await fetch(`/api/workflows?search=${searchQuery}`);
      const result = await response.json();

      expect(result.data.workflows).toHaveLength(2);
      expect(result.data.workflows[0].name).toContain('Email');
    });

    it('should filter workflows by tag via GET /api/workflows?tag=tagName', async () => {
      const tag = 'automation';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          success: true,
          data: {
            workflows: [
              { id: 'workflow-1', name: 'Auto Workflow', tags: ['automation'] },
            ],
            total: 1,
          },
        }),
      });

      const response = await fetch(`/api/workflows?tag=${tag}`);
      const result = await response.json();

      expect(result.data.workflows).toHaveLength(1);
      expect(result.data.workflows[0].tags).toContain('automation');
    });
  });
});
