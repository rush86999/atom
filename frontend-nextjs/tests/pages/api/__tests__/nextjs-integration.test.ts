const mockFetch = jest.fn();

import { createMocks } from "node-mocks-http";
import analyticsHandler from "@/pages/api/integrations/nextjs/analytics";
import buildsHandler from "@/pages/api/integrations/nextjs/builds";
import deployHandler from "@/pages/api/integrations/nextjs/deploy";
import deploymentStatusHandler from "@/pages/api/integrations/nextjs/deployment-status";
import envVarsHandler from "@/pages/api/integrations/nextjs/env-vars";
import projectHandler from "@/pages/api/integrations/nextjs/project";
import projectsHandler from "@/pages/api/integrations/nextjs/projects";

const okResponse = (data: any): any => ({
  ok: true,
  status: 200,
  json: async () => data,
});

const failingResponse = (status: number, data: any): any => ({
  ok: false,
  status,
  json: async () => data,
});

beforeEach(() => {
  jest.clearAllMocks();
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  (global as any).fetch = mockFetch;
  jest.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
});

const invoke = async (handler: any, body?: any, method = "POST"): Promise<any> => {
  const { req, res } = createMocks({ method, body }) as any;
  await handler(req, res);
  return res;
};

// Shared behaviour for every POST proxy in this family: method guard,
// backend URL, error passthrough, default error message, and the 500 path.
const runBaseSuite = (
  describeName: string,
  handler: any,
  backendPath: string,
  defaultErrorMessage: string,
  validBody: any,
  invalidBody: any,
  invalidBodyError: string,
) => {
  describe(describeName, () => {
    it("rejects non-POST methods with 405", async () => {
      const res = await invoke(handler, undefined, "GET");
      expect(res._getStatusCode()).toBe(405);
      expect(res._getJSONData()).toEqual({ error: "Method not allowed" });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("returns 400 for an invalid request body", async () => {
      const res = await invoke(handler, invalidBody);
      expect(res._getStatusCode()).toBe(400);
      expect(res._getJSONData()).toEqual({ error: invalidBodyError });
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("forwards the request to the default backend URL", async () => {
      mockFetch.mockResolvedValue(okResponse({}));
      await invoke(handler, validBody);
      expect(mockFetch.mock.calls[0][0]).toBe(
        `http://127.0.0.1:8000${backendPath}`,
      );
      expect(mockFetch.mock.calls[0][1].method).toBe("POST");
    });

    it("honours NEXT_PUBLIC_API_BASE_URL when configured", async () => {
      process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:5151";
      mockFetch.mockResolvedValue(okResponse({}));
      await invoke(handler, validBody);
      expect(mockFetch.mock.calls[0][0]).toBe(`http://backend:5151${backendPath}`);
    });

    it("mirrors the backend error and status when the fetch fails", async () => {
      mockFetch.mockResolvedValue(failingResponse(401, { error: "Vercel token expired" }));
      const res = await invoke(handler, validBody);
      expect(res._getStatusCode()).toBe(401);
      expect(res._getJSONData()).toEqual({ ok: false, error: "Vercel token expired" });
    });

    it("uses the default error message when the backend omits one", async () => {
      mockFetch.mockResolvedValue(failingResponse(503, {}));
      const res = await invoke(handler, validBody);
      expect(res._getStatusCode()).toBe(503);
      expect(res._getJSONData()).toEqual({ ok: false, error: defaultErrorMessage });
    });

    it("returns 500 when the backend fetch rejects", async () => {
      mockFetch.mockRejectedValue(new Error("backend down"));
      const res = await invoke(handler, validBody);
      expect(res._getStatusCode()).toBe(500);
      expect(res._getJSONData()).toEqual({ ok: false, error: "Internal server error" });
      expect(console.error).toHaveBeenCalled();
    });
  });
};

runBaseSuite(
  "pages/api/integrations/nextjs/analytics",
  analyticsHandler,
  "/api/integrations/nextjs/analytics",
  "Failed to fetch Next.js analytics",
  { user_id: "u", project_id: "p" },
  { user_id: "u" },
  "User ID and Project ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/builds",
  buildsHandler,
  "/api/integrations/nextjs/builds",
  "Failed to fetch Next.js builds",
  { user_id: "u", project_id: "p" },
  {},
  "User ID and Project ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/deploy",
  deployHandler,
  "/api/integrations/nextjs/deploy",
  "Failed to trigger deployment",
  { user_id: "u", project_id: "p" },
  { user_id: "u", project_id: "" },
  "User ID and Project ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/deployment-status",
  deploymentStatusHandler,
  "/api/integrations/nextjs/deployment/status",
  "Failed to fetch deployment status",
  { user_id: "u", deployment_id: "d" },
  { user_id: "u" },
  "User ID and Deployment ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/env-vars",
  envVarsHandler,
  "/api/integrations/nextjs/env-vars",
  "Failed to manage environment variables",
  { user_id: "u", project_id: "p" },
  { project_id: "p" },
  "User ID and Project ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/project",
  projectHandler,
  "/api/integrations/nextjs/project",
  "Failed to fetch project details",
  { user_id: "u", project_id: "p" },
  { user_id: "u" },
  "User ID and Project ID are required",
);

runBaseSuite(
  "pages/api/integrations/nextjs/projects",
  projectsHandler,
  "/api/integrations/nextjs/projects",
  "Failed to fetch Next.js projects",
  { user_id: "u" },
  {},
  "User ID is required",
);

describe("pages/api/integrations/nextjs/analytics (payload specifics)", () => {
  it("sends default metrics and a computed 30-day date range", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ analytics: { pageViews: 10 }, date_range: { start: "s", end: "e" } }),
    );
    const before = Date.now();
    const res = await invoke(analyticsHandler, { user_id: "u", project_id: "p" });
    const after = Date.now();
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      analytics: { pageViews: 10 },
      date_range: { start: "s", end: "e" },
    });
    const sent = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(sent.metrics).toEqual([
      "pageViews",
      "uniqueVisitors",
      "bounceRate",
      "avgSessionDuration",
    ]);
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    const startMs = new Date(sent.date_range.start).getTime();
    expect(startMs).toBeGreaterThanOrEqual(before - thirtyDays);
    expect(startMs).toBeLessThanOrEqual(after - thirtyDays);
    const endMs = new Date(sent.date_range.end).getTime();
    expect(endMs).toBeGreaterThanOrEqual(before);
    expect(endMs).toBeLessThanOrEqual(after);
  });

  it("forwards an explicit date_range and metrics", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const date_range = { start: "2026-01-01", end: "2026-02-01" };
    await invoke(analyticsHandler, {
      user_id: "u",
      project_id: "p",
      date_range,
      metrics: ["pageViews"],
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      date_range,
      metrics: ["pageViews"],
    });
  });
});

describe("pages/api/integrations/nextjs/builds (payload specifics)", () => {
  it("sends default filter values and reports the build count", async () => {
    mockFetch.mockResolvedValue(okResponse({ builds: [{ id: "b1" }, { id: "b2" }] }));
    const res = await invoke(buildsHandler, { user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      builds: [{ id: "b1" }, { id: "b2" }],
      count: 2,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      status: "all",
      limit: 20,
      include_logs: false,
    });
  });

  it("defaults the count to zero when the backend returns no builds", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke(buildsHandler, { user_id: "u", project_id: "p" });
    expect(res._getJSONData()).toEqual({ ok: true, builds: undefined, count: 0 });
  });

  it("forwards explicit filter values", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke(buildsHandler, {
      user_id: "u",
      project_id: "p",
      status: "failed",
      limit: 5,
      include_logs: true,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      status: "failed",
      limit: 5,
      include_logs: true,
    });
  });
});

describe("pages/api/integrations/nextjs/deploy (payload specifics)", () => {
  it("triggers a deployment with default branch and force flag", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ deployment: { id: "d1" }, deployment_url: "https://x.vercel.app" }),
    );
    const res = await invoke(deployHandler, { user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      deployment: { id: "d1" },
      url: "https://x.vercel.app",
      message: "Deployment triggered for project p on branch main",
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      branch: "main",
      force: false,
    });
  });

  it("forwards an explicit branch and force flag", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke(deployHandler, {
      user_id: "u",
      project_id: "p",
      branch: "release",
      force: true,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      branch: "release",
      force: true,
    });
  });
});

describe("pages/api/integrations/nextjs/deployment-status (payload specifics)", () => {
  it("reports READY with build info from the backend", async () => {
    const deployment = {
      status: "READY",
      url: "https://x.vercel.app",
      created_at: "2026-08-14T00:00:00Z",
      ready: true,
    };
    mockFetch.mockResolvedValue(okResponse({ deployment, build: { id: "b1" } }));
    const res = await invoke(deploymentStatusHandler, {
      user_id: "u",
      deployment_id: "d1",
    });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      deployment,
      build: { id: "b1" },
      status: "READY",
      url: "https://x.vercel.app",
      created_at: "2026-08-14T00:00:00Z",
      ready_state: true,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      deployment_id: "d1",
      include_build_info: true,
    });
  });

  it("falls back to status unknown when the backend returns no deployment", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke(deploymentStatusHandler, {
      user_id: "u",
      deployment_id: "d1",
      include_build_info: false,
    });
    expect(res._getJSONData()).toEqual({
      ok: true,
      deployment: undefined,
      build: undefined,
      status: "unknown",
      url: undefined,
      created_at: undefined,
      ready_state: undefined,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      deployment_id: "d1",
      include_build_info: false,
    });
  });
});

describe("pages/api/integrations/nextjs/env-vars (payload specifics)", () => {
  it("lists variables with default action, target, and type", async () => {
    mockFetch.mockResolvedValue(
      okResponse({ result: "ok", environment_variables: [{ key: "A" }] }),
    );
    const res = await invoke(envVarsHandler, { user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      action: "list",
      result: "ok",
      environment_variables: [{ key: "A" }],
      message: "Successfully listed environment variables",
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      action: "list",
      key: undefined,
      value: undefined,
      target: ["production", "preview"],
      type: "plain",
    });
  });

  it("names the key in the success message when one is provided", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke(envVarsHandler, {
      user_id: "u",
      project_id: "p",
      action: "create",
      key: "API_KEY",
      value: "secret",
      target: ["production"],
      type: "encrypted",
    });
    expect(res._getJSONData()).toMatchObject({
      ok: true,
      action: "create",
      message: "Successfully created environment variable API_KEY",
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toMatchObject({
      action: "create",
      key: "API_KEY",
      value: "secret",
      target: ["production"],
      type: "encrypted",
    });
  });
});

describe("pages/api/integrations/nextjs/project (payload specifics)", () => {
  it("fetches project details with the default include flag", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        project: { id: "p" },
        environment_variables: [{ key: "A" }],
        deployments: [{ id: "d" }],
        builds: [{ id: "b" }],
      }),
    );
    const res = await invoke(projectHandler, { user_id: "u", project_id: "p" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      project: { id: "p" },
      environment_variables: [{ key: "A" }],
      deployments: [{ id: "d" }],
      builds: [{ id: "b" }],
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      include_environment_variables: false,
    });
  });

  it("forwards an explicit include_environment_variables flag", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke(projectHandler, {
      user_id: "u",
      project_id: "p",
      include_environment_variables: true,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      project_id: "p",
      include_environment_variables: true,
    });
  });
});

describe("pages/api/integrations/nextjs/projects (payload specifics)", () => {
  it("fetches projects with default filters and reports the count", async () => {
    mockFetch.mockResolvedValue(
      okResponse({
        projects: [{ id: "p1" }, { id: "p2" }],
        builds: [],
        deployments: [{ id: "d" }],
      }),
    );
    const res = await invoke(projectsHandler, { user_id: "u" });
    expect(res._getStatusCode()).toBe(200);
    expect(res._getJSONData()).toEqual({
      ok: true,
      projects: [{ id: "p1" }, { id: "p2" }],
      builds: [],
      deployments: [{ id: "d" }],
      count: 2,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      limit: 50,
      status: "active",
      include_builds: false,
      include_deployments: true,
    });
  });

  it("defaults the count to zero when the backend returns no projects", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    const res = await invoke(projectsHandler, { user_id: "u" });
    expect(res._getJSONData()).toEqual({
      ok: true,
      projects: undefined,
      builds: undefined,
      deployments: undefined,
      count: 0,
    });
  });

  it("forwards explicit filters", async () => {
    mockFetch.mockResolvedValue(okResponse({}));
    await invoke(projectsHandler, {
      user_id: "u",
      limit: 5,
      status: "archived",
      include_builds: true,
      include_deployments: false,
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      user_id: "u",
      limit: 5,
      status: "archived",
      include_builds: true,
      include_deployments: false,
    });
  });
});
