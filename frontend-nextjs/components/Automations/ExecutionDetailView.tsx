import React, { useState, useEffect } from 'react';
import {
    Box,
    VStack,
    HStack,
    Heading,
    Text,
    Badge,
    Button,
    Divider,
    Code,
    Accordion,
    AccordionItem,
    AccordionButton,
    AccordionPanel,
    AccordionIcon,
    Spinner,
    Alert,
    AlertIcon,
    Card,
    CardBody,
    CardHeader
} from '@chakra-ui/react';
import { ArrowBackIcon, CheckCircleIcon, WarningIcon, TimeIcon } from '@chakra-ui/icons';

interface ExecutionDetailViewProps {
    executionId: string;
    onBack: () => void;
}

interface ExecutionDetail {
    execution_id: string;
    workflow_id: string;
    status: string;
    start_time: string;
    end_time?: string;
    duration_ms?: number;
    results: Record<string, any>;
    errors: string[];
    trigger_data: any;
}

const ExecutionDetailView: React.FC<ExecutionDetailViewProps> = ({ executionId, onBack }) => {
    const [detail, setDetail] = useState<ExecutionDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                setLoading(true);
                const response = await fetch(`/api/v1/workflows/executions/${executionId}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch execution details');
                }
                const data = await response.json();
                setDetail(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Unknown error');
            } finally {
                setLoading(false);
            }
        };

        if (executionId) {
            fetchDetail();
        }
    }, [executionId]);

    if (loading) {
        return (
            <Box textAlign="center" py={10}>
                <Spinner size="xl" />
                <Text mt={4}>Loading execution details...</Text>
            </Box>
        );
    }

    if (error || !detail) {
        return (
            <Box p={4}>
                <Button leftIcon={<ArrowBackIcon />} onClick={onBack} mb={4}>
                    Back to History
                </Button>
                <Alert status="error">
                    <AlertIcon />
                    {error || 'Execution not found'}
                </Alert>
            </Box>
        );
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success':
            case 'completed':
                return 'green';
            case 'failed':
                return 'red';
            case 'running':
                return 'blue';
            default:
                return 'gray';
        }
    };

    return (
        <Box>
            <Button leftIcon={<ArrowBackIcon />} onClick={onBack} mb={4} size="sm">
                Back to History
            </Button>

            <VStack spacing={6} align="stretch">
                {/* Header Info */}
                <Card>
                    <CardBody>
                        <VStack align="start" spacing={4}>
                            <HStack justify="space-between" width="100%">
                                <Heading size="md">Execution Details</Heading>
                                <Badge colorScheme={getStatusColor(detail.status)} fontSize="md" px={2} py={1}>
                                    {detail.status.toUpperCase()}
                                </Badge>
                            </HStack>

                            <HStack spacing={8}>
                                <Box>
                                    <Text fontSize="sm" color="gray.500">Started</Text>
                                    <Text fontWeight="medium">{new Date(detail.start_time).toLocaleString()}</Text>
                                </Box>
                                <Box>
                                    <Text fontSize="sm" color="gray.500">Duration</Text>
                                    <Text fontWeight="medium">
                                        {detail.duration_ms ? `${(detail.duration_ms / 1000).toFixed(2)}s` : '-'}
                                    </Text>
                                </Box>
                                <Box>
                                    <Text fontSize="sm" color="gray.500">ID</Text>
                                    <Text fontFamily="monospace" fontSize="sm">{detail.execution_id}</Text>
                                </Box>
                            </HStack>

                            {detail.errors && detail.errors.length > 0 && (
                                <Alert status="error" borderRadius="md">
                                    <AlertIcon />
                                    <Box>
                                        <Text fontWeight="bold">Execution Errors:</Text>
                                        <VStack align="start" spacing={1}>
                                            {detail.errors.map((err, idx) => (
                                                <Text key={idx} fontSize="sm">{err}</Text>
                                            ))}
                                        </VStack>
                                    </Box>
                                </Alert>
                            )}
                        </VStack>
                    </CardBody>
                </Card>

                {/* Trigger Data */}
                <Card>
                    <CardHeader pb={0}>
                        <Heading size="sm">Trigger Data</Heading>
                    </CardHeader>
                    <CardBody>
                        <Box bg="gray.50" p={3} borderRadius="md" overflowX="auto">
                            <Code display="block" whiteSpace="pre" bg="transparent">
                                {JSON.stringify(detail.trigger_data, null, 2)}
                            </Code>
                        </Box>
                    </CardBody>
                </Card>

                {/* Node Results */}
                <Card>
                    <CardHeader pb={0}>
                        <Heading size="sm">Node Execution Results</Heading>
                    </CardHeader>
                    <CardBody>
                        <Accordion allowMultiple defaultIndex={[0]}>
                            {Object.entries(detail.results || {}).map(([nodeId, result]: [string, any]) => (
                                <AccordionItem key={nodeId}>
                                    <h2>
                                        <AccordionButton>
                                            <Box flex="1" textAlign="left">
                                                <HStack>
                                                    {result.status === 'success' ? (
                                                        <CheckCircleIcon color="green.500" />
                                                    ) : result.status === 'failed' ? (
                                                        <WarningIcon color="red.500" />
                                                    ) : (
                                                        <TimeIcon color="gray.500" />
                                                    )}
                                                    <Text fontWeight="medium">{result.node_title || nodeId}</Text>
                                                    <Badge size="sm" colorScheme={getStatusColor(result.status)}>
                                                        {result.status}
                                                    </Badge>
                                                </HStack>
                                            </Box>
                                            <AccordionIcon />
                                        </AccordionButton>
                                    </h2>
                                    <AccordionPanel pb={4}>
                                        <VStack align="stretch" spacing={3}>
                                            <Box>
                                                <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>OUTPUT</Text>
                                                <Box bg="gray.50" p={2} borderRadius="md">
                                                    <Code display="block" whiteSpace="pre-wrap" bg="transparent" fontSize="xs">
                                                        {JSON.stringify(result.output, null, 2)}
                                                    </Code>
                                                </Box>
                                            </Box>
                                            {result.error && (
                                                <Box>
                                                    <Text fontSize="xs" fontWeight="bold" color="red.500" mb={1}>ERROR</Text>
                                                    <Box bg="red.50" p={2} borderRadius="md" color="red.700">
                                                        <Text fontSize="sm">{result.error}</Text>
                                                    </Box>
                                                </Box>
                                            )}
                                        </VStack>
                                    </AccordionPanel>
                                </AccordionItem>
                            ))}
                        </Accordion>
                        {(!detail.results || Object.keys(detail.results).length === 0) && (
                            <Text color="gray.500" fontStyle="italic">No node results recorded.</Text>
                        )}
                    </CardBody>
                </Card>
            </VStack>
        </Box>
    );
};

export default ExecutionDetailView;
