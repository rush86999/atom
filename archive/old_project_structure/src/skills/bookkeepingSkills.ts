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
          description:
            'The ID of the user to send bookkeeping data to Zoho for',
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
  {
    name: 'disconnect_zoho_account',
    description: "Disconnect a user's Zoho account",
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to disconnect the Zoho account for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.disconnect_zoho_account(params.user_id);
    },
  },
  {
    name: 'get_zoho_integration_status',
    description: "Get the status of a user's Zoho integration",
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description:
            'The ID of the user to get the Zoho integration status for',
        },
      },
      required: ['user_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_integration_status(
        params.user_id
      );
    },
  },
  {
    name: 'get_zoho_invoices',
    description: 'Get a list of Zoho invoices for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho invoices for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to get the invoices from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_invoices(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_invoice',
    description: 'Create a new Zoho invoice for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho invoice for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to create the invoice in',
        },
        invoice_data: {
          type: 'object',
          description: 'The data for the new Zoho invoice',
        },
      },
      required: ['user_id', 'organization_id', 'invoice_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_invoice(
        params.user_id,
        params.organization_id,
        params.invoice_data
      );
    },
  },
  {
    name: 'get_zoho_customers',
    description: 'Get a list of Zoho customers for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho customers for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to get the customers from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_customers(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_customer',
    description: 'Create a new Zoho customer for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho customer for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to create the customer in',
        },
        customer_data: {
          type: 'object',
          description: 'The data for the new Zoho customer',
        },
      },
      required: ['user_id', 'organization_id', 'customer_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_customer(
        params.user_id,
        params.organization_id,
        params.customer_data
      );
    },
  },
  {
    name: 'get_zoho_items',
    description: 'Get a list of Zoho items for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho items for',
        },
        organization_id: {
          type: 'string',
          description: 'The ID of the Zoho organization to get the items from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_items(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_item',
    description: 'Create a new Zoho item for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho item for',
        },
        organization_id: {
          type: 'string',
          description: 'The ID of the Zoho organization to create the item in',
        },
        item_data: {
          type: 'object',
          description: 'The data for the new Zoho item',
        },
      },
      required: ['user_id', 'organization_id', 'item_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_item(
        params.user_id,
        params.organization_id,
        params.item_data
      );
    },
  },
  {
    name: 'get_zoho_bills',
    description: 'Get a list of Zoho bills for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho bills for',
        },
        organization_id: {
          type: 'string',
          description: 'The ID of the Zoho organization to get the bills from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_bills(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_bill',
    description: 'Create a new Zoho bill for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho bill for',
        },
        organization_id: {
          type: 'string',
          description: 'The ID of the Zoho organization to create the bill in',
        },
        bill_data: {
          type: 'object',
          description: 'The data for the new Zoho bill',
        },
      },
      required: ['user_id', 'organization_id', 'bill_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_bill(
        params.user_id,
        params.organization_id,
        params.bill_data
      );
    },
  },
  {
    name: 'get_zoho_vendors',
    description: 'Get a list of Zoho vendors for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho vendors for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to get the vendors from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_vendors(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_vendor',
    description: 'Create a new Zoho vendor for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho vendor for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to create the vendor in',
        },
        vendor_data: {
          type: 'object',
          description: 'The data for the new Zoho vendor',
        },
      },
      required: ['user_id', 'organization_id', 'vendor_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_vendor(
        params.user_id,
        params.organization_id,
        params.vendor_data
      );
    },
  },
  {
    name: 'get_zoho_purchase_orders',
    description: 'Get a list of Zoho purchase orders for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho purchase orders for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to get the purchase orders from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_purchase_orders(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_purchase_order',
    description: 'Create a new Zoho purchase order for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description:
            'The ID of the user to create the Zoho purchase order for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to create the purchase order in',
        },
        purchase_order_data: {
          type: 'object',
          description: 'The data for the new Zoho purchase order',
        },
      },
      required: ['user_id', 'organization_id', 'purchase_order_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_purchase_order(
        params.user_id,
        params.organization_id,
        params.purchase_order_data
      );
    },
  },
  {
    name: 'get_zoho_sales_orders',
    description: 'Get a list of Zoho sales orders for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to get the Zoho sales orders for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to get the sales orders from',
        },
      },
      required: ['user_id', 'organization_id'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.get_zoho_sales_orders(
        params.user_id,
        params.organization_id
      );
    },
  },
  {
    name: 'create_zoho_sales_order',
    description: 'Create a new Zoho sales order for a user',
    parameters: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'The ID of the user to create the Zoho sales order for',
        },
        organization_id: {
          type: 'string',
          description:
            'The ID of the Zoho organization to create the sales order in',
        },
        sales_order_data: {
          type: 'object',
          description: 'The data for the new Zoho sales order',
        },
      },
      required: ['user_id', 'organization_id', 'sales_order_data'],
    },
    handler: async (params: any) => {
      return await bookkeeping_service.create_zoho_sales_order(
        params.user_id,
        params.organization_id,
        params.sales_order_data
      );
    },
  },
];
