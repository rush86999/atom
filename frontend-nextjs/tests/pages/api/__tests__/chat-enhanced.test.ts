import { createMocks, RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/chat/enhanced";

const mockFetch = jest.fn();

const aiAnalysis = (overallSentiment: number) => ({
  analysis_id: "analysis-1",
  sentiment_scores: {
    overall_sentiment: overallSentiment,
    positive: 0.2,
    negative: 0.1,
    neutral: 0.7,
  },
  entities: [{ type: "person", value: "Alice", confidence: 0.9 }],
  intents: ["greeting"],
  context_relevance: 0.85,
  suggested_actions: ["search_docs"],
});

const aiResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const backendResponse = (body: any, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
});

describe("pages/api/chat/enhanced", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "warn").mockImplementation(() => {});
    jest.spyOn(console, "error").mockImplementation(() => {});
    (global as any).fetch = mockFetch;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  const invoke = async (method = "POST", body?: any) => {
    const { req, res } =
      method === "POST" && body !== undefined
        ? (createMocks({ method: method as RequestMethod, body }) as any)
        : (createMocks({ method: method as RequestMethod }) as any);
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData()).toEqual({
      success: false,
      message: "Method not allowed",
      type: "error",
    });
  });

  it("returns 400 when userId or message is missing", async () => {
    const noUser = await invoke("POST", { message: "hello" });
    expect(noUser._getStatusCode()).toBe(400);
    expect(noUser._getJSONData()).toEqual({
      success: false,
      message: "Missing required fields: userId and message",
      type: "error",
    });

    const noMessage = await invoke("POST", { userId: "user-1" });
    expect(noMessage._getStatusCode()).toBe(400);
  });

  it("falls back to the final response when the body cannot be read", async () => {
    const { req, res } = createMocks({ method: "POST" }) as any;
    req.body = undefined;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.type).toBe("text");
    expect(body.sessionId).toMatch(/^session_\d+$/);
    expect(body.metadata.suggestedActions).toHaveLength(3);
    expect(console.error).toHaveBeenCalled();
  });

  it("enhances the message for strongly negative sentiment", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse(aiAnalysis(-0.8)))
      .mockResolvedValueOnce(
        backendResponse({ response: "backend says hi", session_id: "be-sess" }),
      );
    const res = await invoke("POST", { userId: "user-1", message: "nothing works" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.type).toBe("enhanced");
    expect(body.message).toBe("backend says hi");
    expect(body.sessionId).toBe("be-sess");
    expect(body.metadata.aiAnalysis).toMatchObject({
      analysisId: "analysis-1",
      contextRelevance: 0.85,
      intents: ["greeting"],
    });
    expect(body.timestamp).toBeDefined();

    const backendCall = mockFetch.mock.calls[1];
    expect(backendCall[0]).toBe("http://127.0.0.1:8000/api/v1/ai/chat");
    expect(JSON.parse(backendCall[1].body).message).toBe(
      'I understand you\'re concerned about: "nothing works". Let me help you with that.',
    );
  });

  it("enhances the message for strongly positive sentiment", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse(aiAnalysis(0.9)))
      .mockResolvedValueOnce(backendResponse({ response: "ok" }));
    await invoke("POST", { userId: "user-1", message: "love this product" });
    const backendBody = JSON.parse(mockFetch.mock.calls[1][1].body);
    expect(backendBody.message).toBe(
      'Great to hear about: "love this product"! Here\'s some information that might help.',
    );
  });

  it("keeps the original message for neutral sentiment", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse(aiAnalysis(0.1)))
      .mockResolvedValueOnce(backendResponse({ response: "neutral reply" }));
    await invoke("POST", { userId: "user-1", message: "what time is it" });
    const backendBody = JSON.parse(mockFetch.mock.calls[1][1].body);
    expect(backendBody.message).toBe("what time is it");
  });

  it("forwards the authorization header and uses the backend message fallback", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse(aiAnalysis(0)))
      .mockResolvedValueOnce(
        backendResponse({ message: "backend message", audio_data: "aud" }),
      );
    const { req, res } = createMocks({
      method: "POST",
      headers: { authorization: "Bearer tok" },
      body: { userId: "user-1", message: "hi", sessionId: "sess-1" },
    }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.message).toBe("backend message");
    expect(body.sessionId).toBe("sess-1");
    expect(body.metadata.audioData).toBe("aud");
    expect(mockFetch.mock.calls[1][1].headers.Authorization).toBe("Bearer tok");
    expect(mockFetch.mock.calls[1][1].headers.Authorization).toBeDefined();
  });

  it("skips AI analysis when enableAIAnalysis is false", async () => {
    mockFetch.mockResolvedValueOnce(
      backendResponse({ response: "plain", type: "workflow" }),
    );
    const res = await invoke("POST", {
      userId: "user-1",
      message: "hi",
      enableAIAnalysis: false,
    });
    expect(res._getStatusCode()).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/v1/ai/chat");
    const body = res._getJSONData();
    expect(body.type).toBe("workflow");
    expect(body.metadata.aiAnalysis).toBeUndefined();
  });

  it("ignores the AI service when it replies non-OK", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse({}, false))
      .mockResolvedValueOnce(backendResponse({ response: "ok" }));
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().type).toBe("text");
    expect(res._getJSONData().metadata.aiAnalysis).toBeUndefined();
  });

  it("continues without AI when the analyze call throws", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("AI down"))
      .mockResolvedValueOnce(backendResponse({ response: "ok" }));
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe("ok");
    expect(console.warn).toHaveBeenCalled();
  });

  it("returns the AI-enhanced fallback when the backend replies non-OK", async () => {
    mockFetch
      .mockResolvedValueOnce(aiResponse(aiAnalysis(0)))
      .mockResolvedValueOnce(backendResponse({ error: "boom" }, false, 500));
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.type).toBe("enhanced");
    expect(body.message).toBe("hi");
    expect(body.metadata.aiAnalysis.analysisId).toBe("analysis-1");
    expect(body.metadata.suggestedActions).toHaveLength(3);
    expect(console.error).toHaveBeenCalled();
  });

  it("returns the plain fallback when both AI and the backend fail", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("AI down"))
      .mockRejectedValueOnce(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { userId: "user-1", message: "hi" });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.type).toBe("text");
    expect(body.sessionId).toMatch(/^session_\d+$/);
    expect(body.metadata.suggestedActions).toHaveLength(3);
  });
});
