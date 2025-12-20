import React, { useState, useEffect } from 'react';
import {
    Box, Container, VStack, HStack, Heading, Text,
    Card, CardBody, CardHeader, Button, Icon, Spinner,
    Badge, SimpleGrid, Flex, useColorModeValue,
    useToast, IconButton, Tooltip, Divider,
    Textarea, Collapse, useDisclosure
} from '@chakra-ui/react';
import {
    FiMail, FiClock, FiSend, FiCheckCircle,
    FiAlertCircle, FiRefreshCw, FiChevronDown, FiChevronUp
} from 'react-icons/fi';
import { emailFollowUpSkill, FollowUpCandidate } from '../../skills/emailFollowUpSkill';

const EmailFollowUpDashboard: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [candidates, setCandidates] = useState<FollowUpCandidate[]>([]);
    const [drafts, setDrafts] = useState<Record<string, string>>({});
    const [sending, setSending] = useState<Record<string, boolean>>({});
    const toast = useToast();

    const bgColor = useColorModeValue('white', 'gray.900');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

    const fetchData = async () => {
        setLoading(true);
        const data = await emailFollowUpSkill.getFollowUpCandidates();
        setCandidates(data);
        setLoading(false);
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleDraft = async (candidate: FollowUpCandidate) => {
        if (drafts[candidate.id]) return;
        const draft = await emailFollowUpSkill.draftFollowUp(candidate);
        setDrafts({ ...drafts, [candidate.id]: draft });
    };

    const handleSend = async (candidate: FollowUpCandidate) => {
        const draft = drafts[candidate.id];
        if (!draft) return;

        setSending({ ...sending, [candidate.id]: true });
        const result = await emailFollowUpSkill.sendFollowUp(candidate.id, draft);
        setSending({ ...sending, [candidate.id]: false });

        if (result.success) {
            toast({
                title: "Follow-up Sent",
                description: `Successfully nudged ${candidate.recipient}`,
                status: "success",
                duration: 3000,
            });
            setCandidates(candidates.filter(c => c.id !== candidate.id));
        } else {
            toast({
                title: "Send Failed",
                description: result.message,
                status: "error",
                duration: 5000,
            });
        }
    };

    if (loading) return <Flex height="400px" align="center" justify="center"><Spinner size="xl" color="blue.500" /></Flex>;

    return (
        <Container maxW="container.xl" py={8}>
            <VStack spacing={8} align="stretch">
                <HStack justify="space-between">
                    <Box>
                        <Heading size="lg">Email Follow-up Center</Heading>
                        <Text color="gray.500">Atom has identified {candidates.length} emails that haven't received a reply.</Text>
                    </Box>
                    <Button leftIcon={<FiRefreshCw />} onClick={fetchData} variant="outline" size="sm">
                        Refresh
                    </Button>
                </HStack>

                {candidates.length === 0 ? (
                    <Flex direction="column" align="center" py={20} bg={useColorModeValue('gray.50', 'whiteAlpha.50')} borderRadius="xl">
                        <Icon as={FiCheckCircle} boxSize={12} color="green.400" mb={4} />
                        <Text fontSize="lg" fontWeight="bold">You're all caught up!</Text>
                        <Text color="gray.500">No sent emails are currently pending a follow-up.</Text>
                    </Flex>
                ) : (
                    <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                        {candidates.map(candidate => (
                            <Card key={candidate.id} bg={bgColor} borderColor={borderColor} borderWidth={1} shadow="sm">
                                <CardBody>
                                    <VStack align="stretch" spacing={4}>
                                        <HStack justify="space-between">
                                            <VStack align="start" spacing={0}>
                                                <Text fontSize="xs" color="gray.500" fontWeight="bold">TO: {candidate.recipient}</Text>
                                                <Heading size="xs" noOfLines={1}>{candidate.subject}</Heading>
                                            </VStack>
                                            <Badge colorScheme="orange">{candidate.days_since_sent} days ago</Badge>
                                        </HStack>

                                        <Box p={3} bg={useColorModeValue('gray.50', 'whiteAlpha.100')} borderRadius="md">
                                            <Text fontSize="sm" color="gray.600" fontStyle="italic">"{candidate.last_message_snippet}"</Text>
                                        </Box>

                                        {drafts[candidate.id] ? (
                                            <VStack align="stretch" spacing={3}>
                                                <Divider />
                                                <Text fontSize="xs" fontWeight="bold" color="blue.500">AI-GENERATED NUDGE</Text>
                                                <Textarea
                                                    value={drafts[candidate.id]}
                                                    onChange={(e) => setDrafts({ ...drafts, [candidate.id]: e.target.value })}
                                                    fontSize="sm"
                                                    rows={5}
                                                    variant="filled"
                                                />
                                                <Button
                                                    leftIcon={<FiSend />}
                                                    colorScheme="blue"
                                                    size="sm"
                                                    isLoading={sending[candidate.id]}
                                                    onClick={() => handleSend(candidate)}
                                                >
                                                    Send Follow-up
                                                </Button>
                                            </VStack>
                                        ) : (
                                            <Button
                                                leftIcon={<FiMail />}
                                                variant="ghost"
                                                colorScheme="blue"
                                                onClick={() => handleDraft(candidate)}
                                                size="sm"
                                            >
                                                Draft Follow-up nudge
                                            </Button>
                                        )}
                                    </VStack>
                                </CardBody>
                            </Card>
                        ))}
                    </SimpleGrid>
                )}
            </VStack>
        </Container>
    );
};

export default EmailFollowUpDashboard;
