"use client";

/**
 * MiniAppHarness — agent-driven mini-app authoring panel (Aug 2026).
 *
 * A collapsible bottom panel for authoring stateful canvas mini-apps directly
 * from the canvas page: scaffold a draft → edit logic (Monaco, syntax-gated
 * server-side) → dev-run (dry: resulting state + proposed ops, NO commit) →
 * publish (credential-stripped blueprint) → install (fresh immutable instance).
 *
 * Live instance state arrives over the WS `canvas:update` channel with
 * `action: "mini_app_state"` and is previewed here as JSON — the user-facing
 * twin of `window.atom.canvas.getState()` (agent-facing dual-face access).
 *
 * Talks to the backend via the unified RPC client (POST /api/rpc/{action})
 * and a direct PUT for save (logic is canvas-scoped).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import AcceptanceCaseEditor from "./AcceptanceCaseEditor";
import LogicRevisionHistory from "./LogicRevisionHistory";
import {
  Play,
  Save,
  Loader2,
  Plus,
  Rocket,
  Boxes,
  ChevronDown,
  ChevronUp,
  Code2,
  Radio,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { rpc } from "@/lib/rpc-client";
import { configureLocalMonaco } from "@/lib/monaco-local";

// Module scope, before React mounts the editor (the loader initializes in the
// Editor's own effect).
configureLocalMonaco();

interface MiniAppHarnessProps {
  canvasId: string;
  lastMessage?: any; // WS stream from the page's useWebSocket
  /**
   * Lossless frame delivery, when the parent shares its live listener.
   *
   * `lastMessage` is ONE state slot: a burst of frames inside a single render
   * commit collapses to one commit, so an effect keyed on it sees only the
   * newest frame — and a `mini_app_state` broadcast that lands mid-burst is
   * simply never applied, leaving the harness showing a stale draft. Passing
   * the parent's `onMessage` applies every frame in arrival order.
   *
   * Optional on purpose: callers with no live socket (and the existing tests)
   * keep the prop path unchanged.
   */
  onSocketMessage?: (handler: (msg: any) => void) => (() => void) | void;
  agentId?: string;
  // The canvas type this panel is mounted on — the default base type for new
  // apps, so authoring from inside a sheets/email/… canvas builds ON it.
  canvasType?: string;
}

interface LogicRunResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  error?: string;
}

interface MiniAppScaffoldResult {
  success: boolean;
  app_id?: string;
  canvas_id?: string;
  logic_source?: string;
  error?: string;
}

interface DevRunResult extends LogicRunResult {
  state?: Record<string, unknown>;
  version?: number;
  proposed_ops?: Array<Record<string, unknown>>;
  op_results?: Record<string, unknown>;
  state_changed?: boolean;
}

/**
 * The exact logic revision this editor read. Bound to the target canvas so a
 * baseline can never be sent to a different target after a late readback.
 */
interface LogicBaseline {
  canvasId: string;
  sourcePresent: boolean;
  sourceSha256: string | null;
}

interface LogicReadData {
  source?: string;
  source_present?: boolean;
  source_sha256?: string | null;
  baseline?: {
    canvas_id?: string;
    source_present?: boolean;
    source_sha256?: string | null;
  };
}

interface LogicSaveResponse {
  success: boolean;
  data?: LogicReadData & {
    source_present?: boolean;
    source_sha256?: string | null;
    baseline?: { canvas_id?: string; source_present?: boolean; source_sha256?: string | null };
  };
}

/** One entry from the existing mini_app_logic_history audit trail. */
interface LogicRevision {
  version: number;
  created_at: string;
  created_by: string;
  preview: string;
}

interface LogicBaselineLoad {
  canvasId: string;
  status: "pending" | "ready" | "failed";
}

interface RestoreRecovery {
  canvasId: string;
  message: string;
}

/**
 * The history action returns one exact envelope:
 * { success, app_id, history: [{ version, created_at, created_by, preview }] }.
 * Reject anything else (including speculative aliases) rather than rendering
 * a malformed response as an empty revision list. Null audit fields map to the
 * display strings the revision-list component already expects.
 */
function parseLogicHistory(result: unknown, requestedApp: string): LogicRevision[] | null {
  if (!result || typeof result !== "object" || Array.isArray(result)) return null;
  const body = result as Record<string, unknown>;
  if (body.success !== true) return null;
  if (typeof body.app_id !== "string" || body.app_id !== requestedApp) return null;
  if (!Array.isArray(body.history)) return null;
  const revisions: LogicRevision[] = [];
  for (const row of body.history) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return null;
    const entry = row as Record<string, unknown>;
    const version = entry.version;
    if (typeof version !== "number" || !Number.isInteger(version) || version <= 0) {
      return null;
    }
    const createdAt = entry.created_at;
    const createdBy = entry.created_by;
    const preview = entry.preview;
    if (createdAt !== null && typeof createdAt !== "string") return null;
    if (createdBy !== null && typeof createdBy !== "string") return null;
    if (typeof preview !== "string") return null;
    revisions.push({
      version,
      created_at: typeof createdAt === "string" ? createdAt : "",
      created_by: typeof createdBy === "string" ? createdBy : "",
      preview,
    });
  }
  return revisions;
}

/**
 * The revert action's exact success result is
 * { success: true, version, reverted_to, app_id }. Confirm only a positive
 * integer `version`, `reverted_to` equal to the requested target version, and
 * the requested `app_id`; anything incomplete or unexpected returns null and
 * is treated as an unknown outcome (never guessed).
 */
function confirmedRevertVersion(
  result: unknown,
  requestedApp: string,
  targetVersion: number
): number | null {
  if (!result || typeof result !== "object" || Array.isArray(result)) return null;
  const body = result as Record<string, unknown>;
  if (body.success !== true) return null;
  const version = body.version;
  if (typeof version !== "number" || !Number.isInteger(version) || version <= 0) {
    return null;
  }
  if (body.reverted_to !== targetVersion) return null;
  if (typeof body.app_id !== "string" || body.app_id !== requestedApp) return null;
  return version;
}

/**
 * A 4xx response is a definitive rejection (including the baseline 409), so
 * the restore was not applied. Network/timeout/5xx failures leave the outcome
 * unknown — never replay those automatically.
 */
function restoreOutcomeUncertain(err: unknown): boolean {
  const error = err as {
    status?: number;
    response?: { status?: number };
    actionResult?: unknown;
  };
  const result = error?.actionResult;
  if (result && typeof result === "object" && (result as { success?: boolean }).success === false) {
    return false;
  }
  const status = error?.status ?? error?.response?.status;
  if (typeof status === "number") return status <= 0 || status === 408 || status >= 500;
  return true;
}

/** The known mini-app action result schema for a semantic failure. */
interface MiniAppHandlerFailure {
  success?: boolean;
  error?: string;
}

/**
 * Recover the already-exposed safe handler error from a body-level RPC
 * failure. `rpc-client` preserves the action's typed result as
 * `RpcError.actionResult`; only trust it when the handler itself reported
 * `success: false` and supplied a string error. Transport/HTTP/unknown
 * failures have no `actionResult`, so they keep the generic RpcError message
 * instead of surfacing private axios/server detail.
 */
function handlerFailureMessage(err: unknown): string | null {
  const result = (err as { actionResult?: unknown })?.actionResult;
  if (!result || typeof result !== "object") return null;
  const failure = result as MiniAppHandlerFailure;
  if (failure.success !== false) return null;
  return typeof failure.error === "string" && failure.error.trim() ? failure.error : null;
}

export function MiniAppHarness({ canvasId, lastMessage, onSocketMessage, agentId, canvasType }: MiniAppHarnessProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [showAcceptance, setShowAcceptance] = useState(false);
  const [scaffolding, setScaffolding] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [result, setResult] = useState<DevRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Authoring target — set after scaffold (the app's blueprint source canvas).
  const [appId, setAppId] = useState<string | null>(null);
  const [blueprintCanvasId, setBlueprintCanvasId] = useState<string | null>(null);
  const [installedCanvasId, setInstalledCanvasId] = useState<string | null>(null);

  // Manifest editor fields.
  const [appName, setAppName] = useState<string>("");
  const [declaredScopes, setDeclaredScopes] = useState<string>("canvas_render");
  const [dependencies, setDependencies] = useState<string>("");
  // Base canvas kind the app builds ON — any slug (crm, accounting, inventory,
  // sheets, …); defaults to the host canvas's type so authoring from inside an
  // existing typed canvas extends it. The backend accepts any well-formed
  // slug and self-registers unknown kinds.
  const [baseType, setBaseType] = useState<string>(canvasType || "mini_app");

  // Live instance state previewed from the WS mini_app_state broadcast.
  const [liveState, setLiveState] = useState<{ version: number; data: Record<string, unknown> } | null>(null);

  // The revision this editor read back. null = no baseline (legacy save).
  const [baseline, setBaseline] = useState<LogicBaseline | null>(null);
  // Whether the baseline readback for a target succeeded. A failed blueprint
  // readback must block writes instead of silently degrading to a legacy save.
  const [baselineLoad, setBaselineLoad] = useState<LogicBaselineLoad>({
    canvasId,
    status: "pending",
  });
  // Revision history visibility, reload epoch (bumped after confirmed writes),
  // and the restore/readback lock.
  const [showHistory, setShowHistory] = useState(false);
  const [historyEpoch, setHistoryEpoch] = useState(0);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [restoreRecovery, setRestoreRecovery] = useState<RestoreRecovery | null>(null);
  // Monotonic token: a slow readback for an old target must never overwrite
  // the source/baseline of the current target.
  const loadSeq = useRef(0);
  const refreshSeq = useRef(0);
  // Set as soon as the user has an explicit authoring target (scaffold/install
  // result). A late mini_app_list readback must not steal that target.
  const explicitTarget = useRef(false);

  const targetCanvasId = blueprintCanvasId ?? canvasId;
  // Latest target for async continuations (a save that finishes after the
  // target moved must not adopt its response as the new target's baseline).
  const targetRef = useRef(targetCanvasId);
  targetRef.current = targetCanvasId;

  // Current values for async continuations/guards. A restore that resolves
  // after the target moved must not adopt a baseline or refresh source for the
  // new target.
  const appIdRef = useRef(appId);
  appIdRef.current = appId;
  const blueprintRef = useRef(blueprintCanvasId);
  blueprintRef.current = blueprintCanvasId;
  const baselineRef = useRef(baseline);
  baselineRef.current = baseline;
  const baselineLoadRef = useRef(baselineLoad);
  baselineLoadRef.current = baselineLoad;
  const operationStateRef = useRef({ loading, saving, running });
  operationStateRef.current = { loading, saving, running };
  // Synchronous guard: a restore must not start in the same tick a save/run
  // begins, before React has rendered the disabled button state.
  const saveRunBusyRef = useRef(false);

  // Restore and its readback share one lock. Counting makes nested refreshes
  // safe without releasing the editor between the two operations.
  const historyBusyCount = useRef(0);
  const historyBusyRef = useRef(false);
  const beginHistoryBusy = useCallback(() => {
    historyBusyCount.current += 1;
    historyBusyRef.current = true;
    setHistoryBusy(true);
  }, []);
  const endHistoryBusy = useCallback(() => {
    historyBusyCount.current = Math.max(0, historyBusyCount.current - 1);
    if (historyBusyCount.current === 0) {
      historyBusyRef.current = false;
      setHistoryBusy(false);
    }
  }, []);

  const applyLogicRead = useCallback((target: string, data?: LogicReadData): boolean => {
    const readBaseline = data?.baseline;
    // Never relabel another canvas's baseline as this target's baseline.
    if (readBaseline?.canvas_id && readBaseline.canvas_id !== target) {
      setBaseline(null);
      setBaselineLoad({ canvasId: target, status: "failed" });
      return false;
    }
    const sourcePresent =
      readBaseline?.source_present ??
      data?.source_present ??
      (data?.source_sha256 != null);
    const sourceSha256 =
      readBaseline?.source_sha256 ?? data?.source_sha256 ?? null;
    setSource(data?.source ?? "");
    setBaseline({
      canvasId: target,
      sourcePresent,
      sourceSha256,
    });
    setBaselineLoad({ canvasId: target, status: "ready" });
    setRestoreRecovery((current) => (current?.canvasId === target ? null : current));
    // A successful readback resolves the "outcome uncertain" warning.
    setError(null);
    return true;
  }, []);

  const applyMissingLogic = useCallback((target: string) => {
    setSource("");
    setBaseline({
      canvasId: target,
      sourcePresent: false,
      sourceSha256: null,
    });
    setBaselineLoad({ canvasId: target, status: "ready" });
  }, []);

  /**
   * A blueprint may only be written when this editor's baseline was read from
   * that exact target. Ordinary canvases keep the legacy no-baseline save path.
   */
  const blueprintWriteBlockMessage = useCallback((target: string): string | null => {
    if (blueprintRef.current !== target) return null;
    const load = baselineLoadRef.current;
    const current = baselineRef.current;
    if (!load || load.canvasId !== target || load.status !== "ready") {
      return "The blueprint logic baseline could not be loaded; refusing to write. Reload before saving or restoring.";
    }
    if (!current || current.canvasId !== target) {
      return "The blueprint logic baseline does not match this target; refusing to write. Reload before saving or restoring.";
    }
    return null;
  }, []);

  // Load existing logic + its readback baseline for the target canvas.
  useEffect(() => {
    const seq = ++loadSeq.current;
    // Invalidate any restore readback started for the previous target.
    refreshSeq.current += 1;
    const loadedTarget = targetCanvasId;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRestoreRecovery(null);
    // Do not carry a previous target's baseline across the switch.
    setBaseline(null);
    setBaselineLoad({ canvasId: loadedTarget, status: "pending" });
    apiClient
      .get<{ success: boolean; data?: LogicReadData }>(`/api/canvas/${loadedTarget}/logic`)
      .then((resp) => {
        if (cancelled || seq !== loadSeq.current) return;
        if (!resp.data?.data) {
          // A success envelope without a readback is not a usable baseline.
          setBaselineLoad({ canvasId: loadedTarget, status: "failed" });
          return;
        }
        applyLogicRead(loadedTarget, resp.data.data);
      })
      .catch((err) => {
        if (cancelled || seq !== loadSeq.current) return;
        // 404 = no logic yet on this canvas; any other failure must not wipe
        // the source the user is editing (transient errors are not "no logic").
        if ((err as { response?: { status?: number } })?.response?.status === 404) {
          applyMissingLogic(loadedTarget);
        } else {
          // A blueprint write must not fall back to a legacy save when its
          // baseline readback failed. Keep the user's source intact.
          setBaselineLoad({ canvasId: loadedTarget, status: "failed" });
        }
      })
      .finally(() => {
        if (!cancelled && seq === loadSeq.current) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (loadSeq.current === seq) loadSeq.current += 1;
    };
  }, [targetCanvasId, applyLogicRead, applyMissingLogic]);

  /** Baseline fields for a save of `target`, or {} for a legacy save. */
  const baselineFields = useCallback((target: string): Record<string, unknown> => {
    if (!baseline || baseline.canvasId !== target) return {};
    if (!baseline.sourcePresent) {
      // Explicit null is meaningful: the readback saw no logic row. It must
      // not be confused with omitting the baseline entirely.
      return {
        expected_source_present: false,
        expected_source_sha256: null,
      };
    }
    return {
      expected_source_present: true,
      ...(baseline.sourceSha256 ? { expected_source_sha256: baseline.sourceSha256 } : {}),
    };
  }, [baseline]);

  /** Adopt the baseline the server reports for a successful save. */
  const adoptSavedBaseline = useCallback((target: string, data: LogicSaveResponse["data"]) => {
    if (!data) return;
    const savedBaseline = data.baseline;
    const sourcePresent = savedBaseline?.source_present ?? data.source_present ?? true;
    const sourceSha256 = savedBaseline?.source_sha256 ?? data.source_sha256 ?? null;
    setBaseline({
      canvasId: savedBaseline?.canvas_id ?? target,
      sourcePresent,
      sourceSha256,
    });
    setBaselineLoad({ canvasId: target, status: "ready" });
  }, []);

  /**
   * Read the blueprint logic back and adopt its source + baseline. Never
   * applies an old readback to a target that has since moved.
   */
  const refreshEditorFor = useCallback(async (target: string): Promise<boolean> => {
    if (blueprintRef.current !== target) return false;
    beginHistoryBusy();
    const seq = ++refreshSeq.current;
    try {
      const resp = await apiClient.get<{ success: boolean; data?: LogicReadData }>(
        `/api/canvas/${target}/logic`
      );
      if (
        targetRef.current !== target ||
        blueprintRef.current !== target ||
        seq !== refreshSeq.current
      ) {
        return false;
      }
      if (!applyLogicRead(target, resp.data?.data)) {
        throw new Error("The readback baseline does not match this blueprint target.");
      }
      return true;
    } catch (e) {
      if (targetRef.current === target && blueprintRef.current === target) {
        // The restore may have committed even though the readback failed.
        // Drop the now-possibly-stale baseline so nothing can write blindly;
        // the recovery affordance below only re-reads.
        setBaseline(null);
        setBaselineLoad({ canvasId: target, status: "failed" });
        setRestoreRecovery({
          canvasId: target,
          message:
            "The editor could not be refreshed after the restore. Re-check the editor below (read-only); the restore will not be replayed.",
        });
      }
      throw e;
    } finally {
      endHistoryBusy();
    }
  }, [applyLogicRead, beginHistoryBusy, endHistoryBusy]);

  const refreshEditor = useCallback(async (): Promise<void> => {
    const target = targetRef.current;
    if (!target || blueprintRef.current !== target) return;
    await refreshEditorFor(target);
  }, [refreshEditorFor]);

  /** Load the app's audit trail for the revision-list component. */
  const loadRevisions = useCallback(async (): Promise<LogicRevision[]> => {
    const requestedApp = appIdRef.current;
    if (!requestedApp) return [];
    const result = await rpc.call<unknown>("mini_app_logic_history", {
      app_id: requestedApp,
    });
    // An async app switch must not paint the old app's history.
    if (appIdRef.current !== requestedApp) return [];
    const revisions = parseLogicHistory(result, requestedApp);
    if (!revisions) {
      throw new Error("Logic history returned an unexpected response.");
    }
    return revisions;
  }, []);

  /**
   * Restore an audited revision. The resource is guarded by the exact baseline
   * this editor read, so a 409 reaches the user instead of being replayed.
   */
  const restoreRevision = useCallback(async (version: number): Promise<number> => {
    if (!Number.isInteger(version) || version <= 0) {
      throw new Error("Invalid revision version.");
    }
    const requestedApp = appIdRef.current;
    const target = targetRef.current;
    if (!requestedApp) throw new Error("Scaffold the mini-app first.");
    if (!target || blueprintRef.current !== target) {
      throw new Error("Revision restore is only available for a mini-app blueprint.");
    }
    if (historyBusyRef.current) {
      throw new Error("A revision restore or readback is already in progress.");
    }
    const operations = operationStateRef.current;
    if (operations.loading || operations.saving || operations.running || saveRunBusyRef.current) {
      throw new Error("Wait for the current load, save, or run to finish before restoring.");
    }
    const blocked = blueprintWriteBlockMessage(target);
    if (blocked) throw new Error(blocked);

    // Established baseline fields (expected_source_present/_sha256). A
    // baseline-checked mutation must not be replayed by transport retry.
    const fields = baselineFields(target);
    if (!Object.prototype.hasOwnProperty.call(fields, "expected_source_present")) {
      throw new Error("The blueprint logic baseline is unavailable; refusing to restore.");
    }
    beginHistoryBusy();
    setError(null);
    setNotice(null);
    setRestoreRecovery(null);
    try {
      const result = await rpc.call<unknown>(
        "mini_app_revert_logic",
        {
          app_id: requestedApp,
          version,
          ...fields,
        },
        { retry: false }
      );
      // Only the exact success envelope confirms the revert. A partial or
      // unfamiliar response leaves the outcome unknown; never infer a version.
      const newVersion = confirmedRevertVersion(result, requestedApp, version);
      if (newVersion === null) {
        throw new Error("The revert response could not be confirmed.");
      }

      // A target/app switch while the restore was in flight: the write belongs
      // to the old blueprint. Do not refresh or adopt anything for the new one.
      if (
        targetRef.current !== target ||
        blueprintRef.current !== target ||
        appIdRef.current !== requestedApp
      ) {
        return newVersion;
      }

      // A confirmed restore is another committed logic revision.
      setHistoryEpoch((epoch) => epoch + 1);
      let refreshed = false;
      try {
        refreshed = await refreshEditorFor(target);
      } catch {
        // refreshEditorFor already recorded the read-only recovery.
        refreshed = false;
      }
      if (
        targetRef.current !== target ||
        blueprintRef.current !== target ||
        appIdRef.current !== requestedApp
      ) {
        return newVersion;
      }
      if (refreshed) {
        setNotice(`Restored revision ${newVersion}. Editor refreshed from the blueprint.`);
      } else {
        setNotice(`Restore returned revision ${newVersion}; editor recovery is available below.`);
      }
      return newVersion;
    } catch (e) {
      if (targetRef.current === target) {
        if (restoreOutcomeUncertain(e)) {
          // The request may have committed. Do not replay it; block writes
          // until the user performs the read-only re-check.
          setBaseline(null);
          setBaselineLoad({ canvasId: target, status: "failed" });
          setRestoreRecovery({
            canvasId: target,
            message:
              "The restore outcome is uncertain. Re-check the editor below (read-only); the restore was not replayed.",
          });
          setError("Restore outcome uncertain — re-check the editor before editing or saving.");
        } else {
          setError(handlerFailureMessage(e) ?? saveFailureMessage(e));
        }
      }
      throw e;
    } finally {
      endHistoryBusy();
    }
  }, [
    baselineFields,
    blueprintWriteBlockMessage,
    beginHistoryBusy,
    endHistoryBusy,
    refreshEditorFor,
  ]);

  // Consume live mini-app state broadcasts from the WS stream.
  const applyLiveState = useCallback((msg: any) => {
    const data = msg?.data ?? msg;
    if (
      msg?.type === "canvas:update" &&
      data?.action === "mini_app_state" &&
      data?.canvas_id &&
      data.canvas_id === (installedCanvasId ?? canvasId)
    ) {
      setLiveState({ version: data.version ?? 0, data: data.data ?? {} });
    }
  }, [canvasId, installedCanvasId]);

  // Live broadcasts, losslessly — see the note on CanvasPanel's listener.
  useEffect(() => {
    if (!onSocketMessage) return;
    return onSocketMessage(applyLiveState);
  }, [onSocketMessage, applyLiveState]);

  // The parent's current frame, applied whenever it changes. Not an
  // alternative to the listener: /canvas/[id] passes both, and gating the prop
  // on `!onSocketMessage` meant the harness never saw the frame that was
  // handed to it directly.
  useEffect(() => {
    if (lastMessage) applyLiveState(lastMessage);
  }, [lastMessage, applyLiveState]);

  // Reconnect after a page reload: appId lives in component state, so a
  // refresh orphaned the draft — Dev-Run/Publish/Install stayed disabled
  // until a fresh scaffold. Match the host canvas against the user's apps'
  // blueprint canvases and restore the authoring target.
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(rpc.call("mini_app_list", {}))
      .then((res: any) => {
        if (cancelled || explicitTarget.current || !res?.apps?.length) return;
        const mine = res.apps.find((a: any) => a.blueprint_canvas_id === canvasId);
        if (mine?.id) {
          // The matched blueprint is the host canvas itself, whose logic the
          // existing load already read. Keep that baseline/source valid rather
          // than parking the panel in a reload that the unchanged target would
          // never trigger.
          setAppId(mine.id);
          setBlueprintCanvasId(mine.blueprint_canvas_id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [canvasId]);

  const scopesList = useMemo(
    () => declaredScopes.split(",").map((s) => s.trim()).filter(Boolean),
    [declaredScopes]
  );
  const depsList = useMemo(
    () => dependencies.split(",").map((s) => s.trim()).filter(Boolean),
    [dependencies]
  );

  const isBlueprintTarget = blueprintCanvasId != null && blueprintCanvasId === targetCanvasId;
  const baselineReady =
    baselineLoad.canvasId === targetCanvasId && baselineLoad.status === "ready";
  const baselineMatches = baseline?.canvasId === targetCanvasId;
  const blueprintWriteBlocked = isBlueprintTarget && (!baselineReady || !baselineMatches);
  const canRestore =
    !!appId &&
    isBlueprintTarget &&
    baselineReady &&
    baselineMatches &&
    !loading &&
    !saving &&
    !running &&
    !historyBusy;

  async function handleScaffold() {
    setScaffolding(true);
    setError(null);
    setNotice(null);
    const normalizedType = baseType.trim().toLowerCase();
    try {
      const res = (await rpc.call("mini_app_scaffold", {
        name: appName.trim() || "Untitled Mini-App",
        declared_scopes: scopesList,
        dependencies: depsList,
        spec: normalizedType && normalizedType !== "mini_app" ? { canvas_type: normalizedType } : {},
      })) as MiniAppScaffoldResult;
      if (!res.success) {
        setError(res.error ?? "Scaffold failed");
        return;
      }
      explicitTarget.current = true;
      // The target is changing: disable mutations and drop the old target's
      // baseline until the new logic readback supplies one.
      setLoading(true);
      setBaseline(null);
      setAppId(res.app_id ?? null);
      setBlueprintCanvasId(res.canvas_id ?? null);
      if (res.logic_source) setSource(res.logic_source);
      setNotice(
        `Draft app "${appName.trim() || "Untitled Mini-App"}"` +
          `${normalizedType && normalizedType !== "mini_app" ? ` (on ${normalizedType})` : ""} created (${res.app_id}). ` +
          `Source canvas: ${res.canvas_id}. Edit logic, then Dev-Run → Publish → Install.`
      );
    } catch (e) {
      const err = e as { message?: string };
      setError(handlerFailureMessage(e) ?? (err?.message || "Failed to scaffold mini-app"));
    } finally {
      setScaffolding(false);
    }
  }

  function saveFailureMessage(e: unknown): string {
    const err = e as {
      status?: number;
      response?: { status?: number; data?: { detail?: unknown } };
      message?: string;
    };
    const detail = err?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    const status = err?.response?.status ?? err?.status;
    if (status === 409) {
      // Deliberately keep `source` untouched: the user's unsaved draft is the
      // only copy if a peer committed v2 after this editor read v1.
      return "Logic changed after it was loaded. Your draft is preserved; reload to reconcile before saving.";
    }
    return "Failed to save logic";
  }

  async function saveDraft(target: string): Promise<LogicSaveResponse["data"]> {
    // Blueprint writes require a baseline read from this exact target. Legacy
    // (non-blueprint) canvas saves keep their ordinary no-baseline path.
    const blocked = blueprintWriteBlockMessage(target);
    if (blocked) throw new Error(blocked);
    // A baseline-checked mutation must never be replayed automatically: a
    // 409 has to reach the editor with its unsaved text intact.
    const noRetry = { retry: false } as Record<string, unknown>;
    const resp = await apiClient.put<LogicSaveResponse>(
      `/api/canvas/${target}/logic`,
      {
        source,
        language: "python",
        agent_id: agentId,
        // Only sends a baseline when this editor's read was for THIS target.
        ...baselineFields(target),
      },
      noRetry as unknown as Parameters<typeof apiClient.put>[2]
    );
    if (targetRef.current === target) {
      adoptSavedBaseline(target, resp.data?.data);
      // Confirmed save: revision history must reload for this app.
      setHistoryEpoch((epoch) => epoch + 1);
    }
    return resp.data?.data;
  }

  async function handleSave() {
    if (historyBusyRef.current) {
      setError("Wait for the revision restore/readback to finish before saving.");
      return;
    }
    if (saveRunBusyRef.current) {
      setError("A save or run is already in progress.");
      return;
    }
    saveRunBusyRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await saveDraft(targetCanvasId);
      setNotice("Logic saved (checkpointed to the audit trail).");
    } catch (e) {
      setError(saveFailureMessage(e));
    } finally {
      saveRunBusyRef.current = false;
      setSaving(false);
    }
  }

  async function handleDevRun() {
    if (historyBusyRef.current) {
      setError("Wait for the revision restore/readback to finish before running.");
      return;
    }
    if (saveRunBusyRef.current) {
      setError("A save or run is already in progress.");
      return;
    }
    if (!appId) {
      setError("Scaffold the mini-app first (creates the draft app + source canvas).");
      return;
    }
    saveRunBusyRef.current = true;
    setRunning(true);
    setError(null);
    setResult(null);
    const runTarget = targetCanvasId;
    try {
      // Autosave must also carry the readback baseline. If a peer changed the
      // logic after this editor loaded it, the 409 is surfaced and the run is
      // NOT attempted (and the unsaved source remains in the editor).
      try {
        await saveDraft(runTarget);
      } catch (e) {
        setError(saveFailureMessage(e));
        return;
      }
      // Backend derives the run canvas from app.blueprint_canvas_id — only app_id (+ optional inputs) is accepted.
      const res = (await rpc.call("mini_app_dev_run", {
        app_id: appId,
        inputs: {},
      })) as DevRunResult;
      // A target switch while the dry run was in flight makes this readback
      // stale; do not paint it over the new target.
      if (targetRef.current !== runTarget) return;
      setResult(res);
      if (res?.success && res.state) {
        setLiveState({ version: res.version ?? 0, data: res.state });
      }
    } catch (e) {
      const err = e as { message?: string };
      setError(handlerFailureMessage(e) ?? (err?.message || "Dev-run failed"));
    } finally {
      saveRunBusyRef.current = false;
      setRunning(false);
    }
  }

  async function handlePublish() {
    if (!appId) {
      setError("Scaffold the mini-app first.");
      return;
    }
    setPublishing(true);
    setError(null);
    setNotice(null);
    try {
      const res = (await rpc.call("mini_app_publish", { app_id: appId })) as { success: boolean; error?: string };
      if (!res.success) {
        setError(res.error ?? "Publish failed (deps scan + rootfs must pass).");
        return;
      }
      setNotice(`Published v${(res as any).version ?? ""}. Snapshot is credential-stripped; installs are immutable.`);
    } catch (e) {
      const err = e as { message?: string };
      setError(handlerFailureMessage(e) ?? (err?.message || "Publish failed"));
    } finally {
      setPublishing(false);
    }
  }

  async function handleInstall() {
    if (!appId) {
      setError("Scaffold the mini-app first.");
      return;
    }
    setInstalling(true);
    setError(null);
    setNotice(null);
    try {
      const res = (await rpc.call("mini_app_install", { app_id: appId })) as {
        success: boolean;
        canvas_id?: string;
        error?: string;
      };
      if (!res.success) {
        setError(res.error ?? "Install failed");
        return;
      }
      setInstalledCanvasId(res.canvas_id ?? null);
      setLiveState(null);
      setNotice(`Installed → instance canvas ${res.canvas_id}. Runs will broadcast state here.`);
    } catch (e) {
      const err = e as { message?: string };
      setError(handlerFailureMessage(e) ?? (err?.message || "Install failed"));
    } finally {
      setInstalling(false);
    }
  }

  return (
    <div className="border-t border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 flex flex-col max-h-[45vh]">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-between px-3 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-zinc-700 dark:text-zinc-200">
          <Boxes className="h-3.5 w-3.5 text-indigo-500" />
          Mini-App Harness
          {appId && (
            <span className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
              {appId.slice(0, 8)}
            </span>
          )}
        </span>
        {collapsed ? (
          <ChevronUp className="h-3.5 w-3.5 text-zinc-400" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
        )}
      </button>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-3 min-h-0">
          {/* Journey guidance: the panel is discoverable but the loop and its
              gates (chat-first authoring, Firecracker-only execution) aren't
              obvious from the button row alone. */}
          <div className="px-2 py-1.5 text-[11px] text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/40 rounded flex gap-1.5">
            <Sparkles className="h-3 w-3 shrink-0 mt-0.5 text-indigo-400" />
            <span>
              Easiest path: give it to your agent to code — run your hire (Agent
              Workspace → Run) with e.g. &ldquo;scaffold a mini-app that tracks
              expenses&rdquo; — and it drives scaffold → code → dev-run → test →
              publish → install, while this panel shows the live state. Or author
              manually below. Executions run in a Firecracker microVM: on hosts
              without one, dev-run fails closed (operator setup:
              docs/deployment/FIRECRACKER_HOST_SETUP.md).
            </span>
          </div>

          {/* Manifest editor */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              App name
              <input
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                placeholder="Expense Tracker"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Base canvas type (any kind)
              <input
                value={baseType}
                onChange={(e) => setBaseType(e.target.value)}
                list="miniapp-base-types"
                placeholder="crm · accounting · sheets …"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
              <datalist id="miniapp-base-types">
                {["mini_app", "sheets", "docs", "email", "generic", "coding", "terminal", "orchestration"].map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Declared scopes (comma-sep)
              <input
                value={declaredScopes}
                onChange={(e) => setDeclaredScopes(e.target.value)}
                placeholder="canvas_render"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
            <label className="flex flex-col gap-1 text-[10px] text-zinc-500">
              Dependencies (comma-sep)
              <input
                value={dependencies}
                onChange={(e) => setDependencies(e.target.value)}
                placeholder="pandas==2.2"
                className="px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-transparent"
              />
            </label>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleScaffold}
              disabled={scaffolding}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 disabled:opacity-50"
            >
              {scaffolding ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Scaffold
            </button>
            <button
              onClick={handleSave}
              disabled={saving || loading || historyBusy || blueprintWriteBlocked}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              Save Logic
            </button>
            <button
              onClick={handleDevRun}
              disabled={running || loading || historyBusy || blueprintWriteBlocked || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              Dev-Run (dry)
            </button>
            <button
              onClick={handlePublish}
              disabled={publishing || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {publishing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Rocket className="h-3 w-3" />}
              Publish
            </button>
            <button
              onClick={handleInstall}
              disabled={installing || !appId}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 disabled:opacity-50"
            >
              {installing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Boxes className="h-3 w-3" />}
              Install
            </button>
          </div>

          {/* Notice / error strips */}
          {notice && (
            <div className="px-2 py-1 text-xs text-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 dark:text-indigo-300 rounded">
              {notice}
            </div>
          )}
          {error && (
            <div className="px-2 py-1 text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded">
              {error}
            </div>
          )}
          {restoreRecovery && restoreRecovery.canvasId === targetCanvasId && (
            <div className="px-2 py-1.5 text-xs text-amber-700 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-300 rounded space-y-1">
              <div>{restoreRecovery.message}</div>
              <button
                type="button"
                disabled={historyBusy}
                onClick={() => {
                  // Read-only recovery: re-read the blueprint. Never replay the
                  // restore request whose outcome is uncertain.
                  void refreshEditor().catch(() => {});
                }}
                className="flex items-center gap-1 px-2 py-1 text-[11px] rounded border border-amber-300 dark:border-amber-700 disabled:opacity-50"
              >
                {historyBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                {historyBusy ? "Re-checking…" : "Re-check editor (read-only)"}
              </button>
            </div>
          )}

          {/* Logic editor */}
          <div className="flex items-center gap-1 text-[10px] text-zinc-500">
            <Code2 className="h-3 w-3" /> Python logic — <span className="font-mono">{targetCanvasId}</span>
          </div>
          {loading ? (
            <div className="p-2 text-xs text-zinc-500 flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" /> Loading…
            </div>
          ) : (
            <Editor
              height="180px"
              defaultLanguage="python"
              theme="vs-dark"
              value={source}
              onChange={(val) => setSource(val ?? "")}
              options={{
                minimap: { enabled: false },
                fontSize: 12,
                scrollBeyondLastLine: false,
                readOnly: historyBusy,
              }}
            />
          )}

          {appId && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  aria-expanded={showAcceptance}
                  className="rounded border border-zinc-200 px-2 py-1 text-xs dark:border-zinc-700"
                  onClick={() => setShowAcceptance((visible) => !visible)}
                >
                  {showAcceptance ? "Hide acceptance tests" : "Show acceptance tests"}
                </button>
                <button
                  type="button"
                  aria-expanded={showHistory}
                  className="rounded border border-zinc-200 px-2 py-1 text-xs dark:border-zinc-700"
                  onClick={() => setShowHistory((visible) => !visible)}
                >
                  {showHistory ? "Hide revision history" : "Show revision history"}
                </button>
              </div>
              {showAcceptance && (
                <AcceptanceCaseEditor key={appId} appId={appId} rpc={rpc.call.bind(rpc)} sourceRevision={source} />
              )}
              {showHistory && (
                <LogicRevisionHistory
                  key={appId}
                  load={loadRevisions}
                  restore={restoreRevision}
                  refreshEditor={refreshEditor}
                  canRestore={canRestore}
                  epoch={historyEpoch}
                />
              )}
            </div>
          )}

          {/* Dev-run result (stdout/stderr + state) */}
          {result && (
            <div className="px-2 py-2 text-xs font-mono border border-zinc-200 dark:border-zinc-700 rounded space-y-1">
              {result.error && (
                <pre className="whitespace-pre-wrap text-red-600 dark:text-red-400">{result.error}</pre>
              )}
              {result.stdout && (
                <pre className="whitespace-pre-wrap text-emerald-600 dark:text-emerald-400">{result.stdout}</pre>
              )}
              {result.stderr && (
                <pre className="whitespace-pre-wrap text-red-600 dark:text-red-400">{result.stderr}</pre>
              )}
              <div className="text-zinc-400">exit code: {result.exit_code ?? "—"} · state_changed: {String(!!result.state_changed)}</div>
              {result.state !== undefined && (
                <pre className="whitespace-pre-wrap text-zinc-300 bg-zinc-900/60 p-2 rounded">
                  {JSON.stringify({ state: result.state, proposed_ops: result.proposed_ops ?? [] }, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* Live instance state preview */}
          <div className="flex items-center gap-1 text-[10px] text-zinc-500">
            <Radio className="h-3 w-3 text-emerald-500" /> Live instance state
            {liveState ? ` (v${liveState.version})` : " — awaiting canvas:update"}
          </div>
          {liveState && (
            <pre className="whitespace-pre-wrap text-[11px] font-mono text-zinc-300 bg-zinc-900/60 p-2 rounded max-h-40 overflow-auto">
              {JSON.stringify(liveState.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default MiniAppHarness;
