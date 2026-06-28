import { apiClient } from './api-client';

export interface Board {
  id: string;
  name: string;
  slug: string | null;
  description: string | null;
  owner_user_id: string | null;
  archived_at: string | null;
  version_id: number;
  created_at: string;
  updated_at: string;
}

export interface BoardColumn {
  id: string;
  board_id: string;
  name: string;
  position: number;
  wip_limit: number | null;
  version_id: number;
  task_count: number;
}

export interface BoardDetail extends Board {
  columns: BoardColumn[];
}

export interface CanvasSummary {
  canvas_id: string;
  name: string;
  status: string;
  artifact_count: number;
  presence_count: number;
}

export interface BoardTask {
  id: string;
  board_id: string;
  column_id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  assignee_user_id: string | null;
  assignee_agent_id: string | null;
  parent_task_id: string | null;
  root_task_id: string | null;
  sort_order: number;
  due_at: string | null;
  labels: string[];
  metadata_json: Record<string, unknown>;
  created_by_user_id: string | null;
  canvas_id: string | null;
  version_id: number;
  created_at: string;
  updated_at: string;
  canvas: CanvasSummary | null;
}

export interface TaskCreateInput {
  title: string;
  column_id: string;
  description?: string;
  status?: string;
  priority?: string;
  assignee_user_id?: string;
  assignee_agent_id?: string;
  parent_task_id?: string;
  due_at?: string;
  labels?: string[];
  metadata_json?: Record<string, unknown>;
  workspace?: boolean;
}

export interface TaskPatchInput {
  expected_version: number;
  column_id?: string;
  sort_order?: number;
  status?: string;
  title?: string;
  description?: string;
  priority?: string;
  assignee_user_id?: string;
  assignee_agent_id?: string;
  due_at?: string;
  labels?: string[];
  metadata_json?: Record<string, unknown>;
  workspace?: boolean;
}

export interface SubtaskProposal {
  title: string;
  description?: string | null;
  column_name: string;
  priority?: string;
  estimated_hours?: number | null;
}

export interface DecomposePreview {
  parent_task_id: string;
  rationale: string;
  subtasks: SubtaskProposal[];
  depth: number;
  max_depth: number;
}

export interface DecomposeCommitResult {
  parent_task_id: string;
  created_task_ids: string[];
  spawned_workspaces: boolean;
}

export async function listBoards(): Promise<Board[]> {
  const res = await apiClient.fetch('/api/boards');
  if (!res.ok) throw new Error(`listBoards failed: ${res.status}`);
  return res.json();
}

export async function getBoard(boardId: string): Promise<BoardDetail> {
  const res = await apiClient.fetch(`/api/boards/${boardId}`);
  if (!res.ok) throw new Error(`getBoard failed: ${res.status}`);
  return res.json();
}

export async function createBoard(input: { name: string; description?: string; seed_default_columns?: boolean }): Promise<Board> {
  const res = await apiClient.fetch('/api/boards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      seed_default_columns: true,
      ...input,
    }),
  });
  if (!res.ok) throw new Error(`createBoard failed: ${res.status}`);
  return res.json();
}

export async function listTasks(boardId: string, columnId?: string): Promise<BoardTask[]> {
  const url = new URL(`/api/boards/${boardId}/tasks`, window.location.origin);
  if (columnId) url.searchParams.set('column_id', columnId);
  const res = await apiClient.fetch(url.toString().replace(window.location.origin, ''));
  if (!res.ok) throw new Error(`listTasks failed: ${res.status}`);
  return res.json();
}

export async function createTask(boardId: string, input: TaskCreateInput): Promise<BoardTask> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`createTask failed: ${res.status}`);
  return res.json();
}

export interface PatchTaskResult {
  task: BoardTask;
  conflict: boolean;
}

export async function patchTask(
  boardId: string,
  taskId: string,
  input: TaskPatchInput,
): Promise<PatchTaskResult> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (res.status === 409) {
    return { task: await res.json().catch(() => ({} as BoardTask)), conflict: true };
  }
  if (!res.ok) throw new Error(`patchTask failed: ${res.status}`);
  return { task: await res.json(), conflict: false };
}

export async function deleteTask(boardId: string, taskId: string): Promise<void> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}`, {
    method: 'DELETE',
  });
  if (!res.ok && res.status !== 204) throw new Error(`deleteTask failed: ${res.status}`);
}

export async function proposeDecompose(
  boardId: string,
  taskId: string,
): Promise<DecomposePreview> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}/decompose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (res.status === 424) {
    throw new DecomposeNeedsKeyError();
  }
  if (!res.ok) throw new Error(`proposeDecompose failed: ${res.status}`);
  return res.json();
}

export async function commitDecompose(
  boardId: string,
  taskId: string,
  proposals: SubtaskProposal[],
  spawnWorkspaces: boolean = false,
): Promise<DecomposeCommitResult> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}/decompose/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposals, spawn_workspaces: spawnWorkspaces }),
  });
  if (!res.ok) throw new Error(`commitDecompose failed: ${res.status}`);
  return res.json();
}

export class DecomposeNeedsKeyError extends Error {
  constructor() {
    super('Task decomposition requires a tenant BYOK key. Add one in Settings → API Keys.');
    this.name = 'DecomposeNeedsKeyError';
  }
}

export interface BoardComment {
  id: string;
  task_id: string | null;
  conversation_id: string | null;
  content: string;
  author: {
    user_id: string | null;
    agent_id: string | null;
    display_name: string | null;
  };
  parent_message_id: string | null;
  created_at: string;
  replies: BoardComment[];
}

export async function listComments(boardId: string, taskId: string): Promise<BoardComment[]> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}/comments`);
  if (!res.ok) throw new Error(`listComments failed: ${res.status}`);
  return res.json();
}

export async function postComment(
  boardId: string,
  taskId: string,
  content: string,
  parent_message_id?: string,
): Promise<BoardComment> {
  const res = await apiClient.fetch(`/api/boards/${boardId}/tasks/${taskId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, parent_message_id }),
  });
  if (!res.ok) throw new Error(`postComment failed: ${res.status}`);
  return res.json();
}
