/**
 * Contract tests for lib/document-delete.ts — the single web client for
 * DELETE /api/documents/{doc_id}.
 *
 * Only a success response whose receipt names the exact document and whose
 * verification is confirmed may be reported as a deletion. Partial/unknown
 * outcomes throw a non-retryable typed error, never a fabricated success.
 */

import {
  deleteDocument,
  deleteFailureMessage,
  deleteSuccessMessage,
  DocumentDeleteError,
} from "@/lib/document-delete";
import { apiClient } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  apiClient: { delete: jest.fn() },
}));

const deleteMock = apiClient.delete as jest.Mock;

const docId = "doc/with space";
const encoded = encodeURIComponent(docId);

const verifiedBody = (id = docId) => ({
  success: true,
  data: {
    doc_id: id,
    deleted: true,
    complete: true,
    verification: { status: "verified", effect: "committed" },
    operation_id: "document:delete:one",
    audit_id: "document:delete:one",
  },
  metadata: {
    operation_id: "document:delete:one",
    audit_id: "document:delete:one",
    target_id: id,
    verification: { status: "verified", effect: "committed" },
  },
});

const detailBody = (
  status: "verified" | "already_applied" | "no_change",
  id = docId,
) => ({
  ...verifiedBody(id),
  data: {
    ...verifiedBody(id).data,
    complete: status !== "no_change",
    verification: { status, effect: "committed" },
  },
  metadata: {
    ...verifiedBody(id).metadata,
    verification: { status, effect: "committed" },
  },
});

const partialDetail = {
  error: {
    code: "DOCUMENT_DELETE_UNVERIFIED",
    message: "sensitive server detail should stay hidden",
  },
  verification: { status: "committed_unverified", effect: "partial", replay: "do_not_repeat" },
  operation_id: "document:delete:partial",
  audit_id: "document:delete:partial",
  target_id: "doc/with space",
};

const unknownDetail = {
  error: {
    code: "DOCUMENT_EFFECT_UNKNOWN",
    message: "sensitive server detail should stay hidden",
  },
  verification: { status: "unavailable", effect: "unknown", replay: "do_not_repeat" },
  operation_id: "document:delete:unknown",
  audit_id: null,
  target_id: "doc/with space",
};

const httpError = (status: number, detail: unknown) => ({
  response: { status, data: { detail } },
});

beforeEach(() => {
  deleteMock.mockReset();
});

describe("deleteDocument confirmed outcomes", () => {
  test("a verified receipt deletes exactly the requested document with no transport retry", async () => {
    deleteMock.mockResolvedValue({ status: 200, data: verifiedBody() });

    await expect(deleteDocument(docId)).resolves.toEqual({
      outcome: "deleted",
      docId,
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
    expect(deleteMock.mock.calls[0][0]).toBe(`/api/documents/${encoded}`);
    expect(deleteMock.mock.calls[0][1]).toMatchObject({ retry: false });
  });

  test.each(["already_applied", "no_change"] as const)(
    "%s receipts are truthful 'already removed' outcomes, not new deletions",
    async (status) => {
      deleteMock.mockResolvedValue({ status: 200, data: detailBody(status) });
      await expect(deleteDocument(docId)).resolves.toEqual({
        outcome: "already_removed",
        docId,
      });
    },
  );

  test("success copy distinguishes a deletion from an already-absent document", () => {
    expect(deleteSuccessMessage("deleted")).toBe("Document deleted.");
    expect(deleteSuccessMessage("already_removed")).toBe(
      "Document was already deleted.",
    );
  });
});

describe("deleteDocument refuses to certify unverified success responses", () => {
  test.each([
    ["success flag false", (body: any) => ({ ...body, success: false })],
    ["replayed for another document", (body: any) => ({
      ...body,
      metadata: { ...body.metadata, target_id: "other-doc" },
    })],
    ["payload names another document", (body: any) => ({
      ...body,
      data: { ...body.data, doc_id: "other-doc" },
    })],
    ["verified without a complete cleanup", (body: any) => ({
      ...body,
      data: { ...body.data, complete: false },
    })],
    ["verification unavailable", (body: any) => ({
      ...body,
      metadata: {
        ...body.metadata,
        verification: { status: "unavailable", effect: "unknown" },
      },
    })],
    ["no verification at all", (body: any) => ({
      ...body,
      data: { ...body.data, verification: undefined },
      metadata: { ...body.metadata, verification: undefined },
    })],
    ["a payload-only receipt without the route envelope", (body: any) => ({
      ...body,
      metadata: undefined,
    })],
  ])("%s throws an unknown, non-retryable outcome", async (_label, mutate) => {
    deleteMock.mockResolvedValue({ status: 200, data: mutate(verifiedBody()) });

    try {
      await deleteDocument(docId);
      throw new Error("expected deleteDocument to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(DocumentDeleteError);
      const failure = error as DocumentDeleteError;
      expect(failure.outcome).toBe("unknown");
      expect(failure.retryable).toBe(false);
      expect(failure.message).not.toContain("sensitive");
    }
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("an empty document id is refused before dispatch", async () => {
    await expect(deleteDocument("")).rejects.toMatchObject({
      outcome: "failed",
      retryable: false,
    });
    expect(deleteMock).not.toHaveBeenCalled();
  });
});

describe("deleteDocument discloses partial and unknown outcomes truthfully", () => {
  test("a committed-but-unverified 503 is partial and is not retried", async () => {
    deleteMock.mockRejectedValue(httpError(503, partialDetail));

    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "partial",
      retryable: false,
      status: 503,
      operationId: "document:delete:partial",
      auditId: "document:delete:partial",
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("a lost-confirmation 503 is unknown and is not retried", async () => {
    deleteMock.mockRejectedValue(httpError(503, unknownDetail));

    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
      status: 503,
      operationId: "document:delete:unknown",
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("a bare 503 proxy body is still unknown, never success", async () => {
    deleteMock.mockRejectedValue(httpError(503, undefined));
    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
    });
  });

  test("a transport failure with no response is unknown, never success", async () => {
    deleteMock.mockRejectedValue(new Error("network down"));
    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
    });
    expect(deleteMock).toHaveBeenCalledTimes(1);
  });

  test("an ambiguous 500 is unknown because the mutation may have landed", async () => {
    deleteMock.mockRejectedValue(httpError(500, { detail: "internal" }));
    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
    });
  });

  test("a contradictory 404 cannot be read as a definite absence", async () => {
    deleteMock.mockRejectedValue(
      httpError(404, {
        error: { code: "NOT_FOUND" },
        replay: "do_not_repeat",
        verification: { effect: "unknown" },
      }),
    );
    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome: "unknown",
      retryable: false,
    });
  });

  test.each([
    ["404", 404, "not_found"],
    ["409", 409, "failed"],
    ["422", 422, "failed"],
    ["401", 401, "failed"],
    ["403", 403, "failed"],
  ])("a plain %s response is reported as %s", async (_label, status, outcome) => {
    deleteMock.mockRejectedValue(httpError(status, { error: "refused" }));
    await expect(deleteDocument(docId)).rejects.toMatchObject({
      outcome,
      retryable: false,
      status,
    });
  });

  test("the disclosed copy is outcome-specific and never echoes server text", () => {
    expect(deleteFailureMessage("partial")).toMatch(/partly verified/i);
    expect(deleteFailureMessage("partial")).toMatch(/do not repeat/i);
    expect(deleteFailureMessage("unknown")).toMatch(/unknown/i);
    expect(deleteFailureMessage("unknown")).toMatch(/refresh/i);
    expect(deleteFailureMessage("not_found")).toMatch(/not found/i);
    expect(deleteFailureMessage("failed")).toMatch(/could not be deleted/i);
    expect(deleteFailureMessage("partial")).not.toContain("sensitive");
  });
});
