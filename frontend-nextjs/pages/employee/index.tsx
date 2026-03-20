import React from 'react';
import Head from 'next/head';
import { Box, Container, Heading, Text, VStack, Button } from '@chakra-ui/react';
import { Workspace } from '../../components/employee/Workspace';

const EmployeeDashboard = () => {
    const [isStarted, setIsStarted] = React.useState(false);

    if (isStarted) {
        return (
            <Box minH="100vh" bg={{ base: 'white', _dark: 'gray.900' }}>
                <Head>
                    <title>AI Employee Workspace | ATOM</title>
                </Head>
                <Box borderBottom="1px solid" borderColor="gray.200" p={4} bg="white">
                    <Heading size="md">AI Employee Workspace</Heading>
                    <Text fontSize="xs" color="gray.500">Autonomous Mode: Supervised | Project: OpenClaw Competitor</Text>
                </Box>
                <Workspace userId="user_123" workspaceId="workspace_456" />
            </Box>
        );
    }

    return (
        <Container maxW="container.md" py={20}>
            <Head>
                <title>Hire an AI Employee | ATOM</title>
            </Head>
            <VStack spacing={8} align="center" textAlign="center">
                <Box p={4} borderRadius="full" bg="blue.50" color="blue.500" fontSize="4xl">
                    🤖
                </Box>
                <VStack spacing={3}>
                    <Heading size="2xl">Meet your new AI Employee</Heading>
                    <Text fontSize="lg" color="gray.500">
                        A high-performance assistant that works in a persistent, canvas-based workspace.
                        Drafts deliverables, browses the web, and executes code autonomously.
                    </Text>
                </VStack>

                <Box
                    p={6}
                    borderRadius="xl"
                    border="1px solid"
                    borderColor="gray.200"
                    w="full"
                    bg="white"
                    boxShadow="sm"
                >
                    <VStack align="start" spacing={4}>
                        <Text fontWeight="bold">Choose a Persona</Text>
                        <VStack w="full" spacing={2}>
                            <Button w="full" variant="outline" justifyContent="start" borderRadius="lg" height="60px">
                                <Box textAlign="left">
                                    <Text fontWeight="bold" fontSize="sm">Market Researcher</Text>
                                    <Text fontSize="xs" color="gray.500">Analyzes trends and drafts reports.</Text>
                                </Box>
                            </Button>
                            <Button w="full" variant="outline" justifyContent="start" borderRadius="lg" height="60px" borderColor="blue.500" bg="blue.50">
                                <Box textAlign="left">
                                    <Text fontWeight="bold" fontSize="sm">Operations Manager</Text>
                                    <Text fontSize="xs" color="gray.500">Organizes projects and tracks sub-tasks.</Text>
                                </Box>
                            </Button>
                        </VStack>
                    </VStack>
                </Box>

                <Button size="lg" colorScheme="blue" px={10} borderRadius="full" onClick={() => setIsStarted(true)}>
                    Enter Workspace
                </Button>
            </VStack>
        </Container>
    );
};

export default EmployeeDashboard;
