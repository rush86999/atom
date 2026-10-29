import Head from "next/head";
import { AssignmentPanel } from "@/components/assignments/AssignmentPanel";

export default function AssignmentsPage() {
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
        <AssignmentPanel />
      </main>
    </>
  );
}
