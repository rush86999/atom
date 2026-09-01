/**
 * Canvas WS frame contract — shared by the canvas page (/canvas/[id]) and
 * the chat-embedded host (components/chat/canvas-host.tsx).
 *
 * A `canvas:update` frame is content-bearing ONLY when its `action` says so.
 * The backend declares every frame's semantics via `action`:
 *
 *   "update" / "present"  → `data` (or `data.data`) carries CANVAS CONTENT
 *                          (tools/canvas_crud_tool._broadcast_canvas_update,
 *                          tools/canvas_tool present flow)
 *   "close"               → drop the canvas (handled by each consumer)
 *   event actions         → `data` is a STATUS payload, never content —
 *                          e.g. email_send broadcasts {status, payload}.
 *
 * Regression (observed live 2026-08-31): the canvas consumers applied every
 * non-close frame as content, so a FAILED email send replaced the drafted
 * email body with the send-status object — "the original draft in the
 * canvas is missing". The durable store was untouched; only the view was
 * clobbered. Event frames must never write content.
 */

// Actions whose payload IS canvas content. Absent action = legacy frame,
// which predates event actions and carries content by contract.
const CANVAS_CONTENT_ACTIONS = new Set(["update", "present"]);

// Actions whose payload is a status/event, never canvas content. Extend
// this list when the backend gains a new event-style broadcast.
const CANVAS_EVENT_ACTIONS = new Set(["mini_app_state", "email_send"]);

export function isCanvasContentFrame(frame: unknown): boolean {
  if (!frame || typeof frame !== "object") return false;
  const action = (frame as Record<string, unknown>).action;
  if (typeof action === "string" && CANVAS_EVENT_ACTIONS.has(action)) {
    return false;
  }
  if (typeof action !== "string" || action === "") return true; // legacy
  return CANVAS_CONTENT_ACTIONS.has(action);
}
