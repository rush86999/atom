/**
 * Tests for lib/user-role.ts — the frontend half of the 2026-09-08
 * role-journey pass (hierarchy + fresh role fetch).
 */
import { roleLevel, meetsRole, SUPERVISOR_MIN_LEVEL, ADMIN_MIN_LEVEL, fetchCurrentRole } from "../user-role";

describe("role hierarchy", () => {
    it("orders the 8 backend roles monotonically", () => {
        expect(roleLevel("guest")).toBeLessThan(roleLevel("viewer"));
        expect(roleLevel("viewer")).toBeLessThan(roleLevel("member"));
        expect(roleLevel("member")).toBeLessThan(roleLevel("team_lead"));
        expect(roleLevel("team_lead")).toBeLessThan(roleLevel("workspace_admin"));
        expect(roleLevel("workspace_admin")).toBeLessThan(roleLevel("admin"));
        expect(roleLevel("admin")).toBeLessThan(roleLevel("owner"));
        expect(roleLevel("owner")).toBeLessThan(roleLevel("super_admin"));
    });

    it("is case-insensitive and tolerant of junk", () => {
        expect(roleLevel("TEAM_LEAD")).toBe(roleLevel("team_lead"));
        expect(roleLevel(" Admin ")).toBe(roleLevel("admin"));
        expect(roleLevel("nonexistent")).toBe(0);
        expect(roleLevel(null)).toBe(0);
        expect(roleLevel(undefined)).toBe(0);
    });

    it("supervisor band starts at team_lead; admin band at workspace_admin", () => {
        expect(SUPERVISOR_MIN_LEVEL).toBe(roleLevel("team_lead"));
        expect(ADMIN_MIN_LEVEL).toBe(roleLevel("workspace_admin"));

        expect(meetsRole("team_lead", SUPERVISOR_MIN_LEVEL)).toBe(true);
        expect(meetsRole("member", SUPERVISOR_MIN_LEVEL)).toBe(false);
        // admin/owner must pass the supervisor band (the inversion this fixes)
        expect(meetsRole("admin", SUPERVISOR_MIN_LEVEL)).toBe(true);
        expect(meetsRole("owner", SUPERVISOR_MIN_LEVEL)).toBe(true);

        expect(meetsRole("workspace_admin", ADMIN_MIN_LEVEL)).toBe(true);
        expect(meetsRole("admin", ADMIN_MIN_LEVEL)).toBe(true);
        expect(meetsRole("owner", ADMIN_MIN_LEVEL)).toBe(true);
        expect(meetsRole("team_lead", ADMIN_MIN_LEVEL)).toBe(false);
    });
});

describe("fetchCurrentRole", () => {
    beforeEach(() => {
        window.localStorage.clear();
    });

    it("reads the role from /api/auth/me and caches it", async () => {
        window.localStorage.setItem("auth_token", "tok-1");
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ id: "u1", role: "team_lead" }),
        });
        jest.spyOn(window, "fetch").mockImplementation(fetchMock);

        const role = await fetchCurrentRole();

        expect(role).toBe("team_lead");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/api/auth/me"),
            expect.objectContaining({ headers: { Authorization: "Bearer tok-1" } })
        );
        expect(window.localStorage.getItem("atom_user_role")).toBe("team_lead");
        (window.fetch as jest.Mock).mockRestore();
    });

    it("returns null without a token and never calls the API", async () => {
        const fetchMock = jest.fn();
        jest.spyOn(window, "fetch").mockImplementation(fetchMock);
        const role = await fetchCurrentRole();
        expect(role).toBeNull();
        expect(fetchMock).not.toHaveBeenCalled();
        (window.fetch as jest.Mock).mockRestore();
    });

    it("returns null on non-200 (stale token) without caching", async () => {
        window.localStorage.setItem("auth_token", "expired");
        jest.spyOn(window, "fetch").mockResolvedValue({ ok: false } as Response);
        const role = await fetchCurrentRole();
        expect(role).toBeNull();
        expect(window.localStorage.getItem("atom_user_role")).toBeNull();
        (window.fetch as jest.Mock).mockRestore();
    });
});
