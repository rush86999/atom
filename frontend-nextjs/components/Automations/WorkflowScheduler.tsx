import React, { useState, useEffect } from 'react';
import {
    Box,
    VStack,
    HStack,
    Heading,
    Text,
    Button,
    FormControl,
    FormLabel,
    Input,
    Select,
    Badge,
    Card,
    CardBody,
    CardHeader,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    IconButton,
    useToast,
    Spinner,
    Alert,
    AlertIcon,
    AlertTitle,
    AlertDescription,
    Tabs,
    TabList,
    TabPanels,
    Tab,
    TabPanel,
    SimpleGrid
} from '@chakra-ui/react';
import { DeleteIcon, TimeIcon, RepeatIcon, CalendarIcon } from '@chakra-ui/icons';

interface ScheduleConfig {
    trigger_type: 'cron' | 'interval' | 'date';
    trigger_config: Record<string, any>;
    input_data?: Record<string, any>;
}

interface ScheduledJob {
    id: string;
    next_run_time: string | null;
    trigger: string;
}

interface WorkflowSchedulerProps {
    workflowId: string;
    workflowName?: string;
}

const WorkflowScheduler: React.FC<WorkflowSchedulerProps> = ({
    workflowId,
    workflowName
}) => {
    const [scheduleType, setScheduleType] = useState<'cron' | 'interval' | 'date'>('interval');
    const [loading, setLoading] = useState(false);
    const [scheduledJobs, setScheduledJobs] = useState<ScheduledJob[]>([]);
    const [refreshing, setRefreshing] = useState(false);
    const toast = useToast();

    // Interval settings
    const [intervalMinutes, setIntervalMinutes] = useState(30);
    const [intervalHours, setIntervalHours] = useState(0);
    const [intervalDays, setIntervalDays] = useState(0);

    // Cron settings
    const [cronExpression, setCronExpression] = useState('0 9 * * *'); // Daily at 9 AM
    const [cronPreset, setCronPreset] = useState('custom');

    // Date settings
    const [runDate, setRunDate] = useState('');
    const [runTime, setRunTime] = useState('');

    const cronPresets = [
        { value: 'custom', label: 'Custom', expression: '' },
        { value: 'hourly', label: 'Every Hour', expression: '0 * * * *' },
        { value: 'daily_9am', label: 'Daily at 9 AM', expression: '0 9 * * *' },
        { value: 'daily_5pm', label: 'Daily at 5 PM', expression: '0 17 * * *' },
        { value: 'weekly_monday', label: 'Weekly on Monday', expression: '0 9 * * 1' },
        { value: 'monthly', label: 'Monthly (1st day)', expression: '0 9 1 * *' },
    ];

    useEffect(() => {
        loadScheduledJobs();
    }, [workflowId]);

    const loadScheduledJobs = async () => {
        try {
            setRefreshing(true);
            const response = await fetch('/api/v1/scheduler/jobs');
            if (response.ok) {
                const allJobs = await response.json();
                // Filter jobs for this workflow (job IDs start with job_{workflowId}_)
                const workflowJobs = allJobs.filter((job: ScheduledJob) =>
                    job.id.includes(workflowId)
                );
                setScheduledJobs(workflowJobs);
            }
        } catch (error) {
            console.error('Error loading scheduled jobs:', error);
        } finally {
            setRefreshing(false);
        }
    };

    const handleSchedule = async () => {
        if (!workflowId) {
            toast({
                title: 'Error',
                description: 'Workflow must be saved first',
                status: 'error',
                duration: 3000,
                isClosable: true,
            });
            return;
        }

        let scheduleConfig: ScheduleConfig;

        try {
            setLoading(true);

            switch (scheduleType) {
                case 'interval':
                    const totalSeconds =
                        intervalDays * 86400 +
                        intervalHours * 3600 +
                        intervalMinutes * 60;

                    if (totalSeconds === 0) {
                        throw new Error('Please specify an interval');
                    }

                    scheduleConfig = {
                        trigger_type: 'interval',
                        trigger_config: {
                            seconds: totalSeconds
                        }
                    };
                    break;

                case 'cron':
                    if (!cronExpression.trim()) {
                        throw new Error('Please enter a cron expression');
                    }

                    // Parse cron expression
                    const cronParts = cronExpression.trim().split(' ');
                    if (cronParts.length !== 5) {
                        throw new Error('Invalid cron expression format (use 5 fields)');
                    }

                    scheduleConfig = {
                        trigger_type: 'cron',
                        trigger_config: {
                            minute: cronParts[0],
                            hour: cronParts[1],
                            day: cronParts[2],
                            month: cronParts[3],
                            day_of_week: cronParts[4]
                        }
                    };
                    break;

                case 'date':
                    if (!runDate || !runTime) {
                        throw new Error('Please specify both date and time');
                    }

                    const runDateTimeStr = `${runDate}T${runTime}:00`;
                    const runDateTime = new Date(runDateTimeStr);

                    if (runDateTime <= new Date()) {
                        throw new Error('Run time must be in the future');
                    }

                    scheduleConfig = {
                        trigger_type: 'date',
                        trigger_config: {
                            run_date: runDateTime.toISOString()
                        }
                    };
                    break;

                default:
                    throw new Error('Invalid schedule type');
            }

            const response = await fetch(`/api/v1/workflows/${workflowId}/schedule`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scheduleConfig),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to schedule workflow');
            }

            const result = await response.json();

            toast({
                title: 'Workflow Scheduled',
                description: `Job ID: ${result.job_id}`,
                status: 'success',
                duration: 4000,
                isClosable: true,
            });

            // Refresh the job list
            await loadScheduledJobs();

            // Reset form
            if (scheduleType === 'date') {
                setRunDate('');
                setRunTime('');
            }
        } catch (error) {
            toast({
                title: 'Scheduling Failed',
                description: error instanceof Error ? error.message : 'Unknown error',
                status: 'error',
                duration: 4000,
                isClosable: true,
            });
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteSchedule = async (jobId: string) => {
        try {
            const response = await fetch(`/api/v1/workflows/${workflowId}/schedule/${jobId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                throw new Error('Failed to delete schedule');
            }

            toast({
                title: 'Schedule Deleted',
                status: 'success',
                duration: 2000,
                isClosable: true,
            });

            await loadScheduledJobs();
        } catch (error) {
            toast({
                title: 'Error',
                description: error instanceof Error ? error.message : 'Failed to delete schedule',
                status: 'error',
                duration: 3000,
                isClosable: true,
            });
        }
    };

    const formatNextRunTime = (isoString: string | null): string => {
        if (!isoString) return 'Never';
        const date = new Date(isoString);
        return date.toLocaleString();
    };

    return (
        <VStack spacing={6} align="stretch">
            <Box>
                <Heading size="md" mb={2}>Schedule Workflow</Heading>
                {workflowName && (
                    <Text color="gray.600" fontSize="sm">
                        Workflow: {workflowName}
                    </Text>
                )}
            </Box>

            <Tabs variant="enclosed" colorScheme="blue">
                <TabList>
                    <Tab onClick={() => setScheduleType('interval')}>
                        <HStack>
                            <RepeatIcon />
                            <Text>Interval</Text>
                        </HStack>
                    </Tab>
                    <Tab onClick={() => setScheduleType('cron')}>
                        <HStack>
                            <TimeIcon />
                            <Text>Cron</Text>
                        </HStack>
                    </Tab>
                    <Tab onClick={() => setScheduleType('date')}>
                        <HStack>
                            <CalendarIcon />
                            <Text>Specific Date</Text>
                        </HStack>
                    </Tab>
                </TabList>

                <TabPanels>
                    {/* Interval Tab */}
                    <TabPanel>
                        <Card>
                            <CardHeader>
                                <Heading size="sm">Run at Regular Intervals</Heading>
                            </CardHeader>
                            <CardBody>
                                <VStack spacing={4} align="stretch">
                                    <Alert status="info" variant="left-accent">
                                        <AlertIcon />
                                        <Box>
                                            <AlertTitle>Interval Schedule</AlertTitle>
                                            <AlertDescription>
                                                The workflow will run repeatedly at the specified interval.
                                            </AlertDescription>
                                        </Box>
                                    </Alert>

                                    <SimpleGrid columns={3} spacing={4}>
                                        <FormControl>
                                            <FormLabel>Days</FormLabel>
                                            <Input
                                                type="number"
                                                min="0"
                                                value={intervalDays}
                                                onChange={(e) => setIntervalDays(parseInt(e.target.value) || 0)}
                                            />
                                        </FormControl>
                                        <FormControl>
                                            <FormLabel>Hours</FormLabel>
                                            <Input
                                                type="number"
                                                min="0"
                                                max="23"
                                                value={intervalHours}
                                                onChange={(e) => setIntervalHours(parseInt(e.target.value) || 0)}
                                            />
                                        </FormControl>
                                        <FormControl>
                                            <FormLabel>Minutes</FormLabel>
                                            <Input
                                                type="number"
                                                min="0"
                                                max="59"
                                                value={intervalMinutes}
                                                onChange={(e) => setIntervalMinutes(parseInt(e.target.value) || 0)}
                                            />
                                        </FormControl>
                                    </SimpleGrid>

                                    <Text fontSize="sm" color="gray.600">
                                        Total: {intervalDays}d {intervalHours}h {intervalMinutes}m
                                    </Text>

                                    <Button
                                        colorScheme="blue"
                                        onClick={handleSchedule}
                                        isLoading={loading}
                                        loadingText="Scheduling..."
                                    >
                                        Schedule Workflow
                                    </Button>
                                </VStack>
                            </CardBody>
                        </Card>
                    </TabPanel>

                    {/* Cron Tab */}
                    <TabPanel>
                        <Card>
                            <CardHeader>
                                <Heading size="sm">Schedule with Cron Expression</Heading>
                            </CardHeader>
                            <CardBody>
                                <VStack spacing={4} align="stretch">
                                    <Alert status="info" variant="left-accent">
                                        <AlertIcon />
                                        <Box>
                                            <AlertTitle>Cron Schedule</AlertTitle>
                                            <AlertDescription>
                                                Use cron expressions for complex scheduling patterns.
                                            </AlertDescription>
                                        </Box>
                                    </Alert>

                                    <FormControl>
                                        <FormLabel>Preset Schedules</FormLabel>
                                        <Select
                                            value={cronPreset}
                                            onChange={(e) => {
                                                const preset = cronPresets.find(p => p.value === e.target.value);
                                                setCronPreset(e.target.value);
                                                if (preset && preset.expression) {
                                                    setCronExpression(preset.expression);
                                                }
                                            }}
                                        >
                                            {cronPresets.map(preset => (
                                                <option key={preset.value} value={preset.value}>
                                                    {preset.label}
                                                </option>
                                            ))}
                                        </Select>
                                    </FormControl>

                                    <FormControl>
                                        <FormLabel>Cron Expression</FormLabel>
                                        <Input
                                            value={cronExpression}
                                            onChange={(e) => {
                                                setCronExpression(e.target.value);
                                                setCronPreset('custom');
                                            }}
                                            placeholder="0 9 * * *"
                                            fontFamily="monospace"
                                        />
                                        <Text fontSize="xs" color="gray.600" mt={1}>
                                            Format: minute hour day month day_of_week (e.g., "0 9 * * *" = Daily at 9 AM)
                                        </Text>
                                    </FormControl>

                                    <Button
                                        colorScheme="blue"
                                        onClick={handleSchedule}
                                        isLoading={loading}
                                        loadingText="Scheduling..."
                                    >
                                        Schedule Workflow
                                    </Button>
                                </VStack>
                            </CardBody>
                        </Card>
                    </TabPanel>

                    {/* Date Tab */}
                    <TabPanel>
                        <Card>
                            <CardHeader>
                                <Heading size="sm">Run Once at Specific Time</Heading>
                            </CardHeader>
                            <CardBody>
                                <VStack spacing={4} align="stretch">
                                    <Alert status="info" variant="left-accent">
                                        <AlertIcon />
                                        <Box>
                                            <AlertTitle>One-Time Schedule</AlertTitle>
                                            <AlertDescription>
                                                The workflow will run once at the specified date and time.
                                            </AlertDescription>
                                        </Box>
                                    </Alert>

                                    <FormControl>
                                        <FormLabel>Date</FormLabel>
                                        <Input
                                            type="date"
                                            value={runDate}
                                            onChange={(e) => setRunDate(e.target.value)}
                                            min={new Date().toISOString().split('T')[0]}
                                        />
                                    </FormControl>

                                    <FormControl>
                                        <FormLabel>Time</FormLabel>
                                        <Input
                                            type="time"
                                            value={runTime}
                                            onChange={(e) => setRunTime(e.target.value)}
                                        />
                                    </FormControl>

                                    {runDate && runTime && (
                                        <Text fontSize="sm" color="gray.600">
                                            Will run at: {new Date(`${runDate}T${runTime}`).toLocaleString()}
                                        </Text>
                                    )}

                                    <Button
                                        colorScheme="blue"
                                        onClick={handleSchedule}
                                        isLoading={loading}
                                        loadingText="Scheduling..."
                                    >
                                        Schedule Workflow
                                    </Button>
                                </VStack>
                            </CardBody>
                        </Card>
                    </TabPanel>
                </TabPanels>
            </Tabs>

            {/* Scheduled Jobs List */}
            <Card>
                <CardHeader>
                    <HStack justify="space-between">
                        <Heading size="sm">Scheduled Jobs</Heading>
                        <IconButton
                            aria-label="Refresh"
                            icon={<RepeatIcon />}
                            size="sm"
                            onClick={loadScheduledJobs}
                            isLoading={refreshing}
                        />
                    </HStack>
                </CardHeader>
                <CardBody>
                    {scheduledJobs.length === 0 ? (
                        <Text color="gray.500" textAlign="center" py={4}>
                            No scheduled jobs for this workflow
                        </Text>
                    ) : (
                        <Table variant="simple" size="sm">
                            <Thead>
                                <Tr>
                                    <Th>Job ID</Th>
                                    <Th>Next Run</Th>
                                    <Th>Trigger</Th>
                                    <Th width="100px">Actions</Th>
                                </Tr>
                            </Thead>
                            <Tbody>
                                {scheduledJobs.map((job) => (
                                    <Tr key={job.id}>
                                        <Td fontFamily="monospace" fontSize="xs">{job.id}</Td>
                                        <Td>{formatNextRunTime(job.next_run_time)}</Td>
                                        <Td>
                                            <Badge colorScheme="blue" fontSize="xs">
                                                {job.trigger.split('[')[0]}
                                            </Badge>
                                        </Td>
                                        <Td>
                                            <IconButton
                                                aria-label="Delete schedule"
                                                icon={<DeleteIcon />}
                                                size="sm"
                                                colorScheme="red"
                                                variant="ghost"
                                                onClick={() => handleDeleteSchedule(job.id)}
                                            />
                                        </Td>
                                    </Tr>
                                ))}
                            </Tbody>
                        </Table>
                    )}
                </CardBody>
            </Card>
        </VStack>
    );
};

export default WorkflowScheduler;
