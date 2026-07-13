"use client";

import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Box, Heading, Container, Text, Button, VStack, HStack, Input, Select, Checkbox, Slider, SliderTrack, SliderFilledTrack, SliderThumb, Badge } from '@chakra-ui/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
            // Also fetch existing capabilities.
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
            <Container maxW="container.xl" py={8}>
                <Box mb={8}>
                    <Heading as="h1" size="xl" mb={2}>Local Models</Heading>
                    <Text color="gray.500">Register local LLM backends (Ollama, LM Studio, vLLM) to use them in routing and the learning system.</Text>
                </Box>

                <Box mb={6}>
                    <Button leftIcon={<Plus className="h-4 w-4" />} colorScheme="blue" onClick={() => setShowAddForm(!showAddForm)}>
                        Add Provider
                    </Button>
                </Box>

                {showAddForm && (
                    <Card className="mb-6">
                        <CardContent className="pt-6 space-y-4">
                            <HStack>
                                <Input placeholder="Name (e.g. 'My Ollama')" value={newProvider.name} onChange={(e: any) => setNewProvider({ ...newProvider, name: e.target.value })} />
                                <Select value={newProvider.provider_type} onChange={(e: any) => setNewProvider({ ...newProvider, provider_type: e.target.value })} width="150px">
                                    <option value="ollama">Ollama</option>
                                    <option value="lm_studio">LM Studio</option>
                                    <option value="vllm">vLLM</option>
                                    <option value="localai">LocalAI</option>
                                    <option value="custom">Custom</option>
                                </Select>
                            </HStack>
                            <Input placeholder="Base URL (e.g. http://localhost:11434/v1)" value={newProvider.base_url} onChange={(e: any) => setNewProvider({ ...newProvider, base_url: e.target.value })} />
                            <Input placeholder="API Key (optional)" type="password" value={newProvider.api_key} onChange={(e: any) => setNewProvider({ ...newProvider, api_key: e.target.value })} />
                            <HStack>
                                <Button colorScheme="green" onClick={handleAdd} disabled={!newProvider.name || !newProvider.base_url}>Register</Button>
                                <Button variant="ghost" onClick={() => setShowAddForm(false)}>Cancel</Button>
                            </HStack>
                        </CardContent>
                    </Card>
                )}

                {loading ? (
                    <div className="space-y-3">
                        <div className="h-20 w-full rounded-lg border bg-muted/30 animate-pulse" />
                        <div className="h-20 w-full rounded-lg border bg-muted/30 animate-pulse" />
                    </div>
                ) : providers.length === 0 ? (
                    <Card><CardContent className="py-12 text-center"><Text color="gray.500">No local providers registered yet. Click "Add Provider" to get started.</Text></CardContent></Card>
                ) : (
                    <VStack spacing={4} align="stretch">
                        {providers.map((p) => (
                            <Card key={p.id}>
                                <CardHeader>
                                    <HStack justify="space-between">
                                        <HStack>
                                            <Cable className="h-5 w-5 text-blue-500" />
                                            <Box>
                                                <CardTitle className="text-lg">{p.name}</CardTitle>
                                                <Text fontSize="sm" color="gray.500">{p.provider_type} • {p.base_url}</Text>
                                            </Box>
                                        </HStack>
                                        <HStack>
                                            <Button size="sm" variant="outline" leftIcon={<RefreshCw className="h-3 w-3" />} onClick={() => handleDiscover(p.id)}>Discover Models</Button>
                                            <Button size="sm" variant="outline" onClick={() => handleTest(p.id)}>Test</Button>
                                            <Button size="sm" variant="ghost" colorScheme="red" leftIcon={<Trash2 className="h-3 w-3" />} onClick={() => handleDelete(p.id)}>Delete</Button>
                                        </HStack>
                                    </HStack>
                                </CardHeader>
                                {discoveredModels[p.id] && discoveredModels[p.id].length > 0 && (
                                    <CardContent>
                                        <Text fontSize="sm" fontWeight="medium" mb={2}>Discovered Models ({discoveredModels[p.id].length}):</Text>
                                        <VStack spacing={2} align="stretch">
                                            {discoveredModels[p.id].map((model) => {
                                                const cap = capabilities[p.id]?.find((c) => c.model_id === model);
                                                return (
                                                    <HStack key={model} justify="space-between" className="rounded-md border p-3">
                                                        <Box>
                                                            <Text fontSize="sm" fontFamily="mono">{model}</Text>
                                                            {cap && (
                                                                <HStack mt={1} spacing={2}>
                                                                    {cap.supports_tools && <Badge colorScheme="blue" fontSize="2xs">tools</Badge>}
                                                                    {cap.supports_vision && <Badge colorScheme="purple" fontSize="2xs">vision</Badge>}
                                                                    {cap.supports_reasoning && <Badge colorScheme="green" fontSize="2xs">reasoning</Badge>}
                                                                    <Badge fontSize="2xs">Q: {(cap.quality_score * 100).toFixed(0)}%</Badge>
                                                                </HStack>
                                                            )}
                                                        </Box>
                                                        <Button size="xs" variant="ghost" leftIcon={<Settings2 className="h-3 w-3" />} onClick={() => setEditingCapFor(editingCapFor === `${p.id}:${model}` ? null : `${p.id}:${model}`)}>
                                                            Configure
                                                        </Button>
                                                    </HStack>
                                                );
                                            })}
                                        </VStack>
                                        {editingCapFor && editingCapFor.startsWith(`${p.id}:`) && (
                                            <Box className="mt-4">
                                                <CapabilityEditor
                                                    providerId={p.id}
                                                    modelId={editingCapFor.split(':')[1]}
                                                    existing={capabilities[p.id]?.find((c) => c.model_id === editingCapFor.split(':')[1])}
                                                    onSaved={() => { setEditingCapFor(null); handleDiscover(p.id); }}
                                                />
                                            </Box>
                                        )}
                                    </CardContent>
                                )}
                            </Card>
                        ))}
                    </VStack>
                )}

                <Box mt={8}>
                    <Link href="/settings/ai"><Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">← Back to AI Provider Settings</Text></Link>
                </Box>
            </Container>
        </Layout>
    );
};

// Inline capability editor component.
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
        <Box className="mt-4 rounded-md border p-4 space-y-3" bg="gray.50">
            <Text fontSize="sm" fontWeight="medium">Configure: {modelId}</Text>
            <HStack spacing={6}>
                <Checkbox isChecked={caps.supports_tools} onChange={(e: any) => setCaps({ ...caps, supports_tools: e.target.checked })}>Tools</Checkbox>
                <Checkbox isChecked={caps.supports_vision} onChange={(e: any) => setCaps({ ...caps, supports_vision: e.target.checked })}>Vision</Checkbox>
                <Checkbox isChecked={caps.supports_reasoning} onChange={(e: any) => setCaps({ ...caps, supports_reasoning: e.target.checked })}>Reasoning</Checkbox>
            </HStack>
            <HStack spacing={6}>
                <Box>
                    <Text fontSize="xs" color="gray.500">Quality: {(caps.quality_score * 100).toFixed(0)}%</Text>
                    <Slider value={caps.quality_score * 100} min={0} max={100} step={5} onChange={(v: any) => setCaps({ ...caps, quality_score: v / 100 })} w="150px">
                        <SliderTrack><SliderFilledTrack /></SliderTrack>
                        <SliderThumb />
                    </Slider>
                </Box>
                <Box>
                    <Text fontSize="xs" color="gray.500">Speed: {(caps.speed_score * 100).toFixed(0)}%</Text>
                    <Slider value={caps.speed_score * 100} min={0} max={100} step={5} onChange={(v: any) => setCaps({ ...caps, speed_score: v / 100 })} w="150px">
                        <SliderTrack><SliderFilledTrack /></SliderTrack>
                        <SliderThumb />
                    </Slider>
                </Box>
                <Box>
                    <Text fontSize="xs" color="gray.500">Context: {caps.context_window}</Text>
                    <Input type="number" value={caps.context_window} onChange={(e: any) => setCaps({ ...caps, context_window: parseInt(e.target.value) || 4096 })} w="100px" size="sm" />
                </Box>
            </HStack>
            <Button size="sm" colorScheme="green" onClick={handleSave}>Save Capabilities</Button>
        </Box>
    );
};

export default LocalModelsPage;
