import React from "react";
import Link from "next/link";
import { Lock } from "lucide-react";

import { useProductProfile, routeCapability } from "@/lib/product-profile";

/**
 * Honest direct-page state for a surface this release does not include.
 *
 * It names the deferred capability and links to the core jobs that ARE
 * available. Deferred code and data stay in the installation; this is a
 * scope statement, not a deleted feature.
 */
export const NotInRelease: React.FC<{ pathname: string }> = ({ pathname }) => {
  const { profile } = useProductProfile();
  const capability = routeCapability(pathname, profile.routes);
  const meta = profile.capabilities[capability];

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6">
      <div className="max-w-xl w-full rounded-xl border border-border bg-card p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-muted">
            <Lock className="h-5 w-5 text-muted-foreground" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">
              {meta?.label || "This page"} is not part of this release
            </h1>
            <p className="text-sm text-muted-foreground">
              This installation is the {profile.statement.toLowerCase()}.
            </p>
          </div>
        </div>

        <p className="mt-6 text-sm text-foreground/80">
          {meta?.job
            ? `Deferred: ${meta.job}`
            : "This surface is deferred until its promised job is verified."}{" "}
          The code and any existing data remain in the installation; they are
          simply not exposed here.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-2 text-sm">
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/chat">
            Chat
          </Link>
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/documents">
            Data
          </Link>
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/canvas">
            Workspace
          </Link>
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/agents">
            Agents
          </Link>
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/goal-runs">
            Activity
          </Link>
          <Link className="rounded-md border border-border px-3 py-2 hover:bg-muted" href="/settings">
            Settings
          </Link>
        </div>

        <p className="mt-6 text-xs text-muted-foreground">
          Requested path: <code>{pathname}</code>
        </p>
      </div>
    </div>
  );
};

export default NotInRelease;
