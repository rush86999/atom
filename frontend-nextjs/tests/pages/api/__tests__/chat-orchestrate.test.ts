import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/chat/orchestrate";

const mockFetch = jest.fn();

function jsonFetch(ok: boolean, status: number, body: any) {
  return {
    ok,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as any;
}

describe("pages/api/chat/orchestrate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (method = "POST", body: any = {}) => {
    const { req, res } = createMocks({ method: method as RequestMethod, body }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 for non-POST methods", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({
      success: false,
      message: "Method not allowed",
      type: "error",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when required fields are missing", async () => {
    const res = await invoke("POST", { message: "hello" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData()).toEqual({
      success: false,
      message: "Missing required fields: userId and message",
      type: "error",
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 400 when the message is missing", async () => {
    const res = await invoke("POST", { userId: "user-1" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Missing required fields");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("forwards the chat message to the backend and maps the response", async () => {
    mockFetch.mockResolvedValue(
      jsonFetch(true, 200, {
        response: "Workflow started",
        type: "workflow",
        metadata: { workflowId: "wf-1" },
        session_id: "sess-backend",
      }),
    );
    const res = await invoke("POST", {
      userId: "user-1",
      message: "run the deploy workflow",
      sessionId: "sess-req",
      processId: "proc-1",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "Workflow started",
      type: "workflow",
      metadata: { workflowId: "wf-1" },
      sessionId: "sess-req",
    });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/v1/ai/chat");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      user_id: "user-1",
      message: "run the deploy workflow",
      session_id: "sess-req",
      process_id: "proc-1",
    });
  });

  it("falls back to the backend message field and generated session id", async () => {
    jest.spyOn(Date, "now").mockReturnValue(1234567890);
    mockFetch.mockResolvedValue(
      jsonFetch(true, 200, { message: "from message field" }),
    );
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      success: true,
      message: "from message field",
      type: "text",
      metadata: undefined,
      sessionId: "session_1234567890",
    });
  });

  it("falls back to a default message when the backend payload is empty", async () => {
    jest.spyOn(Date, "now").mockReturnValue(42);
    mockFetch.mockResolvedValue(jsonFetch(true, 200, {}));
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe("Message processed");
    expect(res._getJSONData().sessionId).toBe("session_42");
  });

  it("honours a custom API base URL from the environment", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://backend.example.com";
    mockFetch.mockResolvedValue(jsonFetch(true, 200, { response: "ok" }));
    const res = await invoke("POST", { userId: "u", message: "m" });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://backend.example.com/api/v1/ai/chat",
    );
  });

  it("returns the fallback response when the backend replies with an error status", async () => {
    mockFetch.mockResolvedValue(jsonFetch(false, 500, { error: "boom" }));
    const res = await invoke("POST", { userId: "u", message: "m" });
    expect(res._getStatusCode()).toBe(200);
    const data = res._getJSONData();
    expect(data.success).toBe(true);
    expect(data.type).toBe("text");
    expect(data.metadata.suggestedActions).toHaveLength(3);
    expect(data.sessionId).toMatch(/^session_\d+$/);
    expect(console.error).toHaveBeenCalled();
  });

  it("returns the fallback response when the backend fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    const res = await invoke("POST", { userId: "u", message: "m" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().success).toBe(true);
    expect(res._getJSONData().message).toContain("I received your message");
    expect(console.error).toHaveBeenCalled();
  });
});
