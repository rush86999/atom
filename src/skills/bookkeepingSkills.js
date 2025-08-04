"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.bookkeepingSkills = void 0;
const services_1 = require("../services");
exports.bookkeepingSkills = [
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_bookkeeping_data(params.user_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_bookkeeping_entry(params.user_id, params.entry_data);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_bookkeeping_summary(params.user_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_bookkeeping_report(params.user_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.export_bookkeeping_data(params.user_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.send_to_zoho(params.user_id, params.organization_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.disconnect_zoho_account(params.user_id);
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
                    description: 'The ID of the user to get the Zoho integration status for',
                },
            },
            required: ['user_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_integration_status(params.user_id);
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
                    description: 'The ID of the Zoho organization to get the invoices from',
                },
            },
            required: ['user_id', 'organization_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_invoices(params.user_id, params.organization_id);
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
                    description: 'The ID of the Zoho organization to create the invoice in',
                },
                invoice_data: {
                    type: 'object',
                    description: 'The data for the new Zoho invoice',
                },
            },
            required: ['user_id', 'organization_id', 'invoice_data'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_invoice(params.user_id, params.organization_id, params.invoice_data);
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
                    description: 'The ID of the Zoho organization to get the customers from',
                },
            },
            required: ['user_id', 'organization_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_customers(params.user_id, params.organization_id);
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
                    description: 'The ID of the Zoho organization to create the customer in',
                },
                customer_data: {
                    type: 'object',
                    description: 'The data for the new Zoho customer',
                },
            },
            required: ['user_id', 'organization_id', 'customer_data'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_customer(params.user_id, params.organization_id, params.customer_data);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_items(params.user_id, params.organization_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_item(params.user_id, params.organization_id, params.item_data);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_bills(params.user_id, params.organization_id);
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
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_bill(params.user_id, params.organization_id, params.bill_data);
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
                    description: 'The ID of the Zoho organization to get the vendors from',
                },
            },
            required: ['user_id', 'organization_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_vendors(params.user_id, params.organization_id);
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
                    description: 'The ID of the Zoho organization to create the vendor in',
                },
                vendor_data: {
                    type: 'object',
                    description: 'The data for the new Zoho vendor',
                },
            },
            required: ['user_id', 'organization_id', 'vendor_data'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_vendor(params.user_id, params.organization_id, params.vendor_data);
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
                    description: 'The ID of the Zoho organization to get the purchase orders from',
                },
            },
            required: ['user_id', 'organization_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_purchase_orders(params.user_id, params.organization_id);
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
                    description: 'The ID of the user to create the Zoho purchase order for',
                },
                organization_id: {
                    type: 'string',
                    description: 'The ID of the Zoho organization to create the purchase order in',
                },
                purchase_order_data: {
                    type: 'object',
                    description: 'The data for the new Zoho purchase order',
                },
            },
            required: ['user_id', 'organization_id', 'purchase_order_data'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_purchase_order(params.user_id, params.organization_id, params.purchase_order_data);
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
                    description: 'The ID of the Zoho organization to get the sales orders from',
                },
            },
            required: ['user_id', 'organization_id'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.get_zoho_sales_orders(params.user_id, params.organization_id);
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
                    description: 'The ID of the Zoho organization to create the sales order in',
                },
                sales_order_data: {
                    type: 'object',
                    description: 'The data for the new Zoho sales order',
                },
            },
            required: ['user_id', 'organization_id', 'sales_order_data'],
        },
        handler: async (params) => {
            return await services_1.bookkeeping_service.create_zoho_sales_order(params.user_id, params.organization_id, params.sales_order_data);
        },
    },
];
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYm9va2tlZXBpbmdTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJib29ra2VlcGluZ1NraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFDQSwwQ0FBa0Q7QUFFckMsUUFBQSxpQkFBaUIsR0FBc0I7SUFDbEQ7UUFDRSxJQUFJLEVBQUUsc0JBQXNCO1FBQzVCLFdBQVcsRUFBRSxpQ0FBaUM7UUFDOUMsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFFBQVE7WUFDZCxVQUFVLEVBQUU7Z0JBQ1YsT0FBTyxFQUFFO29CQUNQLElBQUksRUFBRSxRQUFRO29CQUNkLFdBQVcsRUFBRSxnREFBZ0Q7aUJBQzlEO2FBQ0Y7WUFDRCxRQUFRLEVBQUUsQ0FBQyxTQUFTLENBQUM7U0FDdEI7UUFDRCxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQVcsRUFBRSxFQUFFO1lBQzdCLE9BQU8sTUFBTSw4QkFBbUIsQ0FBQyxvQkFBb0IsQ0FBQyxNQUFNLENBQUMsT0FBTyxDQUFDLENBQUM7UUFDeEUsQ0FBQztLQUNGO0lBQ0Q7UUFDRSxJQUFJLEVBQUUsMEJBQTBCO1FBQ2hDLFdBQVcsRUFBRSwyQ0FBMkM7UUFDeEQsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFFBQVE7WUFDZCxVQUFVLEVBQUU7Z0JBQ1YsT0FBTyxFQUFFO29CQUNQLElBQUksRUFBRSxRQUFRO29CQUNkLFdBQVcsRUFBRSx3REFBd0Q7aUJBQ3RFO2dCQUNELFVBQVUsRUFBRTtvQkFDVixJQUFJLEVBQUUsUUFBUTtvQkFDZCxXQUFXLEVBQUUsd0NBQXdDO2lCQUN0RDthQUNGO1lBQ0QsUUFBUSxFQUFFLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQztTQUNwQztRQUNELE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBVyxFQUFFLEVBQUU7WUFDN0IsT0FBTyxNQUFNLDhCQUFtQixDQUFDLHdCQUF3QixDQUN2RCxNQUFNLENBQUMsT0FBTyxFQUNkLE1BQU0sQ0FBQyxVQUFVLENBQ2xCLENBQUM7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QUFDLFNBQVMsRUFBRSxpQkFBaUIsQ0FBQztTQUN6QztRQUNELE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBVyxFQUFFLEVBQUU7WUFDN0IsT0FBTyxNQUFNLDhCQUFtQixDQUFDLHFCQUFxQixDQUNwRCxNQUFNLENBQUMsT0FBTyxFQUNkLE1BQU0sQ0FBQyxlQUFlLENBQ3ZCLENBQUM7UUFDSixDQUFDO0tBQ0Y7SUFDRDtRQUNFLElBQUksRUFBRSx5QkFBeUI7UUFDL0IsV0FBVyxFQUFFLDBDQUEwQztRQUN2RCxVQUFVLEVBQUU7WUFDVixJQUFJLEVBQUUsUUFBUTtZQUNkLFVBQVUsRUFBRTtnQkFDVixPQUFPLEVBQUU7b0JBQ1AsSUFBSSxFQUFFLFFBQVE7b0JBQ2QsV0FBVyxFQUFFLHVEQUF1RDtpQkFDckU7Z0JBQ0QsZUFBZSxFQUFFO29CQUNmLElBQUksRUFBRSxRQUFRO29CQUNkLFdBQVcsRUFDVCw4REFBOEQ7aUJBQ2pFO2dCQUNELGdCQUFnQixFQUFFO29CQUNoQixJQUFJLEVBQUUsUUFBUTtvQkFDZCxXQUFXLEVBQUUsdUNBQXVDO2lCQUNyRDthQUNGO1lBQ0QsUUFBUSxFQUFFLENBQUMsU0FBUyxFQUFFLGlCQUFpQixFQUFFLGtCQUFrQixDQUFDO1NBQzdEO1FBQ0QsT0FBTyxFQUFFLEtBQUssRUFBRSxNQUFXLEVBQUUsRUFBRTtZQUM3QixPQUFPLE1BQU0sOEJBQW1CLENBQUMsdUJBQXVCLENBQ3RELE1BQU0sQ0FBQyxPQUFPLEVBQ2QsTUFBTSxDQUFDLGVBQWUsRUFDdEIsTUFBTSxDQUFDLGdCQUFnQixDQUN4QixDQUFDO1FBQ0osQ0FBQztLQUNGO0NBQ0YsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFNraWxsRGVmaW5pdGlvbiB9IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGJvb2trZWVwaW5nX3NlcnZpY2UgfSBmcm9tICcuLi9zZXJ2aWNlcyc7XG5cbmV4cG9ydCBjb25zdCBib29ra2VlcGluZ1NraWxsczogU2tpbGxEZWZpbml0aW9uW10gPSBbXG4gIHtcbiAgICBuYW1lOiAnZ2V0X2Jvb2trZWVwaW5nX2RhdGEnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGJvb2trZWVwaW5nIGRhdGEgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBnZXQgYm9va2tlZXBpbmcgZGF0YSBmb3InLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3VzZXJfaWQnXSxcbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIGF3YWl0IGJvb2trZWVwaW5nX3NlcnZpY2UuZ2V0X2Jvb2trZWVwaW5nX2RhdGEocGFyYW1zLnVzZXJfaWQpO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnY3JlYXRlX2Jvb2trZWVwaW5nX2VudHJ5JyxcbiAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBib29ra2VlcGluZyBlbnRyeSBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGNyZWF0ZSB0aGUgYm9va2tlZXBpbmcgZW50cnkgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgZW50cnlfZGF0YToge1xuICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIGRhdGEgZm9yIHRoZSBuZXcgYm9va2tlZXBpbmcgZW50cnknLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3VzZXJfaWQnLCAnZW50cnlfZGF0YSddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5jcmVhdGVfYm9va2tlZXBpbmdfZW50cnkoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMuZW50cnlfZGF0YVxuICAgICAgKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2dldF9ib29ra2VlcGluZ19zdW1tYXJ5JyxcbiAgICBkZXNjcmlwdGlvbjogJ0dldCBhIHN1bW1hcnkgb2YgdGhlIGJvb2trZWVwaW5nIGRhdGEgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBnZXQgdGhlIGJvb2trZWVwaW5nIHN1bW1hcnkgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmdldF9ib29ra2VlcGluZ19zdW1tYXJ5KHBhcmFtcy51c2VyX2lkKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2dldF9ib29ra2VlcGluZ19yZXBvcnQnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgZGV0YWlsZWQgcmVwb3J0IG9mIHRoZSBib29ra2VlcGluZyBkYXRhIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZ2V0IHRoZSBib29ra2VlcGluZyByZXBvcnQgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmdldF9ib29ra2VlcGluZ19yZXBvcnQocGFyYW1zLnVzZXJfaWQpO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZXhwb3J0X2Jvb2trZWVwaW5nX2RhdGEnLFxuICAgIGRlc2NyaXB0aW9uOiAnRXhwb3J0IHRoZSBib29ra2VlcGluZyBkYXRhIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZXhwb3J0IHRoZSBib29ra2VlcGluZyBkYXRhIGZvcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5leHBvcnRfYm9va2tlZXBpbmdfZGF0YShwYXJhbXMudXNlcl9pZCk7XG4gICAgfSxcbiAgfSxcbiAge1xuICAgIG5hbWU6ICdzZW5kX2Jvb2trZWVwaW5nX2RhdGFfdG9fem9obycsXG4gICAgZGVzY3JpcHRpb246ICdTZW5kIGJvb2trZWVwaW5nIGRhdGEgdG8gWm9obyBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBzZW5kIGJvb2trZWVwaW5nIGRhdGEgdG8gWm9obyBmb3InLFxuICAgICAgICB9LFxuICAgICAgICBvcmdhbml6YXRpb25faWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgWm9obyBvcmdhbml6YXRpb24gdG8gc2VuZCB0aGUgZGF0YSB0bycsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnXSxcbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIGF3YWl0IGJvb2trZWVwaW5nX3NlcnZpY2Uuc2VuZF90b196b2hvKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZFxuICAgICAgKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2Rpc2Nvbm5lY3Rfem9ob19hY2NvdW50JyxcbiAgICBkZXNjcmlwdGlvbjogXCJEaXNjb25uZWN0IGEgdXNlcidzIFpvaG8gYWNjb3VudFwiLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZGlzY29ubmVjdCB0aGUgWm9obyBhY2NvdW50IGZvcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5kaXNjb25uZWN0X3pvaG9fYWNjb3VudChwYXJhbXMudXNlcl9pZCk7XG4gICAgfSxcbiAgfSxcbiAge1xuICAgIG5hbWU6ICdnZXRfem9ob19pbnRlZ3JhdGlvbl9zdGF0dXMnLFxuICAgIGRlc2NyaXB0aW9uOiBcIkdldCB0aGUgc3RhdHVzIG9mIGEgdXNlcidzIFpvaG8gaW50ZWdyYXRpb25cIixcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBnZXQgdGhlIFpvaG8gaW50ZWdyYXRpb24gc3RhdHVzIGZvcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5nZXRfem9ob19pbnRlZ3JhdGlvbl9zdGF0dXMoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZ2V0X3pvaG9faW52b2ljZXMnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgbGlzdCBvZiBab2hvIGludm9pY2VzIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZ2V0IHRoZSBab2hvIGludm9pY2VzIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ1RoZSBJRCBvZiB0aGUgWm9obyBvcmdhbml6YXRpb24gdG8gZ2V0IHRoZSBpbnZvaWNlcyBmcm9tJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJywgJ29yZ2FuaXphdGlvbl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5nZXRfem9ob19pbnZvaWNlcyhcbiAgICAgICAgcGFyYW1zLnVzZXJfaWQsXG4gICAgICAgIHBhcmFtcy5vcmdhbml6YXRpb25faWRcbiAgICAgICk7XG4gICAgfSxcbiAgfSxcbiAge1xuICAgIG5hbWU6ICdjcmVhdGVfem9ob19pbnZvaWNlJyxcbiAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBab2hvIGludm9pY2UgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBjcmVhdGUgdGhlIFpvaG8gaW52b2ljZSBmb3InLFxuICAgICAgICB9LFxuICAgICAgICBvcmdhbml6YXRpb25faWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAgICdUaGUgSUQgb2YgdGhlIFpvaG8gb3JnYW5pemF0aW9uIHRvIGNyZWF0ZSB0aGUgaW52b2ljZSBpbicsXG4gICAgICAgIH0sXG4gICAgICAgIGludm9pY2VfZGF0YToge1xuICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIGRhdGEgZm9yIHRoZSBuZXcgWm9obyBpbnZvaWNlJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJywgJ29yZ2FuaXphdGlvbl9pZCcsICdpbnZvaWNlX2RhdGEnXSxcbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIGF3YWl0IGJvb2trZWVwaW5nX3NlcnZpY2UuY3JlYXRlX3pvaG9faW52b2ljZShcbiAgICAgICAgcGFyYW1zLnVzZXJfaWQsXG4gICAgICAgIHBhcmFtcy5vcmdhbml6YXRpb25faWQsXG4gICAgICAgIHBhcmFtcy5pbnZvaWNlX2RhdGFcbiAgICAgICk7XG4gICAgfSxcbiAgfSxcbiAge1xuICAgIG5hbWU6ICdnZXRfem9ob19jdXN0b21lcnMnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgbGlzdCBvZiBab2hvIGN1c3RvbWVycyBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGdldCB0aGUgWm9obyBjdXN0b21lcnMgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgb3JnYW5pemF0aW9uX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBnZXQgdGhlIGN1c3RvbWVycyBmcm9tJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJywgJ29yZ2FuaXphdGlvbl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5nZXRfem9ob19jdXN0b21lcnMoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMub3JnYW5pemF0aW9uX2lkXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnY3JlYXRlX3pvaG9fY3VzdG9tZXInLFxuICAgIGRlc2NyaXB0aW9uOiAnQ3JlYXRlIGEgbmV3IFpvaG8gY3VzdG9tZXIgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBjcmVhdGUgdGhlIFpvaG8gY3VzdG9tZXIgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgb3JnYW5pemF0aW9uX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBjcmVhdGUgdGhlIGN1c3RvbWVyIGluJyxcbiAgICAgICAgfSxcbiAgICAgICAgY3VzdG9tZXJfZGF0YToge1xuICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIGRhdGEgZm9yIHRoZSBuZXcgWm9obyBjdXN0b21lcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnLCAnY3VzdG9tZXJfZGF0YSddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5jcmVhdGVfem9ob19jdXN0b21lcihcbiAgICAgICAgcGFyYW1zLnVzZXJfaWQsXG4gICAgICAgIHBhcmFtcy5vcmdhbml6YXRpb25faWQsXG4gICAgICAgIHBhcmFtcy5jdXN0b21lcl9kYXRhXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZ2V0X3pvaG9faXRlbXMnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgbGlzdCBvZiBab2hvIGl0ZW1zIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZ2V0IHRoZSBab2hvIGl0ZW1zIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBnZXQgdGhlIGl0ZW1zIGZyb20nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3VzZXJfaWQnLCAnb3JnYW5pemF0aW9uX2lkJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmdldF96b2hvX2l0ZW1zKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZFxuICAgICAgKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2NyZWF0ZV96b2hvX2l0ZW0nLFxuICAgIGRlc2NyaXB0aW9uOiAnQ3JlYXRlIGEgbmV3IFpvaG8gaXRlbSBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGNyZWF0ZSB0aGUgWm9obyBpdGVtIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBjcmVhdGUgdGhlIGl0ZW0gaW4nLFxuICAgICAgICB9LFxuICAgICAgICBpdGVtX2RhdGE6IHtcbiAgICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBkYXRhIGZvciB0aGUgbmV3IFpvaG8gaXRlbScsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnLCAnaXRlbV9kYXRhJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmNyZWF0ZV96b2hvX2l0ZW0oXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMub3JnYW5pemF0aW9uX2lkLFxuICAgICAgICBwYXJhbXMuaXRlbV9kYXRhXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZ2V0X3pvaG9fYmlsbHMnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgbGlzdCBvZiBab2hvIGJpbGxzIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgSUQgb2YgdGhlIHVzZXIgdG8gZ2V0IHRoZSBab2hvIGJpbGxzIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBnZXQgdGhlIGJpbGxzIGZyb20nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3VzZXJfaWQnLCAnb3JnYW5pemF0aW9uX2lkJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmdldF96b2hvX2JpbGxzKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZFxuICAgICAgKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2NyZWF0ZV96b2hvX2JpbGwnLFxuICAgIGRlc2NyaXB0aW9uOiAnQ3JlYXRlIGEgbmV3IFpvaG8gYmlsbCBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGNyZWF0ZSB0aGUgWm9obyBiaWxsIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBjcmVhdGUgdGhlIGJpbGwgaW4nLFxuICAgICAgICB9LFxuICAgICAgICBiaWxsX2RhdGE6IHtcbiAgICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBkYXRhIGZvciB0aGUgbmV3IFpvaG8gYmlsbCcsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnLCAnYmlsbF9kYXRhJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmNyZWF0ZV96b2hvX2JpbGwoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMub3JnYW5pemF0aW9uX2lkLFxuICAgICAgICBwYXJhbXMuYmlsbF9kYXRhXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZ2V0X3pvaG9fdmVuZG9ycycsXG4gICAgZGVzY3JpcHRpb246ICdHZXQgYSBsaXN0IG9mIFpvaG8gdmVuZG9ycyBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGdldCB0aGUgWm9obyB2ZW5kb3JzIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ1RoZSBJRCBvZiB0aGUgWm9obyBvcmdhbml6YXRpb24gdG8gZ2V0IHRoZSB2ZW5kb3JzIGZyb20nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3VzZXJfaWQnLCAnb3JnYW5pemF0aW9uX2lkJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmdldF96b2hvX3ZlbmRvcnMoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMub3JnYW5pemF0aW9uX2lkXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnY3JlYXRlX3pvaG9fdmVuZG9yJyxcbiAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBab2hvIHZlbmRvciBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGNyZWF0ZSB0aGUgWm9obyB2ZW5kb3IgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgb3JnYW5pemF0aW9uX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBjcmVhdGUgdGhlIHZlbmRvciBpbicsXG4gICAgICAgIH0sXG4gICAgICAgIHZlbmRvcl9kYXRhOiB7XG4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgZGF0YSBmb3IgdGhlIG5ldyBab2hvIHZlbmRvcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnLCAndmVuZG9yX2RhdGEnXSxcbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIGF3YWl0IGJvb2trZWVwaW5nX3NlcnZpY2UuY3JlYXRlX3pvaG9fdmVuZG9yKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZCxcbiAgICAgICAgcGFyYW1zLnZlbmRvcl9kYXRhXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnZ2V0X3pvaG9fcHVyY2hhc2Vfb3JkZXJzJyxcbiAgICBkZXNjcmlwdGlvbjogJ0dldCBhIGxpc3Qgb2YgWm9obyBwdXJjaGFzZSBvcmRlcnMgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBnZXQgdGhlIFpvaG8gcHVyY2hhc2Ugb3JkZXJzIGZvcicsXG4gICAgICAgIH0sXG4gICAgICAgIG9yZ2FuaXphdGlvbl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ1RoZSBJRCBvZiB0aGUgWm9obyBvcmdhbml6YXRpb24gdG8gZ2V0IHRoZSBwdXJjaGFzZSBvcmRlcnMgZnJvbScsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnXSxcbiAgICB9LFxuICAgIGhhbmRsZXI6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIGF3YWl0IGJvb2trZWVwaW5nX3NlcnZpY2UuZ2V0X3pvaG9fcHVyY2hhc2Vfb3JkZXJzKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZFxuICAgICAgKTtcbiAgICB9LFxuICB9LFxuICB7XG4gICAgbmFtZTogJ2NyZWF0ZV96b2hvX3B1cmNoYXNlX29yZGVyJyxcbiAgICBkZXNjcmlwdGlvbjogJ0NyZWF0ZSBhIG5ldyBab2hvIHB1cmNoYXNlIG9yZGVyIGZvciBhIHVzZXInLFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICB1c2VyX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGNyZWF0ZSB0aGUgWm9obyBwdXJjaGFzZSBvcmRlciBmb3InLFxuICAgICAgICB9LFxuICAgICAgICBvcmdhbml6YXRpb25faWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAgICdUaGUgSUQgb2YgdGhlIFpvaG8gb3JnYW5pemF0aW9uIHRvIGNyZWF0ZSB0aGUgcHVyY2hhc2Ugb3JkZXIgaW4nLFxuICAgICAgICB9LFxuICAgICAgICBwdXJjaGFzZV9vcmRlcl9kYXRhOiB7XG4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdUaGUgZGF0YSBmb3IgdGhlIG5ldyBab2hvIHB1cmNoYXNlIG9yZGVyJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJywgJ29yZ2FuaXphdGlvbl9pZCcsICdwdXJjaGFzZV9vcmRlcl9kYXRhJ10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBib29ra2VlcGluZ19zZXJ2aWNlLmNyZWF0ZV96b2hvX3B1cmNoYXNlX29yZGVyKFxuICAgICAgICBwYXJhbXMudXNlcl9pZCxcbiAgICAgICAgcGFyYW1zLm9yZ2FuaXphdGlvbl9pZCxcbiAgICAgICAgcGFyYW1zLnB1cmNoYXNlX29yZGVyX2RhdGFcbiAgICAgICk7XG4gICAgfSxcbiAgfSxcbiAge1xuICAgIG5hbWU6ICdnZXRfem9ob19zYWxlc19vcmRlcnMnLFxuICAgIGRlc2NyaXB0aW9uOiAnR2V0IGEgbGlzdCBvZiBab2hvIHNhbGVzIG9yZGVycyBmb3IgYSB1c2VyJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXNlcl9pZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIElEIG9mIHRoZSB1c2VyIHRvIGdldCB0aGUgWm9obyBzYWxlcyBvcmRlcnMgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgb3JnYW5pemF0aW9uX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBnZXQgdGhlIHNhbGVzIG9yZGVycyBmcm9tJyxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgICByZXF1aXJlZDogWyd1c2VyX2lkJywgJ29yZ2FuaXphdGlvbl9pZCddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5nZXRfem9ob19zYWxlc19vcmRlcnMoXG4gICAgICAgIHBhcmFtcy51c2VyX2lkLFxuICAgICAgICBwYXJhbXMub3JnYW5pemF0aW9uX2lkXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG4gIHtcbiAgICBuYW1lOiAnY3JlYXRlX3pvaG9fc2FsZXNfb3JkZXInLFxuICAgIGRlc2NyaXB0aW9uOiAnQ3JlYXRlIGEgbmV3IFpvaG8gc2FsZXMgb3JkZXIgZm9yIGEgdXNlcicsXG4gICAgcGFyYW1ldGVyczoge1xuICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIHVzZXJfaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSBJRCBvZiB0aGUgdXNlciB0byBjcmVhdGUgdGhlIFpvaG8gc2FsZXMgb3JkZXIgZm9yJyxcbiAgICAgICAgfSxcbiAgICAgICAgb3JnYW5pemF0aW9uX2lkOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgICAnVGhlIElEIG9mIHRoZSBab2hvIG9yZ2FuaXphdGlvbiB0byBjcmVhdGUgdGhlIHNhbGVzIG9yZGVyIGluJyxcbiAgICAgICAgfSxcbiAgICAgICAgc2FsZXNfb3JkZXJfZGF0YToge1xuICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhlIGRhdGEgZm9yIHRoZSBuZXcgWm9obyBzYWxlcyBvcmRlcicsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgICAgcmVxdWlyZWQ6IFsndXNlcl9pZCcsICdvcmdhbml6YXRpb25faWQnLCAnc2FsZXNfb3JkZXJfZGF0YSddLFxuICAgIH0sXG4gICAgaGFuZGxlcjogYXN5bmMgKHBhcmFtczogYW55KSA9PiB7XG4gICAgICByZXR1cm4gYXdhaXQgYm9va2tlZXBpbmdfc2VydmljZS5jcmVhdGVfem9ob19zYWxlc19vcmRlcihcbiAgICAgICAgcGFyYW1zLnVzZXJfaWQsXG4gICAgICAgIHBhcmFtcy5vcmdhbml6YXRpb25faWQsXG4gICAgICAgIHBhcmFtcy5zYWxlc19vcmRlcl9kYXRhXG4gICAgICApO1xuICAgIH0sXG4gIH0sXG5dO1xuIl19