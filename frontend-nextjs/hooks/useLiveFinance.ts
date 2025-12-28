import { useState, useEffect } from 'react';

export interface UnifiedTransaction {
    id: string;
    description: string;
    amount: number;
    currency: string;
    date: string;
    status: string;
    platform: 'stripe' | 'xero' | 'quickbooks' | 'zoho' | 'dynamics';
    customer_name?: string;
    url?: string;
}

export interface FinanceStats {
    total_revenue: number;
    pending_revenue: number;
    transaction_count: number;
    platform_breakdown: Record<string, number>;
}

interface LiveFinanceResponse {
    ok: boolean;
    stats: FinanceStats;
    transactions: UnifiedTransaction[];
    providers: Record<string, boolean>;
}

export function useLiveFinance() {
    const [transactions, setTransactions] = useState<UnifiedTransaction[]>([]);
    const [stats, setStats] = useState<FinanceStats>({
        total_revenue: 0,
        pending_revenue: 0,
        transaction_count: 0,
        platform_breakdown: {}
    });
    const [isLoading, setIsLoading] = useState(true);
    const [activeProviders, setActiveProviders] = useState<Record<string, boolean>>({});

    const fetchLiveFinance = async () => {
        try {
            const res = await fetch('/api/atom/finance/live/overview');
            if (res.ok) {
                const data: LiveFinanceResponse = await res.json();
                setTransactions(data.transactions);
                setStats(data.stats);
                setActiveProviders(data.providers);
            }
        } catch (error) {
            console.error("Failed to fetch live finance data:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLiveFinance();

        // Poll every 60s
        const interval = setInterval(fetchLiveFinance, 60000);
        return () => clearInterval(interval);
    }, []);

    return {
        transactions,
        stats,
        isLoading,
        activeProviders,
        refresh: fetchLiveFinance
    };
}
