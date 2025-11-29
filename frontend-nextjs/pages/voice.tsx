import React from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import WakeWordDetector from '../components/Voice/WakeWordDetector';
import VoiceCommands from '../components/Voice/VoiceCommands';


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
            <div className="p-6 text-center bg-white dark:bg-gray-800 rounded-lg shadow">
              <h3 className="text-lg font-medium mb-2">AI Chat is now Global!</h3>
              <p className="text-gray-600 dark:text-gray-400">
                Click the chat icon in the bottom-right corner to access the AI assistant from anywhere in the application.
              </p>
            </div>
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
