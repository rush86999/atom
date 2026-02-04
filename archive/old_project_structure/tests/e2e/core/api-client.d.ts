import { APIResponse } from "@playwright/test";
export interface APIResponse<T = any> {
  data: T;
  success: boolean;
  message?: string;
  errors?: string[];
}
export declare class APIClient {
  private baseUrl;
  private authToken?;
  constructor(baseUrl: string, authToken?: string);
  setAuthToken(token: string): void;
  private getHeaders;
  get(endpoint: string): Promise<APIResponse>;
  post(endpoint: string, data?: any): Promise<APIResponse>;
  put(endpoint: string, data?: any): Promise<APIResponse>;
  delete(endpoint: string): Promise<APIResponse>;
  private handleResponse;
}
//# sourceMappingURL=api-client.d.ts.map
