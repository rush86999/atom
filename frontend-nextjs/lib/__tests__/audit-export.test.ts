import {
  AUDIT_EVIDENCE_FORMAT,
  AUDIT_EVIDENCE_LIMITS,
  buildAuditEvidenceBundle,
  evidenceFilename,
  serializeAuditEvidenceBundle,
} from "@/lib/audit-export";
import { ExecutionTimeline } from "@/lib/audit-api";

const TIMELINE: ExecutionTimeline = {
  execution_id: "exec-1",
  found_events: true,
  read_scope: {
    kind: "owner",
    workspace_id: "ws-1",
    supervisor: false,
    note: "Own scope: only audited rows recorded for your user.",
  },
  execution: { id: "exec-1", agent_id: "a1", status: "completed" },
  counts: { tool_calls: 1, llm_calls: 0, failed_events: 0 },
  evidence_limits: {
    signed: false,
    hash_chain: false,
    note: "not tamper-evident",
  },
  events: [
    {
      id: "e1",
      timestamp: "2026-08-24T10:00:00Z",
      event_type: "agent_action",
      action: "execution_start",
      description: "start",
      agent_id: "a1",
      agent_execution_id: "exec-1",
      user_id: "member",
      workspace_id: "ws-1",
      success: true,
      error_message: null,
      metadata: { task_input: "reconcile" },
    },
    {
      id: "e2",
      timestamp: "2026-08-24T10:01:00Z",
      event_type: "agent_action",
      action: "tool:send_email",
      description: "sent",
      agent_id: "a1",
      agent_execution_id: "exec-1",
      user_id: "member",
      workspace_id: "ws-1",
      success: true,
      error_message: null,
      metadata: { args: { to: "a@b.c" } },
    },
  ],
};

test("export rows are exactly the authorized API payload rows", () => {
  const bundle = buildAuditEvidenceBundle(TIMELINE, {
    generatedAt: "2026-08-24T11:00:00.000Z",
    appVersion: "1.2.3",
  });

  expect(bundle.rows).toEqual(TIMELINE.events);
  expect(bundle.row_count).toBe(2);
  expect(bundle.execution_id).toBe("exec-1");
  expect(bundle.filter_window).toEqual({
    start: "2026-08-24T10:00:00Z",
    end: "2026-08-24T10:01:00Z",
  });
  expect(bundle.source_app_version).toBe("1.2.3");
  expect(bundle.generated_at).toBe("2026-08-24T11:00:00.000Z");
  expect(bundle.format).toBe(AUDIT_EVIDENCE_FORMAT);
  expect(bundle.rows.map((row) => row.id)).toEqual(["e1", "e2"]);
});

test("integrity/coverage limits are explicit and never overclaimed", () => {
  const bundle = buildAuditEvidenceBundle(TIMELINE, {
    generatedAt: "2026-08-24T11:00:00.000Z",
  });
  expect(bundle.integrity.signed).toBe(false);
  expect(bundle.integrity.hash_chain).toBe(false);
  expect(bundle.integrity.tamper_evident).toBe(false);
  expect(bundle.integrity.completeness_certified).toBe(false);
  expect(bundle.integrity.statement).toBe(AUDIT_EVIDENCE_LIMITS);
  expect(bundle.coverage.scope_note).toContain("Own scope");
  expect(bundle.source_app_version).toBe("unknown");

  const serialized = serializeAuditEvidenceBundle(bundle);
  expect(serialized).not.toMatch(/tamper-proof|certified complete|complete export/i);
  expect(serialized).toContain("not tamper-evident");
});

test("empty timelines stay empty instead of inventing a window", () => {
  const bundle = buildAuditEvidenceBundle({
    ...TIMELINE,
    found_events: false,
    events: [],
  });
  expect(bundle.row_count).toBe(0);
  expect(bundle.rows).toEqual([]);
  expect(bundle.filter_window).toEqual({ start: null, end: null });
});

test("filename is derived from validated ids, not raw path input", () => {
  expect(evidenceFilename("exec-1", "2026-08-24T11:00:00.000Z")).toBe(
    "audit-evidence-exec-1-2026-08-24T11-00-00-000Z.json",
  );
  expect(evidenceFilename("../../etc/passwd", "x")).toContain(
    "audit-evidence-.._.._etc_passwd-",
  );
  expect(evidenceFilename("../../etc/passwd", "x")).not.toContain("/");
});
