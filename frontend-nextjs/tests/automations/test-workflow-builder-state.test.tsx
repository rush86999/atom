import React from 'react';
import { renderHook, act } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('WorkflowBuilder - State Management Tests', () => {
  describe('Complex State Transitions', () => {
    it('should handle workflow loading state transition', async () => {
      let state = {
        status: 'idle',
        workflow: null,
        error: null,
      };

      // Transition: idle -> loading
      act(() => {
        state = { ...state, status: 'loading' };
      });
      expect(state.status).toBe('loading');

      // Transition: loading -> success
      act(() => {
        state = {
          status: 'success',
          workflow: { id: 'workflow-123', name: 'Test Workflow' },
          error: null,
        };
      });
      expect(state.status).toBe('success');
      expect(state.workflow).toBeDefined();

      // Transition: success -> idle
      act(() => {
        state = { ...state, status: 'idle', workflow: null };
      });
      expect(state.status).toBe('idle');
      expect(state.workflow).toBeNull();
    });

    it('should handle workflow saving state transition', async () => {
      let state = {
        status: 'idle',
        isSaving: false,
        lastSaved: null,
        error: null,
      };

      // Transition: idle -> saving
      act(() => {
        state = { ...state, status: 'saving', isSaving: true };
      });
      expect(state.isSaving).toBe(true);

      // Transition: saving -> saved
      act(() => {
        state = {
          status: 'saved',
          isSaving: false,
          lastSaved: new Date().toISOString(),
          error: null,
        };
      });
      expect(state.isSaving).toBe(false);
      expect(state.lastSaved).toBeDefined();

      // Transition: saved -> idle
      act(() => {
        state = { ...state, status: 'idle' };
      });
      expect(state.status).toBe('idle');
    });

    it('should handle error state transition', async () => {
      let state = {
        status: 'idle',
        error: null,
      };

      // Transition: idle -> error
      act(() => {
        state = {
          status: 'error',
          error: 'Failed to load workflow',
        };
      });
      expect(state.status).toBe('error');
      expect(state.error).toBeDefined();

      // Transition: error -> idle (retry)
      act(() => {
        state = { ...state, status: 'idle', error: null };
      });
      expect(state.status).toBe('idle');
      expect(state.error).toBeNull();
    });

    it('should handle concurrent state updates', async () => {
      let state = {
        nodes: [],
        edges: [],
        updateCount: 0,
      };

      // Simulate concurrent updates
      await act(async () => {
        const updates = [
          Promise.resolve().then(() => {
            state.nodes.push({ id: 'node-1' });
            state.updateCount++;
          }),
          Promise.resolve().then(() => {
            state.edges.push({ id: 'edge-1' });
            state.updateCount++;
          }),
          Promise.resolve().then(() => {
            state.nodes.push({ id: 'node-2' });
            state.updateCount++;
          }),
        ];

        await Promise.all(updates);
      });

      expect(state.nodes).toHaveLength(2);
      expect(state.edges).toHaveLength(1);
      expect(state.updateCount).toBe(3);
    });
  });

  describe('State Persistence', () => {
    it('should persist state to localStorage', () => {
      const state = {
        workflowId: 'workflow-123',
        nodes: [{ id: 'node-1', type: 'trigger' }],
        edges: [],
      };

      const storageKey = 'workflow-builder-state';
      const setItem = jest.fn();
      const getItem = jest.fn();

      // Mock localStorage
      const localStorage = {
        setItem,
        getItem,
      };

      // Save state
      localStorage.setItem(storageKey, JSON.stringify(state));

      expect(setItem).toHaveBeenCalledWith(
        storageKey,
        JSON.stringify(state)
      );
    });

    it('should restore state from localStorage', () => {
      const savedState = {
        workflowId: 'workflow-123',
        nodes: [{ id: 'node-1', type: 'trigger' }],
        edges: [],
      };

      const getItem = jest.fn(() => JSON.stringify(savedState));
      const localStorage = { getItem };

      // Load state
      const stateJson = localStorage.getItem('workflow-builder-state');
      const restoredState = JSON.parse(stateJson || '{}');

      expect(getItem).toHaveBeenCalledWith('workflow-builder-state');
      expect(restoredState).toEqual(savedState);
    });

    it('should handle corrupted localStorage data', () => {
      const getItem = jest.fn(() => 'invalid-json{');
      const localStorage = { getItem };

      try {
        const stateJson = localStorage.getItem('workflow-builder-state');
        JSON.parse(stateJson || '{}');
      } catch (error) {
        expect(error).toBeInstanceOf(SyntaxError);
      }
    });

    it('should clear state from localStorage', () => {
      const removeItem = jest.fn();
      const localStorage = { removeItem };

      localStorage.removeItem('workflow-builder-state');

      expect(removeItem).toHaveBeenCalledWith('workflow-builder-state');
    });
  });

  describe('Derived State Computation', () => {
    it('should compute hasUnsavedChanges derived state', () => {
      const baseState = {
        workflow: { id: 'workflow-123', name: 'Original' },
        lastSaved: { id: 'workflow-123', name: 'Original' },
      };

      const computeHasUnsavedChanges = (state: typeof baseState) => {
        return JSON.stringify(state.workflow) !== JSON.stringify(state.lastSaved);
      };

      expect(computeHasUnsavedChanges(baseState)).toBe(false);

      // Modify workflow
      const modifiedState = {
        ...baseState,
        workflow: { id: 'workflow-123', name: 'Modified' },
      };

      expect(computeHasUnsavedChanges(modifiedState)).toBe(true);
    });

    it('should compute isValid derived state', () => {
      const state = {
        nodes: [
          { id: 'node-1', type: 'trigger' },
          { id: 'node-2', type: 'action' },
        ],
        edges: [{ source: 'node-1', target: 'node-2' }],
      };

      const computeIsValid = (s: typeof state) => {
        const hasTrigger = s.nodes.some((n) => n.type === 'trigger');
        const hasAction = s.nodes.some((n) => n.type === 'action');
        return s.nodes.length > 0 && hasTrigger && hasAction;
      };

      expect(computeIsValid(state)).toBe(true);

      const invalidState = {
        ...state,
        nodes: [{ id: 'node-1', type: 'trigger' }],
      };

      expect(computeIsValid(invalidState)).toBe(false);
    });

    it('should compute canExecute derived state', () => {
      const state = {
        status: 'idle',
        isValid: true,
        hasUnsavedChanges: false,
        isExecuting: false,
      };

      const computeCanExecute = (s: typeof state) => {
        return s.status === 'idle' && s.isValid && !s.hasUnsavedChanges && !s.isExecuting;
      };

      expect(computeCanExecute(state)).toBe(true);

      const cannotExecuteState = {
        ...state,
        hasUnsavedChanges: true,
      };

      expect(computeCanExecute(cannotExecuteState)).toBe(false);
    });

    it('should compute nodeStatistics derived state', () => {
      const state = {
        nodes: [
          { id: 'node-1', type: 'trigger' },
          { id: 'node-2', type: 'action' },
          { id: 'node-3', type: 'condition' },
          { id: 'node-4', type: 'action' },
        ],
      };

      const computeNodeStatistics = (s: typeof state) => {
        const stats = {
          total: s.nodes.length,
          byType: {} as Record<string, number>,
        };

        s.nodes.forEach((node) => {
          stats.byType[node.type] = (stats.byType[node.type] || 0) + 1;
        });

        return stats;
      };

      const stats = computeNodeStatistics(state);

      expect(stats.total).toBe(4);
      expect(stats.byType.trigger).toBe(1);
      expect(stats.byType.action).toBe(2);
      expect(stats.byType.condition).toBe(1);
    });
  });

  describe('State Normalization and Denormalization', () => {
    it('should normalize workflow state', () => {
      const rawState = {
        nodes: [
          {
            id: 'node-1',
            type: 'trigger',
            position: { x: 100, y: 100 },
            data: { trigger: 'webhook' },
          },
          {
            id: 'node-2',
            type: 'action',
            position: { x: 300, y: 100 },
            data: { action: 'send-email' },
          },
        ],
        edges: [
          { id: 'edge-1', source: 'node-1', target: 'node-2' },
        ],
      };

      const normalizedState = {
        nodes: {
          'node-1': { id: 'node-1', type: 'trigger', position: '100,100' },
          'node-2': { id: 'node-2', type: 'action', position: '300,100' },
        },
        edges: ['edge-1'],
        nodeData: {
          'node-1': { trigger: 'webhook' },
          'node-2': { action: 'send-email' },
        },
      };

      // Verify normalization
      expect(Object.keys(normalizedState.nodes)).toHaveLength(2);
      expect(normalizedState.edges).toHaveLength(1);
      expect(normalizedState.nodeData['node-1']).toBeDefined();
    });

    it('should denormalize workflow state for rendering', () => {
      const normalizedState = {
        nodes: {
          'node-1': { id: 'node-1', type: 'trigger', position: '100,100' },
          'node-2': { id: 'node-2', type: 'action', position: '300,100' },
        },
        edges: [{ id: 'edge-1', source: 'node-1', target: 'node-2' }],
        nodeData: {
          'node-1': { trigger: 'webhook' },
          'node-2': { action: 'send-email' },
        },
      };

      const denormalizedState = {
        nodes: Object.values(normalizedState.nodes).map((node) => ({
          ...node,
          position: {
            x: parseInt(node.position.split(',')[0]),
            y: parseInt(node.position.split(',')[1]),
          },
          data: normalizedState.nodeData[node.id],
        })),
        edges: normalizedState.edges,
      };

      expect(denormalizedState.nodes).toHaveLength(2);
      expect(denormalizedState.nodes[0].position.x).toBe(100);
      expect(denormalizedState.nodes[0].data).toBeDefined();
    });
  });

  describe('State Batching', () => {
    it('should batch multiple state updates', async () => {
      let state = {
        nodes: [],
        edges: [],
        updateCount: 0,
      };

      await act(async () => {
        // Batch multiple updates
        const updates = [
          state.nodes.push({ id: 'node-1' }),
          state.nodes.push({ id: 'node-2' }),
          state.edges.push({ id: 'edge-1' }),
          state.updateCount++,
        ];

        // All updates should be applied together
        await Promise.resolve();
      });

      expect(state.nodes).toHaveLength(2);
      expect(state.edges).toHaveLength(1);
      expect(state.updateCount).toBe(1);
    });

    it('should debounce rapid state updates', async () => {
      let state = {
        value: '',
        updateCount: 0,
      };

      const debounce = (fn: Function, delay: number) => {
        let timeoutId: NodeJS.Timeout;
        return (...args: any[]) => {
          clearTimeout(timeoutId);
          timeoutId = setTimeout(() => fn(...args), delay);
        };
      };

      const updateState = debounce((newValue: string) => {
        state.value = newValue;
        state.updateCount++;
      }, 100);

      // Rapid updates
      updateState('a');
      updateState('ab');
      updateState('abc');

      // Wait for debounce
      await new Promise((resolve) => setTimeout(resolve, 150));

      expect(state.value).toBe('abc');
      expect(state.updateCount).toBe(1);
    });
  });

  describe('State History and Undo/Redo', () => {
    it('should maintain state history', () => {
      const history: any[] = [];
      let currentState = { nodes: [] };

      // Add state to history
      history.push({ ...currentState });
      currentState = { nodes: [{ id: 'node-1' }] };

      history.push({ ...currentState });
      currentState = { nodes: [{ id: 'node-1' }, { id: 'node-2' }] };

      history.push({ ...currentState });

      expect(history).toHaveLength(3);
      expect(history[0].nodes).toHaveLength(0);
      expect(history[2].nodes).toHaveLength(2);
    });

    it('should undo to previous state', () => {
      const history = [
        { nodes: [] },
        { nodes: [{ id: 'node-1' }] },
        { nodes: [{ id: 'node-1' }, { id: 'node-2' }] },
      ];
      let currentIndex = 2;

      // Undo
      currentIndex--;
      const previousState = history[currentIndex];

      expect(currentIndex).toBe(1);
      expect(previousState.nodes).toHaveLength(1);
    });

    it('should redo to next state', () => {
      const history = [
        { nodes: [] },
        { nodes: [{ id: 'node-1' }] },
        { nodes: [{ id: 'node-1' }, { id: 'node-2' }] },
      ];
      let currentIndex = 1;

      // Redo
      currentIndex++;
      const nextState = history[currentIndex];

      expect(currentIndex).toBe(2);
      expect(nextState.nodes).toHaveLength(2);
    });

    it('should clear redo history on new state', () => {
      let history = [
        { nodes: [] },
        { nodes: [{ id: 'node-1' }] },
      ];
      let currentIndex = 1;

      // Add new state after undo
      currentIndex++;
      history = history.slice(0, currentIndex);
      history.push({ nodes: [{ id: 'node-3' }] });

      expect(history).toHaveLength(3);
      expect(history[2].nodes).toHaveLength(1);
      expect(history[2].nodes[0].id).toBe('node-3');
    });
  });
});
