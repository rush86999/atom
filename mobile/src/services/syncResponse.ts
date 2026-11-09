/**
 * Shared list-response decoding for sync services.
 *
 * The API transport reports HTTP success independently of the domain body.
 * A successful transport is therefore not evidence that a list was received:
 * the body must contain a real list and every row must decode before callers
 * mutate a cache or advance a sync checkpoint.
 */

import type { ApiResponse } from '../types/common';
import { isValid, parseISO } from 'date-fns';

type ListFailure = { ok: false; error: string };
type ListSuccess<T> = { ok: true; items: T[] };
type DetailSuccess<T> = { ok: true; item: T };
type ExtractedList = { ok: true; value: unknown[] } | ListFailure;
type ExtractedDetail = { ok: true; value: unknown } | ListFailure;
type SuccessCheck = { ok: true } | ListFailure;

export type ListDecodeResult<T> = ListSuccess<T> | ListFailure;
export type DetailDecodeResult<T> = DetailSuccess<T> | ListFailure;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Serialize cache transactions so each read-modify-write critical section sees
 * the cache committed by the preceding transaction. A failed transaction is
 * reported to its caller but never blocks the next transaction.
 */
export function createCacheTransactionQueue(): <T>(task: () => Promise<T>) => Promise<T> {
  let tail: Promise<void> = Promise.resolve();

  return function run<T>(task: () => Promise<T>): Promise<T> {
    const result = tail.then(task);
    tail = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  };
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function decodeDate(value: unknown): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime());
  }

  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
    // Require an explicit instant; do not guess a local timezone or let Date
    // silently roll an impossible calendar date into a different month.
    const decoded = parseISO(value);
    return isValid(decoded) ? decoded : null;
  }

  return null;
}

function fail(error: string): ListFailure {
  return { ok: false, error };
}

function checkSuccessFlag(value: Record<string, unknown>, context: string): SuccessCheck {
  if (value.success === false) {
    return fail(`${context} reported success:false`);
  }
  if (value.success !== undefined && typeof value.success !== 'boolean') {
    return fail(`${context} has a non-boolean success flag`);
  }
  return { ok: true };
}

function extractList(
  body: Record<string, unknown>,
  resourceKey: string,
  depth: number
): ExtractedList {
  if (depth > 3) {
    return fail(`Response body nests too deeply before providing the ${resourceKey} list`);
  }

  const bodySuccess = checkSuccessFlag(body, 'Response body');
  if (!bodySuccess.ok) {
    return bodySuccess;
  }

  if (Object.prototype.hasOwnProperty.call(body, resourceKey) && Object.prototype.hasOwnProperty.call(body, 'data')) {
    return fail(`Response body ambiguously provides both ${resourceKey} and data`);
  }

  if (Object.prototype.hasOwnProperty.call(body, resourceKey)) {
    const list = body[resourceKey];
    if (!Array.isArray(list)) {
      return fail(`Response body ${resourceKey} is not an array`);
    }
    return { ok: true, value: list };
  }

  if (Object.prototype.hasOwnProperty.call(body, 'data')) {
    const data = body.data;
    if (Array.isArray(data)) {
      return { ok: true, value: data };
    }
    if (!isRecord(data)) {
      return fail(`Response body data is not a ${resourceKey} list`);
    }
    return extractList(data, resourceKey, depth + 1);
  }

  return fail(`Response body is missing the ${resourceKey} list`);
}

/**
 * Decode a complete list response before any cache mutation.
 *
 * Supports both the legacy resource-object envelope (`{ agents: [...] }`)
 * and the standard success/data envelope (`{ success: true, data: [...] }`,
 * including a resource object nested under `data`).
 */
export function decodeListResponse<T extends { id: string }>(
  response: ApiResponse<unknown>,
  resourceKey: string,
  decodeRow: (value: unknown) => T | null
): ListDecodeResult<T> {
  if (!response.success) {
    return fail(response.error || 'Transport request failed');
  }

  const body = response.data;
  let extracted: ExtractedList;

  if (Array.isArray(body)) {
    extracted = { ok: true, value: body };
  } else if (!isRecord(body)) {
    return fail(`Response body is missing the ${resourceKey} list`);
  } else {
    extracted = extractList(body, resourceKey, 0);
  }

  if (!extracted.ok) {
    return extracted;
  }

  const items: T[] = [];
  const identities = new Set<string>();
  for (let index = 0; index < extracted.value.length; index += 1) {
    const decoded = decodeRow(extracted.value[index]);
    if (decoded === null) {
      return fail(`Malformed ${resourceKey} record at index ${index}`);
    }
    if (identities.has(decoded.id)) {
      return fail(`Duplicate ${resourceKey} identity at index ${index}`);
    }
    identities.add(decoded.id);
    items.push(decoded);
  }

  return { ok: true, items };
}

function detailResourceAliases(resourceKey: string): string[] {
  const aliases = [resourceKey];
  if (resourceKey === 'canvas') {
    aliases.push('canvases');
  } else if (resourceKey === 'canvases') {
    aliases.push('canvas');
  } else if (resourceKey.endsWith('s')) {
    aliases.push(resourceKey.slice(0, -1));
  } else {
    aliases.push(`${resourceKey}s`);
  }
  return aliases;
}

function extractDetail(
  body: Record<string, unknown>,
  resourceKey: string,
  depth: number
): ExtractedDetail {
  if (depth > 3) {
    return fail(`Response body nests too deeply before providing the ${resourceKey} record`);
  }

  const bodySuccess = checkSuccessFlag(body, 'Response body');
  if (!bodySuccess.ok) {
    return bodySuccess;
  }

  const aliases = detailResourceAliases(resourceKey);
  const presentResources = aliases.filter((key) =>
    Object.prototype.hasOwnProperty.call(body, key)
  );
  const hasId = Object.prototype.hasOwnProperty.call(body, 'id');
  const hasData = Object.prototype.hasOwnProperty.call(body, 'data');

  // A direct record is identified by its own id. A canvas legitimately carries
  // a `data` field, so id presence takes precedence over envelope fields.
  if (hasId) {
    if (presentResources.length > 0) {
      return fail(`Response body ambiguously provides both a direct ${resourceKey} record and ${resourceKey}`);
    }
    return { ok: true, value: body };
  }

  if (presentResources.length > 1) {
    return fail(`Response body ambiguously provides multiple ${resourceKey} branches`);
  }

  if (presentResources.length === 1 && hasData) {
    return fail(`Response body ambiguously provides both ${resourceKey} and data`);
  }

  if (presentResources.length === 1) {
    const resource = body[presentResources[0]];
    if (isRecord(resource)) {
      return extractDetail(resource, resourceKey, depth + 1);
    }
    return { ok: true, value: resource };
  }

  if (hasData) {
    const data = body.data;
    if (!isRecord(data)) {
      return fail(`Response body data is not a ${resourceKey} record`);
    }
    return extractDetail(data, resourceKey, depth + 1);
  }

  return fail(`Response body is missing the ${resourceKey} record`);
}

/**
 * Decode a complete detail response before any cache mutation.
 *
 * Supports a direct record body, the legacy resource-object envelope
 * (`{ agent: {...} }`), and the standard success/data envelope
 * (`{ success: true, data: {...} }`, including nested wrappers). The decoded
 * identity must exactly match the requested opaque id.
 */
export function decodeDetailResponse<T extends { id: string }>(
  response: ApiResponse<unknown>,
  resourceKey: string,
  expectedId: string,
  decodeItem: (value: unknown) => T | null
): DetailDecodeResult<T> {
  if (typeof response.success !== 'boolean' || !response.success) {
    return fail(response.error || 'Transport request failed');
  }

  const body = response.data;
  if (!isRecord(body)) {
    return fail(`Response body is missing the ${resourceKey} record`);
  }

  const extracted = extractDetail(body, resourceKey, 0);
  if (!extracted.ok) {
    return extracted;
  }

  const item = decodeItem(extracted.value);
  if (item === null) {
    return fail(`Malformed ${resourceKey} record`);
  }
  if (item.id !== expectedId) {
    return fail(`Response ${resourceKey} identity does not match the requested id`);
  }

  return { ok: true, item };
}
