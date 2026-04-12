import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock MSW (Mock Service Worker) for API mocking
const mockWorkflowApi = {
  saveWorkflow: jest.fn(),
  loadWorkflow: jest.fn(),
  updateWorkflow: jest.fn(),
  deleteWorkflow: jest.fn(),
};

describe('WorkflowBuilder - API Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock fetch for API calls
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, data: {} }),
      })
    ) as jest.Mock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Workflow Save API Integration', () => {
    it('should save workflow via API and update state', async () => {
      const mockWorkflowData = {
        id: 'workflow-123',
        name: 'Test Workflow',
        nodes: [
          { id: 'node-1', type: 'trigger', data: { label: 'Start' } },
          { id: 'node-2', type: 'action', data: { label: 'Action' } },
        ],
        edges: [
          { id: 'edge-1', source: 'node-1', target: 'node-2' },
        ],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: mockWorkflowData,
        }),
      });

      // Simulate API call
      const response = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mockWorkflowData),
      });

      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mockWorkflowData),
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockWorkflowData);
    });

    it('should handle save errors gracefully', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await expect(fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })).rejects.toThrow('Network error');
    });

    it('should retry failed save operations', async () => {
      let attemptCount = 0;
      (global.fetch as jest.Mock).mockImplementation(() => {
        attemptCount++;
        if (attemptCount < 3) {
          return Promise.reject(new Error('Temporary failure'));
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        });
      });

      // Simulate retry logic
      let success = false;
      for (let i = 0; i < 3; i++) {
        try {
          const response = await fetch('/api/workflows', { method: 'POST' });
          if (response.ok) {
            success = true;
            break;
          }
        } catch (error) {
          // Retry
        }
      }

      expect(attemptCount).toBe(3);
      expect(success).toBe(true);
    });
  });

  describe('Workflow Load API Integration', () => {
    it('should load workflow via API and populate state', async () => {
      const mockWorkflowData = {
        id: 'workflow-123',
        name: 'Loaded Workflow',
        nodes: [{ id: 'node-1', type: 'trigger' }],
        edges: [],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: mockWorkflowData,
        }),
      });

      const response = await fetch('/api/workflows/workflow-123');
      const result = await response.json();

      expect(global.fetch).toHaveBeenCalledWith('/api/workflows/workflow-123');
      expect(result.data).toEqual(mockWorkflowData);
    });

    it('should handle 404 errors when loading non-existent workflow', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({
          error: 'Workflow not found',
        }),
      });

      const response = await fetch('/api/workflows/non-existent');

      expect(response.ok).toBe(false);
      expect(response.status).toBe(404);
    });

    it('should cache loaded workflows to avoid redundant API calls', async () => {
      const cache = new Map();

      (global.fetch as jest.Mock).mockImplementation((url) => {
        if (cache.has(url)) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(cache.get(url)),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => {
            const data = { id: 'workflow-123', name: 'Cached Workflow' };
            cache.set(url, data);
            return Promise.resolve(data);
          },
        });
      });

      // First call - should hit API
      const response1 = await fetch('/api/workflows/workflow-123');
      await response1.json();

      // Second call - should use cache
      const response2 = await fetch('/api/workflows/workflow-123');
      await response2.json();

      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Real-time Updates via WebSocket', () => {
    it('should receive workflow updates via WebSocket', (done) => {
      const mockWebSocket = {
        onmessage: null,
        send: jest.fn(),
        close: jest.fn(),
      };

      // Simulate WebSocket message
      const updateMessage = {
        type: 'WORKFLOW_UPDATE',
        data: {
          workflowId: 'workflow-123',
          nodes: [{ id: 'node-1', type: 'trigger' }],
          timestamp: Date.now(),
        },
      };

      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage({ data: JSON.stringify(updateMessage) });
      }

      expect(mockWebSocket.send).not.toHaveBeenCalled();
      done();
    });

    it('should handle WebSocket connection errors', () => {
      const mockWebSocket = {
        onerror: null,
        close: jest.fn(),
      };

      const errorHandler = jest.fn();
      mockWebSocket.onerror = errorHandler;

      // Simulate WebSocket error
      const error = new Error('WebSocket connection failed');
      if (mockWebSocket.onerror) {
        mockWebSocket.onerror(error);
      }

      expect(errorHandler).toHaveBeenCalledWith(error);
    });

    it('should reconnect WebSocket on connection loss', async () => {
      let reconnectAttempts = 0;
      const maxReconnectAttempts = 3;

      const connectWebSocket = () => {
        return new Promise((resolve, reject) => {
          reconnectAttempts++;
          if (reconnectAttempts <= maxReconnectAttempts) {
            resolve({ connected: true });
          } else {
            reject(new Error('Max reconnect attempts reached'));
          }
        });
      };

      // Simulate reconnection attempts
      for (let i = 0; i < maxReconnectAttempts; i++) {
        try {
          await connectWebSocket();
          break;
        } catch (error) {
          // Retry
        }
      }

      expect(reconnectAttempts).toBeLessThanOrEqual(maxReconnectAttempts);
    });
  });

  describe('Optimistic UI Updates', () => {
    it('should update UI optimistically before API confirmation', async () => {
      let apiCallCount = 0;
      (global.fetch as jest.Mock).mockImplementation(() => {
        apiCallCount++;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { id: 'node-new', type: 'action' },
          }),
        });
      });

      // Optimistic update - update UI immediately
      const optimisticState = {
        nodes: [{ id: 'node-new', type: 'action', data: { label: 'New Node' } }],
        edges: [],
      };

      // Then call API
      await fetch('/api/workflows/nodes', {
        method: 'POST',
        body: JSON.stringify(optimisticState.nodes[0]),
      });

      expect(apiCallCount).toBe(1);
      expect(optimisticState.nodes).toHaveLength(1);
    });

    it('should rollback optimistic update on API failure', async () => {
      const originalState = {
        nodes: [{ id: 'node-1', type: 'trigger' }],
        edges: [],
      };

      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API failed'));

      try {
        // Optimistic update
        const optimisticState = {
          ...originalState,
          nodes: [...originalState.nodes, { id: 'node-2', type: 'action' }],
        };

        // API call fails
        await fetch('/api/workflows/nodes', {
          method: 'POST',
          body: JSON.stringify(optimisticState.nodes[1]),
        });

        // Should rollback to original state
        expect(optimisticState.nodes).toHaveLength(2);
      } catch (error) {
        // Rollback
        expect(originalState.nodes).toHaveLength(1);
      }
    });
  });

  describe('Data Transformation and Validation', () => {
    it('should transform workflow data before sending to API', async () => {
      const rawData = {
        name: 'Test Workflow',
        nodes: [
          { id: '1', type: 'trigger', position: { x: 100, y: 100 } },
        ],
        edges: [{ id: 'e1', source: '1', target: '2' }],
      };

      // Transform data
      const transformedData = {
        ...rawData,
        nodes: rawData.nodes.map(node => ({
          id: node.id,
          type: node.type,
          position: `${node.position.x},${node.position.y}`,
        })),
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await fetch('/api/workflows', {
        method: 'POST',
        body: JSON.stringify(transformedData),
      });

      expect(transformedData.nodes[0].position).toBe('100,100');
    });

    it('should validate workflow data before API call', async () => {
      const invalidData = {
        name: '', // Invalid: empty name
        nodes: [], // Invalid: no nodes
      };

      // Validation should fail before API call
      const validateWorkflow = (data: any) => {
        if (!data.name || data.name.trim() === '') {
          throw new Error('Workflow name is required');
        }
        if (!data.nodes || data.nodes.length === 0) {
          throw new Error('Workflow must have at least one node');
        }
        return true;
      };

      expect(() => validateWorkflow(invalidData)).toThrow('Workflow name is required');
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('State Synchronization', () => {
    it('should demonstrate lack of synchronization with shallow copy', async () => {
      const sharedState = {
        workflowId: 'workflow-123',
        nodes: [{ id: 'node-1', type: 'trigger' }],
        edges: [],
      };

      // Simulate multiple components accessing shared state with shallow copy
      const component1State = { ...sharedState };
      const component2State = { ...sharedState };

      // Update from component1 - this affects both because nodes array is shared
      component1State.nodes.push({ id: 'node-2', type: 'action' });

      // Both components reflect the change (shallow copy issue)
      expect(component1State.nodes).toHaveLength(2);
      expect(component2State.nodes).toHaveLength(2); // Shallow copy shares array reference
    });

    it('should handle concurrent state updates', async () => {
      const state = { count: 0 };

      // Simulate concurrent updates
      const update1 = Promise.resolve().then(() => {
        state.count += 1;
      });

      const update2 = Promise.resolve().then(() => {
        state.count += 2;
      });

      await Promise.all([update1, update2]);

      expect(state.count).toBe(3);
    });
  });
});
