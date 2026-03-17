import React, { useState, useEffect } from 'react';
import { Box, Grid, GridItem, Flex, Text, VStack } from '@chakra-ui/react';
import { Editor } from './Editor';

interface WorkspaceProps {
    userId: string;
    workspaceId: string;
}

export const Workspace: React.FC<WorkspaceProps> = ({ userId, workspaceId }) => {
    const [workspaceState, setWorkspaceState] = useState<any>(null);
    const [realWorkspaceId, setRealWorkspaceId] = useState<string>(workspaceId);

    useEffect(() => {
        const fetchWorkspace = async () => {
            try {
                const response = await fetch(`/api/v1/employee/workspace/init?user_id=${userId}`, {
                    method: 'POST'
                });
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
                await fetch(`/api/v1/employee/workspace/save?workspace_id=${realWorkspaceId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(workspaceState)
                });
            } catch (error) {
                console.error('Failed to save workspace:', error);
            }
        }, 1000); // Debounce save

        return () => clearTimeout(saveTimeout);
    }, [workspaceState, realWorkspaceId]);

    if (!workspaceState) return <Box p={10}>Loading Workspace...</Box>;

    return (
        <Box h="calc(100vh - 100px)" bg={{ base: 'gray.50', _dark: 'gray.900' }} p={4}>
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
                            // Sync with backend
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
                        <Box flex={1} p={3} fontFamily="mono" fontSize="xs" color="green.400">
                            <Text>$ atom-employee status</Text>
                            <Text color="gray.400">> AI Employee Workspace Active</Text>
                        </Box>
                    </Flex>
                </GridItem>
            </Grid>
        </Box>
    );
};

export default Workspace;
