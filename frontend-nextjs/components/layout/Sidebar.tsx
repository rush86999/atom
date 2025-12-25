import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
    Search,
    MessageSquare,
    CheckSquare,
    Play,
    Calendar,
    Terminal,
    Server,
    Settings,
    ChevronLeft,
    ChevronRight,
    Home,
    Target,
    CreditCard,
    Layers,
    Mic,
    Zap,
    Heart,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";

interface SidebarProps {
    className?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ className }) => {
    const router = useRouter();
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobile, setIsMobile] = useState(false);

    // Handle responsive behavior
    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth < 768) {
                setIsMobile(true);
                setIsCollapsed(true);
            } else {
                setIsMobile(false);
                setIsCollapsed(false);
            }
        };

        // Initial check
        handleResize();

        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    const navItems = [
        { label: "Dashboard", icon: Home, path: "/" },
        { label: "Chat", icon: MessageSquare, path: "/chat" },
        { label: "Search", icon: Search, path: "/search" },
        { label: "Tasks", icon: CheckSquare, path: "/tasks" },
        { label: "Automations", icon: Play, path: "/automations" },
        { label: "Calendar", icon: Calendar, path: "/calendar" },
        { label: "Finance", icon: CreditCard, path: "/finance" },
        { label: "Sales", icon: Target, path: "/sales" },
        { label: "Marketing", icon: Zap, path: "/marketing" },
        { label: "Health", icon: Heart, path: "/health" },
        { label: "Integrations", icon: Layers, path: "/integrations" },
        { label: "Voice", icon: Mic, path: "/voice" },
        { label: "Dev Studio", icon: Terminal, path: "/dev-studio" },
        { label: "Settings", icon: Settings, path: "/settings/account" },
    ];

    const toggleSidebar = () => {
        setIsCollapsed(!isCollapsed);
    };

    return (
        <div
            className={cn(
                "relative flex flex-col h-screen bg-background border-r border-border transition-all duration-300 ease-in-out z-40",
                isCollapsed ? "w-20" : "w-64",
                className
            )}
        >
            {/* Logo Area */}
            <div className="flex items-center justify-center h-16 border-b border-border">
                <div className={cn("flex items-center transition-all duration-300", isCollapsed ? "justify-center" : "px-6 w-full")}>
                    <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold text-xl shadow-[0_0_15px_rgba(59,130,246,0.5)]">
                        A
                    </div>
                    {!isCollapsed && (
                        <span className="ml-3 font-bold text-xl tracking-wider text-foreground">
                            ATOM
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation Items */}
            <div className="flex-1 overflow-y-auto py-4 space-y-2 px-3">
                {navItems.map((item) => {
                    const isActive = router.pathname === item.path ||
                        (item.path !== "/" && router.pathname.startsWith(item.path));

                    return (
                        <Link key={item.path} href={item.path} passHref>
                            <div
                                className={cn(
                                    "flex items-center px-3 py-3 rounded-lg cursor-pointer transition-all duration-200 group",
                                    isActive
                                        ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_10px_rgba(59,130,246,0.1)]"
                                        : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                                    isCollapsed ? "justify-center" : ""
                                )}
                                title={isCollapsed ? item.label : ""}
                            >
                                <item.icon
                                    className={cn(
                                        "h-5 w-5 transition-colors",
                                        isActive ? "text-primary drop-shadow-[0_0_5px_rgba(59,130,246,0.5)]" : "group-hover:text-foreground"
                                    )}
                                />
                                {!isCollapsed && (
                                    <span className="ml-3 font-medium text-sm truncate">
                                        {item.label}
                                    </span>
                                )}

                                {/* Active Indicator for collapsed mode */}
                                {isCollapsed && isActive && (
                                    <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-l-full shadow-[0_0_10px_rgba(59,130,246,0.8)]" />
                                )}
                            </div>
                        </Link>
                    );
                })}
            </div>

            {/* Footer / Toggle */}
            <div className="p-4 border-t border-border flex justify-end">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleSidebar}
                    className="text-muted-foreground hover:text-foreground hover:bg-secondary"
                >
                    {isCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                </Button>
            </div>
        </div>
    );
};

export default Sidebar;
