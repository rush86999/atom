import Head from "next/head";
import { useRouter } from "next/router";
import { AssignmentPanel } from "@/components/assignments/AssignmentPanel";

export default function AssignmentsPage() {
  const router = useRouter();
  const agentId = typeof router.query.agent === "string"
    ? router.query.agent
    : null;
  const runQuery = router.query.run;
  const invalidRunQuery =
    runQuery !== undefined &&
    (typeof runQuery !== "string" || runQuery.trim() === "");
  const runId =
    typeof runQuery === "string" && runQuery.trim() !== ""
      ? runQuery
      : null;
  return (
    <>
      <Head>
        <title>Assignments · ATOM</title>
      </Head>
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="mb-4 text-lg font-semibold">Durable assignments</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          This view reads the durable assignment projection. It does not infer
          progress from chat text and does not run restart recovery on load.
        </p>
        {!router.isReady ? null : invalidRunQuery ? (
          <p className="text-sm text-destructive" role="alert">
            This assignment link is invalid.
          </p>
        ) : (
          <AssignmentPanel agentId={agentId} runId={runId} />
        )}
      </main>
    </>
  );
}
