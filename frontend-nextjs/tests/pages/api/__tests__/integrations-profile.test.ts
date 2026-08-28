import { createMocks } from "node-mocks-http";
import type { RequestMethod } from "node-mocks-http";

import asanaProfile from "@/pages/api/integrations/asana/profile";
import boxProfile from "@/pages/api/integrations/box/profile";
import gitlabProfile from "@/pages/api/integrations/gitlab/profile";
import googleProfile from "@/pages/api/integrations/google/profile";
import hubspotProfile from "@/pages/api/integrations/hubspot/profile";
import jiraProfile from "@/pages/api/integrations/jira/profile";
import linearProfile from "@/pages/api/integrations/linear/profile";
import microsoftProfile from "@/pages/api/integrations/microsoft/profile";
import notionProfile from "@/pages/api/integrations/notion/profile";
import salesforceProfile from "@/pages/api/integrations/salesforce/profile";
import shopifyProfile from "@/pages/api/integrations/shopify/profile";
import stripeProfile from "@/pages/api/integrations/stripe/profile";
import trelloProfile from "@/pages/api/integrations/trello/profile";
import xeroProfile from "@/pages/api/integrations/xero/profile";
import zoomProfile from "@/pages/api/integrations/zoom/profile";

type Handler = (req: any, res: any) => void | Promise<void>;

// [provider, acceptedMethod, handler] — service name is derived from provider.
const providers: Array<[string, string, Handler]> = [
  ["asana", "GET", asanaProfile],
  ["box", "POST", boxProfile],
  ["gitlab", "POST", gitlabProfile],
  ["google", "POST", googleProfile],
  ["hubspot", "POST", hubspotProfile],
  ["jira", "POST", jiraProfile],
  ["linear", "POST", linearProfile],
  ["microsoft", "POST", microsoftProfile],
  ["notion", "POST", notionProfile],
  ["salesforce", "GET", salesforceProfile],
  ["shopify", "POST", shopifyProfile],
  ["stripe", "POST", stripeProfile],
  ["trello", "POST", trelloProfile],
  ["xero", "POST", xeroProfile],
  ["zoom", "POST", zoomProfile],
];

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1);

describe.each(providers)(
  "pages/api/integrations/%s/profile",
  (provider, method, handler) => {
    const invoke = async (httpMethod: string) => {
      const { req, res } = createMocks({ method: httpMethod as RequestMethod }) as any;
      await handler(req, res);
      return res;
    };

    it(`returns the stub profile payload for ${method}`, async () => {
      const res = await invoke(method);
      expect(res._getStatusCode()).toBe(200);
      const data = res._getJSONData();
      expect(data.success).toBe(true);
      expect(data.service).toBe(`${capitalize(provider)} Profile`);
      expect(typeof data.timestamp).toBe("string");
    });

    it("rejects other methods with 405", async () => {
      const res = await invoke(method === "GET" ? "POST" : "GET");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    });
  },
);
