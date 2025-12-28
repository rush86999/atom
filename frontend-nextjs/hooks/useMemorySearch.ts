import { useState, useCallback } from 'react';
import { toast } from 'sonner';

export interface MemorySearchResult {
    id: string;
    content: string;
    sender: string;
    timestamp: string;
    app_type: string;
    subject?: string;
    tags?: string[];
    metadata?: any;
}

interface UseMemorySearchOptions {
    tag?: string;
    appId?: string;
    limit?: number;
}

export function useMemorySearch(options: UseMemorySearchOptions = {}) {
    const [results, setResults] = useState<MemorySearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const { tag, appId, limit = 20 } = options;

    const searchMemory = useCallback(async (query: string) => {
        if (!query.trim()) {
            setResults([]);
            return;
        }

        setIsSearching(true);
        try {
            let url = `/api/atom/communication/memory/search?query=${encodeURIComponent(query)}&limit=${limit}`;
            if (tag) url += `&tag=${encodeURIComponent(tag)}`;
            if (appId) url += `&app_id=${encodeURIComponent(appId)}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                if (data.success && data.results) {
                    setResults(data.results);
                } else {
                    setResults([]);
                }
            } else {
                console.error("Memory search failed");
                toast.error("Failed to search historical data");
            }
        } catch (error) {
            console.error("Memory search error:", error);
            toast.error("Error searching historical data");
        } finally {
            setIsSearching(false);
        }
    }, [tag, appId, limit]);

    const clearSearch = useCallback(() => {
        setResults([]);
    }, []);

    return {
        results,
        isSearching,
        searchMemory,
        clearSearch
    };
}
