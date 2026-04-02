'use client';

import { useState, useEffect, useRef } from 'react';
import { Box, ExternalLink, RefreshCw, Maximize2, Minimize2, Settings, Zap, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { GuidancePanel, AgentAction } from './GuidancePanel';
import { useCanvasGuidance } from '@/hooks/useCanvasGuidance';
import { UniversalDocumentViewer } from './UniversalDocumentViewer';
import { useEffect as useAppEffect } from 'react';
import { ActionExecutor } from './ActionExecutor';
import { EntityForm } from './EntityForm';
import { getAgentComponents, UIComponent } from '@/lib/api/ui-component-client';

interface AppConfig {
    url?: string;
    name?: string;
    icon?: string;
    permissions?: string[];
}

interface AppCanvasProps {
    canvasId: string;
    agentId?: string;
}

export function AppCanvas({ canvasId, agentId }: AppCanvasProps) {
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

    const [appConfig, setAppConfig] = useState<AppConfig>({});
    const [isConfigured, setIsConfigured] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Dynamic component loading state
    const [agentComponents, setAgentComponents] = useState<UIComponent[]>([]);
    const [isLoadingComponents, setIsLoadingComponents] = useState(false);
    const [componentError, setComponentError] = useState<string | null>(null);

    const iframeRef = useRef<HTMLIFrameElement>(null);

    /**
     * Fetch agent components on mount if agentId is provided
     */
    useEffect(() => {
        const fetchAgentComponents = async () => {
            if (!agentId) {
                setAgentComponents([]);
                return;
            }

            try {
                setIsLoadingComponents(true);
                setComponentError(null);
                const response = await getAgentComponents(agentId);
                setAgentComponents(response.components);
            } catch (err: any) {
                setComponentError(err.message || 'Failed to load components');
                toast.error(`Failed to load agent components: ${err.message}`);
            } finally {
                setIsLoadingComponents(false);
            }
        };

        fetchAgentComponents();
    }, [agentId]);

    /**
     * Resolve component for current action
     */
    const resolveActionComponent = () => {
        if (!currentAction) {
            return null;
        }

        // Find component matching current action type
        const matchingComponent = agentComponents.find(
            (comp) => comp.capability_name === currentAction.type
        );

        return matchingComponent || null;
    };

    /**
     * Execute action via ActionExecutor
     */
    const handleExecuteAction = async (data: Record<string, any>) => {
        try {
            // For now, just approve the action with data
            // TODO: Update useCanvasGuidance to support action data
            await handleApprove();
        } catch (err: any) {
            throw new Error(err.message || 'Execution failed');
        }
    };

    const loadApp = async () => {
        setIsLoading(true);
        setError(null);

        try {
            if (!appConfig.url) {
                throw new Error('App URL is required');
            }

            // Validate URL
            new URL(appConfig.url);

            setIsConfigured(true);
            toast.success(`Loaded ${appConfig.name || 'application'}`);
        } catch (err: any) {
            setError(err.message || 'Invalid URL');
            toast.error(err.message || 'Failed to load application');
        } finally {
            setIsLoading(false);
        }
    };

    const refreshApp = () => {
        if (iframeRef.current) {
            iframeRef.current.src = iframeRef.current.src;
            toast.success('Application refreshed');
        }
    };

    const handleConfigSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        loadApp();
    };

    if (!isConfigured) {
        return (
            <div className={`h-full flex flex-col bg-gray-950 text-white ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
                {/* Header */}
                <div className="border-b border-gray-800 p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Box className="w-6 h-6 text-purple-400" />
                        <div>
                            <h2 className="text-lg font-semibold">App Canvas</h2>
                            <p className="text-xs text-gray-400">Embed external applications</p>
                        </div>
                    </div>
                </div>

                {/* Configuration Form */}
                <div className="flex-1 flex items-center justify-center p-8">
                    <div className="w-full max-w-md bg-gray-900 rounded-lg border border-gray-800 p-6">
                        <div className="flex items-center gap-3 mb-6">
                            <div className="p-2 bg-purple-500/20 rounded-lg">
                                <Box className="w-6 h-6 text-purple-400" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold">Configure Application</h3>
                                <p className="text-sm text-gray-400">Enter the details of the app to embed</p>
                            </div>
                        </div>

                        <form onSubmit={handleConfigSubmit} className="space-y-4">
                            <div>
                                <Label htmlFor="appName">App Name</Label>
                                <Input
                                    id="appName"
                                    value={appConfig.name || ''}
                                    onChange={(e) => setAppConfig({ ...appConfig, name: e.target.value })}
                                    placeholder="My Application"
                                    className="bg-gray-800 border-gray-700"
                                />
                            </div>

                            <div>
                                <Label htmlFor="appUrl">App URL *</Label>
                                <Input
                                    id="appUrl"
                                    value={appConfig.url || ''}
                                    onChange={(e) => setAppConfig({ ...appConfig, url: e.target.value })}
                                    placeholder="https://example.com"
                                    required
                                    className="bg-gray-800 border-gray-700"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    The URL must support being embedded in an iframe
                                </p>
                            </div>

                            <div>
                                <Label htmlFor="appIcon">Icon URL (optional)</Label>
                                <Input
                                    id="appIcon"
                                    value={appConfig.icon || ''}
                                    onChange={(e) => setAppConfig({ ...appConfig, icon: e.target.value })}
                                    placeholder="https://example.com/icon.png"
                                    className="bg-gray-800 border-gray-700"
                                />
                            </div>

                            {error && (
                                <div className="p-3 bg-red-500/10 border border-red-500/50 rounded-lg flex items-start gap-2">
                                    <AlertCircle className="w-4 h-4 text-red-400 mt-0.5" />
                                    <span className="text-sm text-red-400">{error}</span>
                                </div>
                            )}

                            <div className="flex gap-2">
                                <Button
                                    type="submit"
                                    disabled={isLoading || !appConfig.url}
                                    className="flex-1"
                                >
                                    {isLoading ? (
                                        <>
                                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                            Loading...
                                        </>
                                    ) : (
                                        <>
                                            <Zap className="w-4 h-4 mr-2" />
                                            Load Application
                                        </>
                                    )}
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setAppConfig({})}
                                >
                                    Clear
                                </Button>
                            </div>
                        </form>

                        {/* Examples */}
                        <div className="mt-6 pt-6 border-t border-gray-800">
                            <p className="text-sm text-gray-400 mb-3">Quick Examples:</p>
                            <div className="space-y-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="w-full justify-start"
                                    onClick={() => setAppConfig({
                                        name: 'Wikipedia',
                                        url: 'https://en.wikipedia.org/wiki/Special:Random',
                                    })}
                                >
                                    <ExternalLink className="w-4 h-4 mr-2" />
                                    Wikipedia (Random Article)
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="w-full justify-start"
                                    onClick={() => setAppConfig({
                                        name: 'Example App',
                                        url: 'https://example.com',
                                    })}
                                >
                                    <ExternalLink className="w-4 h-4 mr-2" />
                                    Example.com
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`h-full flex flex-col bg-gray-950 text-white ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
            {/* Header */}
            <div className="border-b border-gray-800 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    {appConfig.icon ? (
                        <img src={appConfig.icon} alt="" className="w-6 h-6 rounded" />
                    ) : (
                        <Box className="w-6 h-6 text-purple-400" />
                    )}
                    <div>
                        <h2 className="text-lg font-semibold">{appConfig.name || 'Application'}</h2>
                        <p className="text-xs text-gray-400 truncate max-w-md">{appConfig.url}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {/* Action-Specific UI Controls - Created on the fly */}
                    {currentAction?.type === 'document_generate' && (
                        <Button 
                            variant="outline" 
                            size="sm" 
                            className="bg-purple-500/10 border-purple-500/20 text-purple-400 hover:bg-purple-500/20"
                            onClick={() => setIsConfigured(false)}
                        >
                            <Box className="w-4 h-4 mr-2" />
                            Switch to App View
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={refreshApp}
                        title="Refresh"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setIsFullscreen(!isFullscreen)}
                        title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
                    >
                        {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                            setIsConfigured(false);
                            setAppConfig({});
                        }}
                        title="Configure"
                    >
                        <Settings className="w-5 h-5" />
                    </Button>
                </div>
            </div>

            {/* Main Content Area - Dynamic Resolution */}
            <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
                <div className="flex-1 relative overflow-hidden bg-gray-900">
                    {/* Loading components state */}
                    {isLoadingComponents && agentId && (
                        <div className="absolute inset-0 flex items-center justify-center bg-gray-950/50 backdrop-blur-sm">
                            <div className="text-center space-y-4">
                                <Loader2 className="w-8 h-8 animate-spin mx-auto text-purple-500" />
                                <p className="text-gray-400">Loading agent components...</p>
                            </div>
                        </div>
                    )}

                    {/* Component loading error */}
                    {componentError && (
                        <div className="absolute inset-0 flex items-center justify-center bg-gray-950">
                            <div className="text-center space-y-4 p-8">
                                <AlertCircle className="w-12 h-12 mx-auto text-red-500" />
                                <div>
                                    <h3 className="text-lg font-semibold text-white">Failed to Load Components</h3>
                                    <p className="text-sm text-gray-400 mt-2">{componentError}</p>
                                </div>
                                <Button
                                    variant="outline"
                                    onClick={() => window.location.reload()}
                                >
                                    Retry
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Dynamic component resolution */}
                    {(() => {
                        const resolvedComponent = resolveActionComponent();

                        // 1. Document generation (specialized component)
                        if (currentAction?.type === 'document_generate') {
                            return (
                                <UniversalDocumentViewer
                                    payload={{
                                        document_id: currentAction.id,
                                        content: (currentAction.data as any)?.rendered_content || 'Generating preview...',
                                        format: (currentAction.data as any)?.target_format || 'pdf',
                                        metadata: {
                                            generated_at: new Date().toISOString(),
                                            tenant_id: 'current_tenant'
                                        }
                                    }}
                                    onApprove={handleApprove}
                                    onReject={(id, reason) => handleSkip()}
                                    onEdit={(id, data) => handleEdit(data)}
                                    onClose={() => setIsConfigured(false)}
                                />
                            );
                        }

                        // 2. Generic Action Executor (fallback for any action)
                        if (currentAction && resolvedComponent?.is_generic) {
                            return (
                                <ActionExecutor
                                    capabilityName={currentAction.type}
                                    toolSchema={(currentAction.data as any)?.tool_schema || { properties: {} }}
                                    onExecute={handleExecuteAction}
                                    executionResult={(currentAction.data as any)?.result}
                                    isExecuting={false}
                                />
                            );
                        }

                        // 3. Entity Form (for entity CRUD operations)
                        if (currentAction?.type === 'entity_create' || currentAction?.type === 'entity_update') {
                            return (
                                <EntityForm
                                    entityTypeSlug={(currentAction.data as any)?.entity_type_slug || ''}
                                    entityId={(currentAction.data as any)?.entity_id}
                                    onSave={async (data) => {
                                        await handleExecuteAction(data);
                                    }}
                                    onCancel={() => handleSkip()}
                                />
                            );
                        }

                        // 4. Standard Iframe View (Legacy/External Apps)
                        return (
                            <iframe
                                ref={iframeRef}
                                src={appConfig.url}
                                className={`w-full h-full border-0 transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
                                title={appConfig.name || 'Application'}
                                sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
                            />
                        );
                    })()}
                    
                    {isLoading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-gray-950/50 backdrop-blur-sm">
                            <RefreshCw className="w-8 h-8 text-purple-500 animate-spin" />
                        </div>
                    )}
                </div>

                {/* Guidance Panel */}
                {wsConnected && (
                    <div className="w-80 border-l border-gray-800 bg-gray-950/50 backdrop-blur-md">
                        <GuidancePanel
                            currentAction={currentAction}
                            actionHistory={actionHistory}
                            onApprove={handleApprove}
                            onEdit={handleEdit}
                            onSkip={handleSkip}
                            onCancel={handleCancel}
                            onGuidance={handleGuidance}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
