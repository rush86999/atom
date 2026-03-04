/**
 * useUndoRedo Hook Tests
 *
 * Tests for undo/redo state management with history stack.
 */

import { renderHook, act } from '@testing-library/react';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import { Node, Edge } from 'reactflow';

// ============================================
// Test Utilities
// ============================================

function createMockFlowState(override?: { nodes?: Node[]; edges?: Edge[] }) {
  return {
    nodes: override?.nodes || [
      { id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'Node 1' } }
    ],
    edges: override?.edges || []
  };
}

// ============================================
// Initialization Tests
// ============================================

describe('useUndoRedo - Initialization', () => {
  test('should initialize with initial state', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    expect(result.current.history.present).toEqual(initialState);
  });

  test('should initialize with empty past array', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    expect(result.current.history.past).toEqual([]);
  });

  test('should initialize with empty future array', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    expect(result.current.history.future).toEqual([]);
  });

  test('should have canUndo false initially', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    expect(result.current.canUndo).toBe(false);
  });

  test('should have canRedo false initially', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    expect(result.current.canRedo).toBe(false);
  });
});

// ============================================
// Take Snapshot Tests
// ============================================

describe('useUndoRedo - Take Snapshot', () => {
  test('should save current state to past', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [
        { id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'Node 1' } },
        { id: '2', type: 'default', position: { x: 100, y: 0 }, data: { label: 'Node 2' } }
      ]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    expect(result.current.history.past).toHaveLength(1);
    expect(result.current.history.past[0]).toEqual(initialState);
  });

  test('should update present state', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [
        { id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'Updated' } }
      ]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    expect(result.current.history.present).toEqual(newState);
  });

  test('should clear future array on new snapshot', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Create first snapshot
    const state1 = createMockFlowState({
      nodes: [{ id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 1' } }]
    });

    act(() => {
      result.current.takeSnapshot(state1);
    });

    // Undo to create future
    act(() => {
      result.current.undo();
    });

    expect(result.current.history.future).toHaveLength(1);

    // Create new snapshot should clear future
    const state2 = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 2' } }]
    });

    act(() => {
      result.current.takeSnapshot(state2);
    });

    expect(result.current.history.future).toHaveLength(0);
  });

  test('should limit history to 50 entries', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Create 51 snapshots
    for (let i = 0; i < 51; i++) {
      const state = createMockFlowState({
        nodes: [{ id: `${i}`, type: 'default', position: { x: 0, y: 0 }, data: { label: `Node ${i}` } }]
      });

      act(() => {
        result.current.takeSnapshot(state);
      });
    }

    // Past should have 50 entries (limit)
    expect(result.current.history.past.length).toBeLessThanOrEqual(50);
  });

  test('should correctly handle FlowState with nodes and edges', () => {
    const initialState: any = { nodes: [], edges: [] };
    const { result } = renderHook(() => useUndoRedo(initialState));

    const stateWithEdges: any = {
      nodes: [
        { id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'Node 1' } },
        { id: '2', type: 'default', position: { x: 100, y: 0 }, data: { label: 'Node 2' } }
      ],
      edges: [
        { id: 'e1-2', source: '1', target: '2', type: 'default' }
      ]
    };

    act(() => {
      result.current.takeSnapshot(stateWithEdges);
    });

    expect(result.current.history.present).toEqual(stateWithEdges);
    expect(result.current.history.present.nodes).toHaveLength(2);
    expect(result.current.history.present.edges).toHaveLength(1);
  });
});

// ============================================
// Undo Tests
// ============================================

describe('useUndoRedo - Undo', () => {
  test('should move present to future', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    const presentBeforeUndo = result.current.history.present;

    act(() => {
      result.current.undo();
    });

    expect(result.current.history.future).toHaveLength(1);
    expect(result.current.history.future[0]).toEqual(presentBeforeUndo);
  });

  test('should restore previous state from past', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    expect(result.current.history.present).toEqual(initialState);
  });

  test('should set canUndo false when past empty', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.canUndo).toBe(false);
  });

  test('should set canRedo true after undo', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);
  });

  test('should be no-op when canUndo is false', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const presentBefore = result.current.history.present;

    act(() => {
      result.current.undo();
    });

    expect(result.current.history.present).toEqual(presentBefore);
    expect(result.current.history.past).toHaveLength(0);
    expect(result.current.history.future).toHaveLength(0);
  });
});

// ============================================
// Redo Tests
// ============================================

describe('useUndoRedo - Redo', () => {
  test('should move present back to past', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    const presentBeforeRedo = result.current.history.present;

    act(() => {
      result.current.redo();
    });

    expect(result.current.history.past).toHaveLength(1);
    expect(result.current.history.past[0]).toEqual(presentBeforeRedo);
  });

  test('should restore future state to present', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    act(() => {
      result.current.redo();
    });

    expect(result.current.history.present).toEqual(newState);
  });

  test('should set canRedo false when future empty', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.redo();
    });

    expect(result.current.canRedo).toBe(false);
  });

  test('should set canUndo true after redo', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    act(() => {
      result.current.redo();
    });

    expect(result.current.canUndo).toBe(true);
  });

  test('should be no-op when canRedo is false', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const presentBefore = result.current.history.present;

    act(() => {
      result.current.redo();
    });

    expect(result.current.history.present).toEqual(presentBefore);
  });
});

// ============================================
// Reset History Tests
// ============================================

describe('useUndoRedo - Reset History', () => {
  test('should clear past and future', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Create multiple snapshots
    for (let i = 0; i < 3; i++) {
      const state = createMockFlowState({
        nodes: [{ id: `${i}`, type: 'default', position: { x: 0, y: 0 }, data: { label: `Node ${i}` } }]
      });

      act(() => {
        result.current.takeSnapshot(state);
      });
    }

    // Undo twice to create future
    act(() => {
      result.current.undo();
      result.current.undo();
    });

    expect(result.current.history.past.length).toBeGreaterThan(0);
    expect(result.current.history.future.length).toBeGreaterThan(0);

    act(() => {
      result.current.resetHistory();
    });

    expect(result.current.history.past).toHaveLength(0);
    expect(result.current.history.future).toHaveLength(0);
  });

  test('should reset present to initialState', () => {
    const initialState = createMockFlowState({
      nodes: [{ id: 'initial', type: 'default', position: { x: 0, y: 0 }, data: { label: 'Initial' } }]
    });

    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: 'new', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    expect(result.current.history.present).not.toEqual(initialState);

    act(() => {
      result.current.resetHistory();
    });

    expect(result.current.history.present).toEqual(initialState);
  });

  test('should set canUndo and canRedo false', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const newState = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'New' } }]
    });

    act(() => {
      result.current.takeSnapshot(newState);
    });

    act(() => {
      result.current.undo();
    });

    expect(result.current.canUndo).toBe(false);  // Past is empty after undo
    expect(result.current.canRedo).toBe(true);   // Future has the undone state

    act(() => {
      result.current.resetHistory();
    });

    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(false);
  });
});

// ============================================
// Edge Cases
// ============================================

describe('useUndoRedo - Edge Cases', () => {
  test('should handle undo/redo with single state', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Single snapshot
    const state1 = createMockFlowState({
      nodes: [{ id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 1' } }]
    });

    act(() => {
      result.current.takeSnapshot(state1);
    });

    // Undo
    act(() => {
      result.current.undo();
    });

    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(true);

    // Redo
    act(() => {
      result.current.redo();
    });

    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  test('should handle multiple snapshots in sequence', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const states = [
      createMockFlowState({ nodes: [{ id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 1' } }] }),
      createMockFlowState({ nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 2' } }] }),
      createMockFlowState({ nodes: [{ id: '3', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 3' } }] })
    ];

    states.forEach(state => {
      act(() => {
        result.current.takeSnapshot(state);
      });
    });

    expect(result.current.history.past).toHaveLength(3);
    expect(result.current.history.present).toEqual(states[2]);

    // Undo all
    act(() => {
      result.current.undo();
      result.current.undo();
      result.current.undo();
    });

    expect(result.current.history.present).toEqual(initialState);
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(true);

    // Redo all
    act(() => {
      result.current.redo();
      result.current.redo();
      result.current.redo();
    });

    expect(result.current.history.present).toEqual(states[2]);
  });

  test('should enforce history limit of 50 states', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Create 60 snapshots
    for (let i = 0; i < 60; i++) {
      const state = createMockFlowState({
        nodes: [{ id: `${i}`, type: 'default', position: { x: 0, y: 0 }, data: { label: `State ${i}` } }]
      });

      act(() => {
        result.current.takeSnapshot(state);
      });
    }

    // History should be limited to 50
    expect(result.current.history.past.length).toBe(50);

    // Oldest states should be dropped
    expect(result.current.history.past[0].nodes[0].id).not.toBe('0');
    expect(result.current.history.past[0].nodes[0].id).toBe('9'); // First kept state (0-8 dropped)
  });

  test('should handle rapid snapshot creation', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    // Rapid snapshot creation
    for (let i = 0; i < 20; i++) {
      const state = createMockFlowState({
        nodes: [{ id: `${i}`, type: 'default', position: { x: i * 10, y: 0 }, data: { label: `Node ${i}` } }]
      });

      act(() => {
        result.current.takeSnapshot(state);
      });
    }

    expect(result.current.history.past).toHaveLength(20);
    expect(result.current.history.present.nodes[0].id).toBe('19');
  });

  test('should handle undo then new snapshot (clears future)', () => {
    const initialState = createMockFlowState();
    const { result } = renderHook(() => useUndoRedo(initialState));

    const state1 = createMockFlowState({
      nodes: [{ id: '1', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 1' } }]
    });

    const state2 = createMockFlowState({
      nodes: [{ id: '2', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 2' } }]
    });

    act(() => {
      result.current.takeSnapshot(state1);
      result.current.takeSnapshot(state2);
    });

    // Undo
    act(() => {
      result.current.undo();
    });

    expect(result.current.history.future).toHaveLength(1);

    // New snapshot should clear future
    const state3 = createMockFlowState({
      nodes: [{ id: '3', type: 'default', position: { x: 0, y: 0 }, data: { label: 'State 3' } }]
    });

    act(() => {
      result.current.takeSnapshot(state3);
    });

    expect(result.current.history.future).toHaveLength(0);
    expect(result.current.canRedo).toBe(false);
  });

  test('should handle complex node and edge structures', () => {
    const initialState: any = {
      nodes: [],
      edges: []
    };

    const { result } = renderHook(() => useUndoRedo(initialState));

    const complexState: any = {
      nodes: [
        { id: '1', type: 'input', position: { x: 0, y: 0 }, data: { label: 'Input' } },
        { id: '2', type: 'default', position: { x: 100, y: 0 }, data: { label: 'Process' } },
        { id: '3', type: 'output', position: { x: 200, y: 0 }, data: { label: 'Output' } }
      ],
      edges: [
        { id: 'e1-2', source: '1', target: '2', type: 'smoothstep', animated: true },
        { id: 'e2-3', source: '2', target: '3', type: 'smoothstep', animated: true }
      ]
    };

    act(() => {
      result.current.takeSnapshot(complexState);
    });

    expect(result.current.history.present.nodes).toHaveLength(3);
    expect(result.current.history.present.edges).toHaveLength(2);

    act(() => {
      result.current.undo();
    });

    expect(result.current.history.present.nodes).toHaveLength(0);
    expect(result.current.history.present.edges).toHaveLength(0);
  });
});
