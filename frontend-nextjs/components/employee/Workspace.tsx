import React, { useState, useEffect } from 'react';
import { Box, Grid, GridItem, Flex, Text, VStack } from '@chakra-ui/react';
import { Editor } from './Editor';
import { CommandBar } from './CommandBar';

interface WorkspaceProps {
    userId: string;
    workspaceId: string;
}

export const Workspace: React.FC<WorkspaceProps> = ({ userId, workspaceId }) => {
    const [workspaceState, setWorkspaceState] = useState<any>(null);
    const [realWorkspaceId, setRealWorkspaceId] = useState<string>(workspaceId);
    const [terminalLogs, setTerminalLogs] = useState<string[]>(['$ atom-employee status', '> AI Employee Workspace Active']);
    const [isExecuting, setIsExecuting] = useState(false);

    useEffect(() => {
        const fetchWorkspace = async () => {
            try {
                // Bypass Next.js proxy and hit backend directly to avoid 404s during dev
                const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace('localhost', '127.0.0.1');
                const response = await fetch(`${API_BASE}/api/v1/employee/workspace/init?user_id=${userId}`, {
                    method: 'POST'
                });
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setWorkspaceState(data.workspace_state);
                setRealWorkspaceId(data.id);
            } catch (error) {
                console.error('Failed to init workspace:', error);
            }
        };

        fetchWorkspace();
    }, [userId, workspaceId]);

    // Save workspace state when it changes
    useEffect(() => {
        if (!workspaceState || !realWorkspaceId) return;

        const saveTimeout = setTimeout(async () => {
            try {
                const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace('localhost', '127.0.0.1');
                await fetch(`${API_BASE}/api/v1/employee/workspace/save?workspace_id=${realWorkspaceId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(workspaceState)
                });
            } catch (error) {
                console.error('Failed to save workspace:', error);
            }
        }, 3000); // Debounce save

        return () => clearTimeout(saveTimeout);
    }, [workspaceState, realWorkspaceId]);

    const handleRunCommand = async (command: string) => {
        setIsExecuting(true);
        setTerminalLogs(prev => [...prev, `$ ${command}`, '> Initiating task...']);

        try {
            const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace('localhost', '127.0.0.1');
            const response = await fetch(`${API_BASE}/api/v1/employee/task`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workspace_id: realWorkspaceId,
                    command: command,
                    current_state: workspaceState
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                setTerminalLogs(prev => [...prev, `> Server Error: ${response.status} - ${errorData.detail || 'Generic failure'}`]);
                setIsExecuting(false);
                return;
            }

            const result = await response.json();

            if (result.logs) {
                setTerminalLogs(prev => [...prev, ...result.logs]);
            }

            if (result.new_state) {
                setWorkspaceState(result.new_state);
            }

        } catch (error: any) {
            setTerminalLogs(prev => [...prev, `> Network Error: ${error.message || 'Failed to connect to backend'}`]);
            console.error('Task execution failed:', error);
        } finally {
            setIsExecuting(false);
        }
    };

    if (!workspaceState) return <Box p={10}>Loading Workspace...</Box>;

    return (
        <Box h="calc(100vh - 100px)" bg={{ base: 'gray.50', _dark: 'gray.900' }} display="flex" flexDirection="column">
            <Box flex={1} p={4} overflow="hidden">
                <Grid
                    h="full"
                    templateRows="repeat(2, 1fr)"
                    templateColumns="repeat(5, 1fr)"
                    gap={4}
                >
                    {/* Main Work Area (Canvas/Editor) */}
                    <GridItem rowSpan={2} colSpan={3}>
                        <Editor
                            content={workspaceState.editorContent}
                            onSave={(content) => {
                                setWorkspaceState({ ...workspaceState, editorContent: content });
                            }}
                            title="Work-in-Progress Artifact"
                        />
                    </GridItem>

                    {/* Browser View (Secondary) */}
                    <GridItem colSpan={2} bg={{ base: 'white', _dark: 'gray.800' }} borderRadius="md" border="1px solid" borderColor="gray.200" overflow="hidden">
                        <Flex direction="column" h="full">
                            <Box p={2} borderBottom="1px solid" borderColor="gray.200" bg="gray.50">
                                <Text fontSize="xs" fontWeight="bold">Browser</Text>
                            </Box>
                            <Box flex={1} bg="white">
                                <Text p={4} textAlign="center" color="gray.400" fontSize="sm">Browser session will appear here.</Text>
                            </Box>
                        </Flex>
                    </GridItem>

                    {/* Terminal / Logs (Tertiary) */}
                    <GridItem colSpan={2} bg="black" borderRadius="md" overflow="hidden">
                        <Flex direction="column" h="full">
                            <Box p={2} borderBottom="1px solid" borderColor="gray.700" bg="gray.900">
                                <Text fontSize="xs" fontWeight="bold" color="white">Terminal</Text>
                            </Box>
                            <Box flex={1} p={3} fontFamily="mono" fontSize="xs" color="green.400" overflowY="auto">
                                {terminalLogs.map((log, i) => (
                                    <Text key={i} color={log.startsWith('$') ? 'green.400' : 'gray.400'}>
                                        {log}
                                    </Text>
                                ))}
                            </Box>
                        </Flex>
                    </GridItem>
                </Grid>
            </Box>

            <CommandBar onCommand={handleRunCommand} isLoading={isExecuting} />
        </Box>
    );
};

export default Workspace;
