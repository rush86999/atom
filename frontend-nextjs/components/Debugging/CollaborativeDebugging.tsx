/**
 * Collaborative Debugging Component
 *
 * Manages multiple users debugging the same session together.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Users, UserPlus, UserMinus, Shield, Eye, Loader2, Copy } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface Collaborator {
  user_id: string;
  permission: 'viewer' | 'operator' | 'owner';
  added_at: string;
}

interface CollaborativeDebuggingProps {
  sessionId: string | null;
  workflowId: string | null;
  currentUserId: string;
  isOwner: boolean;
}

export const CollaborativeDebugging: React.FC<CollaborativeDebuggingProps> = ({
  sessionId,
  workflowId,
  currentUserId,
  isOwner,
}) => {
  const { toast } = useToast();

  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [loading, setLoading] = useState(false);
  const [addUserId, setAddUserId] = useState('');
  const [addPermission, setAddPermission] = useState<'viewer' | 'operator' | 'owner'>('viewer');

  useEffect(() => {
    if (sessionId) {
      fetchCollaborators();
    }
  }, [sessionId]);

  const fetchCollaborators = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      const response = await fetch(`/api/workflows/debug/sessions/${sessionId}/collaborators`);

      if (response.ok) {
        const data = await response.json();
        setCollaborators(data.collaborators);
      }
    } catch (err) {
      console.error('Error fetching collaborators:', err);
    } finally {
      setLoading(false);
    }
  };

  const addCollaborator = async () => {
    if (!sessionId || !addUserId) return;

    if (!isOwner) {
      toast({
        title: 'Permission Denied',
        description: 'Only the session owner can add collaborators',
        variant: 'error',
      });
      return;
    }

    try {
      const response = await fetch(
        `/api/workflows/debug/sessions/${sessionId}/collaborators?user_id=${encodeURIComponent(addUserId)}&permission=${addPermission}`,
        { method: 'POST' }
      );

      if (!response.ok) throw new Error('Failed to add collaborator');

      toast({
        title: 'Collaborator Added',
        description: `Added ${addUserId} as ${addPermission}`,
      });

      setAddUserId('');
      setAddPermission('viewer');
      fetchCollaborators();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to add collaborator',
        variant: 'error',
      });
    }
  };

  const removeCollaborator = async (userId: string) => {
    if (!sessionId) return;

    if (!isOwner) {
      toast({
        title: 'Permission Denied',
        description: 'Only the session owner can remove collaborators',
        variant: 'error',
      });
      return;
    }

    try {
      const response = await fetch(
        `/api/workflows/debug/sessions/${sessionId}/collaborators/${userId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to remove collaborator');

      toast({
        title: 'Collaborator Removed',
        description: `Removed ${userId} from session`,
      });

      fetchCollaborators();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to remove collaborator',
        variant: 'error',
      });
    }
  };

  const copyInviteLink = () => {
    if (!sessionId) return;

    const link = `${window.location.origin}/debug?session=${sessionId}`;
    navigator.clipboard.writeText(link);

    toast({
      title: 'Link Copied',
      description: 'Invite link copied to clipboard',
    });
  };

  const getPermissionBadge = (permission: string) => {
    const variants: Record<string, any> = {
      viewer: { variant: 'secondary', icon: Eye, label: 'Viewer' },
      operator: { variant: 'default', icon: Shield, label: 'Operator' },
      owner: { variant: 'outline', icon: Users, label: 'Owner' },
    };

    const config = variants[permission] || variants.viewer;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="text-xs">
        <Icon className="h-3 w-3 mr-1" />
        {config.label}
      </Badge>
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-indigo-500" />
              Collaborative Debugging
            </CardTitle>
            <CardDescription>
              {collaborators.length + 1} participant{collaborators.length !== 0 ? 's' : ''}
            </CardDescription>
          </div>

          {isOwner && (
            <Button variant="outline" size="sm" onClick={copyInviteLink}>
              <Copy className="h-4 w-4 mr-2" />
              Invite Link
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Add Collaborator (Owner Only) */}
        {isOwner && (
          <div className="p-3 bg-muted rounded-lg space-y-2">
            <h4 className="text-sm font-medium">Add Collaborator</h4>
            <div className="flex gap-2">
              <Input
                placeholder="User ID or email"
                value={addUserId}
                onChange={(e) => setAddUserId(e.target.value)}
                className="flex-1"
              />
              <Select value={addPermission} onValueChange={(v: any) => setAddPermission(v)}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">Viewer</SelectItem>
                  <SelectItem value="operator">Operator</SelectItem>
                  <SelectItem value="owner">Owner</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={addCollaborator} disabled={!addUserId} size="icon">
                <UserPlus className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Collaborators List */}
        <div>
          <h4 className="text-sm font-medium mb-2">Participants</h4>
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : collaborators.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground text-sm">
              No collaborators yet. {isOwner ? 'Add someone to debug together!' : 'Waiting for others to join...'}
            </div>
          ) : (
            <ScrollArea className="h-[200px]">
              <div className="space-y-2">
                {/* Owner (Current User) */}
                <div className="flex items-center justify-between p-2 bg-muted rounded">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-medium">
                    You
                    </div>
                    <div>
                      <p className="text-sm font-medium">Session Owner</p>
                      <p className="text-xs text-muted-foreground">{currentUserId}</p>
                    </div>
                  </div>
                  {getPermissionBadge('owner')}
                </div>

                {/* Collaborators */}
                {collaborators.map((collab) => (
                  <div key={collab.user_id} className="flex items-center justify-between p-2 border rounded">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center text-secondary-foreground text-xs font-medium">
                        {collab.user_id.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{collab.user_id}</p>
                        <p className="text-xs text-muted-foreground">
                          Added {new Date(collab.added_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {getPermissionBadge(collab.permission)}
                      {isOwner && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          onClick={() => removeCollaborator(collab.user_id)}
                        >
                          <UserMinus className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        {/* Permissions Info */}
        <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
          <p><strong>Permissions:</strong></p>
          <ul className="mt-1 space-y-1">
            <li>• <strong>Viewer:</strong> View session state and traces</li>
            <li>• <strong>Operator:</strong> Control execution (step, pause, continue)</li>
            <li>• <strong>Owner:</strong> Full control including managing collaborators</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default CollaborativeDebugging;
