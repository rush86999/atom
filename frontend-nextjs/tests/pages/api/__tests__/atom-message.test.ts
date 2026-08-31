const mockHandleMessage = jest.fn();
jest.mock("@/project/functions/atom-agent/src/handler", () => ({
  handleMessage: mockHandleMessage,
}));

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/atom/message";

describe("pages/api/atom/message", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const invoke = async (method: RequestMethod = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getData()).toContain("Method GET Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 400 when message is missing", async () => {
    const res = await invoke("POST", { userId: "u-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      text: "",
      error: "Missing message in request body",
    });
    expect(mockHandleMessage).not.toHaveBeenCalled();
  });

  it("returns 400 when userId is missing", async () => {
    const res = await invoke("POST", { message: "hello" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      text: "",
      error: "Missing userId in request body",
    });
    expect(mockHandleMessage).not.toHaveBeenCalled();
  });

  it("calls handleMessage with interface type, message, userId, and options", async () => {
    mockHandleMessage.mockResolvedValue({ text: "echo: hello" });
    const res = await invoke("POST", {
      message: "hello",
      userId: "user-9",
      conversationId: "conv-1",
      intentName: "greeting",
      entities: { name: "Atom" },
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ text: "echo: hello" });
    expect(mockHandleMessage).toHaveBeenCalledWith(
      "text",
      "hello",
      "user-9",
      expect.objectContaining({
        userId: "user-9",
        conversationId: "conv-1",
        intentName: "greeting",
        entities: { name: "Atom" },
      }),
    );
  });

  it("returns 500 with the error message when handleMessage throws", async () => {
    mockHandleMessage.mockRejectedValue(new Error("agent crashed"));
    const res = await invoke("POST", { message: "hi", userId: "u-1" });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({ text: "", error: "agent crashed" });
  });
});
