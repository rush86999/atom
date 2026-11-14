/**
 * Read-only Skill Builder catalogue — the single web client for
 * `GET /api/admin/skills/`.
 *
 * The backend route (backend/api/admin/skill_routes.py::list_skill_packages)
 * returns the acting admin's tenant-scoped published packages:
 *
 *   200 { success: true,
 *         data: [{ name, has_manifest, files, modified_at }],
 *         metadata: { total } }
 *
 * ``total`` is always the number of returned packages, and a package name is
 * the addressable directory id (already normalized by the create route). A
 * malformed 2xx is NOT an empty catalogue: callers get a typed error so the
 * UI can say "could not be verified" instead of "nothing is published".
 */

type JsonRecord = Record<string, unknown>;

export const SKILL_PACKAGES_PATH = "/api/admin/skills/";

export interface SkillPackageSummary {
  /** Addressable package id (the tenant skills directory name). */
  name: string;
  hasManifest: boolean;
  files: string[];
  /** Backend file mtime, in epoch seconds. */
  modifiedAt: number;
}

export type SkillPackageListFailure = "refused" | "unverified";

export class SkillPackageListError extends Error {
  readonly outcome: SkillPackageListFailure;
  declare readonly status?: number;

  constructor(details: {
    outcome: SkillPackageListFailure;
    status?: number;
  }) {
    super(skillPackageListFailureMessage(details.outcome));
    this.name = "SkillPackageListError";
    Object.setPrototypeOf(this, SkillPackageListError.prototype);
    this.outcome = details.outcome;
    if (details.status !== undefined) this.status = details.status;
  }
}

/** Safe, outcome-specific copy shared by the page and tests. */
export function skillPackageListFailureMessage(
  outcome: SkillPackageListFailure,
): string {
  if (outcome === "unverified") {
    return "The skill package list could not be verified. Refresh before relying on it.";
  }
  return "Could not load skill packages. Refresh and try again.";
}

/** Admin-specific copy for a refused catalogue read. */
export function skillPackageListRefusalMessage(status?: number): string {
  if (status === 401 || status === 403) {
    return "Workspace admin access is required to list skill packages.";
  }
  return skillPackageListFailureMessage("refused");
}

/** User-facing copy for any list failure (typed or not). */
export function describeSkillPackageListFailure(error: unknown): string {
  if (error instanceof SkillPackageListError) {
    if (error.outcome === "unverified") {
      return skillPackageListFailureMessage("unverified");
    }
    return skillPackageListRefusalMessage(error.status);
  }
  return skillPackageListFailureMessage("refused");
}

function asRecord(value: unknown): JsonRecord | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : undefined;
}

function errorStatus(error: unknown): number | undefined {
  const status = (error as { response?: { status?: unknown } })?.response
    ?.status;
  return typeof status === "number" ? status : undefined;
}

function readPackage(value: unknown): SkillPackageSummary | undefined {
  const row = asRecord(value);
  if (!row) return undefined;
  const name = row.name;
  const files = row.files;
  const modifiedAt = row.modified_at;
  if (typeof name !== "string" || name.length === 0) return undefined;
  if (typeof row.has_manifest !== "boolean") return undefined;
  if (!Array.isArray(files) || !files.every((file) => typeof file === "string")) {
    return undefined;
  }
  if (typeof modifiedAt !== "number" || !Number.isFinite(modifiedAt)) {
    return undefined;
  }
  return {
    name,
    hasManifest: row.has_manifest,
    files: [...files],
    modifiedAt,
  };
}

/**
 * Read the tenant catalogue.
 *
 * Resolves only for a fully valid envelope; anything else throws a
 * `SkillPackageListError` (nothing is ever fabricated as an empty list).
 */
export async function listSkillPackages(): Promise<SkillPackageSummary[]> {
  let response: { status?: number; data?: unknown };
  try {
    const { apiClient } = await import("@/lib/api");
    response = await apiClient.get(SKILL_PACKAGES_PATH, {
      retry: false,
      timeout: 15000,
    });
  } catch (error) {
    throw new SkillPackageListError({
      outcome: "refused",
      status: errorStatus(error),
    });
  }

  const status = response?.status;
  const body = asRecord(response?.data);
  const items = body?.data;
  const metadata = asRecord(body?.metadata);

  const valid =
    body?.success === true &&
    status !== undefined &&
    status >= 200 &&
    status < 300 &&
    Array.isArray(items) &&
    metadata !== undefined &&
    metadata.total === items.length;

  if (!valid) {
    throw new SkillPackageListError({ outcome: "unverified", status });
  }

  const packages: SkillPackageSummary[] = [];
  for (const item of items as unknown[]) {
    const parsed = readPackage(item);
    if (!parsed) {
      throw new SkillPackageListError({ outcome: "unverified", status });
    }
    packages.push(parsed);
  }
  return packages;
}
