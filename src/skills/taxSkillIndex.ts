import { SkillDefinition, ToolImplementation } from '../types';
import { handleTaxQuery } from './taxExpertSkills';

export const taxSkills: SkillDefinition[] = [
  {
    name: 'tax_query',
    description: 'Answer tax-related questions',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'The tax-related question to answer'
        }
      },
      required: ['query']
    },
    handler: async (params: any, context: any) => {
      const userId = context?.metadata?.userId || 'user';
      return await handleTaxQuery(userId, params.query);
    }
  }
];

export const taxAgentTools: ToolImplementation[] = [
  {
    name: 'tax_query_handler',
    description: 'Handle tax-related queries through natural language',
    handler: async (params: any) => {
      return await handleTaxQuery(params.userId, params.query);
    }
  }
];

export const TaxSkillRegistration = {
  name: 'Tax Expert',
  version: '1.0.0',
  description: 'Provides information and answers questions about taxes.',
  capabilities: [
    'Tax calculation',
    'Tax deduction information',
    'General tax advice'
  ],
  activationPrefixes: [
    'tax',
    'taxes'
  ],
  voiceTriggers: [
    'tax help'
  ],
  desktopCommands: [
    'calculate my taxes',
    'find tax deductions'
  ],
  webCommands: '/tax',
  apiEndpoints: {
    web: '/api/tax',
    desktop: 'tax://',
    mobile: 'atom://tax'
  }
};

export const allTaxSkills = [
  ...taxSkills
];
