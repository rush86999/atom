import React from "react";
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
  const [sourceKind, setSourceKind] = useState(
    typeof router.query.source_kind === "string"
      ? router.query.source_kind : "email"
  );
  const [threads, setThreads] = useState<LearningThread[]>([]);
  const [error, setError] = useState<string | null>(null);

  const selectThread = (value: string) => {
    if (!value) {
      setThreadId("");
      setSourceKind("email");
      router.replace({ pathname: "/learning", query: {} }, undefined, {
        shallow: true,
      });
      return;
    }
    const parsed = JSON.parse(value) as [string, string];
    setSourceKind(parsed[0]);
    setThreadId(parsed[1]);
    router.replace({
      pathname: "/learning",
      query: { thread: parsed[1], source_kind: parsed[0] },
    }, undefined, { shallow: true });
  };

  // Deep links and browser back/forward are external navigation state; keep
  // the local selection in sync with the query (the select writes both).
  useEffect(() => {
    const queryThread = typeof router.query.thread === "string"
      ? router.query.thread : "";
    const queryKind = typeof router.query.source_kind === "string"
      ? router.query.source_kind : "email";
    if (queryThread && (queryThread !== threadId || queryKind !== sourceKind)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setThreadId(queryThread);
      setSourceKind(queryKind);
    }
  }, [router.query.thread, router.query.source_kind, threadId, sourceKind]);

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
            value={threads.some((item) =>
              item.thread_id === threadId &&
              (item.source_kind || "email") === sourceKind)
              ? JSON.stringify([sourceKind, threadId]) : ""}
            onChange={(event) => selectThread(event.target.value)}
          >
            <option value="">Select an email or chat conversation</option>
            {threads.map((item) => {
              const kind = item.source_kind || "email";
              return (
                <option key={`${kind}:${item.thread_id}`}
                        value={JSON.stringify([kind, item.thread_id])}>
                  {kind === "native_chat" ? "Chat" : "Email"} · {item.subject}
                  {" · "}{item.message_count} message(s)
                </option>
              );
            })}
          </select>
        </label>
        {threadId ? (
          <ConversationLearningReview threadId={threadId} sourceKind={sourceKind} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Select a persisted email thread to load its evidence.
          </p>
        )}
      </main>
    </>
  );
}
