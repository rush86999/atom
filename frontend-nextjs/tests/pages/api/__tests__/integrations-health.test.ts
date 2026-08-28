import { createMocks, RequestMethod } from "node-mocks-http";

import asanaHealth from "@/pages/api/integrations/asana/health";
import boxHealth from "@/pages/api/integrations/box/health";
import googleHealth from "@/pages/api/integrations/google/health";
import trelloHealth from "@/pages/api/integrations/trello/health";

type Handler = (req: any, res: any) => void | Promise<void>;

// Remaining stub health routes (others like gitlab/hubspot/jira/linear/
// salesforce/slack/monday/bitbucket/azure are covered by dedicated files).
const providers: Array<[string, Handler]> = [
  ["asana", asanaHealth],
  ["box", boxHealth],
  ["google", googleHealth],
  ["trello", trelloHealth],
];

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1);

describe.each(providers)(
  "pages/api/integrations/%s/health",
  (provider, handler) => {
    const invoke = async (httpMethod: RequestMethod) => {
      const { req, res } = createMocks({ method: httpMethod }) as any;
      await handler(req, res);
      return res;
    };

    it("returns the stub health payload for GET", async () => {
      const res = await invoke("GET");
      expect(res._getStatusCode()).toBe(200);
      const data = res._getJSONData();
      expect(data.success).toBe(true);
      expect(data.service).toBe(`${capitalize(provider)} Health`);
      expect(typeof data.timestamp).toBe("string");
    });

    it("rejects non-GET methods with 405", async () => {
      const res = await invoke("POST");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
    });
  },
);
