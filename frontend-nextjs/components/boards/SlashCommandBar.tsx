'use client';

import { useState } from 'react';
import { Terminal, Send } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '../../lib/api-client';

interface Props {
  boardId: string;
}

export function SlashCommandBar({ boardId }: Props) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const text = value.trim();
    if (!text) return;
    if (!text.startsWith('/task')) {
      toast.info('Type /task for board commands. Example: /task list');
      return;
    }
    setBusy(true);
    try {
      const res = await apiClient.fetch('/api/atom-agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          user_id: 'system', // will be overridden by backend
          context: { board_id: boardId },
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json().catch(() => ({}));
      const reply = data.response?.message || data.message || 'Done.';
      toast.success(reply);
      setValue('');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 rounded border bg-gray-50 px-2 py-1">
      <Terminal className="h-4 w-4 text-gray-500" />
      <input
        className="w-64 bg-transparent text-sm focus:outline-none"
        placeholder="/task create Buy milk in To Do"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            submit();
          }
        }}
        disabled={busy}
      />
      <button
        type="button"
        onClick={submit}
        disabled={busy}
        aria-label="Run command"
        className="rounded p-1 text-gray-600 hover:bg-gray-200 disabled:opacity-50"
      >
        <Send className="h-3 w-3" />
      </button>
    </div>
  );
}
