import React, { useEffect } from "react";
import { useRouter } from "next/router";

/**
 * /settings/bpe → /admin/bpe
 *
 * The BPE (Belief/Progress/Experience) workspace is consolidated on the
 * admin surface: /admin/bpe (sidebar: GOVERNANCE → BPE Workspace) — status
 * cards, mode flags, consult policy, evolution population, workspace
 * inspector and telemetry, all on /api/v1/admin/bpe/*. This page only
 * forwards old links.
 */
const BpeRedirectPage = () => {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/bpe");
  }, [router]);

  return (
    <div style={{ padding: "3rem", textAlign: "center" }}>
      <p>
        The BPE Workspace page moved to <a href="/admin/bpe">/admin/bpe</a>…
      </p>
    </div>
  );
};

export default BpeRedirectPage;
