/**
 * Canvas State Machine
 *
 * Manages canvas interaction states and transitions
 * States: idle, drawing, selecting, dragging, resizing
 */

export type CanvasState = 'idle' | 'drawing' | 'selecting' | 'dragging' | 'resizing';
export type CanvasAction =
  | 'startDrawing'
  | 'startSelecting'
  | 'startDragging'
  | 'startResizing'
  | 'finish'
  | 'cancel';

export interface CanvasStatePayload {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  selection?: string[];
  [key: string]: any;
}

export interface CanvasStateMachine {
  currentState: CanvasState;
  payload: CanvasStatePayload;
  transition: (action: CanvasAction, newPayload?: Partial<CanvasStatePayload>) => CanvasState;
  getState: () => CanvasState;
  getPayload: () => CanvasStatePayload;
}

// Valid state transitions
const TRANSITIONS: Record<CanvasState, CanvasAction[]> = {
  idle: ['startDrawing', 'startSelecting', 'startDragging', 'startResizing'],
  drawing: ['finish', 'cancel'],
  selecting: ['finish', 'cancel'],
  dragging: ['finish', 'cancel'],
  resizing: ['finish', 'cancel'],
};

/**
 * Create a canvas state machine
 */
export function canvasStateMachine(
  initialState: CanvasState = 'idle',
  initialPayload: CanvasStatePayload = {}
): CanvasStateMachine {
  let currentState: CanvasState = initialState;
  let payload: CanvasStatePayload = { ...initialPayload };

  return {
    currentState,
    payload,

    transition(action: CanvasAction, newPayload?: Partial<CanvasStatePayload>): CanvasState {
      // Check if transition is valid
      const validActions = TRANSITIONS[currentState];
      if (!validActions.includes(action)) {
        // Invalid action - return current state
        return currentState;
      }

      // Update payload if provided
      if (newPayload) {
        payload = { ...payload, ...newPayload };
      }

      // Perform transition
      switch (action) {
        case 'startDrawing':
          currentState = 'drawing';
          break;
        case 'startSelecting':
          currentState = 'selecting';
          break;
        case 'startDragging':
          currentState = 'dragging';
          break;
        case 'startResizing':
          currentState = 'resizing';
          break;
        case 'finish':
        case 'cancel':
          currentState = 'idle';
          break;
        default:
          // Invalid action - stay in current state
          break;
      }

      this.currentState = currentState;
      this.payload = payload;

      return currentState;
    },

    getState(): CanvasState {
      return currentState;
    },

    getPayload(): CanvasStatePayload {
      return { ...payload };
    },
  };
}
