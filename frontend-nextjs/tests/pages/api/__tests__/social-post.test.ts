const mockGetServerSession = jest.fn();

jest.mock("next-auth/next", () => ({ getServerSession: mockGetServerSession }));
jest.mock("@/pages/api/auth/[...nextauth]", () => ({ authOptions: { providers: [] } }));

import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";
import handler from "@/pages/api/social/post";

const mockFetch = jest.fn();
const mockSession = {
  user: { id: "user-1", email: "user@example.com" },
};

function backendJson(body: any, ok = true, status = 200): any {
  return { ok, status, json: async () => body };
}

describe("pages/api/social/post", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetServerSession.mockResolvedValue(mockSession);
    (global as any).fetch = mockFetch;
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  const invoke = async (method: RequestMethod = "POST", body: any = {}, session: any = mockSession) => {
    mockGetServerSession.mockResolvedValue(session);
    const { req, res } = createMocks({ method, body }) as any;
    await handler(req, res);
    return res;
  };

  it("rejects non-POST methods with 405 and an Allow header", async () => {
    const res = await invoke("GET");
    expect(res._getStatusCode()).toBe(405);
    expect(res._getJSONData().message).toContain("Method GET Not Allowed");
    expect(res.getHeader("Allow")).toEqual(["POST"]);
  });

  it("returns 401 without a session", async () => {
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] }, null);
    expect(res._getStatusCode()).toBe(401);
    expect(res._getJSONData()).toEqual({ message: "Unauthorized" });
  });

  it("returns 400 when text is missing", async () => {
    const res = await invoke("POST", { platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe("Text is required");
  });

  it("returns 400 when no platforms are given", async () => {
    const res = await invoke("POST", { text: "hi" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "At least one platform must be specified",
    );
  });

  it("returns 400 when text exceeds 5000 characters", async () => {
    const res = await invoke("POST", {
      text: "x".repeat(5001),
      platforms: ["twitter"],
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "Text cannot exceed 5000 characters",
    );
  });

  it("returns 400 for unsupported platforms", async () => {
    const res = await invoke("POST", {
      text: "hi",
      platforms: ["twitter", "tiktok"],
    });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Invalid platforms: tiktok");
  });

  it("returns 400 for non-string platform entries instead of crashing", async () => {
    const res = await invoke("POST", { text: "hi", platforms: ["twitter", 123] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toContain("Invalid platforms");
  });

  it("returns 400 when platforms is not an array", async () => {
    const res = await invoke("POST", { text: "hi", platforms: "twitter" });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe(
      "At least one platform must be specified",
    );
  });

  it("omits the X-User-ID header when the session user has no id or email", async () => {
    mockFetch.mockResolvedValue(backendJson({ success: true, platform_results: {} }));
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] }, { user: {} });
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["X-User-ID"]).toBeUndefined();
  });

  it("forwards a valid post with optional fields and maps the success payload", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        success: true,
        post_id: "post-1",
        platform_results: {
          twitter: { success: true, id: "tweet-1" },
        },
      }),
    );
    const res = await invoke("POST", {
      text: "Hello world",
      platforms: ["twitter"],
      scheduled_for: "2026-09-01T10:00:00Z",
      media_urls: ["https://example.com/img.png"],
      link_url: "https://example.com",
    });
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.post_id).toBe("post-1");
    expect(body.platform_results.twitter).toEqual({ success: true, id: "tweet-1" });
    expect(body.scheduled).toBe(false);
    expect(body.message).toBe("Successfully posted to 1 platform");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/social/post",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-User-ID": "user-1",
        }),
      }),
    );
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      text: "Hello world",
      platforms: ["twitter"],
      scheduled_for: "2026-09-01T10:00:00Z",
      media_urls: ["https://example.com/img.png"],
      link_url: "https://example.com",
    });
  });

  it("accepts platform names case-insensitively", async () => {
    mockFetch.mockResolvedValue(backendJson({ success: true, platform_results: {} }));
    const res = await invoke("POST", { text: "hi", platforms: ["TWITTER"] });
    expect(res._getStatusCode()).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body).platforms).toEqual(["TWITTER"]);
  });

  it("returns the scheduled message when the post is scheduled", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        success: true,
        scheduled: true,
        scheduled_for: "2026-09-01T10:00:00Z",
        platform_results: {},
      }),
    );
    const res = await invoke("POST", {
      text: "hi",
      platforms: ["twitter"],
      scheduled_for: "2026-09-01T10:00:00Z",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe("Post scheduled successfully");
  });

  it("reports partial failures in the message", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        success: true,
        platform_results: {
          twitter: { success: true },
          linkedin: { success: false, error: "banned" },
        },
      }),
    );
    const res = await invoke("POST", { text: "hi", platforms: ["twitter", "linkedin"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe(
      "Partially successful: Posted to twitter. Failed: linkedin",
    );
  });

  it("reports total failure when every platform failed", async () => {
    mockFetch.mockResolvedValue(
      backendJson({
        success: false,
        platform_results: { twitter: { success: false, error: "x" } },
      }),
    );
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe("Failed to post to any platform");
  });

  it("does not crash when the backend omits platform_results", async () => {
    mockFetch.mockResolvedValue(backendJson({ success: true, post_id: "post-1" }));
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData().message).toBe("Failed to post to any platform");
  });

  it("maps a backend rate limit (429) into a client 429", async () => {
    mockFetch.mockResolvedValue(backendJson({ detail: "Too many posts" }, false, 429));
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(429);
    expect(res._getJSONData().message).toContain("Rate limit exceeded");
    expect(res._getJSONData().errors).toEqual(["Too many posts"]);
  });

  it("maps a backend 400 into a client 400 with detail", async () => {
    mockFetch.mockResolvedValue(backendJson({ detail: "Duplicate content" }, false, 400));
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(400);
    expect(res._getJSONData().message).toBe("Duplicate content");
  });

  it("returns 500 when the backend is unreachable", async () => {
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await invoke("POST", { text: "hi", platforms: ["twitter"] });
    expect(res._getStatusCode()).toBe(500);
    expect(res._getJSONData()).toEqual({
      message: "Failed to post to social media",
      errors: ["ECONNREFUSED"],
    });
  });
});
