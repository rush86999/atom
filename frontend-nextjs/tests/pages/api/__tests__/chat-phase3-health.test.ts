import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/chat/phase3-health";

const mockFetch = jest.fn();

const availableResponse = (features: any = {}) => ({
  ok: true,
  json: async () => ({
    features: {
      sentiment_analysis: true,
      entity_extraction: true,
      intent_detection: true,
      phase3_enhanced_chat: true,
      ...features,
    },
  }),
});

describe("pages/api/chat/phase3-health", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global as any).fetch = mockFetch;
  });

  const invoke = async (method: RequestMethod = "GET") => {
    const { req, res } = createMocks({ method }) as any;
    await handler(req, res);
    return res;
  };

  it("returns 405 with unavailable status for non-GET methods", async () => {
    const res = await invoke("POST");
    expect(res._getStatusCode()).toBe(405);
    const body = res._getJSONData();
    expect(body.status).toBe("unavailable");
    expect(body.overall_health.enhanced_chat_ready).toBe(false);
    expect(body.recommendations).toContain("Use GET method for health check");
  });

  it("reports healthy when all three services respond", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("5062")) return Promise.resolve(availableResponse());
      return Promise.resolve(availableResponse());
    });
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.status).toBe("healthy");
    expect(body.overall_health).toEqual({
      ai_intelligence_available: true,
      chat_api_available: true,
      websocket_available: true,
      enhanced_chat_ready: true,
    });
    expect(body.services.phase3_ai_intelligence.status).toBe("available");
    expect(body.services.phase3_ai_intelligence.features).toEqual({
      sentiment_analysis: true,
      entity_extraction: true,
      intent_detection: true,
      context_aware_responses: true,
    });
    expect(body.services.main_chat_api.port).toBe(8000);
    expect(body.services.websocket_server.port).toBe(5060);
    expect(body.recommendations).toContain(
      "Enhanced chat with AI intelligence is ready for use",
    );
  });

  it("maps missing feature flags to false in the AI service", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(availableResponse({ sentiment_analysis: false, phase3_enhanced_chat: false })),
    );
    const res = await invoke("GET");
    const features = res._getJSONData().services.phase3_ai_intelligence.features;
    expect(features.sentiment_analysis).toBe(false);
    expect(features.context_aware_responses).toBe(false);
    expect(features.entity_extraction).toBe(true);
  });

  it("reports degraded when one service is down, with a recommendation", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("5062")) return Promise.reject(new Error("ECONNREFUSED"));
      return Promise.resolve(availableResponse());
    });
    const res = await invoke("GET");
    const body = res._getJSONData();
    expect(body.status).toBe("degraded");
    expect(body.overall_health.ai_intelligence_available).toBe(false);
    expect(body.overall_health.enhanced_chat_ready).toBe(false);
    expect(body.recommendations).toContain(
      "Start Phase 3 AI intelligence service on port 5062",
    );
  });

  it("reports unavailable when a service returns a non-OK status", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500 }),
    );
    const res = await invoke("GET");
    const body = res._getJSONData();
    expect(body.status).toBe("unavailable");
    expect(body.overall_health.enhanced_chat_ready).toBe(false);
    expect(body.recommendations).toEqual(
      expect.arrayContaining([
        "Start Phase 3 AI intelligence service on port 5062",
        "Start main chat API service on port 8000",
        "Start WebSocket server on port 5060",
      ]),
    );
  });

  it("returns unavailable status when all services are unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("all down"));
    const res = await invoke("GET");
    const body = res._getJSONData();
    expect(body.status).toBe("unavailable");
    expect(body.services.websocket_server.status).toBe("unavailable");
    expect(body.recommendations).toEqual(
      expect.arrayContaining([
        "Start Phase 3 AI intelligence service on port 5062",
        "Start main chat API service on port 8000",
        "Start WebSocket server on port 5060",
      ]),
    );
  });
});
