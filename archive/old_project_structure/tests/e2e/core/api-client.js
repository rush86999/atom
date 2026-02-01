"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.APIClient = void 0;
class APIClient {
  constructor(baseUrl, authToken) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
  }
  setAuthToken(token) {
    this.authToken = token;
  }
  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
    };
    if (this.authToken) {
      headers["Authorization"] = `Bearer ${this.authToken}`;
    }
    return headers;
  }
  async get(endpoint) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }
  async post(endpoint, data) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined,
    });
    return this.handleResponse(response);
  }
  async put(endpoint, data) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "PUT",
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined,
    });
    return this.handleResponse(response);
  }
  async delete(endpoint) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }
  async handleResponse(response) {
    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }
    try {
      const data = await response.json();
      return {
        data,
        success: true,
      };
    } catch {
      return {
        data: await response.text(),
        success: true,
      };
    }
  }
}
exports.APIClient = APIClient;
//# sourceMappingURL=api-client.js.map
