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
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseUserRole = jest.fn();
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
}));

import Sidebar from "../Sidebar";

beforeEach(() => {
    mockUseUserRole.mockReturnValue({
        role: null,
        level: 0,
        isSupervisor: false,
        isAdmin: false,
        loading: false,
    });
});

describe("Sidebar role gating", () => {
    it("shows everything while the role is unknown (fail-open nav; backend enforces)", () => {
        mockUseUserRole.mockReturnValue({
            role: null, level: 0, isSupervisor: false, isAdmin: false, loading: true,
        });
        render(<Sidebar />);
        expect(screen.getByText("User Management")).toBeInTheDocument();
        expect(screen.getByText("Approvals")).toBeInTheDocument();
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
});
