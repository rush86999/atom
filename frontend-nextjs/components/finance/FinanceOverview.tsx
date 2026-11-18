import React, { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ArrowUpRight, Wallet, Loader2 } from "lucide-react";

interface FinanceSummary {
    totalRevenue: number | null;
    pendingRevenue: number | null;
    currency: string;
}

const SUMMARY_URL = "/api/accounting/summary";
const UNAVAILABLE_MESSAGE = "Finance summary unavailable. The latest revenue data could not be loaded.";
const NOT_SYNCED_LABEL = "Not synced";

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

const isFiniteNumber = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value);

const isSupportedCurrency = (currency: string): boolean => {
    try {
        Intl.NumberFormat("en-US", { style: "currency", currency }).format(0);
        return true;
    } catch {
        return false;
    }
};

/**
 * Extract the two revenue totals the API supplies today. Anything else in the
 * payload (including the backend's placeholder runway value) is ignored.
 */
const parseSummary = (payload: unknown): FinanceSummary | null => {
    if (!isRecord(payload)) {
        return null;
    }

    const { data } = payload;
    if (!isRecord(data)) {
        return null;
    }

    const { total_revenue, pending_revenue, currency, metric_availability } = data;

    // A missing or malformed availability map means the response predates the
    // paired contract. Treat it as unavailable rather than trusting historical
    // default zeros.
    if (!isRecord(metric_availability)) {
        return null;
    }

    const totalAvailable = metric_availability.total_revenue;
    const pendingAvailable = metric_availability.pending_revenue;
    if (typeof totalAvailable !== "boolean" || typeof pendingAvailable !== "boolean") {
        return null;
    }

    let totalRevenue: number | null = null;
    if (totalAvailable) {
        if (!isFiniteNumber(total_revenue)) {
            return null;
        }
        totalRevenue = total_revenue;
    }

    let pendingRevenue: number | null = null;
    if (pendingAvailable) {
        if (!isFiniteNumber(pending_revenue)) {
            return null;
        }
        pendingRevenue = pending_revenue;
    }

    if (typeof currency !== "string") {
        return null;
    }

    const normalizedCurrency = currency.trim().toUpperCase();
    if (!normalizedCurrency || !isSupportedCurrency(normalizedCurrency)) {
        return null;
    }

    return {
        totalRevenue,
        pendingRevenue,
        currency: normalizedCurrency,
    };
};

const formatAmount = (amount: number, currency: string): string => {
    try {
        return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
    } catch {
        return "Unavailable";
    }
};

const FinanceOverview = () => {
    const [summary, setSummary] = useState<FinanceSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [unavailable, setUnavailable] = useState(false);
    const controllerRef = useRef<AbortController | null>(null);

    const loadSummary = useCallback(async () => {
        controllerRef.current?.abort();
        const controller = new AbortController();
        controllerRef.current = controller;

        setLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(SUMMARY_URL, {
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
                },
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error(`Finance summary request failed with status ${response.status}`);
            }

            const parsed = parseSummary(await response.json());
            if (!parsed) {
                throw new Error("Finance summary response was malformed");
            }

            if (controller.signal.aborted) return;
            setSummary(parsed);
            setUnavailable(false);
        } catch (error) {
            if (controller.signal.aborted) return;
            console.error("Failed to fetch finance summary:", error);
            setSummary(null);
            setUnavailable(true);
        } finally {
            if (!controller.signal.aborted) {
                setLoading(false);
            }
        }
    }, []);

    useEffect(() => {
        void loadSummary();

        return () => {
            controllerRef.current?.abort();
        };
    }, [loadSummary]);

    const handleRetry = () => {
        void loadSummary();
    };

    if (unavailable) {
        return (
            <div className="space-y-4">
                <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-4">
                    <p className="text-sm font-medium text-destructive">{UNAVAILABLE_MESSAGE}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                        No figures are shown because a valid summary was not available.
                    </p>
                    <button
                        type="button"
                        onClick={handleRetry}
                        disabled={loading}
                        className="mt-3 inline-flex items-center rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                    >
                        {loading ? "Retrying…" : "Try again"}
                    </button>
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div
                role="status"
                aria-label="Loading finance summary"
                className="flex justify-center p-12"
            >
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!summary) {
        return null;
    }

    const metrics = [
        {
            title: "Total Revenue",
            value: summary.totalRevenue === null
                ? NOT_SYNCED_LABEL
                : formatAmount(summary.totalRevenue, summary.currency),
            icon: Wallet,
            color: "text-muted-foreground"
        },
        {
            title: "Pending Revenue",
            value: summary.pendingRevenue === null
                ? NOT_SYNCED_LABEL
                : formatAmount(summary.pendingRevenue, summary.currency),
            icon: ArrowUpRight,
            color: "text-green-500"
        }
    ];

    return (
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                {metrics.map((metric) => (
                    <Card key={metric.title}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">{metric.title}</CardTitle>
                            <metric.icon className={`h-4 w-4 ${metric.color}`} />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{metric.value}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default FinanceOverview;
