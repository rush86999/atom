// Simple API backend helper for ATOM platform
import { NextApiRequest, NextApiResponse } from "next";

export { resilientFetch };

// Generic resilient fetch wrapper for app-service backend helpers
const resilientFetch = async (
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  url: string,
  options?: RequestInit,
  operationName: string = "externalApiCall",
): Promise<any> => {
  const MAX_RETRIES = 3;
  const DEFAULT_TIMEOUT_MS = 30000;
  let attempt = 0;

  while (attempt < MAX_RETRIES) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(
        () => controller.abort(),
        DEFAULT_TIMEOUT_MS,
      );

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
        body: options?.body,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      attempt++;
      if (attempt >= MAX_RETRIES) {
        console.error(
          `Failed ${operationName} after ${MAX_RETRIES} attempts:`,
          error,
        );
        throw error;
      }
      // Wait before retrying (exponential backoff)
      await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
    }
  }
};

// Google OAuth helpers
export const exchangeCodeForTokens = async (code: string): Promise<any> => {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return resilientFetch(
    "POST",
    `${backendUrl}/api/auth/google/token`,
    {
      body: JSON.stringify({ code }),
    },
    "exchangeCodeForTokens",
  );
};

export const generateGoogleAuthUrl = (): string => {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${backendUrl}/api/auth/google/authorize`;
};

// Calendar integration helpers
export const getMinimalCalendarIntegrationByResource = async (
  userId: string,
  resource: string,
): Promise<any> => {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return resilientFetch(
    "POST",
    `${backendUrl}/api/graphql`,
    {
      body: JSON.stringify({
        query: `
        query GetCalendarIntegration($userId: String!, $resource: String!) {
          Calendar_Integration(
            where: {
              userId: { _eq: $userId },
              resource: { _eq: $resource },
              deleted: { _eq: false }
            }
            limit: 1
          ) {
            id
            token
            refreshToken
            resource
            expiresAt
          }
        }
      `,
        variables: { userId, resource },
      }),
    },
    "getMinimalCalendarIntegrationByResource",
  );
};

export const getAllCalendarIntegrationsByResourceAndClientType = async (
  userId: string,
  resource: string,
  clientType: string,
): Promise<any> => {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return resilientFetch(
    "POST",
    `${backendUrl}/api/graphql`,
    {
      body: JSON.stringify({
        query: `
        query GetCalendarIntegrations($userId: String!, $resource: String!, $clientType: String!) {
          Calendar_Integration(
            where: {
              userId: { _eq: $userId },
              resource: { _eq: $resource },
              clientType: { _eq: $clientType },
              deleted: { _eq: false }
            }
          ) {
            id
            token
            refreshToken
            resource
            clientType
            expiresAt
            createdDate
            updatedAt
          }
        }
      `,
        variables: { userId, resource, clientType },
      }),
    },
    "getAllCalendarIntegrationsByResourceAndClientType",
  );
};

// Schedule meeting helper
export const scheduleMeeting = async (meetingData: any): Promise<any> => {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return resilientFetch(
    "POST",
    `${backendUrl}/api/schedule/meeting`,
    {
      body: JSON.stringify(meetingData),
    },
    "scheduleMeeting",
  );
};

// Zoom token encryption helper
export const encryptZoomTokens = (tokens: any): string => {
  // Simple base64 encoding for demo purposes
  // In production, use proper encryption
  return Buffer.from(JSON.stringify(tokens)).toString("base64");
};

export const decryptZoomTokens = (encrypted: string): any => {
  try {
    return JSON.parse(Buffer.from(encrypted, "base64").toString());
  } catch (error) {
    console.error("Failed to decrypt Zoom tokens:", error);
    return null;
  }
};

// Default export
export default {
  resilientFetch,
  exchangeCodeForTokens,
  generateGoogleAuthUrl,
  getMinimalCalendarIntegrationByResource,
  getAllCalendarIntegrationsByResourceAndClientType,
  scheduleMeeting,
  encryptZoomTokens,
  decryptZoomTokens,
};
