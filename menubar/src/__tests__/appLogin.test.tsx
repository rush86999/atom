import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import App from "../App";

jest.mock("@tauri-apps/api/core", () => ({
  invoke: jest.fn(),
}));

jest.mock("../MenuBar", () => ({
  __esModule: true,
  default: () => <div>menu-bar-ready</div>,
}));

const mockInvoke = invoke as jest.Mock;

const USER = {
  id: "user-1",
  email: "user@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
};

describe("App sign-in bridge", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockInvoke.mockImplementation(
      (command: string, args?: Record<string, unknown>) => {
        if (command === "get_session") {
          return Promise.resolve(null);
        }
        if (command === "login") {
          if (args?.totpCode === "123456") {
            return Promise.resolve({
              token: "token-1",
              user: USER,
              device_id: "device-1",
            });
          }
          return Promise.reject("Two-factor authentication required");
        }
        return Promise.resolve(undefined);
      }
    );
  });

  test("sends a code only on the retry and enters the app on success", async () => {
    render(<App />);

    const email = await screen.findByLabelText("Email");
    fireEvent.change(email, { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    const code = await screen.findByLabelText("Authentication code");
    expect(mockInvoke).toHaveBeenCalledWith("login", {
      email: "user@example.com",
      password: "secret",
      deviceName: "MenuBar",
      totpCode: null,
    });

    fireEvent.change(code, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify Code" }));

    expect(await screen.findByText("menu-bar-ready")).toBeInTheDocument();
    expect(mockInvoke).toHaveBeenLastCalledWith("login", {
      email: "user@example.com",
      password: "secret",
      deviceName: "MenuBar",
      totpCode: "123456",
    });
  });

  test("keeps password-only sign-in on a single login call", async () => {
    mockInvoke.mockImplementation((command: string) => {
      if (command === "get_session") {
        return Promise.resolve(null);
      }
      if (command === "login") {
        return Promise.resolve({
          token: "token-2",
          user: USER,
          device_id: "device-2",
        });
      }
      return Promise.resolve(undefined);
    });

    render(<App />);

    const email = await screen.findByLabelText("Email");
    fireEvent.change(email, { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));

    expect(await screen.findByText("menu-bar-ready")).toBeInTheDocument();

    const loginCalls = mockInvoke.mock.calls.filter(
      ([command]) => command === "login"
    );
    expect(loginCalls).toHaveLength(1);
    expect(loginCalls[0][1]).toEqual({
      email: "user@example.com",
      password: "secret",
      deviceName: "MenuBar",
      totpCode: null,
    });
    await waitFor(() => {
      expect(screen.queryByLabelText("Authentication code")).toBeNull();
    });
  });
});
