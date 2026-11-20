import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  clearStockInvoiceLaunchKey,
  getStockInvoiceLaunchKey,
} from '@/lib/stock-invoice-launch-key';
import type { WorkflowLaunchReceipt } from '@/lib/workflow-launch-receipt';

export const STOCK_ACCOUNT_OWNER_OPTIONS_URL =
  '/api/v1/workflows/workflows/htn_invoice_followup/account-owner-options';
export const STOCK_AUTH_ME_URL = '/api/auth/me';

const STOCK_STORAGE_PROBE_KEY = '__stock_invoice_launch_storage_probe__';
const STOCK_SETTLED_LAUNCH_KEY = 'stock-invoice-launch-settled:v1';
const AUTH_CONTEXT_CHANGED_MESSAGE =
  'Your sign-in changed after this launch setup loaded. Retry setup to revalidate before launching.';
const OWNER_FORM_KEYS = new Set([
  'account_owner_user_id',
  'accountOwnerUserId',
  'account_owner',
  'accountOwner',
]);

export interface StockAccountOwnerOption {
  userId: string;
  displayLabel: string;
}

export interface StockLaunchIdentity {
  userId: string;
  workspaceId: string;
  tenantId: string;
}

export interface PreparedStockLaunch {
  digest: string;
  idempotencyKey: string;
  accountOwnerUserId: string | null;
  /** The exact normalized invoice number represented by the digest. */
  invoiceNumber?: string;
  /** Captured in memory only; the same credential context used for scope + POST. */
  authToken?: string | null;
}

export interface SettledStockLaunch {
  digest: string;
  idempotencyKey: string;
  kind: 'attached' | 'terminal';
  executionId: string | null;
}

export class StockLaunchUnconfirmedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StockLaunchUnconfirmedError';
  }
}

const readIdentifier = (value: unknown): string | null => {
  if (typeof value === 'string' && value.trim().length > 0) {
    return value.trim();
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
};

const getAuthToken = (): string | null => {
  try {
    return typeof window !== 'undefined'
      ? window.localStorage.getItem('auth_token')
      : null;
  } catch {
    return null;
  }
};

const getStockAuthHeaders = (
  token: string | null,
): Record<string, string> =>
  token ? { Authorization: `Bearer ${token}` } : {};

const authenticatedGet = async (
  path: string,
  token: string | null,
): Promise<unknown> => {
  const response = await fetch(path, {
    method: 'GET',
    credentials: 'include',
    headers: getStockAuthHeaders(token),
  });

  if (!response.ok) {
    throw new Error(`Request failed (HTTP ${response.status}).`);
  }

  return response.json();
};

export const parseStockLaunchIdentity = (data: unknown): StockLaunchIdentity => {
  if (data === null || typeof data !== 'object' || Array.isArray(data)) {
    throw new StockLaunchUnconfirmedError(
      'Your signed-in identity could not be confirmed.',
    );
  }

  const payload = data as Record<string, unknown>;
  const nestedUser =
    payload.user !== null
    && typeof payload.user === 'object'
    && !Array.isArray(payload.user)
      ? (payload.user as Record<string, unknown>)
      : null;

  const userId =
    readIdentifier(payload.id)
    ?? readIdentifier(payload.user_id)
    ?? readIdentifier(nestedUser?.id)
    ?? readIdentifier(nestedUser?.user_id);
  const workspaceId =
    readIdentifier(payload.workspace_id)
    ?? readIdentifier(nestedUser?.workspace_id);
  const tenantId =
    readIdentifier(payload.tenant_id)
    ?? readIdentifier(nestedUser?.tenant_id);

  if (!userId || !workspaceId || !tenantId) {
    throw new StockLaunchUnconfirmedError(
      'Your signed-in user, workspace, or tenant scope could not be confirmed. Sign in again before launching.',
    );
  }

  return { userId, workspaceId, tenantId };
};

export const parseStockAccountOwnerOptions = (
  data: unknown,
): StockAccountOwnerOption[] => {
  if (!Array.isArray(data)) {
    throw new StockLaunchUnconfirmedError(
      'Account owner options could not be confirmed. Retry before launching.',
    );
  }

  const seen = new Set<string>();
  return data.map((entry) => {
    if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) {
      throw new StockLaunchUnconfirmedError(
        'Account owner options could not be confirmed. Retry before launching.',
      );
    }

    const payload = entry as Record<string, unknown>;
    const userId = readIdentifier(payload.user_id);
    const displayLabel =
      typeof payload.display_label === 'string'
        ? payload.display_label.trim()
        : '';

    if (!userId || !displayLabel || seen.has(userId)) {
      throw new StockLaunchUnconfirmedError(
        'Account owner options could not be confirmed. Retry before launching.',
      );
    }

    seen.add(userId);
    return { userId, displayLabel };
  });
};

const fetchStockLaunchIdentity = async (
  token: string | null,
): Promise<StockLaunchIdentity> =>
  parseStockLaunchIdentity(await authenticatedGet(STOCK_AUTH_ME_URL, token));

const fetchStockAccountOwnerOptions = async (
  token: string | null,
): Promise<StockAccountOwnerOption[]> =>
  parseStockAccountOwnerOptions(
    await authenticatedGet(STOCK_ACCOUNT_OWNER_OPTIONS_URL, token),
  );

const getStockSessionStorage = (): Storage => {
  try {
    if (typeof window === 'undefined' || !window.sessionStorage) {
      throw new Error('Session storage is unavailable.');
    }
    return window.sessionStorage;
  } catch {
    throw new StockLaunchUnconfirmedError(
      'Session storage is unavailable, so a safe launch key cannot be kept. Enable session storage before launching.',
    );
  }
};

const confirmStockLaunchStorage = (): string | null => {
  try {
    const storage = getStockSessionStorage();
    storage.setItem(STOCK_STORAGE_PROBE_KEY, '1');
    const confirmed = storage.getItem(STOCK_STORAGE_PROBE_KEY) === '1';
    storage.removeItem(STOCK_STORAGE_PROBE_KEY);
    if (!confirmed || storage.getItem(STOCK_STORAGE_PROBE_KEY) !== null) {
      throw new Error('Session storage did not retain a value.');
    }
    return null;
  } catch (error) {
    return error instanceof StockLaunchUnconfirmedError
      ? error.message
      : 'Session storage is unavailable, so a safe launch key cannot be kept. Enable session storage before launching.';
  }
};

const readSettledStockLaunch = (): SettledStockLaunch | null => {
  try {
    const storage = getStockSessionStorage();
    const raw = storage.getItem(STOCK_SETTLED_LAUNCH_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<SettledStockLaunch>;
    if (
      typeof parsed.digest !== 'string'
      || parsed.digest.length === 0
      || typeof parsed.idempotencyKey !== 'string'
      || parsed.idempotencyKey.length === 0
    ) {
      storage.removeItem(STOCK_SETTLED_LAUNCH_KEY);
      return null;
    }
    if (parsed.kind !== 'attached' && parsed.kind !== 'terminal') {
      storage.removeItem(STOCK_SETTLED_LAUNCH_KEY);
      return null;
    }

    return {
      digest: parsed.digest,
      idempotencyKey: parsed.idempotencyKey,
      kind: parsed.kind,
      executionId:
        typeof parsed.executionId === 'string' ? parsed.executionId : null,
    };
  } catch {
    return null;
  }
};

const persistSettledStockLaunch = (settled: SettledStockLaunch): void => {
  try {
    getStockSessionStorage().setItem(
      STOCK_SETTLED_LAUNCH_KEY,
      JSON.stringify(settled),
    );
  } catch {
    // Settlement remains visible in memory; only the reload-survival bit is lost.
  }
};

const clearPersistedSettledStockLaunch = (): void => {
  try {
    getStockSessionStorage().removeItem(STOCK_SETTLED_LAUNCH_KEY);
  } catch {
    // The in-memory settlement still clears, and the key helper is idempotent.
  }
};

const normalizeValue = (value: unknown): unknown => {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }

  if (Array.isArray(value)) {
    return value
      .map(normalizeValue)
      .filter((item) => item !== undefined);
  }

  if (value !== null && typeof value === 'object') {
    const normalized: Record<string, unknown> = {};
    Object.keys(value as Record<string, unknown>)
      .sort()
      .forEach((key) => {
        if (OWNER_FORM_KEYS.has(key) || key.startsWith('__')) return;
        const child = normalizeValue((value as Record<string, unknown>)[key]);
        if (child !== undefined) {
          normalized[key] = child;
        }
      });
    return normalized;
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined;
  }

  if (typeof value === 'boolean') {
    return value;
  }

  return undefined;
};

/**
 * Produces a deterministic, whitespace-normalized invoice object. The intent
 * digest deliberately uses only normalizeStockInvoiceNumber plus the selected
 * owner, so optional invoice fields do not change the launch identity.
 */
export const normalizeStockInvoice = (
  invoice: Record<string, unknown>,
): Record<string, unknown> => {
  const normalized = normalizeValue(invoice);
  return normalized !== null
    && typeof normalized === 'object'
    && !Array.isArray(normalized)
      ? (normalized as Record<string, unknown>)
      : {};
};

const toHex = (buffer: ArrayBuffer): string =>
  Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');

/**
 * The invoice number is the only invoice input that identifies a launch
 * intent. Trim it once and use this exact value both in the digest and in the
 * stock request body.
 */
export const normalizeStockInvoiceNumber = (
  invoice: Record<string, unknown>,
): string | null => {
  const value = invoice?.invoice_number;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
};

/**
 * SHA-256 over a versioned canonical payload of validated identity, the
 * normalized nonblank invoice number, and the explicitly selected owner (or
 * null). Other optional invoice inputs are deliberately ignored. The digest is
 * opaque; no raw invoice, owner, identity, or credential value is persisted.
 */
export const deriveStockInvoiceIntentDigest = async (
  identity: StockLaunchIdentity,
  invoice: Record<string, unknown>,
  ownerUserId: string | null,
): Promise<string> => {
  if (
    ownerUserId !== null
    && (typeof ownerUserId !== 'string' || ownerUserId.trim().length === 0)
  ) {
    throw new StockLaunchUnconfirmedError(
      'Choose an account owner from the available options, or choose No account owner.',
    );
  }

  const invoiceNumber = normalizeStockInvoiceNumber(invoice) ?? '';

  const canonical = JSON.stringify({
    version: 1,
    workflow: 'htn_invoice_followup',
    identity: {
      user_id: identity.userId.trim(),
      workspace_id: identity.workspaceId.trim(),
      tenant_id: identity.tenantId.trim(),
    },
    invoice_number: invoiceNumber,
    account_owner_user_id:
      ownerUserId === null ? null : ownerUserId.trim(),
  });

  const subtle =
    typeof globalThis !== 'undefined' ? globalThis.crypto?.subtle : undefined;
  if (!subtle) {
    throw new StockLaunchUnconfirmedError(
      'A secure intent digest could not be created in this browser. Use a secure browser context before launching.',
    );
  }

  return toHex(await subtle.digest('SHA-256', new TextEncoder().encode(canonical)));
};

type StockLaunchStatus = 'idle' | 'loading' | 'ready' | 'blocked';

export const useStockInvoiceLaunch = ({ enabled }: { enabled: boolean }) => {
  const [status, setStatus] = useState<StockLaunchStatus>('idle');
  const [identity, setIdentity] = useState<StockLaunchIdentity | null>(null);
  const [ownerOptions, setOwnerOptions] = useState<StockAccountOwnerOption[]>([]);
  const [ownerUserId, setOwnerUserIdState] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [rotationProblem, setRotationProblem] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [settledLaunch, setSettledLaunch] =
    useState<SettledStockLaunch | null>(readSettledStockLaunch);
  const settledLaunchRef = useRef<SettledStockLaunch | null>(settledLaunch);
  const authContextTokenRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus('idle');
      setProblems([]);
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setProblems([]);

    const storageProblem = confirmStockLaunchStorage();
    // Capture one credential context for identity and roster. The same token
    // is returned with the prepared launch and used for the POST.
    const authToken = getAuthToken();
    authContextTokenRef.current = authToken;

    Promise.allSettled([
      fetchStockLaunchIdentity(authToken),
      fetchStockAccountOwnerOptions(authToken),
    ]).then(([identityResult, optionsResult]) => {
      if (cancelled) return;

      const nextProblems: string[] = [];
      if (storageProblem) {
        nextProblems.push(storageProblem);
      }

      // A token change while scope is loading invalidates the whole result,
      // even if one of the responses happened to succeed with the old token.
      if (getAuthToken() !== authToken) {
        nextProblems.push(AUTH_CONTEXT_CHANGED_MESSAGE);
      }

      const nextIdentity =
        identityResult.status === 'fulfilled' ? identityResult.value : null;
      if (identityResult.status !== 'fulfilled') {
        nextProblems.push(
          identityResult.reason instanceof StockLaunchUnconfirmedError
            ? identityResult.reason.message
            : 'Your signed-in identity or scope could not be confirmed. Sign in again before launching.',
        );
      }

      const nextOptions =
        optionsResult.status === 'fulfilled' ? optionsResult.value : null;
      if (optionsResult.status !== 'fulfilled') {
        nextProblems.push(
          optionsResult.reason instanceof StockLaunchUnconfirmedError
            ? optionsResult.reason.message
            : 'Account owner options could not be confirmed. Retry before launching.',
        );
      }

      setIdentity(nextIdentity);
      if (nextOptions !== null) {
        setOwnerOptions(nextOptions);
        // Never invent an owner. Keep only a previous explicit selection that
        // is still present in the confirmed options.
        setOwnerUserIdState((previous) =>
          previous === null
          || nextOptions.some((option) => option.userId === previous)
            ? previous
            : null,
        );
      }
      setProblems(nextProblems);
      setStatus(nextProblems.length === 0 ? 'ready' : 'blocked');
    });

    return () => {
      cancelled = true;
    };
  }, [enabled, reloadToken]);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    const handleStorage = (event: StorageEvent) => {
      if (event.key && event.key !== 'auth_token') return;
      if (
        event.storageArea
        && event.storageArea !== window.localStorage
      ) {
        return;
      }
      if (getAuthToken() === authContextTokenRef.current) return;

      setProblems((previous) =>
        previous.includes(AUTH_CONTEXT_CHANGED_MESSAGE)
          ? previous
          : [...previous, AUTH_CONTEXT_CHANGED_MESSAGE],
      );
      setStatus('blocked');
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [enabled]);

  useEffect(() => {
    if (
      ownerUserId !== null
      && !ownerOptions.some((option) => option.userId === ownerUserId)
    ) {
      setOwnerUserIdState(null);
    }
  }, [ownerOptions, ownerUserId]);

  const setOwnerUserId = useCallback(
    (value: string | null) => {
      if (value === null) {
        setOwnerUserIdState(null);
        return;
      }
      if (ownerOptions.some((option) => option.userId === value)) {
        setOwnerUserIdState(value);
      }
    },
    [ownerOptions],
  );

  const retry = useCallback(() => {
    setRotationProblem(null);
    setReloadToken((value) => value + 1);
  }, []);

  const effectiveProblems = rotationProblem
    ? [...problems, rotationProblem]
    : problems;
  const effectiveStatus: StockLaunchStatus = rotationProblem ? 'blocked' : status;

  const prepareLaunch = useCallback(
    async (invoice: Record<string, unknown>): Promise<PreparedStockLaunch> => {
      if (effectiveStatus !== 'ready' || !identity) {
        throw new StockLaunchUnconfirmedError(
          effectiveProblems[0]
            ?? 'The stock invoice launch setup is not confirmed yet. Retry before launching.',
        );
      }

      if (getAuthToken() !== authContextTokenRef.current) {
        setProblems([AUTH_CONTEXT_CHANGED_MESSAGE]);
        setStatus('blocked');
        throw new StockLaunchUnconfirmedError(
          AUTH_CONTEXT_CHANGED_MESSAGE,
        );
      }

      if (
        ownerUserId !== null
        && !ownerOptions.some((option) => option.userId === ownerUserId)
      ) {
        const message =
          'Choose an account owner from the available options, or choose No account owner.';
        setProblems([message]);
        setStatus('blocked');
        throw new StockLaunchUnconfirmedError(message);
      }

      try {
        const storageProblem = confirmStockLaunchStorage();
        if (storageProblem) {
          throw new StockLaunchUnconfirmedError(storageProblem);
        }

        const storage = getStockSessionStorage();
        const invoiceNumber = normalizeStockInvoiceNumber(invoice) ?? '';
        const authToken = authContextTokenRef.current;
        const digest = await deriveStockInvoiceIntentDigest(
          identity,
          invoice,
          ownerUserId,
        );
        if (getAuthToken() !== authToken) {
          throw new StockLaunchUnconfirmedError(
            AUTH_CONTEXT_CHANGED_MESSAGE,
          );
        }
        const idempotencyKey = getStockInvoiceLaunchKey(storage, digest);

        return {
          digest,
          idempotencyKey,
          accountOwnerUserId: ownerUserId,
          invoiceNumber,
          authToken,
        };
      } catch (error) {
        const message =
          error instanceof StockLaunchUnconfirmedError
            ? error.message
            : 'A safe launch key could not be kept. Retry before launching.';
        setProblems([message]);
        setStatus('blocked');
        throw error instanceof StockLaunchUnconfirmedError
          ? error
          : new StockLaunchUnconfirmedError(message);
      }
    },
    [
      effectiveProblems,
      effectiveStatus,
      identity,
      ownerOptions,
      ownerUserId,
    ],
  );

  const assertCurrentLaunchContext = useCallback(
    (prepared: PreparedStockLaunch) => {
      const currentToken = getAuthToken();
      if (
        currentToken !== (prepared.authToken ?? null)
        || currentToken !== authContextTokenRef.current
      ) {
        setProblems([AUTH_CONTEXT_CHANGED_MESSAGE]);
        setStatus('blocked');
        throw new StockLaunchUnconfirmedError(
          AUTH_CONTEXT_CHANGED_MESSAGE,
        );
      }
    },
    [],
  );

  const noteReceipt = useCallback(
    (receipt: WorkflowLaunchReceipt, prepared: PreparedStockLaunch) => {
      // A settled receipt does NOT clear the key. Keep the exact key so a
      // reopen, duplicate submit, or ambiguous retry still represents the same
      // launch. Only the explicit Start a new launch action clears it.
      if (
        !receipt.confirmed
        || (receipt.kind !== 'terminal' && receipt.kind !== 'attached')
      ) {
        return;
      }

      const settled: SettledStockLaunch = {
        digest: prepared.digest,
        idempotencyKey: prepared.idempotencyKey,
        kind: receipt.kind,
        executionId: receipt.executionId,
      };
      // Update the ref synchronously so an explicit Start a new launch action
      // invoked immediately after this receipt still targets the right key.
      settledLaunchRef.current = settled;
      setSettledLaunch(settled);
      persistSettledStockLaunch(settled);
    },
    [],
  );

  const startNewLaunch = useCallback(() => {
    const settled = settledLaunchRef.current;
    if (!settled) return false;

    try {
      const storage = getStockSessionStorage();
      // Remove only the key this settled launch actually used. If the stored
      // key no longer matches, leave it untouched.
      clearStockInvoiceLaunchKey(
        storage,
        settled.digest,
        settled.idempotencyKey,
      );
      clearPersistedSettledStockLaunch();
      settledLaunchRef.current = null;
      setSettledLaunch(null);
      setRotationProblem(null);
      return true;
    } catch {
      setRotationProblem(
        'This launch finished, but the next launch key could not be rotated. Reload before starting another launch.',
      );
      return false;
    }
  }, []);

  return {
    status: effectiveStatus,
    identity,
    ownerOptions,
    ownerUserId,
    setOwnerUserId,
    problems: effectiveProblems,
    retry,
    prepareLaunch,
    noteReceipt,
    settledLaunch,
    startNewLaunch,
    assertCurrentLaunchContext,
  };
};

type StockLaunchController = ReturnType<typeof useStockInvoiceLaunch>;

interface StockInvoiceLaunchFieldsProps {
  controller: StockLaunchController;
  disabled?: boolean;
}

/**
 * Shared account-owner picker + visible setup correction for the stock invoice
 * workflow. The picker can only submit ids that came from the confirmed
 * account-owner-options response; "No account owner" is always available.
 */
export const StockInvoiceLaunchFields: React.FC<
  StockInvoiceLaunchFieldsProps
> = ({ controller, disabled = false }) => {
  const {
    status,
    ownerOptions,
    ownerUserId,
    setOwnerUserId,
    problems,
    retry,
    settledLaunch,
    startNewLaunch,
  } = controller;

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <label
          htmlFor="stock-account-owner"
          className="text-sm font-medium leading-none"
        >
          Account owner (optional)
        </label>
        <select
          id="stock-account-owner"
          data-testid="stock-account-owner"
          name="account_owner_user_id"
          aria-label="Account owner"
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          value={ownerUserId ?? ''}
          onChange={(event) => {
            const value = event.target.value;
            setOwnerUserId(value.length === 0 ? null : value);
          }}
          disabled={disabled || status !== 'ready'}
        >
          <option value="">No account owner</option>
          {ownerOptions.map((option) => (
            <option key={option.userId} value={option.userId}>
              {option.displayLabel}
            </option>
          ))}
        </select>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Choose an owner from the available workspace members, or leave this
          unset.
        </p>
      </div>

      {status === 'loading' && (
        <p className="text-xs text-gray-500 dark:text-gray-400" role="status">
          Confirming account owner options…
        </p>
      )}

      {settledLaunch && (
        <div
          data-testid="stock-settled-launch"
          className="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-900 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-100"
        >
          <p>
            This launch is settled
            {settledLaunch.executionId
              ? ` for execution ${settledLaunch.executionId}`
              : ''}
            . Its launch key is kept until you explicitly start another launch.
          </p>
          <button
            type="button"
            data-testid="stock-start-new-launch"
            onClick={startNewLaunch}
            className="mt-2 text-xs font-medium underline underline-offset-4"
          >
            Start a new launch
          </button>
        </div>
      )}

      {problems.length > 0 && (
        <div
          role="alert"
          data-testid="stock-launch-correction"
          className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200"
        >
          <p className="font-medium">Launch setup needs correction</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {problems.map((problem, index) => (
              <li key={`${problem}-${index}`}>{problem}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={retry}
            className="mt-2 text-xs font-medium underline underline-offset-4"
          >
            Retry setup
          </button>
        </div>
      )}
    </div>
  );
};

export default StockInvoiceLaunchFields;
