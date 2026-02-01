/**
 * Share Workflow Modal Component
 * Modal for sharing workflows with team members via link or email
 */

import React, { useState, useCallback } from 'react';
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
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Link2,
  Mail,
  Copy,
  Check,
  Share2,
  Users,
  Calendar,
  Shield,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface ShareWorkflowModalProps {
  workflowId: string;
  workflowName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUserId: string;
}

interface Permission {
  can_view: boolean;
  can_edit: boolean;
  can_comment: boolean;
  can_share: boolean;
}

export const ShareWorkflowModal: React.FC<ShareWorkflowModalProps> = ({
  workflowId,
  workflowName,
  open,
  onOpenChange,
  currentUserId,
}) => {
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<'link' | 'email'>('link');
  const [shareLink, setShareLink] = useState<string>('');
  const [copied, setCopied] = useState(false);

  // Link sharing
  const [linkPermissions, setLinkPermissions] = useState<Permission>({
    can_view: true,
    can_edit: false,
    can_comment: true,
    can_share: false,
  });
  const [expiresInDays, setExpiresInDays] = useState<number | null>(null);
  const [maxUses, setMaxUses] = useState<number | null>(null);

  // Email sharing
  const [emailAddresses, setEmailAddresses] = useState('');
  const [emailMessage, setEmailMessage] = useState('');

  // Existing shares (for display)
  const [existingShares, setExistingShares] = useState<any[]>([]);

  // Create share link
  const handleCreateShareLink = async () => {
    try {
      const response = await fetch('/api/collaboration/shares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          share_type: 'link',
          permissions: linkPermissions,
          expires_in_days: expiresInDays || undefined,
          max_uses: maxUses || undefined,
        }),
      });

      if (!response.ok) throw new Error('Failed to create share link');

      const share = await response.json();
      const fullLink = `${window.location.origin}/share/${share.share_id}`;

      setShareLink(fullLink);
      setExistingShares([...existingShares, share]);

      toast({
        title: 'Success',
        description: 'Share link created successfully',
      });
    } catch (error) {
      console.error('Error creating share link:', error);
      toast({
        title: 'Error',
        description: 'Failed to create share link',
        variant: 'error',
      });
    }
  };

  // Copy share link to clipboard
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareLink);
      setCopied(true);

      setTimeout(() => setCopied(false), 2000);

      toast({
        title: 'Copied!',
        description: 'Share link copied to clipboard',
      });
    } catch (error) {
      console.error('Error copying link:', error);
      toast({
        title: 'Error',
        description: 'Failed to copy link',
        variant: 'error',
      });
    }
  };

  // Send email invites
  const handleSendEmailInvites = async () => {
    const emails = emailAddresses.split(',').map(e => e.trim()).filter(e => e);

    if (emails.length === 0) {
      toast({
        title: 'Error',
        description: 'Please enter at least one email address',
        variant: 'error',
      });
      return;
    }

    // TODO: Implement email sending
    toast({
      title: 'Coming Soon',
      description: `Invites would be sent to: ${emails.join(', ')}`,
    });
  };

  // Revoke share
  const handleRevokeShare = async (shareId: string) => {
    try {
      const response = await fetch(`/api/collaboration/shares/${shareId}?user_id=${currentUserId}`, {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to revoke share');

      setExistingShares(existingShares.filter(s => s.share_id !== shareId));

      toast({
        title: 'Success',
        description: 'Share link revoked',
      });
    } catch (error) {
      console.error('Error revoking share:', error);
      toast({
        title: 'Error',
        description: 'Failed to revoke share',
        variant: 'error',
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Share2 className="h-5 w-5" />
            Share "{workflowName}"
          </DialogTitle>
          <DialogDescription>
            Share this workflow with your team members
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="link" className="flex items-center gap-2">
              <Link2 className="h-4 w-4" />
              Share Link
            </TabsTrigger>
            <TabsTrigger value="email" className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email Invite
            </TabsTrigger>
          </TabsList>

          {/* Link Sharing Tab */}
          <TabsContent value="link" className="space-y-6 mt-4">
            {/* Permissions */}
            <div className="space-y-4">
              <div>
                <Label className="text-base font-semibold">Permissions</Label>
                <p className="text-sm text-muted-foreground mb-3">
                  Choose what people with this link can do
                </p>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="can_view" className="cursor-pointer">
                      View workflow
                    </Label>
                    <Switch
                      id="can_view"
                      checked={linkPermissions.can_view}
                      onCheckedChange={(checked) =>
                        setLinkPermissions({ ...linkPermissions, can_view: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <Label htmlFor="can_edit" className="cursor-pointer">
                      Edit workflow
                    </Label>
                    <Switch
                      id="can_edit"
                      checked={linkPermissions.can_edit}
                      onCheckedChange={(checked) =>
                        setLinkPermissions({ ...linkPermissions, can_edit: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <Label htmlFor="can_comment" className="cursor-pointer">
                      Comment
                    </Label>
                    <Switch
                      id="can_comment"
                      checked={linkPermissions.can_comment}
                      onCheckedChange={(checked) =>
                        setLinkPermissions({ ...linkPermissions, can_comment: checked })
                      }
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <Label htmlFor="can_share" className="cursor-pointer">
                      Share with others
                    </Label>
                    <Switch
                      id="can_share"
                      checked={linkPermissions.can_share}
                      onCheckedChange={(checked) =>
                        setLinkPermissions({ ...linkPermissions, can_share: checked })
                      }
                    />
                  </div>
                </div>
              </div>

              {/* Expiration */}
              <div>
                <Label className="text-base font-semibold">Expiration (Optional)</Label>
                <p className="text-sm text-muted-foreground mb-3">
                  Set when the link should expire
                </p>

                <div className="flex gap-2">
                  <Button
                    variant={expiresInDays === null ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setExpiresInDays(null)}
                  >
                    Never
                  </Button>
                  <Button
                    variant={expiresInDays === 7 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setExpiresInDays(7)}
                  >
                    7 Days
                  </Button>
                  <Button
                    variant={expiresInDays === 30 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setExpiresInDays(30)}
                  >
                    30 Days
                  </Button>
                </div>
              </div>

              {/* Usage Limit */}
              <div>
                <Label className="text-base font-semibold">Usage Limit (Optional)</Label>
                <p className="text-sm text-muted-foreground mb-3">
                  Maximum number of times the link can be used
                </p>

                <div className="flex gap-2">
                  <Button
                    variant={maxUses === null ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setMaxUses(null)}
                  >
                    Unlimited
                  </Button>
                  <Input
                    type="number"
                    placeholder="10"
                    value={maxUses || ''}
                    onChange={(e) => setMaxUses(e.target.value ? parseInt(e.target.value) : null)}
                    className="w-32"
                    min={1}
                  />
                </div>
              </div>

              {/* Create Link Button */}
              {!shareLink ? (
                <Button onClick={handleCreateShareLink} className="w-full">
                  <Link2 className="h-4 w-4 mr-2" />
                  Generate Share Link
                </Button>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                    <Input
                      value={shareLink}
                      readOnly
                      className="flex-1 font-mono text-sm"
                    />
                    <Button size="sm" onClick={handleCopyLink}>
                      {copied ? (
                        <>
                          <Check className="h-4 w-4 mr-2" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy
                        </>
                      )}
                    </Button>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Shield className="h-4 w-4" />
                      {linkPermissions.can_edit ? 'Can edit' : 'View only'}
                    </div>
                    {expiresInDays && (
                      <div className="flex items-center gap-1">
                        <Calendar className="h-4 w-4" />
                        Expires in {expiresInDays} days
                      </div>
                    )}
                    {maxUses && (
                      <div className="flex items-center gap-1">
                        <Users className="h-4 w-4" />
                        {maxUses} uses max
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Existing Shares */}
              {existingShares.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Active Share Links</Label>
                  {existingShares.map((share) => (
                    <div
                      key={share.share_id}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {share.share_link}
                        </p>
                        <div className="flex items-center gap-3 mt-1">
                          <Badge variant="secondary" className="text-xs">
                            {share.use_count} uses
                          </Badge>
                          {share.expires_at && (
                            <span className="text-xs text-muted-foreground">
                              Exp: {new Date(share.expires_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRevokeShare(share.share_id)}
                      >
                        Revoke
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

          {/* Email Invite Tab */}
          <TabsContent value="email" className="space-y-4 mt-4">
            <div className="space-y-4">
              <div>
                <Label htmlFor="emails">Email Addresses</Label>
                <Input
                  id="emails"
                  type="email"
                  placeholder="user1@example.com, user2@example.com"
                  value={emailAddresses}
                  onChange={(e) => setEmailAddresses(e.target.value)}
                  className="mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Separate multiple emails with commas
                </p>
              </div>

              <div>
                <Label htmlFor="message">Personal Message (Optional)</Label>
                <Textarea
                  id="message"
                  placeholder="Hi! I'd like to share this workflow with you..."
                  value={emailMessage}
                  onChange={(e) => setEmailMessage(e.target.value)}
                  rows={4}
                  className="mt-1"
                />
              </div>

              <Button onClick={handleSendEmailInvites} className="w-full">
                <Mail className="h-4 w-4 mr-2" />
                Send Invites
              </Button>

              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">
                  <strong>Note:</strong> Email invites will be sent with a unique access link.
                  Recipients will be able to view and edit the workflow based on the
                  permissions you specify.
                </p>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ShareWorkflowModal;
