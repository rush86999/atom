import React, { useState, useEffect } from 'react';
import {
    Box,
    SimpleGrid,
    Text,
    Stat,
    StatLabel,
    StatNumber,
    StatHelpText,
    StatArrow,
    Progress,
    VStack,
    HStack,
    Badge,
    useColorModeValue,
    Card,
    CardHeader,
    CardBody,
    Icon,
} from '@chakra-ui/react';
import { CheckCircleIcon, WarningIcon, TimeIcon } from '@chakra-ui/icons';

interface SystemStatusData {
    timestamp: string;
    overall_status: string;
    resources: {
        cpu: {
            percent: number;
            count: number;
        };
        memory: {
            percent: number;
            system_used_percent: number;
            system_total_mb: number;
            system_available_mb: number;
        };
        disk: {
            percent: number;
            free_gb: number;
            total_gb: number;
        };
    };
    services: {
        [key: string]: {
            name: string;
            status: string;
            response_time_ms: number;
        };
    };
    uptime: {
        system_seconds: number;
    };
}

const SystemMonitor = () => {
    const [status, setStatus] = useState<SystemStatusData | null>(null);
    const [loading, setLoading] = useState(true);

    const bgColor = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

    const fetchStatus = async () => {
        try {
            const response = await fetch('/api/system/status');
            const data = await response.json();
            setStatus(data);
            setLoading(false);
        } catch (error) {
            console.error("Failed to fetch system status:", error);
        }
    };

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000); // Refresh every 5 seconds
        return () => clearInterval(interval);
    }, []);

    if (!status) {
        return <Progress size="xs" isIndeterminate />;
    }

    const formatUptime = (seconds: number) => {
        const days = Math.floor(seconds / (3600 * 24));
        const hours = Math.floor((seconds % (3600 * 24)) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${days}d ${hours}h ${minutes}m`;
    };

    const getStatusColor = (status: string) => {
        switch (status?.toLowerCase()) {
            case 'healthy':
            case 'operational':
                return 'green';
            case 'degraded':
                return 'yellow';
            case 'unhealthy':
            case 'unreachable':
                return 'red';
            default:
                return 'gray';
        }
    };

    return (
        <Box p={4}>
            <HStack justify="space-between" mb={6}>
                <VStack align="start" spacing={1}>
                    <Text fontSize="2xl" fontWeight="bold">System Monitor</Text>
                    <Text fontSize="sm" color="gray.500">Last updated: {new Date(status.timestamp).toLocaleTimeString()}</Text>
                </VStack>
                <Badge
                    colorScheme={getStatusColor(status.overall_status)}
                    fontSize="lg"
                    p={2}
                    borderRadius="md"
                >
                    System: {status.overall_status.toUpperCase()}
                </Badge>
            </HStack>

            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6} mb={8}>
                <Card bg={bgColor} border="1px" borderColor={borderColor}>
                    <CardBody>
                        <Stat>
                            <StatLabel>CPU Usage</StatLabel>
                            <StatNumber>{status.resources.cpu.percent}%</StatNumber>
                            <StatHelpText>
                                {status.resources.cpu.count} Cores Active
                            </StatHelpText>
                        </Stat>
                        <Progress
                            value={status.resources.cpu.percent}
                            colorScheme={status.resources.cpu.percent > 80 ? 'red' : 'blue'}
                            size="sm"
                            mt={2}
                            borderRadius="full"
                        />
                    </CardBody>
                </Card>

                <Card bg={bgColor} border="1px" borderColor={borderColor}>
                    <CardBody>
                        <Stat>
                            <StatLabel>Memory Usage</StatLabel>
                            <StatNumber>{status.resources.memory.percent}%</StatNumber>
                            <StatHelpText>
                                {status.resources.memory.system_available_mb} MB Available
                            </StatHelpText>
                        </Stat>
                        <Progress
                            value={status.resources.memory.percent}
                            colorScheme={status.resources.memory.percent > 80 ? 'orange' : 'purple'}
                            size="sm"
                            mt={2}
                            borderRadius="full"
                        />
                    </CardBody>
                </Card>

                <Card bg={bgColor} border="1px" borderColor={borderColor}>
                    <CardBody>
                        <Stat>
                            <StatLabel>System Uptime</StatLabel>
                            <StatNumber fontSize="2xl">{formatUptime(status.uptime.system_seconds)}</StatNumber>
                            <StatHelpText>
                                Since last reboot
                            </StatHelpText>
                        </Stat>
                        <Box mt={2} h="4px" bg="green.400" borderRadius="full" />
                    </CardBody>
                </Card>
            </SimpleGrid>

            <Text fontSize="xl" fontWeight="bold" mb={4}>Service Health</Text>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                {Object.entries(status.services).map(([key, service]) => (
                    <Card key={key} bg={bgColor} border="1px" borderColor={borderColor}>
                        <CardBody>
                            <HStack justify="space-between" mb={2}>
                                <Text fontWeight="bold">{service.name}</Text>
                                <Icon
                                    as={service.status === 'healthy' ? CheckCircleIcon : WarningIcon}
                                    color={`${getStatusColor(service.status)}.500`}
                                />
                            </HStack>
                            <HStack justify="space-between">
                                <Badge colorScheme={getStatusColor(service.status)}>{service.status}</Badge>
                                <Text fontSize="xs" color="gray.500">{service.response_time_ms}ms</Text>
                            </HStack>
                        </CardBody>
                    </Card>
                ))}
            </SimpleGrid>
        </Box>
    );
};

export default SystemMonitor;
