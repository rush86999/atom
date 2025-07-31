import { SkillDefinition } from '../types';
import { bookkeeping_service } from '../services';

export const bookkeepingSkills: SkillDefinition[] = [
  {
    name: 'get_bookkeeping_data',
    description: 'Get bookkeeping data for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get bookkeeping data for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_bookkeeping_data(params.user_id);
    },
  },
  {
    name: 'create_bookkeeping_entry',
    description: 'Create a new bookkeeping entry for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the bookkeeping entry for',
        },
        entry_data: {
          type: 'object',
          description: 'The data for the new bookkeeping entry',
        },
      },
      required: ['user_id', 'entry_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_bookkeeping_entry(
        params.user_id,
        params.entry_data
      );
    },
  },
];
