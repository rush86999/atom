import { SkillResponse } from '../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../_libs/constants';
import { logger } from '../_utils/logger';

interface BookkeepingEntry {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: string;
  type: 'income' | 'expense';
}

interface ZohoInvoice {
  invoice_id: string;
  invoice_number: string;
  date: string;
  due_date: string;
  customer_name: string;
  total: number;
  status: string;
}

interface ZohoCustomer {
  customer_id: string;
  display_name: string;
  email: string;
  phone: string;
}

// Helper function for API calls
async function callBookkeepingApi(endpoint: string, params?: Record<string, any>): Promise<any> {
  if (!PYTHON_API_SERVICE_BASE_URL) {
    throw new Error('Python API service URL is not configured.');
  }

  const url = new URL(`${PYTHON_API_SERVICE_BASE_URL}${endpoint}`);
  if (params) {
    Object.keys(params).forEach(key => {
      url.searchParams.append(key, params[key]);
    });
  }

  try {
    const response = await fetch(url.toString());
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || 'API request failed');
    }

    return data;
  } catch (error) {
    logger.error('Bookkeeping API call failed', error);
    throw error;
  }
}

export async function handleGetBookkeepingData(userId: string): Promise<string> {
  try {
    const data = await callBookkeepingApi('/api/bookkeeping/data', { user_id: userId });
    const entries = data.entries || [];
    return `Found ${entries.length} bookkeeping entries`;
  } catch (error: any) {
    return `Error fetching bookkeeping data: ${error.message}`;
  }
}

export async function handleCreateBookkeepingEntry(userId: string, entities: any): Promise<string> {
  try {
    const {PYTHON_API_SERVICE_BASE_URL} = require('../_libs/constants');
    const entryData = {
      description: entities.description || 'Entry from agent',
      amount: parseFloat(entities.amount) || 0,
      category: entities.category || 'Miscellaneous',
      type: entities.type || 'expense',
      date: entities.date || new Date().toISOString().split('T')[0]
    };

    const response = await fetch(`${PYTHON_API_SERVICE_BASE_URL}/api/bookkeeping/entry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, entry_data: entryData })
    });

    const result = await response.json();
    return `Created bookkeeping entry: ${result.id}`;
  } catch (error: any) {
    return `Error creating bookkeeping entry: ${error.message}`;
  }
}

export async function handleGetBookkeepingSummary(userId: string): Promise<string> {
  try {
    const summary = await callBookkeepingApi('/api/bookkeeping/summary', { user_id: userId });
    return `Bookkeeping summary: ${summary.total_income || 0} income, ${summary.total_expenses || 0} expenses`;
  } catch (error: any) {
    return `Error fetching bookkeeping summary: ${error.message}`;
  }
}

export async function handleGetZohoInvoices(userId: string, entities: any): Promise<string> {
  const orgId = entities.organization_id || entities.orgId;
  if (!orgId) {
    return 'Please provide a Zoho organization ID';
  }

  try {
    const invoices = await callBookkeepingApi('/api/zoho/invoices', {
      user_id: userId,
      organization_id: orgId
    });

    const invoiceList = invoices.invoices || [];
    return `Found ${invoiceList.length} Zoho invoice${invoiceList.length !== 1 ? 's' : ''}`;
  } catch (error: any) {
    return `Error fetching Zoho invoices: ${error.message}`;
  }
}

export async function handleCreateZohoInvoice(userId: string, entities: any): Promise<string> {
  const orgId = entities.organization_id || entities.orgId;
  if (!orgId) {
    return 'Please provide a Zoho organization ID';
  }

  try {
    const invoiceData = {
      customer_id: entities.customer_id,
      invoice_number: entities.invoice_number || `INV-${Date.now()}`,
      date: entities.date || new Date().toISOString().split('T')[0],
      due_date: entities.due_date,
      line_items: entities.line_items || []
    };

    const response = await fetch(`${PYTHON_API_SERVICE_BASE_URL}/api/zoho/invoices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        organization_id: orgId,
        invoice_data: invoiceData
      })
    });

    const result = await response.json();
    return `Created Zoho invoice: ${result.invoice.invoice_number}`;
  } catch (error: any) {
    return `Error creating Zoho invoice: ${error.message}`;
  }
}

export async function handleGetZohoCustomers(userId: string, entities: any): Promise<string> {
  const orgId = entities.organization_id || entities.orgId;
  if (!orgId) {
    return 'Please provide a Zoho organization ID';
  }

  try {
    const customers = await callBookkeepingApi('/api/zoho/customers', {
      user_id: userId,
      organization_id: orgId
    });

    const customerList = customers.customers || [];
    return `Found ${customerList.length} Zoho customer${customerList.length !== 1 ? 's' : ''}`;
  } catch (error: any) {
    return `Error fetching Zoho customers: ${error.message}`;
  }
}

export async function handleCreateZohoCustomer(userId: string, entities: any): Promise<string> {
  const orgId = entities.organization_id || entities.orgId;
  if (!orgId) {
    return 'Please provide a Zoho organization ID';
  }

  try {
    const customerData = {
      display_name: entities.display_name || entities.name,
      email: entities.email,
      phone: entities.phone,
      billing_address: entities.billing_address
    };

    const response = await fetch(`${PYTHON_API_SERVICE_BASE_URL}/api/zoho/customers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        organization_id: orgId,
        customer_data: customerData
      })
    });

    const result = await response.json();
    return `Created Zoho customer: ${result.customer.display_name}`;
  } catch (error: any) {
    return `Error creating Zoho customer: ${error.message}`;
  }
}

export async function handleSendBookkeepingToZoho(userId: string, entities: any): Promise<string> {
  const orgId = entities.organization_id || entities.orgId;
  if (!orgId) {
    return 'Please provide a Zoho organization ID';
  }

  try {
    await callBookkeepingApi('/api/bookkeeping/zoho/sync', {
      user_id: userId,
      organization_id: orgId
    });

    return `Successfully synced bookkeeping data with Zoho Books`;
  } catch (error: any) {
    return `Error syncing with Zoho Books: ${error.message}`;
  }
}
