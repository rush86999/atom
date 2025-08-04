interface AgentClientCommand {
    command_id: string;
    action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
    payload?: {
        suggestedTitle?: string;
        linkedEventId?: string;
    };
}
declare const assistant_brain: (eventPayload: string | Buffer, // Changed 'event' to 'eventPayload' for clarity
userIdFromWs: string, // Explicitly passed by server.ts
sendCommandToUserFunc?: (userId: string, command: AgentClientCommand) => Promise<boolean>) => Promise<string>;
export default assistant_brain;
