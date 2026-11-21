import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AcceptanceCaseEditor from "../AcceptanceCaseEditor";

const existing = {name: "prior", inputs: {rows: [1]}, expect_state: {total: 1}, initial_state: {keep: true}};
const status = (cases: unknown[], digest: string) => ({
  status: {acceptance: {cases, tests_sha256: digest}, logic: {source_sha256: "saved-code"}},
});
function draft() {
  for (const [label, value] of Object.entries({
    "New case name": "Zeros", "Input field": "values", "New case input": "[0,0]",
    "Expected state field": "total", "New case expected": "0",
  })) fireEvent.change(screen.getByLabelText(label), {target: {value}});
}

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
