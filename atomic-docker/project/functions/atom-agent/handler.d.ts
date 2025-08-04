import { AgentClientCommand } from '../types';
export interface HandleMessageResponse {
    text: string;
    audioUrl?: string;
    error?: string;
    structuredData?: any;
}
/**
 * Activates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/activate
 */
export declare function activateConversationWrapper(): Promise<{
    status: string;
    active: boolean;
    message?: string;
}>;
/**
 * Deactivates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/deactivate
 */
export declare function deactivateConversationWrapper(reason?: string): Promise<{
    status: string;
    active: boolean;
    message?: string;
}>;
/**
 * Handles an interrupt signal.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/interrupt
 */
export declare function handleInterruptWrapper(): Promise<{
    status: string;
    message: string;
}>;
/**
 * Handles transcribed text input for an ongoing conversation.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/conversation
 * Expects payload: { "text": "user's transcribed speech" }
 */
export declare function handleConversationInputWrapper(payload: {
    text: string;
}, optionsFromCaller?: TempOptionsForCaller): Promise<HandleMessageResponse | {
    error: string;
    active: boolean;
    message?: string;
}>;
interface TempOptionsForCaller {
    sendCommandToClientFunction?: (userId: string, command: AgentClientCommand) => Promise<boolean>;
}
/**
 * This is the original handleMessage function, primarily for Hasura Action.
 * It remains largely stateless and does not interact with isAgentResponding by default.
 * If Hasura actions need to be part of conversational flow, this would require more thought.
 */
export declare function handleMessage(message: string, settings: any): Promise<HandleMessageResponse>;
export declare function testActivateConversation(): Promise<{
    status: string;
    active: any;
    agentResponding: any;
}>;
export declare function testDeactivateConversation(): Promise<{
    status: string;
    active: any;
    agentResponding: any;
}>;
export declare function getConversationStatus(): Promise<{
    voice_active: any;
    voice_agentResponding: any;
    text_active: any;
    text_agentResponding: any;
    voice_state: any;
    text_state: any;
}>;
export {};
