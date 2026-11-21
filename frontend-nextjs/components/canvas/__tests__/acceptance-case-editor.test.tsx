import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AcceptanceCaseEditor, { GRADE_PENDING_STORAGE_PREFIX } from "../AcceptanceCaseEditor";

const existing = {name: "prior", inputs: {rows: [1]}, expect_state: {total: 1}, initial_state: {keep: true}};
const status = (cases: unknown[], digest: string, source = "saved-code") => ({
  status: {acceptance: {cases, tests_sha256: digest}, logic: {source_sha256: source}},
});
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const principal = {tenantId: "t", workspaceId: "w", userId: "u"};
const keyFor = (userId: string) =>
  `${GRADE_PENDING_STORAGE_PREFIX}:tenant:t:workspace:w:user:${userId}:app:app`;
const report = {passed: 1, total: 1, results: [{name: "prior", passed: true}]};

function pendingRecord() {
  for (let i = 0; i < sessionStorage.length; i += 1) {
    const key = sessionStorage.key(i);
    if (key?.startsWith(GRADE_PENDING_STORAGE_PREFIX)) {
      return {key, value: JSON.parse(sessionStorage.getItem(key) ?? "null")};
    }
  }
  return null;
}

function draft() {
  for (const [label, value] of Object.entries({
    "New case name": "Zeros", "Input field": "values", "New case input": "[0,0]",
    "Expected state field": "total", "New case expected": "0",
  })) fireEvent.change(screen.getByLabelText(label), {target: {value}});
}

beforeEach(() => sessionStorage.clear());

test("preserves existing cases and pins saved tests and source", async () => {
  const rpc = jest.fn()
    .mockResolvedValueOnce(status([existing], "before"))
    .mockResolvedValueOnce({success: true, tests_sha256: "after"})
    .mockResolvedValueOnce(status([existing], "after"))
    .mockResolvedValueOnce({success: true, source_sha256: "saved-code", tests_sha256: "after", passed: 1, total: 2, results: [{name: "Zeros", passed: false}]});
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" />);
  await screen.findByText("prior");
  draft();
  fireEvent.click(screen.getByRole("button", {name: "Add case"}));
  await screen.findByText("Zeros");
  expect(rpc).toHaveBeenNthCalledWith(2, "mini_app_set_tests", {
    app_id: "app", expected_tests_sha256: "before",
    tests: [existing, {name: "Zeros", inputs: {values: [0,0]}, expect_state: {total: 0}}],
  });
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await screen.findByText("1/2 passed for saved logic.");
  expect(rpc).toHaveBeenNthCalledWith(4, "mini_app_run_tests", {
    app_id: "app", expected_tests_sha256: "after", expected_source_sha256: "saved-code",
  });
});

test("preserves unsaved case when the server reports a stale snapshot", async () => {
  const rpc = jest.fn()
    .mockResolvedValueOnce(status([existing], "before"))
    .mockRejectedValueOnce({actionResult: {error: "mini_app_acceptance_tests_changed"}})
    .mockResolvedValueOnce(status([{...existing, name: "newer"}], "new-digest"));
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" />);
  await screen.findByText("prior");
  draft();
  fireEvent.click(screen.getByRole("button", {name: "Add case"}));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert").textContent).toContain("Reload the snapshot");
  fireEvent.click(screen.getAllByRole("button", {name: "Reload snapshot"})[0]);
  await screen.findByText("newer");
  await waitFor(() => expect((screen.getByLabelText("New case name") as HTMLInputElement).value).toBe("Zeros"));
});

test("shows a plain successful summary for saved code while the editor shows an unsaved change", async () => {
  const rpc = jest.fn()
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockResolvedValueOnce({success: true, source_sha256: "saved-code", tests_sha256: "tests", passed: 1, total: 1, results: [{name: "prior", passed: true}]});
  const editor = (sourceRevision: string) => <AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision={sourceRevision} />;
  const {rerender} = render(editor("return 1"));
  await screen.findByText("prior");
  rerender(editor("return 999"));
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await screen.findByText("1/1 passed for saved logic.");
  expect(rpc).toHaveBeenNthCalledWith(3, "mini_app_run_tests", {
    app_id: "app", expected_tests_sha256: "tests", expected_source_sha256: "saved-code",
  });
});

test("shows source-change guidance without an incomplete grade", async () => {
  const rpc = jest.fn()
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockRejectedValueOnce({ actionResult: { error: "mini_app_logic_changed" } });
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" />);
  await screen.findByText("prior");
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await screen.findByText("Saved logic changed during grading. Reload the saved logic and run the tests again.");
  expect(screen.queryByText(/passed for saved logic/)).toBeNull();
});

test("withholds a report whose source differs from the requested revision", async () => {
  const rpc = jest.fn()
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockResolvedValueOnce(status([existing], "tests"))
    .mockResolvedValueOnce({success:true, source_sha256:"different", tests_sha256:"tests", passed:1, total:1});
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" />);
  await screen.findByText("prior");
  fireEvent.click(screen.getByRole("button", {name:"Run saved tests"}));
  await screen.findByRole("alert");
  expect(screen.queryByText(/passed for saved logic/)).toBeNull();
});

test("durable: pins the saved revision and starts a client-generated submission", async () => {
  const rpc = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "tests");
    if (action === "mini_app_start_grade") {
      return {
        run_id: "run-1", submission_id: args.submission_id, status: "completed",
        source_digest: args.expected_source_digest, tests_digest: args.expected_tests_digest, report,
      };
    }
    throw new Error(`unexpected action: ${action}`);
  });
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" principal={principal} />);
  await screen.findByText("prior");
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await screen.findByText("1/1 passed for saved logic.");
  const start = rpc.mock.calls.find(([action]) => action === "mini_app_start_grade");
  expect(start?.[1]).toMatchObject({
    app_id: "app", expected_tests_digest: "tests", expected_source_digest: "saved-code",
    submission_id: expect.stringMatching(uuid),
  });
  expect(rpc.mock.calls.some(([action]) => action === "mini_app_run_tests")).toBe(false);
});

test("durable: persists before dispatch and resumes the same submission after a lost acknowledgment and remount", async () => {
  let submission = "";
  let storedAtDispatch: any = null;
  const first = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "tests");
    if (action === "mini_app_start_grade") {
      submission = args.submission_id;
      storedAtDispatch = pendingRecord()?.value;
      throw Object.assign(new Error("network down"), {status: 503});
    }
    if (action === "mini_app_grade_status") {
      return {run_id: "run-1", submission_id: args.submission_id, status: "pending",
        source_digest: "saved-code", tests_digest: "tests"};
    }
    throw new Error(`unexpected action: ${action}`);
  });
  const view = render(<AcceptanceCaseEditor appId="app" rpc={first} sourceRevision="code" principal={principal} />);
  await screen.findByText("prior");
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await waitFor(() => expect(storedAtDispatch).not.toBeNull());

  expect(storedAtDispatch).toMatchObject({
    submission_id: submission, source_digest: "saved-code", tests_digest: "tests",
  });
  expect(storedAtDispatch).not.toHaveProperty("report");
  expect(storedAtDispatch).not.toHaveProperty("auth");
  view.unmount();

  const second = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "tests");
    if (action === "mini_app_grade_status") {
      expect(args).toEqual({app_id: "app", submission_id: submission});
      return {run_id: "run-1", submission_id: submission, status: "completed",
        source_digest: "saved-code", tests_digest: "tests", report};
    }
    throw new Error(`unexpected action: ${action}`);
  });
  render(<AcceptanceCaseEditor appId="app" rpc={second} sourceRevision="code" principal={principal} />);
  await screen.findByText("1/1 passed for saved logic.");
  expect(second.mock.calls.some(([action]) => action === "mini_app_start_grade")).toBe(false);
  expect(pendingRecord()).toBeNull();
});

test("durable: resubmits the identical UUID and pins after an exact status miss", async () => {
  let submission = "";
  const first = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "tests");
    if (action === "mini_app_start_grade") {
      submission = args.submission_id;
      throw Object.assign(new Error("network down"), {status: 503});
    }
    if (action === "mini_app_grade_status") {
      return {run_id: "run-1", submission_id: args.submission_id, status: "pending",
        source_digest: "saved-code", tests_digest: "tests"};
    }
    throw new Error(`unexpected action: ${action}`);
  });
  const view = render(<AcceptanceCaseEditor appId="app" rpc={first} sourceRevision="code" principal={principal} />);
  await screen.findByText("prior");
  fireEvent.click(screen.getByRole("button", {name: "Run saved tests"}));
  await waitFor(() => expect(pendingRecord()).not.toBeNull());
  view.unmount();

  let missed = false;
  const second = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "tests");
    if (action === "mini_app_grade_status") {
      if (!missed) {
        missed = true;
        expect(args).toEqual({app_id: "app", submission_id: submission});
        return null;
      }
      throw new Error("unexpected repeated status");
    }
    if (action === "mini_app_start_grade") {
      expect(args).toEqual({
        app_id: "app", submission_id: submission,
        expected_source_digest: "saved-code", expected_tests_digest: "tests",
      });
      return {run_id: "run-2", submission_id: submission, status: "completed",
        source_digest: "saved-code", tests_digest: "tests", report};
    }
    throw new Error(`unexpected action: ${action}`);
  });
  render(<AcceptanceCaseEditor appId="app" rpc={second} sourceRevision="code" principal={principal} />);
  await screen.findByText("1/1 passed for saved logic.");
  expect(second.mock.calls.filter(([action]) => action === "mini_app_start_grade")).toHaveLength(1);
  expect(pendingRecord()).toBeNull();
});

test("durable: shows a restored older pin as stale only, never as the current report", async () => {
  sessionStorage.setItem(keyFor("u"), JSON.stringify({
    submission_id: "pending-1", source_digest: "old-source", tests_digest: "old-tests",
  }));
  const rpc = jest.fn(async (action: string, args: Record<string, any>) => {
    if (action === "mini_app_status") return status([existing], "new-tests", "new-source");
    if (action === "mini_app_grade_status") {
      expect(args).toEqual({app_id: "app", submission_id: "pending-1"});
      return {run_id: "run-old", submission_id: "pending-1", status: "completed",
        source_digest: "old-source", tests_digest: "old-tests", report};
    }
    throw new Error(`unexpected action: ${action}`);
  });
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" principal={principal} />);
  await screen.findByText(/older saved revision/i);
  expect(screen.getByText(/stale/i)).toBeInTheDocument();
  expect(screen.queryByText(/passed for saved logic/)).toBeNull();
  expect(pendingRecord()).toBeNull();
});

test("durable: does not observe another owner's pending submission", async () => {
  sessionStorage.setItem(keyFor("someone-else"), JSON.stringify({
    submission_id: "their-pending", source_digest: "saved-code", tests_digest: "tests",
  }));
  const rpc = jest.fn(async (action: string) => {
    if (action === "mini_app_status") return status([existing], "tests");
    throw new Error(`unexpected action: ${action}`);
  });
  render(<AcceptanceCaseEditor appId="app" rpc={rpc} sourceRevision="code" principal={principal} />);
  await screen.findByText("prior");
  expect(rpc.mock.calls.some(([action]) => action === "mini_app_grade_status")).toBe(false);
  expect(pendingRecord()?.value.submission_id).toBe("their-pending");
});
