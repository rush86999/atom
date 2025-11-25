import React from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import WakeWordDetector from '../components/Voice/WakeWordDetector';
import VoiceCommands from '../components/Voice/VoiceCommands';
import ChatInterface from '../components/AI/ChatInterface';

const VoicePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="flex flex-col space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Voice & AI Features</h1>

        <Tabs defaultValue="chat" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="chat">AI Chat</TabsTrigger>
            <TabsTrigger value="commands">Voice Commands</TabsTrigger>
            <TabsTrigger value="wakeword">Wake Word Detection</TabsTrigger>
          </TabsList>

          <TabsContent value="chat" className="mt-6">
            <ChatInterface
              showNavigation={true}
              availableModels={['gpt-4', 'gpt-3.5-turbo', 'claude-3', 'llama-2']}
            />
          </TabsContent>

          <TabsContent value="commands" className="mt-6">
            <VoiceCommands
              showNavigation={true}
              onCommandRecognized={(result) => {
                console.log('Command recognized:', result);
              }}
              onCommandExecute={(command, parameters) => {
                console.log('Command executed:', command, parameters);
              }}
            />
          </TabsContent>

          <TabsContent value="wakeword" className="mt-6">
            <WakeWordDetector
              showNavigation={true}
              onDetection={(detection) => {
                console.log('Wake word detected:', detection);
              }}
              onModelChange={(model) => {
                console.log('Model changed:', model);
              }}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default VoicePage;
