import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { ConversationLearningReview } from "@/components/learning/ConversationLearningReview";
import {
  LearningThread,
  listLearningThreads,
} from "@/lib/conversation-learning-api";

export default function LearningPage() {
  const router = useRouter();
  const [threadId, setThreadId] = useState(
    typeof router.query.thread === "string" ? router.query.thread : ""
  );
  const [threads, setThreads] = useState<LearningThread[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listLearningThreads()
      .then((rows) => {
        if (!cancelled) setThreads(rows);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message
            || "Could not list local email threads");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <Head>
        <title>Conversation learning · ATOM</title>
      </Head>
      <main className="mx-auto max-w-4xl p-6">
        <h1 className="mb-2 text-lg font-semibold">Conversation learning</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          Review a lesson derived from a conversation against its resolved
          resources, method, exceptions and unresolved questions before it
          becomes standing guidance.
        </p>
        {error ? (
          <p className="mb-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
            {error}
          </p>
        ) : null}
        <label className="mb-3 block text-sm">
          Conversation thread
          <select
            className="mt-1 w-full rounded border p-2"
            data-testid="learning-thread-select"
            value={threads.some((item) => item.thread_id === threadId)
              ? threadId : ""}
            onChange={(event) => setThreadId(event.target.value)}
          >
            <option value="">Select a local email thread</option>
            {threads.map((item) => (
              <option key={item.thread_id} value={item.thread_id}>
                {item.subject} · {item.message_count} message(s)
              </option>
            ))}
          </select>
        </label>
        <label className="mb-3 block text-sm">
          Or enter a thread id
          <input
            className="mt-1 w-full rounded border p-2"
            data-testid="learning-thread-input"
            value={threadId}
            onChange={(event) => setThreadId(event.target.value)}
            placeholder="thread id"
          />
        </label>
        {threadId ? (
          <ConversationLearningReview threadId={threadId} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Select a persisted email thread to load its evidence.
          </p>
        )}
      </main>
    </>
  );
}
