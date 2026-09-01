/**
 * Canvas WS frame contract (lib/canvasFrame).
 *
 * Regression (2026-08-31): every non-close `canvas:update` frame was applied
 * as canvas content, so the `email_send` status broadcast ({status, payload})
 * replaced the drafted email in the open canvas — "the original draft is
 * missing". The durable store was untouched. These tests pin the contract:
 * event frames never write content; content frames (update/present/legacy)
 * pass through.
 */
import { isCanvasContentFrame } from "../canvasFrame";

describe("isCanvasContentFrame", () => {
  it("accepts update frames (canvas_crud echo / canvasSync)", () => {
    expect(
      isCanvasContentFrame({
        action: "update",
        canvas_id: "c-1",
        data: { to: "a@b.com", subject: "s", body: "hi" },
      })
    ).toBe(true);
  });

  it("accepts present frames (tools/canvas_tool)", () => {
    expect(
      isCanvasContentFrame({
        action: "present",
        component: "chart",
        data: { data: { series: [] }, title: "Chart" },
      })
    ).toBe(true);
  });

  it("accepts legacy frames without an action", () => {
    expect(isCanvasContentFrame({ canvas_id: "c-1", content: "text" })).toBe(true);
  });

  it("rejects email_send status frames — the draft clobberer", () => {
    expect(
      isCanvasContentFrame({
        action: "email_send",
        canvas_id: "c-1",
        canvas_type: "email",
        component: "email",
        data: { status: "failed", payload: { to: ["mark@x.ca"], cc: [], subject: "Re: Quote" } },
      })
    ).toBe(false);
  });

  it("rejects mini_app_state frames (MiniAppHarness preview)", () => {
    expect(isCanvasContentFrame({ action: "mini_app_state", data: { state: {} } })).toBe(false);
  });

  it("is null/undefined-safe", () => {
    expect(isCanvasContentFrame(null)).toBe(false);
    expect(isCanvasContentFrame(undefined)).toBe(false);
    expect(isCanvasContentFrame("frame")).toBe(false);
  });
});
