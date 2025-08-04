import { HandleMessageResponse } from './handler';
export type InterfaceType = 'text' | 'voice';
interface ConversationState {
    isActive: boolean;
    isAgentResponding: boolean;
    lastInteractionTime: number | null;
    conversationHistory: Array<{
        user: string;
        agent: HandleMessageResponse;
        timestamp: number;
    }>;
    idleTimer: NodeJS.Timeout | null;
    currentIntent: string | null;
    identifiedEntities: Record<string, any> | null;
    userGoal: string | null;
    turnHistory: Array<{
        userInput: string;
        agentResponse: any;
        intent?: string;
        entities?: Record<string, any>;
        timestamp: number;
    }>;
    ltmContext: any[] | null;
}
export declare function getConversationStateSnapshot(interfaceType: InterfaceType): Readonly<ConversationState>;
export declare function setAgentResponding(interfaceType: InterfaceType, isResponding: boolean): void;
export declare function checkIfAgentIsResponding(interfaceType: InterfaceType): boolean;
export declare function deactivateConversation(interfaceType: InterfaceType, reason?: string): void;
export declare function activateConversation(interfaceType: InterfaceType): {
    status: string;
    active: boolean;
};
export declare function recordUserInteraction(interfaceType: InterfaceType, text: string): void;
export declare function recordAgentResponse(interfaceType: InterfaceType, userText: string, agentResponse: HandleMessageResponse, intent?: string, entities?: Record<string, any>): void;
export declare function updateIntentAndEntities(interfaceType: InterfaceType, intent: string | null, entities: Record<string, any> | null): void;
export declare function updateUserGoal(interfaceType: InterfaceType, goal: string | null): void;
export declare function updateLTMContext(interfaceType: InterfaceType, context: any[] | null): void;
export declare function isConversationActive(interfaceType: InterfaceType): boolean;
export declare function getConversationHistory(interfaceType: InterfaceType): Readonly<Array<{
    user: string;
    agent: HandleMessageResponse;
    timestamp: number;
}>>;
export declare function _test_setConversationActive(interfaceType: InterfaceType, active: boolean): void;
export {};
