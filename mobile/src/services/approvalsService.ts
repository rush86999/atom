/**
 * Approvals Service
 *
 * Round 80s — mobile parity for the HITL approval journey (web approvals.tsx
 * + R81i supervisor panel). Supervisors can review pending workflow
 * approvals and approve/reject them from the device.
 *
 * Backend contract (api/agent_governance_routes.py):
 *   GET  /api/agent-governance/pending-approvals  {pending_approvals, count}
 *   POST /api/agent-governance/approve/{id}       RBAC: TEAM_LEAD+
 *   POST /api/agent-governance/reject/{id}        RBAC: TEAM_LEAD+
 */

import apiService from './api';

export interface PendingApproval {
  id?: string;
  approval_id?: string;
  agent_id?: string;
  agent_name?: string;
  workflow_name?: string;
  requested_by?: string;
  maturity_level?: string;
  status?: string;
  created_at?: string;
  [key: string]: any;
}

const approvalId = (a: PendingApproval): string =>
  a.id || a.approval_id || '';

export async function getPendingApprovals(): Promise<PendingApproval[]> {
  const response = await apiService.get<{ pending_approvals: PendingApproval[]; count: number }>(
    '/api/agent-governance/pending-approvals'
  );
  if (response.success && response.data) {
    return response.data.pending_approvals || [];
  }
  throw new Error(response.error || 'Failed to fetch pending approvals');
}

export async function approveWorkflow(approvalId: string): Promise<void> {
  const id = approvalId || '';
  if (!id) throw new Error('Missing approval id');
  const response = await apiService.post(`/api/agent-governance/approve/${id}`);
  if (!response.success) {
    throw new Error(response.error || 'Failed to approve');
  }
}

export async function rejectWorkflow(approvalId: string): Promise<void> {
  const id = approvalId || '';
  if (!id) throw new Error('Missing approval id');
  const response = await apiService.post(`/api/agent-governance/reject/${id}`);
  if (!response.success) {
    throw new Error(response.error || 'Failed to reject');
  }
}

export { approvalId };
