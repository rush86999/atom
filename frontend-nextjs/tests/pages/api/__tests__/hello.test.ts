import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/hello";

describe("pages/api/hello", () => {
  it("returns the sample name payload", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({ name: "John Doe" });
  });
});
