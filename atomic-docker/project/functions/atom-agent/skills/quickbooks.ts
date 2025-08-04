import {
  ListQuickBooksInvoicesResponse,
  GetQuickBooksInvoiceDetailsResponse,
} from '../../types';
import {
  getAuthUri,
  listQuickBooksInvoices as listInvoices,
  getQuickBooksInvoiceDetails as getInvoiceDetails,
} from './quickbooksSkills';
import { ATOM_QB_TOKEN_FILE_PATH } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';

export async function handleGetQuickBooksAuthUrl(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const authUri = getAuthUri();
    if (authUri) {
      return `To authorize QuickBooks Online (via NLU), please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
    } else {
      return 'Could not generate QuickBooks authorization URL (via NLU). Please check server configuration.';
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).'
    );
  }
}

export async function handleListQuickBooksInvoices(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const {
      customer_id,
      status,
      limit: nluLimit,
      offset: nluOffset,
    } = entities;
    const options: {
      limit?: number;
      offset?: number;
      customerId?: string;
      status?: string;
    } = {};
    if (nluLimit) {
      if (typeof nluLimit === 'number') options.limit = nluLimit;
      else if (typeof nluLimit === 'string') {
        const parsed = parseInt(nluLimit, 10);
        if (!isNaN(parsed)) options.limit = parsed;
      }
    }
    if (nluOffset) {
      if (typeof nluOffset === 'number') options.offset = nluOffset;
      else if (typeof nluOffset === 'string') {
        const parsed = parseInt(nluOffset, 10);
        if (!isNaN(parsed)) options.offset = parsed;
      }
    }
    if (customer_id && typeof customer_id === 'string')
      options.customerId = customer_id;
    if (status && typeof status === 'string')
      console.log(
        `[handleListQuickBooksInvoices] NLU: received status filter: ${status}. Currently illustrative, skill may not filter by it.`
      );
    const response: ListQuickBooksInvoicesResponse =
      await listInvoices(options);
    if (response.ok && response.invoices && response.invoices.length > 0) {
      let output = 'QuickBooks Invoices (via NLU):\n';
      for (const inv of response.invoices) {
        output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\n`;
      }
      if (response.queryResponse)
        output += `Showing results. Max per page: ${response.queryResponse.maxResults || options.limit}\n`;
      return output;
    } else if (response.ok) {
      return 'No QuickBooks invoices found via NLU matching your criteria.';
    } else {
      return `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}. Ensure QuickBooks is connected and authorized.`;
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an error occurred while fetching QuickBooks invoices via NLU.'
    );
  }
}

export async function handleGetQuickBooksInvoiceDetails(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const { invoice_id } = entities;
    if (!invoice_id || typeof invoice_id !== 'string') {
      return 'Invoice ID is required to get QuickBooks invoice details via NLU.';
    } else {
      const response: GetQuickBooksInvoiceDetailsResponse =
        await getInvoiceDetails(invoice_id);
      if (response.ok && response.invoice) {
        const inv = response.invoice;
        return `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\nBalance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}`;
      } else {
        return `Error fetching QuickBooks invoice details via NLU: ${response.error || 'Invoice not found or error occurred.'}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an error occurred while fetching QuickBooks invoice details via NLU.'
    );
  }
}
