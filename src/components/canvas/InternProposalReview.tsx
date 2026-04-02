/**
 * Intern Proposal Review Component
 *
 * Interface for reviewing intern agent proposals (for autonomous agents or users).
 */

'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Check, X, FileText, Shield } from 'lucide-react';

interface ProposalData {
    id: string;
    tenant_id: string;
    user_id: string;
    agent_id: string;
    proposal_type: 'action' | 'workflow' | 'analysis';
    proposal_data: any;
    status: string;
    approver_type: string;
    approver_id: string;
    approval_reason: string | null;
    confidence_score: number | null;
    risk_assessment: string | null;
    suggested_modifications: string | null;
    category: string | null;
    created_at: string;
    reviewed_at: string | null;
}

interface InternProposalReviewProps {
    proposalId: string;
    onApproved?: (proposalId: string) => void;
    onRejected?: (proposalId: string) => void;
    onComplete?: () => void;
}

/**
 * Proposal review interface for intern agents
 *
 * Shows proposal details and allows approval/rejection.
 *
 * @example
 * ```tsx
 * <InternProposalReview
 *   proposalId="prop-123"
 *   onApproved={(id) => console.log('Approved:', id)}
 *   onRejected={(id) => console.log('Rejected:', id)}
 * />
 * ```
 */
export function InternProposalReview({
    proposalId,
    onApproved,
    onRejected,
    onComplete
}: InternProposalReviewProps) {
    const [proposal, setProposal] = useState<ProposalData | null>(null);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [reason, setReason] = useState('');
    const [confidence, setConfidence] = useState(0.8);

    // Fetch proposal details
    useEffect(() => {
        const fetchProposal = async () => {
            try {
                const response = await fetch(`/api/proposals/${proposalId}`);
                if (response.ok) {
                    const data = await response.json();
                    setProposal(data);
                }
            } catch (error) {
                console.error('[InternProposalReview] Failed to fetch proposal:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchProposal();
    }, [proposalId]);

    /**
     * Approve proposal
     */
    const handleApprove = async () => {
        if (!proposal) return;

        setProcessing(true);

        try {
            const response = await fetch(`/api/proposals/${proposalId}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reason: reason || null,
                    confidence: confidence
                })
            });

            if (response.ok) {
                onApproved?.(proposalId);
            } else {
                throw new Error('Failed to approve proposal');
            }
        } catch (error) {
            console.error('[InternProposalReview] Failed to approve:', error);
        } finally {
            setProcessing(false);
        }
    };

    /**
     * Reject proposal
     */
    const handleReject = async () => {
        if (!proposal) return;

        if (!reason.trim()) {
            alert('Please provide a reason for rejection');
            return;
        }

        setProcessing(true);

        try {
            const response = await fetch(`/api/proposals/${proposalId}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    reason,
                    confidence: confidence,
                    suggested_modifications: null
                })
            });

            if (response.ok) {
                onRejected?.(proposalId);
            } else {
                throw new Error('Failed to reject proposal');
            }
        } catch (error) {
            console.error('[InternProposalReview] Failed to reject:', error);
        } finally {
            setProcessing(false);
        }
    };

    if (loading) {
        return (
            <Card className="p-4">
                <p className="text-sm text-gray-500">Loading proposal...</p>
            </Card>
        );
    }

    if (!proposal) {
        return (
            <Card className="p-4">
                <p className="text-sm text-red-500">Failed to load proposal</p>
            </Card>
        );
    }

    return (
        <Card className="p-4 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    <h3 className="font-semibold">Intern Agent Proposal</h3>
                    <Badge variant="outline">{proposal.proposal_type}</Badge>
                    {proposal.category && (
                        <Badge variant="secondary">{proposal.category}</Badge>
                    )}
                </div>
            </div>

            {/* Proposal data */}
            <div className="space-y-2">
                <Label className="text-sm font-medium">Proposal Details</Label>
                <ScrollArea className="h-32 w-full rounded-md border bg-gray-50 dark:bg-gray-900 p-3">
                    <pre className="text-xs font-mono">
                        {JSON.stringify(proposal.proposal_data, null, 2)}
                    </pre>
                </ScrollArea>
            </div>

            {/* Review form */}
            <div className="space-y-3">
                <div>
                    <Label htmlFor="reason">Reason (required for rejection)</Label>
                    <Textarea
                        id="reason"
                        placeholder="Provide reason for approval or rejection..."
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        rows={3}
                    />
                </div>

                <div>
                    <Label htmlFor="confidence">Confidence: {confidence.toFixed(2)}</Label>
                    <input
                        id="confidence"
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={confidence}
                        onChange={(e) => setConfidence(parseFloat(e.target.value))}
                        className="w-full"
                    />
                </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
                <Button
                    variant="default"
                    className="flex-1 gap-1"
                    onClick={handleApprove}
                    disabled={processing}
                >
                    <Check className="w-4 h-4" />
                    Approve
                </Button>
                <Button
                    variant="destructive"
                    className="flex-1 gap-1"
                    onClick={handleReject}
                    disabled={processing}
                >
                    <X className="w-4 h-4" />
                    Reject
                </Button>
            </div>

            {/* Metadata */}
            <div className="text-xs text-gray-500 space-y-1">
                <p>Agent ID: {proposal.agent_id}</p>
                <p>Created: {new Date(proposal.created_at).toLocaleString()}</p>
            </div>
        </Card>
    );
}

export default InternProposalReview;
