import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import EventSourcePicker from '../EventSourcePicker';
import NodeConfigSidebar from '../NodeConfigSidebar';
jest.mock('../VariablePicker', () => () => null);
jest.mock('../ManageConnectionsModal', () => () => null);
const binding = { connection_id: 'mail/one', source: 'outlook', event_type: 'message.created', enabled: true };
const row = { connection_id: 'mail/one', name: 'My inbox', source: 'outlook', events: [{ key: 'message.created', label: 'New email' }], registration: null };
const reply = (body: any, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => body } as Response);
let wire: jest.Mock;
beforeEach(() => {
    localStorage.setItem('auth_token', 'synthetic-session');
    wire = jest.fn().mockResolvedValue(reply({ callback_configured: true, sources: [row] }));
    global.fetch = wire;
});
afterEach(() => localStorage.clear());
it('edits the real sidebar, enrolls explicitly once, and reloads its saved binding', async () => {
    const change = jest.fn();
    const node = { id: 'stable-trigger', type: 'trigger', data: { serviceId: 'workflow_event', label: 'Connected event', config: {} } };
    const view = render(<NodeConfigSidebar selectedNode={node} allNodes={[node]} onUpdateNode={change} onClose={jest.fn()} />);
    await screen.findByRole('option', { name: 'My inbox' });
    expect(wire).toHaveBeenCalledTimes(1);
    expect(new Headers(wire.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer synthetic-session');
    fireEvent.change(screen.getByLabelText('Event connection'), { target: { value: row.connection_id } });
    fireEvent.change(screen.getByLabelText('Event'), { target: { value: 'message.created' } });
    const saved = change.mock.calls.at(-1)[1].config.event_subscription;
    expect(saved).toEqual(binding);
    wire.mockResolvedValueOnce(reply({ status: 'registered' })).mockResolvedValue(reply({ callback_configured: true,
        sources: [{ ...row, registration: { phase: 'registered', enabled: true } }] }));
    fireEvent.click(screen.getByRole('button', { name: 'Connect event delivery' }));
    await screen.findByText('Event delivery registered');
    expect(wire.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
    expect(wire.mock.calls[1][0]).toBe('/api/v1/workflows/event-sources/mail%2Fone/enroll');
    expect(wire.mock.calls[1][1].body).toBe('{}');
    view.unmount();
    render(<NodeConfigSidebar selectedNode={{ ...node, data: { ...node.data, config: { event_subscription: saved } } }} allNodes={[node]} onUpdateNode={change} onClose={jest.fn()} />);
    await screen.findByText('Event delivery registered');
    expect(screen.getByLabelText('Event connection')).toHaveValue(binding.connection_id);
    expect(screen.getByLabelText('Event')).toHaveValue('message.created');
});
it('clears old event material on connection change', async () => {
    wire.mockResolvedValue(reply({ callback_configured: true, sources: [row, { ...row, connection_id: 'second', source: 'microsoft365', name: 'Second' }] }));
    const change = jest.fn();
    render(<EventSourcePicker binding={binding} onChange={change} />);
    await screen.findByRole('option', { name: 'Second' });
    fireEvent.change(screen.getByLabelText('Event connection'), { target: { value: 'second' } });
    expect(change).toHaveBeenLastCalledWith({ connection_id: 'second', source: 'microsoft365', event_type: '', enabled: false });
    expect(screen.getByLabelText('Event')).toHaveValue('');
});
it.each(['effect_unknown', 'committed_unverified', 'transport'])('does not repeat after %s', async status => {
    render(<EventSourcePicker binding={binding} onChange={jest.fn()} />);
    await screen.findByRole('button', { name: 'Connect event delivery' });
    if (status === 'transport') wire.mockRejectedValueOnce(new Error('disconnected'));
    else wire.mockResolvedValueOnce(reply({ status, do_not_repeat: true }, false));
    fireEvent.click(screen.getByRole('button', { name: 'Connect event delivery' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Connect event delivery' })).toBeDisabled());
    expect(wire.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
});
it('does not connect without callback configuration', async () => {
    wire.mockResolvedValue(reply({ callback_configured: false, sources: [row] }));
    render(<EventSourcePicker binding={binding} onChange={jest.fn()} />);
    await screen.findByRole('button', { name: 'Connect event delivery' });
    expect(screen.getByRole('button', { name: 'Connect event delivery' })).toBeDisabled();
    expect(wire).toHaveBeenCalledTimes(1);
});
it('does not substitute a peer for an unavailable saved connection', async () => {
    const change = jest.fn();
    render(<EventSourcePicker binding={{ ...binding, connection_id: 'removed' }} onChange={change} />);
    await screen.findByRole('alert');
    expect(change).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Connect event delivery' })).not.toBeInTheDocument();
});


it('explains that missing credentials need a reconnect without repeating setup', async () => {
    render(<EventSourcePicker binding={binding} onChange={jest.fn()} />);
    await screen.findByRole('button', { name: 'Connect event delivery' });
    wire.mockResolvedValueOnce(reply({ status: 'credentials_unavailable', do_not_repeat: true }, false));
    fireEvent.click(screen.getByRole('button', { name: 'Connect event delivery' }));
    await screen.findByText('Event delivery is waiting for connection credentials. Reconnect the account, then refresh source status.');
    expect(screen.getByRole('button', { name: 'Connect event delivery' })).toBeDisabled();
    expect(wire.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
});
