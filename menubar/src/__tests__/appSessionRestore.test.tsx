import { fireEvent, render, screen } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import App from "../App";

jest.mock("@tauri-apps/api/core", () => ({
  invoke: jest.fn(),
}));

jest.mock("../MenuBar", () => ({
  __esModule: true,
  default: ({
    token,
    user,
    onLogout,
  }: {
    token: string | null;
    user: { email: string } | null;
    onLogout: () => void;
  }) => (
    <div>
      <div data-testid="menu-bar">
        menu-bar:{token}:{user?.email}
      </div>
      <button onClick={onLogout}>Log out</button>
    </div>
  ),
}));

const mockInvoke = invoke as jest.Mock;

const USER = {
  id: "user-1",
  email: "user@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
};

describe("App native session restoration", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("enters the app with the session restored across relaunch", async () => {
    mockInvoke.mockResolvedValueOnce({ token: "restored-token", user: USER });

    render(<App />);

    const menuBar = await screen.findByTestId("menu-bar");
    expect(menuBar).toHaveTextContent("menu-bar:restored-token:user@example.com");
    expect(mockInvoke).toHaveBeenCalledWith("get_session");
    expect(screen.queryByLabelText("Email")).toBeNull();
  });

  test("stays on sign-in when native restore fails closed", async () => {
    mockInvoke.mockRejectedValueOnce("Not authenticated");

    render(<App />);

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByTestId("menu-bar")).toBeNull();
  });

  test("stays on sign-in when native restore returns no session", async () => {
    mockInvoke.mockResolvedValueOnce(null);

    render(<App />);

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByTestId("menu-bar")).toBeNull();
  });

  test("logout fails closed in the UI even when native cleanup rejects", async () => {
    mockInvoke.mockImplementation((command: string) => {
      if (command === "get_session") {
        return Promise.resolve({ token: "restored-token", user: USER });
      }
      if (command === "logout") {
        return Promise.reject("Failed to delete token");
      }
      return Promise.resolve(undefined);
    });

    render(<App />);

    await screen.findByTestId("menu-bar");
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByTestId("menu-bar")).toBeNull();
    expect(mockInvoke).toHaveBeenCalledWith("logout");
  });
});
