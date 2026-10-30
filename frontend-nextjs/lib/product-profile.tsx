import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

/**
 * The one instruction the UI follows for what this release exposes.
 *
 * The backend serves the same document at /api/product/profile. Navigation,
 * dashboard links and direct-page access all read it, so a deferred surface
 * cannot reappear in one place while disappearing in another. Until the
 * document loads (or if it cannot), the UI falls back to the core release
 * surface — never to "show everything".
 */

export type CapabilityMeta = {
  label: string;
  enabled: boolean;
  job?: string;
  nav?: boolean;
  min_role?: string;
};

export type ProductProfile = {
  profile: "core" | "full";
  version: string;
  statement: string;
  capabilities: Record<string, CapabilityMeta>;
  enabled_capabilities: string[];
  deferred_capabilities: string[];
  routes: Record<string, string>;
};

const CORE_ROUTE_FALLBACK: Record<string, string> = {
  "/dashboard": "chat",
  "/chat": "chat",
  "/documents": "documents",
  "/canvas": "canvas",
  "/agents": "agents",
  "/learning": "learning",
  "/goal-runs": "activity",
  "/execution-history": "activity",
  "/activity": "activity",
  "/assignments": "activity",
  "/approvals": "approvals",
  "/settings/harness-evolution": "governance",
  "/settings": "settings",
  "/login": "core",
  "/auth": "core",
};

const CORE_CAPABILITIES: Record<string, CapabilityMeta> = {
  chat: { label: "Chat", enabled: true },
  documents: { label: "Data", enabled: true },
  canvas: { label: "Workspace", enabled: true },
  agents: { label: "Agents", enabled: true },
  learning: { label: "Learning", enabled: true },
  activity: { label: "Activity", enabled: true },
  settings: { label: "Settings", enabled: true },
  approvals: { label: "Approvals", enabled: true, nav: false, min_role: "team_lead" },
};

const FALLBACK_PROFILE: ProductProfile = {
  profile: "core",
  version: "2026-10-27",
  statement: "Company data + trained agent workspace",
  capabilities: CORE_CAPABILITIES,
  enabled_capabilities: Object.keys(CORE_CAPABILITIES),
  deferred_capabilities: [],
  routes: CORE_ROUTE_FALLBACK,
};

export function routeCapability(
  pathname: string,
  routes: Record<string, string>
): string {
  const path = (pathname || "/").split("?")[0].replace(/\/+$/, "") || "/";
  const prefixes = Object.keys(routes).sort((a, b) => b.length - a.length);
  for (const prefix of prefixes) {
    if (path === prefix || path.startsWith(`${prefix}/`)) {
      return routes[prefix];
    }
  }
  return "deferred";
}

export function isRouteEnabled(pathname: string, profile: ProductProfile): boolean {
  const capability = routeCapability(pathname, profile.routes);
  if (capability === "core") return true;
  return Boolean(profile.capabilities[capability]?.enabled);
}

type ProductProfileState = {
  profile: ProductProfile;
  loading: boolean;
  source: "api" | "fallback";
  isCapabilityEnabled: (capability: string) => boolean;
  isRouteAllowed: (pathname: string) => boolean;
};

const ProductProfileContext = createContext<ProductProfileState>({
  profile: FALLBACK_PROFILE,
  loading: true,
  source: "fallback",
  isCapabilityEnabled: (capability) =>
    Boolean(FALLBACK_PROFILE.capabilities[capability]?.enabled),
  isRouteAllowed: (pathname) => isRouteEnabled(pathname, FALLBACK_PROFILE),
});

export const ProductProfileProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [profile, setProfile] = useState<ProductProfile>(FALLBACK_PROFILE);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"api" | "fallback">("fallback");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/product/profile")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: ProductProfile) => {
        if (cancelled || !data?.capabilities) return;
        setProfile(data);
        setSource("api");
      })
      .catch(() => {
        // Keep the core fallback. It is the release-safe surface, not a
        // permission grant for deferred pages.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isCapabilityEnabled = useCallback(
    (capability: string) =>
      capability === "core" ||
      Boolean(profile.capabilities[capability]?.enabled),
    [profile]
  );

  const isRouteAllowed = useCallback(
    (pathname: string) => isRouteEnabled(pathname, profile),
    [profile]
  );

  const value = useMemo(
    () => ({ profile, loading, source, isCapabilityEnabled, isRouteAllowed }),
    [profile, loading, source, isCapabilityEnabled, isRouteAllowed]
  );

  return (
    <ProductProfileContext.Provider value={value}>
      {children}
    </ProductProfileContext.Provider>
  );
};

export function useProductProfile(): ProductProfileState {
  return useContext(ProductProfileContext);
}

export { FALLBACK_PROFILE };
