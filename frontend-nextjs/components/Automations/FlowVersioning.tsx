'use client';

import React, { useState, useMemo } from 'react';
import {
    History, GitBranch, Save, RefreshCw, GitCompare, ChevronRight, Check, X, AlertCircle,
    GitCommit, CheckCircle, Clock, User, Eye, RotateCcw
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// Version definition
export interface FlowVersion {
    id: string;
    version: string;
    createdAt: string;
    createdBy: string;
    message: string;
    status: 'draft' | 'published' | 'archived';
    changes: {
        nodesAdded: number;
        nodesModified: number;
        nodesRemoved: number;
    };
    nodeCount: number;
    edgeCount: number;
    isCurrent?: boolean;
}

// Sample version history
const SAMPLE_VERSIONS: FlowVersion[] = [
    {
        id: 'v8',
        version: '2.3.0',
        createdAt: '2024-01-16T14:30:00Z',
        createdBy: 'You',
        message: 'Added AI enrichment step and Slack notification',
        status: 'published',
        changes: { nodesAdded: 2, nodesModified: 1, nodesRemoved: 0 },
        nodeCount: 8,
        edgeCount: 7,
        isCurrent: true,
    },
    {
        id: 'v7',
        version: '2.2.1',
        createdAt: '2024-01-15T10:15:00Z',
        createdBy: 'You',
        message: 'Fixed conditional logic for lead scoring',
        status: 'archived',
        changes: { nodesAdded: 0, nodesModified: 2, nodesRemoved: 0 },
        nodeCount: 6,
        edgeCount: 5,
    },
    {
        id: 'v6',
        version: '2.2.0',
        createdAt: '2024-01-14T16:45:00Z',
        createdBy: 'You',
        message: 'Added lead scoring condition',
        status: 'archived',
        changes: { nodesAdded: 1, nodesModified: 1, nodesRemoved: 0 },
        nodeCount: 6,
        edgeCount: 5,
    },
    {
        id: 'v5',
        version: '2.1.0',
        createdAt: '2024-01-12T09:30:00Z',
        createdBy: 'Team Member',
        message: 'Integrated HubSpot trigger',
        status: 'archived',
        changes: { nodesAdded: 1, nodesModified: 0, nodesRemoved: 1 },
        nodeCount: 5,
        edgeCount: 4,
    },
    {
        id: 'v4',
        version: '2.0.0',
        createdAt: '2024-01-10T11:00:00Z',
        createdBy: 'You',
        message: 'Major refactor - simplified workflow',
        status: 'archived',
        changes: { nodesAdded: 2, nodesModified: 3, nodesRemoved: 4 },
        nodeCount: 5,
        edgeCount: 4,
    },
    {
        id: 'v3',
        version: '1.2.0',
        createdAt: '2024-01-08T14:20:00Z',
        createdBy: 'You',
        message: 'Added email notification step',
        status: 'archived',
        changes: { nodesAdded: 1, nodesModified: 0, nodesRemoved: 0 },
        nodeCount: 7,
        edgeCount: 6,
    },
    {
        id: 'v2',
        version: '1.1.0',
        createdAt: '2024-01-05T10:00:00Z',
        createdBy: 'You',
        message: 'Updated API endpoint configuration',
        status: 'archived',
        changes: { nodesAdded: 0, nodesModified: 1, nodesRemoved: 0 },
        nodeCount: 6,
        edgeCount: 5,
    },
    {
        id: 'v1',
        version: '1.0.0',
        createdAt: '2024-01-03T09:00:00Z',
        createdBy: 'You',
        message: 'Initial version',
        status: 'archived',
        changes: { nodesAdded: 6, nodesModified: 0, nodesRemoved: 0 },
        nodeCount: 6,
        edgeCount: 5,
    },
];

interface FlowVersioningProps {
    flowId?: string;
    flowName?: string;
    onRestoreVersion?: (version: FlowVersion) => void;
    onViewVersion?: (version: FlowVersion) => void;
    onCompareVersions?: (v1: FlowVersion, v2: FlowVersion) => void;
    className?: string;
}

const FlowVersioning: React.FC<FlowVersioningProps> = ({
    flowId,
    flowName = 'Lead Enrichment Flow',
    onRestoreVersion,
    onViewVersion,
    onCompareVersions,
    className
}) => {
    const [versions] = useState<FlowVersion[]>(SAMPLE_VERSIONS);
    const [selectedVersion, setSelectedVersion] = useState<FlowVersion | null>(null);
    const [compareMode, setCompareMode] = useState(false);
    const [compareWith, setCompareWith] = useState<FlowVersion | null>(null);

    const currentVersion = versions.find(v => v.isCurrent);

    const handleRestore = (version: FlowVersion) => {
        if (confirm(`Restore to version ${version.version}? This will create a new version.`)) {
            onRestoreVersion?.(version);
        }
    };

    const handleCompare = (version: FlowVersion) => {
        if (!compareMode) {
            setCompareMode(true);
            setCompareWith(version);
        } else if (compareWith && compareWith.id !== version.id) {
            onCompareVersions?.(compareWith, version);
            setCompareMode(false);
            setCompareWith(null);
        }
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getChangeSummary = (changes: FlowVersion['changes']) => {
        const parts = [];
        if (changes.nodesAdded > 0) parts.push(`+${changes.nodesAdded}`);
        if (changes.nodesModified > 0) parts.push(`~${changes.nodesModified}`);
        if (changes.nodesRemoved > 0) parts.push(`-${changes.nodesRemoved}`);
        return parts.join(' ');
    };

    return (
        <div className={cn("flex h-full bg-gray-50", className)}>
            {/* Version List */}
            <div className="w-80 border-r bg-white flex flex-col">
                <div className="p-4 border-b">
                    <div className="flex items-center gap-2 mb-2">
                        <GitBranch className="w-5 h-5 text-violet-600" />
                        <h3 className="font-bold">Version History</h3>
                    </div>
                    <p className="text-sm text-gray-500">{flowName}</p>
                    <p className="text-xs text-gray-400 mt-1">{versions.length} versions</p>
                </div>

                {compareMode && (
                    <div className="p-3 bg-blue-50 border-b border-blue-100">
                        <p className="text-sm text-blue-700">
                            <GitCompare className="w-4 h-4 inline mr-1" />
                            Select another version to compare with v{compareWith?.version}
                        </p>
                        <Button
                            size="sm"
                            variant="ghost"
                            className="mt-1 text-xs"
                            onClick={() => { setCompareMode(false); setCompareWith(null); }}
                        >
                            Cancel
                        </Button>
                    </div>
                )}

                <ScrollArea className="flex-1">
                    <div className="p-2">
                        {versions.map((version, idx) => (
                            <button
                                key={version.id}
                                onClick={() => setSelectedVersion(version)}
                                className={cn(
                                    "w-full text-left p-3 rounded-lg mb-1 transition-colors relative",
                                    selectedVersion?.id === version.id
                                        ? "bg-violet-100 text-violet-900"
                                        : "hover:bg-gray-100",
                                    compareWith?.id === version.id && "ring-2 ring-blue-400"
                                )}
                            >
                                {/* Timeline connector */}
                                {idx < versions.length - 1 && (
                                    <div className="absolute left-[22px] top-[40px] bottom-[-8px] w-0.5 bg-gray-200" />
                                )}

                                <div className="flex items-start gap-3">
                                    <div className={cn(
                                        "w-8 h-8 rounded-full flex items-center justify-center relative z-10",
                                        version.isCurrent
                                            ? "bg-violet-600 text-white"
                                            : "bg-gray-200 text-gray-600"
                                    )}>
                                        <GitCommit className="w-4 h-4" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono font-semibold text-sm">
                                                v{version.version}
                                            </span>
                                            {version.isCurrent && (
                                                <Badge className="bg-green-100 text-green-700 text-[9px]">
                                                    Current
                                                </Badge>
                                            )}
                                            {version.status === 'draft' && (
                                                <Badge variant="outline" className="text-[9px]">
                                                    Draft
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-600 truncate">
                                            {version.message}
                                        </p>
                                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                                            <span>{formatDate(version.createdAt)}</span>
                                            <span>•</span>
                                            <span>{version.createdBy}</span>
                                        </div>
                                        <div className="mt-1">
                                            <span className={cn(
                                                "text-xs font-mono",
                                                version.changes.nodesAdded > 0 && "text-green-600",
                                                version.changes.nodesRemoved > 0 && !version.changes.nodesAdded && "text-red-600"
                                            )}>
                                                {getChangeSummary(version.changes)} nodes
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                </ScrollArea>
            </div>

            {/* Version Details */}
            <div className="flex-1 flex flex-col">
                {selectedVersion ? (
                    <>
                        <div className="p-6 border-b bg-white">
                            <div className="flex justify-between items-start">
                                <div>
                                    <div className="flex items-center gap-3 mb-2">
                                        <h2 className="text-2xl font-bold font-mono">
                                            v{selectedVersion.version}
                                        </h2>
                                        {selectedVersion.isCurrent && (
                                            <Badge className="bg-green-100 text-green-700">
                                                <CheckCircle className="w-3 h-3 mr-1" />
                                                Current Version
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-gray-600">{selectedVersion.message}</p>
                                    <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                                        <span className="flex items-center gap-1">
                                            <Clock className="w-4 h-4" />
                                            {formatDate(selectedVersion.createdAt)}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <User className="w-4 h-4" />
                                            {selectedVersion.createdBy}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleCompare(selectedVersion)}
                                    >
                                        <GitCompare className="w-4 h-4 mr-1" />
                                        Compare
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => onViewVersion?.(selectedVersion)}
                                    >
                                        <Eye className="w-4 h-4 mr-1" />
                                        View
                                    </Button>
                                    {!selectedVersion.isCurrent && (
                                        <Button
                                            size="sm"
                                            onClick={() => handleRestore(selectedVersion)}
                                        >
                                            <RotateCcw className="w-4 h-4 mr-1" />
                                            Restore
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="p-6 flex-1 overflow-auto">
                            {/* Changes Summary */}
                            <Card className="mb-6">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-base">Changes in this Version</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="p-4 bg-green-50 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-green-600">
                                                +{selectedVersion.changes.nodesAdded}
                                            </div>
                                            <div className="text-sm text-green-700">Nodes Added</div>
                                        </div>
                                        <div className="p-4 bg-blue-50 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-blue-600">
                                                ~{selectedVersion.changes.nodesModified}
                                            </div>
                                            <div className="text-sm text-blue-700">Nodes Modified</div>
                                        </div>
                                        <div className="p-4 bg-red-50 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-red-600">
                                                -{selectedVersion.changes.nodesRemoved}
                                            </div>
                                            <div className="text-sm text-red-700">Nodes Removed</div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Flow Stats */}
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-base">Flow Statistics</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                            <div className="w-10 h-10 bg-violet-100 rounded-lg flex items-center justify-center">
                                                <GitCommit className="w-5 h-5 text-violet-600" />
                                            </div>
                                            <div>
                                                <div className="text-xl font-bold">{selectedVersion.nodeCount}</div>
                                                <div className="text-sm text-gray-500">Total Nodes</div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                                                <ChevronRight className="w-5 h-5 text-indigo-600" />
                                            </div>
                                            <div>
                                                <div className="text-xl font-bold">{selectedVersion.edgeCount}</div>
                                                <div className="text-sm text-gray-500">Connections</div>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-500">
                        <div className="text-center">
                            <History className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <h3 className="font-semibold text-lg mb-1">Select a Version</h3>
                            <p className="text-sm">Choose a version from the timeline to view details</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FlowVersioning;
