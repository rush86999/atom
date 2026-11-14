import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LoginScreen from "../LoginScreen";

function fillCredentials(email = "user@example.com", password = "secret") {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: password },
  });
}

async function submitCredentials() {
  fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
  return screen.findByLabelText("Authentication code");
}

describe("LoginScreen", () => {
  test("keeps password-only sign-in unchanged", async () => {
    const onLogin = jest.fn().mockResolvedValue(undefined);
    render(<LoginScreen onLogin={onLogin} />);

    expect(screen.queryByLabelText("Authentication code")).toBeNull();

    fillCredentials();
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenCalledWith("user@example.com", "secret");
    });
    expect(onLogin).toHaveBeenCalledTimes(1);
    expect(onLogin.mock.calls[0]).toHaveLength(2);
    expect(screen.queryByLabelText("Authentication code")).toBeNull();
  });

  test("prompts for an authenticator code after the password challenge", async () => {
    const onLogin = jest
      .fn()
      .mockRejectedValueOnce("Two-factor authentication required")
      .mockResolvedValueOnce(undefined);
    render(<LoginScreen onLogin={onLogin} />);

    fillCredentials();
    const codeInput = await submitCredentials();

    expect(screen.getByTestId("two-factor-prompt").textContent).toContain(
      "user@example.com"
    );
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(codeInput).toHaveFocus();
    expect(codeInput).toHaveAttribute("autocomplete", "one-time-code");
    expect(codeInput).toHaveAttribute("inputmode", "numeric");
    expect(
      screen.getByRole("button", { name: "Verify Code" })
    ).toBeDisabled();

    fireEvent.change(codeInput, { target: { value: "12a34 56" } });
    expect(codeInput).toHaveValue("123456");
    fireEvent.click(screen.getByRole("button", { name: "Verify Code" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenLastCalledWith(
        "user@example.com",
        "secret",
        "123456"
      );
    });
  });

  test("shows an invalid-code error, clears the field and allows a retry", async () => {
    const onLogin = jest
      .fn()
      .mockRejectedValueOnce("Two-factor authentication required")
      .mockRejectedValueOnce("Invalid two-factor code")
      .mockResolvedValueOnce(undefined);
    render(<LoginScreen onLogin={onLogin} />);

    fillCredentials("retry@example.com", "hunter2");
    const codeInput = await submitCredentials();

    fireEvent.change(codeInput, { target: { value: "111111" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify Code" }));

    const error = await screen.findByTestId("login-error");
    expect(error).toHaveTextContent("Invalid two-factor code");
    expect(screen.getByLabelText("Authentication code")).toHaveValue("");
    expect(screen.getByLabelText("Authentication code")).not.toBeDisabled();
    expect(screen.getByTestId("two-factor-prompt")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Authentication code"), {
      target: { value: "222222" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Verify Code" }));

    await waitFor(() => {
      expect(onLogin).toHaveBeenLastCalledWith(
        "retry@example.com",
        "hunter2",
        "222222"
      );
    });
    expect(onLogin).toHaveBeenCalledTimes(3);
    expect(screen.queryByTestId("login-error")).toBeNull();
  });

  test("keeps a non-2FA refusal on the password form", async () => {
    const onLogin = jest
      .fn()
      .mockRejectedValueOnce("Invalid email or password");
    render(<LoginScreen onLogin={onLogin} />);

    fillCredentials();
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByTestId("login-error")).toHaveTextContent(
      "Invalid email or password"
    );
    expect(screen.queryByLabelText("Authentication code")).toBeNull();
    expect(screen.getByLabelText("Email")).toHaveValue("user@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("secret");
  });

  test("returns to the password form with the credentials intact", async () => {
    const onLogin = jest
      .fn()
      .mockRejectedValueOnce("Two-factor authentication required");
    render(<LoginScreen onLogin={onLogin} />);

    fillCredentials();
    await submitCredentials();

    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));

    expect(screen.queryByLabelText("Authentication code")).toBeNull();
    expect(screen.queryByTestId("login-error")).toBeNull();
    expect(screen.getByLabelText("Email")).toHaveValue("user@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("secret");
  });

  test("surfaces a string rejection instead of a generic failure", async () => {
    const onLogin = jest
      .fn()
      .mockRejectedValueOnce("Failed to connect to server");
    render(<LoginScreen onLogin={onLogin} />);

    fillCredentials();
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByTestId("login-error")).toHaveTextContent(
      "Failed to connect to server"
    );
  });
});
