/**
 * Atom Agent Finance NLU Integration
 * Enables "Atom" wake word + natural language finance queries through existing NLU system
 * Integrates fully with wake word activation flow ➜ NLU processor ➜ finance agent
 */
import { AgentContext, NLUHandler } from '../services/agentNluSystem';
/**
 * Finance NLU Handler that plugs into Atom's existing wake-word activated system
 * Wake word "Atom" triggers agent ➜ this NLU handler processes finance commands naturally
 */
export declare const financeNluHandler: NLUHandler;
export declare const activateFinanceThroughWakeWord: () => Promise<{
    awake: boolean;
    listenFor: string[];
    responseMode: string;
}>;
export declare const processFinanceThroughNlu: (context: AgentContext, text: string) => Promise<any>;
export declare const FinanceWakeFlow: {
    title: string;
    description: string;
    flow: string[];
    voiceCommands: string[];
    integration: string;
};
declare const _default: {
    handler: NLUHandler;
    activate: () => Promise<{
        awake: boolean;
        listenFor: string[];
        responseMode: string;
    }>;
    processFinanceThroughNlu: (context: AgentContext, text: string) => Promise<any>;
};
export default _default;
