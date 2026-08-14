import { useState, useCallback, useRef } from 'react';
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

    // Request-token guard: prevents an out-of-order (stale) fetch from
    // overwriting newer results. Each searchMemory call increments the token;
    // only the latest call's results are applied (BUG-040).
    const requestIdRef = useRef(0);

    const searchMemory = useCallback(async (query: string) => {
        if (!query.trim()) {
            setResults([]);
            return;
        }

        const myRequestId = ++requestIdRef.current;
        setIsSearching(true);
        try {
            let url = `/api/atom/communication/memory/search?query=${encodeURIComponent(query)}&limit=${limit}`;
            if (tag) url += `&tag=${encodeURIComponent(tag)}`;
            if (appId) url += `&app_id=${encodeURIComponent(appId)}`;

            const res = await fetch(url);
            // Guard: discard this response if a newer search superseded it.
            if (myRequestId !== requestIdRef.current) return;

            if (res.ok) {
                const data = await res.json();
                if (myRequestId !== requestIdRef.current) return; // re-check after await
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
            // Guard: a superseded (stale) request's failure must not toast or
            // log — only the latest search's outcome is user-visible (BUG-040).
            if (myRequestId !== requestIdRef.current) return;
            console.error("Memory search error:", error);
            toast.error("Error searching historical data");
        } finally {
            if (myRequestId === requestIdRef.current) {
                setIsSearching(false);
            }
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
