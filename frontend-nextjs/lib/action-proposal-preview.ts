import type { ActionProposal } from './maturity-api';

const MAX_STRING_LENGTH = 1_200;
const MAX_PAYLOAD_LENGTH = 6_000;
const MAX_DEPTH = 8;
const MAX_ARRAY_ITEMS = 30;
const MAX_OBJECT_KEYS = 40;
const REDACTED = '[REDACTED]';
const TRUNCATED = '[TRUNCATED]';
const SENSITIVE_KEY = /(password|passwd|secret|token|apikey|credential|authorization|privatekey|accesskey|refreshtoken)/i;
const SECRET_VALUE = /^(?:bearer\s+|sk[-_]?)[A-Za-z0-9._~+/=-]{12,}$/i;

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function boundedText(value: unknown, maxLength: number): string {
  let text: string;
  if (typeof value === 'string') {
    text = value;
  } else {
    try {
      text = JSON.stringify(value) ?? String(value);
    } catch {
      text = String(value);
    }
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}… ${TRUNCATED}` : text;
}

function redactValue(
  value: unknown,
  depth: number,
  seen: WeakSet<object>
): unknown {
  if (typeof value === 'string') {
    return SECRET_VALUE.test(value.trim()) ? REDACTED : boundedText(value, MAX_STRING_LENGTH);
  }
  if (
    value === null ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return value;
  }
  if (typeof value === 'bigint') {
    return String(value);
  }
  if (typeof value === 'function' || typeof value === 'symbol') {
    return String(value);
  }
  if (depth >= MAX_DEPTH) {
    return TRUNCATED;
  }
  if (typeof value !== 'object') {
    return String(value);
  }
  if (seen.has(value)) {
    return '[CIRCULAR]';
  }
  seen.add(value);

  if (Array.isArray(value)) {
    const bounded = value
      .slice(0, MAX_ARRAY_ITEMS)
      .map((item) => redactValue(item, depth + 1, seen));
    if (value.length > MAX_ARRAY_ITEMS) bounded.push(TRUNCATED);
    return bounded;
  }

  const entries = Object.entries(value as JsonRecord);
  const redacted: JsonRecord = Object.create(null);
  for (const [key, item] of entries.slice(0, MAX_OBJECT_KEYS)) {
    if (SENSITIVE_KEY.test(key.replace(/[^a-z0-9]/gi, ''))) {
      redacted[key] = REDACTED;
    } else {
      redacted[key] = redactValue(item, depth + 1, seen);
    }
  }
  if (entries.length > MAX_OBJECT_KEYS) {
    redacted.__truncated__ = TRUNCATED;
  }
  return redacted;
}

export function redactActionProposalValue(value: unknown): unknown {
  return redactValue(value, 0, new WeakSet<object>());
}

function findText(value: unknown, keys: string[]): string {
  if (!isRecord(value)) return '';
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === 'string' && candidate.trim()) {
      return boundedText(candidate, MAX_STRING_LENGTH);
    }
    if (isRecord(candidate) || Array.isArray(candidate)) {
      const nested = findText(candidate, keys);
      if (nested) return nested;
    }
  }
  return '';
}

export function buildActionProposalPreview(proposal: ActionProposal) {
  const rawAction = proposal.proposed_action ?? {};
  const safeAction = redactActionProposalValue(rawAction);
  const action = isRecord(safeAction) ? safeAction : {};
  const rawParameters = isRecord(rawAction)
    ? rawAction.parameters ?? rawAction.params
    : undefined;
  const rawSource = isRecord(rawAction)
    ? rawAction.source_content ?? rawAction.source
    : undefined;
  const prompt = findText(rawAction, ['prompt', 'instruction', 'message']);
  const parameters = rawParameters === undefined
    ? ''
    : boundedText(redactActionProposalValue(rawParameters), MAX_PAYLOAD_LENGTH);
  const sourceContent = rawSource === undefined
    ? ''
    : boundedText(redactActionProposalValue(rawSource), MAX_PAYLOAD_LENGTH);
  const payloadText = boundedText(safeAction, MAX_PAYLOAD_LENGTH);

  return {
    targetAgent: boundedText(
      proposal.agent_name || proposal.agent_id || 'Unknown agent',
      MAX_STRING_LENGTH
    ),
    targetAgentId: boundedText(proposal.agent_id, MAX_STRING_LENGTH),
    actionType: boundedText(
      typeof action.action_type === 'string'
        ? action.action_type
        : proposal.proposal_type || 'Unknown action',
      MAX_STRING_LENGTH
    ),
    prompt: prompt || 'No prompt supplied',
    parameters: parameters || 'No parameters supplied',
    sourceContent: sourceContent || 'No source content supplied',
    payloadText,
  };
}
