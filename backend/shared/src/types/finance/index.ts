export interface FinanceTransaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: string;
  status: 'completed' | 'pending' | 'failed' | 'cancelled';
  account: string;
  metadata?: Record<string, any>;
  receipt?: string;
  vendor?: string;
  tags?: string[];
  notes?: string;
  attachments?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface FinanceInvoice {
  id: string;
  number: string;
  customer: {
    id: string;
    name: string;
    email: string;
    phone?: string;
    address?: string;
  };
  items: InvoiceItem[];
  subtotal: number;
  tax: number;
  total: number;
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
  dueDate: string;
  sentDate?: string;
  paidDate?: string;
  notes?: string;
  attachments?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: number;
  unitPrice: number;
  total: number;
  tax?: number;
  category?: string;
}

export interface FinanceExpense {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: string;
  vendor: {
    id: string;
    name: string;
    email?: string;
    phone?: string;
  };
  status: 'draft' | 'submitted' | 'approved' | 'rejected' | 'reimbursed';
  receipt?: string;
  tags?: string[];
  notes?: string;
  attachments?: string[];
  submittedBy?: string;
  approvedBy?: string;
  approvedAt?: string;
  reimbursedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceAccount {
  id: string;
  name: string;
  type: 'checking' | 'savings' | 'credit_card' | 'investment' | 'loan';
  balance: number;
  currency: string;
  bankName?: string;
  accountNumber?: string;
  routingNumber?: string;
  status: 'active' | 'inactive' | 'closed';
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceBudget {
  id: string;
  name: string;
  category: string;
  budgeted: number;
  spent: number;
  remaining: number;
  percentage: number;
  period: string;
  startDate: string;
  endDate: string;
  status: 'active' | 'completed' | 'cancelled';
  alertThreshold?: number;
  alertsEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceReport {
  id: string;
  title: string;
  type: 'profit_loss' | 'cash_flow' | 'balance_sheet' | 'expenses' | 'revenue' | 'budget';
  period: string;
  startDate: string;
  endDate: string;
  data: Record<string, any>;
  format: 'pdf' | 'excel' | 'csv';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  generatedAt?: string;
  downloadUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceDashboardData {
  totalRevenue: number;
  totalExpenses: number;
  netProfit: number;
  cashFlow: number;
  revenueChange: number;
  expensesChange: number;
  profitChange: number;
  cashFlowChange: number;
  revenueTrend: Array<{ x: number; y: number }>;
  categoryBreakdown: {
    revenue: number;
    expenses: number;
    investments: number;
    other: number;
  };
  recentTransactions: FinanceTransaction[];
  alerts: FinanceAlert[];
  summary: {
    period: string;
    startDate: string;
    endDate: string;
    generatedAt: string;
  };
}

export interface FinanceAlert {
  id: string;
  type: 'info' | 'warning' | 'error' | 'success';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  category?: string;
  transactionId?: string;
  read: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceAnalytics {
  revenueAnalytics: {
    current: number;
    previous: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
    forecast: Array<{ period: string; value: number }>;
  };
  expenseAnalytics: {
    current: number;
    previous: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
    byCategory: Record<string, number>;
  };
  profitabilityAnalytics: {
    grossMargin: number;
    netMargin: number;
    operatingMargin: number;
    trend: 'up' | 'down' | 'stable';
  };
  cashFlowAnalytics: {
    operatingCashFlow: number;
    investingCashFlow: number;
    financingCashFlow: number;
    netCashFlow: number;
    trend: 'up' | 'down' | 'stable';
  };
  budgetAnalytics: {
    totalBudgeted: number;
    totalSpent: number;
    variance: number;
    byCategory: Array<{
      category: string;
      budgeted: number;
      spent: number;
      variance: number;
    }>;
  };
  riskAnalytics: {
    overallRisk: 'low' | 'medium' | 'high';
    riskFactors: Array<{
      type: string;
      level: 'low' | 'medium' | 'high';
      description: string;
    }>;
    recommendations: string[];
  };
}

export interface FinanceApp {
  id: string;
  name: string;
  category: FinanceAppCategory;
  description: string;
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: string;
  features: string[];
  supportedEntities: string[];
  config: FinanceAppConfig;
  createdAt: string;
  updatedAt: string;
}

export type FinanceAppCategory = 
  | 'accounting'
  | 'payment_processing'
  | 'expense_management'
  | 'banking_integration'
  | 'payroll_hrm'
  | 'procurement_sourcing'
  | 'investments'
  | 'tax_management'
  | 'reporting';

export interface FinanceAppConfig {
  apiVersion: string;
  realTimeSync: boolean;
  webhooks: boolean;
  batchSize: number;
  dataRetentionDays: number;
  enhancementLevel: 'standard' | 'advanced' | 'premium';
  complianceStandards: string[];
  features: string[];
  supportedEntities: string[];
}

export interface FinanceSearchFilters {
  period?: string;
  category?: string;
  account?: string;
  status?: string;
  dateRange?: {
    start: string;
    end: string;
  };
  amountRange?: {
    min: number;
    max: number;
  };
  search?: string;
  tags?: string[];
}

export interface FinanceApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface FinanceSyncResult {
  syncId: string;
  status: 'started' | 'in_progress' | 'completed' | 'failed';
  startedAt: string;
  completedAt?: string;
  recordsProcessed: number;
  recordsTotal: number;
  errors?: string[];
  estimatedCompletion?: string;
}

// Web-specific types
export interface WebFinanceChartOptions {
  responsive: boolean;
  animations: boolean;
  tooltip: boolean;
  legend: boolean;
  theme: 'light' | 'dark' | 'auto';
}

export interface WebFinanceTableState {
  pagination: {
    page: number;
    rowsPerPage: number;
    total: number;
  };
  sorting: {
    field: string;
    direction: 'asc' | 'desc';
  };
  filters: FinanceSearchFilters;
  selectedRows: string[];
}

// Desktop-specific types
export interface DesktopFinanceWindowConfig {
  width: number;
  height: number;
  x: number;
  y: number;
  fullscreen: boolean;
  alwaysOnTop: boolean;
  decorations: boolean;
}

export interface DesktopFinanceEvent {
  type: string;
  payload: any;
  timestamp: string;
}

export interface DesktopFinanceNotification {
  title: string;
  body: string;
  icon?: string;
  badge?: number;
  sound?: string;
  actions?: Array<{
    id: string;
    title: string;
    icon?: string;
  }>;
}

export interface DesktopFinanceShortcut {
  key: string;
  modifiers: Array<'ctrl' | 'alt' | 'shift' | 'meta'>;
  action: string;
  description: string;
}
