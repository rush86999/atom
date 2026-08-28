import { createMocks } from "node-mocks-http";
import gitlabHealth from "@/pages/api/integrations/gitlab/health";
import microsoftHealth from "@/pages/api/integrations/microsoft/health";
import shopifyHealth from "@/pages/api/integrations/shopify/health";

const cases: Array<[string, any, string]> = [
  ["gitlab", gitlabHealth, "Gitlab Health"],
  ["microsoft", microsoftHealth, "Microsoft Health"],
  ["shopify", shopifyHealth, "Shopify Health"],
];

describe.each(cases)("pages/api/integrations/%s/health", (_name, handler, service) => {
  it("returns healthy service payload for GET", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(200);
    const body = res._getJSONData();
    expect(body.success).toBe(true);
    expect(body.service).toBe(service);
    expect(typeof body.timestamp).toBe("string");
    expect(Number.isNaN(Date.parse(body.timestamp))).toBe(false);
  });

  it("rejects non-GET methods with 405", async () => {
    for (const method of ["POST", "PUT", "DELETE"] as const) {
      const { req, res } = createMocks({ method }) as any;
      await handler(req, res);
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    }
  });
});
