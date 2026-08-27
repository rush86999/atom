import React, { useEffect, useState } from "react";
import { useRouter } from 'next/router';
import { Button } from "../../components/ui/button";
import { Menu, PanelRightOpen, X } from "lucide-react";
import ChatHistorySidebar from "../../components/chat/ChatHistorySidebar";
import ChatInterface from "../../components/chat/ChatInterface";
import AgentWorkspace from "../../components/chat/AgentWorkspace";

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

                {/* Right Pane: Agent Workspace (desktop; mobile uses an overlay drawer) */}
                <div className="hidden md:block w-[45%] min-w-[300px] bg-muted/10 border-l border-border">
                    <AgentWorkspace
                        sessionId={selectedSessionId}
                        initialAgentId={initialAgentId}
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
