/**
 * Atom Agent Voice-Finance Integration
 * Direct integration with existing Atom agent skills and NLU
 * Leverages AgentContext and LLM-powered natural language understanding
 */
import { SkillResponse } from '../types';
export declare class FinanceVoiceAgent {
    /**
     * Process voice command through Atom's existing NLU system
     * This integrates directly with Atom's LLM context - no separate voice processing
     */
    processVoiceFinanceCommand(userId: string, voiceText: string, context?: any): Promise<SkillResponse<string>>;
    n: any;
    n: any; /**\n   * Sophisticated voice query enrichment leveraging Atom's LLM
    n   * Handles natural language, context, and intent extraction
    n   */
    n: any;
    private enhanceVoiceQuery;
    private buildFollowUpQuery;
}
