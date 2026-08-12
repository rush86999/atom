import React, { useState } from "react";
import { useRouter } from 'next/router';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../../components/ui/resizable";
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
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(() => {
        if (typeof window === "undefined") return null;
        const saved = window.localStorage.getItem("atom_chat_session_id");
        return saved && saved !== "new" ? saved : null;
    });
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

    return (
        <div className="h-[calc(100vh-2rem)] w-full bg-background overflow-hidden rounded-lg border border-border shadow-sm flex flex-col">
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

            {/* Desktop: 3-pane resizable layout */}
            <div className="hidden md:flex flex-1 overflow-hidden">
                <ResizablePanelGroup direction="horizontal">
                    {/* Left Pane: Chat History */}
                    <ResizablePanel defaultSize={15} minSize={10} maxSize={25} className="bg-muted/30">
                        <ChatHistorySidebar
                            selectedSessionId={selectedSessionId}
                            onSelectSession={handleSelectSession}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Middle Pane: Chat Interface */}
                    <ResizablePanel defaultSize={40} minSize={30}>
                        <ChatInterface
                            sessionId={selectedSessionId}
                            onSessionCreated={handleSessionCreated}
                            initialAgentId={initialAgentId}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Right Pane: Agent Workspace */}
                    <ResizablePanel defaultSize={45} minSize={20} className="bg-muted/10">
                        <AgentWorkspace
                            sessionId={selectedSessionId}
                            initialAgentId={initialAgentId}
                        />
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>

            {/* Mobile: single-pane with drawer overlays */}
            <div className="md:hidden flex-1 overflow-hidden relative">
                {/* Chat always visible */}
                <div className="h-full">
                    <ChatInterface
                        sessionId={selectedSessionId}
                        onSessionCreated={handleSessionCreated}
                        initialAgentId={initialAgentId}
                    />
                </div>

                {/* Sidebar drawer */}
                {showSidebar && (
                    <div className="absolute inset-y-0 left-0 w-64 bg-background border-r border-border shadow-lg z-10">
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

                {/* Workspace drawer */}
                {showWorkspace && (
                    <div className="absolute inset-y-0 right-0 w-64 bg-background border-l border-border shadow-lg z-10">
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
        </div>
    );
};

export default ChatPage;
