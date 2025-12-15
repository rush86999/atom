/**
 * Workflow Versioning Component
 *
 * Comprehensive UI for workflow version management including:
 * - Version history display
 * - Version comparison
 * - Rollback functionality
 * - Branch management
 * - Performance metrics
 * - Visual diff viewer
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  GitBranch,
  GitCommit,
  GitCompare,
  GitMerge,
  GitPullRequest,
  History,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  User,
  Tag,
  Activity,
  TrendingUp,
  FileText,
  Settings,
  ChevronRight,
  ChevronDown,
  Eye,
  EyeOff,
  Download,
  Upload,
  GitCompareArrows,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react';
import { format } from 'date-fns';

// Types for workflow versioning
interface WorkflowVersion {
  workflow_id: string;
  version: string;
  version_type: string;
  change_type: string;
  created_at: string;
  created_by: string;
  commit_message: string;
  tags: string[];
  parent_version?: string;
  branch_name: string;
  checksum?: string;
  is_active: boolean;
}

interface VersionDiff {
  workflow_id: string;
  from_version: string;
  to_version: string;
  impact_level: string;
  added_steps_count: number;
  removed_steps_count: number;
  modified_steps_count: number;
  structural_changes: string[];
  dependency_changes: any[];
  parametric_changes: Record<string, any>;
  metadata_changes: Record<string, any>;
}

interface Branch {
  branch_name: string;
  workflow_id: string;
  base_version: string;
  current_version: string;
  created_at: string;
  created_by: string;
  is_protected: boolean;
  merge_strategy: string;
}

interface VersionMetrics {
  execution_count: number;
  success_rate: number;
  avg_execution_time: number;
  error_count: number;
  last_execution?: string;
  performance_score: number;
}

const WorkflowVersioning: React.FC<{ workflowId: string }> = ({ workflowId }) => {
  // State management
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<WorkflowVersion | null>(null);
  const [compareFrom, setCompareFrom] = useState<string>('');
  const [compareTo, setCompareTo] = useState<string>('');
  const [versionDiff, setVersionDiff] = useState<VersionDiff | null>(null);
  const [versionMetrics, setVersionMetrics] = useState<Record<string, VersionMetrics>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('history');
  const [expandedVersions, setExpandedVersions] = useState<Set<string>>(new Set());
  const [rollbackDialogOpen, setRollbackDialogOpen] = useState(false);
  const [rollbackReason, setRollbackReason] = useState('');
  const [createBranchDialogOpen, setCreateBranchDialogOpen] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [sourceBranch, setSourceBranch] = useState('');
  const [targetBranch, setTargetBranch] = useState('');

  // Fetch data on component mount
  useEffect(() => {
    fetchWorkflowData();
  }, [workflowId]);

  const fetchWorkflowData = async () => {
    try {
      setLoading(true);

      // Fetch versions
      const versionsResponse = await fetch(`/api/v1/workflows/${workflowId}/versions?limit=50`);
      if (versionsResponse.ok) {
        const versionsData = await versionsResponse.json();
        setVersions(versionsData);
      }

      // Fetch branches
      const branchesResponse = await fetch(`/api/v1/workflows/${workflowId}/branches`);
      if (branchesResponse.ok) {
        const branchesData = await branchesResponse.json();
        setBranches(branchesData);
      }

    } catch (error) {
      console.error('Error fetching workflow data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchVersionDiff = async (from: string, to: string) => {
    try {
      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions/compare?from_version=${from}&to_version=${to}`
      );
      if (response.ok) {
        const diffData = await response.json();
        setVersionDiff(diffData);
      }
    } catch (error) {
      console.error('Error fetching version diff:', error);
    }
  };

  const fetchVersionMetrics = async (version: string) => {
    try {
      const response = await fetch(`/api/v1/workflows/${workflowId}/versions/${version}/metrics`);
      if (response.ok) {
        const metricsData = await response.json();
        setVersionMetrics(prev => ({
          ...prev,
          [version]: metricsData.metrics || {}
        }));
      }
    } catch (error) {
      console.error('Error fetching version metrics:', error);
    }
  };

  const handleRollback = async () => {
    if (!selectedVersion || !rollbackReason) return;

    try {
      const response = await fetch(`/api/v1/workflows/${workflowId}/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_version: selectedVersion.version,
          rollback_reason: rollbackReason
        })
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Rollback successful:', result);
        setRollbackDialogOpen(false);
        setRollbackReason('');
        fetchWorkflowData(); // Refresh data
      }
    } catch (error) {
      console.error('Error during rollback:', error);
    }
  };

  const handleCreateBranch = async () => {
    if (!newBranchName || !selectedVersion) return;

    try {
      const response = await fetch(`/api/v1/workflows/${workflowId}/branches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          branch_name: newBranchName,
          base_version: selectedVersion.version,
          merge_strategy: 'merge_commit'
        })
      });

      if (response.ok) {
        console.log('Branch created successfully');
        setCreateBranchDialogOpen(false);
        setNewBranchName('');
        fetchWorkflowData(); // Refresh data
      }
    } catch (error) {
      console.error('Error creating branch:', error);
    }
  };

  const handleMergeBranch = async () => {
    if (!sourceBranch || !targetBranch) return;

    try {
      const response = await fetch(`/api/v1/workflows/${workflowId}/branches/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_branch: sourceBranch,
          target_branch: targetBranch,
          merge_message: `Merge ${sourceBranch} into ${targetBranch}`
        })
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Merge successful:', result);
        setMergeDialogOpen(false);
        fetchWorkflowData(); // Refresh data
      }
    } catch (error) {
      console.error('Error during merge:', error);
    }
  };

  const getVersionTypeColor = (versionType: string) => {
    switch (versionType) {
      case 'major': return 'destructive';
      case 'minor': return 'default';
      case 'patch': return 'secondary';
      case 'hotfix': return 'destructive';
      case 'beta': return 'outline';
      case 'alpha': return 'outline';
      default: return 'default';
    }
  };

  const getChangeTypeColor = (changeType: string) => {
    switch (changeType) {
      case 'structural': return 'destructive';
      case 'execution': return 'default';
      case 'dependency': return 'secondary';
      case 'parametric': return 'outline';
      case 'metadata': return 'outline';
      default: return 'default';
    }
  };

  const getImpactLevelColor = (level: string) => {
    switch (level) {
      case 'critical': return 'destructive';
      case 'high': return 'destructive';
      case 'medium': return 'default';
      case 'low': return 'secondary';
      default: return 'default';
    }
  };

  const toggleVersionExpansion = (version: string) => {
    setExpandedVersions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(version)) {
        newSet.delete(version);
      } else {
        newSet.add(version);
        // Fetch metrics when expanding
        fetchVersionMetrics(version);
      }
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading version data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <GitBranch className="h-6 w-6" />
            Workflow Versioning
          </h2>
          <p className="text-muted-foreground">
            Manage versions, branches, and rollback operations
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => fetchWorkflowData()}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Version History
          </TabsTrigger>
          <TabsTrigger value="compare" className="flex items-center gap-2">
            <GitCompareArrows className="h-4 w-4" />
            Compare
          </TabsTrigger>
          <TabsTrigger value="branches" className="flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Branches
          </TabsTrigger>
          <TabsTrigger value="metrics" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Metrics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitCommit className="h-5 w-5" />
                Version History
              </CardTitle>
              <CardDescription>
                Complete history of all workflow versions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {versions.map((version, index) => (
                  <div key={version.version} className="border rounded-lg p-4">
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => toggleVersionExpansion(version.version)}
                    >
                      <div className="flex items-center gap-3">
                        {expandedVersions.has(version.version) ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-semibold">{version.version}</span>
                            <Badge variant={getVersionTypeColor(version.version_type)}>
                              {version.version_type}
                            </Badge>
                            <Badge variant={getChangeTypeColor(version.change_type)}>
                              {version.change_type}
                            </Badge>
                            {version.tags.map(tag => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                <Tag className="h-3 w-3 mr-1" />
                                {tag}
                              </Badge>
                            ))}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {version.commit_message}
                          </p>
                          <div className="flex items-center gap-4 text-xs text-muted-foreground mt-2">
                            <span className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {version.created_by}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {format(new Date(version.created_at), 'MMM dd, yyyy HH:mm')}
                            </span>
                            <span className="flex items-center gap-1">
                              <GitBranch className="h-3 w-3" />
                              {version.branch_name}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {version.is_active ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <EyeOff className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                    </div>

                    {expandedVersions.has(version.version) && (
                      <div className="mt-4 pl-7 space-y-3">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <Label className="text-xs font-medium">Parent Version</Label>
                            <p className="font-mono">{version.parent_version || 'None'}</p>
                          </div>
                          <div>
                            <Label className="text-xs font-medium">Checksum</Label>
                            <p className="font-mono text-xs">{version.checksum?.substring(0, 16)}...</p>
                          </div>
                        </div>

                        {versionMetrics[version.version] && (
                          <div className="border-t pt-3">
                            <Label className="text-xs font-medium mb-2 block">Performance Metrics</Label>
                            <div className="grid grid-cols-4 gap-4">
                              <div className="text-center">
                                <p className="text-2xl font-bold">
                                  {versionMetrics[version.version].execution_count}
                                </p>
                                <p className="text-xs text-muted-foreground">Executions</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold">
                                  {versionMetrics[version.version].success_rate.toFixed(1)}%
                                </p>
                                <p className="text-xs text-muted-foreground">Success Rate</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold">
                                  {(versionMetrics[version.version].avg_execution_time / 1000).toFixed(1)}s
                                </p>
                                <p className="text-xs text-muted-foreground">Avg Time</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold">
                                  {versionMetrics[version.version].performance_score.toFixed(0)}
                                </p>
                                <p className="text-xs text-muted-foreground">Performance</p>
                              </div>
                            </div>
                          </div>
                        )}

                        <div className="flex gap-2 pt-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedVersion(version)}
                          >
                            <Eye className="h-4 w-4 mr-2" />
                            View Details
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setCreateBranchDialogOpen(true);
                              setSelectedVersion(version);
                            }}
                          >
                            <GitBranch className="h-4 w-4 mr-2" />
                            Create Branch
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedVersion(version);
                              setRollbackDialogOpen(true);
                            }}
                            disabled={version.is_active}
                          >
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Rollback
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="compare" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitCompareArrows className="h-5 w-5" />
                Version Comparison
              </CardTitle>
              <CardDescription>
                Compare different versions to see changes and impact
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <Label>From Version</Label>
                  <Select value={compareFrom} onValueChange={setCompareFrom}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select from version" />
                    </SelectTrigger>
                    <SelectContent>
                      {versions.map(version => (
                        <SelectItem key={version.version} value={version.version}>
                          {version.version} - {version.commit_message}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>To Version</Label>
                  <Select value={compareTo} onValueChange={setCompareTo}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select to version" />
                    </SelectTrigger>
                    <SelectContent>
                      {versions.map(version => (
                        <SelectItem key={version.version} value={version.version}>
                          {version.version} - {version.commit_message}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {compareFrom && compareTo && (
                <div className="space-y-4">
                  <Button
                    onClick={() => fetchVersionDiff(compareFrom, compareTo)}
                    className="w-full"
                  >
                    <GitCompareArrows className="h-4 w-4 mr-2" />
                    Compare Versions
                  </Button>

                  {versionDiff && (
                    <div className="border rounded-lg p-4 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold">Comparison Results</h3>
                        <Badge variant={getImpactLevelColor(versionDiff.impact_level)}>
                          {versionDiff.impact_level.toUpperCase()} IMPACT
                        </Badge>
                      </div>

                      <div className="grid grid-cols-3 gap-4">
                        <div className="text-center">
                          <p className="text-2xl font-bold text-green-600">
                            +{versionDiff.added_steps_count}
                          </p>
                          <p className="text-sm text-muted-foreground">Added Steps</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-orange-600">
                            ~{versionDiff.modified_steps_count}
                          </p>
                          <p className="text-sm text-muted-foreground">Modified Steps</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-red-600">
                            -{versionDiff.removed_steps_count}
                          </p>
                          <p className="text-sm text-muted-foreground">Removed Steps</p>
                        </div>
                      </div>

                      {versionDiff.structural_changes.length > 0 && (
                        <div>
                          <Label className="text-sm font-medium mb-2 block">Structural Changes</Label>
                          <ul className="text-sm space-y-1">
                            {versionDiff.structural_changes.map((change, index) => (
                              <li key={index} className="flex items-center gap-2">
                                <AlertTriangle className="h-3 w-3 text-orange-500" />
                                {change}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {Object.keys(versionDiff.parametric_changes).length > 0 && (
                        <div>
                          <Label className="text-sm font-medium mb-2 block">Parameter Changes</Label>
                          <div className="text-sm space-y-2">
                            {Object.entries(versionDiff.parametric_changes).map(([stepId, changes]) => (
                              <div key={stepId} className="border-l-2 border-blue-500 pl-3">
                                <p className="font-medium">Step: {stepId}</p>
                                <pre className="text-xs bg-muted p-2 rounded mt-1">
                                  {JSON.stringify(changes, null, 2)}
                                </pre>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="branches" className="space-y-4">
          <div className="flex justify-between items-center">
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Branch Management
            </CardTitle>
            <Button
              onClick={() => setMergeDialogOpen(true)}
              variant="outline"
            >
              <GitMerge className="h-4 w-4 mr-2" />
              Merge Branches
            </Button>
          </div>

          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Branch Name</TableHead>
                    <TableHead>Base Version</TableHead>
                    <TableHead>Current Version</TableHead>
                    <TableHead>Created By</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {branches.map(branch => (
                    <TableRow key={branch.branch_name}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <GitBranch className="h-4 w-4" />
                          {branch.branch_name}
                          {branch.is_protected && (
                            <Badge variant="secondary" className="text-xs">
                              Protected
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono">{branch.base_version}</TableCell>
                      <TableCell className="font-mono">{branch.current_version}</TableCell>
                      <TableCell>{branch.created_by}</TableCell>
                      <TableCell>
                        {format(new Date(branch.created_at), 'MMM dd, yyyy')}
                      </TableCell>
                      <TableCell>
                        <Badge variant={branch.branch_name === 'main' ? 'default' : 'outline'}>
                          {branch.branch_name === 'main' ? 'Primary' : 'Feature'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSourceBranch(branch.branch_name);
                            setTargetBranch('main');
                          }}
                          disabled={branch.branch_name === 'main'}
                        >
                          <GitPullRequest className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Performance Metrics
              </CardTitle>
              <CardDescription>
                Track performance and execution metrics across versions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {versions.filter(v => versionMetrics[v.version]).map(version => {
                  const metrics = versionMetrics[version.version];
                  return (
                    <div key={version.version} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="font-semibold">Version {version.version}</h4>
                        <div className="flex items-center gap-2">
                          <Badge variant={metrics.success_rate > 90 ? 'default' : 'destructive'}>
                            {metrics.success_rate.toFixed(1)}% Success
                          </Badge>
                          <Badge variant={metrics.performance_score > 80 ? 'default' : 'secondary'}>
                            Score: {metrics.performance_score.toFixed(0)}
                          </Badge>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="text-center p-3 bg-muted rounded">
                          <p className="text-lg font-bold">{metrics.execution_count}</p>
                          <p className="text-xs text-muted-foreground">Total Executions</p>
                        </div>
                        <div className="text-center p-3 bg-muted rounded">
                          <p className="text-lg font-bold text-green-600">
                            {metrics.success_rate.toFixed(1)}%
                          </p>
                          <p className="text-xs text-muted-foreground">Success Rate</p>
                        </div>
                        <div className="text-center p-3 bg-muted rounded">
                          <p className="text-lg font-bold">
                            {(metrics.avg_execution_time / 1000).toFixed(1)}s
                          </p>
                          <p className="text-xs text-muted-foreground">Avg Time</p>
                        </div>
                        <div className="text-center p-3 bg-muted rounded">
                          <p className="text-lg font-bold text-red-600">{metrics.error_count}</p>
                          <p className="text-xs text-muted-foreground">Errors</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Rollback Dialog */}
      <Dialog open={rollbackDialogOpen} onOpenChange={setRollbackDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rollback Workflow</DialogTitle>
            <DialogDescription>
              Rollback the workflow to version {selectedVersion?.version}.
              This will create a new rollback version.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="rollback-reason">Reason for Rollback</Label>
              <Textarea
                id="rollback-reason"
                placeholder="Explain why you're rolling back to this version..."
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRollbackDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleRollback}
                disabled={!rollbackReason}
                variant="destructive"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Rollback
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Branch Dialog */}
      <Dialog open={createBranchDialogOpen} onOpenChange={setCreateBranchDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Branch</DialogTitle>
            <DialogDescription>
              Create a new branch from version {selectedVersion?.version}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="branch-name">Branch Name</Label>
              <Input
                id="branch-name"
                placeholder="feature/new-feature"
                value={newBranchName}
                onChange={(e) => setNewBranchName(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateBranchDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateBranch} disabled={!newBranchName}>
                <GitBranch className="h-4 w-4 mr-2" />
                Create Branch
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Merge Branch Dialog */}
      <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge Branch</DialogTitle>
            <DialogDescription>
              Merge source branch into target branch
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Source Branch</Label>
              <Select value={sourceBranch} onValueChange={setSourceBranch}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source branch" />
                </SelectTrigger>
                <SelectContent>
                  {branches.filter(b => b.branch_name !== 'main').map(branch => (
                    <SelectItem key={branch.branch_name} value={branch.branch_name}>
                      {branch.branch_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Target Branch</Label>
              <Select value={targetBranch} onValueChange={setTargetBranch}>
                <SelectTrigger>
                  <SelectValue placeholder="Select target branch" />
                </SelectTrigger>
                <SelectContent>
                  {branches.map(branch => (
                    <SelectItem key={branch.branch_name} value={branch.branch_name}>
                      {branch.branch_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleMergeBranch}
                disabled={!sourceBranch || !targetBranch || sourceBranch === targetBranch}
              >
                <GitMerge className="h-4 w-4 mr-2" />
                Merge Branch
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WorkflowVersioning;