/** Actual serialized queue -> observed pass -> mounted modal; transport is controlled. */
import React from 'react';
import { render, act, fireEvent, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import NetInfo, { NetInfoStateType } from '@react-native-community/netinfo';
import { SyncProgressModal } from '../offline/SyncProgressModal';
import { offlineSyncService, SyncResult } from '../../services/offlineSyncService';
import { storageService } from '../../services/storageService';
import { apiService } from '../../services/api';
import { ApiResponse } from '../../types/common';

jest.mock('@react-native-community/netinfo', () => ({
  __esModule: true,
  default: { fetch: jest.fn(), addEventListener: jest.fn(() => jest.fn()) },
  NetInfoStateType: { unknown: 'unknown' },
}));
jest.mock('../../services/api', () => ({ apiService: { post: jest.fn() } }));

describe('actual sync producer and modal result join', () => {
  beforeEach(async () => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    jest.mocked(apiService.post).mockReset();
    await storageService.clear();
    jest.mocked(NetInfo.fetch).mockResolvedValue({
      type: NetInfoStateType.unknown, isConnected: true, isInternetReachable: null, details: null,
    });
    await offlineSyncService.initialize();
  });
  afterEach(() => {
    offlineSyncService.destroy();
    jest.clearAllTimers();
    jest.useRealTimers();
  });
  const add = () => offlineSyncService.queueAction('agent_message', {
    agentId: 'controlled-agent', message: 'controlled local pass',
  }, 'low', 'controlled-user', 'controlled-device');

  test('observed result reaches the modal once without invented totals', async () => {
    const id = await add();
    let accept!: (value: ApiResponse<unknown>) => void;
    jest.mocked(apiService.post).mockImplementationOnce(() => new Promise(resolve => { accept = resolve; }));
    const completed = jest.fn();
    const screen = render(<NavigationContainer><SyncProgressModal visible onComplete={completed} /></NavigationContainer>);
    let running!: Promise<SyncResult>;
    act(() => { running = offlineSyncService.triggerSync(); });
    await act(async () => { await jest.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('Syncing Data')).toBeTruthy();
    expect(screen.getByText('Other')).toBeTruthy();
    expect(screen.getByText('0/1')).toBeTruthy();
    expect(screen.queryByText('Agents')).toBeNull();
    expect(screen.queryByText('Sync Complete')).toBeNull();
    let result!: SyncResult;
    await act(async () => { accept({ success: true, data: {} }); result = await running; });
    await waitFor(() => expect(screen.getByText('Sync Complete')).toBeTruthy());
    expect(screen.getByText('1 item synced')).toBeTruthy();
    expect((await offlineSyncService.getSyncState()).cycle?.actionIds).toEqual([id]);
    fireEvent.press(screen.getByText('Done'));
    fireEvent.press(screen.getByText('Done'));
    expect(completed).toHaveBeenCalledTimes(1);
    expect(completed).toHaveBeenCalledWith(expect.objectContaining({ cycleId: result.cycleId, synced: 1, bytesTransferred: result.bytesTransferred }));
    await act(async () => { await add(); });
    await waitFor(() => expect(screen.queryByText('Sync Complete')).toBeNull());
    expect(completed).toHaveBeenCalledTimes(1);
  });

  test('a refused transport produces an incomplete observed pass, not a completion callback', async () => {
    await add();
    jest.mocked(apiService.post).mockResolvedValue({ success: false, error: 'controlled refusal' });
    const completed = jest.fn();
    const screen = render(<NavigationContainer><SyncProgressModal visible onComplete={completed} /></NavigationContainer>);
    await act(async () => { await offlineSyncService.triggerSync(); });
    await waitFor(() => expect(screen.getByText('Sync Incomplete')).toBeTruthy());
    expect(screen.getByText('1 item failed')).toBeTruthy();
    expect(screen.queryByText('Sync Complete')).toBeNull();
    expect((await offlineSyncService.getSyncState()).pendingCount).toBe(1);
    fireEvent.press(screen.getByText('Done'));
    expect(completed).not.toHaveBeenCalled();
  });
});
