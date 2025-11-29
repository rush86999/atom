import React, { useState, useEffect } from 'react';
import { CheckCircle, Plus } from 'lucide-react';
import { FaGoogle, FaSlack, FaGithub, FaMicrosoft, FaSalesforce, FaHubspot } from 'react-icons/fa';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// Define integration types
export interface IntegrationOption {
    id: string;
    name: string;
    icon: any;
    color: string;
    connected: boolean;
    category: string;
}

interface IntegrationSelectorProps {
    onSelect: (integrationId: string) => void;
    selectedIntegrationId?: string;
}

const IntegrationSelector: React.FC<IntegrationSelectorProps> = ({ onSelect, selectedIntegrationId }) => {
    const [integrations, setIntegrations] = useState<IntegrationOption[]>([]);
    const [loading, setLoading] = useState(true);

    // Initial list of supported integrations for workflows
    const supportedIntegrations: IntegrationOption[] = [
        { id: 'gmail', name: 'Gmail', icon: FaGoogle, color: '#EA4335', connected: false, category: 'communication' },
        { id: 'slack', name: 'Slack', icon: FaSlack, color: '#4A154B', connected: false, category: 'communication' },
        { id: 'github', name: 'GitHub', icon: FaGithub, color: '#181717', connected: false, category: 'development' },
        { id: 'outlook', name: 'Outlook', icon: FaMicrosoft, color: '#0078D4', connected: false, category: 'communication' },
        { id: 'salesforce', name: 'Salesforce', icon: FaSalesforce, color: '#00A1E0', connected: false, category: 'crm' },
        { id: 'hubspot', name: 'HubSpot', icon: FaHubspot, color: '#FF7A59', connected: false, category: 'crm' },
    ];

    useEffect(() => {
        const checkHealth = async () => {
            try {
                // Check health for each supported integration
                const checks = await Promise.all(
                    supportedIntegrations.map(async (integration) => {
                        try {
                            const res = await fetch(`/api/integrations/${integration.id}/health`);
                            return { ...integration, connected: res.ok };
                        } catch (e) {
                            return { ...integration, connected: false };
                        }
                    })
                );
                setIntegrations(checks);
            } catch (error) {
                console.error('Failed to check integration status', error);
                setIntegrations(supportedIntegrations);
            } finally {
                setLoading(false);
            }
        };

        checkHealth();
    }, []);

    if (loading) {
        return (
            <div className="text-center py-4">
                <div className="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
                <p className="text-sm mt-2 text-muted-foreground">Checking connections...</p>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {integrations.map((integration) => {
                const IconComponent = integration.icon;
                return (
                    <Card
                        key={integration.id}
                        className={`
                            cursor-${integration.connected ? 'pointer' : 'not-allowed'}
                            ${selectedIntegrationId === integration.id ? 'border-2 border-blue-500' : 'border-2 border-gray-200'}
                            ${integration.connected ? 'opacity-100 hover:border-blue-500 hover:-translate-y-0.5' : 'opacity-60'}
                            transition-all duration-200
                        `}
                        onClick={() => integration.connected && onSelect(integration.id)}
                    >
                        <CardContent className="p-3">
                            <div className="flex justify-between items-center">
                                <div className="flex items-center gap-2">
                                    <IconComponent style={{ color: integration.color }} className="w-5 h-5" />
                                    <span className="font-bold text-sm">{integration.name}</span>
                                </div>
                                {integration.connected ? (
                                    <CheckCircle className="w-3 h-3 text-green-500" />
                                ) : (
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            window.open(`/integrations/${integration.id}`, '_blank');
                                        }}
                                    >
                                        <Plus className="w-3 h-3 mr-1" />
                                        Connect
                                    </Button>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
};

export default IntegrationSelector;
