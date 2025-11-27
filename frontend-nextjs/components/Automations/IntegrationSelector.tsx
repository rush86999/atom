import React, { useState, useEffect } from 'react';
import {
    Box,
    SimpleGrid,
    Text,
    VStack,
    HStack,
    Icon,
    Badge,
    Spinner,
    Button,
    useColorModeValue,
    Card,
    CardBody,
} from '@chakra-ui/react';
import { CheckCircleIcon, WarningTwoIcon, AddIcon } from '@chakra-ui/icons';
import { FaGoogle, FaSlack, FaGithub, FaMicrosoft, FaSalesforce, FaHubspot } from 'react-icons/fa';

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
    const bgColor = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');
    const selectedBorderColor = useColorModeValue('blue.500', 'blue.300');

    // Initial list of supported integrations for workflows
    const supportedIntegrations: IntegrationOption[] = [
        { id: 'gmail', name: 'Gmail', icon: FaGoogle, color: 'red.500', connected: false, category: 'communication' },
        { id: 'slack', name: 'Slack', icon: FaSlack, color: 'purple.500', connected: false, category: 'communication' },
        { id: 'github', name: 'GitHub', icon: FaGithub, color: 'gray.800', connected: false, category: 'development' },
        { id: 'outlook', name: 'Outlook', icon: FaMicrosoft, color: 'blue.500', connected: false, category: 'communication' },
        { id: 'salesforce', name: 'Salesforce', icon: FaSalesforce, color: 'blue.400', connected: false, category: 'crm' },
        { id: 'hubspot', name: 'HubSpot', icon: FaHubspot, color: 'orange.500', connected: false, category: 'crm' },
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
            <Box textAlign="center" py={4}>
                <Spinner size="md" />
                <Text fontSize="sm" mt={2}>Checking connections...</Text>
            </Box>
        );
    }

    return (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
            {integrations.map((integration) => (
                <Card
                    key={integration.id}
                    cursor={integration.connected ? 'pointer' : 'not-allowed'}
                    onClick={() => integration.connected && onSelect(integration.id)}
                    borderWidth="2px"
                    borderColor={selectedIntegrationId === integration.id ? selectedBorderColor : borderColor}
                    bg={bgColor}
                    opacity={integration.connected ? 1 : 0.6}
                    _hover={integration.connected ? { borderColor: selectedBorderColor, transform: 'translateY(-1px)' } : {}}
                    transition="all 0.2s"
                >
                    <CardBody p={3}>
                        <HStack justify="space-between">
                            <HStack>
                                <Icon as={integration.icon} color={integration.color} boxSize={5} />
                                <Text fontWeight="bold" fontSize="sm">{integration.name}</Text>
                            </HStack>
                            {integration.connected ? (
                                <CheckCircleIcon color="green.500" w={3} h={3} />
                            ) : (
                                <Button
                                    size="xs"
                                    leftIcon={<AddIcon />}
                                    variant="ghost"
                                    colorScheme="blue"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        window.open(`/integrations/${integration.id}`, '_blank');
                                    }}
                                >
                                    Connect
                                </Button>
                            )}
                        </HStack>
                    </CardBody>
                </Card>
            ))}
        </SimpleGrid>
    );
};

export default IntegrationSelector;
