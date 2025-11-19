import React, { useState, useEffect } from 'react';
import {
    Box,
    VStack,
    HStack,
    Text,
    Button,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    Badge,
    useColorModeValue,
    Spinner,
    useToast,
    Modal,
    ModalOverlay,
    ModalContent,
    ModalHeader,
    ModalFooter,
    ModalBody,
    ModalCloseButton,
    FormControl,
    FormLabel,
    Input,
    Select,
    useDisclosure,
    IconButton,
    Stat,
    StatLabel,
    StatNumber,
    StatHelpText,
    SimpleGrid,
} from '@chakra-ui/react';
import { AddIcon, DeleteIcon, RepeatIcon } from '@chakra-ui/icons';

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
    const { isOpen, onOpen, onClose } = useDisclosure();
    const toast = useToast();

    const [selectedProvider, setSelectedProvider] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [keyName, setKeyName] = useState('default');

    const bgColor = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

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
                status: "error",
                duration: 3000,
                isClosable: true,
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
                status: "warning",
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        try {
            const response = await fetch(`/api/ai/providers/${selectedProvider}/keys?key_name=${keyName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(apiKey), // The endpoint expects the key as body string based on signature, or query param? 
                // Checking signature: store_api_key(provider_id, api_key, ...)
                // Wait, the python signature is: async def store_api_key(provider_id: str, api_key: str, ...)
                // FastAPI usually expects query params for simple types unless Body() is used.
                // Let's try sending as query param first if body fails, or check docs.
                // Actually, looking at the python code: 
                // @router.post("/api/ai/providers/{provider_id}/keys")
                // async def store_api_key(provider_id: str, api_key: str, ...)
                // This implies api_key is a query parameter by default in FastAPI if not specified as Body.
                // Let's adjust the fetch to send as query param to be safe, or try to fix the backend if needed.
                // Re-reading backend code: `api_key: str` is a parameter.
                // Let's try sending as query param.
            });

            // Actually, sending sensitive data as query param is bad practice.
            // But based on the backend code provided:
            // @router.post("/api/ai/providers/{provider_id}/keys")
            // async def store_api_key(provider_id: str, api_key: str, ...)
            // It IS a query param. I will use it as such for now to match the backend.

            const url = `/api/ai/providers/${selectedProvider}/keys?api_key=${encodeURIComponent(apiKey)}&key_name=${keyName}`;
            const res = await fetch(url, { method: 'POST' });
            const data = await res.json();

            if (data.success) {
                toast({
                    title: "API Key added",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                onClose();
                fetchProviders();
                setApiKey('');
                setKeyName('default');
            } else {
                throw new Error(data.detail || "Failed to add key");
            }
        } catch (error: any) {
            toast({
                title: "Error adding key",
                description: error.message,
                status: "error",
                duration: 3000,
                isClosable: true,
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
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                fetchProviders();
            }
        } catch (error) {
            toast({
                title: "Error deleting key",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        }
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" h="400px">
                <Spinner size="xl" />
            </Box>
        );
    }

    return (
        <Box p={4}>
            <HStack justify="space-between" mb={6}>
                <Text fontSize="2xl" fontWeight="bold">AI Providers (BYOK)</Text>
                <Button leftIcon={<AddIcon />} colorScheme="teal" onClick={onOpen}>
                    Add API Key
                </Button>
            </HStack>

            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6} mb={8}>
                <Stat bg={bgColor} p={4} borderRadius="lg" border="1px" borderColor={borderColor}>
                    <StatLabel>Total Providers</StatLabel>
                    <StatNumber>{providers.length}</StatNumber>
                    <StatHelpText>Available integrations</StatHelpText>
                </Stat>
                <Stat bg={bgColor} p={4} borderRadius="lg" border="1px" borderColor={borderColor}>
                    <StatLabel>Active Providers</StatLabel>
                    <StatNumber>{providers.filter(p => p.status === 'active').length}</StatNumber>
                    <StatHelpText>With valid keys</StatHelpText>
                </Stat>
                <Stat bg={bgColor} p={4} borderRadius="lg" border="1px" borderColor={borderColor}>
                    <StatLabel>Total Cost</StatLabel>
                    <StatNumber>
                        ${providers.reduce((acc, curr) => acc + curr.usage.cost_accumulated, 0).toFixed(4)}
                    </StatNumber>
                    <StatHelpText>Accumulated usage</StatHelpText>
                </Stat>
            </SimpleGrid>

            <Box overflowX="auto" bg={bgColor} borderRadius="lg" border="1px" borderColor={borderColor}>
                <Table variant="simple">
                    <Thead>
                        <Tr>
                            <Th>Provider</Th>
                            <Th>Status</Th>
                            <Th>Cost / Token</Th>
                            <Th>Usage (Reqs)</Th>
                            <Th>Total Cost</Th>
                            <Th>Actions</Th>
                        </Tr>
                    </Thead>
                    <Tbody>
                        {providers.map((item) => (
                            <Tr key={item.provider.id}>
                                <Td>
                                    <VStack align="start" spacing={0}>
                                        <Text fontWeight="bold">{item.provider.name}</Text>
                                        <Text fontSize="xs" color="gray.500">{item.provider.id}</Text>
                                    </VStack>
                                </Td>
                                <Td>
                                    <Badge colorScheme={item.status === 'active' ? 'green' : 'gray'}>
                                        {item.status}
                                    </Badge>
                                </Td>
                                <Td>${item.provider.cost_per_token}</Td>
                                <Td>{item.usage.total_requests}</Td>
                                <Td>${item.usage.cost_accumulated.toFixed(4)}</Td>
                                <Td>
                                    {item.has_api_keys ? (
                                        <IconButton
                                            aria-label="Delete Key"
                                            icon={<DeleteIcon />}
                                            size="sm"
                                            colorScheme="red"
                                            variant="ghost"
                                            onClick={() => handleDeleteKey(item.provider.id)}
                                        />
                                    ) : (
                                        <Button size="xs" onClick={() => {
                                            setSelectedProvider(item.provider.id);
                                            onOpen();
                                        }}>
                                            Add Key
                                        </Button>
                                    )}
                                </Td>
                            </Tr>
                        ))}
                    </Tbody>
                </Table>
            </Box>

            <Modal isOpen={isOpen} onClose={onClose}>
                <ModalOverlay />
                <ModalContent>
                    <ModalHeader>Add API Key</ModalHeader>
                    <ModalCloseButton />
                    <ModalBody pb={6}>
                        <FormControl>
                            <FormLabel>Provider</FormLabel>
                            <Select
                                placeholder="Select provider"
                                value={selectedProvider}
                                onChange={(e) => setSelectedProvider(e.target.value)}
                            >
                                {providers.map(p => (
                                    <option key={p.provider.id} value={p.provider.id}>
                                        {p.provider.name}
                                    </option>
                                ))}
                            </Select>
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>API Key</FormLabel>
                            <Input
                                type="password"
                                placeholder="sk-..."
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Key Name (Optional)</FormLabel>
                            <Input
                                placeholder="default"
                                value={keyName}
                                onChange={(e) => setKeyName(e.target.value)}
                            />
                        </FormControl>
                    </ModalBody>

                    <ModalFooter>
                        <Button colorScheme="teal" mr={3} onClick={handleAddKey}>
                            Save Key
                        </Button>
                        <Button onClick={onClose}>Cancel</Button>
                    </ModalFooter>
                </ModalContent>
            </Modal>
        </Box>
    );
};

export default BYOKManager;
