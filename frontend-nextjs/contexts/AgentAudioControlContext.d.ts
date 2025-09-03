import React, { ReactNode } from 'react';
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
    dispatchAgentCommand: (command: AgentAudioCommand) => void;
    clearLastCommand: () => void;
}
export declare const AgentAudioControlProvider: React.FC<{
    children: ReactNode;
}>;
export declare const useAgentAudioControl: () => AgentAudioControlContextType;
export {};
