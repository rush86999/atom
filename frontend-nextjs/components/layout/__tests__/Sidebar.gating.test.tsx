/**
 * Sidebar role-gating tests (2026-09-08 role-journey pass).
 *
 * Locks the nav contract per role:
 * - members/viewers must NOT see admin-band links (they 403 on arrival)
 * - team_lead sees Approvals but not the admin band
 * - workspace_admin+ sees the admin band AND the previously-unreachable
 *   /admin/settings link
 */
import React from "react";
import { screen } from "@testing-library/react";
import { renderWithProviders as render } from "../../../tests/test-utils";
import "@testing-library/jest-dom";

// Role-only assertions use the explicit full profile; production defaults core.
const mockCapabilityEnabled = jest.fn();
jest.mock("../../../lib/product-profile", () => ({
    useProductProfile: () => ({ isCapabilityEnabled: mockCapabilityEnabled }),
}));
const mockUseUserRole = jest.fn();
const mockUseActionProposals = jest.fn();
jest.mock("../../../hooks/useActionProposals", () => ({
    useActionProposals: (...args: any[]) => mockUseActionProposals(...args),
}));
jest.mock("../../../lib/user-role", () => ({
    useUserRole: () => mockUseUserRole(),
    ADMIN_MIN_LEVEL: 5,
    SUPERVISOR_MIN_LEVEL: 4,
}));

jest.mock("next/router", () => ({
    useRouter: () => ({
        pathname: "/",
        push: jest.fn(),
        replace: jest.fn(),
        prefetch: jest.fn(),
    }),
}));

jest.mock("next-auth/react", () => ({
    useSession: () => ({ data: null, status: "unauthenticated" }),
    signOut: jest.fn(),
    SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import Sidebar from "../Sidebar";

beforeEach(() => {
    mockCapabilityEnabled.mockReturnValue(true);
    mockUseActionProposals.mockReturnValue({
        pendingCount: null,
        isPending: true,
        isError: false,
    });
    mockUseUserRole.mockReturnValue({
        role: null,
        level: 0,
        isSupervisor: false,
        isAdmin: false,
        loading: false,
    });
    global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
    } as any) as any;
});

describe("Sidebar role gating", () => {
    it("shows everything while the role is unknown (fail-open nav; backend enforces)", () => {
        mockUseUserRole.mockReturnValue({
            role: null, level: 0, isSupervisor: false, isAdmin: false, loading: true,
        });
        render(<Sidebar />);
        // Historical case identity retained; current loading policy is closed.
        expect(screen.queryByText("User Management")).not.toBeInTheDocument();
        expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });

    it("member: hides Approvals and the admin band, keeps member surfaces", () => {
        mockUseUserRole.mockReturnValue({
            role: "member", level: 3, isSupervisor: false, isAdmin: false, loading: false,
        });
        render(<Sidebar />);
        expect(screen.getByText("Dashboard")).toBeInTheDocument();
        expect(screen.getByText("Agents")).toBeInTheDocument();
        expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
        expect(screen.queryByText("User Management")).not.toBeInTheDocument();
        expect(screen.queryByText("JIT Verification")).not.toBeInTheDocument();
        expect(screen.queryByText("Dev Studio")).not.toBeInTheDocument();
        expect(screen.queryByText("Admin Settings")).not.toBeInTheDocument();
        // GOVERNANCE keeps its one ungated entry (Self-Healing Harness)
        expect(screen.getByText("GOVERNANCE")).toBeInTheDocument();
        expect(screen.getByText("Self-Healing Harness")).toBeInTheDocument();
    });

    it("team_lead: sees Approvals, still no admin band", () => {
        mockUseUserRole.mockReturnValue({
            role: "team_lead", level: 4, isSupervisor: true, isAdmin: false, loading: false,
        });
        render(<Sidebar />);
        expect(screen.getByText("Approvals")).toBeInTheDocument();
        expect(screen.queryByText("User Management")).not.toBeInTheDocument();
        expect(screen.getByText("Self-Healing Harness")).toBeInTheDocument();
    });

    it("shows the pending count and an accessible live status", async () => {
        mockUseUserRole.mockReturnValue({
            role: "team_lead", level: 4, isSupervisor: true, isAdmin: false, loading: false,
        });
        mockUseActionProposals.mockReturnValue({
            pendingCount: 2,
            isPending: false,
            isError: false,
        });
        const originalFetch = global.fetch;
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => [{ id: "hitl-1" }],
        } as any);
        render(<Sidebar />);

        expect(await screen.findByTestId("approvals-pending-badge")).toHaveTextContent("3");
        expect(screen.getByRole("status")).toHaveTextContent("3 pending reviews");
        global.fetch = originalFetch;
    });

    it("workspace_admin: sees the admin band plus the new Admin Settings link", () => {
        mockUseUserRole.mockReturnValue({
            role: "workspace_admin", level: 5, isSupervisor: true, isAdmin: true, loading: false,
        });
        render(<Sidebar />);
        expect(screen.getByText("User Management")).toBeInTheDocument();
        expect(screen.getByText("Business Facts")).toBeInTheDocument();
        const settingsLink = screen.getByText("Admin Settings").closest("a");
        expect(settingsLink).toHaveAttribute("href", "/admin/settings");
        expect(screen.getByText("GOVERNANCE")).toBeInTheDocument();
    });

    it("super_admin sees everything", () => {
        mockUseUserRole.mockReturnValue({
            role: "super_admin", level: 8, isSupervisor: true, isAdmin: true, loading: false,
        });
        render(<Sidebar />);
        expect(screen.getByText("User Management")).toBeInTheDocument();
        expect(screen.getByText("Dev Studio")).toBeInTheDocument();
        expect(screen.getByText("Admin Settings")).toBeInTheDocument();
    });

    // 2026-09-09 batch 4: /goal-runs was orphaned (canvas badges + the
    // notification bell only). Reads are any-signed-in on the backend, so
    // every role gets the nav item; the page gates its own actions.
    it("every role sees Goal Runs (reads are any-signed-in; actions gate in-page)", () => {
        for (const role of ["member", "team_lead", "workspace_admin"]) {
            mockUseUserRole.mockReturnValue({
                role, level: role === "member" ? 3 : role === "team_lead" ? 4 : 5,
                isSupervisor: role !== "member", isAdmin: role === "workspace_admin",
                loading: false,
            });
            const { unmount } = render(<Sidebar />);
            const link = screen.getByText("Activity").closest("a");
            expect(link).toHaveAttribute("href", "/goal-runs");
            unmount();
        }
    });
    it("core profile keeps deferred navigation hidden even for an administrator", () => {
        const enabled = new Set(["chat", "documents", "canvas", "agents", "learning", "activity", "settings", "approvals"]);
        mockCapabilityEnabled.mockImplementation((capability: string) => enabled.has(capability));
        mockUseUserRole.mockReturnValue({ role: "super_admin", level: 8, isSupervisor: true, isAdmin: true, loading: false });
        render(<Sidebar />);
        expect(screen.getByText("Activity").closest("a")).toHaveAttribute("href", "/goal-runs");
        expect(screen.getByText("Approvals")).toBeInTheDocument();
        expect(screen.queryByText("User Management")).not.toBeInTheDocument();
        expect(screen.queryByText("Dev Studio")).not.toBeInTheDocument();
        expect(screen.queryByText("Search")).not.toBeInTheDocument();
        expect(screen.queryByText("Marketplace")).not.toBeInTheDocument();
    });
});
