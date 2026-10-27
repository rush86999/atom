import React from "react";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";

/** Clean denied state for a role-gated surface (no data, no empty admin shell). */
export const RoleRequired: React.FC<{ capabilityLabel: string; minimum: string }> = ({
  capabilityLabel,
  minimum,
}) => (
  <div className="min-h-[60vh] flex items-center justify-center p-6">
    <div className="max-w-lg w-full rounded-xl border border-border bg-card p-8 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <ShieldAlert className="h-5 w-5 text-muted-foreground" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Supervisor access required</h1>
          <p className="text-sm text-muted-foreground">
            {capabilityLabel} needs the {minimum.replace(/_/g, " ")} role.
          </p>
        </div>
      </div>
      <p className="mt-6 text-sm text-foreground/80">
        This page is a supervision safeguard. Your account can still do the
        core work: chat, records, workspace deliverables, and agent teaching.
      </p>
      <div className="mt-6">
        <Link
          className="rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"
          href="/dashboard"
        >
          Back to the workspace
        </Link>
      </div>
    </div>
  </div>
);

export default RoleRequired;
