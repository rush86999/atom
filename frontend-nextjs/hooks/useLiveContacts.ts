import { useState, useEffect } from 'react';

export interface Contact {
    id: string;
    name: string;
    provider: string;
    status: string;
    avatar: string;
}

export function useLiveContacts() {
    const [contacts, setContacts] = useState<Contact[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchContacts = async () => {
            try {
                const res = await fetch('/api/atom/communication/live/contacts/recent?limit=10');
                if (res.ok) {
                    const data = await res.json();
                    if (data.ok && data.contacts) {
                        setContacts(data.contacts);
                    }
                }
            } catch (error) {
                console.error('Failed to fetch contacts:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchContacts();

        // Poll every 60s
        const interval = setInterval(fetchContacts, 60000);
        return () => clearInterval(interval);
    }, []);

    return { contacts, loading };
}
