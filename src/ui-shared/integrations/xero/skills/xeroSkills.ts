/**
 * Xero Integration Skills
 * Frontend service for Xero API interactions
 * Following ATOM patterns for integration services
 */

import { api } from '../../../services/api';

export interface XeroTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  expiresAt: string;
  tenantId: string;
  idToken: string;
  environment: 'production' | 'sandbox';
}

export interface XeroInvoice {
  invoiceID: string;
  invoiceNumber: string;
  type: string;
  contact: {
    contactID: string;
    name: string;
    emailAddress: string;
    phones: Array<{
      phoneNumber: string;
      phoneType: string;
    }>;
  };
  date: string;
  dueDate: string;
  status: string;
  lineAmountTypes: {
    subtotal: number;
    total: number;
    totalTax: number;
  };
  currencyCode: string;
  total: number;
  amountDue: number;
  amountPaid: number;
  url: string;
  hasAttachments: boolean;
  isSent: boolean;
  isPaid: boolean;
  creditNotes: Array<{
    creditNoteID: string;
    creditNoteNumber: string;
    amount: number;
  }>;
  payments: Array<{
    paymentID: string;
    amount: number;
    date: string;
    status: string;
  }>;
  createdDateUTC: string;
  updatedDateUTC: string;
  reference?: string;
  lineItems: Array<{
    lineItemID: string;
    description: string;
    quantity: number;
    unitAmount: number;
    accountCode: string;
    taxType: string;
    taxAmount: number;
    lineAmount: number;
    tracking?: Array<{
      trackingCategoryID: string;
      trackingOptionID: string;
      name: string;
    }>;
  }>;
}

export interface XeroContact {
  contactID: string;
  contactNumber?: string;
  contactStatus: string;
  name: string;
  firstName?: string;
  lastName?: string;
  emailAddress?: string;
  skypeUserName?: string;
  bankAccountDetails?: {
    accountName: string;
    accountNumber: string;
    sortCode: string;
    bankName: string;
  };
  taxNumber?: string;
  accountsReceivableTaxType?: string;
  accountsPayableTaxType?: string;
  phones: Array<{
    phoneNumber: string;
    phoneType: string;
    phoneAreaCode?: string;
    phoneCountryCode?: string;
  }>;
  addresses: Array<{
    addressType: string;
    addressLine1: string;
    addressLine2?: string;
    addressLine3?: string;
    addressLine4?: string;
    city: string;
    region: string;
    postalCode: string;
    country: string;
    attentionTo?: string;
  }>;
  isCustomer: boolean;
  isSupplier: boolean;
  defaultCurrency: string;
  updatedDateUTC: string;
  contactGroups: Array<{
    contactGroupID: string;
    name: string;
    status: string;
  }>;
  website?: string;
  discount?: number;
  xeroNetworkKey?: string;
  salesTrackingCategories: Array<{
    trackingCategoryID: string;
    name: string;
    trackingOptionID: string;
    trackingOptionName: string;
    status: string;
  }>;
  purchasingTrackingCategories?: Array<{
    trackingCategoryID: string;
    name: string;
    trackingOptionID: string;
    trackingOptionName: string;
    status: string;
  }>;
  attachments?: Array<{
    id: string;
    fileName: string;
    url: string;
    mimeType: string;
    fileSize: number;
  }>;
}

export interface XeroBankAccount {
  bankAccountID: string;
  code: string;
  name: string;
  type: string;
  bankAccountNumber: string;
  status: string;
  bankName: string;
  bankBranch: string;
  currencyCode: string;
  bankAccountNumber?: string;
  sortCode?: string;
  accountNumber?: string;
  bsb?: string;
  routingNumber?: string;
  includeInBankFeeds: boolean;
  showInExpenseClaims: boolean;
  displayInBankRegister: boolean;
  enableBankFeeds: boolean;
  bankAccountType: string;
  bankAccountClass: string;
  bankAccountStatus: string;
  url: string;
  numberOfAttachments?: number;
  updatedDateUTC: string;
  lastReconciliationDate?: string;
}

export interface XeroTransaction {
  transactionID: string;
  type: string;
  contact?: {
    contactID: string;
    name: string;
  };
  lineItems: Array<{
    lineItemID: string;
    description: string;
    quantity: number;
    unitAmount: number;
    accountCode: string;
    taxType: string;
    taxAmount: number;
    lineAmount: number;
    tracking?: Array<{
      trackingCategoryID: string;
      trackingOptionID: string;
      name: string;
    }>;
  }>;
  date: string;
  status: string;
  lineAmountTypes: {
    subtotal: number;
    total: number;
    totalTax: number;
  };
  currencyCode: string;
  currencyRate: number;
  total: number;
  url: string;
  reference?: string;
  hasAttachments: boolean;
  createdDateUTC: string;
  updatedDateUTC: string;
  bankTransaction?: {
    bankTransactionID: string;
    amount: number;
    date: string;
    status: string;
    reference: string;
    details: string;
  };
  sourceTransactionID?: string;
  sourceSystem?: string;
  sourceTransactionType?: string;
  reconciliationStatus?: string;
}

export interface XeroFinancialReport {
  reportID: string;
  reportName: string;
  reportTitles: Array<{
    title: string;
  }>;
  reportDate: string;
  rows: Array<{
    rowType: string;
    title?: string;
    cells: Array<{
      value: string;
    }>;
  }>;
  columns: Array<{
    columnName: string;
  }>;
  summary: Array<{
    columnName: string;
    value: string;
  }>;
  updatedDateUTC: string;
}

export interface XeroAccount {
  accountID: string;
  code: string;
  name: string;
  type: string;
  bankAccountNumber: string;
  status: string;
  description: string;
  taxType: string;
  enablePaymentsToAccount: boolean;
  showInExpenseClaims: boolean;
  class: string;
  systemAccount: boolean;
  reportingCode: string;
  reportingCodeName: string;
  hasAttachments: boolean;
  updatedDateUTC: string;
  currencyCode: string;
  currentBalance?: number;
}

export interface XeroPayment {
  paymentID: string;
  invoice: {
    invoiceID: string;
    invoiceNumber: string;
    type: string;
    contact: {
      contactID: string;
      name: string;
    };
  };
  account: {
    accountID: string;
    code: string;
    name: string;
    type: string;
  };
  date: string;
  amount: number;
  reference: string;
  status: string;
  isReconciled: boolean;
  hasAttachments: boolean;
  updatedDateUTC: string;
  currencyRate: number;
  currencyCode: string;
  bankTransactionID?: string;
}

export interface XeroTaxRate {
  taxType: string;
  name: string;
  taxComponent?: string;
  rate?: number;
  status: string;
  reportTaxType?: string;
  canApplyToExpenses?: boolean;
  canApplyToRevenue?: boolean;
  displayTaxRate?: number;
  effectiveRate?: number;
}

export interface XeroTrackingCategory {
  trackingCategoryID: string;
  name: string;
  status: string;
  class: string;
  options: Array<{
    trackingOptionID: string;
    name: string;
    status: string;
  }>;
}

export interface XeroCreateOptions {
  properties?: { [key: string]: any };
  attachments?: Array<{
    fileName: string;
    content: string;
    contentType?: string;
  }>;
}

export interface XeroSearchOptions {
  query?: string;
  type?: 'invoice' | 'contact' | 'transaction' | 'account';
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  status?: string;
  contact_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface XeroListOptions {
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  status?: string;
  where?: string;
}

class XeroSkills {
  private readonly baseUrl = '/api/integrations/xero';
  private readonly authUrl = '/auth/xero';

  // Authentication methods
  async getStoredTokens(): Promise<XeroTokens | null> {
    try {
      const response = await api.get(`${this.authUrl}/status`);
      if (response.data.authenticated) {
        return response.data.tokens;
      }
      return null;
    } catch (error) {
      console.error('Failed to get stored tokens:', error);
      return null;
    }
  }

  async initiateOAuth(): Promise<void> {
    try {
      window.location.href = `${this.authUrl}`;
    } catch (error) {
      throw new Error(`Failed to initiate OAuth: ${error.message}`);
    }
  }

  async handleOAuthCallback(code: string, state: string): Promise<XeroTokens> {
    try {
      const response = await api.post(`${this.authUrl}/save`, { code, state });
      return response.data.tokens;
    } catch (error) {
      throw new Error(`OAuth callback failed: ${error.message}`);
    }
  }

  async revokeAuthentication(): Promise<void> {
    try {
      await api.delete(`${this.authUrl}`);
    } catch (error) {
      throw new Error(`Failed to revoke authentication: ${error.message}`);
    }
  }

  // Invoice methods
  async getInvoices(options: XeroListOptions = {}): Promise<{
    invoices: XeroInvoice[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.status) params.append('status', options.status);
      if (options.where) params.append('where', options.where);

      const response = await api.get(`${this.baseUrl}/invoices?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get invoices: ${error.message}`);
    }
  }

  async getInvoice(invoiceId: string): Promise<XeroInvoice> {
    try {
      const response = await api.get(`${this.baseUrl}/invoices/${invoiceId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get invoice: ${error.message}`);
    }
  }

  async createInvoice(invoiceData: XeroCreateOptions & {
    type: 'ACCREC' | 'ACCPAY';
    contactID: string;
    date: string;
    dueDate: string;
    lineItems: Array<{
      description: string;
      quantity: number;
      unitAmount: number;
      accountCode: string;
      taxType: string;
    }>;
    reference?: string;
    currencyCode?: string;
    status?: string;
  }): Promise<XeroInvoice> {
    try {
      const response = await api.post(`${this.baseUrl}/invoices`, invoiceData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create invoice: ${error.message}`);
    }
  }

  async updateInvoice(invoiceId: string, updateData: Partial<XeroInvoice>): Promise<XeroInvoice> {
    try {
      const response = await api.put(`${this.baseUrl}/invoices/${invoiceId}`, updateData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update invoice: ${error.message}`);
    }
  }

  async deleteInvoice(invoiceId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/invoices/${invoiceId}`);
    } catch (error) {
      throw new Error(`Failed to delete invoice: ${error.message}`);
    }
  }

  async sendInvoice(invoiceId: string): Promise<{ message: string; status: string }> {
    try {
      const response = await api.post(`${this.baseUrl}/invoices/${invoiceId}/send`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to send invoice: ${error.message}`);
    }
  }

  async voidInvoice(invoiceId: string, reason?: string): Promise<{ message: string; status: string }> {
    try {
      const response = await api.post(`${this.baseUrl}/invoices/${invoiceId}/void`, { reason });
      return response.data;
    } catch (error) {
      throw new Error(`Failed to void invoice: ${error.message}`);
    }
  }

  // Contact methods
  async getContacts(options: XeroListOptions = {}): Promise<{
    contacts: XeroContact[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.where) params.append('where', options.where);

      const response = await api.get(`${this.baseUrl}/contacts?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contacts: ${error.message}`);
    }
  }

  async getContact(contactId: string): Promise<XeroContact> {
    try {
      const response = await api.get(`${this.baseUrl}/contacts/${contactId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get contact: ${error.message}`);
    }
  }

  async createContact(contactData: XeroCreateOptions & {
    name: string;
    firstName?: string;
    lastName?: string;
    emailAddress?: string;
    isCustomer?: boolean;
    isSupplier?: boolean;
    defaultCurrency?: string;
    phones?: Array<{
      phoneNumber: string;
      phoneType: string;
    }>;
    addresses?: Array<{
      addressType: string;
      addressLine1: string;
      city: string;
      region: string;
      postalCode: string;
      country: string;
    }>;
    taxNumber?: string;
    website?: string;
  }): Promise<XeroContact> {
    try {
      const response = await api.post(`${this.baseUrl}/contacts`, contactData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create contact: ${error.message}`);
    }
  }

  async updateContact(contactId: string, updateData: Partial<XeroContact>): Promise<XeroContact> {
    try {
      const response = await api.put(`${this.baseUrl}/contacts/${contactId}`, updateData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update contact: ${error.message}`);
    }
  }

  async deleteContact(contactId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/contacts/${contactId}`);
    } catch (error) {
      throw new Error(`Failed to delete contact: ${error.message}`);
    }
  }

  // Bank Account methods
  async getBankAccounts(): Promise<{
    bankAccounts: XeroBankAccount[];
    count: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/bank-accounts`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get bank accounts: ${error.message}`);
    }
  }

  async getBankAccount(bankAccountId: string): Promise<XeroBankAccount> {
    try {
      const response = await api.get(`${this.baseUrl}/bank-accounts/${bankAccountId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get bank account: ${error.message}`);
    }
  }

  // Bank Transaction methods
  async getBankTransactions(options: XeroListOptions = {}): Promise<{
    transactions: XeroTransaction[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.status) params.append('status', options.status);
      if (options.where) params.append('where', options.where);

      const response = await api.get(`${this.baseUrl}/bank-transactions?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get bank transactions: ${error.message}`);
    }
  }

  async getBankTransaction(transactionId: string): Promise<XeroTransaction> {
    try {
      const response = await api.get(`${this.baseUrl}/bank-transactions/${transactionId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get bank transaction: ${error.message}`);
    }
  }

  async createBankTransaction(transactionData: XeroCreateOptions & {
    type: 'SPEND' | 'RECEIVE' | 'TRANSFER';
    contactID?: string;
    bankAccountID: string;
    date: string;
    lineItems: Array<{
      description: string;
      quantity: number;
      unitAmount: number;
      accountCode: string;
      taxType: string;
    }>;
    reference?: string;
    currencyCode?: string;
  }): Promise<XeroTransaction> {
    try {
      const response = await api.post(`${this.baseUrl}/bank-transactions`, transactionData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create bank transaction: ${error.message}`);
    }
  }

  async updateBankTransaction(transactionId: string, updateData: Partial<XeroTransaction>): Promise<XeroTransaction> {
    try {
      const response = await api.put(`${this.baseUrl}/bank-transactions/${transactionId}`, updateData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to update bank transaction: ${error.message}`);
    }
  }

  async deleteBankTransaction(transactionId: string): Promise<void> {
    try {
      await api.delete(`${this.baseUrl}/bank-transactions/${transactionId}`);
    } catch (error) {
      throw new Error(`Failed to delete bank transaction: ${error.message}`);
    }
  }

  // Payment methods
  async getPayments(options: XeroListOptions = {}): Promise<{
    payments: XeroPayment[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.where) params.append('where', options.where);

      const response = await api.get(`${this.baseUrl}/payments?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get payments: ${error.message}`);
    }
  }

  async createPayment(paymentData: XeroCreateOptions & {
    invoiceID: string;
    accountID: string;
    date: string;
    amount: number;
    reference?: string;
    currencyCode?: string;
  }): Promise<XeroPayment> {
    try {
      const response = await api.post(`${this.baseUrl}/payments`, paymentData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create payment: ${error.message}`);
    }
  }

  // Account methods
  async getAccounts(options: XeroListOptions = {}): Promise<{
    accounts: XeroAccount[];
    count: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.where) params.append('where', options.where);

      const response = await api.get(`${this.baseUrl}/accounts?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get accounts: ${error.message}`);
    }
  }

  // Tax Rate methods
  async getTaxRates(): Promise<{
    taxRates: XeroTaxRate[];
    count: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tax-rates`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get tax rates: ${error.message}`);
    }
  }

  // Tracking Category methods
  async getTrackingCategories(): Promise<{
    trackingCategories: XeroTrackingCategory[];
    count: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tracking-categories`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get tracking categories: ${error.message}`);
    }
  }

  // Financial Reports methods
  async getFinancialReports(): Promise<{
    reports: Array<{
      reportID: string;
      reportName: string;
      reportType: string;
      updatedDateUTC: string;
    }>;
    count: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/reports`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get financial reports: ${error.message}`);
    }
  }

  async getFinancialReport(reportId: string, options: {
    date?: string;
    period?: string;
    trackingCategoryID?: string;
    trackingOptionID?: string;
    standardLayout?: boolean;
    paymentsOnly?: boolean;
  } = {}): Promise<XeroFinancialReport> {
    try {
      const params = new URLSearchParams();
      if (options.date) params.append('date', options.date);
      if (options.period) params.append('period', options.period);
      if (options.trackingCategoryID) params.append('trackingCategoryID', options.trackingCategoryID);
      if (options.trackingOptionID) params.append('trackingOptionID', options.trackingOptionID);
      if (options.standardLayout !== undefined) params.append('standardLayout', options.standardLayout.toString());
      if (options.paymentsOnly !== undefined) params.append('paymentsOnly', options.paymentsOnly.toString());

      const response = await api.get(`${this.baseUrl}/reports/${reportId}?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get financial report: ${error.message}`);
    }
  }

  // Search methods
  async searchContacts(options: XeroSearchOptions): Promise<{
    contacts: XeroContact[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.query) params.append('query', options.query);
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);

      const response = await api.get(`${this.baseUrl}/contacts/search?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search contacts: ${error.message}`);
    }
  }

  async searchInvoices(options: XeroSearchOptions): Promise<{
    invoices: XeroInvoice[];
    count: number;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      if (options.query) params.append('query', options.query);
      if (options.page) params.append('page', options.page.toString());
      if (options.per_page) params.append('per_page', options.per_page.toString());
      if (options.sort_by) params.append('sort_by', options.sort_by);
      if (options.sort_order) params.append('sort_order', options.sort_order);
      if (options.status) params.append('status', options.status);
      if (options.contact_id) params.append('contact_id', options.contact_id);
      if (options.date_from) params.append('date_from', options.date_from);
      if (options.date_to) params.append('date_to', options.date_to);

      const response = await api.get(`${this.baseUrl}/invoices/search?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to search invoices: ${error.message}`);
    }
  }

  // Utility methods
  getStatusColor(status: string): string {
    const colors: { [key: string]: string } = {
      'DRAFT': 'gray',
      'SUBMITTED': 'blue',
      'AUTHORISED': 'purple',
      'PAID': 'green',
      'PARTIALLYPAID': 'yellow',
      'VOIDED': 'red',
      'DELETED': 'red'
    };
    return colors[status?.toUpperCase()] || 'gray';
  }

  getTransactionTypeColor(type: string): string {
    const colors: { [key: string]: string } = {
      'SPEND': 'red',
      'RECEIVE': 'green',
      'TRANSFER': 'blue'
    };
    return colors[type?.toUpperCase()] || 'gray';
  }

  getBankAccountTypeColor(type: string): string {
    const colors: { [key: string]: string } = {
      'BANK': 'blue',
      'CREDITCARD': 'purple',
      'PAYPAL': 'orange'
    };
    return colors[type?.toUpperCase()] || 'gray';
  }

  formatDate(dateString: string): string {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString();
  }

  formatCurrency(amount: number, currency: string = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  }

  getRelativeTime(dateString: string): string {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
    return `${Math.floor(days / 30)} months ago`;
  }

  validateInvoice(invoice: Partial<XeroInvoice>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!invoice.contactID) {
      errors.push('Contact is required');
    }
    
    if (!invoice.date) {
      errors.push('Invoice date is required');
    }
    
    if (!invoice.dueDate) {
      errors.push('Due date is required');
    }
    
    if (!invoice.lineItems || invoice.lineItems.length === 0) {
      errors.push('At least one line item is required');
    }
    
    if (invoice.lineItems) {
      invoice.lineItems.forEach((item, index) => {
        if (!item.description) {
          errors.push(`Line item ${index + 1} description is required`);
        }
        if (!item.accountCode) {
          errors.push(`Line item ${index + 1} account code is required`);
        }
        if (item.quantity <= 0) {
          errors.push(`Line item ${index + 1} quantity must be greater than 0`);
        }
        if (item.unitAmount < 0) {
          errors.push(`Line item ${index + 1} unit amount must be non-negative`);
        }
      });
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateContact(contact: Partial<XeroContact>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!contact.name || contact.name.trim().length === 0) {
      errors.push('Name is required');
    }
    
    if (contact.emailAddress && !this.isValidEmail(contact.emailAddress)) {
      errors.push('Invalid email address');
    }
    
    if (!contact.isCustomer && !contact.isSupplier) {
      errors.push('Contact must be either a customer or supplier');
    }
    
    if (!contact.defaultCurrency) {
      errors.push('Default currency is required');
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateTransaction(transaction: Partial<XeroTransaction>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    if (!transaction.type) {
      errors.push('Transaction type is required');
    }
    
    if (!transaction.bankAccountID) {
      errors.push('Bank account is required');
    }
    
    if (!transaction.date) {
      errors.push('Transaction date is required');
    }
    
    if (!transaction.lineItems || transaction.lineItems.length === 0) {
      errors.push('At least one line item is required');
    }
    
    if (transaction.lineItems) {
      transaction.lineItems.forEach((item, index) => {
        if (!item.description) {
          errors.push(`Line item ${index + 1} description is required`);
        }
        if (!item.accountCode) {
          errors.push(`Line item ${index + 1} account code is required`);
        }
        if (item.quantity <= 0) {
          errors.push(`Line item ${index + 1} quantity must be greater than 0`);
        }
      });
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  // Health check
  async getHealthStatus(): Promise<{
    status: 'healthy' | 'unhealthy';
    authenticated: boolean;
    lastSync?: string;
    message?: string;
    version: string;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/health`);
      return response.data;
    } catch (error) {
      return {
        status: 'unhealthy',
        authenticated: false,
        message: error.message,
        version: 'unknown'
      };
    }
  }
}

// Export singleton instance
export const xeroSkills = new XeroSkills();
export default xeroSkills;