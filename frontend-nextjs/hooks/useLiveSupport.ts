import { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Ticket {
    id: string;
    subject: string;
    status: 'Open' | 'Pending' | 'Closed';
    priority: 'High' | 'Medium' | 'Low';
    platform: 'zendesk' | 'freshdesk' | 'intercom';
    customer: string;
}

export function useLiveSupport() {
    const [tickets, setTickets] = useState<Ticket[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchTickets = useCallback(async () => {
        try {
            setIsLoading(true);
            setError(null);
            const response = await fetch(`${API_BASE}/api/atom/communication/live/support/tickets`);
            if (response.ok) {
                const data = await response.json();
                setTickets(Array.isArray(data.tickets) ? data.tickets : (Array.isArray(data) ? data : []));
            } else {
                setError(`HTTP ${response.status}`);
                setTickets([]);
            }
        } catch (err) {
            console.error('Failed to fetch support tickets:', err);
            setError(err instanceof Error ? err.message : 'Failed to load');
            setTickets([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTickets();
    }, [fetchTickets]);

    return {
        tickets,
        isLoading,
        error,
        refresh: fetchTickets
    };
}
