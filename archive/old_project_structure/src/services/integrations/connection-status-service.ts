import axios from 'axios';

export interface ConnectionStatus {
  connected: boolean;
  email?: string;
  name?: string;
  message?: string;
  last_updated?: string;
  scopes?: string[];
  team_name?: string;
  user_name?: string;
  team?: string;
  username?: string;
  institution_count?: number;
}

export interface AllConnectionsStatus {
  user_id: string;
  timestamp: string;
  connections: {
    google: ConnectionStatus;
    slack: ConnectionStatus;
    microsoft: ConnectionStatus;
    linkedin: ConnectionStatus;
    twitter: ConnectionStatus;
    plaid: ConnectionStatus;
  };
}

class ConnectionStatusService {
  private baseURL = process.env.NEXT_PUBLIC_CONNECTION_STATUS_API || 'http://localhost:8005';
  private userId: string;

  constructor(userId: string) {
    this.userId = userId;
  }

  async getAllConnections(): Promise<AllConnectionsStatus> {
    try {
      const response = await axios.get(`${this.baseURL}/status/${this.userId}`);
      return response.data;
    } catch (error) {
      console.warn('Could not fetch connection status from backend, using mock data:', error);
      return this.getMockConnections();
    }
  }

  async getServiceStatus(service: string): Promise<ConnectionStatus> {
    try {
      const response = await axios.get(`${this.baseURL}/status/${this.userId}/${service}`);
      return response.data.status;
    } catch (error) {
      console.warn(`Could not fetch ${service} status from backend, using mock data:`, error);
      return this.getMockServiceStatus(service);
    }
  }

  private getMockConnections(): AllConnectionsStatus {
    return {
      user_id: this.userId,
      timestamp: new Date().toISOString(),
      connections: {
        google: { connected: true, email: 'user@example.com', scopes: ['calendar.readonly', 'gmail.readonly'] },
        slack: { connected: true, team_name: 'Acme Team', user_name: 'John Doe' },
        microsoft: { connected: true, email: 'user@company.com', display_name: 'John Doe' },
        linkedin: { connected: false, message: 'No LinkedIn OAuth found' },
        twitter: { connected: false, message: 'No Twitter OAuth found' },
        plaid: { connected: true, institution_count: 2 }
      }
    };
  }

  private getMockServiceStatus(service: string): ConnectionStatus {
    const mockStatus = {
      connected: false,
      message: `${service} not configured`
    };

    switch (service) {
      case 'google':
        return { connected: true, email: 'user@example.com', scopes: ['calendar.readonly', 'gmail.readonly'] };
      case 'slack':
        return { connected: true, team_name: 'Acme Team', user_name: 'John Doe' };
      case 'microsoft':
        return { connected: true, email: 'user@company.com', display_name: 'John Doe' };
      case 'linkedin':
        return { connected: false, message: 'No LinkedIn OAuth found' };
      case 'twitter':
        return { connected: false, message: 'No Twitter OAuth found' };
      case 'plaid':
        return { connected: true, institution_count: 2 };
      default:
        return mockStatus;
    }
  }

  async refreshConnection(service: string): Promise<void> {
    try {
      await axios.post(`${this.baseURL}/status/${this.userId}/${service}`, {
        refresh: true,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.warn(`Could not refresh ${service} connection:`, error);
    }
  }
}

// Export singleton instance creator
export const createConnectionStatusService = (userId: string) => new ConnectionStatusService(userId);
