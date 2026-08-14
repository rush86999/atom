/**
 * VersionHistoryPage tests (pages/automations/versions.tsx, was 0% coverage)
 *
 * Covers: forwarding flowId from the router query to FlowVersioning and
 * the restore / view / compare handlers (toast + router push).
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import VersionHistoryPage from "@/pages/automations/versions";

const mockPush = jest.fn();
const mockToast = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: (...args: any[]) => mockPush(...args),
    query: { flowId: "flow-9" },
  }),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: (...args: any[]) => mockToast(...args) }),
}));

let latestVersioningProps: any = null;
jest.mock("@/components/Automations/FlowVersioning", () => ({
  __esModule: true,
  default: (props: any) => {
    latestVersioningProps = props;
    return <div data-testid="flow-versioning">Versions</div>;
  },
}));

describe("VersionHistoryPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    latestVersioningProps = null;
  });

  test("renders FlowVersioning with the flowId query param", () => {
    render(<VersionHistoryPage />);
    expect(screen.getByTestId("flow-versioning")).toBeInTheDocument();
    expect(latestVersioningProps.flowId).toBe("flow-9");
    expect(latestVersioningProps.className).toBe("h-full");
  });

  test("restoring a version shows a toast", () => {
    render(<VersionHistoryPage />);
    act(() => {
      latestVersioningProps.onRestoreVersion({ version: 3 });
    });
    expect(mockToast).toHaveBeenCalledWith({
      title: "Version Restored",
      description: "Restored to version 3. A new version has been created.",
    });
  });

  test("viewing a version navigates to the read-only builder", () => {
    render(<VersionHistoryPage />);
    act(() => {
      latestVersioningProps.onViewVersion({ id: "v42" });
    });
    expect(mockPush).toHaveBeenCalledWith("/automations/builder?version=v42&readonly=true");
  });

  test("comparing versions shows a toast", () => {
    render(<VersionHistoryPage />);
    act(() => {
      latestVersioningProps.onCompareVersions({ version: 1 }, { version: 2 });
    });
    expect(mockToast).toHaveBeenCalledWith({
      title: "Compare Mode",
      description: "Comparing v1 with v2",
    });
  });
});
