import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import SettingsModal from "../components/SettingsModal";
import { SERVER_URL_STORAGE_KEY } from "../config";

jest.mock("@tauri-apps/api/core", () => ({
  invoke: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("../components/IntegrationsPanel", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("../components/WorkflowsPanel", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("../components/AnalyticsPanel", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("../components/ApprovalsPanel", () => ({
  __esModule: true,
  default: () => null,
}));

const mockInvoke = invoke as jest.Mock;

describe("settings endpoint validation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  test("rejects credentials and does not persist the invalid server URL", async () => {
    const onClose = jest.fn();
    const onServerUrlChange = jest.fn();

    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        onLogout={jest.fn()}
        serverUrl="http://127.0.0.1:8123"
        onServerUrlChange={onServerUrlChange}
      />
    );

    const input = screen.getByDisplayValue("http://127.0.0.1:8123");
    fireEvent.change(input, {
      target: { value: "http://user:secret@127.0.0.1:8123" },
    });
    fireEvent.click(screen.getByText("Save Changes"));

    const error = await screen.findByTestId("server-url-error");
    expect(error.textContent).toContain("credentials");
    expect(error.textContent).not.toContain("secret");
    expect(error.textContent).not.toContain("127.0.0.1");

    expect(localStorage.getItem(SERVER_URL_STORAGE_KEY)).toBeNull();
    expect(onServerUrlChange).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(mockInvoke).not.toHaveBeenCalled();
  });

  test("rejects a non-http scheme before saving", async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={jest.fn()}
        onLogout={jest.fn()}
        serverUrl="http://127.0.0.1:8123"
      />
    );

    const input = screen.getByDisplayValue("http://127.0.0.1:8123");
    fireEvent.change(input, { target: { value: "ws://127.0.0.1:8123" } });
    fireEvent.click(screen.getByText("Save Changes"));

    const error = await screen.findByTestId("server-url-error");
    expect(error.textContent).toContain("http:// or https://");
    expect(localStorage.getItem(SERVER_URL_STORAGE_KEY)).toBeNull();
  });

  test("does not mount endpoint panels when the endpoint is unavailable", async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={jest.fn()}
        onLogout={jest.fn()}
        serverUrl="http://127.0.0.1:8123"
        endpointAvailable={false}
        endpointConfigError="Native backend endpoint configuration was rejected."
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("endpoint-config-error")).toBeTruthy();
    });
    expect(screen.queryByText("INTEGRATIONS")).toBeNull();
    expect(screen.queryByText("WORKFLOWS")).toBeNull();
    expect(screen.queryByText("ANALYTICS")).toBeNull();
    expect(screen.queryByText("APPROVALS")).toBeNull();
    expect(screen.getByDisplayValue("http://127.0.0.1:8123")).toBeDisabled();
  });
});
