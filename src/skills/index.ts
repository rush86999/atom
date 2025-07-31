/**
 * Skills Index - Finance Capabilities Registration
 * Registers finance skills as Atom agent capabilities ready for wake word activation
 */

import { registerSkill, SkillDefinition } from '../services/agentSkillRegistry';
import { allFinanceSkills, financeAgentTools, FinanceSkillRegistration } from './financeSkillIndex';
import { processVoiceFinance } from './financeVoiceAgent';
import { researchSkills } from './researchSkillIndex';
import { legalSkills } from './legalSkillIndex';
import { allTaxSkills, taxAgentTools, TaxSkillRegistration } from './taxSkillIndex';

// Finance skill activation triggers
const financeSkillConfig = {
  wakeWordTriggers: [
    'finance',
    'money',
    'budget',
    'spending',
    'net worth',
    'investment',
    'goals',
    'savings',
    'account'
  ],

  activationPatterns: [
    '^what.*net.*worth',
    '^show.*budget',
    '^how.*much.*spend',
    '^create.*budget',
    '^set.*goal',
    '^where.*money.*go',
    '^investment.*portfolio',
    '^finance.*help'
  ],

  naturalLanguagePatterns: [
    'what is my net worth',
    'show my budget for this month',
    'how much did I spend on dining',
    'create a grocery budget',
    'am I on track for retirement',
    'investment performance this quarter',
    'show my financial goals',
    'budget breakdown',
    'overspending detection'
  ]
};

// Register all finance skills with Atom agent
export async function registerFinanceSkills() {
  console.log('🔥 Registering Atom Finance Skills for Wake Word Activation');

  try {
    // Register each finance skill
    for (const skill of allFinanceSkills) {
      await registerSkill(skill);
    }

    // Register finance-specific tools for LLM function calling
    for (const tool of financeAgentTools) {
      await registerSkill({
        name: tool.name,
        description: tool.description || 'Finance tool',
        parameters: {}, // Tool-specific parameters assigned during registry
        handler: tool.handler
      } as SkillDefinition);
    }

    console.log('✅ Finance skills registered successfully');

    return {
      success: true,
      registeredSkills: allFinanceSkills.length + financeAgentTools.length,
      wakeWordTriggers: financeSkillConfig.wakeWordTriggers,
      naturalLanguageSupport: true
    };

  } catch (error) {
    console.error('❌ Failed to register finance skills:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Voice Command Handler Integration
export class FinanceVoiceHandler {
  private isActive = false;

  async handleWakeWordActivation(context: any) {
    this.isActive = true;

    return {
      message: "💰 Finance agent activated. Ask me anything about your money!",
      examples: financeSkillConfig.naturalLanguagePatterns.slice(0, 6),
      isFinanceMode: true
    };
  }

  async processFinanceVoiceCommand(voiceText: string, context: any) {
    const userId = context?.userId || 'current_user';

    try {
      // Clean wake word from start of phrase if present
      const cleanedText = voiceText.replace(/^(atom|hey atom)\s*/gi, '').trim();

      return await processVoiceFinance.processVoiceFinanceCommand(
        userId,
        cleanedText,
        {
          ...context,
          interface: 'voice',
          transactionSource: 'wake_word'
        }
      );

    } catch (error) {
      return {
        ok: false,
        response: "I couldn't process your finance request. Try rephrasing or type it out.",
        suggestions: ["What's my net worth", "Show budget", "Spending this month"]
      };
    }
  }

  getFinancePrompt(context: any): string {
    return `💰 You are now in finance mode. Use any of these commands:\n${financeSkillConfig.naturalLanguagePatterns.join('\n• ')}`;
  }
}

// Export singleton
export const financeVoiceHandler = new FinanceVoiceHandler();

// Register all research skills with Atom agent
export async function registerResearchSkills() {
  console.log('🔬 Registering Atom Research Skills for Wake Word Activation');

  try {
    // Register each research skill
    for (const skill of researchSkills) {
      await registerSkill(skill);
    }

    console.log('✅ Research skills registered successfully');

    return {
      success: true,
      registeredSkills: researchSkills.length,
      naturalLanguageSupport: true,
    };

  } catch (error) {
    console.error('❌ Failed to register research skills:', error);
    return {
      success: false,
      error: error.message,
    };
  }
}

// Register all legal skills with Atom agent
export async function registerLegalSkills() {
  console.log('⚖️ Registering Atom Legal Skills for Wake Word Activation');

  try {
    // Register each legal skill
    for (const skill of legalSkills) {
      await registerSkill(skill);
    }

    console.log('✅ Legal skills registered successfully');

    return {
      success: true,
      registeredSkills: legalSkills.length,
      naturalLanguageSupport: true,
    };

  } catch (error) {
    console.error('❌ Failed to register legal skills:', error);
    return {
      success: false,
      error: error.message,
    };
  }
}

// Register all tax skills with Atom agent
export async function registerTaxSkills() {
  console.log('💸 Registering Atom Tax Skills for Wake Word Activation');

  try {
    // Register each tax skill
    for (const skill of allTaxSkills) {
      await registerSkill(skill);
    }

    // Register tax-specific tools for LLM function calling
    for (const tool of taxAgentTools) {
      await registerSkill({
        name: tool.name,
        description: tool.description || 'Tax tool',
        parameters: {}, // Tool-specific parameters assigned during registry
        handler: tool.handler
      } as SkillDefinition);
    }

    console.log('✅ Tax skills registered successfully');

    return {
      success: true,
      registeredSkills: allTaxSkills.length + taxAgentTools.length,
      naturalLanguageSupport: true
    };

  } catch (error) {
    console.error('❌ Failed to register tax skills:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

// Auto-registration on import
registerFinanceSkills().catch(console.error);
registerResearchSkills().catch(console.error);
registerLegalSkills().catch(console.error);
registerTaxSkills().catch(console.error);

// Integration exports
export { FinanceSkillRegistration as FinanceCapabilities };
export { TaxSkillRegistration as TaxCapabilities };
export { financeSkillConfig as FinanceCommandConfig };
export * as boxSkills from './boxSkills';
export * as asanaSkills from './asanaSkills';
export * as trelloSkills from './trelloSkills';
export * as jiraSkills from './jiraSkills';

// Default export for import
export default {
  registerFinanceSkills,
  financeVoiceHandler,
  financeSkillConfig,
  allFinanceSkills,
  financeAgentTools
};
