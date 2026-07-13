"use client";

import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, Trash2, RefreshCw, Cable, Settings2 } from 'lucide-react';
import Layout from '../../components/layout/Layout';

interface Provider {
    id: string;
    name: string;
    provider_type: string;
    base_url: string;
    is_active: boolean;
    has_api_key: boolean;
}

interface ModelCapabilities {
    model_id: string;
    supports_tools: boolean;
    supports_vision: boolean;
    supports_reasoning: boolean;
    quality_score: number;
    speed_score: number;
    context_window: number;
}

const LocalModelsPage: React.FC = () => {
    const [providers, setProviders] = useState<Provider[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAddForm, setShowAddForm] = useState(false);
    const [newProvider, setNewProvider] = useState({ name: '', provider_type: 'ollama', base_url: 'http://localhost:11434/v1', api_key: '' });
    const [discoveredModels, setDiscoveredModels] = useState<Record<string, string[]>>({});
    const [capabilities, setCapabilities] = useState<Record<string, ModelCapabilities[]>>({});
    const [editingCapFor, setEditingCapFor] = useState<string | null>(null);

    const fetchProviders = async () => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const resp = await apiClient.get('/api/local-models');
            const data = (resp as any).data || resp;
            setProviders(Array.isArray(data) ? data : []);
        } catch {
            setProviders([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchProviders(); }, []);

    const handleAdd = async () => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            await apiClient.post('/api/local-models', {
                name: newProvider.name,
                provider_type: newProvider.provider_type,
                base_url: newProvider.base_url,
                api_key: newProvider.api_key || undefined,
            });
            setNewProvider({ name: '', provider_type: 'ollama', base_url: 'http://localhost:11434/v1', api_key: '' });
            setShowAddForm(false);
            fetchProviders();
        } catch (e) {
            console.error('Failed to add provider:', e);
        }
    };

    const handleDelete = async (id: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            await apiClient.delete(`/api/local-models/${id}`);
            fetchProviders();
        } catch (e) {
            console.error('Failed to delete provider:', e);
        }
    };

    const handleDiscover = async (providerId: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const resp = await apiClient.get(`/api/local-models/${providerId}/models`);
            const data = (resp as any).data || resp;
            setDiscoveredModels({ ...discoveredModels, [providerId]: data.models || [] });
            const capResp = await apiClient.get(`/api/local-models/${providerId}/capabilities`);
            const capData = (capResp as any).data || capResp;
            setCapabilities({ ...capabilities, [providerId]: Array.isArray(capData) ? capData : [] });
        } catch (e) {
            console.error('Discovery failed:', e);
            setDiscoveredModels({ ...discoveredModels, [providerId]: [] });
        }
    };

    const handleTest = async (providerId: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const resp = await apiClient.post(`/api/local-models/${providerId}/test`);
            const data = (resp as any).data || resp;
            alert(data.reachable ? '✅ Connection successful!' : `❌ Not reachable: ${data.error || 'unknown'}`);
        } catch (e) {
            alert('❌ Connection test failed');
        }
    };

    return (
        <Layout>
            <Head><title>Local Models | Atom</title></Head>
            <div className="container mx-auto max-w-4xl py-8">
                <div className="mb-8">
                    <h1 className="text-2xl font-bold">Local Models</h1>
                    <p className="text-muted-foreground mt-1">Register local LLM backends (Ollama, LM Studio, vLLM) to use them in routing and the learning system.</p>
                </div>

                <div className="mb-6">
                    <Button onClick={() => setShowAddForm(!showAddForm)}>
                        <Plus className="h-4 w-4 mr-2" /> Add Provider
                    </Button>
                </div>

                {showAddForm && (
                    <Card className="mb-6">
                        <CardContent className="pt-6 space-y-4">
                            <div className="flex gap-4">
                                <Input placeholder="Name (e.g. 'My Ollama')" value={newProvider.name} onChange={(e: any) => setNewProvider({ ...newProvider, name: e.target.value })} />
                                <Select value={newProvider.provider_type} onValueChange={(v: any) => setNewProvider({ ...newProvider, provider_type: v })}>
                                    <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ollama">Ollama</SelectItem>
                                        <SelectItem value="lm_studio">LM Studio</SelectItem>
                                        <SelectItem value="vllm">vLLM</SelectItem>
                                        <SelectItem value="localai">LocalAI</SelectItem>
                                        <SelectItem value="custom">Custom</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <Input placeholder="Base URL (e.g. http://localhost:11434/v1)" value={newProvider.base_url} onChange={(e: any) => setNewProvider({ ...newProvider, base_url: e.target.value })} />
                            <Input placeholder="API Key (optional)" type="password" value={newProvider.api_key} onChange={(e: any) => setNewProvider({ ...newProvider, api_key: e.target.value })} />
                            <div className="flex gap-2">
                                <Button onClick={handleAdd} disabled={!newProvider.name || !newProvider.base_url}>Register</Button>
                                <Button variant="ghost" onClick={() => setShowAddForm(false)}>Cancel</Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {loading ? (
                    <div className="space-y-3">
                        <div className="h-20 w-full rounded-lg border bg-muted/30 animate-pulse" />
                        <div className="h-20 w-full rounded-lg border bg-muted/30 animate-pulse" />
                    </div>
                ) : providers.length === 0 ? (
                    <Card><CardContent className="py-12 text-center"><p className="text-muted-foreground">No local providers registered yet. Click "Add Provider" to get started.</p></CardContent></Card>
                ) : (
                    <div className="space-y-4">
                        {providers.map((p) => (
                            <Card key={p.id}>
                                <CardHeader>
                                    <div className="flex justify-between items-center">
                                        <div className="flex items-center gap-2">
                                            <Cable className="h-5 w-5 text-blue-500" />
                                            <div>
                                                <CardTitle className="text-lg">{p.name}</CardTitle>
                                                <p className="text-sm text-muted-foreground">{p.provider_type} • {p.base_url}</p>
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <Button size="sm" variant="outline" onClick={() => handleDiscover(p.id)}><RefreshCw className="h-3 w-3 mr-1" /> Discover</Button>
                                            <Button size="sm" variant="outline" onClick={() => handleTest(p.id)}>Test</Button>
                                            <Button size="sm" variant="ghost" onClick={() => handleDelete(p.id)}><Trash2 className="h-3 w-3 mr-1 text-red-500" /> Delete</Button>
                                        </div>
                                    </div>
                                </CardHeader>
                                {discoveredModels[p.id] && discoveredModels[p.id].length > 0 && (
                                    <CardContent>
                                        <p className="text-sm font-medium mb-2">Discovered Models ({discoveredModels[p.id].length}):</p>
                                        <div className="space-y-2">
                                            {discoveredModels[p.id].map((model) => {
                                                const cap = capabilities[p.id]?.find((c) => c.model_id === model);
                                                return (
                                                    <div key={model} className="flex justify-between items-center rounded-md border p-3">
                                                        <div>
                                                            <p className="text-sm font-mono">{model}</p>
                                                            {cap && (
                                                                <div className="flex gap-2 mt-1">
                                                                    {cap.supports_tools && <Badge variant="secondary">tools</Badge>}
                                                                    {cap.supports_vision && <Badge variant="secondary">vision</Badge>}
                                                                    {cap.supports_reasoning && <Badge variant="secondary">reasoning</Badge>}
                                                                    <Badge variant="outline">Q: {(cap.quality_score * 100).toFixed(0)}%</Badge>
                                                                </div>
                                                            )}
                                                        </div>
                                                        <Button size="sm" variant="ghost" onClick={() => setEditingCapFor(editingCapFor === `${p.id}:${model}` ? null : `${p.id}:${model}`)}>
                                                            <Settings2 className="h-3 w-3 mr-1" /> Configure
                                                        </Button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                        {editingCapFor && editingCapFor.startsWith(`${p.id}:`) && (
                                            <div className="mt-4">
                                                <CapabilityEditor
                                                    providerId={p.id}
                                                    modelId={editingCapFor.split(':')[1]}
                                                    existing={capabilities[p.id]?.find((c) => c.model_id === editingCapFor.split(':')[1])}
                                                    onSaved={() => { setEditingCapFor(null); handleDiscover(p.id); }}
                                                />
                                            </div>
                                        )}
                                    </CardContent>
                                )}
                            </Card>
                        ))}
                    </div>
                )}

                <div className="mt-8">
                    <Link href="/settings/ai"><p className="text-blue-500 hover:underline cursor-pointer">← Back to AI Provider Settings</p></Link>
                </div>
            </div>
        </Layout>
    );
};

const CapabilityEditor: React.FC<{ providerId: string; modelId: string; existing?: ModelCapabilities; onSaved: () => void }> = ({ providerId, modelId, existing, onSaved }) => {
    const [caps, setCaps] = useState({
        supports_tools: existing?.supports_tools ?? false,
        supports_vision: existing?.supports_vision ?? false,
        supports_reasoning: existing?.supports_reasoning ?? false,
        quality_score: existing?.quality_score ?? 0.5,
        speed_score: existing?.speed_score ?? 0.5,
        context_window: existing?.context_window ?? 4096,
    });

    const handleSave = async () => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            await apiClient.post(`/api/local-models/${providerId}/capabilities`, { model_id: modelId, ...caps });
            onSaved();
        } catch (e) {
            console.error('Failed to save capabilities:', e);
        }
    };

    return (
        <div className="mt-4 rounded-md border p-4 space-y-3 bg-muted/50">
            <p className="text-sm font-medium">Configure: {modelId}</p>
            <div className="flex gap-6">
                <div className="flex items-center gap-2"><Checkbox checked={caps.supports_tools} onCheckedChange={(v: any) => setCaps({ ...caps, supports_tools: !!v })} /> Tools</div>
                <div className="flex items-center gap-2"><Checkbox checked={caps.supports_vision} onCheckedChange={(v: any) => setCaps({ ...caps, supports_vision: !!v })} /> Vision</div>
                <div className="flex items-center gap-2"><Checkbox checked={caps.supports_reasoning} onCheckedChange={(v: any) => setCaps({ ...caps, supports_reasoning: !!v })} /> Reasoning</div>
            </div>
            <div className="flex gap-6 items-end">
                <div>
                    <p className="text-xs text-muted-foreground">Quality: {(caps.quality_score * 100).toFixed(0)}%</p>
                    <input type="range" min={0} max={100} step={5} value={caps.quality_score * 100} onChange={(e) => setCaps({ ...caps, quality_score: parseInt(e.target.value) / 100 })} className="w-[150px]" />
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">Speed: {(caps.speed_score * 100).toFixed(0)}%</p>
                    <input type="range" min={0} max={100} step={5} value={caps.speed_score * 100} onChange={(e) => setCaps({ ...caps, speed_score: parseInt(e.target.value) / 100 })} className="w-[150px]" />
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">Context: {caps.context_window}</p>
                    <Input type="number" value={caps.context_window} onChange={(e: any) => setCaps({ ...caps, context_window: parseInt(e.target.value) || 4096 })} className="w-[100px]" />
                </div>
            </div>
            <Button size="sm" onClick={handleSave}>Save Capabilities</Button>
        </div>
    );
};

export default LocalModelsPage;
