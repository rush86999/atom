import React from 'react';
import { Box, Tabs, TabList, TabPanels, Tab, TabPanel, useColorModeValue } from '@chakra-ui/react';
import BYOKManager from '../components/DevStudio/BYOKManager';
import SystemMonitor from '../components/DevStudio/SystemMonitor';
import AtomChatAssistant from '../components/AtomChatAssistant';

const DevStudio = () => {
    const bg = useColorModeValue('gray.50', 'gray.900');

    return (
        <Box minH="100vh" bg={bg} p={8}>
            {/* @ts-ignore */}
            <Tabs variant="enclosed" colorScheme="teal" isLazy>
                <TabList>
                    <Tab fontWeight="bold">AI Providers (BYOK)</Tab>
                    <Tab fontWeight="bold">System Monitor</Tab>
                    <Tab fontWeight="bold">Atom Assistant</Tab>
                </TabList>

                <TabPanels>
                    <TabPanel>
                        <BYOKManager />
                    </TabPanel>
                    <TabPanel>
                        <SystemMonitor />
                    </TabPanel>
                    <TabPanel>
                        <AtomChatAssistant />
                    </TabPanel>
                </TabPanels>
            </Tabs>
        </Box>
    );
};

export default DevStudio;
