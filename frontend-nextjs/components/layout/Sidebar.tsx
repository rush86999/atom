import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useSession, signOut } from "next-auth/react";
import {
    Search,
    MessageSquare,
    CheckSquare,
    Play,
    Calendar,
    Terminal,
    Settings,
    ChevronLeft,
    ChevronRight,
    Home,
    Target,
    CreditCard,
    Layers,
    Layout,
    Mic,
    Zap,
    Heart,
    Bot,
    Store,
    BarChart3,
    User,
    LogOut,
    FileText,
    Shield,
    CheckCircle,
    KanbanSquare,
    Brain,
    Wrench,
    GraduationCap,
    Rocket,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { getAuthToken } from "../../lib/identity";
import { useActionProposals } from "../../hooks/useActionProposals";
import {
    useUserRole,
    ADMIN_MIN_LEVEL,
    SUPERVISOR_MIN_LEVEL,
} from "../../lib/user-role";
import { useProductProfile } from "../../lib/product-profile";

interface SidebarProps {
    className?: string;
}

interface SidebarItem {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    path: string;
    /** capability required by the active product profile. Deferred surfaces
     * stay in this file (code and data are kept) but are not rendered in the
     * core release; direct links get the explicit NotInRelease page. */
    capability?: string;
    /** minimum role level; items are hidden once the viewer's role is known
     * to be below it (backend still enforces every gate — this only stops
     * roles from clicking into guaranteed 403s). */
    minLevel?: number;
}

const getProfileEmail = () =>
    typeof window === "undefined" ? "" : window.localStorage.getItem("user_email") || "";

const subscribeToProfile = (onStoreChange: () => void) => {
    if (typeof window === "undefined") return () => {};
    window.addEventListener("storage", onStoreChange);
    return () => window.removeEventListener("storage", onStoreChange);
};

const getServerProfileEmail = () => "";

/** Pending-count pill for the Approvals nav item: HITL actions + INTERN
 * action proposals (data triggers held for review). Discovery gap fix — the
 * queue previously surfaced only if you already knew to open the page.
 * Fetches only when the viewer passes the supervisor gate (both queues are
 * TEAM_LEAD+); any failure → hidden, never noisy. */
function ApprovalsPendingBadge({ active, collapsed }: { active: boolean; collapsed: boolean }): React.ReactElement | null {
    const [hitlCount, setHitlCount] = useState<number | null>(null);
    const proposalQuery = useActionProposals({
        statusFilter: "pending_approval",
        limit: 50,
        enabled: active,
    });
    const proposalCount = proposalQuery.pendingCount;

    React.useEffect(() => {
        if (!active) {
            setHitlCount(null);
            return;
        }
        const controller = new AbortController();
        let cancelled = false;
        const API = process.env.NEXT_PUBLIC_API_URL || "";
        const load = async () => {
            try {
                const res = await fetch(`${API}/api/agents/approvals/pending`, {
                    headers: { Authorization: `Bearer ${getAuthToken() || ""}` },
                    signal: controller.signal,
                });
                if (!res.ok) {
                    if (!cancelled) setHitlCount(null);
                    return;
                }
                const data = await res.json();
                if (!cancelled && Array.isArray(data)) setHitlCount(data.length);
            } catch (err: any) {
                if (err?.name !== "AbortError" && !cancelled) setHitlCount(null);
            }
        };
        void load();
        const t = setInterval(load, 60000);
        return () => {
            cancelled = true;
            controller.abort();
            clearInterval(t);
        };
    }, [active]);

    if (
        !active ||
        hitlCount === null ||
        proposalCount === null ||
        proposalQuery.isPending ||
        proposalQuery.isError
    ) return null;
    const count = hitlCount + proposalCount;
    if (count <= 0) return null;
    const liveStatus = `${count} pending review${count === 1 ? "" : "s"}`;

    if (collapsed) {
        return (
            <>
                <span
                    data-testid="approvals-pending-dot"
                    title={liveStatus}
                    className="absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full bg-red-500 border-2 border-background"
                />
                <span role="status" aria-live="polite" className="sr-only">{liveStatus}</span>
            </>
        );
    }
    return (
        <>
            <span
                data-testid="approvals-pending-badge"
                className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500/90 px-1.5 text-[10px] font-bold text-white"
            >
                {count > 99 ? "99+" : count}
            </span>
            <span role="status" aria-live="polite" className="sr-only">{liveStatus}</span>
        </>
    );
}

const Sidebar: React.FC<SidebarProps> = ({ className }) => {
    const router = useRouter();
    const { data: session } = useSession();
    const { level: roleLevel, loading: roleLoading } = useUserRole();
    const { isCapabilityEnabled } = useProductProfile();
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobile, setIsMobile] = useState(false);
    // Real identity fallback: the API-first login (persistBackendToken) stores
    // the backend email in localStorage; NextAuth's session stays empty when
    // sign-in bypassed the NextAuth route, which used to leave the static
    // "Atom User" placeholder in the sidebar.
    const profileEmail = React.useSyncExternalStore(
        subscribeToProfile,
        getProfileEmail,
        getServerProfileEmail,
    );
    const profile = React.useMemo(() => {
        if (!profileEmail) return {};
        const [name] = profileEmail.split("@");
        return { name, email: profileEmail };
    }, [profileEmail]);
    const displayName = session?.user?.name || profile.name || "Atom User";
    const displayEmail = session?.user?.email || profile.email || "Premium Agent Ops";

    const handleSignOut = async () => {
        if (typeof window !== "undefined") {
            const token = getAuthToken();
            const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
            if (token && apiBase) {
                try {
                    await fetch(`${apiBase}/api/auth/logout`, {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                    });
                } catch {
                    // Local sign-out still proceeds; the UI must not trap a user.
                }
            }
            localStorage.setItem("atom_explicit_logout", "1");
            localStorage.removeItem("auth_token");
            localStorage.removeItem("token");
            // Also clear the API-first credentials. persistBackendToken (lib/backendAuth.ts)
            // stores access_token + user_email alongside auth_token; leaving them behind
            // after logout keeps stale credentials in storage (e2e logout assertions and
            // any later "user email" reads pick them up).
            localStorage.removeItem("access_token");
            localStorage.removeItem("user_email");
            document.cookie = "auth_token=; path=/; max-age=0";
            document.cookie = "next-auth.session-token=; path=/; max-age=0";
        }
        signOut({ callbackUrl: "/auth/signin" });
    };

    // Handle responsive behavior
    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth < 1024) {
                setIsMobile(true);
                setIsCollapsed(true);
            } else {
                setIsMobile(false);
                setIsCollapsed(false);
            }
        };

        handleResize();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    const categories: { name: string; items: SidebarItem[] }[] = [
        {
            name: "CORE",
            items: [
                { label: "Dashboard", icon: Home, path: "/", capability: "chat" },
                { label: "Chat", icon: MessageSquare, path: "/chat", capability: "chat" },
                { label: "Workspace", icon: Layout, path: "/canvas", capability: "canvas" },
                // Deferred in the core release (documents search stays inside
                // the Documents page). Kept in code for the full profile.
                { label: "Search", icon: Search, path: "/search", capability: "search" },
                { label: "Data", icon: FileText, path: "/documents", capability: "documents" },
                { label: "Tasks", icon: CheckSquare, path: "/tasks", capability: "tasks" },
                { label: "Kanban", icon: KanbanSquare, path: "/boards", capability: "boards" },
                { label: "Automations", icon: Play, path: "/automations", capability: "automations" },
                { label: "Agents", icon: Bot, path: "/agents", capability: "agents" },
                // Approvals = the HITL/supervision queue: decisions need
                // team_lead+ on the backend. Kept as a safeguard in the core
                // release, but it is not an ordinary work surface.
                { label: "Approvals", icon: CheckSquare, path: "/approvals", capability: "approvals", minLevel: SUPERVISOR_MIN_LEVEL },
                // Activity: results, failures and unfinished work. Goal Runs
                // is the durable run surface; execution history is linked
                // from it.
                { label: "Activity", icon: Rocket, path: "/goal-runs", capability: "activity" },
                { label: "Marketplace", icon: Store, path: "/marketplace", capability: "marketplace" },
            ]
        },
        {
            name: "COMMAND CENTERS",
            items: [
                { label: "Projects", icon: Target, path: "/dashboards/projects", capability: "command_centers" },
                { label: "Sales & CRM", icon: Zap, path: "/dashboards/sales", capability: "command_centers" },
                { label: "Support", icon: Heart, path: "/dashboards/support", capability: "command_centers" },
                { label: "Knowledge", icon: Layout, path: "/dashboards/knowledge", capability: "command_centers" },
                { label: "Communication", icon: MessageSquare, path: "/communication", capability: "command_centers" },
            ]
        },
        {
            name: "BUSINESS",
            items: [
                { label: "Sales", icon: Target, path: "/sales", capability: "business_dashboards" },
                { label: "Marketing", icon: Zap, path: "/marketing", capability: "business_dashboards" },
                { label: "Finance", icon: CreditCard, path: "/finance", capability: "business_dashboards" },
                { label: "Analytics", icon: BarChart3, path: "/analytics", capability: "business_dashboards" },
            ]
        },
        {
            name: "PRODUCTIVITY",
            items: [
                { label: "Calendar", icon: Calendar, path: "/calendar", capability: "productivity" },
                { label: "Health", icon: Heart, path: "/health", capability: "productivity" },
                { label: "Voice", icon: Mic, path: "/voice", capability: "productivity" },
            ]
        },
        {
            name: "GOVERNANCE",
            items: [
                // Admin band (workspace_admin+). Deferred in the core release;
                // retained for the full profile.
                { label: "JIT Verification", icon: Shield, path: "/admin/jit-verification", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "BPE Workspace", icon: Brain, path: "/admin/bpe", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Learning & Verification", icon: GraduationCap, path: "/admin/learning-verification", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Self-Healing Harness", icon: Wrench, path: "/settings/harness-evolution", capability: "governance" },
                { label: "Business Facts", icon: CheckCircle, path: "/admin/business-facts", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "User Management", icon: Shield, path: "/admin/users", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Admin Settings", icon: Settings, path: "/admin/settings", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Audit Trail", icon: FileText, path: "/audit-trail", capability: "governance", minLevel: SUPERVISOR_MIN_LEVEL },
                { label: "Skill Builder", icon: Wrench, path: "/admin/skills/new", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Owner Cockpit", icon: BarChart3, path: "/dashboard/owner", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Forensics", icon: Search, path: "/dashboard/forensics", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
            ]
        },
        {
            name: "PLATFORM",
            items: [
                { label: "Integrations", icon: Layers, path: "/integrations", capability: "connectors" },
                { label: "Dev Studio", icon: Terminal, path: "/dev-studio", capability: "governance", minLevel: ADMIN_MIN_LEVEL },
                { label: "Settings", icon: Settings, path: "/settings", capability: "settings" },
            ]
        }
    ];

    const toggleSidebar = () => {

        setIsCollapsed(!isCollapsed);
    };

    return (
        <aside
            aria-label="Sidebar"
            className={cn(
                "relative flex flex-col h-screen bg-background border-r border-border transition-all duration-300 ease-in-out z-40 backdrop-blur-xl bg-opacity-80",
                isCollapsed ? "w-20" : "w-64",
                className
            )}
        >
            {/* Logo Area */}
            <div className="flex items-center justify-center h-16 border-b border-border">
                <div className={cn("flex items-center transition-all duration-300", isCollapsed ? "justify-center" : "px-6 w-full")}>
                    <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center text-primary-foreground font-bold text-xl shadow-[0_0_20px_rgba(59,130,246,0.4)]">
                        A
                    </div>
                    {!isCollapsed && (
                        <span className="ml-3 font-bold text-xl tracking-tight text-foreground bg-clip-text text-transparent bg-gradient-to-r from-foreground to-muted-foreground">
                            ATOM
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation Categories */}
            <nav aria-label="Main Navigation" className="flex-1 overflow-y-auto py-6 space-y-6 px-3 scrollbar-hide">
                {categories.map((category) => {
                    // Role-aware filtering. While the role is still loading,
                    // hide elevated items (a member must not see the admin
                    // band for the first seconds after login). If the fetch
                    // FAILS, fail open — a real admin must not be stranded by
                    // a transient /api/auth/me error; the backend enforces
                    // every gate.
                    // One capability configuration decides what this release
                    // exposes; role gating is applied on top of it.
                    const visibleItems = category.items.filter((item) => {
                        if (item.capability && !isCapabilityEnabled(item.capability)) {
                            return false;
                        }
                        if (roleLevel > 0) {
                            return !item.minLevel || roleLevel >= item.minLevel;
                        }
                        return roleLoading ? !item.minLevel : true;
                    });
                    if (visibleItems.length === 0) return null;
                    return (
                    <div key={category.name} className="space-y-1">
                        {!isCollapsed && (
                            <h3 className="px-3 text-[10px] font-bold tracking-widest text-muted-foreground uppercase mb-2 ml-1">
                                {category.name}
                            </h3>
                        )}
                        <div className="space-y-1">
                            {visibleItems.map((item) => {
                                const isActive = router.pathname === item.path ||
                                    (item.path !== "/" && router.pathname.startsWith(item.path));

                                return (
                                    <Link key={item.path} href={item.path} passHref>
                                        <div
                                            className={cn(
                                                "relative flex items-center px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 group",
                                                isActive
                                                    ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(59,130,246,0.05)]"
                                                    : "text-muted-foreground hover:bg-secondary/80 hover:text-foreground",
                                                isCollapsed ? "justify-center" : ""
                                            )}
                                            title={isCollapsed ? item.label : ""}
                                        >
                                            <item.icon
                                                className={cn(
                                                    "h-[18px] w-[18px] transition-all duration-300",
                                                    isActive
                                                        ? "text-primary drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] scale-110"
                                                        : "group-hover:text-foreground group-hover:scale-105"
                                                )}
                                            />
                                            {!isCollapsed && (
                                                <span className="ml-3 font-semibold text-[13.5px] truncate transition-colors">
                                                    {item.label}
                                                </span>
                                            )}

                                            {/* Pending-review count on the
                                                Approvals entry (supervisor
                                                gate resolved; hidden while
                                                the role is unknown). */}
                                            {item.path === "/approvals" && (
                                                <ApprovalsPendingBadge
                                                    active={roleLevel >= SUPERVISOR_MIN_LEVEL}
                                                    collapsed={isCollapsed}
                                                />
                                            )}

                                            {/* Active Indicator for collapsed mode */}
                                            {isCollapsed && isActive && (
                                                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-l-full shadow-[0_0_10px_rgba(59,130,246,1)]" />
                                            )}

                                            {/* Subtle Glow for active item */}
                                            {isActive && !isCollapsed && (
                                                <div className="absolute left-0 w-1 h-4 bg-primary rounded-r-full shadow-[0_0_10px_rgba(59,130,246,0.8)]" />
                                            )}
                                        </div>
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                    );
                })}
            </nav>

            {/* Footer / User Profile & Toggle */}
            <div className="p-3 border-t border-border bg-secondary/20 space-y-3">
                {!isCollapsed && (
                    <div
                        data-testid="dashboard-user-profile-button"
                        className="flex items-center p-2 rounded-xl bg-background/50 border border-border/50 group cursor-pointer hover:bg-background/80 transition-all"
                    >
                        <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center text-white ring-2 ring-background border border-blue-400/30">
                            <User className="h-5 w-5" />
                        </div>
                        <div className="ml-3 flex-1 overflow-hidden">
                            <p className="text-sm font-bold text-foreground truncate">{displayName}</p>
                            <p className="text-[11px] text-muted-foreground truncate">{displayEmail}</p>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            data-testid="dashboard-logout-button"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Sign out"
                            onClick={handleSignOut}
                        >
                            <LogOut className="h-4 w-4" />
                        </Button>
                    </div>
                )}

                <div className="flex items-center justify-between">
                    {isCollapsed && (
                        <>
                            <div
                                className="mx-auto h-9 w-9 rounded-xl bg-secondary/50 flex items-center justify-center text-muted-foreground hover:text-foreground transition-all cursor-pointer"
                                title={displayName}
                            >
                                <User className="h-5 w-5" />
                            </div>
                            <button
                                onClick={handleSignOut}
                                title="Sign out"
                                className="mx-auto h-8 w-8 rounded-xl flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                            >
                                <LogOut className="h-4 w-4" />
                            </button>
                        </>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleSidebar}
                        className={cn("text-muted-foreground hover:text-foreground hover:bg-secondary", isCollapsed ? "hidden" : "")}
                    >
                        {isCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                    </Button>
                    {isCollapsed && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={toggleSidebar}
                            className="text-muted-foreground hover:text-foreground hover:bg-secondary mx-auto"
                        >
                            <ChevronRight className="h-5 w-5" />
                        </Button>
                    )}
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;


