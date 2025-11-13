import { 
  FinanceDashboardData, 
  FinanceTransaction, 
  FinanceApiResponse,
  FinanceSearchFilters,
  FinanceSyncResult,
  FinanceAnalytics,
  FinanceReport
} from '@shared/types/finance';

export class FinanceService {
  private static instance: FinanceService;
  private baseUrl: string;
  private apiKey: string;

  private constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || '';
  }

  public static getInstance(): FinanceService {
    if (!FinanceService.instance) {
      FinanceService.instance = new FinanceService();
    }
    return FinanceService.instance;
  }

  // Dashboard Methods
  public async getDashboardData(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceDashboardData>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/dashboard?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Transaction Methods
  public async getTransactions(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceTransaction[]>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);
    if (filters.status) params.append('status', filters.status);
    if (filters.search) params.append('search', filters.search);
    if (filters.dateRange) {
      params.append('start_date', filters.dateRange.start);
      params.append('end_date', filters.dateRange.end);
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data: data.transactions,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async createTransaction(transaction: Partial<FinanceTransaction>): Promise<FinanceApiResponse<FinanceTransaction>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(transaction)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async updateTransaction(id: string, transaction: Partial<FinanceTransaction>): Promise<FinanceApiResponse<FinanceTransaction>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(transaction)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async deleteTransaction(id: string): Promise<FinanceApiResponse<void>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return {
        success: true,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Analytics Methods
  public async getAnalytics(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceAnalytics>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/analytics?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Report Methods
  public async generateReport(type: string, filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceReport>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/reports`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          type,
          ...filters
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Export Methods
  public async exportData(format: 'excel' | 'csv' | 'pdf' = 'excel', filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<Blob>> {
    const params = new URLSearchParams();
    params.append('format', format);
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/export?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const blob = await response.blob();
      return {
        success: true,
        data: blob,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Sync Methods
  public async syncFinanceApp(appId: string, syncConfig: any = {}): Promise<FinanceApiResponse<FinanceSyncResult>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/apps/${appId}/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(syncConfig)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Health Check
  public async healthCheck(): Promise<FinanceApiResponse<{ status: string; timestamp: string }>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/health`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }
}
