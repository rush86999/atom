import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import RevisionHistory from "../LogicRevisionHistory";

const row = (version: number) => ({
  version, created_at: "2026-11-20T12:00:00Z", created_by: "Owner", preview: "total = 18",
});

test("cancel leaves the history unchanged and confirmation restores once", async () => {
  const load = jest.fn().mockResolvedValue([row(1)]);
  const restore = jest.fn().mockResolvedValue(2);
  const refreshEditor = jest.fn().mockRejectedValue(new Error("offline"));
  render(<RevisionHistory {...{ load, restore, refreshEditor }} canRestore epoch={0} />);
  const action = await screen.findByRole("button", { name: "Restore version 1" });
  fireEvent.click(action);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(restore).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Restore version 1" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm restore" }));
  await screen.findByText(/restore is still confirmed/);
  expect(restore).toHaveBeenCalledTimes(1);
  expect(restore).toHaveBeenCalledWith(1);
  expect(load).toHaveBeenCalledTimes(2);
});

test("unsaved editor disables restore", async () => {
  const load = jest.fn().mockResolvedValue([row(1)]);
  render(<RevisionHistory load={load} restore={jest.fn()} refreshEditor={jest.fn()} canRestore={false} epoch={0} />);
  const action = await screen.findByRole("button", { name: "Restore version 1" });
  expect((action as HTMLButtonElement).disabled).toBe(true);
});
