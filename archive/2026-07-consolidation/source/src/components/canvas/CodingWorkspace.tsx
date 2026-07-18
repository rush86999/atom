'use client';

import { useState, useEffect } from 'react';
import { TerminalCanvas } from './TerminalCanvas';
import { DocumentCanvas } from './DocumentCanvas';
import { BrowserCanvas } from './BrowserCanvas';
import { GuidancePanel } from './GuidancePanel';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Code, Terminal, Brain, Settings, Play, Shield, Globe } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

import { useCanvasGuidance } from '@/hooks/useCanvasGuidance';

interface CodingWorkspaceProps {
    canvasId: string;
    agentId?: string;
    tenantId?: string;
}

/**
 * CodingWorkspace - A unified environment for AI Software Engineering.
 * Combines code editing, terminal execution, and human guidance.
 */
export function CodingWorkspace({ canvasId, agentId, tenantId }: CodingWorkspaceProps) {
    const {
        currentAction,
        actionHistory,
        handleApprove,
        handleEdit,
        handleSkip,
        handleCancel,
        handleGuidance
    } = useCanvasGuidance(canvasId);

    const [activeTab, setActiveTab] = useState('editor');
    const [isAgentActive, setIsAgentActive] = useState(false);

    // Simulate agent activity for UI demo purposes
    useEffect(() => {
        if (agentId) {
            setIsAgentActive(true);
        }
    }, [agentId]);

    return (
        <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
            <ResizablePanelGroup direction="horizontal">
                {/* Main Content Area: Editor + Terminal */}
                <ResizablePanel defaultSize={70} minSize={30}>
                    <ResizablePanelGroup direction="vertical">
                        {/* Editor Area */}
                        <ResizablePanel defaultSize={60} minSize={20}>
                            <div className="h-full flex flex-col">
                                <div className="bg-gray-900 border-b border-gray-800 px-4 py-2 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Code className="w-4 h-4 text-blue-400" />
                                        <span className="text-sm font-medium">Code Editor</span>
                                        <Badge variant="outline" className="text-xs bg-blue-900/20 text-blue-400 border-blue-800">
                                            Atom Engineer
                                        </Badge>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button size="sm" variant="ghost" className="h-8 text-xs text-gray-400 hover:text-white">
                                            <Play className="w-3 h-3 mr-1" /> Run
                                        </Button>
                                        <Button size="sm" className="h-8 text-xs bg-blue-600 hover:bg-blue-700">
                                            Commit Changes
                                        </Button>
                                    </div>
                                </div>
                                <div className="flex-1 bg-gray-950 overflow-auto">
                                    <DocumentCanvas
                                        documentId={`${canvasId}-code`}
                                        initialTitle="main.py"
                                        initialContent="# Atom Coding Agent Workspace\n\ndef main():\n    print('Hello from the Universal Canvas!')\n\nif __name__ == '__main__':\n    main()"
                                    />
                                </div>
                            </div>
                        </ResizablePanel>

                        <ResizableHandle withHandle />

                        {/* Secondary Tool Area (Terminal/Browser) */}
                        <ResizablePanel defaultSize={40} minSize={10}>
                            <Tabs defaultValue="terminal" className="h-full flex flex-col bg-black">
                                <div className="bg-gray-900 border-b border-gray-800 px-2 flex items-center h-9">
                                    <TabsList className="bg-transparent h-7">
                                        <TabsTrigger value="terminal" className="text-[10px] gap-1 data-[state=active]:bg-gray-800 h-6">
                                            <Terminal className="w-3 h-3" /> Terminal
                                        </TabsTrigger>
                                        <TabsTrigger value="browser" className="text-[10px] gap-1 data-[state=active]:bg-gray-800 h-6">
                                            <Globe className="w-3 h-3" /> Research Browser
                                        </TabsTrigger>
                                    </TabsList>
                                </div>
                                <TabsContent value="terminal" className="flex-1 m-0 overflow-hidden">
                                    <TerminalCanvas canvasId={canvasId} />
                                </TabsContent>
                                <TabsContent value="browser" className="flex-1 m-0 overflow-hidden bg-white/5">
                                    <BrowserCanvas canvasId={canvasId} />
                                </TabsContent>
                            </Tabs>
                        </ResizablePanel>
                    </ResizablePanelGroup>
                </ResizablePanel>

                <ResizableHandle withHandle />

                {/* Right Sidebar: Guidance + Intelligence */}
                <ResizablePanel defaultSize={30} minSize={20}>
                    <div className="h-full flex flex-col bg-gray-900 border-l border-gray-800">
                        <Tabs defaultValue="guidance" className="w-full h-full flex flex-col">
                            <div className="px-4 py-2 border-b border-gray-800">
                                <TabsList className="bg-gray-800 h-9 p-1">
                                    <TabsTrigger value="guidance" className="text-xs gap-1 data-[state=active]:bg-gray-700">
                                        <Brain className="w-3 h-3" /> Guidance
                                    </TabsTrigger>
                                    <TabsTrigger value="governance" className="text-xs gap-1 data-[state=active]:bg-gray-700">
                                        <Shield className="w-3 h-3" /> Governance
                                    </TabsTrigger>
                                    <TabsTrigger value="settings" className="text-xs gap-1 data-[state=active]:bg-gray-700">
                                        <Settings className="w-3 h-3" /> Config
                                    </TabsTrigger>
                                </TabsList>
                            </div>

                            <TabsContent value="guidance" className="flex-1 overflow-hidden m-0">
                                <GuidancePanel
                                    currentAction={currentAction}
                                    actionHistory={actionHistory}
                                    onApprove={handleApprove}
                                    onEdit={handleEdit}
                                    onSkip={handleSkip}
                                    onCancel={handleCancel}
                                    onGuidance={handleGuidance}
                                />
                            </TabsContent>


                            <TabsContent value="governance" className="flex-1 p-4 bg-gray-950 overflow-auto m-0">
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-gray-300">Active Security Policies</h3>
                                    <div className="space-y-2">
                                        <PolicyItem name="Command Whitelist" status="Active" description="Only allowed dev tools can be executed" />
                                        <PolicyItem name="Network Egress" status="Restricted" description="No external connections allowed during test execution" />
                                        <PolicyItem name="File Isolation" status="Active" description="Agent restricted to tenant workspace root" />
                                    </div>
                                    <Separator className="bg-gray-800" />
                                    <h3 className="text-sm font-semibold text-gray-300">Action History</h3>
                                    <div className="text-xs text-gray-500 italic text-center py-4">
                                        No historical violations detected.
                                    </div>
                                </div>
                            </TabsContent>

                            <TabsContent value="settings" className="flex-1 p-4 m-0 overflow-auto">
                                <div className="space-y-4">
                                    <h3 className="text-sm font-semibold text-gray-300">Agent Configuration</h3>
                                    <div className="space-y-3">
                                        <div>
                                            <label className="text-xs text-gray-500 mb-1 block">Execution Engine</label>
                                            <select className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200">
                                                <option>Atom Engineer (Python)</option>
                                                <option>Coding Assistant (GPT-4o)</option>
                                                <option>Safe Executor (Sandboxed)</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="text-xs text-gray-500 mb-1 block">Context Window</label>
                                            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                                <div className="h-full bg-blue-500 w-[65%]" />
                                            </div>
                                            <div className="flex justify-between mt-1 text-[10px] text-gray-500">
                                                <span>65,536 tokens</span>
                                                <span>128k total</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </TabsContent>
                        </Tabs>
                    </div>
                </ResizablePanel>
            </ResizablePanelGroup>
        </div>
    );
}

function PolicyItem({ name, status, description }: { name: string; status: string; description: string }) {
    return (
        <div className="p-2 border border-gray-800 rounded-md bg-gray-900/50">
            <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-200">{name}</span>
                <Badge variant="outline" className="text-[10px] h-4 bg-green-900/20 text-green-400 border-green-800">
                    {status}
                </Badge>
            </div>
            <p className="text-[10px] text-gray-500">{description}</p>
        </div>
    );
}

function Separator({ className }: { className?: string }) {
    return <div className={`h-[1px] ${className}`} />;
}
