/**
 * Opaque, per-user/per-agent job reference cached for reload readback.
 *
 * The cached value is ONLY a locator. The backend re-checks the admitted
 * actor, workspace and job identity on every read, so a stale or cross-user
 * reference can never restore a question or result on its own.
 */

export type AgentJobRef = {
  agentId: string;
  jobId: string;
};

const jobKey = (userId: string, agentId: string) =>
  `atom.agent-job.ref.${userId}.${agentId}`;
const lastKey = (userId: string) => `atom.agent-job.last.${userId}`;

function parseRef(raw: string | null): AgentJobRef | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    if (typeof value.agentId !== "string" || !value.agentId) return null;
    if (typeof value.jobId !== "string" || !value.jobId) return null;
    return { agentId: value.agentId, jobId: value.jobId };
  } catch {
    return null;
  }
}

export function rememberAgentJob(
  userId: string,
  agentId: string,
  jobId: string,
): void {
  if (typeof window === "undefined" || !userId || !agentId || !jobId) return;
  const ref = { agentId, jobId };
  try {
    window.localStorage.setItem(jobKey(userId, agentId), JSON.stringify(ref));
    window.localStorage.setItem(lastKey(userId), JSON.stringify(ref));
  } catch {
    // Storage may be unavailable (private mode); the live panel still works.
  }
}

export function loadAgentJob(
  userId: string,
  agentId: string,
): AgentJobRef | null {
  if (typeof window === "undefined" || !userId || !agentId) return null;
  try {
    return parseRef(window.localStorage.getItem(jobKey(userId, agentId)));
  } catch {
    return null;
  }
}

export function loadLastAgentJob(userId: string): AgentJobRef | null {
  if (typeof window === "undefined" || !userId) return null;
  try {
    return parseRef(window.localStorage.getItem(lastKey(userId)));
  } catch {
    return null;
  }
}

export function forgetAgentJob(userId: string, agentId: string): void {
  if (typeof window === "undefined" || !userId || !agentId) return;
  try {
    window.localStorage.removeItem(jobKey(userId, agentId));
    const last = parseRef(window.localStorage.getItem(lastKey(userId)));
    if (!last || last.agentId === agentId) {
      window.localStorage.removeItem(lastKey(userId));
    }
  } catch {
    // Best effort: the server remains authoritative.
  }
}

export function forgetAgentJobIfCurrent(
  userId: string,
  agentId: string,
  jobId: string,
): void {
  if (typeof window === "undefined" || !userId || !agentId || !jobId) return;
  try {
    const current = parseRef(
      window.localStorage.getItem(jobKey(userId, agentId)));
    if (current?.jobId === jobId) {
      forgetAgentJob(userId, agentId);
    }
  } catch {
    // Best effort.
  }
}
