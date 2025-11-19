import React from 'react';
import { Box, Tabs, TabList, TabPanels, Tab, TabPanel, useColorModeValue } from '@chakra-ui/react';
import BYOKManager from '../components/DevStudio/BYOKManager';
import SystemMonitor from '../components/DevStudio/SystemMonitor';

const DevStudio = () => {
    const bg = useColorModeValue('gray.50', 'gray.900');

    return (
        <Box minH="100vh" bg={bg} p={8}>
            <Tabs variant="enclosed" colorScheme="teal" isLazy>
                <TabList>
                    <Tab fontWeight="bold">AI Providers (BYOK)</Tab>
                    <Tab fontWeight="bold">System Monitor</Tab>
                </TabList>

                <TabPanels>
                    <TabPanel>
                        <BYOKManager />
                    </TabPanel>
                    <TabPanel>
                        <SystemMonitor />
                    </TabPanel>
                </TabPanels>
            </Tabs>
        </Box>
    );
};

export default DevStudio;
