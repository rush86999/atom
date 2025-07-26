/**
 * Atom Agent Finance NLU Integration
 * Enables "Atom" wake word + natural language finance queries through existing NLU system
 * Integrates fully with wake word activation flow ➜ NLU processor ➜ finance agent
 */

import { AgentContext, NLUHandler, skillExecutor } from '../services/agentNluSystem';
import { handleFinanceQuery } from './financeAgentSkills';
import { processVoiceFinance } from './financeVoiceAgent';

/**
 * Finance NLU Handler that plugs into Atom's existing wake-word activated system
 * Wake word "Atom" triggers agent ➜ this NLU handler processes finance commands naturally
 */
export const financeNluHandler: NLUHandler = {
  name: 'finance-handler',

  // Finance-specific intent recognition leveraging existing NLU
  intents: [
    {
      name: 'net_worth_query',
      patterns: [
        /what.*net.*worth/i,
        /how.*much.*(am|do).*worth/i,
        /financial.*position/i,
        /wealth.*summary/i
      ]
    },
    {
      name: 'budget_query',
      patterns: [
        /budget.*status/i,
        /spending.*limit/i,
        /how.*much.*left.*for.*budget/i
      ]
    },
    {
      name: 'spending_analysis',
      patterns: [
        /how.*much.*spent/i,
        /where.*money.*go/i,
        /spending.*breakdown/i,
        /expenses.*this.*month/i
      ]
    },
    {
      name: 'create_budget',
      patterns: [
        /set.*budget/i,
        /create.*budget/i,
        /budget.*for.*\$(\d+)/i
      ]
    },
    {
      name: 'financial_goals',
      patterns: [
        /show.*goals/i,
        /savings.*progress/i,
        /financial.*goals/i,
        /retirement.*tracking/i
      ]
    },
    {
      name: 'investment_overview',
      patterns: [
        /investment.*portfolio/i,
        /portfolio.*performance/i,
        /stock.*investments/i
      ]
    },
    {
      name: 'transaction_search',
      patterns: [
        /find.*transactions/i,
        /search.*purchases/i,
        /show.*spending/i
      ]
    }
  ],

  /**
   * Processes any text entering Atom's NLU system after "Atom" wake word
   * Example flow: "Atom → show my net worth" ➜ NLU captures ➜ finance processing
   */
  async handleText(context: AgentContext, text: string): Promise<any> {
    const userId = context.user?.id || 'user';

    // Clean "Atom" wake word prefix if present
    const cleanText = text.replace(/^atom\s*/i, '').trim();

    if (!cleanText) return null;

    // Route through existing finance system
    return await handleFinanceQuery(userId, cleanText, {
      ...context,
      source: 'voice_wake',
      interface: 'voice_nlu'
    });
  },

  /**
   * Voice-aware natural language processing leveraging existing Atom NLU
   */
  voiceProcessing: {
    handleWakeActivation: async (context: AgentContext) => {
      return {
        greeting: "💰 Finance mode activated! Say things like:",
        examples: [
          "What is my net worth?",
          "Show my budget",
          "How much did I spend on restaurants?",
          "Create a savings goal",
          "Investment portfolio"
        ]
      };
    },

    processVoiceInput: async (voiceText: string, context: AgentContext) => {
      const userId = context.user?.id || 'user';

      // Direct voice processing through NLU layer
      return await processVoiceFinance.processVoiceFinanceCommand(
        userId,
        voiceText,
        {
          ...context,
          interface: 'voice_wake_nlu',
          timestamp: Date.now()
        }
      );
    }
  }
};

// Integration hook for existing Atom NLU system
export const activateFinanceThroughWakeWord = async () => {
  await skillExecutor.registerNluHandler('finance', financeNluHandler);
  console.log('🔊 Atom finance NLU integrated with wake word system');
  console.log('✅ Say "Atom" then any finance command naturally');

  return {
    awake: false,
    listenFor: [
      'what is my net worth',
      'show my budget',
      'how much did I spend on',
      'create a budget for',
      'show my financial goals',
      'investment portfolio',
      'compare this month to last'
    ],
    responseMode: 'conversational'
  };
};

// Direct finance command processing regardless of entry point
export const processFinanceThroughNlu = async (
  context: AgentContext,
  text: string
): Promise<any> => {
  return await financeNluHandler.handleText(context, text);
};

// Auto-registration on module import
if (typeof window === 'undefined') {
  // Server-side: register immediately
  activateFinanceThroughWakeWord().catch(console.error);
} else {
  // Client-side: register when DOM ready
  try {
    activateFinanceThroughWakeWord();
  } catch (error) {
    console.log('Finance NLU system ready for Atom wake word');
  }
}

// Activation flow documentation
export const FinanceWakeFlow = {
  title: "Atom Finance Activation Flow",
  description: "How wake word + finance works through NLU",
  flow: [
    "User: 'Atom show my net worth'",
    "Wake Word Detector: Activates Atom agent",
    "NLU System: Detects finance intent → routes to finance handler",
    "Finance Agent: Processes query → returns formatted response",
    "Atom: Speaks back via voice/TTS"
  ],
  voiceCommands: [
    "Atom what is my net worth",
    "Atom show my budget for this month",
    "Atom how much did I spend on dining",
    "Atom create a travel goal of $2000",
    "Atom investment portfolio performance",
    "Atom help with budgets",
    "Atom compare this month to last"
  ],
  integration: "Uses existing wake word system, no new wake words needed"
};

// Export for wake word system integration
export default {
  handler: financeNluHandler,
  activate: activateFinanceThroughWakeWord,
  processFinanceThroughNlu
};
