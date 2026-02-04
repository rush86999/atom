/**
 * Version Diff Viewer Component
 *
 * Side-by-side comparison of workflow changes between two versions.
 * Shows added, removed, and modified steps with detailed changes.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  GitCompare,
  Plus,
  Minus,
  Replace,
  FileJson,
  ArrowRight,
  ArrowLeft,
  GitCommit,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  Filter,
  Download,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

// Types
interface VersionDiffResponse {
  workflow_id: string;
  from_version: string;
  to_version: string;
  impact_level: string;
  added_steps_count: number;
  removed_steps_count: number;
  modified_steps_count: number;
  structural_changes: string[];
  dependency_changes: Array<{
    added: string[];
    removed: string[];
  }>;
  parametric_changes: Record<string, { old: any; new: any }>;
  metadata_changes: Record<string, { old: any; new: any }>;
}

interface StepChange {
  step_id: string;
  old_step: Record<string, any>;
  new_step: Record<string, any>;
  changes: {
    parameters: Record<string, { old: any; new: any }>;
    execution_logic: { old: any; new: any };
    metadata: Record<string, { old: any; new: any }>;
    structural: boolean;
  };
}

interface VersionDiffViewerProps {
  workflowId: string;
  fromVersion: string;
  toVersion: string;
  onClose?: () => void;
}

// Impact level colors
const impactColors: Record<string, string> = {
  low: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  high: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  critical: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export const VersionDiffViewer: React.FC<VersionDiffViewerProps> = ({
  workflowId,
  fromVersion,
  toVersion,
  onClose,
}) => {
  const { toast } = useToast();

  const [diff, setDiff] = useState<VersionDiffResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [filter, setFilter] = useState<string>('all');
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchDiff();
  }, [workflowId, fromVersion, toVersion]);

  const fetchDiff = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions/compare?from_version=${fromVersion}&to_version=${toVersion}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch version diff');
      }

      const data: VersionDiffResponse = await response.json();
      setDiff(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      toast({
        title: 'Error',
        description: 'Failed to fetch version diff',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (stepId: string) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepId)) {
      newExpanded.delete(stepId);
    } else {
      newExpanded.add(stepId);
    }
    setExpandedSteps(newExpanded);
  };

  const exportDiff = () => {
    if (!diff) return;

    const data = JSON.stringify(diff, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diff_${fromVersion}_to_${toVersion}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: 'Exported',
      description: 'Diff exported successfully',
    });
  };

  const renderValue = (value: any): React.ReactNode => {
    if (value === null) return <span className="text-muted-foreground italic">null</span>;
    if (value === undefined) return <span className="text-muted-foreground italic">undefined</span>;
    if (typeof value === 'boolean') return <span>{value.toString()}</span>;
    if (typeof value === 'object') return <code className="text-xs">{JSON.stringify(value)}</code>;
    return <span>{String(value)}</span>;
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Comparing Versions</CardTitle>
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
          <CardTitle>Version Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-destructive">
            <AlertTriangle className="h-12 w-12 mx-auto mb-4" />
            <p>{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!diff) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <GitCompare className="h-5 w-5" />
              Version Comparison
            </CardTitle>
            <CardDescription>
              {diff.from_version} → {diff.to_version}
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Badge className={impactColors[diff.impact_level]}>
              {diff.impact_level.toUpperCase()} IMPACT
            </Badge>

            <Button variant="outline" size="sm" onClick={exportDiff}>
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>

            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose}>
                Close
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="steps">
              Steps{' '}
              <Badge variant="secondary" className="ml-2">
                {diff.added_steps_count + diff.removed_steps_count + diff.modified_steps_count}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="dependencies">Dependencies</TabsTrigger>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            {/* Impact Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">Added</span>
                  <Plus className="h-4 w-4 text-green-500" />
                </div>
                <p className="text-2xl font-bold">{diff.added_steps_count}</p>
                <p className="text-xs text-muted-foreground">steps</p>
              </div>

              <div className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">Removed</span>
                  <Minus className="h-4 w-4 text-red-500" />
                </div>
                <p className="text-2xl font-bold">{diff.removed_steps_count}</p>
                <p className="text-xs text-muted-foreground">steps</p>
              </div>

              <div className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">Modified</span>
                  <Replace className="h-4 w-4 text-yellow-500" />
                </div>
                <p className="text-2xl font-bold">{diff.modified_steps_count}</p>
                <p className="text-xs text-muted-foreground">steps</p>
              </div>
            </div>

            {/* Structural Changes */}
            {diff.structural_changes.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Structural Changes</h4>
                <div className="space-y-2">
                  {diff.structural_changes.map((change, idx) => (
                    <div key={idx} className="flex items-start gap-2 p-2 bg-muted rounded">
                      <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5" />
                      <p className="text-sm">{change}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Impact Assessment */}
            <div>
              <h4 className="font-semibold mb-2">Impact Assessment</h4>
              <div className={`p-4 rounded-lg ${impactColors[diff.impact_level]}`}>
                <div className="flex items-center gap-2 mb-2">
                  {diff.impact_level === 'critical' && <XCircle className="h-5 w-5" />}
                  {diff.impact_level === 'high' && <AlertTriangle className="h-5 w-5" />}
                  {diff.impact_level === 'medium' && <ChevronDown className="h-5 w-5" />}
                  {diff.impact_level === 'low' && <CheckCircle className="h-5 w-5" />}
                  <span className="font-semibold capitalize">{diff.impact_level} Impact</span>
                </div>
                <p className="text-sm">
                  {diff.impact_level === 'critical' && 'This change introduces breaking changes that require immediate attention.'}
                  {diff.impact_level === 'high' && 'This change significantly affects workflow behavior.'}
                  {diff.impact_level === 'medium' && 'This change may affect some workflow scenarios.'}
                  {diff.impact_level === 'low' && 'This change has minimal impact on workflow behavior.'}
                </p>
              </div>
            </div>
          </TabsContent>

          {/* Steps Tab */}
          <TabsContent value="steps" className="space-y-4">
            {/* Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              >
                <option value="all">All Changes</option>
                <option value="added">Added Only</option>
                <option value="removed">Removed Only</option>
                <option value="modified">Modified Only</option>
              </select>
            </div>

            {/* Parametric Changes */}
            {Object.keys(diff.parametric_changes).length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Parameter Changes</h4>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {Object.entries(diff.parametric_changes).map(([stepId, change]) => {
                      if (filter !== 'all' && filter !== 'modified') return null;

                      return (
                        <div key={stepId} className="border rounded-lg p-4">
                          <div className="flex items-center justify-between mb-2">
                            <Badge variant="outline" className="font-mono">
                              {stepId}
                            </Badge>
                            <Badge variant="secondary">
                              <Replace className="h-3 w-3 mr-1" />
                              Modified
                            </Badge>
                          </div>

                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <p className="text-muted-foreground mb-1">Old Value</p>
                              <div className="bg-red-50 dark:bg-red-900/20 p-2 rounded">
                                {renderValue(change.old)}
                              </div>
                            </div>
                            <div>
                              <p className="text-muted-foreground mb-1">New Value</p>
                              <div className="bg-green-50 dark:bg-green-900/20 p-2 rounded">
                                {renderValue(change.new)}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </div>
            )}

            {Object.keys(diff.parametric_changes).length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <FileJson className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No parameter changes detected</p>
              </div>
            )}
          </TabsContent>

          {/* Dependencies Tab */}
          <TabsContent value="dependencies" className="space-y-4">
            {diff.dependency_changes.length > 0 ? (
              <div className="space-y-4">
                {diff.dependency_changes.map((change, idx) => (
                  <div key={idx}>
                    {change.added.length > 0 && (
                      <div className="mb-4">
                        <h5 className="text-sm font-semibold text-green-600 dark:text-green-400 mb-2">
                          <Plus className="h-4 w-4 inline mr-1" />
                          Added Dependencies
                        </h5>
                        <div className="space-y-1">
                          {change.added.map((dep, depIdx) => (
                            <div key={depIdx} className="flex items-center gap-2 p-2 bg-green-50 dark:bg-green-900/20 rounded">
                              <Plus className="h-4 w-4 text-green-500" />
                              <code className="text-sm">{dep}</code>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {change.removed.length > 0 && (
                      <div>
                        <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">
                          <Minus className="h-4 w-4 inline mr-1" />
                          Removed Dependencies
                        </h5>
                        <div className="space-y-1">
                          {change.removed.map((dep, depIdx) => (
                            <div key={depIdx} className="flex items-center gap-2 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                              <Minus className="h-4 w-4 text-red-500" />
                              <code className="text-sm">{dep}</code>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <GitBranch className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No dependency changes detected</p>
              </div>
            )}
          </TabsContent>

          {/* Metadata Tab */}
          <TabsContent value="metadata" className="space-y-4">
            {Object.keys(diff.metadata_changes).length > 0 ? (
              <ScrollArea className="h-[400px]">
                <div className="space-y-3">
                  {Object.entries(diff.metadata_changes).map(([key, change]) => (
                    <div key={key} className="border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Badge variant="outline">{key}</Badge>
                        <Badge variant="secondary">
                          <Replace className="h-3 w-3 mr-1" />
                          Changed
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Old Value</p>
                          <div className="bg-red-50 dark:bg-red-900/20 p-2 rounded text-sm">
                            {renderValue(change.old)}
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">New Value</p>
                          <div className="bg-green-50 dark:bg-green-900/20 p-2 rounded text-sm">
                            {renderValue(change.new)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <FileJson className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No metadata changes detected</p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default VersionDiffViewer;
