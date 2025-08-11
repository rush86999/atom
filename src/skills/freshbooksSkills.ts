import { Tool, tool } from '@atom-tools/agent';
import * as services from '@atom-tools/services';

const freshbooks_service = services.freshbooks_service;

const freshbooksSkills: Tool[] = [
  tool({
    name: 'get_freshbooks_invoices',
    description: 'Get a list of invoices from FreshBooks.',
    args: {
      user_id: {
        type: 'string',
        description: 'The ID of the user.',
      },
      organization_id: {
        type: 'string',
        description: 'The ID of the organization.',
      },
    },
    run: async (params: any) => {
      return await freshbooks_service.get_invoices(
        params.user_id,
        params.organization_id
      );
    },
  }),
  tool({
    name: 'create_freshbooks_invoice',
    description: 'Create a new invoice in FreshBooks.',
    args: {
      user_id: {
        type: 'string',
        description: 'The ID of the user.',
      },
      organization_id: {
        type: 'string',
        description: 'The ID of the organization.',
      },
      invoice_data: {
        type: 'object',
        description: 'The data for the new invoice.',
      },
    },
    run: async (params: any) => {
      return await freshbooks_service.create_invoice(
        params.user_id,
        params.organization_id,
        params.invoice_data
      );
    },
  }),
  tool({
    name: 'get_freshbooks_clients',
    description: 'Get a list of clients from FreshBooks.',
    args: {
      user_id: {
        type: 'string',
        description: 'The ID of the user.',
      },
      organization_id: {
        type: 'string',
        description: 'The ID of the organization.',
      },
    },
    run: async (params: any) => {
      return await freshbooks_service.get_clients(
        params.user_id,
        params.organization_id
      );
    },
  }),
  tool({
    name: 'create_freshbooks_client',
    description: 'Create a new client in FreshBooks.',
    args: {
      user_id: {
        type: 'string',
        description: 'The ID of the user.',
      },
      organization_id: {
        type: 'string',
        description: 'The ID of the organization.',
      },
      client_data: {
        type: 'object',
        description: 'The data for the new client.',
      },
    },
    run: async (params: any) => {
      return await freshbooks_service.create_client(
        params.user_id,
        params.organization_id,
        params.client_data
      );
    },
  }),
];

export default freshbooksSkills;
