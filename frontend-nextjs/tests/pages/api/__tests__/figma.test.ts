const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import analyticsHandler from "@/pages/api/integrations/figma/analytics";
import filesHandler from "@/pages/api/integrations/figma/files";
import profileHandler from "@/pages/api/integrations/figma/profile";

const jsonResponse = (ok: boolean, status: number, data: any): any => ({
  ok,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.PYTHON_API_SERVICE_BASE_URL;
});

// Every handler in this family proxies to a single fixed backend endpoint and
// maps non-ok backend responses to a 400. `allowedMethod` is the only method
// the handler accepts; anything else gets a 405 with an Allow header.
const runFigmaSuite = (
  describeName: string,
  handler: any,
  backendUrl: string,
  allowedMethod: "POST" | "GET",
  payload: any,
) => {
  describe(describeName, () => {
    const invoke = async (method = allowedMethod, body?: any) => {
      const { req, res } = createMocks({ method, body }) as any;
      await handler(req, res);
      return res;
    };

    it(`rejects non-${allowedMethod} methods with 405 and an Allow header`, async () => {
      const other = allowedMethod === "POST" ? "GET" : "POST";
      const res = await invoke(other);
      expect(res._getStatusCode()).toBe(405);
      expect(res.getHeader("Allow")).toEqual([allowedMethod]);
      expect(res._getData()).toBe(`Method ${other} Not Allowed`);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("returns the backend payload on success", async () => {
      mockFetch.mockResolvedValue(jsonResponse(true, 200, payload));
      const res = await invoke(allowedMethod, payload);
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual(payload);
      expect(mockFetch).toHaveBeenCalledWith(
        backendUrl,
        allowedMethod === "POST"
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            }
          : {
              method: "GET",
              headers: { "Content-Type": "application/json" },
            },
      );
    });

    it("maps non-ok backend responses to 400 with the payload", async () => {
      mockFetch.mockResolvedValue(
        jsonResponse(false, 500, { error: "figma unavailable" }),
      );
      const res = await invoke();
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: "figma unavailable" });
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({
        success: false,
        error: "Endpoint failed",
      });
      expect(console.error).toHaveBeenCalled();
    });

    it("honours PYTHON_API_SERVICE_BASE_URL when configured", async () => {
      process.env.PYTHON_API_SERVICE_BASE_URL = "http://python:5058";
      mockFetch.mockResolvedValue(jsonResponse(true, 200, {}));
      const res = await invoke();
      expect(res._getStatusCode()).toBe(200);
      expect(mockFetch.mock.calls[0][0]).toBe(backendUrl.replace(
        "http://127.0.0.1:8000",
        "http://python:5058",
      ));
    });
  });
};

runFigmaSuite(
  "pages/api/integrations/figma/analytics",
  analyticsHandler,
  "http://127.0.0.1:8000/api/figma/analytics",
  "POST",
  { files_analyzed: 4 },
);

runFigmaSuite(
  "pages/api/integrations/figma/files",
  filesHandler,
  "http://127.0.0.1:8000/api/figma/files",
  "POST",
  { files: [{ id: "f1", name: "Landing page" }] },
);

runFigmaSuite(
  "pages/api/integrations/figma/profile",
  profileHandler,
  "http://127.0.0.1:8000/api/figma/user",
  "GET",
  { id: "u1", handle: "atom-user" },
);
