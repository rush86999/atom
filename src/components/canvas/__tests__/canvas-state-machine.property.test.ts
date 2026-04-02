import { describe, test, expect } from 'vitest';
import * as fc from 'fast-check';
import { canvasStateMachine, CanvasState, CanvasAction } from '../canvas-state-machine';

describe('Canvas State Machine Property Tests', () => {
  test('state transitions are valid from any state', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'drawing', 'selecting', 'dragging', 'resizing'),
        fc.constantFrom<CanvasAction>('startDrawing', 'startSelecting', 'startDragging', 'startResizing', 'finish', 'cancel'),
        (currentState, action) => {
          const machine = canvasStateMachine(currentState);
          const nextState = machine.transition(action);

          // Property: Next state is always valid (never undefined/null)
          expect(nextState).toBeDefined();

          // Property: Next state is one of the valid states
          expect(['idle', 'drawing', 'selecting', 'dragging', 'resizing']).toContain(nextState);
        }
      ),
      { numRuns: 200 }
    );
  });

  test('cancelling from any state returns to idle', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('drawing', 'selecting', 'dragging', 'resizing'),
        (activeState) => {
          const machine = canvasStateMachine(activeState);
          const nextState = machine.transition('cancel');

          // Property: Cancel always returns to idle
          expect(nextState).toBe('idle');
        }
      ),
      { numRuns: 100 }
    );
  });

  test('state payload integrity preserved across transitions', () => {
    fc.assert(
      fc.property(
        fc.record({
          x: fc.integer(),
          y: fc.integer(),
          width: fc.integer({ min: 1 }),
          height: fc.integer({ min: 1 }),
          selection: fc.array(fc.uuid())
        }),
        (payload) => {
          const machine = canvasStateMachine('idle');
          machine.transition('startSelecting', payload);
          machine.transition('finish');

          // Property: Final state preserves payload data
          const finalState = machine.getState();
          const finalPayload = machine.getPayload();
          expect(finalPayload.x).toBe(payload.x);
          expect(finalPayload.y).toBe(payload.y);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('invalid transition does not corrupt state', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'drawing', 'selecting'),
        fc.string(), // Invalid action names
        (currentState, invalidAction) => {
          const machine = canvasStateMachine(currentState);
          const beforeState = machine.getState();
          const beforePayload = machine.getPayload();

          // Property: Invalid action doesn't change state
          const nextState = machine.transition(invalidAction as any);
          expect(nextState).toBe(currentState);
          expect(machine.getState()).toBe(beforeState);
          expect(machine.getPayload()).toEqual(beforePayload);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('finish action always returns to idle', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('drawing', 'selecting', 'dragging', 'resizing'),
        (activeState) => {
          const machine = canvasStateMachine(activeState);
          const nextState = machine.transition('finish');

          // Property: Finish always returns to idle
          expect(nextState).toBe('idle');
        }
      ),
      { numRuns: 100 }
    );
  });

  test('state machine can handle rapid transitions', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.constantFrom<CanvasAction>('startDrawing', 'startSelecting', 'startDragging', 'startResizing', 'finish', 'cancel'),
          { minLength: 10, maxLength: 50 }
        ),
        (actions) => {
          const machine = canvasStateMachine('idle');

          // Property: Machine handles all transitions without crashing
          expect(() => {
            for (const action of actions) {
              machine.transition(action);
            }
          }).not.toThrow();

          // Property: Final state is always valid
          const finalState = machine.getState();
          expect(['idle', 'drawing', 'selecting', 'dragging', 'resizing']).toContain(finalState);
        }
      ),
      { numRuns: 50 }
    );
  });

  test('payload updates are preserved', () => {
    fc.assert(
      fc.property(
        fc.integer(),
        fc.integer(),
        (x, y) => {
          const machine = canvasStateMachine('idle');

          // Property: Payload updates are preserved
          machine.transition('startDrawing', { x, y });
          const payload = machine.getPayload();
          expect(payload.x).toBe(x);
          expect(payload.y).toBe(y);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('multiple state machines do not share state', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'selecting', 'dragging', 'resizing'),
        fc.constantFrom<CanvasState>('idle', 'selecting', 'dragging', 'resizing'),
        (state1, state2) => {
          const machine1 = canvasStateMachine(state1);
          const machine2 = canvasStateMachine(state2);

          // Property: Machines start with correct states
          expect(machine1.getState()).toBe(state1);
          expect(machine2.getState()).toBe(state2);

          // Both machines can transition independently
          machine1.transition('cancel'); // Always goes to idle
          machine2.transition('finish'); // Always goes to idle

          // Property: Both machines end in idle independently
          expect(machine1.getState()).toBe('idle');
          expect(machine2.getState()).toBe('idle');
        }
      ),
      { numRuns: 50 }
    );
  });

  test('idempotency - identical operations produce same result', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'drawing', 'selecting'),
        fc.constantFrom<CanvasAction>('cancel', 'finish'),
        (initialState, action) => {
          const machine1 = canvasStateMachine(initialState);
          const machine2 = canvasStateMachine(initialState);

          // Perform same action on both machines
          const result1 = machine1.transition(action);
          const result2 = machine2.transition(action);

          // Property: Identical operations produce identical results
          expect(result1).toBe(result2);
          expect(machine1.getState()).toBe(machine2.getState());
          expect(machine1.getPayload()).toEqual(machine2.getPayload());
        }
      ),
      { numRuns: 100 }
    );
  });

  test('idempotency - multiple cancel operations converge to idle', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('drawing', 'selecting', 'dragging', 'resizing'),
        fc.array(fc.constantFrom('cancel' as CanvasAction), { minLength: 2, maxLength: 10 }),
        (initialState, cancelActions) => {
          const machine = canvasStateMachine(initialState);

          // Apply multiple cancel operations
          for (const action of cancelActions) {
            machine.transition(action);
          }

          // Property: Multiple cancels always converge to idle
          expect(machine.getState()).toBe('idle');
        }
      ),
      { numRuns: 50 }
    );
  });

  test('reachability - all valid states reachable from idle', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('drawing', 'selecting', 'dragging', 'resizing'),
        (targetState) => {
          const machine = canvasStateMachine('idle');

          // Map target states to their initiating actions
          const actionMap: Record<CanvasState, CanvasAction> = {
            drawing: 'startDrawing',
            selecting: 'startSelecting',
            dragging: 'startDragging',
            resizing: 'startResizing',
            idle: 'cancel'
          };

          const action = actionMap[targetState];
          const nextState = machine.transition(action);

          // Property: All states reachable from idle
          expect(nextState).toBe(targetState);
        }
      ),
      { numRuns: 50 }
    );
  });

  test('reachability - can return to any state from idle', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.constantFrom<CanvasAction>('startDrawing', 'startSelecting', 'startDragging', 'startResizing', 'finish', 'cancel'),
          { minLength: 1, maxLength: 20 }
        ),
        (actions) => {
          const machine = canvasStateMachine('idle');

          // Apply sequence of actions
          for (const action of actions) {
            machine.transition(action);
          }

          // Property: Final state is always a valid state
          const finalState = machine.getState();
          expect(['idle', 'drawing', 'selecting', 'dragging', 'resizing']).toContain(finalState);

          // Property: Can always return to idle
          machine.transition('cancel');
          expect(machine.getState()).toBe('idle');
        }
      ),
      { numRuns: 100 }
    );
  });

  test('no invalid transitions - state machine rejects invalid operations', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'drawing', 'selecting'),
        fc.string().filter(s => !['startDrawing', 'startSelecting', 'startDragging', 'startResizing', 'finish', 'cancel'].includes(s)),
        (currentState, invalidAction) => {
          const machine = canvasStateMachine(currentState);
          const beforeState = machine.getState();
          const beforePayload = machine.getPayload();

          // Attempt invalid transition
          const nextState = machine.transition(invalidAction as any);

          // Property: Invalid action doesn't change state
          expect(nextState).toBe(beforeState);
          expect(machine.getState()).toBe(beforeState);
          expect(machine.getPayload()).toEqual(beforePayload);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('serialization roundtrip preserves state', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<CanvasState>('idle', 'drawing', 'selecting', 'dragging', 'resizing'),
        fc.record({
          x: fc.integer(),
          y: fc.integer(),
          width: fc.integer({ min: 1 }),
          height: fc.integer({ min: 1 }),
          selection: fc.array(fc.uuid())
        }),
        (initialState, initialPayload) => {
          const originalMachine = canvasStateMachine(initialState, initialPayload);

          // Serialize state
          const serialized = {
            state: originalMachine.getState(),
            payload: originalMachine.getPayload()
          };

          // Deserialize by creating new machine
          const restoredMachine = canvasStateMachine(serialized.state, serialized.payload);

          // Property: Deserialized state matches original
          expect(restoredMachine.getState()).toBe(originalMachine.getState());
          expect(restoredMachine.getPayload()).toEqual(originalMachine.getPayload());
        }
      ),
      { numRuns: 100 }
    );
  });

  test('command-based state machine testing with command sequences', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            action: fc.constantFrom<CanvasAction>('startDrawing', 'startSelecting', 'startDragging', 'startResizing', 'finish', 'cancel'),
            payload: fc.option(fc.record({
              x: fc.integer(),
              y: fc.integer(),
              width: fc.integer({ min: 1 }),
              height: fc.integer({ min: 1 })
            }))
          }),
          { minLength: 5, maxLength: 30 }
        ),
        (commands) => {
          const machine = canvasStateMachine('idle');

          // Property: Machine handles all commands without crashing
          expect(() => {
            for (const command of commands) {
              machine.transition(command.action, command.payload);
            }
          }).not.toThrow();

          // Property: Final state is always valid
          const finalState = machine.getState();
          expect(['idle', 'drawing', 'selecting', 'dragging', 'resizing']).toContain(finalState);
        }
      ),
      { numRuns: 50 }
    );
  });
});
