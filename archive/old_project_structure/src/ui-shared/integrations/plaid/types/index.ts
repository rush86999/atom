/**
 * ATOM Plaid Integration Types
 * Financial Services → ATOM Ingestion Pipeline
 * Plaid API Integration for Banking and Payment Automation
 */

export interface PlaidAccount {
  account_id: string;
  balances: {
    current: number;
    available: number;
    limit: number | null;
  };
  mask: string;
  name: string;
  official_name: string | null;
  subtype: string[];
  type: string;
  verification_status: string | null;
}

export interface PlaidAccountBalance {
  account_id: string;
  balances: {
    available: number;
    current: number;
    iso_currency_code: string;
    limit: number | null;
    unofficial_currency_code: string | null;
  };
}

export interface PlaidTransaction {
  transaction_id: string;
  pending: boolean;
  amount: number;
  iso_currency_code: string;
  unofficial_currency_code: string | null;
  category: string[];
  category_id: string;
  date: string;
  authorized_date: string | null;
  location: {
    address: string | null;
    city: string | null;
    region: string | null;
    postal_code: string | null;
    country: string | null;
    lat: number | null;
    lon: number | null;
    store_number: string | null;
  };
  name: string;
  merchant_name: string | null;
  payment_channel: string;
  payment_meta: {
    by_order_of: string | null;
    payee: string | null;
    payer: string | null;
    payment_method: string | null;
    payment_processor: string | null;
    ppd_id: string | null;
    reason: string | null;
    reference_number: string | null;
  };
  account_id: string;
  account_owner: string | null;
  logo_url: string | null;
  website: string | null;
}

export interface PlaidInvestmentTransaction {
  investment_transaction_id: string;
  security_id: string | null;
  cusip: string | null;
  name: string;
  quantity: number | null;
  cancel_transaction_id: string | null;
  fees: number | null;
  price: number | null;
  type: string;
  subtype: string | null;
  iso_currency_code: string | null;
  unofficial_currency_code: string | null;
  date: string;
  investment_transaction_id?: string;
}

export interface PlaidHolding {
  security_id: string;
  account_id: string;
  cost_basis: number | null;
  institution_price: number | null;
  institution_price_as_of: string | null;
  institution_price_datetime: string | null;
  quantity: number;
  iso_currency_code: string;
  unofficial_currency_code: string | null;
}

export interface PlaidSecurity {
  security_id: string;
  proxy_security_id: string | null;
  cusip: string | null;
  sedol: string | null;
  isin: string | null;
  institution_id: string | null;
  institution_security_id: string | null;
  ticker_symbol: string | null;
  name: string;
  is_cash: boolean;
  type: string;
  close_price: number | null;
  close_price_as_of: string | null;
  iso_currency_code: string;
  unofficial_currency_code: string | null;
}

export interface PlaidItem {
  item_id: string;
  institution_id: string;
  webhook: string;
  error: any | null;
  available_products: string[];
  billed_products: string[];
  request_id: string;
  consent_expiration_time: string | null;
}

export interface PlaidInstitution {
  institution_id: string;
  name: string;
  products: string[];
  country_codes: string[];
  url: string;
  logo: string;
  primary_color: string;
}

export interface PlaidIncomeVerification {
  income_source_id: string;
  flow_type: string;
  origination_account_id: string;
  access_token: string | null;
  user_id: string | null;
  account_ids: string[];
  bank_income: {
    end_date: string;
    start_date: string;
    annual_income: number;
    monthly_income: number;
    currency: string;
    confidence_type: string;
    stated_income: number;
    pay_frequency: string;
    projected_yearly_income: number;
    max_seen_account_balance: number;
    min_seen_account_balance: number;
  }[];
  historical_income: Array<{
    month: string;
    amount: number;
  }>;
  documents: Array<{
    document_id: string;
    document_type: string;
    created_at: string;
    status: string;
    error: any;
  }>;
}

export interface PlaidCreditCardLiability {
  account_id: string;
  last_payment_amount: number | null;
  last_payment_date: string | null;
  minimum_payment_amount: number | null;
  next_payment_due_date: string | null;
  aprs: Array<{
    apr_percentage: number;
    apr_type: string;
    balance_subject_to_apr: number | null;
    interest_charge_amount: number | null;
  }>;
  is_overdue: boolean;
}

export interface PlaidStudentLoanLiability {
  account_id: string;
  last_payment_amount: number | null;
  last_payment_date: string | null;
  next_payment_due_date: string | null;
  origination_date: string | null;
  disbursement_dates: string[];
  expected_payoff_date: string;
  guarantor: string;
  interest_rate_percentage: number;
  minimum_payment_amount: number | null;
  repayment_type: string;
  series_id: string;
  loan_name: string;
  loan_status: string;
  pslf_status: string | null;
  ytd_interest_paid: number;
  ytd_principal_paid: number;
}

export interface PlaidMortgageLiability {
  account_id: string;
  last_payment_amount: number | null;
  last_payment_date: string | null;
  next_payment_due_date: string | null;
  origination_date: string;
  origination_principal_amount: number;
  current_principal_amount: number;
  interest_rate_percentage: number;
  escrow_balance: number | null;
  has_pmi: boolean;
  has_prepayment_penalty: boolean;
  loan_term: string;
  months_to_maturity: number | null;
  next_monthly_payment: number | null;
  property_address: {
    city: string;
    country: string;
    postal_code: string;
    region: string;
    street: string | null;
  };
}

// ATOM Integration Types
export interface AtomPlaidDataSourceProps {
  // Plaid Authentication
  accessToken: string;
  itemId: string;
  onTokenRefresh?: (newToken: string) => void;
  
  // Existing ATOM Pipeline Integration
  atomIngestionPipeline?: any;
  dataSourceRegistry?: any;
  
  // Data Source Configuration
  config?: AtomPlaidIngestionConfig;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  
  // Events
  onDataSourceReady?: (dataSource: any) => void;
  onIngestionStart?: (config: any) => void;
  onIngestionComplete?: (results: any) => void;
  onIngestionProgress?: (progress: any) => void;
  onDataSourceError?: (error: any) => void;
  onAccountProcessed?: (account: PlaidAccount) => void;
  onTransactionProcessed?: (transaction: PlaidTransaction) => void;
  
  // Children
  children?: React.ReactNode;
}

export interface AtomPlaidDataSourceState {
  initialized: boolean;
  connected: boolean;
  loading: boolean;
  error: string | null;
  
  // Plaid State
  item: PlaidItem | null;
  institution: PlaidInstitution | null;
  accounts: PlaidAccount[];
  transactions: PlaidTransaction[];
  balances: PlaidAccountBalance[];
  holdings: PlaidHolding[];
  securities: PlaidSecurity[];
  
  // Income & Liabilities
  incomeVerification: PlaidIncomeVerification | null;
  creditCardLiabilities: PlaidCreditCardLiability[];
  studentLoanLiabilities: PlaidStudentLoanLiability[];
  mortgageLiabilities: PlaidMortgageLiability[];
  
  // Ingestion State
  ingestionActive: boolean;
  ingestionProgress: {
    total: number;
    processed: number;
    percentage: number;
    currentAccount?: string;
  };
  ingestionResults: any[];
  
  // Sync State
  lastSync: string | null;
  syncActive: boolean;
}

export interface AtomPlaidIngestionConfig {
  // Account Filtering
  accountTypes?: string[];
  excludeAccountTypes?: string[];
  includeInactiveAccounts?: boolean;
  
  // Transaction Configuration
  transactionStartDate?: string;
  includePendingTransactions?: boolean;
  transactionCategories?: string[];
  excludeTransactionCategories?: string[];
  
  // Income Verification
  enableIncomeVerification?: boolean;
  incomeVerificationTypes?: string[];
  
  // Investment Data
  includeInvestmentHoldings?: boolean;
  includeInvestmentTransactions?: boolean;
  
  // Liability Data
  includeCreditCardLiabilities?: boolean;
  includeStudentLoanLiabilities?: boolean;
  includeMortgageLiabilities?: boolean;
  
  // Sync Configuration
  enableRealTimeSync?: boolean;
  syncInterval?: number;
  webhookUrl?: string;
  
  // Processing Configuration
  extractTransactionMetadata?: boolean;
  generateSpendingInsights?: boolean;
  categorizeTransactions?: boolean;
  
  // Batch Processing
  batchSize?: number;
  concurrentProcessing?: boolean;
  maxConcurrency?: number;
  
  // Advanced Configuration
  includeHistoricalData?: boolean;
  historicalDataDays?: number;
  retryFailedOperations?: boolean;
  maxRetries?: number;
  
  // Notifications
  enableNotifications?: boolean;
  notificationChannels?: string[];
  
  // Privacy & Security
  encryptSensitiveData?: boolean;
  maskAccountNumbers?: boolean;
  anonymizeTransactions?: boolean;
}

// Enhanced Types with ATOM Integration
export interface PlaidAccountEnhanced extends PlaidAccount {
  // ATOM Enhanced Metadata
  atomId: string;
  atomTimestamp: string;
  atomSource: 'plaid';
  atomProcessed: boolean;
  atomIngestionId?: string;
  
  // Processing Results
  accountTypeClassification: string;
  riskAssessment: {
    score: number;
    level: 'low' | 'medium' | 'high';
    factors: string[];
  };
  spendingAnalysis?: {
    avgMonthlySpending: number;
    avgMonthlyIncome: number;
    netMonthly: number;
  };
  
  // Integration Data
  syncedWithAtom: boolean;
  lastSynced?: string;
  atomMetadata?: any;
}

export interface PlaidTransactionEnhanced extends PlaidTransaction {
  // ATOM Enhanced Metadata
  atomId: string;
  atomTimestamp: string;
  atomSource: 'plaid';
  atomProcessed: boolean;
  atomIngestionId?: string;
  
  // Processing Results
  enhancedCategory: string;
  subcategory: string;
  merchantClassification: {
    type: string;
    category: string;
    confidence: number;
  };
  spendingInsight: {
    type: 'recurring' | 'one-time' | 'subscription' | 'large_purchase';
    frequency?: string;
    amount_vs_average?: number;
    budget_impact?: 'low' | 'medium' | 'high';
  };
  
  // Location Analysis
  locationAnalysis?: {
    is_recurring_location: boolean;
    distance_from_usual?: number;
    location_risk_score: number;
  };
  
  // Integration Data
  syncedWithAtom: boolean;
  lastSynced?: string;
  atomMetadata?: any;
}

// API Response Types
export interface PlaidAPIResponse<T = any> {
  request_id: string;
  data: T;
}

export interface PlaidCreatePublicTokenResponse {
  public_token: string;
  expiration: string;
  request_id: string;
}

export interface PlaidExchangePublicTokenResponse {
  access_token: string;
  item_id: string;
  request_id: string;
}

export interface PlaidItemWebhook {
  webhook_type: string;
  webhook_code: string;
  item_id: string;
  error: any | null;
  new_transactions: {
    from_date: string;
    to_date: string;
  } | null;
  updated_transactions: {
    from_date: string;
    to_date: string;
  } | null;
  removed_transactions: {
    from_date: string;
    to_date: string;
  } | null;
}

// Error Types
export interface PlaidError {
  error_code: string;
  error_message: string;
  error_type: string;
  display_message?: string;
  request_id?: string;
  causes?: Array<{
    error_code: string;
    error_message: string;
    error_type: string;
  }>;
  status: number;
  documentation_url?: string;
  suggested_action?: string;
}

// Search and Filter Types
export interface PlaidTransactionSearch {
  query?: string;
  account_ids?: string[];
  categories?: string[];
  date_range?: {
    from: string;
    to: string;
  };
  amount_range?: {
    min: number;
    max: number;
  };
  merchants?: string[];
  pending_only?: boolean;
  limit?: number;
  offset?: number;
}

// Analytics Types
export interface PlaidSpendingAnalytics {
  total_spending: number;
  total_income: number;
  net_amount: number;
  spending_by_category: Array<{
    category: string;
    amount: number;
    percentage: number;
    transaction_count: number;
  }>;
  income_by_source: Array<{
    source: string;
    amount: number;
    percentage: number;
  }>;
  monthly_trends: Array<{
    month: string;
    income: number;
    spending: number;
    net: number;
  }>;
  top_merchants: Array<{
    merchant_name: string;
    amount: number;
    transaction_count: number;
  }>;
  recurring_transactions: Array<{
    name: string;
    amount: number;
    frequency: string;
    next_expected: string;
  }>;
}

export interface PlaidAccountSummary {
  total_balance: number;
  available_balance: number;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  accounts: Array<{
    id: string;
    name: string;
    type: string;
    balance: number;
    available_balance: number;
  }>;
}

// Constants
export const PLAID_DEFAULT_CONFIG: AtomPlaidIngestionConfig = {
  accountTypes: [
    'depository',
    'credit',
    'loan',
    'investment',
    'brokerage'
  ],
  excludeAccountTypes: [
    'other'
  ],
  includeInactiveAccounts: false,
  transactionStartDate: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 90 days ago
  includePendingTransactions: true,
  enableIncomeVerification: false,
  includeInvestmentHoldings: true,
  includeInvestmentTransactions: true,
  includeCreditCardLiabilities: true,
  includeStudentLoanLiabilities: true,
  includeMortgageLiabilities: true,
  enableRealTimeSync: true,
  syncInterval: 24 * 60 * 60 * 1000, // 24 hours
  extractTransactionMetadata: true,
  generateSpendingInsights: true,
  categorizeTransactions: true,
  batchSize: 100,
  concurrentProcessing: true,
  maxConcurrency: 5,
  includeHistoricalData: true,
  historicalDataDays: 365, // 1 year
  retryFailedOperations: true,
  maxRetries: 3,
  enableNotifications: true,
  encryptSensitiveData: true,
  maskAccountNumbers: true,
  anonymizeTransactions: false,
};

export const PLAID_SUPPORTED_PRODUCTS = [
  'auth',
  'transactions',
  'identity',
  'income',
  'assets',
  'investments',
  'liabilities',
  'payment_initiation',
  'transfer',
  'deposit_switch',
  'employment',
  'benefits',
  'recurring_transactions',
  'standalone_recurring_transactions',
];

export const PLAID_TRANSACTION_CATEGORIES = [
  'TRANSFER',
  'TRAVEL',
  'FOOD_AND_DRINK',
  'RECREATION',
  'SHOPS',
  'PERSONAL',
  'HOME',
  'PAYMENTS',
  'BANK_FEES',
  'SERVICE',
  'INCOME',
];

export const PLAID_ACCOUNT_TYPES = [
  'depository',
  'credit',
  'loan',
  'investment',
  'brokerage',
  'other',
];

export const PLAID_WEBHOOK_TYPES = [
  'ITEM',
  'TRANSACTIONS',
  'AUTH',
  'INCOME',
  'ASSETS',
  'INVESTMENTS_TRANSACTIONS',
  'LIABILITIES',
  'TRANSFER',
  'PAYMENT_INITIATION',
  'BENEFITS',
  'RECURRING_TRANSACTIONS',
];

export const PLAID_ERROR_CODES = {
  // Item errors
  'INVALID_CREDENTIALS': 'Invalid credentials for financial institution',
  'ITEM_LOGIN_REQUIRED': 'Item requires login to financial institution',
  'INSUFFICIENT_CREDENTIALS': 'MFA or other additional credentials required',
  'ITEM_LOCKED': 'Item locked at financial institution',
  'USER_SETUP_REQUIRED': 'User action required at financial institution',
  
  // Transaction errors
  'TRANSACTIONS_NOT_AVAILABLE': 'Transactions not available for this institution',
  'NO_ACCOUNTS': 'No accounts found for this item',
  
  // API errors
  'INVALID_REQUEST': 'Invalid request format or parameters',
  'INVALID_ACCESS_TOKEN': 'Invalid access token',
  'INVALID_PUBLIC_TOKEN': 'Invalid public token',
  'INTERNAL_SERVER_ERROR': 'Plaid internal server error',
  'PLAID_MAINTENANCE': 'Plaid is undergoing maintenance',
  
  // Rate limiting
  'RATE_LIMIT_EXCEEDED': 'Rate limit exceeded',
  
  // Access errors
  'PRODUCTS_NOT_SUPPORTED': 'Requested products not supported by institution',
  'TEMPORARY_UNAVAILABLE': 'Temporary service unavailability',
};