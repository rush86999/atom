'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  approveActionProposal,
  listActionProposals,
  rejectActionProposal,
  type ActionProposal,
  type ActionProposalApprovalResult,
} from '../lib/maturity-api';

export const ACTION_PROPOSALS_QUERY_KEY = ['maturity', 'action-proposals'] as const;
export const ACTION_PROPOSALS_STALE_TIME = 15_000;
export const ACTION_PROPOSALS_REFETCH_INTERVAL = 30_000;

export interface UseActionProposalsOptions {
  agentId?: string | null;
  statusFilter?: string;
  limit?: number;
  enabled?: boolean;
}

export interface ApproveActionProposalVariables {
  proposalId: string;
  modifications?: Record<string, unknown>;
}

export interface RejectActionProposalVariables {
  proposalId: string;
  reason: string;
}

export function useActionProposals({
  agentId,
  statusFilter,
  limit = 50,
  enabled = true,
}: UseActionProposalsOptions = {}) {
  const queryClient = useQueryClient();
  const query = useQuery<ActionProposal[]>({
    queryKey: [
      ...ACTION_PROPOSALS_QUERY_KEY,
      agentId ?? null,
      statusFilter ?? null,
      limit,
    ],
    queryFn: ({ signal }) =>
      listActionProposals({
        agentId: agentId ?? undefined,
        statusFilter,
        limit,
        signal,
      }),
    enabled: enabled && agentId !== null,
    staleTime: ACTION_PROPOSALS_STALE_TIME,
    refetchInterval: ACTION_PROPOSALS_REFETCH_INTERVAL,
    refetchIntervalInBackground: false,
  });

  const approveMutation = useMutation<ActionProposalApprovalResult, Error, ApproveActionProposalVariables>({
    mutationFn: ({ proposalId, modifications }) =>
      approveActionProposal(proposalId, modifications),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ACTION_PROPOSALS_QUERY_KEY }),
  });

  const rejectMutation = useMutation<void, Error, RejectActionProposalVariables>({
    mutationFn: ({ proposalId, reason }) =>
      rejectActionProposal(proposalId, reason),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ACTION_PROPOSALS_QUERY_KEY }),
  });

  const pendingProposals = query.isSuccess
    ? query.data.filter(
        (proposal) =>
          proposal.status === 'pending_approval' || proposal.status === 'pending'
      )
    : undefined;

  return {
    ...query,
    pendingProposals,
    pendingCount: pendingProposals?.length ?? null,
    isAuthoritativeEmpty: query.isSuccess && pendingProposals.length === 0,
    approveMutation,
    rejectMutation,
  };
}
