/**
 * FinanceCommandCenter WebSocket status_update filter tests.
 *
 * The dashboard subscribes to the shared `communication_stats` channel, which
 * carries status_update messages for ALL domains (projects, sales, finance).
 * Without a domain filter, FinanceCommandCenter refreshes + toasts on every
 * other domain's pipeline completion — wrong-data-source refresh and a
 * misleading "Refreshing finance data..." toast for unrelated syncs.
 *
 * The fix: only refresh when the status_update is relevant to finance
 * (data.pipeline === 'finance' or absent/unknown — be conservative).
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

// --- Mocks for the deep dependency tree ---

// `refresh` is a jest.fn so the tests can assert the filter decides whether a
// refresh happens at all.
const refreshSpy = jest.fn();

// --- WS mock -----------------------------------------------------------------
// Frames reach the component through the socket's `onMessage` listener, so the
// mock must deliver to listeners as well as to the state slot. tests/helpers/
// wsMock does both, and `wsMock().burst()` reproduces the case this component
// has to survive: many frames inside one render commit.
import { wsMock } from '../../../tests/helpers/wsMock';

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: require('../../../tests/helpers/wsMock').createWebSocketMock(),
}));

jest.mock('@/hooks/useLiveFinance', () => ({
  useLiveFinance: () => ({
    transactions: [],
    stats: { totalRevenue: 0, totalExpenses: 0, netIncome: 0, transactionCount: 0 },
    isLoading: false,
    activeProviders: [],
    refresh: refreshSpy,
  }),
  UnifiedTransaction: {},
}));

jest.mock('@/hooks/useMemorySearch', () => ({
  useMemorySearch: () => ({
    results: [],
    isSearching: false,
    searchMemory: jest.fn(),
    clearSearch: jest.fn(),
  }),
}));

jest.mock('@/components/shared/CommentSection', () => ({
  CommentSection: () => null,
}));

jest.mock('@/components/shared/PipelineSettingsPanel', () => ({
  PipelineSettingsPanel: () => null,
}));

import { FinanceCommandCenter } from '../FinanceCommandCenter';

describe('FinanceCommandCenter status_update filtering', () => {
  beforeEach(() => {
    refreshSpy.mockClear();
  });

  const sendMessage = (msg: any) => {
    act(() => { wsMock().emit(msg); });
  };

  it('does NOT refresh on a projects-pipeline status_update', () => {
    render(<FinanceCommandCenter />);
    expect(refreshSpy).not.toHaveBeenCalled();

    sendMessage({
      type: 'status_update',
      data: { pipeline: 'projects', status: 'completed' },
    });

    // A projects sync must not trigger a finance data refresh.
    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it('does NOT refresh on a sales-pipeline status_update', () => {
    render(<FinanceCommandCenter />);

    sendMessage({
      type: 'status_update',
      data: { pipeline: 'sales', status: 'completed' },
    });

    expect(refreshSpy).not.toHaveBeenCalled();
  });

  it('DOES refresh on a finance-pipeline status_update', () => {
    render(<FinanceCommandCenter />);

    sendMessage({
      type: 'status_update',
      data: { pipeline: 'finance', status: 'completed' },
    });

    expect(refreshSpy).toHaveBeenCalled();
  });
});
