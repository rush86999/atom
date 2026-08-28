import React, { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from 'next/router';
import { Button } from "../../components/ui/button";
import { Menu, PanelRightOpen, X } from "lucide-react";
import ChatHistorySidebar from "../../components/chat/ChatHistorySidebar";
import ChatInterface from "../../components/chat/ChatInterface";
import AgentWorkspace from "../../components/chat/AgentWorkspace";

const AUTO_HIDE_STORAGE_KEY = "atom_workspace_autohide";
/** How long a settled run stays open before auto-hiding. */
const AUTO_HIDE_DELAY_MS = 8000;

const ChatPage = () => {
    const router = useRouter();
    const { agent_id } = router.query;
    const initialAgentId = Array.isArray(agent_id) ? agent_id[0] : agent_id || null;

    // Restore the last active session after a page reload so the conversation
    // isn't lost (the chat sidebar lists sessions, but the middle pane should
    // resume where the user left off).
    // Mount-guarded: reading localStorage during initial render produced
    // server/client hydration mismatches ("Text content does not match").
    // Start empty; restore the last session right after mount.
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

    useEffect(() => {
        const saved =
            typeof window === "undefined"
                ? null
                : window.localStorage.getItem("atom_chat_session_id");
        if (saved && saved !== "new") {
            setSelectedSessionId(saved);
        }
    }, []);
    // Mobile drawer state.
    const [showSidebar, setShowSidebar] = useState(false);
    const [showWorkspace, setShowWorkspace] = useState(false);

    // ── Workspace auto-show / auto-hide ──────────────────────────────────
    // The desktop pane stays mounted; `workspaceOpen` only toggles between
    // the full panel and the slim activity rail. Policy: open as soon as
    // agent activity streams in, collapse ~8s after the run settles —
    // unless the user grabbed control (manual close suppresses auto-open
    // for the rest of that run; any interaction cancels the pending hide).
    const [workspaceOpen, setWorkspaceOpen] = useState(true);
    const [autoHideEnabled, setAutoHideEnabled] = useState(true);
    const autoOpenedRef = useRef(false);
    const userClosedThisRunRef = useRef(false);
    const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const saved = window.localStorage.getItem(AUTO_HIDE_STORAGE_KEY);
        if (saved !== null) setAutoHideEnabled(saved !== "off");
    }, []);

    const cancelSettleTimer = useCallback(() => {
        if (settleTimerRef.current) {
            clearTimeout(settleTimerRef.current);
            settleTimerRef.current = null;
        }
    }, []);

    const handleAgentActivity = useCallback((kind: "step" | "run_start") => {
        if (kind === "run_start") {
            // a fresh run re-arms auto-open even if the user closed the panel
            // during the previous one
            userClosedThisRunRef.current = false;
            cancelSettleTimer();
        }
        setWorkspaceOpen((open) => {
            if (!open && !userClosedThisRunRef.current) {
                autoOpenedRef.current = true;
                return true;
            }
            return open;
        });
    }, [cancelSettleTimer]);

    const handleRunSettled = useCallback(() => {
        if (!autoHideEnabled) return;
        cancelSettleTimer();
        settleTimerRef.current = setTimeout(() => {
            settleTimerRef.current = null;
            if (autoOpenedRef.current) {
                setWorkspaceOpen(false);
                autoOpenedRef.current = false;
            }
        }, AUTO_HIDE_DELAY_MS);
    }, [autoHideEnabled, cancelSettleTimer]);

    const handleToggleWorkspace = useCallback(() => {
        cancelSettleTimer();
        setWorkspaceOpen((open) => {
            const next = !open;
            if (next) {
                autoOpenedRef.current = false;
                userClosedThisRunRef.current = false;
            } else {
                // manual close wins for the rest of the current run
                userClosedThisRunRef.current = true;
                autoOpenedRef.current = false;
            }
            return next;
        });
    }, [cancelSettleTimer]);

    const handleUserInteraction = useCallback(() => {
        cancelSettleTimer();
    }, [cancelSettleTimer]);

    const handleAutoHideToggle = useCallback((enabled: boolean) => {
        setAutoHideEnabled(enabled);
        window.localStorage.setItem(AUTO_HIDE_STORAGE_KEY, enabled ? "on" : "off");
        if (!enabled) cancelSettleTimer();
    }, [cancelSettleTimer]);

    const handleSessionCreated = (sessionId: string) => {
        setSelectedSessionId(sessionId);
        if (sessionId && sessionId !== "new" && sessionId !== "unknown") {
            window.localStorage.setItem("atom_chat_session_id", sessionId);
        }
    };

    const handleSelectSession = (id: string) => {
        setSelectedSessionId(id);
        if (id && id !== "new") {
            window.localStorage.setItem("atom_chat_session_id", id);
        }
    };

    // NOTE: ChatInterface is rendered exactly ONCE and shared by both the
    // desktop 3-pane layout and the mobile single-pane layout (the sidebar /
    // workspace are desktop panels or mobile overlay drawers). Rendering a
    // second (CSS-hidden) ChatInterface for mobile used to duplicate every
    // data-testid in the DOM, which broke strict-mode selectors and doubled
    // message counts in E2E tests.
    return (
        <div className="h-[calc(100vh-2rem)] w-full bg-background overflow-hidden rounded-lg border border-border shadow-sm flex flex-col relative">
            {/* Mobile top bar with toggle buttons (hidden on desktop) */}
            <div className="md:hidden flex items-center justify-between p-2 border-b border-border bg-muted/30">
                <Button size="icon" variant="ghost" aria-label="Toggle history" onClick={() => { setShowSidebar(!showSidebar); setShowWorkspace(false); }}>
                    <Menu className="h-4 w-4" />
                </Button>
                <span className="text-sm font-medium">Chat</span>
                <Button size="icon" variant="ghost" aria-label="Toggle workspace" onClick={() => { setShowWorkspace(!showWorkspace); setShowSidebar(false); }}>
                    <PanelRightOpen className="h-4 w-4" />
                </Button>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Left Pane: Chat History (desktop; mobile uses an overlay drawer) */}
                <div className="hidden md:block w-[15%] min-w-[180px] max-w-[280px] bg-muted/30 border-r border-border">
                    <ChatHistorySidebar
                        selectedSessionId={selectedSessionId}
                        onSelectSession={handleSelectSession}
                    />
                </div>

                {/* Middle Pane: Chat Interface (single instance for all layouts) */}
                <div className="flex-1 min-w-0">
                    <ChatInterface
                        sessionId={selectedSessionId}
                        onSessionCreated={handleSessionCreated}
                        initialAgentId={initialAgentId}
                    />
                </div>

                {/* Right Pane: Agent Workspace (desktop; mobile uses an overlay drawer).
                    Stays mounted while "closed" so it renders as the slim activity rail
                    and keeps receiving WebSocket events for auto-show. */}
                <div className={`hidden md:block ${workspaceOpen ? "w-[45%] min-w-[300px]" : "w-11"} bg-muted/10 border-l border-border shrink-0`}>
                    <AgentWorkspace
                        sessionId={selectedSessionId}
                        initialAgentId={initialAgentId}
                        collapsed={!workspaceOpen}
                        onToggleCollapsed={handleToggleWorkspace}
                        onAgentActivity={handleAgentActivity}
                        onRunSettled={handleRunSettled}
                        onUserInteraction={handleUserInteraction}
                        autoHide={autoHideEnabled}
                        onAutoHideToggle={handleAutoHideToggle}
                    />
                </div>
            </div>

            {/* Mobile drawers (only rendered while open) */}
            {showSidebar && (
                <div className="md:hidden absolute inset-y-0 left-0 w-64 bg-background border-r border-border shadow-lg z-10">
                    <div className="flex justify-end p-1">
                        <Button size="icon" variant="ghost" aria-label="Close history" onClick={() => setShowSidebar(false)}>
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                    <ChatHistorySidebar
                        selectedSessionId={selectedSessionId}
                        onSelectSession={(id) => { handleSelectSession(id); setShowSidebar(false); }}
                    />
                </div>
            )}

            {showWorkspace && (
                <div className="md:hidden absolute inset-y-0 right-0 w-64 bg-background border-l border-border shadow-lg z-10">
                    <div className="flex justify-end p-1">
                        <Button size="icon" variant="ghost" aria-label="Close workspace" onClick={() => setShowWorkspace(false)}>
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                    <AgentWorkspace
                        sessionId={selectedSessionId}
                        initialAgentId={initialAgentId}
                    />
                </div>
            )}
        </div>
    );
};

export default ChatPage;
