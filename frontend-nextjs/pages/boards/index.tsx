'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Plus, KanbanSquare } from 'lucide-react';
import { useBoards, useCreateBoard } from '../../hooks/useBoard';

export default function BoardsListPage() {
  const { data: boards, isLoading } = useBoards();
  const createBoard = useCreateBoard();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');

  const submit = async () => {
    if (!name.trim()) return;
    await createBoard.mutateAsync({ name: name.trim() });
    setName('');
    setShowCreate(false);
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <KanbanSquare className="h-6 w-6 text-blue-500" />
            Kanban Boards
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Multi-agent task coordination with live Canvas workspaces.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 rounded bg-blue-500 px-3 py-1.5 text-sm text-white hover:bg-blue-600"
        >
          <Plus className="h-4 w-4" />
          New Board
        </button>
      </div>

      {showCreate && (
        <div className="mt-4 rounded border bg-gray-50 p-4">
          <input
            className="w-full rounded border px-3 py-2 text-sm bg-white"
            placeholder="Board name (e.g. Sprint 14)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            autoFocus
          />
          <div className="mt-2 flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="rounded border px-3 py-1 text-sm bg-white hover:bg-gray-50">
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={!name.trim() || createBoard.isPending}
              className="rounded bg-blue-500 px-3 py-1 text-sm text-white hover:bg-blue-600 disabled:opacity-50"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="mt-8 text-gray-500">Loading…</p>
      ) : boards && boards.length > 0 ? (
        <ul className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {boards.map((b) => (
            <li key={b.id}>
              <Link
                href={`/boards/${b.id}`}
                className="block rounded-lg border bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
              >
                <h3 className="font-semibold text-gray-900">{b.name}</h3>
                {b.description && (
                  <p className="mt-1 text-sm text-gray-600 line-clamp-2">{b.description}</p>
                )}
                <p className="mt-2 text-xs text-gray-400">
                  Created {new Date(b.created_at).toLocaleDateString()}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-8 text-gray-500">
          No boards yet. Click “New Board” to create your first.
        </p>
      )}
    </div>
  );
}
