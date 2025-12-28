import { useState, useEffect, useCallback } from 'react';

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

    const fetchTickets = useCallback(async () => {
        try {
            setIsLoading(true);
            // In a real implementation, we would fetch from a Live API
            // For now, mirroring the existing mock logic but in a hook
            const mockTickets: Ticket[] = [
                { id: 'TKT-991', subject: 'Cloud Sync Failed for Org #55', status: 'Open', priority: 'High', platform: 'zendesk', customer: 'Acme Corp' },
                { id: 'FR-22', subject: 'Billing Inquiry: Overcharged', status: 'Pending', priority: 'Medium', platform: 'freshdesk', customer: 'Bob Smith' },
                { id: 'IC-451', subject: 'How do I add a team member?', status: 'Closed', priority: 'Low', platform: 'intercom', customer: 'Sarah Lane' }
            ];

            // Artificial delay to simulate network
            await new Promise(resolve => setTimeout(resolve, 500));
            setTickets(mockTickets);
        } catch (error) {
            console.error('Failed to fetch support tickets:', error);
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
        refresh: fetchTickets
    };
}
