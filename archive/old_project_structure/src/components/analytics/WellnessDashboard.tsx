import React, { useState, useEffect, useMemo } from 'react';
import {
    Box, Container, VStack, HStack, Heading, Text, Divider,
    Grid, Card, CardBody, CardHeader, Button, Icon, Spinner,
    Alert, AlertIcon, AlertTitle, AlertDescription, Badge,
    SimpleGrid, Flex, Stat, StatLabel, StatNumber, StatHelpText,
    StatArrow, Progress, CircularProgress, CircularProgressLabel,
    useColorModeValue, Table, Thead, Tbody, Tr, Th, Td, Tag,
    useToast, IconButton, Tooltip
} from '@chakra-ui/react';
import {
    FiActivity, FiCalendar, FiClock, FiAlertTriangle, FiZap,
    FiCheckCircle, FiMoreHorizontal, FiArrowRight, FiInfo,
    FiUserCheck, FiTarget
} from 'react-icons/fi';
import {
    LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
    Tooltip as RechartsTooltip, ResponsiveContainer, RadarChart,
    PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts';

interface WellnessScore {
    risk_level: string;
    score: number;
    factors: Record<string, number>;
    recommendations: string[];
    type: string;
}

const WellnessDashboard: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [burnoutRisk, setBurnoutRisk] = useState<WellnessScore | null>(null);
    const [deadlineRisk, setDeadlineRisk] = useState<WellnessScore | null>(null);
    const toast = useToast();

    const bgColor = useColorModeValue('white', 'gray.900');
    const borderColor = useColorModeValue('gray.200', 'gray.700');
    const riskColor = (score: number) => score > 70 ? 'red.500' : score > 40 ? 'orange.400' : 'green.500';

    useEffect(() => {
        const fetchData = async () => {
            try {
                // In a real app, these would be actual API calls
                const burnoutRes = await fetch('/api/v1/analytics/burnout-risk');
                const deadlineRes = await fetch('/api/v1/analytics/deadline-risk');

                if (burnoutRes.ok) setBurnoutRisk(await burnoutRes.json());
                if (deadlineRes.ok) setDeadlineRisk(await deadlineRes.json());
            } catch (err) {
                console.error("Failed to fetch wellness data", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const radarData = useMemo(() => {
        if (!burnoutRisk) return [];
        return [
            { subject: 'Meeting density', A: burnoutRisk.factors.meeting_density || 0, fullMark: 100 },
            { subject: 'Backlog Load', A: burnoutRisk.factors.backlog_growth || 0, fullMark: 100 },
            { subject: 'Comm Latency', A: burnoutRisk.factors.comm_latency || 0, fullMark: 100 },
            { subject: 'Deadline Risk', A: deadlineRisk?.score || 0, fullMark: 100 },
            { subject: 'Focus Time', A: 35, fullMark: 100 }, // Mock
        ];
    }, [burnoutRisk, deadlineRisk]);

    if (loading) return <Flex height="400px" align="center" justify="center"><Spinner size="xl" color="purple.500" /></Flex>;

    return (
        <Container maxW="container.xl" py={8}>
            <VStack spacing={8} align="stretch">
                {/* Header */}
                <Flex justify="space-between" align="center">
                    <Box>
                        <Heading size="lg" bgGradient="linear(to-r, purple.400, blue.400)" bgClip="text">
                            Wellness & Productivity Intelligence
                        </Heading>
                        <Text color="gray.500">Monitor burnout risk and optimize your workflow health.</Text>
                    </Box>
                    <HStack>
                        <Badge colorScheme="purple" p={2} borderRadius="md">EXPERIMENTAL FEATURE</Badge>
                        <IconButton aria-label="Settings" icon={<FiInfo />} variant="ghost" />
                    </HStack>
                </Flex>

                {/* Top Stats */}
                <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
                    <Card bg={bgColor} borderColor={borderColor} borderWidth={1} shadow="sm">
                        <CardBody>
                            <HStack spacing={4}>
                                <CircularProgress value={burnoutRisk?.score} color={riskColor(burnoutRisk?.score || 0)} size="80px">
                                    <CircularProgressLabel>{burnoutRisk?.score}%</CircularProgressLabel>
                                </CircularProgress>
                                <VStack align="start" spacing={0}>
                                    <Text fontSize="sm" color="gray.500" fontWeight="bold">BURNOUT RISK</Text>
                                    <Heading size="md">{burnoutRisk?.risk_level}</Heading>
                                </VStack>
                            </HStack>
                        </CardBody>
                    </Card>

                    <Card bg={bgColor} borderColor={borderColor} borderWidth={1} shadow="sm">
                        <CardBody>
                            <Stat>
                                <StatLabel color="gray.500" fontWeight="bold">DEADLINE PRESSURE</StatLabel>
                                <StatNumber fontSize="3xl">{deadlineRisk?.score}%</StatNumber>
                                <StatHelpText>
                                    <StatArrow type={deadlineRisk?.score && deadlineRisk.score > 50 ? 'increase' : 'decrease'} />
                                    {deadlineRisk?.factors.at_risk_count} tasks at risk
                                </StatHelpText>
                            </Stat>
                        </CardBody>
                    </Card>

                    <Card bg={bgColor} borderColor={borderColor} borderWidth={1} shadow="sm">
                        <CardBody>
                            <Stat>
                                <StatLabel color="gray.500" fontWeight="bold">FOCUS HOURS</StatLabel>
                                <StatNumber fontSize="3xl">12.5h</StatNumber>
                                <StatHelpText>Last 7 days</StatHelpText>
                            </Stat>
                        </CardBody>
                    </Card>
                </SimpleGrid>

                {/* Main Analytics Content */}
                <Grid templateColumns={{ base: "1fr", lg: "2fr 1fr" }} gap={8}>
                    {/* Charts Section */}
                    <VStack spacing={6} align="stretch">
                        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
                            <CardHeader pb={0}>
                                <Heading size="sm">Wellness Factor Distribution</Heading>
                            </CardHeader>
                            <CardBody height="350px">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                        <PolarGrid />
                                        <PolarAngleAxis dataKey="subject" />
                                        <PolarRadiusAxis angle={30} domain={[0, 100]} />
                                        <Radar dataKey="A" stroke="#805AD5" fill="#805AD5" fillOpacity={0.6} />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </CardBody>
                        </Card>

                        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
                            <CardHeader pb={0}>
                                <Heading size="sm">Risk Mitigation Center</Heading>
                            </CardHeader>
                            <CardBody spacing={4} as={VStack} align="stretch">
                                <Text fontSize="sm" color="gray.600">AI-suggested actions to reduce overload:</Text>
                                {burnoutRisk?.recommendations.map((rec, i) => (
                                    <HStack key={i} p={3} borderRadius="md" bg="purple.50" justify="space-between" _hover={{ bg: "purple.100" }} transition="0.2s">
                                        <HStack>
                                            <Icon as={FiZap} color="purple.500" />
                                            <Text fontSize="sm" fontWeight="medium">{rec}</Text>
                                        </HStack>
                                        <Button size="xs" colorScheme="purple" variant="ghost" rightIcon={<FiArrowRight />}>Implement</Button>
                                    </HStack>
                                ))}
                            </CardBody>
                        </Card>
                    </VStack>

                    {/* Right Sidebar - Critical Issues */}
                    <VStack spacing={6} align="stretch">
                        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
                            <CardHeader pb={0}>
                                <Heading size="sm" color="red.500">Critical At-Risk Tasks</Heading>
                            </CardHeader>
                            <CardBody>
                                <VStack align="stretch" spacing={3}>
                                    <Box p={3} bg="red.50" borderRadius="md" borderWidth={1} borderColor="red.100">
                                        <HStack justify="space-between" mb={1}>
                                            <Text size="xs" fontWeight="bold">Database Migration</Text>
                                            <Badge colorScheme="red">CRITICAL</Badge>
                                        </HStack>
                                        <Progress value={20} size="xs" colorScheme="red" mb={2} />
                                        <Text fontSize="xs" color="red.700">Due in 24 hours. Only 20% progress detected.</Text>
                                        <HStack mt={3}>
                                            <Button size="xs" variant="outline" colorScheme="red" leftIcon={<FiCalendar />}>Reschedule</Button>
                                            <Button size="xs" variant="solid" colorScheme="red" leftIcon={<FiUserCheck />}>Delegate</Button>
                                        </HStack>
                                    </Box>

                                    <Box p={3} bg="orange.50" borderRadius="md" borderWidth={1} borderColor="orange.100">
                                        <HStack justify="space-between" mb={1}>
                                            <Text size="xs" fontWeight="bold">UI Bug Fixes</Text>
                                            <Badge colorScheme="orange">HIGH RISK</Badge>
                                        </HStack>
                                        <Progress value={10} size="xs" colorScheme="orange" mb={2} />
                                        <Text fontSize="xs" color="orange.700">Due in 4 hours. No recent activity tracked.</Text>
                                        <Button mt={3} size="xs" variant="solid" colorScheme="orange" leftIcon={<FiAlertTriangle />}>Notify Collaborators</Button>
                                    </Box>
                                </VStack>
                            </CardBody>
                        </Card>

                        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
                            <CardHeader pb={0}>
                                <Heading size="sm">Health Tips</Heading>
                            </CardHeader>
                            <CardBody>
                                <VStack align="start" spacing={3}>
                                    <HStack spacing={3}>
                                        <Icon as={FiTarget} color="blue.500" />
                                        <Text fontSize="xs">Try to keep 'Meeting Density' under 5 hours/day.</Text>
                                    </HStack>
                                    <HStack spacing={3}>
                                        <Icon as={FiClock} color="green.500" />
                                        <Text fontSize="xs">Blocking 2h of focus time daily can reduce stress by 20%.</Text>
                                    </HStack>
                                </VStack>
                            </CardBody>
                        </Card>
                    </VStack>
                </Grid>
            </VStack>
        </Container>
    );
};

export default WellnessDashboard;
