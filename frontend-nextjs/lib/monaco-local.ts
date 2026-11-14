import { loader } from "@monaco-editor/react";

/**
 * Same-origin path of the bundled Monaco editor build.
 *
 * `scripts/sync-monaco-assets.js` materializes `public/monaco/vs` from the
 * installed `monaco-editor` package at every `next dev` / `next build`
 * startup; `next.config.js` calls it. Without this override the loader's
 * default is `https://cdn.jsdelivr.net/npm/monaco-editor@<version>/min/vs`,
 * which makes the canvas editor unusable offline (air-gapped install, the
 * desktop/Tauri bundle, a firewalled deployment) and leaks a non-loopback
 * asset request into acceptance runs that require external traffic to be
 * refused.
 */
export const LOCAL_MONACO_VS_PATH = "/monaco/vs";

type LoaderConfig = { paths?: { vs?: string } };
type LoaderLike = { config?: (value: LoaderConfig) => void };

let configured = false;

/**
 * Point `@monaco-editor/loader` at the bundled editor exactly once.
 *
 * Must run at module scope in every component that renders `Editor` (before
 * React mounts it — the loader initializes during the child's effect). Calling
 * it again is a no-op. Returns false during SSR and under test doubles that
 * export only the component, so importing this module never throws there.
 */
export function configureLocalMonaco(): boolean {
  if (configured) return true;
  if (typeof window === "undefined") return false;
  const candidate = loader as unknown as LoaderLike | undefined;
  if (!candidate || typeof candidate.config !== "function") return false;
  candidate.config({ paths: { vs: LOCAL_MONACO_VS_PATH } });
  configured = true;
  return true;
}

/** Test-only: forget the process-wide "already configured" latch. */
export function resetLocalMonacoForTests(): void {
  configured = false;
}
