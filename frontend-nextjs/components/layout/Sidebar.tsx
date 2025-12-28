import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useSession } from "next-auth/react";
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
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";

interface SidebarProps {
    className?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ className }) => {
    const router = useRouter();
    const { data: session } = useSession();
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

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

    const categories = [
        {
            name: "CORE",
            items: [
                { label: "Dashboard", icon: Home, path: "/" },
                { label: "Chat", icon: MessageSquare, path: "/chat" },
                { label: "Search", icon: Search, path: "/search" },
                { label: "Tasks", icon: CheckSquare, path: "/tasks" },
                { label: "Automations", icon: Play, path: "/automations" },
                { label: "Agents", icon: Bot, path: "/agents" },
                { label: "Marketplace", icon: Store, path: "/marketplace" },
            ]
        },
        {
            name: "COMMAND CENTERS",
            items: [
                { label: "Projects", icon: Target, path: "/dashboards/projects" },
                { label: "Sales & CRM", icon: Zap, path: "/dashboards/sales" },
                { label: "Support", icon: Heart, path: "/dashboards/support" },
                { label: "Knowledge", icon: Layout, path: "/dashboards/knowledge" },
                { label: "Communication", icon: MessageSquare, path: "/communication" },
            ]
        },
        {
            name: "BUSINESS",
            items: [
                { label: "Sales", icon: Target, path: "/sales" },
                { label: "Marketing", icon: Zap, path: "/marketing" },
                { label: "Finance", icon: CreditCard, path: "/finance" },
                { label: "Analytics", icon: BarChart3, path: "/analytics" },
            ]
        },
        {
            name: "PRODUCTIVITY",
            items: [
                { label: "Calendar", icon: Calendar, path: "/calendar" },
                { label: "Health", icon: Heart, path: "/health" },
                { label: "Voice", icon: Mic, path: "/voice" },
            ]
        },
        {
            name: "PLATFORM",
            items: [
                { label: "Integrations", icon: Layers, path: "/integrations" },
                { label: "Dev Studio", icon: Terminal, path: "/dev-studio" },
                { label: "Settings", icon: Settings, path: "/settings/account" },
            ]
        }
    ];

    const toggleSidebar = () => {
        setIsCollapsed(!isCollapsed);
    };

    return (
        <div
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
            <div className="flex-1 overflow-y-auto py-6 space-y-6 px-3 scrollbar-hide">
                {categories.map((category) => (
                    <div key={category.name} className="space-y-1">
                        {!isCollapsed && (
                            <h3 className="px-3 text-[10px] font-bold tracking-widest text-muted-foreground uppercase mb-2 ml-1">
                                {category.name}
                            </h3>
                        )}
                        <div className="space-y-1">
                            {category.items.map((item) => {
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
                ))}
            </div>

            {/* Footer / User Profile & Toggle */}
            <div className="p-3 border-t border-border bg-secondary/20 space-y-3">
                {!isCollapsed && (
                    <div className="flex items-center p-2 rounded-xl bg-background/50 border border-border/50 group cursor-pointer hover:bg-background/80 transition-all">
                        <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center text-white ring-2 ring-background border border-blue-400/30">
                            <User className="h-5 w-5" />
                        </div>
                        <div className="ml-3 flex-1 overflow-hidden">
                            <p className="text-sm font-bold text-foreground truncate">{session?.user?.name || "Atom User"}</p>
                            <p className="text-[11px] text-muted-foreground truncate">{session?.user?.email || "Premium Agent Ops"}</p>
                        </div>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity">
                            <LogOut className="h-4 w-4" />
                        </Button>
                    </div>
                )}

                <div className="flex items-center justify-between">
                    {isCollapsed && (
                        <div className="mx-auto h-9 w-9 rounded-xl bg-secondary/50 flex items-center justify-center text-muted-foreground hover:text-foreground transition-all cursor-pointer">
                            <User className="h-5 w-5" />
                        </div>
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
        </div>
    );
};

export default Sidebar;
