import { useState, useCallback } from 'react';
import { toast } from 'sonner';

export interface SearchResult {
    id: string;
    content: string;
    sender: string;
    timestamp: string;
    app_type: string;
}

export function useCommunicationSearch() {
    const [results, setResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    const searchMessages = useCallback(async (query: string) => {
        if (!query.trim()) {
            setResults([]);
            return;
        }

        setIsSearching(true);
        try {
            const res = await fetch(`/api/atom/communication/memory/search?query=${encodeURIComponent(query)}&limit=20`);
            if (res.ok) {
                const data = await res.json();
                if (data.success && data.results) {
                    setResults(data.results);
                } else {
                    setResults([]);
                }
            } else {
                console.error("Search failed");
                toast.error("Failed to search messages");
            }
        } catch (error) {
            console.error("Search error:", error);
            toast.error("Error searching messages");
        } finally {
            setIsSearching(false);
        }
    }, []);

    return {
        results,
        isSearching,
        searchMessages
    };
}
