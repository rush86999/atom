/**
 * Shared list-response decoding for sync services.
 *
 * The API transport reports HTTP success independently of the domain body.
 * A successful transport is therefore not evidence that a list was received:
 * the body must contain a real list and every row must decode before callers
 * mutate a cache or advance a sync checkpoint.
 */

import { ApiResponse } from '../types/common';

type ListFailure = { ok: false; error: string };
type ListSuccess<T> = { ok: true; items: T[] };
type ExtractedList = { ok: true; value: unknown[] } | ListFailure;
type SuccessCheck = { ok: true } | ListFailure;

export type ListDecodeResult<T> = ListSuccess<T> | ListFailure;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function decodeDate(value: unknown): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime());
  }

  if (typeof value === 'string') {
    const decoded = new Date(value);
    return Number.isNaN(decoded.getTime()) ? null : decoded;
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
export function decodeListResponse<T>(
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
  for (let index = 0; index < extracted.value.length; index += 1) {
    const decoded = decodeRow(extracted.value[index]);
    if (decoded === null) {
      return fail(`Malformed ${resourceKey} record at index ${index}`);
    }
    items.push(decoded);
  }

  return { ok: true, items };
}
