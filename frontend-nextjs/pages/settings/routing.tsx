"use client";

import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Box, Heading, Container, Text, Button } from '@chakra-ui/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, RefreshCw, AlertCircle, TrendingUp, Database } from 'lucide-react';
import Layout from '../../components/layout/Layout';

interface EmaModelScore {
    score: number;
    success_rate: number;
    avg_latency_ms: number;
    avg_cost: number;
    samples: number;
}

interface RoutingStats {
    feedback_samples: number;
    model_success_rates: Record<string, number>;
    ema_enabled?: boolean;
    ema_scores?: Record<string, EmaModelScore>;
    cached_weights?: number;
    total_models?: number;
}

interface RoutingStatsResponse {
    enabled: boolean;
    ema_enabled?: boolean;
    stats: RoutingStats | { error?: string };
}

const RoutingDashboardPage: React.FC = () => {
    const [data, setData] = useState<RoutingStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchStats = async () => {
        setRefreshing(true);
        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.get('/api/chat/routing-stats');
            const result = (response as any).data || response;
            setData(result);
        } catch (err) {
            console.error('Failed to load routing stats:', err);
            setData({ enabled: false, ema_enabled: false, stats: { feedback_samples: 0, model_success_rates: {}, ema_scores: {} } });
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { fetchStats(); }, []);

    const stats = data?.stats as RoutingStats | undefined;
    const enabled = data?.enabled ?? false;
    const emaEnabled = data?.ema_enabled ?? stats?.ema_enabled ?? false;
    const samples = stats?.feedback_samples ?? 0;
    const successRates = stats?.model_success_rates ?? {};
    const emaScores = stats?.ema_scores ?? {};

    return (
        <Layout>
            <Head>
                <title>Routing &amp; Learning | Atom</title>
            </Head>
            <Container maxW="container.xl" py={8}>
                <Box mb={8}>
                    <Heading as="h1" size="xl" mb={2}>Routing &amp; Telemetry</Heading>
                    <Text color="gray.500">How Atom dynamically scores, ranks, and learns to route requests to optimal models.</Text>
                </Box>

                {!enabled && !emaEnabled && (
                    <Card className="mb-6 border-amber-300 bg-amber-50">
                        <CardContent className="flex items-start gap-3 pt-6">
                            <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5" />
                            <div>
                                <p className="font-medium text-amber-900">Learning &amp; EMA Routers are off</p>
                                <p className="text-sm text-amber-700 mt-1">
                                    Adaptive routing is currently disabled. Enable ML predictors via
                                    <code className="mx-1 px-1 py-0.5 rounded bg-amber-100">ATOM_LEARNING_ROUTER=true</code>
                                    or real-time telemetry via
                                    <code className="mx-1 px-1 py-0.5 rounded bg-amber-100">ATOM_EMA_ROUTER_ENABLED=true</code>.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <div className="grid gap-4 md:grid-cols-4 mb-8">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium">Feedback Samples</CardTitle>
                            <Database className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{samples.toLocaleString()}</div>
                            <p className="text-xs text-muted-foreground mt-1">Observed outcomes collected</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium">Models Tracked</CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{Object.keys(successRates).length || Object.keys(emaScores).length}</div>
                            <p className="text-xs text-muted-foreground mt-1">Models with active telemetry</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium">ML Predictor Status</CardTitle>
                            <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{enabled ? 'Active' : 'Off'}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {enabled ? 'Learning from feedback' : 'ATOM_LEARNING_ROUTER=false'}
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium">EMA Telemetry</CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{emaEnabled ? 'Active' : 'Off'}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {emaEnabled ? 'Real-time latency &amp; cost decay' : 'ATOM_EMA_ROUTER_ENABLED=false'}
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* EMA Scores Table */}
                {Object.keys(emaScores).length > 0 && (
                    <Card className="mb-6">
                        <CardHeader>
                            <CardTitle>EMA Protocol Telemetry (Real-Time)</CardTitle>
                            <CardDescription>
                                Exponential Moving Average of latency, cost, and success rate per candidate model.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm border-collapse">
                                    <thead>
                                        <tr className="border-b font-medium text-muted-foreground">
                                            <th className="py-2 px-3">Model ID</th>
                                            <th className="py-2 px-3">EMA Score</th>
                                            <th className="py-2 px-3">Success Rate</th>
                                            <th className="py-2 px-3">Avg Latency</th>
                                            <th className="py-2 px-3">Avg Cost</th>
                                            <th className="py-2 px-3">Samples</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {Object.entries(emaScores)
                                            .sort(([, a], [, b]) => b.score - a.score)
                                            .map(([model, metrics]) => (
                                                <tr key={model} className="border-b last:border-0 hover:bg-muted/50">
                                                    <td className="py-2 px-3 font-mono">{model}</td>
                                                    <td className="py-2 px-3 font-semibold">{(metrics.score * 100).toFixed(1)}%</td>
                                                    <td className="py-2 px-3">{(metrics.success_rate * 100).toFixed(0)}%</td>
                                                    <td className="py-2 px-3">{metrics.avg_latency_ms.toFixed(0)} ms</td>
                                                    <td className="py-2 px-3">${metrics.avg_cost.toFixed(4)}</td>
                                                    <td className="py-2 px-3">{metrics.samples}</td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <Card className="mb-6">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Per-Model Success Rate</CardTitle>
                            <CardDescription>
                                How often each model produced a successful, quality-satisfying response.
                            </CardDescription>
                        </div>
                        <Button variant="outline" size="sm" onClick={fetchStats} disabled={refreshing}>
                            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </CardHeader>
                    <CardContent>
                        {loading ? (
                            <div className="space-y-2">
                                <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
                                <div className="h-4 w-1/2 rounded bg-muted animate-pulse" />
                                <div className="h-4 w-2/3 rounded bg-muted animate-pulse" />
                            </div>
                        ) : Object.keys(successRates).length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                                No per-model data yet. Data appears here as users chat and submit feedback.
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {Object.entries(successRates)
                                    .sort(([, a], [, b]) => b - a)
                                    .map(([model, rate]) => (
                                        <div key={model} className="flex items-center justify-between py-2 border-b last:border-0">
                                            <span className="font-mono text-sm">{model}</span>
                                            <Badge variant={rate >= 0.8 ? 'default' : rate >= 0.5 ? 'secondary' : 'destructive'}>
                                                {(rate * 100).toFixed(0)}%
                                            </Badge>
                                        </div>
                                    ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Box mt={6}>
                    <Link href="/settings/ai">
                        <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                            ← Back to AI Provider Settings
                        </Text>
                    </Link>
                </Box>
            </Container>
        </Layout>
    );
};

export default RoutingDashboardPage;
