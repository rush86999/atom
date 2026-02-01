import React, { useState, useEffect } from 'react';
import {
    Box,
    VStack,
    HStack,
    Heading,
    Text,
    Progress,
    Card,
    CardHeader,
    CardBody,
    Badge,
    Icon,
    Button,
    SimpleGrid,
    List,
    ListItem,
    ListIcon,
    Divider,
    useColorModeValue,
    Flex,
    Tooltip,
} from '@chakra-ui/react';
import {
    CheckCircleIcon,
    TimeIcon,
    WarningIcon,
    InfoIcon,
    ArrowForwardIcon,
    TargetIcon, // Assuming custom icon or using EmailIcon as fallback
} from '@chakra-ui/icons';

interface SubTask {
    id: string;
    title: string;
    due_date: string;
    status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'DELAYED';
}

interface Goal {
    id: string;
    title: string;
    progress: number;
    status: 'ACTIVE' | 'COMPLETED' | 'AT_RISK';
    target_date: string;
    sub_tasks: SubTask[];
}

const GoalDashboard: React.FC = () => {
    const [goals, setGoals] = useState<Goal[]>([]);
    const [loading, setLoading] = useState(true);

    const bgColor = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

    useEffect(() => {
        // Mock fetching goals
        const mockGoals: Goal[] = [
            {
                id: '1',
                title: 'Close Q4 Enterprise Deal',
                progress: 25,
                status: 'ACTIVE',
                target_date: '2025-12-31',
                sub_tasks: [
                    { id: '1-1', title: 'Initial Discovery Call', due_date: '2025-12-05', status: 'COMPLETED' },
                    { id: '1-2', title: 'Proposal Drafting', due_date: '2025-12-15', status: 'IN_PROGRESS' },
                    { id: '1-3', title: 'Technical Review', due_date: '2025-12-20', status: 'PENDING' },
                    { id: '1-4', title: 'Final Negotiation', due_date: '2025-12-30', status: 'PENDING' },
                ],
            },
            {
                id: '2',
                title: 'Hire Senior Product Manager',
                progress: 50,
                status: 'AT_RISK',
                target_date: '2025-12-25',
                sub_tasks: [
                    { id: '2-1', title: 'Job Description', due_date: '2025-11-20', status: 'COMPLETED' },
                    { id: '2-2', title: 'Candidate Sourcing', due_date: '2025-12-01', status: 'COMPLETED' },
                    { id: '2-3', title: 'First Round Interviews', due_date: '2025-12-10', status: 'DELAYED' },
                    { id: '2-4', title: 'Onsite Loop', due_date: '2025-12-20', status: 'PENDING' },
                ],
            },
        ];

        setTimeout(() => {
            setGoals(mockGoals);
            setLoading(false);
        }, 800);
    }, []);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'COMPLETED': return 'green';
            case 'ACTIVE': return 'blue';
            case 'AT_RISK': return 'red';
            case 'DELAYED': return 'orange';
            default: return 'gray';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'COMPLETED': return CheckCircleIcon;
            case 'DELAYED': return WarningIcon;
            case 'AT_RISK': return WarningIcon;
            case 'IN_PROGRESS': return TimeIcon;
            default: return InfoIcon;
        }
    };

    return (
        <Box p={6}>
            <VStack spacing={8} align="stretch">
                <HStack justify="space-between">
                    <VStack align="left" spacing={0}>
                        <Heading size="lg">Goal-Driven Automation</Heading>
                        <Text color="gray.500">Atom is managing your top objectives</Text>
                    </VStack>
                    <Button leftIcon={<ArrowForwardIcon />} colorScheme="blue">New Goal</Button>
                </HStack>

                <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                    {goals.map((goal) => (
                        <Card key={goal.id} variant="outline" bg={bgColor} borderColor={borderColor}>
                            <CardHeader>
                                <HStack justify="space-between" mb={2}>
                                    <Heading size="md">{goal.title}</Heading>
                                    <Badge colorScheme={getStatusColor(goal.status)}>{goal.status}</Badge>
                                </HStack>
                                <VStack align="stretch" spacing={1}>
                                    <HStack justify="space-between">
                                        <Text fontSize="sm">Overall Progress</Text>
                                        <Text fontSize="sm" fontWeight="bold">{goal.progress}%</Text>
                                    </HStack>
                                    <Progress value={goal.progress} size="sm" colorScheme={getStatusColor(goal.status)} borderRadius="full" />
                                </VStack>
                            </CardHeader>
                            <CardBody>
                                <Text fontWeight="bold" fontSize="sm" mb={3}>Sub-Tasks</Text>
                                <List spacing={3}>
                                    {goal.sub_tasks.map((task) => (
                                        <ListItem key={task.id}>
                                            <HStack justify="space-between" align="center">
                                                <HStack spacing={3}>
                                                    <ListIcon as={getStatusIcon(task.status)} color={`${getStatusColor(task.status)}.500`} />
                                                    <VStack align="left" spacing={0}>
                                                        <Text fontSize="sm" fontWeight={task.status === 'COMPLETED' ? 'normal' : 'bold'} textDecoration={task.status === 'COMPLETED' ? 'line-through' : 'none'} color={task.status === 'COMPLETED' ? 'gray.500' : 'inherit'}>
                                                            {task.title}
                                                        </Text>
                                                        <Text fontSize="xs" color="gray.500">Due: {new Date(task.due_date).toLocaleDateString()}</Text>
                                                    </VStack>
                                                </HStack>
                                                {task.status === 'DELAYED' && (
                                                    <Tooltip label="Atom suggests rescheduling or nudging contact">
                                                        <Button size="xs" colorScheme="orange" variant="ghost">Remediate</Button>
                                                    </Tooltip>
                                                )}
                                                {task.status === 'IN_PROGRESS' && (
                                                    <Badge size="xs" variant="outline">Working</Badge>
                                                )}
                                            </HStack>
                                        </ListItem>
                                    ))}
                                </List>
                            </CardBody>
                        </Card>
                    ))}
                </SimpleGrid>

                <Card variant="filled" bg={useColorModeValue('blue.50', 'blue.900')}>
                    <CardBody>
                        <HStack spacing={4}>
                            <Icon as={InfoIcon} color="blue.500" boxSize={6} />
                            <VStack align="left" spacing={0}>
                                <Text fontWeight="bold">Proactive Monitoring Active</Text>
                                <Text fontSize="sm">Atom will escalate if sub-tasks fall behind their projected deadlines.</Text>
                            </VStack>
                        </HStack>
                    </CardBody>
                </Card>
            </VStack>
        </Box>
    );
};

export default GoalDashboard;
