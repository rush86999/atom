import { createMocks, RequestMethod } from "node-mocks-http";

import asanaResources from "@/pages/api/integrations/asana/resources";
import boxResources from "@/pages/api/integrations/box/resources";
import gitlabResources from "@/pages/api/integrations/gitlab/resources";
import googleResources from "@/pages/api/integrations/google/resources";
import hubspotResources from "@/pages/api/integrations/hubspot/resources";
import jiraResources from "@/pages/api/integrations/jira/resources";
import linearResources from "@/pages/api/integrations/linear/resources";
import microsoftResources from "@/pages/api/integrations/microsoft/resources";
import notionResources from "@/pages/api/integrations/notion/resources";
import salesforceResources from "@/pages/api/integrations/salesforce/resources";
import shopifyResources from "@/pages/api/integrations/shopify/resources";
import stripeResources from "@/pages/api/integrations/stripe/resources";
import trelloResources from "@/pages/api/integrations/trello/resources";
import xeroResources from "@/pages/api/integrations/xero/resources";
import zoomResources from "@/pages/api/integrations/zoom/resources";

type Handler = (req: any, res: any) => void | Promise<void>;

// All resources routes are POST-only stub responders.
const providers: Array<[string, Handler]> = [
  ["asana", asanaResources],
  ["box", boxResources],
  ["gitlab", gitlabResources],
  ["google", googleResources],
  ["hubspot", hubspotResources],
  ["jira", jiraResources],
  ["linear", linearResources],
  ["microsoft", microsoftResources],
  ["notion", notionResources],
  ["salesforce", salesforceResources],
  ["shopify", shopifyResources],
  ["stripe", stripeResources],
  ["trello", trelloResources],
  ["xero", xeroResources],
  ["zoom", zoomResources],
];

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1);

describe.each(providers)(
  "pages/api/integrations/%s/resources",
  (provider, handler) => {
    const invoke = async (httpMethod: RequestMethod) => {
      const { req, res } = createMocks({ method: httpMethod }) as any;
      await handler(req, res);
      return res;
    };

    it("returns the stub resources payload for POST", async () => {
      const res = await invoke("POST");
      expect(res._getStatusCode()).toBe(200);
      const data = res._getJSONData();
      expect(data.success).toBe(true);
      expect(data.service).toBe(`${capitalize(provider)} Resources`);
      expect(typeof data.timestamp).toBe("string");
    });

    it("rejects GET with 405", async () => {
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    });
  },
);
