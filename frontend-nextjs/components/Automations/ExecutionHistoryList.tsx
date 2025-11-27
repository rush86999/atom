import React, { useState, useEffect } from 'react';
import {
    Box,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    Badge,
    Text,
    IconButton,
    Tooltip,
    Spinner,
    Flex,
    useColorModeValue
} from '@chakra-ui/react';
import { ViewIcon, TimeIcon, CheckCircleIcon, WarningIcon } from '@chakra-ui/icons';

interface Execution {
    execution_id: string;
    workflow_id: string;
    status: 'success' | 'failed' | 'running' | 'completed';
    start_time: string;
    end_time?: string;
    duration_ms?: number;
    actions_executed: string[];
    errors: string[];
}

interface ExecutionHistoryListProps {
    workflowId: string;
    onSelectExecution: (executionId: string) => void;
    refreshTrigger?: number;
}

const ExecutionHistoryList: React.FC<ExecutionHistoryListProps> = ({
    workflowId,
    onSelectExecution,
    refreshTrigger
}) => {
    const [executions, setExecutions] = useState<Execution[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHistory = async () => {
        if (!workflowId) return;

        try {
            setLoading(true);
            const response = await fetch(`/api/v1/workflows/${workflowId}/executions`);
            if (!response.ok) {
                throw new Error('Failed to fetch execution history');
            }
            const data = await response.json();
            setExecutions(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [workflowId, refreshTrigger]);

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

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'success':
            case 'completed':
                return <CheckCircleIcon color="green.500" />;
            case 'failed':
                return <WarningIcon color="red.500" />;
            case 'running':
                return <Spinner size="xs" color="blue.500" />;
            default:
                return <TimeIcon color="gray.500" />;
        }
    };

    const formatDuration = (ms?: number) => {
        if (!ms) return '-';
        if (ms < 1000) return `${Math.round(ms)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleString();
    };

    const hoverBg = useColorModeValue('gray.50', 'gray.700');

    if (loading && executions.length === 0) {
        return (
            <Flex justify="center" align="center" h="200px">
                <Spinner size="xl" />
            </Flex>
        );
    }

    if (error) {
        return (
            <Box p={4} color="red.500" textAlign="center">
                <WarningIcon mb={2} boxSize={6} />
                <Text>Error loading history: {error}</Text>
            </Box>
        );
    }

    if (executions.length === 0) {
        return (
            <Box p={8} textAlign="center" color="gray.500">
                <TimeIcon mb={2} boxSize={8} />
                <Text>No execution history found for this workflow.</Text>
                <Text fontSize="sm">Run the workflow to see results here.</Text>
            </Box>
        );
    }

    return (
        <Box overflowX="auto">
            <Table variant="simple" size="sm">
                <Thead>
                    <Tr>
                        <Th>Status</Th>
                        <Th>Date</Th>
                        <Th>Duration</Th>
                        <Th>Actions</Th>
                        <Th>Details</Th>
                    </Tr>
                </Thead>
                <Tbody>
                    {executions.map((exec) => (
                        <Tr
                            key={exec.execution_id}
                            _hover={{ bg: hoverBg }}
                            cursor="pointer"
                            onClick={() => onSelectExecution(exec.execution_id)}
                        >
                            <Td>
                                <Flex align="center" gap={2}>
                                    {getStatusIcon(exec.status)}
                                    <Badge colorScheme={getStatusColor(exec.status)}>
                                        {exec.status}
                                    </Badge>
                                </Flex>
                            </Td>
                            <Td>{formatDate(exec.start_time)}</Td>
                            <Td>{formatDuration(exec.duration_ms)}</Td>
                            <Td>{exec.actions_executed?.length || 0} nodes</Td>
                            <Td>
                                <Tooltip label="View Details">
                                    <IconButton
                                        aria-label="View details"
                                        icon={<ViewIcon />}
                                        size="sm"
                                        variant="ghost"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onSelectExecution(exec.execution_id);
                                        }}
                                    />
                                </Tooltip>
                            </Td>
                        </Tr>
                    ))}
                </Tbody>
            </Table>
        </Box>
    );
};

export default ExecutionHistoryList;
