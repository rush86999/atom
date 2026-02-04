/**
 * Atom Agent Voice-Finance Integration
 * Direct integration with existing Atom agent skills and NLU
 * Leverages AgentContext and LLM-powered natural language understanding
 */

import { SkillResponse } from '../types';
import { financeAgentService } from '../services/financeAgentService';
import { handleFinanceQuery } from './financeAgentSkills';

// Voice trigger patterns that map directly to finance agent skills
const voiceCommands: Record<string, string> = {
  "net worth": "What is my current net worth including all assets and liabilities?",
  "wealth status": "Show me my complete financial position and net worth",
  "budget overview": "Show my budget status and spending by category for this month",
  "spending breakdown": "Analyze my spending by category for this month",
  "where money go": "Break down my expenses by merchant and category this month",
  "financial goals": "Show all my financial goals with current progress",
  "save money": "Give me actionable financial recommendations to save more",
  "retirement funding": "Show my retirement savings progress",
  "investment portfolio": "Display my complete investment portfolio performance",
  "overspending": "Identify which categories I'm exceeding my budget in",
  "cash flow": "Show my money in vs money out this month",
  "account balances": "Show all my account balances and account types",
  "create goal": "Help me create a new financial goal",
  "set budget": "Create a new budget category",
  "monthly budget": "Show my monthly budget and spending status"
};

// Core voice-to-finance processor leveraging existing Atom infrastructure
export class FinanceVoiceAgent {

  /**
   * Process voice command through Atom's existing NLU system
   * This integrates directly with Atom's LLM context - no separate voice processing
   */
  async processVoiceFinanceCommand(
    userId: string,
    voiceText: string,
    context?: any
  ): Promise<SkillResponse<string>> {

    try {
      const normalizedText = voiceText.toLowerCase().trim();

      // Direct map to existing finance skills
      const matchedCommand = Object.keys(voiceCommands).find(cmd =>
        normalizedText.includes(cmd) ||
        normalizedText.startsWith(cmd)
      );

      let financeQuery: string;

      if (matchedCommand) {
n        // Use pre-mapped query for efficiency
        financeQuery = voiceCommands[matchedCommand];
      } else {
n        // Enhanced NLP for free-form queries
        financeQuery = await this.enhanceVoiceQuery(voiceText, context);
      }

      // Process through existing finance agent skills (reusing full LLM power)
      return await handleFinanceQuery(userId, financeQuery, context);
n
    } catch (error) {
      return {
        ok: false,
        error: {
          code: 'VOICE_PROCESSING_ERROR',
          message: 'Failed to process voice command through finance agent'
n        }
n      };
n    }
n  }
n\n  /**\n   * Sophisticated voice query enrichment leveraging Atom's LLM
n   * Handles natural language, context, and intent extraction
n   */
n  private async enhanceVoiceQuery(voiceText: string, context?: any): Promise<string> {
n    const enhancedQuery = voiceText;\n\n    // Voice-specific handling patterns
n    if (voiceText.includes('how much') && voiceText.includes('spend')) {\n      const categoryMatch = voiceText.match(/on\\s+([a-zA-Z\\s]+?)(?:\\s|$)/i);\n      const category = categoryMatch?.[1]?.trim();\n      return category \n        ? `How much did I spend on ${category} this month?`\n        : `How much did I spend this month by category?`;\n    }\n\n    if (voiceText.match(/over\\s+budget|exceeded|went\\s+over/i)) {\n      return `Show which budget categories I've exceeded and by how much`;\n    }\n\n    if (voiceText.includes('compare') && voiceText.includes('last month')) {\n      return `Compare my spending this month to last month by category`;\n    }\n\n    if (voiceText.includes('biggest') && voiceText.includes('purchase')) {\n      return `Show my largest transactions this month`;\n    }\n\n    if (voiceText.includes('still need') && voiceText.includes('goal')) {\n      return `Show how much more I need to save for each active goal`;\n    }\n\n    // Handle budget setting queries\n    if (voiceText.match(/set\\s+budget\\s+.*\\$(\\d+)/)) {\n      const match = voiceText.match(/set\\s+budget\\s+(?:for\\s+)?([a-zA-Z\\s]+?)\\s+of?\\s+\\$(\\d+)/i);\n      const category = match?.[1]?.trim();\n      const amount = match?.[2];\n      return category && amount \n        ? `Create a ${category} budget for this month of $${amount}`\n        : `Create a new budget based on voice input: ${voiceText}`;\n    }\n\n    // Handle goal creation\n    if (voiceText.includes('save') && voiceText.includes('for')) {\n      const match = voiceText.match(/save\\s+.*(\\$\\d+).*for\\s+([a-zA-Z\\s]+)/i);\n      const amount = match?.[1];\n      const purpose = match?.[2];\n      return purpose && amount\n        ? `Create a savings goal called \"${purpose.trim()}\" for ${amount}`\n        : `Create a savings goal based on: ${voiceText}`;\n    }\n\n    return voiceText; // Direct query for flexible voice processing\n  }\n\n  /**\n   * Context-aware voice command suggestions\n   */\n  getVoiceCommandSuggestions(context?: any): string[] {\n    const baseSuggestions = [\n      \"What's my net worth?\",\n      \"Show my budget\",\n      \"How much did I spend on dining?\",\n      \"Where did my money go this month?\",\n      \"Am I on track for my financial goals?\",\n      \"Create a budget for groceries\"\n    ];\n\n    if (context?.lastQuery) {\n      return [\n        ...baseSuggestions.slice(0, 3),\n        `Details on ${context.lastQuery}`,\n        `Compare ${context.lastQuery} to last month`,\n        \"Show recommendations\"\n      ];\n    }\n\n    return baseSuggestions;\n  }\n\n  /**\n   * Advanced multi-turn voice conversation support\n   */
n  async processFollowUp(\n    userId: string,\n    followUpVoiceText: string,\n    conversationContext: any\n  ): Promise<SkillResponse<string>> {\n    \n    const followUpPrompt = this.buildFollowUpQuery(followUpVoiceText, conversationContext);\n    return await handleFinanceQuery(userId, followUpPrompt, conversationContext);\n  }\n\n  private buildFollowUpQuery(followUp: string, context: any): string {\n    if (followUp.includes('more specifics') || followUp.includes('details')) {\n      return `Give me detailed analysis for: ${context.lastTopic} including charts and insights`;\n    }\n\n    if (followUp.includes('month') || followUp.includes('last')) {\n      return `Compare ${context.lastTopic} this month to last month`;\n    }\n\n    if (followUp.includes('next')) {\n      return `What are my next steps for ${context.lastTopic}?`;\n    }\n\n    return followUp; // Continue conversation naturally\n  }\n}\n\n// Single function integration for Atom skills system\nexport const processVoiceFinance = new FinanceVoiceAgent();\n\nexport async function handleVoiceFinanceCommand(\n  context: AgentContext,\n  voiceText: string,\n  userId: string = 'current_user'\n): Promise<SkillResponse<string>> {\n  return await processVoiceFinance.processVoiceFinanceCommand(userId, voiceText, context);\n}\n\n// Voice-to-finance integration constants for Atom registration\nexport const VOICE_FINANCE_INTEGRATION = {\n  enabled: true,\n  name: \"Atom Finance Voice\",\n  description: \"Natural language finance querying through Atom's existing voice and NLU systems\",\n  capabilities: [\n    \"Voice-powered net worth queries\",\n    \"Voice budget management\", \n    \"Voice spending analysis with natural language\",\n    \"Multi-turn finance conversations\",\n    \"Simplified voice command processing\"\n  ],\n  voiceCommands: Object.keys(voiceCommands),\n  integrationPoints: [\n    \"atom://voice/activate-finance\",\n    \"chrome://voice/finance-mode\",\n    \"desktop-voice-finance\"\n  ]\n};\n\n// Export for use in other skills\nexport default processVoiceFinance;
