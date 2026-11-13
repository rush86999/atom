/**
 * SkillPackageList — published package catalogue + verified deletion.
 *
 * The assertions mirror the backend's receipt contract: a row is only removed
 * for a confirmed receipt; not_applied retries reuse the same operation id;
 * partial/unknown outcomes keep the row and disable a blind repeat until an
 * explicit refresh reconciles it.
 */

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SkillPackageList } from "@/components/admin/skills/SkillPackageList";
import { listSkillPackages } from "@/lib/skill-packages";
import {
  SkillPackageDeleteError,
  deleteSkillPackage,
  newSkillPackageDeleteOperationId,
} from "@/lib/skill-package-delete";

jest.mock("@/lib/skill-packages", () => {
  const actual = jest.requireActual("@/lib/skill-packages");
  return { ...actual, listSkillPackages: jest.fn() };
});

jest.mock("@/lib/skill-package-delete", () => {
  const actual = jest.requireActual("@/lib/skill-package-delete");
  return {
    ...actual,
    deleteSkillPackage: jest.fn(),
    newSkillPackageDeleteOperationId: jest.fn(),
  };
});

const listMock = listSkillPackages as jest.Mock;
const deleteMock = deleteSkillPackage as jest.Mock;
const newIdMock = newSkillPackageDeleteOperationId as jest.Mock;

const packageRow = (
  name: string,
  overrides: Partial<{
    hasManifest: boolean;
    files: string[];
    modifiedAt: number;
  }> = {},
) => ({
  name,
  hasManifest: true,
  files: ["SKILL.md", "run.py"],
  modifiedAt: 1763000000,
  ...overrides,
});

const generatedId = "skill-package:delete:generated";

const deleteButton = (name: string) =>
  screen.getByTestId(`delete-skill-package-${name}`);

const confirmSpy = () => jest.spyOn(window, "confirm").mockReturnValue(true);

beforeEach(() => {
  listMock.mockReset();
  deleteMock.mockReset();
  newIdMock.mockReset();
  newIdMock.mockImplementation(() => generatedId);
  listMock.mockResolvedValue([
    packageRow("weekly-digest"),
    packageRow("monthly-report"),
  ]);
  window.sessionStorage.clear();
});

describe("SkillPackageList catalogue", () => {
  test("renders the tenant packages with manifest state and file counts", async () => {
    render(<SkillPackageList />);

    expect(await screen.findByText("weekly-digest")).toBeInTheDocument();
    expect(screen.getByText("monthly-report")).toBeInTheDocument();
    expect(screen.getAllByText("manifest")).toHaveLength(2);
    expect(screen.getAllByText(/2 files/)).toHaveLength(2);
    expect(listMock).toHaveBeenCalledTimes(1);
  });

  test("shows a truthful empty state only for a genuine empty catalogue", async () => {
    listMock.mockResolvedValue([]);
    render(<SkillPackageList />);

    expect(await screen.findByTestId("skill-packages-empty")).toHaveTextContent(
      /no packages published yet/i,
    );
    expect(screen.queryByTestId("skill-packages-error")).not.toBeInTheDocument();
  });

  test("an unverified list is an error with a retry, never an empty catalogue", async () => {
    const { SkillPackageListError } = jest.requireActual("@/lib/skill-packages");
    listMock
      .mockRejectedValueOnce(
        new SkillPackageListError({ outcome: "unverified", status: 200 }),
      )
      .mockResolvedValueOnce([packageRow("weekly-digest")]);

    render(<SkillPackageList />);

    const error = await screen.findByTestId("skill-packages-error");
    expect(error).toHaveTextContent(/could not be verified/i);
    expect(screen.queryByTestId("skill-packages-empty")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText("weekly-digest")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledTimes(2);
  });

  test("an explicit refresh reloads without fabricating a deletion notice", async () => {
    listMock.mockResolvedValueOnce([packageRow("weekly-digest")]);
    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");

    fireEvent.click(screen.getByTestId("refresh-skill-packages"));
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
    expect(
      screen.queryByTestId("skill-package-delete-notice"),
    ).not.toBeInTheDocument();
  });
});

describe("SkillPackageList verified deletion", () => {
  test("asks for confirmation and removes only the confirmed package", async () => {
    const confirm = confirmSpy();
    deleteMock.mockResolvedValue({
      outcome: "deleted",
      skillId: "weekly-digest",
      operationId: generatedId,
    });

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");

    fireEvent.click(deleteButton("weekly-digest"));

    expect(confirm).toHaveBeenCalledWith(
      expect.stringMatching(/delete skill package "weekly-digest"/i),
    );
    expect(deleteMock).toHaveBeenCalledTimes(1);
    expect(deleteMock).toHaveBeenCalledWith("weekly-digest", generatedId);

    await waitFor(() =>
      expect(screen.queryByText("weekly-digest")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("monthly-report")).toBeInTheDocument();
    expect(screen.getByTestId("skill-package-delete-notice")).toHaveTextContent(
      "Skill package deleted.",
    );
  });

  test("a cancelled confirmation dispatches nothing", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");

    fireEvent.click(deleteButton("weekly-digest"));

    expect(deleteMock).not.toHaveBeenCalled();
    expect(screen.getByText("weekly-digest")).toBeInTheDocument();
  });

  test("an already-applied receipt is not reported as a new deletion", async () => {
    confirmSpy();
    deleteMock.mockResolvedValue({
      outcome: "already_removed",
      skillId: "weekly-digest",
      operationId: generatedId,
    });

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));

    expect(
      await screen.findByTestId("skill-package-delete-notice"),
    ).toHaveTextContent("Skill package was already deleted.");
    expect(screen.queryByText("weekly-digest")).not.toBeInTheDocument();
  });

  test("a not_found refusal drops the stale row without claiming a deletion", async () => {
    confirmSpy();
    deleteMock.mockRejectedValue(
      new SkillPackageDeleteError({ outcome: "not_found", status: 404 }),
    );

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));

    await waitFor(() =>
      expect(screen.queryByText("weekly-digest")).not.toBeInTheDocument(),
    );
    const notice = screen.getByTestId("skill-package-delete-notice");
    expect(notice).toHaveTextContent(/not found/i);
    expect(notice).not.toHaveTextContent("Skill package deleted.");
  });
});

describe("SkillPackageList uncertain outcomes", () => {
  test("a partial receipt keeps the row, disables a repeat and shows the stable operation id", async () => {
    confirmSpy();
    deleteMock.mockRejectedValue(
      new SkillPackageDeleteError({
        outcome: "partial",
        status: 503,
        operationId: "skill-package:delete:partial",
      }),
    );

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));

    const notice = await screen.findByTestId("skill-package-delete-notice");
    expect(notice).toHaveTextContent(/partly verified/i);
    expect(notice).toHaveTextContent(/do not repeat/i);
    expect(screen.getByText("weekly-digest")).toBeInTheDocument();
    expect(deleteButton("weekly-digest")).toBeDisabled();
    expect(
      screen.getByTestId("skill-package-delete-operation-id"),
    ).toHaveTextContent("skill-package:delete:partial");
  });

  test("an unknown outcome keeps the row disabled until an explicit refresh", async () => {
    confirmSpy();
    deleteMock.mockRejectedValue(
      new SkillPackageDeleteError({ outcome: "unknown", status: 503 }),
    );

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));

    expect(
      await screen.findByTestId("skill-package-delete-notice"),
    ).toHaveTextContent(/outcome is unknown/i);
    expect(screen.getByText("weekly-digest")).toBeInTheDocument();
    expect(deleteButton("weekly-digest")).toBeDisabled();
    expect(
      screen.getByTestId("skill-package-delete-operation-id"),
    ).toHaveTextContent(generatedId);
  });

  test("after refresh, an uncertain deletion retries with the SAME operation id", async () => {
    confirmSpy();
    deleteMock
      .mockRejectedValueOnce(
        new SkillPackageDeleteError({
          outcome: "partial",
          status: 503,
          operationId: "skill-package:delete:partial",
        }),
      )
      .mockResolvedValueOnce({
        outcome: "already_removed",
        skillId: "weekly-digest",
        operationId: "skill-package:delete:partial",
      });

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));
    await screen.findByTestId("skill-package-delete-notice");
    expect(deleteButton("weekly-digest")).toBeDisabled();

    fireEvent.click(screen.getByTestId("refresh-skill-packages"));
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(deleteButton("weekly-digest")).not.toBeDisabled(),
    );

    fireEvent.click(deleteButton("weekly-digest"));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(deleteMock.mock.calls[0][1]).toBe(generatedId);
    expect(deleteMock.mock.calls[1][1]).toBe("skill-package:delete:partial");
    expect(screen.queryByText("weekly-digest")).not.toBeInTheDocument();
  });

  test("an uncertain operation id survives a page reload and is reused", async () => {
    confirmSpy();

    deleteMock.mockRejectedValueOnce(
      new SkillPackageDeleteError({
        outcome: "unknown",
        status: 503,
        operationId: generatedId,
      }),
    );

    const first = render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));
    await screen.findByTestId("skill-package-delete-notice");
    first.unmount();

    // A reload starts a fresh component; the id is restored from the page
    // session instead of a new operation being minted.
    deleteMock.mockResolvedValueOnce({
      outcome: "already_removed",
      skillId: "weekly-digest",
      operationId: generatedId,
    });
    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");
    fireEvent.click(deleteButton("weekly-digest"));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(deleteMock.mock.calls[1][1]).toBe(generatedId);
    expect(newIdMock).toHaveBeenCalledTimes(1);
  });

  test("a not_applied refusal stays retryable with the same operation id", async () => {
    confirmSpy();
    deleteMock
      .mockRejectedValueOnce(
        new SkillPackageDeleteError({
          outcome: "not_applied",
          status: 409,
          operationId: generatedId,
        }),
      )
      .mockResolvedValueOnce({
        outcome: "deleted",
        skillId: "weekly-digest",
        operationId: generatedId,
      });

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");

    fireEvent.click(deleteButton("weekly-digest"));
    expect(
      await screen.findByTestId("skill-package-delete-notice"),
    ).toHaveTextContent(/nothing changed/i);
    expect(deleteButton("weekly-digest")).not.toBeDisabled();

    fireEvent.click(deleteButton("weekly-digest"));
    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(deleteMock.mock.calls[1][1]).toBe(generatedId);
    expect(newIdMock).toHaveBeenCalledTimes(1);
  });

  test("a refused deletion starts a new operation id on the next attempt", async () => {
    confirmSpy();
    newIdMock
      .mockReturnValueOnce("skill-package:delete:first")
      .mockReturnValueOnce("skill-package:delete:second");
    deleteMock
      .mockRejectedValueOnce(
        new SkillPackageDeleteError({ outcome: "failed", status: 403 }),
      )
      .mockResolvedValueOnce({
        outcome: "deleted",
        skillId: "weekly-digest",
        operationId: "skill-package:delete:second",
      });

    render(<SkillPackageList />);
    await screen.findByText("weekly-digest");

    fireEvent.click(deleteButton("weekly-digest"));
    expect(
      await screen.findByTestId("skill-package-delete-notice"),
    ).toHaveTextContent(/could not be deleted/i);
    expect(
      screen.queryByTestId("skill-package-delete-operation-id"),
    ).not.toBeInTheDocument();

    fireEvent.click(deleteButton("weekly-digest"));
    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(deleteMock.mock.calls[0][1]).toBe("skill-package:delete:first");
    expect(deleteMock.mock.calls[1][1]).toBe("skill-package:delete:second");
  });

  test("a successful create signal refreshes the catalogue", async () => {
    const { rerender } = render(<SkillPackageList refreshSignal={0} />);
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1));

    rerender(<SkillPackageList refreshSignal={1} />);
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  });
});
