import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

export interface KnowledgeItem {
    id: string;
    name: string;
    platform: string;
    type: 'file' | 'task' | 'deal' | 'ticket';
    modified_at?: string;
    status?: string;
    value?: number;
    priority?: string;
}

export interface SmartInsight {
    anomaly_id: string;
    severity: 'critical' | 'warning' | 'info';
    title: string;
    description: string;
    affected_entities: string[];
    platforms: string[];
    recommendation: string;
    timestamp: string;
}

export function useLiveKnowledge() {
    const [items, setItems] = useState<KnowledgeItem[]>([]);
    const [insights, setInsights] = useState<SmartInsight[]>([]);
    const [loading, setLoading] = useState(true);
    const [insightsLoading, setInsightsLoading] = useState(true);

    const fetchKnowledge = useCallback(async () => {
        try {
            setLoading(true);
            const response = await axios.get<{ status: string, entities: any[] }>('/api/intelligence/entities');
            if (response.data?.status === 'success') {
                const mappedItems: KnowledgeItem[] = response.data.entities.map(e => ({
                    id: e.id,
                    name: e.name,
                    platform: e.platforms[0] || 'unknown',
                    type: e.type,
                    status: e.status,
                    value: e.value,
                    modified_at: e.modified_at
                }));
                setItems(mappedItems);
            }
        } catch (error) {
            console.error('Failed to fetch knowledge:', error);
            toast.error('Failed to fetch real-time intelligence data');
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchInsights = useCallback(async () => {
        try {
            setInsightsLoading(true);
            const response = await axios.get<{ status: string, insights: SmartInsight[] }>('/api/intelligence/insights');
            if (response.data?.status === 'success') {
                setInsights(response.data.insights);
            }
        } catch (error) {
            console.error('Failed to fetch insights:', error);
        } finally {
            setInsightsLoading(false);
        }
    }, []);

    const refresh = useCallback(async () => {
        await Promise.all([fetchKnowledge(), fetchInsights()]);
    }, [fetchKnowledge, fetchInsights]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    return {
        items,
        insights,
        loading,
        insightsLoading,
        refresh
    };
}
