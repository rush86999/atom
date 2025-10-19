import React from 'react';
import { Box, Tabs, TabList, TabPanels, Tab, TabPanel, VStack, Heading } from '@chakra-ui/react';
import WakeWordDetector from '../components/Voice/WakeWordDetector';
import VoiceCommands from '../components/Voice/VoiceCommands';
import ChatInterface from '../components/AI/ChatInterface';

const VoicePage: React.FC = () => {
  return (
    <Box minH="100vh" bg="gray.50" p={6}>
      <VStack spacing={6} align="stretch">
        <Heading size="lg">Voice & AI Features</Heading>

        <Tabs variant="enclosed" colorScheme="blue">
          <TabList>
            <Tab>AI Chat</Tab>
            <Tab>Voice Commands</Tab>
            <Tab>Wake Word Detection</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              <ChatInterface
                showNavigation={true}
                availableModels={['gpt-4', 'gpt-3.5-turbo', 'claude-3', 'llama-2']}
              />
            </TabPanel>

            <TabPanel>
              <VoiceCommands
                showNavigation={true}
                onCommandRecognized={(result) => {
                  console.log('Command recognized:', result);
                }}
                onCommandExecute={(command, parameters) => {
                  console.log('Command executed:', command, parameters);
                }}
              />
            </TabPanel>

            <TabPanel>
              <WakeWordDetector
                showNavigation={true}
                onDetection={(detection) => {
                  console.log('Wake word detected:', detection);
                }}
                onModelChange={(model) => {
                  console.log('Model changed:', model);
                }}
              />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default VoicePage;
