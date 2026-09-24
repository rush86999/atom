import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

jest.mock('../../lib/maturity-api', () => ({
  listActionProposals: jest.fn(),
  approveActionProposal: jest.fn(),
  rejectActionProposal: jest.fn(),
}));

import {
  approveActionProposal,
  listActionProposals,
  rejectActionProposal,
} from '../../lib/maturity-api';
import {
  ACTION_PROPOSALS_QUERY_KEY,
  ACTION_PROPOSALS_REFETCH_INTERVAL,
  ACTION_PROPOSALS_STALE_TIME,
  useActionProposals,
} from '../useActionProposals';

const mockedList = listActionProposals as jest.Mock;
const mockedApprove = approveActionProposal as jest.Mock;
const mockedReject = rejectActionProposal as jest.Mock;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  mockedList.mockReset();
  mockedApprove.mockReset();
  mockedReject.mockReset();
});

describe('useActionProposals', () => {
  test('keeps loading and authoritative-empty distinct', async () => {
    let resolveList: (value: unknown[]) => void = () => {};
    mockedList.mockImplementation(() => new Promise((resolve) => {
      resolveList = resolve;
    }));
    const queryClient = createQueryClient();
    const { result } = renderHook(
      () => useActionProposals({ statusFilter: 'pending_approval', limit: 10 }),
      { wrapper: createWrapper(queryClient) }
    );

    expect(result.current.isPending).toBe(true);
    expect(result.current.pendingCount).toBeNull();
    expect(result.current.isAuthoritativeEmpty).toBe(false);

    await act(async () => {
      resolveList([]);
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.pendingCount).toBe(0);
    expect(result.current.isAuthoritativeEmpty).toBe(true);
  });

  test.each([401, 500])('keeps a failed request distinct from an empty result (%s)', async (status) => {
    mockedList.mockRejectedValue(new Error(`Action proposal list failed (${status})`));
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useActionProposals(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.pendingCount).toBeNull();
    expect(result.current.isAuthoritativeEmpty).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  test('returns only pending proposals for the count', async () => {
    mockedList.mockResolvedValue([
      { id: 'p1', status: 'pending_approval' },
      { id: 'p2', status: 'pending' },
      { id: 'p3', status: 'approved' },
    ]);
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useActionProposals(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.pendingCount).toBe(2);
    expect(result.current.pendingProposals?.map((proposal) => proposal.id)).toEqual(['p1', 'p2']);
  });

  test('cancels a stale request when its query key changes', async () => {
    const signals: AbortSignal[] = [];
    const resolvers: Array<(value: unknown[]) => void> = [];
    mockedList.mockImplementation(({ signal }: { signal: AbortSignal }) => new Promise((resolve) => {
      signals.push(signal);
      resolvers.push(resolve);
    }));
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ agentId }: { agentId: string }) => useActionProposals({ agentId, limit: 10 }),
      {
        initialProps: { agentId: 'agent-a' },
        wrapper: createWrapper(queryClient),
      }
    );

    await waitFor(() => expect(signals).toHaveLength(1));
    rerender({ agentId: 'agent-b' });
    await waitFor(() => expect(signals[0].aborted).toBe(true));
    expect(signals[1].aborted).toBe(false);

    await act(async () => {
      resolvers[0]([{ id: 'old', status: 'pending_approval' }]);
      resolvers[1]([{ id: 'new', status: 'pending_approval' }]);
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.data?.[0]?.id).toBe('new'));
  });

  test('uses bounded foreground polling and invalidates after both decisions', async () => {
    mockedList.mockResolvedValue([]);
    mockedApprove.mockResolvedValue({ execution_result: { success: true } });
    mockedReject.mockResolvedValue(undefined);
    const queryClient = createQueryClient();
    const { result } = renderHook(
      () => useActionProposals({ statusFilter: 'pending_approval', limit: 10 }),
      { wrapper: createWrapper(queryClient) }
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const query = queryClient.getQueryCache().findAll({ queryKey: ACTION_PROPOSALS_QUERY_KEY })[0];
    const options = query?.options as any;
    expect(options?.staleTime).toBe(ACTION_PROPOSALS_STALE_TIME);
    expect(options?.refetchInterval).toBe(ACTION_PROPOSALS_REFETCH_INTERVAL);
    expect(options?.refetchIntervalInBackground).toBe(false);

    await act(async () => {
      await result.current.approveMutation.mutateAsync({ proposalId: 'p1' });
    });
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2));

    await act(async () => {
      await result.current.rejectMutation.mutateAsync({ proposalId: 'p1', reason: 'not now' });
    });
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(3));
  });
});
