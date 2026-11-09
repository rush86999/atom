/**
 * Pending-write owner resolution.
 *
 * Queued work stores only the owner identifiers captured from the canonical
 * local session/profile. A cached profile is an owner hint; it is never
 * execution authority. Before dispatch, the caller must be re-authorized
 * against the live server identity with the exact session generation that was
 * observed locally.
 */
import { apiService } from './api';
import type { ApiRequestConfig } from './api';
import {
  isAccessTokenSnapshotCurrent,
  readAuthSessionSnapshot,
} from '../storage/secureTokenStorage';
import type { AuthSessionSnapshot } from '../storage/secureTokenStorage';

export interface PendingWriteOwner {
  readonly userId: string;
  readonly workspaceId: string;
  readonly deviceId: string;
}

export interface PendingWriteOwnerSession {
  readonly owner: PendingWriteOwner;
  readonly session: AuthSessionSnapshot;
}

type UnknownRecord = { [key: string]: unknown };

function isUnknownRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function parseProfile(userData: string | null): UnknownRecord | null {
  if (userData === null) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(userData);
  } catch {
    return null;
  }

  return isUnknownRecord(parsed) ? parsed : null;
}

/**
 * Resolve the canonical owner for a pending write. This is a local read only:
 * it performs no transport and makes no permission decision.
 */
export async function readPendingWriteOwner(
  userId: string,
  deviceId: string,
): Promise<PendingWriteOwnerSession | null> {
  if (!isNonEmptyString(userId) || !isNonEmptyString(deviceId)) {
    return null;
  }

  const session = await readAuthSessionSnapshot();
  if (!isNonEmptyString(session.token)) {
    return null;
  }
  if (!isNonEmptyString(session.deviceId) || session.deviceId !== deviceId) {
    return null;
  }

  const profile = parseProfile(session.userData);
  if (!profile) {
    return null;
  }

  const profileUserId = profile.id;
  const profileWorkspaceId = profile.workspace_id;
  if (!isNonEmptyString(profileUserId) || !isNonEmptyString(profileWorkspaceId)) {
    return null;
  }
  if (profileUserId !== userId) {
    return null;
  }

  // The generation must still be the one observed after every await above.
  if (!isAccessTokenSnapshotCurrent(session)) {
    return null;
  }

  return {
    owner: {
      userId: profileUserId,
      workspaceId: profileWorkspaceId,
      deviceId: session.deviceId,
    },
    session,
  };
}

/**
 * Authorize a queued owner against the live server identity.
 *
 * The queued identifiers must match both the caller and the current canonical
 * local session, and the server must confirm the exact same user/workspace as
 * active. The captured session is returned only if its generation is still
 * current after the authorization round trip.
 */
export async function authorizePendingWriteOwner(
  owner: PendingWriteOwner,
  userId: string,
  deviceId: string,
): Promise<AuthSessionSnapshot | null> {
  if (!isNonEmptyString(owner.userId) ||
      !isNonEmptyString(owner.workspaceId) ||
      !isNonEmptyString(owner.deviceId)) {
    return null;
  }
  if (!isNonEmptyString(userId) || !isNonEmptyString(deviceId)) {
    return null;
  }
  if (owner.userId !== userId || owner.deviceId !== deviceId) {
    return null;
  }

  const current = await readPendingWriteOwner(userId, deviceId);
  if (!current) {
    return null;
  }
  if (current.owner.userId !== owner.userId ||
      current.owner.workspaceId !== owner.workspaceId ||
      current.owner.deviceId !== owner.deviceId) {
    return null;
  }

  const config: ApiRequestConfig = {
    expectedAccessTokenSnapshot: current.session,
  };

  let response: { success: boolean; data?: unknown } | null = null;
  try {
    response = await apiService.get<unknown>('/api/auth/me', config);
  } catch {
    return null;
  }

  if (!response || !response.success || !isUnknownRecord(response.data)) {
    return null;
  }

  const data = response.data;
  if (!isNonEmptyString(data.id) || !isNonEmptyString(data.workspace_id)) {
    return null;
  }
  if (data.id !== owner.userId || data.workspace_id !== owner.workspaceId) {
    return null;
  }
  if (data.status !== 'active') {
    return null;
  }

  if (!isAccessTokenSnapshotCurrent(current.session)) {
    return null;
  }

  return current.session;
}
