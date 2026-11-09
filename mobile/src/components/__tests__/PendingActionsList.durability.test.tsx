/** Real queue/storage consumer; UI reads are detached serialized snapshots. */
import React from 'react';
import { Alert } from 'react-native';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react-native';
import { PendingActionsList } from '../offline/PendingActionsList';
import { offlineSyncService, OfflineAction } from '../../services/offlineSyncService';
import { storageService } from '../../services/storageService';

jest.mock('@react-navigation/native', () => ({ useTheme: () => ({ colors: { primary: '#2196F3', background: '#fff', card: '#fff', text: '#000', border: '#ccc', notification: '#f00' } }) }));
jest.mock('@react-native-community/netinfo', () => ({ __esModule: true, default: { fetch: jest.fn().mockResolvedValue({ type: 'unknown', isConnected: false, isInternetReachable: false, details: null }), addEventListener: jest.fn(() => jest.fn()) } }));
jest.mock('../../services/api', () => ({ apiService: { post: jest.fn() } }));

function readQueue(): OfflineAction[] {
  const raw = storageService.getString('offline_queue');
  return raw ? JSON.parse(raw) : [];
}

describe('PendingActionsList durable consumer contract', () => {
  beforeEach(async () => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    await storageService.clear();
    await offlineSyncService.initialize();
    const action: OfflineAction = { id: 'controlled-action', type: 'agent_message', payload: { agentId: 'controlled-agent', message: 'controlled intent' }, priority: 2, priorityLevel: 'low', status: 'failed', syncAttempts: 3, createdAt: new Date(), userId: 'controlled-user', deviceId: 'controlled-device' };
    await storageService.setString('offline_queue', JSON.stringify([action]));
  });
  afterEach(() => {
    cleanup();
    offlineSyncService.destroy();
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('retry persists the actual failed row before requesting sync', async () => {
    render(<PendingActionsList />);
    fireEvent.press(await screen.findByTestId('icon-refresh'));
    await waitFor(() => expect(readQueue()[0]).toEqual(expect.objectContaining({ id: 'controlled-action', syncAttempts: 0, status: 'pending' })));
  });

  test('priority changes survive a fresh serialized read', async () => {
    render(<PendingActionsList />);
    fireEvent.press(await screen.findByTestId('icon-arrow-up'));
    await waitFor(() => expect(readQueue()[0].priority).toBe(4));
  });

  test('confirmed delete removes only its selected durable row', async () => {
    const original = readQueue()[0];
    await storageService.setString('offline_queue', JSON.stringify([original, { ...original, id: 'controlled-peer', type: 'feedback', status: 'pending' }]));
    const alerts = jest.spyOn(Alert, 'alert');
    render(<PendingActionsList />);
    fireEvent.press((await screen.findAllByTestId('icon-trash'))[0]);
    const buttons = alerts.mock.calls[0]?.[2];
    const confirm = buttons?.find((b) => b.text === 'Delete');
    if (!confirm?.onPress) throw new Error('missing controlled confirmation');
    await act(async () => { confirm.onPress?.(); });
    await waitFor(() => expect(readQueue().map((a) => a.id)).toEqual(['controlled-peer']));
  });
  test('a failed retry write leaves durable work failed and dispatches no sync', async () => {
    const sync = jest.spyOn(offlineSyncService, 'triggerSync');
    const alerts = jest.spyOn(Alert, 'alert');
    render(<PendingActionsList />);
    const retry = await screen.findByTestId('icon-refresh');
    jest.spyOn(storageService, 'setString').mockResolvedValueOnce(false);
    fireEvent.press(retry);
    await waitFor(() => expect(alerts).toHaveBeenCalledWith('Error', 'Failed to retry action'));
    expect(readQueue()[0]).toEqual(expect.objectContaining({ status: 'failed', syncAttempts: 3 }));
    expect(sync).not.toHaveBeenCalled();
  });

  test('unreadable retained work is not shown as all caught up', async () => {
    await storageService.setString('offline_queue', '{controlled-retained-broken');
    render(<PendingActionsList />);
    expect(await screen.findByText('Pending actions unavailable')).toBeTruthy();
    expect(screen.queryByText('All Caught Up!')).toBeNull();
    expect(storageService.getString('offline_queue')).toBe('{controlled-retained-broken');
  });

});
