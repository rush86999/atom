/**
 * Rollback Workflow Modal Component
 *
 * Modal for one-click rollback with confirmation and reason input.
 * Shows preview of target version and creates rollback version.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  ArrowLeftCircle,
  GitCommit,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Eye,
  Calendar,
  User,
  Tag,
  Info,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
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

interface RollbackWorkflowModalProps {
  workflowId: string;
  workflowName: string;
  targetVersion: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUserId: string;
  onRollbackComplete?: (newVersion: string) => void;
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

export const RollbackWorkflowModal: React.FC<RollbackWorkflowModalProps> = ({
  workflowId,
  workflowName,
  targetVersion,
  open,
  onOpenChange,
  currentUserId,
  onRollbackComplete,
}) => {
  const { toast } = useToast();

  const [targetVersionData, setTargetVersionData] = useState<WorkflowVersion | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingVersion, setFetchingVersion] = useState(false);
  const [rollbackReason, setRollbackReason] = useState('');
  const [versionError, setVersionError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    if (open && targetVersion) {
      fetchTargetVersion();
    }
  }, [open, targetVersion]);

  const fetchTargetVersion = async () => {
    try {
      setFetchingVersion(true);
      setVersionError(null);

      const response = await fetch(
        `/api/v1/workflows/${workflowId}/versions/${targetVersion}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch target version');
      }

      const data: WorkflowVersion = await response.json();
      setTargetVersionData(data);
    } catch (err) {
      setVersionError(err instanceof Error ? err.message : 'Unknown error');
      toast({
        title: 'Error',
        description: 'Failed to fetch target version details',
        variant: 'error',
      });
    } finally {
      setFetchingVersion(false);
    }
  };

  const handleRollback = async () => {
    if (!rollbackReason.trim()) {
      toast({
        title: 'Reason Required',
        description: 'Please provide a reason for the rollback',
        variant: 'error',
      });
      return;
    }

    try {
      setLoading(true);

      const response = await fetch(`/api/v1/workflows/${workflowId}/rollback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_version: targetVersion,
          rollback_reason: rollbackReason,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to rollback workflow');
      }

      const result = await response.json();

      toast({
        title: 'Rollback Successful',
        description: `Workflow rolled back to version ${targetVersion}. New version: ${result.rollback_version}`,
      });

      onRollbackComplete?.(result.rollback_version);
      onOpenChange(false);
      setRollbackReason('');
    } catch (err) {
      toast({
        title: 'Rollback Failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowLeftCircle className="h-5 w-5 text-orange-500" />
            Rollback Workflow
          </DialogTitle>
          <DialogDescription>
            Rollback &quot;{workflowName}&quot; to version {targetVersion}
          </DialogDescription>
        </DialogHeader>

        {fetchingVersion ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading version details...</span>
          </div>
        ) : versionError ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Error Loading Version</AlertTitle>
            <AlertDescription>{versionError}</AlertDescription>
          </Alert>
        ) : targetVersionData ? (
          <div className="space-y-6">
            {/* Target Version Preview */}
            <div className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Badge className={`${versionTypeColors[targetVersionData.version_type]} font-mono`}>
                    v{targetVersionData.version}
                  </Badge>
                  <Badge variant="secondary">{targetVersionData.change_type}</Badge>
                  <Badge variant="outline">
                    <GitCommit className="h-3 w-3 mr-1" />
                    {targetVersionData.branch_name}
                  </Badge>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowPreview(!showPreview)}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  {showPreview ? 'Hide' : 'Show'} Details
                </Button>
              </div>

              <div>
                <p className="font-medium">{targetVersionData.commit_message}</p>
              </div>

              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  <span>{targetVersionData.created_by}</span>
                </div>

                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span>
                    {formatDistanceToNow(new Date(targetVersionData.created_at), {
                      addSuffix: true,
                    })}
                  </span>
                </div>

                {targetVersionData.parent_version && (
                  <div className="flex items-center gap-1">
                    <GitCommit className="h-4 w-4" />
                    <span>from v{targetVersionData.parent_version}</span>
                  </div>
                )}
              </div>

              {targetVersionData.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {targetVersionData.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      <Tag className="h-3 w-3 mr-1" />
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}

              {/* Expanded Preview */}
              {showPreview && (
                <div className="pt-3 border-t space-y-2">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Version Type</p>
                      <p className="capitalize">{targetVersionData.version_type}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Change Type</p>
                      <p className="capitalize">{targetVersionData.change_type}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Created At</p>
                      <p>{new Date(targetVersionData.created_at).toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Status</p>
                      <Badge variant={targetVersionData.is_active ? 'default' : 'secondary'}>
                        {targetVersionData.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>

                  {targetVersionData.checksum && (
                    <div>
                      <p className="text-muted-foreground text-sm">Checksum</p>
                      <p className="font-mono text-xs">{targetVersionData.checksum}</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Rollback Reason Input */}
            <div className="space-y-2">
              <Label htmlFor="rollback-reason">
                Rollback Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="rollback-reason"
                placeholder="Describe why you are rolling back to this version..."
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                rows={3}
                className={rollbackReason.trim() === '' ? 'border-destructive' : ''}
              />
              <p className="text-xs text-muted-foreground">
                This will be recorded in the version history for audit purposes.
              </p>
            </div>

            {/* Warning Alert */}
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Important</AlertTitle>
              <AlertDescription>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>A new rollback version will be created</li>
                  <li>Current workflow state will be preserved</li>
                  <li>This action cannot be undone</li>
                  <li>All collaborators will be notified of this change</li>
                </ul>
              </AlertDescription>
            </Alert>

            {/* Info Alert */}
            <Alert>
              <Info className="h-4 w-4" />
              <AlertTitle>What happens next?</AlertTitle>
              <AlertDescription className="text-sm">
                After rollback, the workflow will be restored to the exact state of version{' '}
                {targetVersion}. A new hotfix version will be created with your rollback reason.
              </AlertDescription>
            </Alert>
          </div>
        ) : null}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false);
              setRollbackReason('');
              setShowPreview(false);
            }}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleRollback}
            disabled={loading || !targetVersionData || rollbackReason.trim() === ''}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Rolling Back...
              </>
            ) : (
              <>
                <ArrowLeftCircle className="h-4 w-4 mr-2" />
                Confirm Rollback
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RollbackWorkflowModal;
