/**
 * Contract tests for lib/skill-package-delete.ts — the single web client for
 * DELETE /api/admin/skills/{skill_id}?operation_id=...
 *
 * Only a success response whose receipt names the exact package, binds the
 * requested operation id and whose verification + filesystem effects are
 * confirmed may be reported as a deletion. Partial/unknown outcomes throw a
 * non-retryable typed error, never a fabricated success. The caller's
 * operation id is stable: retries must keep using it.
 */

import {
  SkillPackageDeleteError,
  canonicalSkillPackageOperationId,
  deleteSkillPackage,
  newSkillPackageDeleteOperationId,
  normalizeSkillPackageId,
  skillPackageDeleteFailureMessage,
  skillPackageDeleteSuccessMessage,
} from "@/lib/skill-package-delete";
import { apiClient } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  apiClient: { delete: jest.fn() },
}));

const deleteMock = apiClient.delete as jest.Mock;

const skillId = "weekly-digest";
const otherPackage = "monthly-report";
const opId = "skill-package:delete:test-operation";

const verifiedBody = (id = skillId, operationId = opId) => ({
  success: true,
  data: {
    skill_id: id,
    name: id,
    deleted: true,
    outcome: "verified",
    effects: {
      package: "retired",
      quarantine: "deleted",
      pre_files: 3,
    },
    verification: {
      status: "verified",
      effect: "committed",
      audit_id: operationId,
    },
    operation_id: operationId,
    audit_id: operationId,
  },
  metadata: {
    operation_id: operationId,
    audit_id: operationId,
    target_id: "opaque-target-digest",
    verification: {
      status: "verified",
      effect: "committed",
      audit_id: operationId,
    },
  },
  message: "sensitive server detail should stay hidden",
});

const receiptFor = (
  status: "verified" | "already_applied" | "no_change",
  id = skillId,
  operationId = opId,
) => {
  const body = verifiedBody(id, operationId);
  // `no_change` data is the raw receipt (no operation_id/verification under
  // `data`); metadata remains authoritative.
  const data =
    status === "no_change"
      ? {
          skill_id: id,
          name: id,
          deleted: true,
          outcome: "no_change",
          effects: {
            package: "absent",
            quarantine: "absent",
            pre_files: 0,
          },
        }
      : {
          ...body.data,
          outcome: status,
          verification: {
            status,
            effect: "committed",
            audit_id: operationId,
          },
        };
  return {
    ...body,
    data,
    metadata: {
      ...body.metadata,
      verification: {
        status,
        effect: "committed",
        audit_id: operationId,
      },
    },
  };
};

const partialDetail = {
  error: {
    code: "SKILL_PACKAGE_DELETE_UNVERIFIED",
    message: "sensitive server detail should stay hidden",
  },
  verification: {
    status: "committed_unverified",
    effect: "partial",
    replay: "do_not_repeat",
  },
  operation_id: "skill-package:delete:partial",
  audit_id: "skill-package:delete:partial",
  target_id: "opaque-target-digest",
  data: { skill_id: skillId },
};

const unknownDetail = {
  error: {
    code: "SKILL_PACKAGE_EFFECT_UNKNOWN",
    message: "sensitive server detail should stay hidden",
  },
  verification: {
    status: "unavailable",
    effect: "unknown",
    replay: "do_not_repeat",
  },
  operation_id: "skill-package:delete:unknown",
  audit_id: null,
  target_id: "opaque-target-digest",
};

const notAppliedDetail = {
  error: {
    code: "SKILL_PACKAGE_DELETE_NOT_APPLIED",
    message: "the rename was refused",
  },
  verification: {
    status: "refused",
    effect: "none",
    replay: "safe_same_operation",
  },
  operation_id: opId,
  audit_id: opId,
};

const conflictDetail = {
  error: {
    code: "OPERATION_CONFLICT",
    message: "operation_id is bound to different work",
  },
  verification: { status: "refuted", effect: "none" },
};

const httpError = (status: number, detail: unknown) => ({
  response: { status, data: { detail } },
});

beforeEach(() => {
  deleteMock.mockReset();
});

describe("deleteSkillPackage confirmed outcomes", () => {
  test("a verified receipt deletes exactly the requested package with no transport retry", async () => {
    deleteMock.mockResolvedValue({ status: 200, data: verifiedBody() });

    await expect(deleteSkillPackage(skillId, opId)).resolves.toEqual({
      outcome: "deleted",
      skillId,
      operationId: opId,
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
    expect(deleteMock.mock.calls[0][0]).toBe(
      `/api/admin/skills/${encodeURIComponent(skillId)}`,
    );
    expect(deleteMock.mock.calls[0][1]).toMatchObject({
      retry: false,
      params: { operation_id: opId },
    });
  });

  test.each(["already_applied", "no_change"] as const)(
    "%s receipts are truthful 'already removed' outcomes, not new deletions",
    async (status) => {
      deleteMock.mockResolvedValue({
        status: 200,
        data: receiptFor(status),
      });
      await expect(deleteSkillPackage(skillId, opId)).resolves.toEqual({
        outcome: "already_removed",
        skillId,
        operationId: opId,
      });
    },
  );

  test("success copy distinguishes a deletion from an already-absent package", () => {
    expect(skillPackageDeleteSuccessMessage("deleted")).toBe(
      "Skill package deleted.",
    );
    expect(skillPackageDeleteSuccessMessage("already_removed")).toBe(
      "Skill package was already deleted.",
    );
  });

  test("a caller-supplied raw id is canonicalized exactly once and bound to the receipt", async () => {
    const canonical = "skill-package:delete:raw-id";
    deleteMock.mockResolvedValue({
      status: 200,
      data: verifiedBody(skillId, canonical),
    });

    await expect(deleteSkillPackage(skillId, "raw-id")).resolves.toEqual({
      outcome: "deleted",
      skillId,
      operationId: canonical,
    });
    expect(deleteMock.mock.calls[0][1].params).toEqual({
      operation_id: canonical,
    });
  });
});

describe("deleteSkillPackage refuses to certify unverified success responses", () => {
  test.each([
    ["success flag false", (body: any) => ({ ...body, success: false })],
    [
      "replayed for another package",
      (body: any) => ({
        ...body,
        data: { ...body.data, skill_id: otherPackage, name: otherPackage },
      }),
    ],
    [
      "receipt for another operation",
      (body: any) => ({
        ...body,
        metadata: {
          ...body.metadata,
          operation_id: "skill-package:delete:other",
        },
      }),
    ],
    [
      "payload names another operation",
      (body: any) => ({
        ...body,
        data: {
          ...body.data,
          operation_id: "skill-package:delete:other",
        },
      }),
    ],
    [
      "no target digest",
      (body: any) => ({
        ...body,
        metadata: { ...body.metadata, target_id: undefined },
      }),
    ],
    [
      "verification unavailable",
      (body: any) => ({
        ...body,
        metadata: {
          ...body.metadata,
          verification: { status: "unavailable", effect: "unknown" },
        },
      }),
    ],
    [
      "no verification at all",
      (body: any) => ({
        ...body,
        metadata: { ...body.metadata, verification: undefined },
      }),
    ],
    [
      "a payload-only receipt without the route envelope",
      (body: any) => ({ ...body, metadata: undefined }),
    ],
    [
      "verified without a retired package",
      (body: any) => ({
        ...body,
        data: {
          ...body.data,
          effects: { ...body.data.effects, package: "present" },
        },
      }),
    ],
    [
      "verified without a purged quarantine",
      (body: any) => ({
        ...body,
        data: {
          ...body.data,
          effects: { ...body.data.effects, quarantine: "delete_failed" },
        },
      }),
    ],
    [
      "deleted flag missing",
      (body: any) => ({
        ...body,
        data: { ...body.data, deleted: false },
      }),
    ],
  ])("%s throws an unknown, non-retryable outcome", async (_label, mutate) => {
    deleteMock.mockResolvedValue({
      status: 200,
      data: mutate(verifiedBody()),
    });

    try {
      await deleteSkillPackage(skillId, opId);
      throw new Error("expected deleteSkillPackage to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(SkillPackageDeleteError);
      const failure = error as SkillPackageDeleteError;
      expect(failure.outcome).toBe("unknown");
      expect(failure.retryable).toBe(false);
      expect(failure.replay).toBe("do_not_repeat");
      expect(failure.message).not.toContain("sensitive");
    }
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("an empty package id is refused before dispatch", async () => {
    await expect(deleteSkillPackage("", opId)).rejects.toMatchObject({
      outcome: "failed",
      retryable: false,
    });
    expect(deleteMock).not.toHaveBeenCalled();
  });

  test("an empty or malformed operation id is refused before dispatch", async () => {
    await expect(deleteSkillPackage(skillId, "   ")).rejects.toMatchObject({
      outcome: "failed",
      retryable: false,
    });
    await expect(
      deleteSkillPackage(skillId, "bad id with spaces!"),
    ).rejects.toMatchObject({ outcome: "failed", retryable: false });
    expect(deleteMock).not.toHaveBeenCalled();
  });
});

describe("deleteSkillPackage discloses partial and unknown outcomes truthfully", () => {
  test("a committed-but-unverified 503 is partial, retains the id and is not retried", async () => {
    deleteMock.mockRejectedValue(httpError(503, partialDetail));

    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "partial",
      retryable: false,
      replay: "do_not_repeat",
      status: 503,
      operationId: "skill-package:delete:partial",
      auditId: "skill-package:delete:partial",
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("a lost-confirmation 503 is unknown and is not retried", async () => {
    deleteMock.mockRejectedValue(httpError(503, unknownDetail));

    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
      replay: "do_not_repeat",
      status: 503,
      operationId: "skill-package:delete:unknown",
    });
  });

  test("a bare 503 proxy body is still unknown, never success", async () => {
    deleteMock.mockRejectedValue(httpError(503, undefined));
    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
      replay: "do_not_repeat",
    });
  });

  test("a 503 refusal that explicitly proves no effect is a known refusal", async () => {
    deleteMock.mockRejectedValue(
      httpError(503, {
        error: { code: "AUTHORITY_UNAVAILABLE" },
        verification: { status: "not_attempted", effect: "none" },
      }),
    );
    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "failed",
      retryable: false,
      replay: "new_operation",
      status: 503,
    });
  });

  test("a transport failure with no response is unknown, never success", async () => {
    deleteMock.mockRejectedValue(new Error("network down"));
    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
      replay: "do_not_repeat",
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("an ambiguous 500 is unknown because the mutation may have landed", async () => {
    deleteMock.mockRejectedValue(httpError(500, { detail: "internal" }));
    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
    });
  });

  test("a contradictory 404 cannot be read as a definite absence", async () => {
    deleteMock.mockRejectedValue(
      httpError(404, {
        error: { code: "NOT_FOUND" },
        verification: { effect: "unknown" },
        replay: "do_not_repeat",
      }),
    );
    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
      replay: "do_not_repeat",
    });
  });
});

describe("deleteSkillPackage distinguishes safe-retry refusals", () => {
  test("not_applied keeps the same operation id retryable", async () => {
    deleteMock.mockRejectedValue(httpError(409, notAppliedDetail));

    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "not_applied",
      retryable: false,
      replay: "same_operation",
      status: 409,
      operationId: opId,
      auditId: opId,
    });
  });

  test("an operation conflict requires a new intention", async () => {
    deleteMock.mockRejectedValue(httpError(409, conflictDetail));

    await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
      outcome: "conflict",
      retryable: false,
      replay: "new_operation",
    });
  });

  test.each([
    ["404", 404, "not_found", "new_operation"],
    ["409", 409, "failed", "new_operation"],
    ["422", 422, "failed", "new_operation"],
    ["401", 401, "failed", "new_operation"],
    ["403", 403, "failed", "new_operation"],
  ])(
    "a plain %s response is reported as %s",
    async (_label, status, outcome, replay) => {
      deleteMock.mockRejectedValue(httpError(status, { error: "refused" }));
      await expect(deleteSkillPackage(skillId, opId)).rejects.toMatchObject({
        outcome,
        replay,
        retryable: false,
        status,
      });
    },
  );

  test("the disclosed copy is outcome-specific and never echoes server text", () => {
    expect(skillPackageDeleteFailureMessage("partial")).toMatch(/partly verified/i);
    expect(skillPackageDeleteFailureMessage("partial")).toMatch(/do not repeat/i);
    expect(skillPackageDeleteFailureMessage("unknown")).toMatch(/unknown/i);
    expect(skillPackageDeleteFailureMessage("unknown")).toMatch(/refresh/i);
    expect(skillPackageDeleteFailureMessage("not_applied")).toMatch(/nothing changed/i);
    expect(skillPackageDeleteFailureMessage("not_applied")).toMatch(/safe/i);
    expect(skillPackageDeleteFailureMessage("conflict")).toMatch(/bound to different work/i);
    expect(skillPackageDeleteFailureMessage("not_found")).toMatch(/not found/i);
    expect(skillPackageDeleteFailureMessage("failed")).toMatch(/could not be deleted/i);
    expect(skillPackageDeleteFailureMessage("partial")).not.toContain("sensitive");
  });
});

describe("operation identity helpers", () => {
  test("generated ids are canonical, safe and unique", () => {
    const first = newSkillPackageDeleteOperationId();
    const second = newSkillPackageDeleteOperationId();
    expect(first).toMatch(/^skill-package:delete:[A-Za-z0-9_-]{1,140}$/);
    expect(first.startsWith("skill-package:delete:")).toBe(true);
    expect(first).not.toBe(second);
  });

  test("canonicalization matches the backend's single prefix rule", () => {
    expect(canonicalSkillPackageOperationId("abc")).toBe(
      "skill-package:delete:abc",
    );
    expect(canonicalSkillPackageOperationId("  skill-package:delete:abc  ")).toBe(
      "skill-package:delete:abc",
    );
    expect(canonicalSkillPackageOperationId("")).toBe(
      "skill-package:delete:",
    );
  });

  test("package identity normalization mirrors the backend name rule", () => {
    expect(normalizeSkillPackageId("Weekly Digest")).toBe("weeklydigest");
    expect(normalizeSkillPackageId("weekly-digest")).toBe("weekly-digest");
    expect(normalizeSkillPackageId("../t-b/skills/report")).toBe("t-bskillsreport");
  });
});
