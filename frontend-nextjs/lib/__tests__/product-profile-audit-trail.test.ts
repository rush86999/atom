/**
 * Owner-scoped Audit Trail is part of the core Activity workflow.
 *
 * The release gate reads the loaded `/api/product/profile` document, and the
 * pre-load gate reads the hard-coded core fallback. Both must agree that
 * `/audit-trail` is member Activity, while the admin/forensics/self-healing
 * siblings stay deferred governance.
 */
import {
  FALLBACK_PROFILE,
  isRouteEnabled,
  routeCapability,
  type ProductProfile,
} from "../product-profile";

const GOVERNANCE_ROUTES = [
  "/admin/users",
  "/dashboard/owner",
  "/dashboard/forensics",
  "/settings/harness-evolution",
  "/system-status",
  "/dev-studio",
];

function loadedCoreProfile(): ProductProfile {
  return {
    ...FALLBACK_PROFILE,
    capabilities: {
      ...FALLBACK_PROFILE.capabilities,
      governance: { label: "Governance", enabled: false },
      search: { label: "Search", enabled: false },
    },
    deferred_capabilities: ["search", "governance"],
    routes: {
      ...FALLBACK_PROFILE.routes,
      "/search": "search",
      "/admin": "governance",
      "/dashboard/owner": "governance",
      "/dashboard/forensics": "governance",
      "/system-status": "governance",
      "/dev-studio": "governance",
    },
  };
}

describe("core product profile audit trail surface", () => {
  it("fallback profile resolves /audit-trail to enabled Activity", () => {
    expect(routeCapability("/audit-trail", FALLBACK_PROFILE.routes)).toBe(
      "activity"
    );
    expect(isRouteEnabled("/audit-trail", FALLBACK_PROFILE)).toBe(true);
    expect(FALLBACK_PROFILE.capabilities.activity.enabled).toBe(true);
  });

  it("loaded core profile resolves /audit-trail to enabled Activity", () => {
    const profile = loadedCoreProfile();
    expect(routeCapability("/audit-trail", profile.routes)).toBe("activity");
    expect(isRouteEnabled("/audit-trail", profile)).toBe(true);
    expect(profile.capabilities.activity.enabled).toBe(true);
  });

  it("fallback and loaded profiles agree on the direct route", () => {
    const loaded = loadedCoreProfile();
    expect(isRouteEnabled("/audit-trail", loaded)).toBe(
      isRouteEnabled("/audit-trail", FALLBACK_PROFILE)
    );
  });

  it("keeps every governance sibling deferred in the loaded core profile", () => {
    const profile = loadedCoreProfile();
    expect(profile.capabilities.governance.enabled).toBe(false);
    for (const path of GOVERNANCE_ROUTES) {
      expect(routeCapability(path, profile.routes)).toBe("governance");
      expect(isRouteEnabled(path, profile)).toBe(false);
    }
  });

  it("keeps governance siblings deferred in the core fallback", () => {
    expect(FALLBACK_PROFILE.capabilities.governance?.enabled ?? false).toBe(
      false
    );
    // The fallback maps the governance capability explicitly where it can;
    // unmatched deferred routes fail closed as "deferred".
    expect(routeCapability("/settings/harness-evolution", FALLBACK_PROFILE.routes)).toBe(
      "governance"
    );
    for (const path of ["/settings/harness-evolution", "/admin/users", "/dev-studio"]) {
      expect(isRouteEnabled(path, FALLBACK_PROFILE)).toBe(false);
    }
  });
});
