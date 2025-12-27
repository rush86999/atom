import React, { useState, useEffect } from 'react';
import {
    X,
    Save,
    Info,
    Zap,
    ChevronDown,
    ChevronRight,
    Database,
    Variable,
    Code,
    Loader2,
    AlertCircle,
    Link2,
    PlusCircle
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import VariablePicker from './VariablePicker';

interface NodeConfigSidebarProps {
    selectedNode: any;
    allNodes: any[];
    onClose: () => void;
    onUpdateNode: (nodeId: string, data: any) => void;
}

const NodeConfigSidebar: React.FC<NodeConfigSidebarProps> = ({
    selectedNode,
    allNodes,
    onClose,
    onUpdateNode
}) => {
    const [loading, setLoading] = useState(false);
    const [metadata, setMetadata] = useState<any>(null);
    const [config, setConfig] = useState<any>(selectedNode?.data?.config || {});
    const [activeTab, setActiveTab] = useState<'config' | 'test'>('config');
    const [dynamicOptions, setDynamicOptions] = useState<Record<string, { options: any[], loading: boolean }>>({});
    const [connections, setConnections] = useState<any[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<string | null>(selectedNode?.data?.config?.connectionId || null);

    useEffect(() => {
        if (selectedNode?.data?.serviceId) {
            fetchMetadata(selectedNode.data.serviceId);
            fetchConnections(selectedNode.data.serviceId);
        }
        setConfig(selectedNode?.data?.config || {});
        setSelectedConnection(selectedNode?.data?.config?.connectionId || null);
    }, [selectedNode]);

    // Fetch user connections for this piece
    const fetchConnections = async (pieceId: string) => {
        try {
            // In real app, this would fetch from /api/v1/connections?pieceId=...
            // For now, mocking some connections
            const mockConnections = [
                { id: 'conn_1', name: 'My Slack Workspace', pieceId: '@activepieces/piece-slack' },
                { id: 'conn_2', name: 'Dev Workspace', pieceId: '@activepieces/piece-slack' },
                { id: 'conn_3', name: 'Personal Gmail', pieceId: '@activepieces/piece-gmail' }
            ].filter(c => c.pieceId === pieceId);
            setConnections(mockConnections);
        } catch (error) {
            console.error("Error fetching connections:", error);
        }
    };

    const fetchMetadata = async (pieceId: string) => {
        setLoading(true);
        try {
            // Updated to use the new External Integrations API
            const response = await fetch(`/api/v1/external-integrations/${encodeURIComponent(pieceId)}`);
            if (response.ok) {
                const data = await response.json();
                setMetadata(data);
            }
        } catch (error) {
            console.error("Error fetching piece metadata:", error);
        } finally {
            setLoading(false);
        }
    };

    // ... (keep fetchMetadata as is, from previous step)

    // RESTORED HANDLERS:
    const handleInputChange = (key: string, value: any) => {
        const newConfig = { ...config, [key]: value };
        setConfig(newConfig);
        onUpdateNode(selectedNode.id, { ...selectedNode.data, config: newConfig });

        // Check for dependent dynamic fields
        triggerDependentFields(key, value);
    };

    const handleConnectionChange = (connectionId: string) => {
        setSelectedConnection(connectionId);
        const newConfig = { ...config, connectionId };
        setConfig(newConfig);
        onUpdateNode(selectedNode.id, { ...selectedNode.data, config: newConfig });

        // Trigger all dynamic fields for this piece
        fetchAllDynamicFields(connectionId);
    };

    const triggerDependentFields = (changedKey: string, newValue: any) => {
        // Implementation for Activepieces "refreshers"
        // If this field is a refresher for other fields, trigger them
        if (metadata) {
            const currentAction = metadata.actions?.find((a: any) => a.name === selectedNode.data.action) ||
                metadata.triggers?.find((t: any) => t.name === selectedNode.data.action);

            if (currentAction?.props) {
                Object.entries(currentAction.props).forEach(([key, prop]: [string, any]) => {
                    if (prop.refreshers?.includes(changedKey)) {
                        fetchDynamicOptions(key, prop);
                    }
                });
            }
        }
    };

    const fetchAllDynamicFields = (connectionId: string) => {
        if (metadata) {
            const currentAction = metadata.actions?.find((a: any) => a.name === selectedNode.data.action) ||
                metadata.triggers?.find((t: any) => t.name === selectedNode.data.action);

            if (currentAction?.props) {
                Object.entries(currentAction.props).forEach(([key, prop]: [string, any]) => {
                    if (prop.type === 'DROPDOWN' && !prop.options?.options) {
                        fetchDynamicOptions(key, prop, connectionId);
                    }
                });
            }
        }
    };

    const fetchDynamicOptions = async (key: string, prop: any, connectionId?: string) => {
        setDynamicOptions(prev => ({ ...prev, [key]: { options: [], loading: true } }));
        try {
            const response = await fetch('/api/v1/integrations/dynamic-options', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pieceId: selectedNode.data.serviceId,
                    actionName: selectedNode.data.action,
                    propertyName: key,
                    connectionId: connectionId || selectedConnection,
                    config: config
                })
            });
            if (response.ok) {
                const data = await response.json();
                setDynamicOptions(prev => ({
                    ...prev,
                    [key]: { options: data.options || [], loading: false }
                }));
            }
        } catch (error) {
            console.error(`Error fetching dynamic options for ${key}:`, error);
            setDynamicOptions(prev => ({ ...prev, [key]: { options: [], loading: false } }));
        }
    };

    const renderField = (key: string, prop: any) => {
        const value = config[key] || prop.defaultValue || '';

        switch (prop.type) {
            case 'SHORT_TEXT':
            case 'TEXT': // Alias
                return (
                    <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                            <Label className="text-xs font-semibold flex items-center gap-1">
                                {prop.displayName}
                                {prop.required && <span className="text-red-500">*</span>}
                            </Label>
                            <VariablePicker
                                onSelect={(v: string) => handleInputChange(key, (value + v))}
                                trigger={<Button variant="ghost" size="icon" className="h-6 w-6 text-purple-600"><Variable className="h-3 w-3" /></Button>}
                                availableNodes={allNodes.filter(n => n.id !== selectedNode.id)}
                            />
                        </div>
                        <Input
                            value={value}
                            onChange={(e) => handleInputChange(key, e.target.value)}
                            placeholder={prop.description}
                            className="text-sm h-8"
                        />
                        {prop.description && <p className="text-[10px] text-gray-500">{prop.description}</p>}
                    </div>
                );
            case 'LONG_TEXT':
                return (
                    <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                            <Label className="text-xs font-semibold flex items-center gap-1">
                                {prop.displayName}
                                {prop.required && <span className="text-red-500">*</span>}
                            </Label>
                            <VariablePicker
                                onSelect={(v: string) => handleInputChange(key, (value + v))}
                                trigger={<Button variant="ghost" size="icon" className="h-6 w-6 text-purple-600"><Variable className="h-3 w-3" /></Button>}
                                availableNodes={allNodes.filter(n => n.id !== selectedNode.id)}
                            />
                        </div>
                        <Textarea
                            value={value}
                            onChange={(e) => handleInputChange(key, e.target.value)}
                            placeholder={prop.description}
                            className="text-sm min-h-[80px]"
                        />
                        {prop.description && <p className="text-[10px] text-gray-500">{prop.description}</p>}
                    </div>
                );
            case 'NUMBER':
                return (
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold flex items-center gap-1">
                            {prop.displayName}
                            {prop.required && <span className="text-red-500">*</span>}
                        </Label>
                        <Input
                            type="number"
                            value={value}
                            onChange={(e) => handleInputChange(key, parseFloat(e.target.value))}
                            placeholder={prop.description}
                            className="text-sm h-8"
                        />
                        {prop.description && <p className="text-[10px] text-gray-500">{prop.description}</p>}
                    </div>
                );
            case 'DROPDOWN':
            case 'STATIC_DROPDOWN': // ActivePieces type
            case 'DYNAMIC': // Dynamic dropdowns
                const dynamic = dynamicOptions[key];
                const options = prop.options?.options || dynamic?.options || [];
                const fieldLoading = dynamic?.loading || false;

                return (
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold flex items-center gap-1">
                            {prop.displayName}
                            {prop.required && <span className="text-red-500">*</span>}
                            {fieldLoading && <Loader2 className="h-3 w-3 animate-spin text-purple-600 ml-1" />}
                        </Label>
                        <Select value={value?.toString()} onValueChange={(v: string) => handleInputChange(key, v)}>
                            <SelectTrigger className="h-8 text-sm">
                                <SelectValue placeholder={prop.placeholder || (fieldLoading ? "Loading..." : "Select an option")} />
                            </SelectTrigger>
                            <SelectContent>
                                {options.map((opt: any, idx: number) => {
                                    const val = opt.value?.toString() ?? "";
                                    return (
                                        <SelectItem key={`${val}-${idx}`} value={val}>
                                            {opt.label}
                                        </SelectItem>
                                    );
                                })}
                            </SelectContent>
                        </Select>
                        {prop.description && <p className="text-[10px] text-gray-500">{prop.description}</p>}
                    </div>
                );
            case 'MARKDOWN':
                return (
                    <div className="p-3 bg-blue-50/30 rounded border border-blue-100 text-[11px] text-blue-900 leading-relaxed prose prose-sm max-w-none">
                        <div dangerouslySetInnerHTML={{ __html: prop.description?.replace(/\n/g, '<br/>') || '' }} />
                    </div>
                );
            case 'CHECKBOX':
                return (
                    <div className="flex items-center justify-between py-2">
                        <div className="space-y-0.5">
                            <Label className="text-xs font-semibold">{prop.displayName}</Label>
                            {prop.description && <p className="text-[10px] text-gray-500">{prop.description}</p>}
                        </div>
                        <Switch
                            checked={!!value}
                            onCheckedChange={(v: boolean) => handleInputChange(key, v)}
                        />
                    </div>
                );
            case 'ARRAY':
                // Simple array implementation (comma separated for now, could be better)
                return (
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold flex items-center gap-1">
                            {prop.displayName} (List)
                            {prop.required && <span className="text-red-500">*</span>}
                        </Label>
                        <Textarea
                            value={Array.isArray(value) ? value.join(', ') : value}
                            onChange={(e) => handleInputChange(key, e.target.value.split(',').map((s: string) => s.trim()))}
                            placeholder="Item 1, Item 2..."
                            className="text-sm min-h-[60px]"
                        />
                        <p className="text-[10px] text-gray-500">Comma-separated values</p>
                    </div>
                );
            case 'OBJECT':
            case 'JSON_OBJECT':
                return (
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold flex items-center gap-1">
                            {prop.displayName} (JSON)
                            {prop.required && <span className="text-red-500">*</span>}
                        </Label>
                        <Textarea
                            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : value}
                            onChange={(e) => {
                                try {
                                    handleInputChange(key, JSON.parse(e.target.value));
                                } catch (err) {
                                    // Handle invalid JSON gracefully or just store string until valid
                                    // For now, updating metadata only on valid JSON might be safer or storing string
                                }
                            }}
                            placeholder='{ "key": "value" }'
                            className="text-sm min-h-[100px] font-mono"
                        />
                    </div>
                );
            default:
                // Fallback for unknown types - treat as short text
                return (
                    <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                            <Label className="text-xs font-semibold flex items-center gap-1">
                                {prop.displayName} <span className="text-gray-400 font-normal">({prop.type})</span>
                                {prop.required && <span className="text-red-500">*</span>}
                            </Label>
                        </div>
                        <Input
                            value={value}
                            onChange={(e) => handleInputChange(key, e.target.value)}
                            placeholder={prop.description}
                            className="text-sm h-8"
                        />
                    </div>
                );
        }
    };

    if (!selectedNode) return null;

    const currentAction = metadata?.actions?.find((a: any) => a.name === selectedNode.data.action) ||
        metadata?.triggers?.find((t: any) => t.name === selectedNode.data.action);

    return (
        <div className="w-96 border-l bg-white flex flex-col h-full shadow-2xl relative z-50 animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="p-4 border-b flex items-center justify-between bg-gray-50/50">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-white rounded border shadow-sm">
                        {metadata?.icon ? (
                            <img src={metadata.icon} alt={metadata.name} className="w-5 h-5 object-contain" />
                        ) : (
                            <Zap className="w-5 h-5 text-purple-600" />
                        )}
                    </div>
                    <div>
                        <h3 className="font-bold text-sm text-gray-900">{metadata?.name || selectedNode.data.service}</h3>
                        <p className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">{selectedNode.type}</p>
                    </div>
                </div>
                <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 rounded-full">
                    <X className="h-4 w-4" />
                </Button>
            </div>

            {/* Sidebar Content */}
            <ScrollArea className="flex-1">
                <div className="p-5 space-y-6">
                    {/* Connection Selection */}
                    {metadata?.auth && (
                        <div className="space-y-3 p-4 bg-gray-50/50 rounded-xl border border-gray-100">
                            <div className="flex items-center justify-between">
                                <Label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Connection</Label>
                                <Badge variant="outline" className="text-[9px] h-4 bg-white font-mono text-purple-600 border-purple-100">
                                    Required
                                </Badge>
                            </div>
                            <div className="flex gap-2">
                                <Select value={selectedConnection || ""} onValueChange={handleConnectionChange}>
                                    <SelectTrigger className="h-9 text-sm bg-white border-gray-200">
                                        <SelectValue placeholder="Select a connection" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {connections.map(conn => (
                                            <SelectItem key={conn.id} value={conn.id}>
                                                <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 bg-green-500 rounded-full" />
                                                    {conn.name}
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button variant="outline" size="icon" className="h-9 w-9 shrink-0 bg-white border-gray-200 hover:bg-purple-50 hover:text-purple-600 hover:border-purple-200">
                                    <PlusCircle className="h-4 w-4" />
                                </Button>
                            </div>
                            <p className="text-[10px] text-gray-500 flex items-center gap-1">
                                <Link2 className="h-3 w-3" />
                                Manage your {metadata.name} authentication
                            </p>
                        </div>
                    )}

                    {/* Action Selection Info */}
                    <div className="p-3 bg-purple-50/50 rounded-lg border border-purple-100 flex gap-3">
                        <div className="bg-purple-100 p-2 rounded-full h-fit">
                            <Zap className="h-4 w-4 text-purple-600" />
                        </div>
                        <div className="space-y-1">
                            <h4 className="text-xs font-bold text-purple-900">{currentAction?.displayName || selectedNode.data.label}</h4>
                            <p className="text-[10px] text-purple-700 leading-relaxed">
                                {currentAction?.description || selectedNode.data.description || "Configure the parameters for this step."}
                            </p>
                        </div>
                    </div>

                    {/* Form Fields */}
                    <div className="space-y-5">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest px-1">
                            <span>Configuration</span>
                            <div className="h-[1px] flex-1 bg-gray-100"></div>
                        </div>

                        {loading ? (
                            <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-3">
                                <Loader2 className="h-6 w-6 animate-spin" />
                                <span className="text-xs font-medium">Loading parameters...</span>
                            </div>
                        ) : currentAction?.props ? (
                            Object.entries(currentAction.props).map(([key, prop]) => (
                                <div key={key}>
                                    {renderField(key, prop)}
                                </div>
                            ))
                        ) : (
                            <div className="flex flex-col items-center justify-center py-8 text-center bg-gray-50 rounded-lg border border-dashed border-gray-200">
                                <AlertCircle className="h-5 w-5 text-gray-400 mb-2" />
                                <p className="text-xs text-gray-500 font-medium px-4">
                                    No configurable parameters found for this {selectedNode.type}.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </ScrollArea>

            {/* Footer */}
            <div className="p-4 border-t bg-gray-50/80 mt-auto">
                <div className="flex gap-2">
                    <Button variant="outline" className="flex-1 h-9 text-xs" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button className="flex-1 h-9 text-xs bg-purple-600 hover:bg-purple-700" onClick={onClose}>
                        <Save className="h-3 w-3 mr-1.5" />
                        Save Step
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default NodeConfigSidebar;
