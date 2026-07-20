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
} from "lucide-react";

import { Button } from "../components/ui/button";
import {
  Card,
  CardHeader,

  CardTitle,
  CardContent,
} from "../components/ui/card";
import { OnboardingWizard } from "../components/Onboarding/OnboardingWizard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DashboardFeed {
  recent_executions: Array<{
    id: string;
    agent_id: string | null;
    agent_name: string;
    status: string;
    input_summary: string;
    started_at: string | null;
    duration_seconds: number;
  }>;
  recent_canvases: Array<{
    id: string;
    canvas_id: string | null;
    action: string | null;
    created_at: string | null;
  }>;
  last_chat_session: { id: string; title: string; updated_at: string | null } | null;
  agents_progress: Array<{
    id: string;
    name: string;
    current_tier: string;
    next_tier: string | null;
    next_threshold_episodes: number | null;
  }>;
}

const Home = () => {
  const router = useRouter();
  useEffect(() => {
    const hasAuth = () => {
      const token = localStorage.getItem('token');
      const sessionToken = localStorage.getItem('auth_token');
      const cookieToken = typeof document !== 'undefined'
        ? document.cookie.includes('next-auth.session-token=') || document.cookie.includes('auth_token=')
        : false;
      return Boolean(token || sessionToken || cookieToken);
    };

    const runBootstrap = async () => {
      if (typeof window === 'undefined') return;

      if (hasAuth()) {
        router.replace('/dashboard');
        return;
      }

      const explicitLogout = localStorage.getItem('atom_explicit_logout') === '1';
      if (explicitLogout) {
        router.replace('/login');
        return;
      }

      const host = window.location.hostname;
      const isLocalHost = host === 'localhost' || host === '127.0.0.1';
      if (!isLocalHost) return;

      try {
        const response = await fetch('/api/dev/bootstrap-session');
        if (!response.ok) return;

        const data = await response.json();
        if (!data?.access_token) return;

        localStorage.removeItem('atom_explicit_logout');
        localStorage.setItem('auth_token', data.access_token);
        document.cookie = `auth_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
        document.cookie = `next-auth.session-token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
        router.replace('/dashboard');
      } catch (error) {
        console.error('Dev bootstrap failed:', error);
      }
    };

    runBootstrap();
  }, [router]);

  const [showWizard, setShowWizard] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [feed, setFeed] = useState<DashboardFeed | null>(null);

  useEffect(() => {
    const checkOnboarding = async () => {
      try {
        const token = localStorage.getItem("token") || localStorage.getItem("auth_token");
        // Only check if we have a token (logged in)
        if (token) {
          const res = await fetch(`${API_BASE}/api/onboarding/status`, {
            headers: { "Authorization": `Bearer ${token}` }
          });
          if (res.ok) {
            const data = await res.json();
            if (!data.onboarding_completed) {
              setShowWizard(true);
              // Fetch full user details for wizard personalized greeting
              const userRes = await fetch(`${API_BASE}/api/users/me`, {
                headers: { "Authorization": `Bearer ${token}` }
              });
              if (userRes.ok) {
                setUser(await userRes.json());
              }
            }
          }
        }
      } catch (err) {
        console.error("Failed to check onboarding status", err);
      }
    };

    // P3.2 — pull the dashboard activity feed once on mount. Non-blocking;
    // failure leaves feed=null and the static feature grid still renders.
    const loadFeed = async () => {
      try {
        const token = localStorage.getItem("token") || localStorage.getItem("auth_token");
        if (!token) return;
        const res = await fetch(`${API_BASE}/api/dashboard/feed`, {
          headers: { "Authorization": `Bearer ${token}` },
        });
        if (!res.ok) return;
        const json = await res.json();
        setFeed(json?.data ?? json);
      } catch {
        // Silent — the dashboard section just won't render.
      }
    };

    checkOnboarding();
    loadFeed();
  }, []);

  const hasFeed = !!feed && (
    (feed.recent_executions?.length ?? 0) > 0 ||
    !!feed.last_chat_session ||
    (feed.agents_progress?.length ?? 0) > 0
  );

  const features = [
    {
      title: "Search",
      description:
        "AI-powered search across all your documents, meetings, and notes",
      icon: Search,
      path: "/search",
      color: "text-blue-500",
    },
    {
      title: "Communication",
      description: "Unified messaging hub for all your communication platforms",
      icon: MessageSquare,
      path: "/communication",
      color: "text-green-500",
    },
    {
      title: "Tasks",
      description: "Smart task management with AI-powered prioritization",
      icon: CheckSquare,
      path: "/tasks",
      color: "text-orange-500",
    },
    {
      title: "Workflow Automation",
      description: "Create and manage automated workflows across services",
      icon: Play,
      path: "/automations",
      color: "text-purple-500",
    },
    {
      title: "Calendar",
      description: "Smart scheduling and calendar management",
      icon: Calendar,
      path: "/calendar",
      color: "text-red-500",
    },
    {
      title: "Finance",
      description: "Manage subscriptions, invoices, and financial integrations",
      icon: Server,
      path: "/finance",
      color: "text-green-500",
    },
    {
      title: "Integrations",
      description: "Connect and manage all your third-party integrations",
      icon: Server,
      path: "/integrations",
      color: "text-blue-500",
    },
    {
      title: "Voice",
      description: "AI voice assistants and phone integration",
      icon: MessageSquare,
      path: "/voice",
      color: "text-pink-500",
    },
    {
      title: "Settings",
      description: "Account settings, preferences, and session management",
      icon: Server,
      path: "/settings/account",
      color: "text-gray-500 dark:text-gray-400",
    },
    {
      title: "Dev Studio",
      description: "Web app development and testing environment",
      icon: Terminal,
      path: "/dev-studio",
      color: "text-purple-500",
    },
    {
      title: "Dev Tools",
      description: "Development utilities and system integration",
      icon: Terminal,
      path: "/dev-tools",
      color: "text-purple-500",
    },
    {
      title: "Dev Status",
      description: "Development environment monitoring and status",
      icon: Server,
      path: "/dev-status",
      color: "text-teal-500",
    },
  ];

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <OnboardingWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        user={user}
        onUpdate={(data) => {
          // Optimistically update local state if needed
          if (data.onboarding_completed) {
            setShowWizard(false);
          }
        }}
      />
      <div className="flex flex-col space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-4">Welcome to ATOM</h1>
          <p className="text-xl text-gray-600 dark:text-gray-400">
            Your AI-powered personal automation platform
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            (Development Mode - Auth Disabled)
          </p>
        </div>

        {/* P3.2 — Activity feed dashboard. Replaces the static-feature-grid-only
            landing with a real "pick up where you left off" surface. Renders
            only when there is activity; otherwise the static grid below still
            serves as the explore-the-platform fallback. */}
        {hasFeed && feed && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Pick up where you left off */}
            {feed.last_chat_session && (
              <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => router.push(`/chat?session=${feed.last_chat_session!.id}`)}>
                <CardHeader>
                  <CardTitle className="text-base">Pick up where you left off</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm font-medium truncate">{feed.last_chat_session.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {feed.last_chat_session.updated_at
                      ? `Updated ${new Date(feed.last_chat_session.updated_at).toLocaleString()}`
                      : "Continue this conversation →"}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Recent executions */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent activity</CardTitle>
              </CardHeader>
              <CardContent>
                {feed.recent_executions.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No agent runs yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {feed.recent_executions.slice(0, 5).map((ex) => (
                      <li key={ex.id} className="flex items-center justify-between text-sm">
                        <span className="truncate flex-1 min-w-0">
                          <span className="font-medium">{ex.agent_name}</span>
                          <span className="text-muted-foreground"> — {ex.input_summary.slice(0, 60) || "(no input)"}</span>
                        </span>
                        <span className={`ml-2 shrink-0 text-xs px-2 py-0.5 rounded-full ${
                          ex.status === "completed" ? "bg-green-100 text-green-800" :
                          ex.status === "failed" ? "bg-red-100 text-red-800" :
                          "bg-gray-100 text-gray-700"
                        }`}>
                          {ex.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Agent progress */}
            {feed.agents_progress.length > 0 && (
              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base">Your agents&apos; progress</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {feed.agents_progress.slice(0, 6).map((a) => (
                      <li key={a.id} className="flex items-center justify-between text-sm">
                        <Link href={`/agents`} className="truncate font-medium hover:underline">{a.name}</Link>
                        <span className="text-xs text-muted-foreground ml-2 shrink-0">
                          <span className="inline-block px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 uppercase tracking-wide mr-2">{a.current_tier}</span>
                          {a.next_threshold_episodes ? `${a.next_threshold_episodes} eps → ${a.next_tier}` : "max tier"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <div key={index}>
              <Card
                className="h-full cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-200"
                onClick={() => router.push(feature.path)}
              >
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <feature.icon className={`h-6 w-6 ${feature.color}`} />
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600 dark:text-gray-400">{feature.description}</p>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>

        <div className="text-center mt-8">
          <p className="text-lg text-gray-600 dark:text-gray-400 mb-4">
            Ready to automate your workflow?
          </p>
          <Button
            size="lg"
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={() => router.push("/automations")}
          >
            Get Started with Automation
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Home;


