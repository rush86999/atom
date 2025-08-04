interface AgentClientCommand {
    command_id: string;
    action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
    payload?: {
        suggestedTitle?: string;
        linkedEventId?: string;
    };
}
export declare function sendCommandToUser(userId: string, command: AgentClientCommand): Promise<boolean>;
export {};
