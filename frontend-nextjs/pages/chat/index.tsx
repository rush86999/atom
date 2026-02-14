import React, { useState } from "react";
import { useRouter } from 'next/router';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../../components/ui/resizable";
import ChatHistorySidebar from "../../components/chat/ChatHistorySidebar";
import ChatInterface from "../../components/chat/ChatInterface";
import AgentWorkspace from "../../components/chat/AgentWorkspace";

const ChatPage = () => {
    const router = useRouter(); // Use router to get query params
    const { agent_id } = router.query;
    const initialAgentId = Array.isArray(agent_id) ? agent_id[0] : agent_id || null;

    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

    return (
        <div className="h-[calc(100vh-2rem)] w-full bg-background overflow-hidden rounded-lg border border-border shadow-sm">
            <ResizablePanelGroup direction="horizontal">
                {/* Left Pane: Chat History */}
                <ResizablePanel defaultSize={20} minSize={15} maxSize={30} className="bg-muted/30">
                    <ChatHistorySidebar
                        selectedSessionId={selectedSessionId}
                        onSelectSession={setSelectedSessionId}
                    />
                </ResizablePanel>

                <ResizableHandle />

                {/* Middle Pane: Chat Interface */}
                <ResizablePanel defaultSize={40} minSize={30}>
                    <ChatInterface
                        sessionId={selectedSessionId}
                        onSessionCreated={setSelectedSessionId}
                        initialAgentId={initialAgentId}
                    />
                </ResizablePanel>

                <ResizableHandle />

                {/* Right Pane: Agent Workspace */}
                <ResizablePanel defaultSize={40} minSize={30} className="bg-muted/10">
                    <AgentWorkspace
                        sessionId={selectedSessionId}
                        initialAgentId={initialAgentId}
                    />
                </ResizablePanel>
            </ResizablePanelGroup>
        </div>
    );
};

export default ChatPage;
