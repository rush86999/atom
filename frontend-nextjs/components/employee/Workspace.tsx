import React, { useState, useEffect, useCallback } from 'react';
import { Box, Flex, Text, VStack, Button, Center } from '@chakra-ui/react';
import { Editor } from './Editor';
import { CommandBar } from './CommandBar';

interface WorkspaceProps {
    userId: string;
    workspaceId: string;
}

interface WorkspaceState {
    editorContent: string;
    views: any[];
    plan?: string[];
    deliverables?: { name: string; type: string }[];
}

export const Workspace: React.FC<WorkspaceProps> = ({ userId, workspaceId }) => {
    const [workspaceState, setWorkspaceState] = useState<WorkspaceState>({
        editorContent: '# Your AI Employee Workspace\n\nStarting task...',
        views: [],
        plan: [],
        deliverables: []
    });
    const [realWorkspaceId, setRealWorkspaceId] = useState<string>(workspaceId);
    const [terminalLogs, setTerminalLogs] = useState<string[]>(['$ atom-employee status', '> AI Employee Workspace Active']);
    const [isExecuting, setIsExecuting] = useState(false);

    const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace('localhost', '127.0.0.1');

    const initWorkspace = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/employee/workspace/init?user_id=${userId}`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            setRealWorkspaceId(data.id);
            if (data.workspace_state) {
                setWorkspaceState(data.workspace_state);
            }
        } catch (error) {
            console.error('Failed to init workspace:', error);
            setTerminalLogs(prev => [...prev, '!! Error initializing workspace.']);
        }
    }, [userId, API_BASE]);

    useEffect(() => {
        initWorkspace();
    }, [initWorkspace]);

    const handleRunCommand = async (command: string) => {
        setIsExecuting(true);
        setTerminalLogs(prev => [...prev, `$ ${command}`, '> Initiating task...']);

        try {
            const response = await fetch(`${API_BASE}/api/v1/employee/task`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    command,
                    workspace_id: realWorkspaceId,
                    current_state: workspaceState
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(errorData.detail || 'Generic failure');
            }

            const data = await response.json();
            if (data.new_state) {
                setWorkspaceState(data.new_state);
            }
            if (data.logs) {
                setTerminalLogs(prev => [...prev, ...data.logs]);
            }
        } catch (err: any) {
            setTerminalLogs(prev => [...prev, `!! Execution Error: ${err.message}`]);
        } finally {
            setIsExecuting(false);
        }
    };

    const resetWorkspace = async () => {
        if (!confirm('Are you sure you want to reset the workspace? All logs and progress will be cleared.')) return;
        try {
            const response = await fetch(`${API_BASE}/api/v1/employee/workspace/reset?workspace_id=${realWorkspaceId}`, {
                method: 'POST'
            });
            const data = await response.json();
            if (data.new_state) {
                setWorkspaceState(data.new_state);
                setTerminalLogs(['> Workspace reset.']);
            }
        } catch (err) {
            setTerminalLogs(prev => [...prev, '!! Failed to reset workspace.']);
        }
    };

    return (
        <Box height="calc(100vh - 80px)" p={4} bg={{ base: 'gray.50', _dark: 'gray.950' }}>
            <Flex height="100%" gap={4}>
                {/* Left Sidebar: Plan and Deliverables */}
                <Box width="280px" display="flex" flexDirection="column" gap={4}>
                    {/* Execution Plan */}
                    <Box bg="white" _dark={{ bg: 'gray.900' }} p={4} borderRadius="md" border="1px solid" borderColor="gray.200" flex="1" overflowY="auto">
                        <Flex justify="space-between" align="center" mb={3}>
                            <Text fontWeight="bold" fontSize="sm">Execution Plan</Text>
                            <Button size="xs" variant="ghost" colorScheme="red" onClick={resetWorkspace}>Reset</Button>
                        </Flex>
                        <VStack align="start" spacing={2}>
                            {workspaceState.plan && workspaceState.plan.length > 0 ? (
                                workspaceState.plan.map((step, idx) => (
                                    <Flex key={idx} align="center" gap={2} p={1} w="full" bg={idx === 0 ? "blue.50" : "transparent"} borderRadius="sm">
                                        <Text fontSize="xs" fontWeight="bold" color="blue.500">{idx + 1}.</Text>
                                        <Text fontSize="xs" noOfLines={1}>{step}</Text>
                                    </Flex>
                                ))
                            ) : (
                                <Text fontSize="xs" color="gray.400">No active plan.</Text>
                            )}
                        </VStack>
                    </Box>

                    {/* Deliverables List */}
                    <Box bg="white" _dark={{ bg: 'gray.900' }} p={4} borderRadius="md" border="1px solid" borderColor="gray.200" height="200px" overflowY="auto">
                        <Text fontWeight="bold" fontSize="sm" mb={3}>Deliverables</Text>
                        <VStack align="start" spacing={2}>
                            {workspaceState.deliverables && workspaceState.deliverables.length > 0 ? (
                                workspaceState.deliverables.map((d, idx) => (
                                    <Flex key={idx} align="center" gap={2} p={2} w="full" bg="green.50" borderRadius="sm" border="1px solid" borderColor="green.100">
                                        <Text fontSize="xs" fontWeight="medium" color="green.700">{d.name}</Text>
                                    </Flex>
                                ))
                            ) : (
                                <Text fontSize="xs" color="gray.400">None yet.</Text>
                            )}
                        </VStack>
                    </Box>
                </Box>

                {/* Main Content Area */}
                <Flex flex={1} direction="column" gap={4}>
                    <Flex flex={2} gap={4}>
                        <Box flex={3}>
                            <Editor content={workspaceState.editorContent} onSave={(c) => setWorkspaceState(prev => ({ ...prev, editorContent: c }))} />
                        </Box>
                        <Box flex={2}>
                            <Box height="100%" bg="white" _dark={{ bg: 'gray.900' }} border="1px solid" borderColor="gray.200" borderRadius="md" display="flex" flexDir="column">
                                <Box p={2} borderBottom="1px solid" borderColor="gray.100" bg="gray.50" _dark={{ bg: 'gray.800', borderColor: 'gray.700' }}>
                                    <Text fontSize="xs" fontWeight="bold">Browser Integration</Text>
                                </Box>
                                <Center flex={1} flexDir="column">
                                    <Text fontSize="sm" color="gray.400">Live Browser View</Text>
                                    <Text fontSize="xs" color="gray.300">Scraping 'brennan.ca'...</Text>
                                </Center>
                            </Box>
                        </Box>
                    </Flex>

                    <Flex flex={1} gap={4}>
                        <Box flex={3}>
                            <Box height="100%" bg="gray.900" borderRadius="md" p={3} fontFamily="mono" fontSize="xs" position="relative" overflowY="auto">
                                <Box color="green.400">
                                    {terminalLogs.map((log, i) => <Text key={i}>{log}</Text>)}
                                    {isExecuting && <Text className="animate-pulse" color="blue.300">Thinking...</Text>}
                                </Box>
                                <Box position="absolute" top={2} right={2} color="gray.600">TERMINAL</Box>
                            </Box>
                        </Box>
                        <Box flex={2}>
                            <CommandBar onCommand={handleRunCommand} isLoading={isExecuting} />
                        </Box>
                    </Flex>
                </Flex>
            </Flex>
        </Box>
    );
};

export default Workspace;
