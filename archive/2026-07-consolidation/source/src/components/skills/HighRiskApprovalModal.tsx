/**
 * HighRiskApprovalModal Component
 *
 * Modal for approving HIGH_RISK OpenClaw skills.
 * Follows HITL (Human-in-the-Loop) approval pattern.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { SafetyBadge } from './SafetyBadge';
import {
  requestApproval,
  checkApprovalStatus,
  submitAdminApproval,
  ApprovalResponse,
} from '@/lib/openclaw/openclaw-approvals';
import { AlertTriangle, Shield, Check, X, Loader2 } from 'lucide-react';

interface HighRiskApprovalModalProps {
  skillId: string;
  skillName: string;
  safetyFindings: string[];
  criticalPatterns?: string[];
  isOpen: boolean;
  onClose: () => void;
  onApproved?: () => void;
  isAdmin?: boolean;
  userId?: string;
}

export function HighRiskApprovalModal({
  skillId,
  skillName,
  safetyFindings,
  criticalPatterns = [],
  isOpen,
  onClose,
  onApproved,
  isAdmin = false,
  userId,
}: HighRiskApprovalModalProps) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [existingApproval, setExistingApproval] = useState<ApprovalResponse | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Check if approval already exists
      checkApprovalStatus(skillId).then(setExistingApproval);
    }
  }, [isOpen, skillId]);

  const handleRequestApproval = async () => {
    if (!userId || !acknowledged) return;

    setLoading(true);
    try {
      await requestApproval(skillId, userId, reason);
      onApproved?.();
      onClose();
    } catch (err) {
      console.error('Failed to request approval:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdminApprove = async () => {
    if (!userId || !acknowledged) return;

    setLoading(true);
    try {
      await submitAdminApproval(skillId, userId, true, reason);
      onApproved?.();
      onClose();
    } catch (err) {
      console.error('Failed to approve:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdminReject = async () => {
    if (!userId) return;

    setLoading(true);
    try {
      await submitAdminApproval(skillId, userId, false, reason || 'Not approved');
      onClose();
    } catch (err) {
      console.error('Failed to reject:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b bg-orange-50">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-orange-600" />
            <div>
              <h2 className="text-lg font-semibold text-orange-900">
                High Risk Skill Approval Required
              </h2>
              <p className="text-sm text-orange-700">{skillName}</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Warning message */}
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
            <div className="flex items-start gap-2">
              <Shield className="w-5 h-5 text-orange-600 mt-0.5" />
              <div className="text-sm text-orange-800">
                <p className="font-semibold mb-1">Security Warning</p>
                <p>
                  This skill has been classified as <strong>HIGH RISK</strong> and may
                  perform sensitive operations. Review the security findings below before
                  proceeding.
                </p>
              </div>
            </div>
          </div>

          {/* Safety findings */}
          {safetyFindings.length > 0 && (
            <div>
              <Label className="text-sm font-medium">Security Findings</Label>
              <ScrollArea className="h-32 w-full mt-2 rounded-md border bg-gray-50 p-3">
                <ul className="space-y-1 text-sm">
                  {safetyFindings.map((finding, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-orange-600">•</span>
                      <span>{finding}</span>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            </div>
          )}

          {/* Critical patterns */}
          {criticalPatterns.length > 0 && (
            <div>
              <Label className="text-sm font-medium">Critical Patterns Detected</Label>
              <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                <ul className="space-y-1 text-sm text-red-800">
                  {criticalPatterns.map((pattern, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-red-600">✕</span>
                      <span>{pattern}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Existing approval status */}
          {existingApproval && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="outline">{existingApproval.status}</Badge>
                <span className="text-blue-800">
                  {existingApproval.status === 'APPROVED'
                    ? `Approved by ${existingApproval.approved_by}`
                    : 'Awaiting admin approval'}
                </span>
              </div>
            </div>
          )}

          {/* Reason input */}
          <div>
            <Label htmlFor="reason">Reason {isAdmin ? '(for approval/rejection)' : '(optional)'}</Label>
            <Textarea
              id="reason"
              placeholder={isAdmin ? 'Provide reason for your decision...' : 'Why do you need this skill?'}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="mt-1"
            />
          </div>

          {/* Acknowledgment checkbox */}
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="rounded mt-1"
            />
            <span className="text-sm text-gray-700">
              I acknowledge the security risks and accept responsibility for activating
              this skill. I understand that this skill may perform operations that
              require careful oversight.
            </span>
          </label>
        </div>

        {/* Actions */}
        <div className="p-6 border-t bg-gray-50 flex gap-3">
          {/* Non-admin: Request approval button */}
          {!isAdmin && (
            <>
              <Button
                variant="outline"
                onClick={onClose}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant="default"
                onClick={handleRequestApproval}
                disabled={!acknowledged || loading}
                className="flex-1 bg-orange-600 hover:bg-orange-700"
              >
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Request Approval
              </Button>
            </>
          )}

          {/* Admin: Approve/Reject buttons */}
          {isAdmin && (
            <>
              <Button
                variant="outline"
                onClick={handleAdminReject}
                disabled={loading}
                className="flex-1 border-red-200 text-red-600 hover:bg-red-50"
              >
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <X className="w-4 h-4 mr-2" />}
                Reject
              </Button>
              <Button
                variant="default"
                onClick={handleAdminApprove}
                disabled={!acknowledged || loading}
                className="flex-1 bg-green-600 hover:bg-green-700"
              >
                {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Check className="w-4 h-4 mr-2" />}
                Approve
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default HighRiskApprovalModal;
