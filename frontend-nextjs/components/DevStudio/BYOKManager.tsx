import React, { useState, useEffect } from 'react';
import { Plus, Trash2, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Spinner } from '../ui/spinner';
import { useToast } from '../ui/use-toast';
import { Modal, ModalFooter } from '../ui/modal';
import { Label } from '../ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

interface Provider {
    id: string;
    name: string;
    description: string;
    cost_per_token: number;
    supported_tasks: string[];
    is_active: boolean;
}

interface ProviderStatus {
    provider: Provider;
    usage: {
        total_requests: number;
        successful_requests: number;
        failed_requests: number;
        cost_accumulated: number;
    };
    has_api_keys: boolean;
    status: string;
}

const BYOKManager = () => {
    const [providers, setProviders] = useState<ProviderStatus[]>([]);
    const [loading, setLoading] = useState(true);
    const [isOpen, setIsOpen] = useState(false);
    const { toast } = useToast();

    const [selectedProvider, setSelectedProvider] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [keyName, setKeyName] = useState('default');

    const fetchProviders = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/ai/providers');
            const data = await response.json();
            if (data.providers) {
                setProviders(data.providers);
            }
        } catch (error) {
            console.error("Failed to fetch providers:", error);
            toast({
                title: "Error fetching providers",
                variant: "error",
                duration: 3000,
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProviders();
    }, []);

    const handleAddKey = async () => {
        if (!selectedProvider || !apiKey) {
            toast({
                title: "Missing information",
                description: "Please select a provider and enter an API key",
                variant: "warning",
                duration: 3000,
            });
            return;
        }

        try {
            // Using query params as per backend implementation
            const url = `/api/ai/providers/${selectedProvider}/keys?api_key=${encodeURIComponent(apiKey)}&key_name=${keyName}`;
            const res = await fetch(url, { method: 'POST' });
            const data = await res.json();

            if (data.success) {
                toast({
                    title: "API Key added",
                    variant: "success",
                    duration: 3000,
                });
                setIsOpen(false);
                fetchProviders();
                setApiKey('');
                setKeyName('default');
                setSelectedProvider('');
            } else {
                throw new Error(data.detail || "Failed to add key");
            }
        } catch (error: any) {
            toast({
                title: "Error adding key",
                description: error.message,
                variant: "error",
                duration: 3000,
            });
        }
    };

    const handleDeleteKey = async (providerId: string, keyName: string = 'default') => {
        try {
            const response = await fetch(`/api/ai/providers/${providerId}/keys/${keyName}`, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (data.success) {
                toast({
                    title: "API Key deleted",
                    variant: "success",
                    duration: 3000,
                });
                fetchProviders();
            }
        } catch (error) {
            toast({
                title: "Error deleting key",
                variant: "error",
                duration: 3000,
            });
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-[400px]">
                <Spinner size="lg" />
            </div>
        );
    }

    return (
        <div className="p-4 space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">AI Providers (BYOK)</h2>
                <Button onClick={() => setIsOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add API Key
                </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Providers</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{providers.length}</div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Available integrations</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Providers</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{providers.filter(p => p.status === 'active').length}</div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">With valid keys</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Cost</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            ${providers.reduce((acc, curr) => acc + curr.usage.cost_accumulated, 0).toFixed(4)}
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Accumulated usage</p>
                    </CardContent>
                </Card>
            </div>

            <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">
                        <tr>
                            <th className="px-6 py-3">Provider</th>
                            <th className="px-6 py-3">Status</th>
                            <th className="px-6 py-3">Cost / Token</th>
                            <th className="px-6 py-3">Usage (Reqs)</th>
                            <th className="px-6 py-3">Total Cost</th>
                            <th className="px-6 py-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900">
                        {providers.map((item) => (
                            <tr key={item.provider.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                <td className="px-6 py-4">
                                    <div className="flex flex-col">
                                        <span className="font-medium text-gray-900 dark:text-gray-100">{item.provider.name}</span>
                                        <span className="text-xs text-gray-500">{item.provider.id}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <Badge variant={item.status === 'active' ? 'success' : 'secondary'}>
                                        {item.status}
                                    </Badge>
                                </td>
                                <td className="px-6 py-4 text-gray-500 dark:text-gray-400">${item.provider.cost_per_token}</td>
                                <td className="px-6 py-4 text-gray-500 dark:text-gray-400">{item.usage.total_requests}</td>
                                <td className="px-6 py-4 text-gray-500 dark:text-gray-400">${item.usage.cost_accumulated.toFixed(4)}</td>
                                <td className="px-6 py-4">
                                    {item.has_api_keys ? (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleDeleteKey(item.provider.id)}
                                            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    ) : (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                                setSelectedProvider(item.provider.id);
                                                setIsOpen(true);
                                            }}
                                        >
                                            Add Key
                                        </Button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <Modal
                isOpen={isOpen}
                onClose={() => setIsOpen(false)}
                title="Add API Key"
            >
                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label>Provider</Label>
                        <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select provider" />
                            </SelectTrigger>
                            <SelectContent>
                                {providers.map(p => (
                                    <SelectItem key={p.provider.id} value={p.provider.id}>
                                        {p.provider.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label>API Key</Label>
                        <Input
                            type="password"
                            placeholder="sk-..."
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Key Name (Optional)</Label>
                        <Input
                            placeholder="default"
                            value={keyName}
                            onChange={(e) => setKeyName(e.target.value)}
                        />
                    </div>
                </div>

                <ModalFooter>
                    <Button variant="outline" onClick={() => setIsOpen(false)}>Cancel</Button>
                    <Button onClick={handleAddKey}>Save Key</Button>
                </ModalFooter>
            </Modal>
        </div>
    );
};

export default BYOKManager;

