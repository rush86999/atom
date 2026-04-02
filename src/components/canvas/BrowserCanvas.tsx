'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
    Globe,
    ArrowLeft,
    ArrowRight,
    RotateCw,
    X,
    AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';
import { GuidancePanel, AgentAction } from './GuidancePanel';
import { useMediaQuery } from '@/hooks/use-media-query';
import { useAccessibilityMirror } from '@/lib/canvas/accessibility';

interface BrowserSession {
    id: string;
    current_url: string;
    page_title: string;
    screenshot: string | null;  // base64 encoded
}

interface BoundingBox {
    x: number;
    y: number;
    width: number;
    height: number;
}

interface BrowserCanvasProps {
    canvasId: string;
}

import { useCanvasGuidance } from '@/hooks/useCanvasGuidance';

export function BrowserCanvas({ canvasId }: BrowserCanvasProps) {
    const {
        currentAction,
        actionHistory,
        wsConnected,
        handleApprove,
        handleEdit,
        handleSkip,
        handleCancel,
        handleGuidance
    } = useCanvasGuidance(canvasId);

    const [session, setSession] = useState<BrowserSession | null>(null);
    const [screenshot, setScreenshot] = useState<string | null>(null);
    const [urlInput, setUrlInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [highlightedElement, setHighlightedElement] = useState<BoundingBox | null>(null);

    // Execution mode state
    const [executionMode, setExecutionMode] = useState<'cloud' | 'desktop'>('cloud');
    const [isTauriApp, setIsTauriApp] = useState(false);

    const isMobile = useMediaQuery('(max-width: 768px)');

    // Accessibility mirror for screen readers and AI agents
    const accessibilityMirror = useAccessibilityMirror({
        canvasId,
        canvasType: 'browser',
        getContent: () => {
            const lines: string[] = [];
            if (session?.current_url) lines.push(`URL: ${session.current_url}`);
            if (session?.page_title) lines.push(`Title: ${session.page_title}`);
            if (session?.screenshot) {
                lines.push('Screenshot available (visual content)');
            }
            if (highlightedElement) {
                lines.push(`Highlighted element at (${highlightedElement.x}, ${highlightedElement.y})`);
            }
            return lines.length > 0 ? lines : ['No page loaded'];
        },
    });


    // Detect Tauri environment
    useEffect(() => {
        const checkTauri = () => {
            try {
                if (typeof window !== 'undefined' && window.__TAURI__) {
                    setIsTauriApp(true);
                    console.log('Tauri environment detected - desktop mode available');
                }
            } catch (error) {
                console.log('Not a Tauri app - cloud mode only');
            }
        };
        checkTauri();
    }, []);

    // Create browser session
    const createSession = async (initialUrl: string = 'about:blank') => {
        try {
            setLoading(true);
            const res = await fetch(`/api/canvas/${canvasId}/browser/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    initial_url: initialUrl,
                    execution_mode: executionMode
                })
            });

            if (res.ok) {
                const data = await res.json();
                setSession({
                    id: data.session_id,
                    current_url: data.current_url,
                    page_title: data.page_title,
                    screenshot: data.screenshot
                });
                setScreenshot(data.screenshot);
                setUrlInput(data.current_url);

                if (executionMode === 'desktop') {
                    toast.success('Browser session created - Launch via Tauri app');
                    toast.info('Desktop mode: Browser will open on your machine');
                } else {
                    toast.success('Browser session created on cloud');
                }
            } else {
                const error = await res.json();
                toast.error(error.detail || 'Failed to create browser session');
            }
        } catch (error) {
            console.error('Failed to create session:', error);
            toast.error('Failed to create browser session');
        } finally {
            setLoading(false);
        }
    };

    // Navigate to URL
    const navigate = async (url: string) => {
        if (!session || !url.trim()) return;

        try {
            setLoading(true);
            const res = await fetch(
                `/api/canvas/${canvasId}/browser/${session.id}/navigate`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, user_approved_sensitive: false })
                }
            );

            if (res.ok) {
                const data = await res.json();

                if (data.success) {
                    setSession(prev => prev ? {
                        ...prev,
                        current_url: data.url,
                        page_title: data.title
                    } : null);
                    setScreenshot(data.screenshot);
                    setUrlInput(data.url);
                    toast.success(`Navigated to ${data.title || data.url}`);
                } else {
                    toast.error(data.error_message || 'Navigation failed');
                }
            } else {
                const error = await res.json();
                toast.error(error.detail || 'Navigation failed');
            }
        } catch (error) {
            console.error('Failed to navigate:', error);
            toast.error('Navigation failed');
        } finally {
            setLoading(false);
        }
    };

    // Execute browser action
    const executeAction = async (actionType: string, selector: string, value?: string) => {
        if (!session) return;

        try {
            setLoading(true);
            const res = await fetch(
                `/api/canvas/${canvasId}/browser/${session.id}/action`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: {
                            type: actionType,
                            selector,
                            value
                        }
                    })
                }
            );

            if (res.ok) {
                const data = await res.json();

                if (data.success) {
                    setScreenshot(data.screenshot);
                    toast.success(`Action '${actionType}' executed`);
                } else {
                    toast.error(data.error_message || 'Action failed');
                }
            } else {
                const error = await res.json();
                toast.error(error.detail || 'Action failed');
            }
        } catch (error) {
            console.error('Failed to execute action:', error);
            toast.error('Action failed');
        } finally {
            setLoading(false);
        }
    };



    return (
        <div className={`flex h-full bg-gray-950 ${isMobile ? 'flex-col' : ''}`}>
            {/* Browser Area */}
            <div className="flex-1 flex flex-col">
                {/* Header */}
                <div className="bg-gray-900 border-b border-gray-800 p-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Globe className="w-5 h-5 text-blue-400" />
                        <span className="text-white font-medium">Browser</span>

                        {/* Mode Selector */}
                        <select
                            value={executionMode}
                            onChange={(e) => setExecutionMode(e.target.value as 'cloud' | 'desktop')}
                            disabled={!!session || loading}
                            className="bg-gray-800 border border-gray-700 text-white text-sm rounded px-2 py-1 disabled:opacity-50"
                        >
                            <option value="cloud">☁️ Cloud</option>
                            <option value="desktop" disabled={!isTauriApp}>
                                💻 Desktop {!isTauriApp && '(Tauri only)'}
                            </option>
                        </select>

                        {/* Status Badges */}
                        {wsConnected && (
                            <Badge className="bg-green-600 text-xs">Live</Badge>
                        )}
                        {session && (
                            <Badge className={executionMode === 'cloud' ? 'bg-blue-600 text-xs' : 'bg-purple-600 text-xs'}>
                                {executionMode === 'cloud' ? 'Cloud' : 'Desktop'}
                            </Badge>
                        )}
                    </div>
                </div>

                {/* Navigation Bar */}
                {session && (
                    <div className="bg-gray-900 border-b border-gray-800 p-3 flex items-center gap-2">
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={loading}
                            className="border-gray-700"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={loading}
                            className="border-gray-700"
                        >
                            <ArrowRight className="w-4 h-4" />
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate(session.current_url)}
                            disabled={loading}
                            className="border-gray-700"
                        >
                            <RotateCw className="w-4 h-4" />
                        </Button>

                        <Input
                            value={urlInput}
                            onChange={(e) => setUrlInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && navigate(urlInput)}
                            placeholder="Enter URL..."
                            disabled={loading}
                            className="flex-1 bg-black border-gray-700 text-white"
                        />

                        <Button
                            onClick={() => navigate(urlInput)}
                            disabled={loading || !urlInput.trim()}
                            className="bg-blue-600 hover:bg-blue-500"
                        >
                            Go
                        </Button>
                    </div>
                )}

                {/* Browser Viewport */}
                <div className="flex-1 bg-black overflow-auto p-4">
                    {!session ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-center text-gray-500">
                                <Globe className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p className="mb-4">No browser session</p>
                                <Button onClick={() => createSession()}>
                                    Create Browser Session
                                </Button>
                            </div>
                        </div>
                    ) : screenshot ? (
                        <div className="relative inline-block">
                            {/* Screenshot */}
                            <img
                                src={`data:image/png;base64,${screenshot}`}
                                alt="Browser screenshot"
                                className="max-w-full border border-gray-800 rounded"
                            />

                            {/* Element Highlight Overlay */}
                            {highlightedElement && (
                                <div
                                    className="absolute border-2 border-yellow-400 bg-yellow-400/10 rounded animate-pulse"
                                    style={{
                                        left: `${highlightedElement.x}px`,
                                        top: `${highlightedElement.y}px`,
                                        width: `${highlightedElement.width}px`,
                                        height: `${highlightedElement.height}px`
                                    }}
                                />
                            )}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full text-gray-500">
                            <div className="text-center">
                                <RotateCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
                                <p>Loading page...</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Guidance Panel */}
            <GuidancePanel
                currentAction={currentAction}
                onApprove={handleApprove}
                onEdit={handleEdit}
                onSkip={handleSkip}
                onCancel={handleCancel}
                onGuidance={handleGuidance}
                actionHistory={actionHistory}
                disabled={loading}
            />
        </div>
    );
}
