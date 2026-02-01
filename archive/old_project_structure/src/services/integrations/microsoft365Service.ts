/**
 * Microsoft 365 Integration Service
 *
 * This service provides TypeScript integration for Microsoft 365 operations
 * including Teams, Outlook, Calendar, and user profile management.
 */

import { apiService } from '../utils/api-service';

export interface Microsoft365User {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
}

export interface Microsoft365Team {
  id: string;
  displayName: string;
  description?: string;
  visibility?: string;
}

export interface Microsoft365Channel {
  id: string;
  displayName: string;
  description?: string;
}

export interface Microsoft365Message {
  id: string;
  subject: string;
  from: {
    emailAddress: {
      address: string;
    };
  };
  receivedDateTime: string;
  bodyPreview: string;
}

export interface Microsoft365Event {
  id: string;
  subject: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location?: {
    displayName: string;
  };
}

export interface Microsoft365AuthResponse {
  auth_url: string;
  state: string;
}

export interface Microsoft365ServiceStatus {
  teams: {
    status: string;
    lastChecked: string;
  };
  outlook: {
    status: string;
    lastChecked: string;
  };
  onedrive: {
    status: string;
    lastChecked: string;
  };
  sharepoint: {
    status: string;
    lastChecked: string;
  };
}

export interface Microsoft365ServiceResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

class Microsoft365Service {
  private basePath = '/microsoft365';

  /**
   * Initiate Microsoft 365 OAuth authentication
   */
  async authenticate(userId: string): Promise<Microsoft365ServiceResponse<Microsoft365AuthResponse>> {
    try {
      const response = await apiService.get(`${this.basePath}/auth`, {
        params: { user_id: userId }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Microsoft 365 authentication failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Authentication failed'
      };
    }
  }

  /**
   * Get Microsoft 365 user profile
   */
  async getUserProfile(accessToken: string): Promise<Microsoft365ServiceResponse<Microsoft365User>> {
    try {
      const response = await apiService.get(`${this.basePath}/user`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Microsoft 365 get user profile failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get user profile'
      };
    }
  }

  /**
   * List Microsoft Teams
   */
  async listTeams(accessToken: string): Promise<Microsoft365ServiceResponse<Microsoft365Team[]>> {
    try {
      const response = await apiService.get(`${this.basePath}/teams`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data.teams };
    } catch (error) {
      console.error('Microsoft 365 list teams failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to list teams'
      };
    }
  }

  /**
   * List channels in a Microsoft Team
   */
  async listChannels(
    accessToken: string,
    teamId: string
  ): Promise<Microsoft365ServiceResponse<Microsoft365Channel[]>> {
    try {
      const response = await apiService.get(`${this.basePath}/teams/${teamId}/channels`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data.channels };
    } catch (error) {
      console.error('Microsoft 365 list channels failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to list channels'
      };
    }
  }

  /**
   * Get Outlook messages
   */
  async getMessages(
    accessToken: string,
    folderId: string = 'inbox',
    top: number = 10
  ): Promise<Microsoft365ServiceResponse<Microsoft365Message[]>> {
    try {
      const response = await apiService.get(`${this.basePath}/outlook/messages`, {
        params: {
          access_token: accessToken,
          folder_id: folderId,
          top: top
        }
      });
      return { status: 'success', data: response.data.messages };
    } catch (error) {
      console.error('Microsoft 365 get messages failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get messages'
      };
    }
  }

  /**
   * Get calendar events
   */
  async getEvents(
    accessToken: string,
    startDate: string,
    endDate: string
  ): Promise<Microsoft365ServiceResponse<Microsoft365Event[]>> {
    try {
      const response = await apiService.get(`${this.basePath}/calendar/events`, {
        params: {
          access_token: accessToken,
          start_date: startDate,
          end_date: endDate
        }
      });
      return { status: 'success', data: response.data.events };
    } catch (error) {
      console.error('Microsoft 365 get events failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get events'
      };
    }
  }

  /**
   * Get Microsoft 365 service status
   */
  async getServiceStatus(accessToken: string): Promise<Microsoft365ServiceResponse<Microsoft365ServiceStatus>> {
    try {
      const response = await apiService.get(`${this.basePath}/services/status`, {
        params: { access_token: accessToken }
      });
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Microsoft 365 get service status failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get service status'
      };
    }
  }

  /**
   * Health check for Microsoft 365 service
   */
  async healthCheck(): Promise<Microsoft365ServiceResponse<{ status: string; service: string; timestamp: string }>> {
    try {
      const response = await apiService.get(`${this.basePath}/health`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Microsoft 365 health check failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Health check failed'
      };
    }
  }

  /**
   * Get service capabilities
   */
  async getCapabilities(): Promise<Microsoft365ServiceResponse<{
    service: string;
    capabilities: string[];
    supportedServices: string[];
    integrationFeatures: string[];
  }>> {
    try {
      const response = await apiService.get(`${this.basePath}/capabilities`);
      return { status: 'success', data: response.data };
    } catch (error) {
      console.error('Microsoft 365 get capabilities failed:', error);
      return {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to get capabilities'
      };
    }
  }
}

// Export singleton instance
export const microsoft365Service = new Microsoft365Service();

// Export for use in React components
export default microsoft365Service;
