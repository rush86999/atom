import { auditAPI, AuditApiError } from "@/lib/audit-api";

function mockFetchOnce(impl: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  const spy = jest.spyOn(global, "fetch" as any).mockImplementation(impl as any);
  return spy;
}

afterEach(() => {
  jest.restoreAllMocks();
});

test("403 is classified as a permission error, not a generic failure", async () => {
  mockFetchOnce(() =>
    Promise.resolve(
      new Response(JSON.stringify({ detail: "Insufficient permissions" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(auditAPI.summary(7)).rejects.toMatchObject({
    name: "AuditApiError",
    kind: "forbidden",
    status: 403,
  });
});

test("network failure is distinguishable from a permission error", async () => {
  mockFetchOnce(() => {
    throw new TypeError("Failed to fetch");
  });

  try {
    await auditAPI.summary(7);
    throw new Error("expected rejection");
  } catch (err) {
    expect(err).toMatchObject({ kind: "network", status: null });
  }
});

test("404 detail and timeline path use the exact execution id", async () => {
  const spy = mockFetchOnce(() =>
    Promise.resolve(
      new Response(JSON.stringify({ detail: { code: "AUDIT_EVENT_NOT_FOUND", message: "not found" } }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(auditAPI.timeline("exec/../other")).rejects.toMatchObject({
    kind: "not_found",
    status: 404,
    code: "AUDIT_EVENT_NOT_FOUND",
    message: "not found",
  });
  expect(String(spy.mock.calls[0][0])).toContain(
    "/api/audit/executions/exec%2F..%2Fother",
  );
});

test("a flat typed 422 refusal keeps its code and explanatory message", async () => {
  // The backend flattens a dict HTTPException detail, so this refusal arrives
  // as {code, message} with no `detail` wrapper (browser-pre.report.json).
  mockFetchOnce(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          code: "CORRECTION_SUBJECT_MISMATCH",
          message: "The agent id does not match the execution.",
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  await expect(
    auditAPI.correctionRequest({
      agentId: "agent-foreign-synthetic",
      executionId: "exec-member-primary-synthetic",
      auditId: "event-1",
      reason: "Wrong action taken",
    }),
  ).rejects.toMatchObject({
    name: "AuditApiError",
    kind: "invalid",
    status: 422,
    code: "CORRECTION_SUBJECT_MISMATCH",
    message: "The agent id does not match the execution.",
  });
});

test("non-JSON error bodies fall back to the HTTP status text", async () => {
  mockFetchOnce(() =>
    Promise.resolve(
      new Response("upstream unavailable", {
        status: 503,
        statusText: "Service Unavailable",
      }),
    ),
  );

  await expect(auditAPI.summary(7)).rejects.toMatchObject({
    kind: "server",
    status: 503,
    code: "http_503",
    message: "Service Unavailable",
  });
});

test("an unrecognized JSON error body falls back without stringifying it", async () => {
  mockFetchOnce(() =>
    Promise.resolve(
      new Response(JSON.stringify({ ok: false }), {
        status: 400,
        statusText: "Bad Request",
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(auditAPI.summary(7)).rejects.toMatchObject({
    kind: "invalid",
    status: 400,
    code: "http_400",
    message: "Bad Request",
  });
});

test("correction request posts the audit subject and never sends a user id", async () => {
  const spy = mockFetchOnce(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          success: true,
          data: {
            id: "fb-1",
            feedback_id: "fb-1",
            correction_status: "recorded",
            correction_audit_id: "aud-1",
            applied: false,
            verified: false,
            status_note: "recorded",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );

  const receipt = await auditAPI.correctionRequest({
    agentId: "agent-1",
    executionId: "exec-1",
    auditId: "event-1",
    reason: "Wrong result",
  });

  expect(receipt.applied).toBe(false);
  expect(receipt.verified).toBe(false);

  const body = JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body));
  expect(body.subject_audit_id).toBe("event-1");
  expect(body.execution_id).toBe("exec-1");
  expect(body.correction_requested).toBe(true);
  expect(body).not.toHaveProperty("user_id");
  expect(body).not.toHaveProperty("workspace_id");
});
