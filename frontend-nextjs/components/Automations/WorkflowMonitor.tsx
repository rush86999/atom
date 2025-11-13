import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Badge,
  Button,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  SimpleGrid,
  Flex,
  Spinner,
  useToast,
  Progress,
  Tooltip,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow
} from '@chakra-ui/react';
import { SearchIcon, RepeatIcon, ViewIcon, ChevronDownIcon, ArrowForwardIcon, CloseIcon, SettingsIcon } from '@chakra-ui/icons';

interface WorkflowExecution {
  id: string;
  workflowId: string;
  workflowName: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'pending';
  startTime: Date;
  endTime?: Date;
  duration?: number;
  trigger: string;
  inputData?: Record<string, any>;
  outputData?: Record<string, any>;
  error?: string;
  steps: WorkflowStepExecution[];
  progress: number;
  logs: ExecutionLog[];
}

interface WorkflowStepExecution {
  id: string;
  stepId: string;
  stepName: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startTime?: Date;
  endTime?: Date;
  duration?: number;
  input?: Record<string, any>;
  output?: Record<string, any>;
  error?: string;
}

interface ExecutionLog {
  timestamp: Date;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  stepId?: string;
  data?: Record<string, any>;
}

interface WorkflowMonitorProps {
  executions?: WorkflowExecution[];
  onExecutionStart?: (workflowId: string, inputData?: Record<string, any>) => void;
  onExecutionStop?: (executionId: string) => void;
  onExecutionRetry?: (executionId: string) => void;
  onExecutionDelete?: (executionId: string) => void;
  onLogsDownload?: (executionId: string) => void;
  showNavigation?: boolean;
  compactView?: boolean;
  refreshInterval?: number;
}

const WorkflowMonitor: React.FC<WorkflowMonitorProps> = ({
  executions = [],
  onExecutionStart,
  onExecutionStop,
  onExecutionRetry,
  onExecutionDelete,
  onLogsDownload,
  showNavigation = true,
  compactView = false,
  refreshInterval = 30000
}) => {
  const [filteredExecutions, setFilteredExecutions] = useState<WorkflowExecution[]>(executions);
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [timeRange, setTimeRange] = useState<string>('24h');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  // Auto-refresh executions
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      // In a real implementation, this would fetch updated executions from the server
      setFilteredExecutions(prev => [...prev]);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  // Filter executions based on search and filters
  useEffect(() => {
    let filtered = executions;

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(exec =>
        exec.workflowName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        exec.trigger.toLowerCase().includes(searchTerm.toLowerCase()) ||
        exec.id.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(exec => exec.status === statusFilter);
    }

    // Apply time range filter
    const now = new Date();
    switch (timeRange) {
      case '1h':
        filtered = filtered.filter(exec =>
          exec.startTime > new Date(now.getTime() - 60 * 60 * 1000)
        );
        break;
      case '24h':
        filtered = filtered.filter(exec =>
          exec.startTime > new Date(now.getTime() - 24 * 60 * 60 * 1000)
        );
        break;
      case '7d':
        filtered = filtered.filter(exec =>
          exec.startTime > new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        );
        break;
      case '30d':
        filtered = filtered.filter(exec =>
          exec.startTime > new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        );
        break;
    }

    setFilteredExecutions(filtered);
  }, [executions, searchTerm, statusFilter, timeRange]);

  const getStatusColor = (status: WorkflowExecution['status']) => {
    switch (status) {
      case 'completed': return 'green';
      case 'running': return 'blue';
      case 'pending': return 'yellow';
      case 'failed': return 'red';
      case 'cancelled': return 'gray';
      default: return 'gray';
    }
  };

  const getStepStatusColor = (status: WorkflowStepExecution['status']) => {
    switch (status) {
      case 'completed': return 'green';
      case 'running': return 'blue';
      case 'pending': return 'yellow';
      case 'failed': return 'red';
      case 'skipped': return 'gray';
      default: return 'gray';
    }
  };

  const getLogLevelColor = (level: ExecutionLog['level']) => {
    switch (level) {
      case 'error': return 'red';
      case 'warning': return 'orange';
      case 'info': return 'blue';
      case 'debug': return 'gray';
      default: return 'gray';
    }
  };

  const formatDuration = (milliseconds: number) => {
    if (milliseconds < 1000) return `${milliseconds}ms`;
    if (milliseconds < 60000) return `${(milliseconds / 1000).toFixed(1)}s`;
    if (milliseconds < 3600000) return `${Math.floor(milliseconds / 60000)}m ${Math.floor((milliseconds % 60000) / 1000)}s`;
    return `${Math.floor(milliseconds / 3600000)}h ${Math.floor((milliseconds % 3600000) / 60000)}m`;
  };

  const calculateStatistics = () => {
    const total = executions.length;
    const completed = executions.filter(e => e.status === 'completed').length;
    const failed = executions.filter(e => e.status === 'failed').length;
    const running = executions.filter(e => e.status === 'running').length;
    const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;

    const totalDuration = executions
      .filter(e => e.duration)
      .reduce((sum, e) => sum + (e.duration || 0), 0);
    const avgDuration = executions.filter(e => e.duration).length > 0
      ? totalDuration / executions.filter(e => e.duration).length
      : 0;

    return { total, completed, failed, running, successRate, avgDuration };
  };

  const handleStartExecution = (workflowId: string) => {
    onExecutionStart?.(workflowId);
    toast({
      title: 'Workflow execution started',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleStopExecution = (executionId: string) => {
    onExecutionStop?.(executionId);
    toast({
      title: 'Workflow execution stopped',
      status: 'warning',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleRetryExecution = (executionId: string) => {
    onExecutionRetry?.(executionId);
    toast({
      title: 'Workflow execution retrying',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteExecution = (executionId: string) => {
    onExecutionDelete?.(executionId);
    toast({
      title: 'Workflow execution deleted',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDownloadLogs = (executionId: string) => {
    onLogsDownload?.(executionId);
    toast({
      title: 'Logs download started',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const stats = calculateStatistics();

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading workflow executions...</Text>
      </Box>
    );
  }

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>Workflow Monitor</Heading>
            <HStack spacing={2}>
              <Switch
                isChecked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                size="sm"
              />
              <Text fontSize="sm">Auto Refresh</Text>
              <Button
                leftIcon={<RepeatIcon />}
                size={compactView ? "sm" : "md"}
                onClick={() => setFilteredExecutions([...executions])}
              >
                Refresh
              </Button>
            </HStack>
          </Flex>
        )}

        {/* Statistics */}
        {showNavigation && (
          <SimpleGrid columns={5} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Executions</StatLabel>
                  <StatNumber>{stats.total}</StatNumber>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Success Rate</StatLabel>
                  <StatNumber>{stats.successRate}%</StatNumber>
                  <StatHelpText>
                    <StatArrow type={stats.successRate >= 90 ? 'increase' : 'decrease'} />
                    {stats.successRate >= 90 ? 'Excellent' : 'Needs attention'}
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Running</StatLabel>
                  <StatNumber color="blue.500">{stats.running}</StatNumber>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Failed</StatLabel>
                  <StatNumber color="red.500">{stats.failed}</StatNumber>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Avg Duration</StatLabel>
                  <StatNumber>{formatDuration(stats.avgDuration)}</StatNumber>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Filters */}
        {showNavigation && (
          <Card>
            <CardBody>
              <SimpleGrid columns={4} spacing={4}>
                <FormControl>
                  <FormLabel>Search</FormLabel>
                  <Input
                    placeholder="Search workflows..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    leftElement={<SearchIcon color="gray.400" />}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Status</FormLabel>
                  <Select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">All Status</option>
                    <option value="running">Running</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="pending">Pending</option>
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Time Range</FormLabel>
                  <Select
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                  >
                    <option value="1h">Last Hour</option>
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                    <option value="all">All Time</option>
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Actions</FormLabel>
                  <Button
                    width="100%"
                    variant="outline"
                    onClick={() => {
                      setSearchTerm('');
                      setStatusFilter('all');
                      setTimeRange('24h');
                    }}
                  >
                    Clear Filters
                  </Button>
                </FormControl>
              </SimpleGrid>
            </CardBody>
          </Card>
        )}

        {/* Executions Table */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>
              Workflow Executions ({filteredExecutions.length})
            </Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Workflow</Th>
                  <Th>Status</Th>
                  <Th>Trigger</Th>
                  <Th>Start Time</Th>
                  <Th>Duration</Th>
                  <Th>Progress</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {filteredExecutions.map(execution => (
                  <Tr
                    key={execution.id}
                    cursor="pointer"
                    _hover={{ bg: 'gray.50' }}
                    onClick={() => {
                      setSelectedExecution(execution);
                      onOpen();
                    }}
                  >
                    <Td>
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="medium">{execution.workflowName}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {execution.id.slice(0, 8)}...
                        </Text>
                      </VStack>
                    </Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(execution.status)}>
                        {execution.status}
                      </Badge>
                    </Td>
                    <Td>{execution.trigger}</Td>
                    <Td>{execution.startTime.toLocaleString()}</Td>
                    <Td>
                      {execution.duration ? formatDuration(execution.duration) : '-'}
                    </Td>
                    <Td width="200px">
                      <Progress
                        value={execution.progress}
                        size="sm"
                        colorScheme={
                          execution.status === 'failed' ? 'red' :
                          execution.status === 'completed' ? 'green' : 'blue'
                        }
                      />
                      <Text fontSize="xs" textAlign="center" mt={1}>
                        {execution.progress}%
                      </Text>
                    </Td>
                    <Td>
                      <HStack spacing={1}>
                        <Tooltip label="View Details">
                          <IconButton
                            aria-label="View execution details"
                            icon={<ViewIcon />}
                            size="sm"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedExecution(execution);
                              onOpen();
                            }}
                          />
                        </Tooltip>
                        {execution.status === 'running' && (
                          <Tooltip label="Stop Execution">
                            <IconButton
                              aria-label="Stop execution"
                              icon={<CloseIcon />}
                              size="sm"
                              variant="ghost"
                              colorScheme="red"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStopExecution(execution.id);
                              }}
                            />
                          </Tooltip>
                        )}
                        {execution.status === 'failed' && (
                          <Tooltip label="Retry Execution">
                            <IconButton
                              aria-label="Retry execution"
                              icon={<RepeatIcon />}
                              size="sm"
                              variant="ghost"
                              colorScheme="blue"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRetryExecution(execution.id);
                              }}
                            />
                          </Tooltip>
                        )}
                        <Tooltip label="Download Logs">
                          <IconButton
                            aria-label="Download logs"
                            icon={<ChevronDownIcon />}
                            size="sm"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadLogs(execution.id);
                            }}
                          />
                        </Tooltip>
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>

            {filteredExecutions.length === 0 && (
              <Box textAlign="center" py={8}>
                <Text color="gray.500">No workflow executions found</Text>
                <Text fontSize="sm" color="gray.400" mt={2}>
                  Try adjusting your filters or check back later
                </Text>
              </Box>
            )}
          </CardBody>
        </Card>

        {/* Execution Details Modal */}
        <Modal isOpen={isOpen} onClose={onClose} size="6xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              <HStack spacing={3}>
