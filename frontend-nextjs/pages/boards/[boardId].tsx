'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/router';
import { useBoard } from '../../hooks/useBoard';
import { useBoardWebSocket } from '../../hooks/useBoardWebSocket';

const KanbanBoard = dynamic(
  () => import('../../components/boards/KanbanBoard').then((m) => m.KanbanBoard),
  { ssr: false, loading: () => <div className="p-8 text-gray-500">Loading board…</div> },
);

export default function BoardPage() {
  const router = useRouter();
  const boardId = router.query.boardId as string;
  const { data: board, isLoading } = useBoard(boardId || null);

  // Subscribe to WS events to keep the board in sync
  useBoardWebSocket(boardId || null);

  if (isLoading || !board) {
    return <div className="p-8 text-gray-500">Loading board…</div>;
  }

  return <KanbanBoard board={board} />;
}
