import { Command, CommandHandler } from '../types';
import { NLULeadAgent } from '../../../nlu_agents/nlu_lead_agent';
import {
  createTransactionRule,
  listTransactionRules,
  updateTransactionRule,
  deleteTransactionRule,
} from '../skills/transactionCategorizationSkill';
import { AgentLLMService } from '../../../nlu_agents/nlu_types';

export class TransactionCategorizationCommandHandler implements CommandHandler {
  private nluAgent: NLULeadAgent;

  constructor(llmService: AgentLLMService, context: any, memory: any, functions: any) {
    this.nluAgent = new NLULeadAgent(llmService, context, memory, functions);
  }

  async handleCommand(command: Command): Promise<string> {
    const { userId, text } = command;

    // Use the NLU service to understand the user's intent and entities
    const nluResult = await this.nluAgent.analyzeIntent({ userInput: text, userId });

    if (nluResult.suggestedNextAction?.skillId !== 'TransactionCategorization') {
      return "I'm sorry, I can only help with transaction categorization rules.";
    }

    switch (nluResult.primaryGoal) {
      case 'create_transaction_rule': {
        const { merchant_name, category_name } = nluResult.extractedParameters as any;
        if (!merchant_name || !category_name) {
          return "I'm sorry, I need both a merchant name and a category to create a rule.";
        }
        const newRule = { pattern: merchant_name, target_value: category_name };
        const createResponse = await createTransactionRule(userId, newRule);
        return createResponse.message;
      }

      case 'list_transaction_rules': {
        const listResponse = await listTransactionRules(userId);
        if (listResponse.success && listResponse.data) {
          const rules = listResponse.data as any[];
          if (rules.length === 0) {
            return 'You have no transaction categorization rules.';
          }
          const ruleList = rules.map(rule => `- ${rule.rule_name}: ${rule.pattern} -> ${rule.target_value}`).join('\n');
          return `Here are your transaction categorization rules:\n${ruleList}`;
        }
        return listResponse.message;
      }

      case 'update_transaction_rule': {
        const { rule_id, updates } = nluResult.extractedParameters as any;
        if (!rule_id || !updates) {
          return "I'm sorry, I need a rule ID and the updates to apply.";
        }
        const updateResponse = await updateTransactionRule(userId, rule_id, updates);
        return updateResponse.message;
      }

      case 'delete_transaction_rule': {
        const { rule_id } = nluResult.extractedParameters as any;
        if (!rule_id) {
          return "I'm sorry, I need the ID of the rule to delete.";
        }
        const deleteResponse = await deleteTransactionRule(userId, rule_id);
        return deleteResponse.message;
      }

      default:
        return "I'm sorry, I don't understand that command. You can ask me to 'list transaction rules', 'create a new rule', 'update a rule', or 'delete a rule'.";
    }
  }
}
