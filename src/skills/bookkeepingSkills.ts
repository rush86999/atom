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
  {
    name: 'get_bookkeeping_summary',
    description: 'Get a summary of the bookkeeping data for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the bookkeeping summary for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_bookkeeping_summary(params.user_id);
    },
  },
  {
    name: 'get_bookkeeping_report',
    description: 'Get a detailed report of the bookkeeping data for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the bookkeeping report for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_bookkeeping_report(params.user_id);
    },
  },
  {
    name: 'export_bookkeeping_data',
    description: 'Export the bookkeeping data for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to export the bookkeeping data for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.export_bookkeeping_data(params.user_id);
    },
  },
  {
    name: 'send_bookkeeping_data_to_zoho',
    description: 'Send bookkeeping data to Zoho for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to send bookkeeping data to Zoho for',
        },
        organization_id: {
          type: 'string',
          description: 'The ID of the Zoho organization to send the data to',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.send_to_zoho(
        params.user_id,
        params.organization_id
      );
    },
  },
];
