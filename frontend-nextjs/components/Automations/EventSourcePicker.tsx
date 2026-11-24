import React, { useEffect, useRef, useState } from 'react';
import { authFetch } from '@/lib/auth-headers';
import { Button } from '@/components/ui/button';

export interface EventBinding {
    connection_id: string;
    source: string;
    event_type: string;
    enabled: boolean;
}
interface Source {
    connection_id: string;
    name: string;
    source: string;
    events: { key: string; label: string }[];
    registration: { phase: string; enabled: boolean } | null;
}
const endpoint = '/api/v1/workflows/event-sources';

/** Native event choices come from the backend; piece labels are not delivery proof. */
export default function EventSourcePicker({ binding, onChange }: {
    binding?: EventBinding; onChange: (binding: EventBinding) => void;
}) {
    const [sources, setSources] = useState<Source[]>([]);
    const [connection, setConnection] = useState(binding?.connection_id || '');
    const [configured, setConfigured] = useState(false);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState('');
    const [uncertain, setUncertain] = useState<Record<string, boolean>>({});
    const mounted = useRef(true);
    const source = sources.find(row => row.connection_id === connection);
    const registered = source?.registration?.phase === 'registered' && source.registration.enabled;

    async function load() {
        const response = await authFetch(endpoint);
        if (!response.ok) throw new Error('Event sources are unavailable. Check your connection and permissions.');
        const data = await response.json();
        if (!Array.isArray(data.sources)) throw new Error('Event sources are unavailable.');
        if (mounted.current) {
            setSources(data.sources);
            setConfigured(data.callback_configured === true);
        }
    }
    useEffect(() => {
        mounted.current = true;
        load().catch(error => { if (mounted.current) setMessage(error.message); })
            .finally(() => { if (mounted.current) setLoading(false); });
        return () => { mounted.current = false; };
    }, []);

    async function enroll() {
        if (!source || busy || uncertain[connection]) return;
        const id = connection;
        setBusy(true);
        setMessage('');
        try {
            const response = await authFetch(`${endpoint}/${encodeURIComponent(id)}/enroll`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
            });
            const result = await response.json();
            if (!mounted.current) return;
            if (response.ok && ['registered', 'already_applied'].includes(result.status)) {
                setMessage('Event delivery is registered. Save the workflow to apply your trigger.');
                await load();
            } else if (result.status === 'credentials_unavailable') {
                setUncertain(previous => ({ ...previous, [id]: true }));
                setMessage('Event delivery is waiting for connection credentials. Reconnect the account, then refresh source status.');
            } else if (result.do_not_repeat || ['effect_unknown', 'committed_unverified'].includes(result.status)) {
                setUncertain(previous => ({ ...previous, [id]: true }));
                setMessage('Provider confirmation is pending. Do not reconnect; a verified delivery can reconcile the original setup.');
            } else {
                setMessage('Event delivery was not connected. Check the connection and server callback configuration.');
            }
        } catch {
            if (mounted.current) {
                setUncertain(previous => ({ ...previous, [id]: true }));
                setMessage('Setup confirmation was lost. Do not reconnect; refresh source status before continuing.');
            }
        } finally { if (mounted.current) setBusy(false); }
    }

    return <section aria-label="Connected event source" className="space-y-3 rounded border p-3">
        <h4 className="text-sm font-semibold">Connected event</h4>
        <p className="text-xs">Choose a supported event from one of your existing connections.</p>
        {loading ? <p role="status">Loading event sources…</p> : <>
            <label className="block text-xs">Event connection
                <select aria-label="Event connection" className="block w-full border rounded p-2" value={connection}
                    disabled={busy} onChange={event => {
                        const id = event.target.value;
                        setConnection(id); setMessage('');
                        const next = sources.find(row => row.connection_id === id);
                        // Clear the previous binding immediately; a different connection
                        // must never retain another connection's selected event.
                        onChange({ connection_id: id, source: next?.source || '', event_type: '', enabled: false });
                    }}>
                    <option value="">Select a connection</option>
                    {sources.map(row => <option key={row.connection_id} value={row.connection_id}>{row.name || row.source}</option>)}
                </select>
            </label>
            {sources.length === 0 && <p>No supported event connections are available.</p>}
            {binding?.connection_id && !source && <p role="alert">The saved event connection is unavailable. Select a current connection before saving.</p>}
            {source && <>
                <label className="block text-xs">Event
                    <select aria-label="Event" className="block w-full border rounded p-2"
                        value={binding?.connection_id === connection ? binding.event_type || '' : ''}
                        onChange={event => onChange({ connection_id: connection, source: source.source,
                            event_type: event.target.value, enabled: !!event.target.value })}>
                        <option value="">Select an event</option>
                        {source.events.map(event => <option key={event.key} value={event.key}>{event.label}</option>)}
                    </select>
                </label>
                <p role="status">{registered ? 'Event delivery registered' : 'Event delivery is not yet verified'}</p>
                {!registered && <Button type="button" disabled={!configured || busy || uncertain[connection]}
                    onClick={enroll}>{busy ? 'Connecting…' : 'Connect event delivery'}</Button>}
            </>}
            {!configured && <p>Event delivery needs a public HTTPS callback configured on this Atom server.</p>}
        </>}
        {message && <p role="status">{message}</p>}
    </section>;
}
