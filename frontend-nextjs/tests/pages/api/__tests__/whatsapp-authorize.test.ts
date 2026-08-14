import { createMocks } from "node-mocks-http";
import handler from "@/pages/api/integrations/whatsapp/authorize";

describe("pages/api/integrations/whatsapp/authorize", () => {
  it("issues a 307 redirect to the unified OAuth initiate endpoint", async () => {
    const { req, res } = createMocks({ method: "GET" }) as any;
    await handler(req, res);
    expect(res._getStatusCode()).toBe(307);
    expect(res._getRedirectUrl()).toBe(
      "/api/v1/auth/oauth/whatsapp/initiate",
    );
  });
});
