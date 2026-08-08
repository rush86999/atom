import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AccountSettings from "@/pages/settings/account";
import { useRouter } from "next/router";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/Settings/TwoFactorSettings", () => ({
  __esModule: true,
  default: () => (
    <div data-testid="two-factor-settings">
      <span>Two-Factor Authentication</span>
    </div>
  ),
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/settings/account",
    pathname: "/settings/account",
    query: {},
    asPath: "/settings/account",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockPush = jest.fn();
const mockToast = jest.fn();

const ACCOUNT_DATA = {
  user: {
    email: "rishi@example.com",
    name: "Rishi Parikh",
    email_verified: "2026-01-10T00:00:00Z",
    image: null,
    created_at: "2025-06-01T00:00:00Z",
  },
  accounts: [
    {
      id: "acct-google",
      provider: "google",
      provider_account_id: "g-123",
      created_at: "2025-06-01T00:00:00Z",
      expires_at: null,
    },
    {
      id: "acct-credentials",
      provider: "credentials",
      provider_account_id: "c-456",
      created_at: "2025-06-02T00:00:00Z",
      expires_at: null,
    },
  ],
};

const okResponse = (body: any) => ({ ok: true, status: 200, statusText: "OK", json: async () => body });
const errResponse = (status: number, body: any) => ({
  ok: false,
  status,
  statusText: status === 401 ? "Unauthorized" : status === 500 ? "Internal Server Error" : "Bad Request",
  json: async () => body,
  text: async () => JSON.stringify(body),
});

describe("AccountSettings", () => {
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let removeItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    removeItemSpy = jest.spyOn(Storage.prototype, "removeItem");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (useRouter as jest.Mock).mockReturnValue({
      route: "/settings/account",
      pathname: "/settings/account",
      query: {},
      asPath: "/settings/account",
      push: mockPush,
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/auth/accounts")) {
        return Promise.resolve(okResponse(ACCOUNT_DATA));
      }
      return Promise.resolve(okResponse({}));
    });
  });

  it("shows the loading spinner before the account data arrives", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<AccountSettings />);
    expect(document.querySelector(".animate-spin")).not.toBeNull();
    expect(screen.queryByText("Account Settings")).not.toBeInTheDocument();
  });

  it("renders the profile, linked accounts and provider labels from the API", async () => {
    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByText("Rishi Parikh")).toBeInTheDocument();
    });

    expect(screen.getByText("rishi@example.com")).toBeInTheDocument();
    expect(screen.getByText("Email Verified")).toBeInTheDocument();
    expect(screen.getByText("Google")).toBeInTheDocument();
    expect(screen.getByText("Email/Password")).toBeInTheDocument();
    // Two accounts: neither is the sole Primary
    expect(screen.getAllByText("Linked")).toHaveLength(2);
    expect(screen.queryByText("Primary")).not.toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/auth/accounts",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
  });

  it("shows the unverified state when email_verified is null", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(
        okResponse({
          ...ACCOUNT_DATA,
          user: { ...ACCOUNT_DATA.user, email_verified: null },
        })
      )
    );

    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByText("Email Not Verified")).toBeInTheDocument();
    });
  });

  it("redirects to /login when no auth token exists", async () => {
    getItemSpy.mockReturnValue(null);

    render(<AccountSettings />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("clears the token and redirects to login on a 401", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(errResponse(401, { detail: "Expired" }))
    );

    render(<AccountSettings />);

    await waitFor(() => {
      expect(removeItemSpy).toHaveBeenCalledWith("auth_token");
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("shows the error state with a retry button when the fetch fails", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(errResponse(500, { detail: "Database exploded" }))
    );

    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByText(/Error 500: Internal Server Error - Database exploded/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /↻ Retry/i })).toBeInTheDocument();
  });

  it("retries the account fetch after a failure", async () => {
    mockFetch
      .mockImplementationOnce((url: string) => Promise.resolve(errResponse(500, { detail: "boom" })))
      .mockImplementation((url: string) => Promise.resolve(okResponse(ACCOUNT_DATA)));

    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /↻ Retry/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /↻ Retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Rishi Parikh")).toBeInTheDocument();
    });
  });

  it("shows the empty linked-accounts message when no accounts exist", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({ ...ACCOUNT_DATA, accounts: [] }))
    );

    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByText(/no linked accounts found/i)).toBeInTheDocument();
    });
  });

  it("warns when there is a single account and hides the unlink button", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({ ...ACCOUNT_DATA, accounts: [ACCOUNT_DATA.accounts[1]] }))
    );

    render(<AccountSettings />);

    await waitFor(() => {
      expect(screen.getByText("Primary")).toBeInTheDocument();
      expect(screen.getByText(/only authentication method/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /unlink/i })).not.toBeInTheDocument();
  });

  it("rejects a password change when the passwords do not match", async () => {
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.change(document.getElementById("currentPassword")!, { target: { value: "old-pass-1" } });
    fireEvent.change(document.getElementById("newPassword")!, { target: { value: "new-pass-1" } });
    fireEvent.change(document.getElementById("confirmPassword")!, { target: { value: "new-pass-2" } });

    // Real UX: the submit button is disabled while the passwords differ...
    expect(screen.getByRole("button", { name: /update password/i })).toBeDisabled();
    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();

    // ...and even a direct form submission is rejected without a network call
    fireEvent.submit(document.querySelector("form")!);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ description: "New passwords do not match", variant: "error" })
      );
    });
    expect(mockFetch).not.toHaveBeenCalledWith(
      "/api/auth/change-password",
      expect.anything()
    );
  });

  it("rejects a password shorter than 8 characters", async () => {
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.change(document.getElementById("currentPassword")!, { target: { value: "old-pass-1" } });
    fireEvent.change(document.getElementById("newPassword")!, { target: { value: "short" } });
    fireEvent.change(document.getElementById("confirmPassword")!, { target: { value: "short" } });

    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ description: "Password must be at least 8 characters", variant: "error" })
      );
    });
  });

  it("updates the password successfully and clears the form", async () => {
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.change(document.getElementById("currentPassword")!, { target: { value: "old-pass-1" } });
    fireEvent.change(document.getElementById("newPassword")!, { target: { value: "new-pass-123" } });
    fireEvent.change(document.getElementById("confirmPassword")!, { target: { value: "new-pass-123" } });

    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Success", description: "Password updated successfully", variant: "success" })
      );
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/auth/change-password",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          current_password: "old-pass-1",
          new_password: "new-pass-123",
        }),
      })
    );
    expect((document.getElementById("currentPassword") as HTMLInputElement).value).toBe("");
  });

  it("surfaces the backend error detail when the password change is rejected", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/auth/change-password")) {
        return Promise.resolve(errResponse(400, { detail: "Current password is incorrect" }));
      }
      return Promise.resolve(okResponse(ACCOUNT_DATA));
    });

    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.change(document.getElementById("currentPassword")!, { target: { value: "wrong-old" } });
    fireEvent.change(document.getElementById("newPassword")!, { target: { value: "new-pass-123" } });
    fireEvent.change(document.getElementById("confirmPassword")!, { target: { value: "new-pass-123" } });

    fireEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ description: "Current password is incorrect", variant: "error" })
      );
    });
  });

  it("unlinks a linked account after confirmation and refreshes the list", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /unlink/i })[0]);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/auth/accounts",
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ accountId: "acct-google" }),
        })
      );
    });
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("unlink your google account"));
  });

  it("does not unlink when the user cancels the confirmation", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /unlink/i })[0]);

    await waitFor(() => {
      expect(mockFetch).not.toHaveBeenCalledWith(
        "/api/auth/accounts",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("shows an error alert when unlinking fails", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<AccountSettings />);
    await waitFor(() => expect(screen.getByText("Rishi Parikh")).toBeInTheDocument());

    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(errResponse(400, { error: "Cannot unlink primary account" }))
    );

    fireEvent.click(screen.getAllByRole("button", { name: /unlink/i })[0]);

    await waitFor(() => {
      expect(screen.getByText("Cannot unlink primary account")).toBeInTheDocument();
    });
  });
});
