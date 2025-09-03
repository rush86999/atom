import React, { createContext, useState, useContext, ReactNode, useCallback } from 'react';

// Define the structure of commands received from the agent
// This should align with the `AgentClientCommand` defined in the agent skill
export interface AgentAudioCommand {
  command_id: string;
  action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
  };
}

interface AgentAudioControlContextType {
  latestCommand: AgentAudioCommand | null;
  dispatchAgentCommand: (command: AgentAudioCommand) => void; // Called by WebSocket listener
  clearLastCommand: () => void; // Called by components after consuming the command
}

const AgentAudioControlContext = createContext<AgentAudioControlContextType | undefined>(undefined);

export const AgentAudioControlProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [latestCommand, setLatestCommand] = useState<AgentAudioCommand | null>(null);

  const dispatchAgentCommand = useCallback((command: AgentAudioCommand) => {
    console.log('AgentAudioControlContext: Dispatching command:', command);
    setLatestCommand(command);
  }, []);

  const clearLastCommand = useCallback(() => {
    console.log('AgentAudioControlContext: Clearing last command.');
    setLatestCommand(null);
  }, []);

  return (
    <AgentAudioControlContext.Provider value={{ latestCommand, dispatchAgentCommand, clearLastCommand }}>
      {children}
    </AgentAudioControlContext.Provider>
  );
};

export const useAgentAudioControl = (): AgentAudioControlContextType => {
  const context = useContext(AgentAudioControlContext);
  if (context === undefined) {
    throw new Error('useAgentAudioControl must be used within an AgentAudioControlProvider');
  }
  return context;
};

// Example of how a WebSocket listener might use this context:
// (This part would NOT be in this file, but in your WebSocket handling logic)
/*
function webSocketMessageHandler(message: any, dispatchAgentCommand: (command: AgentAudioCommand) => void) {
  try {
    const parsedMessage = JSON.parse(message.data); // Or however messages are structured

    // Check if it's an audio control command
    if (parsedMessage && parsedMessage.type === 'AGENT_AUDIO_CONTROL_COMMAND' && parsedMessage.commandDetails) {
      const commandDetails = parsedMessage.commandDetails as AgentAudioCommand;
      // Validate commandDetails structure if necessary
      if (commandDetails.action && commandDetails.command_id) {
         dispatchAgentCommand(commandDetails);
      } else {
        console.warn("Received invalid agent audio command structure:", commandDetails);
      }
    } else {
      // Handle other types of WebSocket messages
    }
  } catch (error) {
    console.error("Error processing WebSocket message:", error);
  }
}

// Somewhere in your app where WebSocket is initialized:
// const { dispatchAgentCommand } = useAgentAudioControl(); // If context is available globally
// or pass dispatchAgentCommand to your WebSocket service.
// webSocket.onmessage = (event) => webSocketMessageHandler(event, dispatchAgentCommand);
*/
