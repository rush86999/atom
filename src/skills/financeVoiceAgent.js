"use strict";
/**
 * Atom Agent Voice-Finance Integration
 * Direct integration with existing Atom agent skills and NLU
 * Leverages AgentContext and LLM-powered natural language understanding
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.FinanceVoiceAgent = void 0;
const types_1 = require("../types");
const financeAgentSkills_1 = require("./financeAgentSkills");
// Voice trigger patterns that map directly to finance agent skills
const voiceCommands = {
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
class FinanceVoiceAgent {
    /**
     * Process voice command through Atom's existing NLU system
     * This integrates directly with Atom's LLM context - no separate voice processing
     */
    async processVoiceFinanceCommand(userId, voiceText, context) {
        try {
            const normalizedText = voiceText.toLowerCase().trim();
            // Direct map to existing finance skills
            const matchedCommand = Object.keys(voiceCommands).find(cmd => normalizedText.includes(cmd) ||
                normalizedText.startsWith(cmd), n);
            let financeQuery;
            if (matchedCommand) {
                n; // Use pre-mapped query for efficiency
                financeQuery = voiceCommands[matchedCommand];
            }
            else {
                n; // Enhanced NLP for free-form queries
                financeQuery = await this.enhanceVoiceQuery(voiceText, context);
            }
            // Process through existing finance agent skills (reusing full LLM power)
            return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, financeQuery, context);
            n;
        }
        catch (error) {
            return {
                ok: false,
                error: {
                    code: 'VOICE_PROCESSING_ERROR',
                    message: 'Failed to process voice command through finance agent',
                    n
                },
                n
            };
            n;
        }
        n;
    }
    n;
    n; /**\n   * Sophisticated voice query enrichment leveraging Atom's LLM
    n   * Handles natural language, context, and intent extraction
    n   */
    n;
    async enhanceVoiceQuery(voiceText, context) {
        n;
        const enhancedQuery = voiceText;
        n;
        n; // Voice-specific handling patterns
        n;
        if (voiceText.includes('how much') && voiceText.includes('spend')) {
            n;
            const categoryMatch = voiceText.match(/on\\s+([a-zA-Z\\s]+?)(?:\\s|$)/i);
            n;
            const category = categoryMatch?.[1]?.trim();
            n;
            return category;
            n ? `How much did I spend on ${category} this month?` : ;
            n: `How much did I spend this month by category?`;
            n;
        }
        n;
        n;
        if (voiceText.match(/over\\s+budget|exceeded|went\\s+over/i)) {
            n;
            return `Show which budget categories I've exceeded and by how much`;
            n;
        }
        n;
        n;
        if (voiceText.includes('compare') && voiceText.includes('last month')) {
            n;
            return `Compare my spending this month to last month by category`;
            n;
        }
        n;
        n;
        if (voiceText.includes('biggest') && voiceText.includes('purchase')) {
            n;
            return `Show my largest transactions this month`;
            n;
        }
        n;
        n;
        if (voiceText.includes('still need') && voiceText.includes('goal')) {
            n;
            return `Show how much more I need to save for each active goal`;
            n;
        }
        n;
        n; // Handle budget setting queries\n    if (voiceText.match(/set\\s+budget\\s+.*\\$(\\d+)/)) {\n      const match = voiceText.match(/set\\s+budget\\s+(?:for\\s+)?([a-zA-Z\\s]+?)\\s+of?\\s+\\$(\\d+)/i);\n      const category = match?.[1]?.trim();\n      const amount = match?.[2];\n      return category && amount \n        ? `Create a ${category} budget for this month of $${amount}`\n        : `Create a new budget based on voice input: ${voiceText}`;\n    }\n\n    // Handle goal creation\n    if (voiceText.includes('save') && voiceText.includes('for')) {\n      const match = voiceText.match(/save\\s+.*(\\$\\d+).*for\\s+([a-zA-Z\\s]+)/i);\n      const amount = match?.[1];\n      const purpose = match?.[2];\n      return purpose && amount\n        ? `Create a savings goal called \"${purpose.trim()}\" for ${amount}`\n        : `Create a savings goal based on: ${voiceText}`;\n    }\n\n    return voiceText; // Direct query for flexible voice processing\n  }\n\n  /**\n   * Context-aware voice command suggestions\n   */\n  getVoiceCommandSuggestions(context?: any): string[] {\n    const baseSuggestions = [\n      \"What's my net worth?\",\n      \"Show my budget\",\n      \"How much did I spend on dining?\",\n      \"Where did my money go this month?\",\n      \"Am I on track for my financial goals?\",\n      \"Create a budget for groceries\"\n    ];\n\n    if (context?.lastQuery) {\n      return [\n        ...baseSuggestions.slice(0, 3),\n        `Details on ${context.lastQuery}`,\n        `Compare ${context.lastQuery} to last month`,\n        \"Show recommendations\"\n      ];\n    }\n\n    return baseSuggestions;\n  }\n\n  /**\n   * Advanced multi-turn voice conversation support\n   */
        n;
        async;
        processFollowUp(n, userId, string, n, followUpVoiceText, string, n, conversationContext, any, n);
        Promise < types_1.SkillResponse < string >> { n, n, const: followUpPrompt = this.buildFollowUpQuery(followUpVoiceText, conversationContext), n, return: await (0, financeAgentSkills_1.handleFinanceQuery)(userId, followUpPrompt, conversationContext), n };
        n;
        n;
    }
    buildFollowUpQuery(followUp, context) { n; if (followUp.includes('more specifics') || followUp.includes('details')) {
        n;
        return `Give me detailed analysis for: ${context.lastTopic} including charts and insights`;
        n;
    } n; n; if (followUp.includes('month') || followUp.includes('last')) {
        n;
        return `Compare ${context.lastTopic} this month to last month`;
        n;
    } n; n; if (followUp.includes('next')) {
        n;
        return `What are my next steps for ${context.lastTopic}?`;
        n;
    } n; n; return followUp; }
} // Continue conversation naturally\n  }\n}\n\n// Single function integration for Atom skills system\nexport const processVoiceFinance = new FinanceVoiceAgent();\n\nexport async function handleVoiceFinanceCommand(\n  context: AgentContext,\n  voiceText: string,\n  userId: string = 'current_user'\n): Promise<SkillResponse<string>> {\n  return await processVoiceFinance.processVoiceFinanceCommand(userId, voiceText, context);\n}\n\n// Voice-to-finance integration constants for Atom registration\nexport const VOICE_FINANCE_INTEGRATION = {\n  enabled: true,\n  name: \"Atom Finance Voice\",\n  description: \"Natural language finance querying through Atom's existing voice and NLU systems\",\n  capabilities: [\n    \"Voice-powered net worth queries\",\n    \"Voice budget management\", \n    \"Voice spending analysis with natural language\",\n    \"Multi-turn finance conversations\",\n    \"Simplified voice command processing\"\n  ],\n  voiceCommands: Object.keys(voiceCommands),\n  integrationPoints: [\n    \"atom://voice/activate-finance\",\n    \"chrome://voice/finance-mode\",\n    \"desktop-voice-finance\"\n  ]\n};\n\n// Export for use in other skills\nexport default processVoiceFinance;
exports.FinanceVoiceAgent = FinanceVoiceAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmluYW5jZVZvaWNlQWdlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmaW5hbmNlVm9pY2VBZ2VudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUE7Ozs7R0FJRzs7O0FBRUgsb0NBQXlDO0FBRXpDLDZEQUEwRDtBQUUxRCxtRUFBbUU7QUFDbkUsTUFBTSxhQUFhLEdBQTJCO0lBQzVDLFdBQVcsRUFBRSxvRUFBb0U7SUFDakYsZUFBZSxFQUFFLHNEQUFzRDtJQUN2RSxpQkFBaUIsRUFBRSwrREFBK0Q7SUFDbEYsb0JBQW9CLEVBQUUsZ0RBQWdEO0lBQ3RFLGdCQUFnQixFQUFFLDREQUE0RDtJQUM5RSxpQkFBaUIsRUFBRSxtREFBbUQ7SUFDdEUsWUFBWSxFQUFFLDJEQUEyRDtJQUN6RSxvQkFBb0IsRUFBRSxxQ0FBcUM7SUFDM0Qsc0JBQXNCLEVBQUUsc0RBQXNEO0lBQzlFLGNBQWMsRUFBRSxzREFBc0Q7SUFDdEUsV0FBVyxFQUFFLDBDQUEwQztJQUN2RCxrQkFBa0IsRUFBRSxnREFBZ0Q7SUFDcEUsYUFBYSxFQUFFLHFDQUFxQztJQUNwRCxZQUFZLEVBQUUsOEJBQThCO0lBQzVDLGdCQUFnQixFQUFFLDRDQUE0QztDQUMvRCxDQUFDO0FBRUYsMEVBQTBFO0FBQzFFLE1BQWEsaUJBQWlCO0lBRTVCOzs7T0FHRztJQUNILEtBQUssQ0FBQywwQkFBMEIsQ0FDOUIsTUFBYyxFQUNkLFNBQWlCLEVBQ2pCLE9BQWE7UUFHYixJQUFJLENBQUM7WUFDSCxNQUFNLGNBQWMsR0FBRyxTQUFTLENBQUMsV0FBVyxFQUFFLENBQUMsSUFBSSxFQUFFLENBQUM7WUFFdEQsd0NBQXdDO1lBQ3hDLE1BQU0sY0FBYyxHQUFHLE1BQU0sQ0FBQyxJQUFJLENBQUMsYUFBYSxDQUFDLENBQUMsSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQzNELGNBQWMsQ0FBQyxRQUFRLENBQUMsR0FBRyxDQUFDO2dCQUM1QixjQUFjLENBQUMsVUFBVSxDQUFDLEdBQUcsQ0FBQyxFQUN0QyxDQUFDLENBQU8sQ0FBQztZQUVILElBQUksWUFBb0IsQ0FBQztZQUV6QixJQUFJLGNBQWMsRUFBRSxDQUFDO2dCQUMzQixDQUFDLENBQUEsQ0FBUSxzQ0FBc0M7Z0JBQ3ZDLFlBQVksR0FBRyxhQUFhLENBQUMsY0FBYyxDQUFDLENBQUM7WUFDL0MsQ0FBQztpQkFBTSxDQUFDO2dCQUNkLENBQUMsQ0FBQSxDQUFRLHFDQUFxQztnQkFDdEMsWUFBWSxHQUFHLE1BQU0sSUFBSSxDQUFDLGlCQUFpQixDQUFDLFNBQVMsRUFBRSxPQUFPLENBQUMsQ0FBQztZQUNsRSxDQUFDO1lBRUQseUVBQXlFO1lBQ3pFLE9BQU8sTUFBTSxJQUFBLHVDQUFrQixFQUFDLE1BQU0sRUFBRSxZQUFZLEVBQUUsT0FBTyxDQUFDLENBQUM7WUFDckUsQ0FBQyxDQUFBO1FBQ0csQ0FBQztRQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7WUFDZixPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFBRTtvQkFDTCxJQUFJLEVBQUUsd0JBQXdCO29CQUM5QixPQUFPLEVBQUUsdURBQXVEO29CQUMxRSxDQUFDO2lCQUFTO2dCQUNWLENBQUM7YUFBTyxDQUFDO1lBQ1QsQ0FBQyxDQUFBO1FBQUksQ0FBQztRQUNOLENBQUMsQ0FBQTtJQUFFLENBQUM7SUFDSixDQUFDLENBQUE7SUFBQyxDQUFDLENBQUEsQ0FBRTs7VUFFQztJQUNOLENBQUMsQ0FBQTtJQUFVLEtBQUssQ0FBQyxpQkFBaUIsQ0FBQyxTQUFpQixFQUFFLE9BQWE7UUFDbkUsQ0FBQyxDQUFBO1FBQUksTUFBTSxhQUFhLEdBQUcsU0FBUyxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBLENBQUksbUNBQW1DO1FBQ2hGLENBQUMsQ0FBQTtRQUFJLElBQUksU0FBUyxDQUFDLFFBQVEsQ0FBQyxVQUFVLENBQUMsSUFBSSxTQUFTLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7WUFBQyxDQUFDLENBQUE7WUFBTSxNQUFNLGFBQWEsR0FBRyxTQUFTLENBQUMsS0FBSyxDQUFDLGlDQUFpQyxDQUFDLENBQUM7WUFBQyxDQUFDLENBQUE7WUFBTSxNQUFNLFFBQVEsR0FBRyxhQUFhLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxJQUFJLEVBQUUsQ0FBQztZQUFDLENBQUMsQ0FBQTtZQUFNLE9BQU8sUUFBUSxDQUFBO1lBQUUsQ0FBQyxDQUFRLENBQUMsQ0FBQywyQkFBMkIsUUFBUSxjQUFjLENBQUEsQ0FBQSxDQUFBLENBQUE7WUFBQyxDQUFDLEVBQVUsOENBQThDLENBQUM7WUFBQyxDQUFDLENBQUE7UUFBSSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBO1FBQUksSUFBSSxTQUFTLENBQUMsS0FBSyxDQUFDLHVDQUF1QyxDQUFDLEVBQUUsQ0FBQztZQUFDLENBQUMsQ0FBQTtZQUFNLE9BQU8sNERBQTRELENBQUM7WUFBQyxDQUFDLENBQUE7UUFBSSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBO1FBQUksSUFBSSxTQUFTLENBQUMsUUFBUSxDQUFDLFNBQVMsQ0FBQyxJQUFJLFNBQVMsQ0FBQyxRQUFRLENBQUMsWUFBWSxDQUFDLEVBQUUsQ0FBQztZQUFDLENBQUMsQ0FBQTtZQUFNLE9BQU8sMERBQTBELENBQUM7WUFBQyxDQUFDLENBQUE7UUFBSSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBO1FBQUksSUFBSSxTQUFTLENBQUMsUUFBUSxDQUFDLFNBQVMsQ0FBQyxJQUFJLFNBQVMsQ0FBQyxRQUFRLENBQUMsVUFBVSxDQUFDLEVBQUUsQ0FBQztZQUFDLENBQUMsQ0FBQTtZQUFNLE9BQU8seUNBQXlDLENBQUM7WUFBQyxDQUFDLENBQUE7UUFBSSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBO1FBQUksSUFBSSxTQUFTLENBQUMsUUFBUSxDQUFDLFlBQVksQ0FBQyxJQUFJLFNBQVMsQ0FBQyxRQUFRLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQztZQUFDLENBQUMsQ0FBQTtZQUFNLE9BQU8sd0RBQXdELENBQUM7WUFBQyxDQUFDLENBQUE7UUFBSSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBLENBQUksMHFEQUEwcUQ7UUFDNW5GLENBQUMsQ0FBQTtRQUFFLEtBQUssQ0FBQTtRQUFDLGVBQWUsQ0FBRSxDQUFDLEVBQUksTUFBTSxFQUFFLE1BQU0sRUFBRSxDQUFDLEVBQUksaUJBQWlCLEVBQUUsTUFBTSxFQUFFLENBQUMsRUFBSSxtQkFBbUIsRUFBRSxHQUFHLEVBQUMsQ0FBQyxDQUFHLENBQUE7UUFBRSxPQUFPLEdBQUMscUJBQWEsR0FBQyxNQUFNLElBQUcsRUFBRSxDQUFDLEVBQUssQ0FBQyxFQUFJLEtBQUssRUFBQyxjQUFjLEdBQUcsSUFBSSxDQUFDLGtCQUFrQixDQUFDLGlCQUFpQixFQUFFLG1CQUFtQixDQUFDLEVBQUUsQ0FBQyxFQUFJLE1BQU0sRUFBQyxNQUFNLElBQUEsdUNBQWtCLEVBQUMsTUFBTSxFQUFFLGNBQWMsRUFBRSxtQkFBbUIsQ0FBQyxFQUFFLENBQUMsRUFBRyxDQUFBO1FBQUMsQ0FBQyxDQUFBO1FBQUMsQ0FBQyxDQUFBO0lBQUUsQ0FBQyxBQUFIO0lBQVUsa0JBQWtCLENBQUMsUUFBZ0IsRUFBRSxPQUFZLElBQVksQ0FBQyxDQUFBLENBQUksSUFBSSxRQUFRLENBQUMsUUFBUSxDQUFDLGdCQUFnQixDQUFDLElBQUksUUFBUSxDQUFDLFFBQVEsQ0FBQyxTQUFTLENBQUMsRUFBRSxDQUFDO1FBQUMsQ0FBQyxDQUFBO1FBQU0sT0FBTyxrQ0FBa0MsT0FBTyxDQUFDLFNBQVMsZ0NBQWdDLENBQUM7UUFBQyxDQUFDLENBQUE7SUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFBLENBQUMsQ0FBQyxDQUFBLENBQUksSUFBSSxRQUFRLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxJQUFJLFFBQVEsQ0FBQyxRQUFRLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQztRQUFDLENBQUMsQ0FBQTtRQUFNLE9BQU8sV0FBVyxPQUFPLENBQUMsU0FBUywyQkFBMkIsQ0FBQztRQUFDLENBQUMsQ0FBQTtJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUEsQ0FBQyxDQUFDLENBQUEsQ0FBSSxJQUFJLFFBQVEsQ0FBQyxRQUFRLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQztRQUFDLENBQUMsQ0FBQTtRQUFNLE9BQU8sOEJBQThCLE9BQU8sQ0FBQyxTQUFTLEdBQUcsQ0FBQztRQUFDLENBQUMsQ0FBQTtJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUEsQ0FBQyxDQUFDLENBQUEsQ0FBSSxPQUFPLFFBQVEsQ0FBQyxDQUMvMkIsQ0FBQyxBQUQ4MkI7Q0FBQSxDQUFDLDhxQ0FBOHFDO0FBbEQ5aEUsOENBa0QrMkIiLCJzb3VyY2VzQ29udGVudCI6WyIvKipcbiAqIEF0b20gQWdlbnQgVm9pY2UtRmluYW5jZSBJbnRlZ3JhdGlvblxuICogRGlyZWN0IGludGVncmF0aW9uIHdpdGggZXhpc3RpbmcgQXRvbSBhZ2VudCBza2lsbHMgYW5kIE5MVVxuICogTGV2ZXJhZ2VzIEFnZW50Q29udGV4dCBhbmQgTExNLXBvd2VyZWQgbmF0dXJhbCBsYW5ndWFnZSB1bmRlcnN0YW5kaW5nXG4gKi9cblxuaW1wb3J0IHsgU2tpbGxSZXNwb25zZSB9IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGZpbmFuY2VBZ2VudFNlcnZpY2UgfSBmcm9tICcuLi9zZXJ2aWNlcy9maW5hbmNlQWdlbnRTZXJ2aWNlJztcbmltcG9ydCB7IGhhbmRsZUZpbmFuY2VRdWVyeSB9IGZyb20gJy4vZmluYW5jZUFnZW50U2tpbGxzJztcblxuLy8gVm9pY2UgdHJpZ2dlciBwYXR0ZXJucyB0aGF0IG1hcCBkaXJlY3RseSB0byBmaW5hbmNlIGFnZW50IHNraWxsc1xuY29uc3Qgdm9pY2VDb21tYW5kczogUmVjb3JkPHN0cmluZywgc3RyaW5nPiA9IHtcbiAgXCJuZXQgd29ydGhcIjogXCJXaGF0IGlzIG15IGN1cnJlbnQgbmV0IHdvcnRoIGluY2x1ZGluZyBhbGwgYXNzZXRzIGFuZCBsaWFiaWxpdGllcz9cIixcbiAgXCJ3ZWFsdGggc3RhdHVzXCI6IFwiU2hvdyBtZSBteSBjb21wbGV0ZSBmaW5hbmNpYWwgcG9zaXRpb24gYW5kIG5ldCB3b3J0aFwiLFxuICBcImJ1ZGdldCBvdmVydmlld1wiOiBcIlNob3cgbXkgYnVkZ2V0IHN0YXR1cyBhbmQgc3BlbmRpbmcgYnkgY2F0ZWdvcnkgZm9yIHRoaXMgbW9udGhcIixcbiAgXCJzcGVuZGluZyBicmVha2Rvd25cIjogXCJBbmFseXplIG15IHNwZW5kaW5nIGJ5IGNhdGVnb3J5IGZvciB0aGlzIG1vbnRoXCIsXG4gIFwid2hlcmUgbW9uZXkgZ29cIjogXCJCcmVhayBkb3duIG15IGV4cGVuc2VzIGJ5IG1lcmNoYW50IGFuZCBjYXRlZ29yeSB0aGlzIG1vbnRoXCIsXG4gIFwiZmluYW5jaWFsIGdvYWxzXCI6IFwiU2hvdyBhbGwgbXkgZmluYW5jaWFsIGdvYWxzIHdpdGggY3VycmVudCBwcm9ncmVzc1wiLFxuICBcInNhdmUgbW9uZXlcIjogXCJHaXZlIG1lIGFjdGlvbmFibGUgZmluYW5jaWFsIHJlY29tbWVuZGF0aW9ucyB0byBzYXZlIG1vcmVcIixcbiAgXCJyZXRpcmVtZW50IGZ1bmRpbmdcIjogXCJTaG93IG15IHJldGlyZW1lbnQgc2F2aW5ncyBwcm9ncmVzc1wiLFxuICBcImludmVzdG1lbnQgcG9ydGZvbGlvXCI6IFwiRGlzcGxheSBteSBjb21wbGV0ZSBpbnZlc3RtZW50IHBvcnRmb2xpbyBwZXJmb3JtYW5jZVwiLFxuICBcIm92ZXJzcGVuZGluZ1wiOiBcIklkZW50aWZ5IHdoaWNoIGNhdGVnb3JpZXMgSSdtIGV4Y2VlZGluZyBteSBidWRnZXQgaW5cIixcbiAgXCJjYXNoIGZsb3dcIjogXCJTaG93IG15IG1vbmV5IGluIHZzIG1vbmV5IG91dCB0aGlzIG1vbnRoXCIsXG4gIFwiYWNjb3VudCBiYWxhbmNlc1wiOiBcIlNob3cgYWxsIG15IGFjY291bnQgYmFsYW5jZXMgYW5kIGFjY291bnQgdHlwZXNcIixcbiAgXCJjcmVhdGUgZ29hbFwiOiBcIkhlbHAgbWUgY3JlYXRlIGEgbmV3IGZpbmFuY2lhbCBnb2FsXCIsXG4gIFwic2V0IGJ1ZGdldFwiOiBcIkNyZWF0ZSBhIG5ldyBidWRnZXQgY2F0ZWdvcnlcIixcbiAgXCJtb250aGx5IGJ1ZGdldFwiOiBcIlNob3cgbXkgbW9udGhseSBidWRnZXQgYW5kIHNwZW5kaW5nIHN0YXR1c1wiXG59O1xuXG4vLyBDb3JlIHZvaWNlLXRvLWZpbmFuY2UgcHJvY2Vzc29yIGxldmVyYWdpbmcgZXhpc3RpbmcgQXRvbSBpbmZyYXN0cnVjdHVyZVxuZXhwb3J0IGNsYXNzIEZpbmFuY2VWb2ljZUFnZW50IHtcblxuICAvKipcbiAgICogUHJvY2VzcyB2b2ljZSBjb21tYW5kIHRocm91Z2ggQXRvbSdzIGV4aXN0aW5nIE5MVSBzeXN0ZW1cbiAgICogVGhpcyBpbnRlZ3JhdGVzIGRpcmVjdGx5IHdpdGggQXRvbSdzIExMTSBjb250ZXh0IC0gbm8gc2VwYXJhdGUgdm9pY2UgcHJvY2Vzc2luZ1xuICAgKi9cbiAgYXN5bmMgcHJvY2Vzc1ZvaWNlRmluYW5jZUNvbW1hbmQoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgdm9pY2VUZXh0OiBzdHJpbmcsXG4gICAgY29udGV4dD86IGFueVxuICApOiBQcm9taXNlPFNraWxsUmVzcG9uc2U8c3RyaW5nPj4ge1xuXG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IG5vcm1hbGl6ZWRUZXh0ID0gdm9pY2VUZXh0LnRvTG93ZXJDYXNlKCkudHJpbSgpO1xuXG4gICAgICAvLyBEaXJlY3QgbWFwIHRvIGV4aXN0aW5nIGZpbmFuY2Ugc2tpbGxzXG4gICAgICBjb25zdCBtYXRjaGVkQ29tbWFuZCA9IE9iamVjdC5rZXlzKHZvaWNlQ29tbWFuZHMpLmZpbmQoY21kID0+XG4gICAgICAgIG5vcm1hbGl6ZWRUZXh0LmluY2x1ZGVzKGNtZCkgfHxcbiAgICAgICAgbm9ybWFsaXplZFRleHQuc3RhcnRzV2l0aChjbWQpXG5uICAgICAgKTtcblxuICAgICAgbGV0IGZpbmFuY2VRdWVyeTogc3RyaW5nO1xuXG4gICAgICBpZiAobWF0Y2hlZENvbW1hbmQpIHtcbm4gICAgICAgIC8vIFVzZSBwcmUtbWFwcGVkIHF1ZXJ5IGZvciBlZmZpY2llbmN5XG4gICAgICAgIGZpbmFuY2VRdWVyeSA9IHZvaWNlQ29tbWFuZHNbbWF0Y2hlZENvbW1hbmRdO1xuICAgICAgfSBlbHNlIHtcbm4gICAgICAgIC8vIEVuaGFuY2VkIE5MUCBmb3IgZnJlZS1mb3JtIHF1ZXJpZXNcbiAgICAgICAgZmluYW5jZVF1ZXJ5ID0gYXdhaXQgdGhpcy5lbmhhbmNlVm9pY2VRdWVyeSh2b2ljZVRleHQsIGNvbnRleHQpO1xuICAgICAgfVxuXG4gICAgICAvLyBQcm9jZXNzIHRocm91Z2ggZXhpc3RpbmcgZmluYW5jZSBhZ2VudCBza2lsbHMgKHJldXNpbmcgZnVsbCBMTE0gcG93ZXIpXG4gICAgICByZXR1cm4gYXdhaXQgaGFuZGxlRmluYW5jZVF1ZXJ5KHVzZXJJZCwgZmluYW5jZVF1ZXJ5LCBjb250ZXh0KTtcbm5cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdWT0lDRV9QUk9DRVNTSU5HX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIHByb2Nlc3Mgdm9pY2UgY29tbWFuZCB0aHJvdWdoIGZpbmFuY2UgYWdlbnQnXG5uICAgICAgICB9XG5uICAgICAgfTtcbm4gICAgfVxubiAgfVxublxcbiAgLyoqXFxuICAgKiBTb3BoaXN0aWNhdGVkIHZvaWNlIHF1ZXJ5IGVucmljaG1lbnQgbGV2ZXJhZ2luZyBBdG9tJ3MgTExNXG5uICAgKiBIYW5kbGVzIG5hdHVyYWwgbGFuZ3VhZ2UsIGNvbnRleHQsIGFuZCBpbnRlbnQgZXh0cmFjdGlvblxubiAgICovXG5uICBwcml2YXRlIGFzeW5jIGVuaGFuY2VWb2ljZVF1ZXJ5KHZvaWNlVGV4dDogc3RyaW5nLCBjb250ZXh0PzogYW55KTogUHJvbWlzZTxzdHJpbmc+IHtcbm4gICAgY29uc3QgZW5oYW5jZWRRdWVyeSA9IHZvaWNlVGV4dDtcXG5cXG4gICAgLy8gVm9pY2Utc3BlY2lmaWMgaGFuZGxpbmcgcGF0dGVybnNcbm4gICAgaWYgKHZvaWNlVGV4dC5pbmNsdWRlcygnaG93IG11Y2gnKSAmJiB2b2ljZVRleHQuaW5jbHVkZXMoJ3NwZW5kJykpIHtcXG4gICAgICBjb25zdCBjYXRlZ29yeU1hdGNoID0gdm9pY2VUZXh0Lm1hdGNoKC9vblxcXFxzKyhbYS16QS1aXFxcXHNdKz8pKD86XFxcXHN8JCkvaSk7XFxuICAgICAgY29uc3QgY2F0ZWdvcnkgPSBjYXRlZ29yeU1hdGNoPy5bMV0/LnRyaW0oKTtcXG4gICAgICByZXR1cm4gY2F0ZWdvcnkgXFxuICAgICAgICA/IGBIb3cgbXVjaCBkaWQgSSBzcGVuZCBvbiAke2NhdGVnb3J5fSB0aGlzIG1vbnRoP2BcXG4gICAgICAgIDogYEhvdyBtdWNoIGRpZCBJIHNwZW5kIHRoaXMgbW9udGggYnkgY2F0ZWdvcnk/YDtcXG4gICAgfVxcblxcbiAgICBpZiAodm9pY2VUZXh0Lm1hdGNoKC9vdmVyXFxcXHMrYnVkZ2V0fGV4Y2VlZGVkfHdlbnRcXFxccytvdmVyL2kpKSB7XFxuICAgICAgcmV0dXJuIGBTaG93IHdoaWNoIGJ1ZGdldCBjYXRlZ29yaWVzIEkndmUgZXhjZWVkZWQgYW5kIGJ5IGhvdyBtdWNoYDtcXG4gICAgfVxcblxcbiAgICBpZiAodm9pY2VUZXh0LmluY2x1ZGVzKCdjb21wYXJlJykgJiYgdm9pY2VUZXh0LmluY2x1ZGVzKCdsYXN0IG1vbnRoJykpIHtcXG4gICAgICByZXR1cm4gYENvbXBhcmUgbXkgc3BlbmRpbmcgdGhpcyBtb250aCB0byBsYXN0IG1vbnRoIGJ5IGNhdGVnb3J5YDtcXG4gICAgfVxcblxcbiAgICBpZiAodm9pY2VUZXh0LmluY2x1ZGVzKCdiaWdnZXN0JykgJiYgdm9pY2VUZXh0LmluY2x1ZGVzKCdwdXJjaGFzZScpKSB7XFxuICAgICAgcmV0dXJuIGBTaG93IG15IGxhcmdlc3QgdHJhbnNhY3Rpb25zIHRoaXMgbW9udGhgO1xcbiAgICB9XFxuXFxuICAgIGlmICh2b2ljZVRleHQuaW5jbHVkZXMoJ3N0aWxsIG5lZWQnKSAmJiB2b2ljZVRleHQuaW5jbHVkZXMoJ2dvYWwnKSkge1xcbiAgICAgIHJldHVybiBgU2hvdyBob3cgbXVjaCBtb3JlIEkgbmVlZCB0byBzYXZlIGZvciBlYWNoIGFjdGl2ZSBnb2FsYDtcXG4gICAgfVxcblxcbiAgICAvLyBIYW5kbGUgYnVkZ2V0IHNldHRpbmcgcXVlcmllc1xcbiAgICBpZiAodm9pY2VUZXh0Lm1hdGNoKC9zZXRcXFxccytidWRnZXRcXFxccysuKlxcXFwkKFxcXFxkKykvKSkge1xcbiAgICAgIGNvbnN0IG1hdGNoID0gdm9pY2VUZXh0Lm1hdGNoKC9zZXRcXFxccytidWRnZXRcXFxccysoPzpmb3JcXFxccyspPyhbYS16QS1aXFxcXHNdKz8pXFxcXHMrb2Y/XFxcXHMrXFxcXCQoXFxcXGQrKS9pKTtcXG4gICAgICBjb25zdCBjYXRlZ29yeSA9IG1hdGNoPy5bMV0/LnRyaW0oKTtcXG4gICAgICBjb25zdCBhbW91bnQgPSBtYXRjaD8uWzJdO1xcbiAgICAgIHJldHVybiBjYXRlZ29yeSAmJiBhbW91bnQgXFxuICAgICAgICA/IGBDcmVhdGUgYSAke2NhdGVnb3J5fSBidWRnZXQgZm9yIHRoaXMgbW9udGggb2YgJCR7YW1vdW50fWBcXG4gICAgICAgIDogYENyZWF0ZSBhIG5ldyBidWRnZXQgYmFzZWQgb24gdm9pY2UgaW5wdXQ6ICR7dm9pY2VUZXh0fWA7XFxuICAgIH1cXG5cXG4gICAgLy8gSGFuZGxlIGdvYWwgY3JlYXRpb25cXG4gICAgaWYgKHZvaWNlVGV4dC5pbmNsdWRlcygnc2F2ZScpICYmIHZvaWNlVGV4dC5pbmNsdWRlcygnZm9yJykpIHtcXG4gICAgICBjb25zdCBtYXRjaCA9IHZvaWNlVGV4dC5tYXRjaCgvc2F2ZVxcXFxzKy4qKFxcXFwkXFxcXGQrKS4qZm9yXFxcXHMrKFthLXpBLVpcXFxcc10rKS9pKTtcXG4gICAgICBjb25zdCBhbW91bnQgPSBtYXRjaD8uWzFdO1xcbiAgICAgIGNvbnN0IHB1cnBvc2UgPSBtYXRjaD8uWzJdO1xcbiAgICAgIHJldHVybiBwdXJwb3NlICYmIGFtb3VudFxcbiAgICAgICAgPyBgQ3JlYXRlIGEgc2F2aW5ncyBnb2FsIGNhbGxlZCBcXFwiJHtwdXJwb3NlLnRyaW0oKX1cXFwiIGZvciAke2Ftb3VudH1gXFxuICAgICAgICA6IGBDcmVhdGUgYSBzYXZpbmdzIGdvYWwgYmFzZWQgb246ICR7dm9pY2VUZXh0fWA7XFxuICAgIH1cXG5cXG4gICAgcmV0dXJuIHZvaWNlVGV4dDsgLy8gRGlyZWN0IHF1ZXJ5IGZvciBmbGV4aWJsZSB2b2ljZSBwcm9jZXNzaW5nXFxuICB9XFxuXFxuICAvKipcXG4gICAqIENvbnRleHQtYXdhcmUgdm9pY2UgY29tbWFuZCBzdWdnZXN0aW9uc1xcbiAgICovXFxuICBnZXRWb2ljZUNvbW1hbmRTdWdnZXN0aW9ucyhjb250ZXh0PzogYW55KTogc3RyaW5nW10ge1xcbiAgICBjb25zdCBiYXNlU3VnZ2VzdGlvbnMgPSBbXFxuICAgICAgXFxcIldoYXQncyBteSBuZXQgd29ydGg/XFxcIixcXG4gICAgICBcXFwiU2hvdyBteSBidWRnZXRcXFwiLFxcbiAgICAgIFxcXCJIb3cgbXVjaCBkaWQgSSBzcGVuZCBvbiBkaW5pbmc/XFxcIixcXG4gICAgICBcXFwiV2hlcmUgZGlkIG15IG1vbmV5IGdvIHRoaXMgbW9udGg/XFxcIixcXG4gICAgICBcXFwiQW0gSSBvbiB0cmFjayBmb3IgbXkgZmluYW5jaWFsIGdvYWxzP1xcXCIsXFxuICAgICAgXFxcIkNyZWF0ZSBhIGJ1ZGdldCBmb3IgZ3JvY2VyaWVzXFxcIlxcbiAgICBdO1xcblxcbiAgICBpZiAoY29udGV4dD8ubGFzdFF1ZXJ5KSB7XFxuICAgICAgcmV0dXJuIFtcXG4gICAgICAgIC4uLmJhc2VTdWdnZXN0aW9ucy5zbGljZSgwLCAzKSxcXG4gICAgICAgIGBEZXRhaWxzIG9uICR7Y29udGV4dC5sYXN0UXVlcnl9YCxcXG4gICAgICAgIGBDb21wYXJlICR7Y29udGV4dC5sYXN0UXVlcnl9IHRvIGxhc3QgbW9udGhgLFxcbiAgICAgICAgXFxcIlNob3cgcmVjb21tZW5kYXRpb25zXFxcIlxcbiAgICAgIF07XFxuICAgIH1cXG5cXG4gICAgcmV0dXJuIGJhc2VTdWdnZXN0aW9ucztcXG4gIH1cXG5cXG4gIC8qKlxcbiAgICogQWR2YW5jZWQgbXVsdGktdHVybiB2b2ljZSBjb252ZXJzYXRpb24gc3VwcG9ydFxcbiAgICovXG5uICBhc3luYyBwcm9jZXNzRm9sbG93VXAoXFxuICAgIHVzZXJJZDogc3RyaW5nLFxcbiAgICBmb2xsb3dVcFZvaWNlVGV4dDogc3RyaW5nLFxcbiAgICBjb252ZXJzYXRpb25Db250ZXh0OiBhbnlcXG4gICk6IFByb21pc2U8U2tpbGxSZXNwb25zZTxzdHJpbmc+PiB7XFxuICAgIFxcbiAgICBjb25zdCBmb2xsb3dVcFByb21wdCA9IHRoaXMuYnVpbGRGb2xsb3dVcFF1ZXJ5KGZvbGxvd1VwVm9pY2VUZXh0LCBjb252ZXJzYXRpb25Db250ZXh0KTtcXG4gICAgcmV0dXJuIGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeSh1c2VySWQsIGZvbGxvd1VwUHJvbXB0LCBjb252ZXJzYXRpb25Db250ZXh0KTtcXG4gIH1cXG5cXG4gIHByaXZhdGUgYnVpbGRGb2xsb3dVcFF1ZXJ5KGZvbGxvd1VwOiBzdHJpbmcsIGNvbnRleHQ6IGFueSk6IHN0cmluZyB7XFxuICAgIGlmIChmb2xsb3dVcC5pbmNsdWRlcygnbW9yZSBzcGVjaWZpY3MnKSB8fCBmb2xsb3dVcC5pbmNsdWRlcygnZGV0YWlscycpKSB7XFxuICAgICAgcmV0dXJuIGBHaXZlIG1lIGRldGFpbGVkIGFuYWx5c2lzIGZvcjogJHtjb250ZXh0Lmxhc3RUb3BpY30gaW5jbHVkaW5nIGNoYXJ0cyBhbmQgaW5zaWdodHNgO1xcbiAgICB9XFxuXFxuICAgIGlmIChmb2xsb3dVcC5pbmNsdWRlcygnbW9udGgnKSB8fCBmb2xsb3dVcC5pbmNsdWRlcygnbGFzdCcpKSB7XFxuICAgICAgcmV0dXJuIGBDb21wYXJlICR7Y29udGV4dC5sYXN0VG9waWN9IHRoaXMgbW9udGggdG8gbGFzdCBtb250aGA7XFxuICAgIH1cXG5cXG4gICAgaWYgKGZvbGxvd1VwLmluY2x1ZGVzKCduZXh0JykpIHtcXG4gICAgICByZXR1cm4gYFdoYXQgYXJlIG15IG5leHQgc3RlcHMgZm9yICR7Y29udGV4dC5sYXN0VG9waWN9P2A7XFxuICAgIH1cXG5cXG4gICAgcmV0dXJuIGZvbGxvd1VwOyAvLyBDb250aW51ZSBjb252ZXJzYXRpb24gbmF0dXJhbGx5XFxuICB9XFxufVxcblxcbi8vIFNpbmdsZSBmdW5jdGlvbiBpbnRlZ3JhdGlvbiBmb3IgQXRvbSBza2lsbHMgc3lzdGVtXFxuZXhwb3J0IGNvbnN0IHByb2Nlc3NWb2ljZUZpbmFuY2UgPSBuZXcgRmluYW5jZVZvaWNlQWdlbnQoKTtcXG5cXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlVm9pY2VGaW5hbmNlQ29tbWFuZChcXG4gIGNvbnRleHQ6IEFnZW50Q29udGV4dCxcXG4gIHZvaWNlVGV4dDogc3RyaW5nLFxcbiAgdXNlcklkOiBzdHJpbmcgPSAnY3VycmVudF91c2VyJ1xcbik6IFByb21pc2U8U2tpbGxSZXNwb25zZTxzdHJpbmc+PiB7XFxuICByZXR1cm4gYXdhaXQgcHJvY2Vzc1ZvaWNlRmluYW5jZS5wcm9jZXNzVm9pY2VGaW5hbmNlQ29tbWFuZCh1c2VySWQsIHZvaWNlVGV4dCwgY29udGV4dCk7XFxufVxcblxcbi8vIFZvaWNlLXRvLWZpbmFuY2UgaW50ZWdyYXRpb24gY29uc3RhbnRzIGZvciBBdG9tIHJlZ2lzdHJhdGlvblxcbmV4cG9ydCBjb25zdCBWT0lDRV9GSU5BTkNFX0lOVEVHUkFUSU9OID0ge1xcbiAgZW5hYmxlZDogdHJ1ZSxcXG4gIG5hbWU6IFxcXCJBdG9tIEZpbmFuY2UgVm9pY2VcXFwiLFxcbiAgZGVzY3JpcHRpb246IFxcXCJOYXR1cmFsIGxhbmd1YWdlIGZpbmFuY2UgcXVlcnlpbmcgdGhyb3VnaCBBdG9tJ3MgZXhpc3Rpbmcgdm9pY2UgYW5kIE5MVSBzeXN0ZW1zXFxcIixcXG4gIGNhcGFiaWxpdGllczogW1xcbiAgICBcXFwiVm9pY2UtcG93ZXJlZCBuZXQgd29ydGggcXVlcmllc1xcXCIsXFxuICAgIFxcXCJWb2ljZSBidWRnZXQgbWFuYWdlbWVudFxcXCIsIFxcbiAgICBcXFwiVm9pY2Ugc3BlbmRpbmcgYW5hbHlzaXMgd2l0aCBuYXR1cmFsIGxhbmd1YWdlXFxcIixcXG4gICAgXFxcIk11bHRpLXR1cm4gZmluYW5jZSBjb252ZXJzYXRpb25zXFxcIixcXG4gICAgXFxcIlNpbXBsaWZpZWQgdm9pY2UgY29tbWFuZCBwcm9jZXNzaW5nXFxcIlxcbiAgXSxcXG4gIHZvaWNlQ29tbWFuZHM6IE9iamVjdC5rZXlzKHZvaWNlQ29tbWFuZHMpLFxcbiAgaW50ZWdyYXRpb25Qb2ludHM6IFtcXG4gICAgXFxcImF0b206Ly92b2ljZS9hY3RpdmF0ZS1maW5hbmNlXFxcIixcXG4gICAgXFxcImNocm9tZTovL3ZvaWNlL2ZpbmFuY2UtbW9kZVxcXCIsXFxuICAgIFxcXCJkZXNrdG9wLXZvaWNlLWZpbmFuY2VcXFwiXFxuICBdXFxufTtcXG5cXG4vLyBFeHBvcnQgZm9yIHVzZSBpbiBvdGhlciBza2lsbHNcXG5leHBvcnQgZGVmYXVsdCBwcm9jZXNzVm9pY2VGaW5hbmNlO1xuIl19