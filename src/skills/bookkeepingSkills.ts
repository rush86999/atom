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
];
