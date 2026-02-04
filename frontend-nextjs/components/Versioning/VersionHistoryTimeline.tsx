/**
 * Version History Timeline Component
 *
 * Displays a visual timeline of workflow versions with metadata,
 * commit messages, and author attribution.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  GitCommit,
  GitBranch,
  GitMerge,
  GitPullRequest,
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
  History,
  Tag,
  User,
  Calendar,
  FileJson,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Copy,
  Download,
  Trash2,
  Eye,
  GitCompareArrows,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { formatDistanceToNow } from 'date-fns';

// Types
interface WorkflowVersion {
  workflow_id: string;
  version: string;
  version_type: string;
  change_type: string;
  created_at: string;
  created_by: string;
  commit_message: string;
  tags: string[];
  parent_version: string | null;
  branch_name: string;
  checksum: string | null;
  is_active: boolean;
}

interface VersionHistoryTimelineProps {
  workflowId: string;
  workflowName: string;
  currentUserId: string;
  onVersionSelect?: (version: WorkflowVersion) => void;
  onCompareVersions?: (fromVersion: string, toVersion: string) => void;
  onRollback?: (version: string) => void;
}

// Version type colors
const versionTypeColors: Record<string, string> = {
  major: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  minor: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  patch: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  hotfix: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  beta: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  alpha: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
};

// Version type icons
const versionTypeIcons: Record<string, React.ReactNode> = {
  major: <AlertTriangle className="h-4 w-4" />,
  minor: <GitCommit className="h-4 w-4" />,
  patch: <CheckCircle className="h-4 w-4" />,
  hotfix: <XCircle className="h-4 w-4" />,
  beta: <GitBranch className="h-4 w-4" />,
  alpha: <GitPullRequest className="h-4 w-4" />,
};

export const VersionHistoryTimeline: React.FC<VersionHistoryTimelineProps> = ({
  workflowId,
  workflowName,
  currentUserId,
  onVersionSelect,
  onCompareVersions,
  onRollback,
}) => {
  const { toast } = useToast();

  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [branchFilter, setBranchFilter] = useState<string>('main');
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [branches, setBranches] = useState<string[]>(['main']);

  // Fetch version history
  useEffect(() => {
    fetchVersionHistory();
  }, [workflowId, branchFilter]);

  const fetchVersionHistory = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions?branch_name=${branchFilter}&limit=100`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch version history');
      }

      const data: WorkflowVersion[] = await response.json();
      setVersions(data);

      // Extract unique branches
      const uniqueBranches = Array.from(new Set(data.map((v) => v.branch_name)));
      setBranches(uniqueBranches);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      toast({
        title: 'Error',
        description: 'Failed to fetch version history',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (version: string) => {
    const newExpanded = new Set(expandedVersions);
    if (newExpanded.has(version)) {
      newExpanded.delete(version);
    } else {
      newExpanded.add(version);
    }
    setExpandedVersions(newExpanded);
  };

  const toggleVersionSelection = (version: string) => {
    const newSelected = [...selectedVersions];
    if (newSelected.includes(version)) {
      setSelectedVersions(newSelected.filter((v) => v !== version));
    } else {
      if (newSelected.length >= 2) {
        newSelected.shift();
      }
      newSelected.push(version);
    }
    setSelectedVersions(newSelected);
  };

  const handleCompare = () => {
    if (selectedVersions.length === 2 && onCompareVersions) {
      onCompareVersions(selectedVersions[0], selectedVersions[1]);
    } else {
      toast({
        title: 'Select two versions',
        description: 'Please select exactly two versions to compare',
        variant: 'error',
      });
    }
  };

  const handleRollback = async (version: string) => {
    if (onRollback) {
      onRollback(version);
    }
  };

  const handleDeleteVersion = async (version: string) => {
    if (!confirm(`Are you sure you want to delete version ${version}?`)) {
      return;
    }

    try {
      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions/${version}?delete_reason=Deleted by user`,
        {
          method: 'DELETE',
        }
      );

      if (!response.ok) {
        throw new Error('Failed to delete version');
      }

      toast({
        title: 'Success',
        description: `Version ${version} has been deleted`,
      });

      fetchVersionHistory();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to delete version',
        variant: 'error',
      });
    }
  };

  const copyChecksum = (checksum: string) => {
    navigator.clipboard.writeText(checksum);
    toast({
      title: 'Copied',
      description: 'Checksum copied to clipboard',
    });
  };

  const exportVersion = async (version: string) => {
    try {
      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions/${version}/data`
      );

      if (!response.ok) {
        throw new Error('Failed to export version');
      }

      const data = await response.json();

      // Download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${workflowName}_v${version}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: 'Exported',
        description: `Version ${version} exported successfully`,
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to export version',
        variant: 'error',
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Version History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Version History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-destructive">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4" />
            <p>{error}</p>
            <Button onClick={fetchVersionHistory} className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Version History
            </CardTitle>
            <CardDescription>
              {versions.length} version{versions.length !== 1 ? 's' : ''} • {workflowName}
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {/* Branch filter */}
            <Select value={branchFilter} onValueChange={setBranchFilter}>
              <SelectTrigger className="w-[180px]">
                <GitBranch className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Select branch" />
              </SelectTrigger>
              <SelectContent>
                {branches.map((branch) => (
                  <SelectItem key={branch} value={branch}>
                    {branch}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Compare button */}
            {selectedVersions.length === 2 && (
              <Button onClick={handleCompare} variant="default" size="sm">
                <GitCompareArrows className="h-4 w-4 mr-2" />
                Compare
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {versions.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <GitCommit className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No versions found</p>
            <p className="text-sm">Create your first version to start tracking changes</p>
          </div>
        ) : (
          <ScrollArea className="h-[600px] pr-4">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-border" />

              {/* Version items */}
              <div className="space-y-4">
                {versions.map((version, index) => (
                  <div key={version.version} className="relative">
                    {/* Timeline dot */}
                    <div className="absolute left-[11px] top-4 w-4 h-4 rounded-full bg-primary border-4 border-background" />

                    {/* Version content */}
                    <div className="ml-12">
                      <div
                        className={`border rounded-lg p-4 transition-colors ${
                          selectedVersions.includes(version.version)
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        {/* Header */}
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-3">
                            {/* Checkbox for comparison */}
                            <input
                              type="checkbox"
                              checked={selectedVersions.includes(version.version)}
                              onChange={() => toggleVersionSelection(version.version)}
                              className="h-4 w-4"
                            />

                            {/* Version number */}
                            <Badge
                              variant="outline"
                              className={`${versionTypeColors[version.version_type]} font-mono text-sm`}
                            >
                              v{version.version}
                            </Badge>

                            {/* Version type icon */}
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger>
                                  <div className="text-muted-foreground">
                                    {versionTypeIcons[version.version_type]}
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p className="capitalize">{version.version_type}</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>

                            {/* Change type badge */}
                            <Badge variant="secondary" className="text-xs">
                              {version.change_type}
                            </Badge>

                            {/* Branch */}
                            <Badge variant="outline" className="text-xs">
                              <GitBranch className="h-3 w-3 mr-1" />
                              {version.branch_name}
                            </Badge>

                            {/* Active indicator */}
                            {version.is_active && (
                              <Badge variant="default" className="text-xs">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Active
                              </Badge>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleExpand(version.version)}
                            >
                              {expandedVersions.has(version.version) ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </Button>

                            {version.is_active && onRollback && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleRollback(version.version)}
                                    >
                                      <ArrowUpDown className="h-4 w-4" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>Rollback to this version</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )}

                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => exportVersion(version.version)}
                                  >
                                    <Download className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>Export version</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>

                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDeleteVersion(version.version)}
                                    disabled={index === 0}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>Delete version</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                        </div>

                        {/* Commit message */}
                        <div className="mb-2">
                          <p className="text-sm font-medium">{version.commit_message}</p>
                        </div>

                        {/* Metadata */}
                        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            <span>{version.created_by}</span>
                          </div>

                          <div className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            <span>
                              {formatDistanceToNow(new Date(version.created_at), {
                                addSuffix: true,
                              })}
                            </span>
                          </div>

                          {version.parent_version && (
                            <div className="flex items-center gap-1">
                              <GitCommit className="h-3 w-3" />
                              <span>Parent: v{version.parent_version}</span>
                            </div>
                          )}

                          {version.checksum && (
                            <div className="flex items-center gap-1">
                              <FileJson className="h-3 w-3" />
                              <code className="text-xs">
                                {version.checksum.slice(0, 8)}...
                              </code>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-4 w-4 p-0"
                                onClick={() => copyChecksum(version.checksum!)}
                              >
                                <Copy className="h-3 w-3" />
                              </Button>
                            </div>
                          )}
                        </div>

                        {/* Tags */}
                        {version.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {version.tags.map((tag) => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                <Tag className="h-3 w-3 mr-1" />
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        )}

                        {/* Expanded details */}
                        {expandedVersions.has(version.version) && (
                          <div className="mt-4 pt-4 border-t space-y-2">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <p className="text-muted-foreground">Version ID</p>
                                <p className="font-mono">{version.version}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground">Workflow ID</p>
                                <p className="font-mono text-xs">{version.workflow_id}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground">Created At</p>
                                <p>{new Date(version.created_at).toLocaleString()}</p>
                              </div>
                              <div>
                                <p className="text-muted-foreground">Created By</p>
                                <p>{version.created_by}</p>
                              </div>
                            </div>

                            {version.checksum && (
                              <div>
                                <p className="text-muted-foreground text-sm">SHA-256 Checksum</p>
                                <p className="font-mono text-xs break-all">{version.checksum}</p>
                              </div>
                            )}

                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full"
                              onClick={() => onVersionSelect?.(version)}
                            >
                              <Eye className="h-4 w-4 mr-2" />
                              View Full Version Details
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
};

export default VersionHistoryTimeline;
