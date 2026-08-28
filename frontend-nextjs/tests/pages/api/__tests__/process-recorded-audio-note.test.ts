import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/process-recorded-audio-note";

describe("pages/api/process-recorded-audio-note", () => {
  it("returns ok for any request (route is disabled)", async () => {
    for (const method of ["POST", "GET", "PUT"] as const) {
      const { req, res } = createMocks({ method }) as any;
      await handler(req, res);
      expect(res._getStatusCode()).toBe(200);
      expect(res._getJSONData()).toEqual({ ok: true });
    }
  });
});
