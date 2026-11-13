/**
 * Contract tests for lib/skill-packages.ts — the single web client for
 * GET /api/admin/skills/.
 *
 * A malformed 2xx must never be presented as an empty catalogue: the page has
 * to say the list could not be verified, not "nothing is published".
 */

import {
  SkillPackageListError,
  describeSkillPackageListFailure,
  listSkillPackages,
  skillPackageListFailureMessage,
} from "@/lib/skill-packages";
import { apiClient } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  apiClient: { get: jest.fn() },
}));

const getMock = apiClient.get as jest.Mock;

const packageRow = (name = "weekly-digest") => ({
  name,
  has_manifest: true,
  files: ["SKILL.md", "run.py"],
  modified_at: 1763000000.5,
});

const listBody = (names: string[] = ["weekly-digest", "monthly-report"]) => ({
  success: true,
  data: names.map((name) => packageRow(name)),
  metadata: { total: names.length },
});

const httpError = (status: number, data: unknown = {}) => ({
  response: { status, data },
});

beforeEach(() => {
  getMock.mockReset();
});

describe("listSkillPackages confirmed catalogue", () => {
  test("maps the tenant catalogue from the admin route without transport retries", async () => {
    getMock.mockResolvedValue({ status: 200, data: listBody() });

    await expect(listSkillPackages()).resolves.toEqual([
      {
        name: "weekly-digest",
        hasManifest: true,
        files: ["SKILL.md", "run.py"],
        modifiedAt: 1763000000.5,
      },
      {
        name: "monthly-report",
        hasManifest: true,
        files: ["SKILL.md", "run.py"],
        modifiedAt: 1763000000.5,
      },
    ]);
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(getMock.mock.calls[0][0]).toBe("/api/admin/skills/");
    expect(getMock.mock.calls[0][1]).toMatchObject({ retry: false });
  });

  test("a genuine empty catalogue is an empty list, not an error", async () => {
    getMock.mockResolvedValue({ status: 200, data: listBody([]) });
    await expect(listSkillPackages()).resolves.toEqual([]);
  });

  test("an item without a manifest is preserved truthfully", async () => {
    getMock.mockResolvedValue({
      status: 200,
      data: {
        success: true,
        data: [{ ...packageRow("bare"), has_manifest: false }],
        metadata: { total: 1 },
      },
    });
    await expect(listSkillPackages()).resolves.toEqual([
      {
        name: "bare",
        hasManifest: false,
        files: ["SKILL.md", "run.py"],
        modifiedAt: 1763000000.5,
      },
    ]);
  });
});

describe("listSkillPackages refuses unverified success material", () => {
  test.each([
    ["success flag false", { success: false, data: [], metadata: { total: 0 } }],
    ["data is not an array", { success: true, data: {}, metadata: { total: 0 } }],
    ["missing metadata", { success: true, data: [] }],
    [
      "total disagrees with the rows",
      { success: true, data: [packageRow()], metadata: { total: 2 } },
    ],
    [
      "row without a name",
      {
        success: true,
        data: [{ ...packageRow(), name: "" }],
        metadata: { total: 1 },
      },
    ],
    [
      "row without manifest state",
      {
        success: true,
        data: [{ ...packageRow(), has_manifest: undefined }],
        metadata: { total: 1 },
      },
    ],
    [
      "row with non-string files",
      {
        success: true,
        data: [{ ...packageRow(), files: [1] }],
        metadata: { total: 1 },
      },
    ],
    [
      "row without a modification time",
      {
        success: true,
        data: [{ ...packageRow(), modified_at: undefined }],
        metadata: { total: 1 },
      },
    ],
  ])("%s throws an unverified list error", async (_label, payload) => {
    getMock.mockResolvedValue({ status: 200, data: payload });

    try {
      await listSkillPackages();
      throw new Error("expected listSkillPackages to reject");
    } catch (error) {
      expect(error).toBeInstanceOf(SkillPackageListError);
      const failure = error as SkillPackageListError;
      expect(failure.outcome).toBe("unverified");
      expect(failure.message).toMatch(/could not be verified/i);
      expect(describeSkillPackageListFailure(failure)).toMatch(
        /could not be verified/i,
      );
    }
    expect(getMock).toHaveBeenCalledTimes(1);
  });
});

describe("listSkillPackages reports transport refusals", () => {
  test.each([
    [401, /workspace admin access is required/i],
    [403, /workspace admin access is required/i],
    [500, /could not load skill packages/i],
    [503, /could not load skill packages/i],
  ])("a %s response is reported without server detail", async (status, copy) => {
    getMock.mockRejectedValue(
      httpError(status, { detail: "private connection diagnostic" }),
    );

    const error = await listSkillPackages().catch((caught) => caught);
    expect(error).toBeInstanceOf(SkillPackageListError);
    expect(error).toMatchObject({ outcome: "refused", status });
    const message = describeSkillPackageListFailure(error);
    expect(message).toMatch(copy);
    expect(message).not.toContain("private connection diagnostic");
    expect(getMock).toHaveBeenCalledTimes(1);
  });

  test("a network failure is a refused catalogue read", async () => {
    getMock.mockRejectedValue(new Error("network down"));
    const error = await listSkillPackages().catch((caught) => caught);
    expect(error).toBeInstanceOf(SkillPackageListError);
    expect((error as SkillPackageListError).outcome).toBe("refused");
    expect(describeSkillPackageListFailure(error)).toMatch(
      /could not load skill packages/i,
    );
  });

  test("the safe copy is outcome-specific", () => {
    expect(skillPackageListFailureMessage("unverified")).toMatch(
      /could not be verified/i,
    );
    expect(skillPackageListFailureMessage("refused")).toMatch(
      /could not load skill packages/i,
    );
  });
});
