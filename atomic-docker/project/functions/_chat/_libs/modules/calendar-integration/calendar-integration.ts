// Calendar Integration Operations - Unified calendar management across providers
import { graphileClient } from '../graphile/client';
import { CalendarIntegrationType } from '../../types/CalendarIntegrationType';
import { v4 as uuid } from 'uuid';

const calendarLogger = {
  info: console.log.bind(console, '[CalendarIntegration] INFO:'),
  error: console.error.bind(console, '[CalendarIntegration] ERROR:'),
};

// Types
export interface SyncResult {
  success: boolean;
  eventsUpdated: number;
  errors: string[];
}

export interface CalendarProviderConfig {
  provider: 'google' | 'outlook' | 'zoom';
  credentials: {
    accessToken: string;
    refreshToken?: string;
    expiresAt?: string;
  };
}

// Core integration functions

// Get by resource + user
export const getCalendarIntegrationByResource = async (
  userId: string,
  resource: string
): Promise<CalendarIntegrationType | null> => {
  const query = `
    query GetCalendarIntegration($userId: uuid!, $resource: String!) {
      Calendar_Integration(where: { userId: { _eq: $userId }, resource: { _eq: $resource }, deleted: { _eq: false } }) {
        id, userId, resource, token, refreshToken, expiresAt, clientType, enabled, createdDate, updatedAt
      }
    }
  `;
  const data = await graphileClient.request(query, { userId, resource });
  return data?.Calendar_Integration?.[0] || null;
};

// Get by name
export const getCalendarIntegrationByName = async (
  userId: string,
  name: string
): Promise<CalendarIntegrationType | null> => {
  const query = `
    query GetIntegrationByName($userId: uuid!, $name: String!) {
      Calendar_Integration(where: { userId: { _eq: $userId }, name: { _ilike: $name }, deleted: { _eq: false } }) {
        id, userId, resource, name, token, refreshToken, expiresAt, clientType, enabled
      }
    }
  `;
  const data = await graphileClient.request(query, { userId, name: `%${name}%` });
  return data?.Calendar_Integration?.[0] || null;
};

// Update integration
export const updateCalendarIntegration = async (
  id: string,
  updates: Partial<CalendarIntegrationType>
): Promise<boolean> => {
  const query = `
    mutation UpdateCalendarIntegration($id: String!, $updates: Calendar_Integration_set_input!) {
      update_Calendar_Integration_by_pk(pk_columns: { id: $id }, _set: $updates) { id }
    }`;
  const data = await graphileClient.request(query, { id, updates });
  return !!data?.update_Calendar_Integration_by_pk;
};

// Upsert integration
export const upsertCalendarIntegration = async (
  integration: CalendarIntegrationType
): Promise<string | null> => {
  const id = integration.id || uuid();
  const query = `
    mutation UpsertCalendarIntegration($objects: [Calendar_Integration_insert_input!]!) {
      insert_Calendar_Integration(objects: $objects, on_conflict: { constraint: Calendar_Integration_pkey, update_columns: [token, refreshToken, expiresAt, enabled, updatedAt] }) {
        returning { id }
      }
    }`;
  const data = await graphileClient.request(query, {
    objects: [{...integration, id, updatedAt: new Date().toISOString(), createdDate: new Date().toISOString()}]
  });
  return data?.insert_Calendar_Integration?.returning?.[0]?.id || null;
};

// List user integrations
export const listCalendarIntegrationsByUserId = async (
  userId: string
): Promise<CalendarIntegrationType[]> => {
  const query = `
    query ListIntegrations($userId: uuid!) {
n      Calendar_Integration(where: { userId: { _eq: $userId }, deleted: { _eq: false } }) {
n        id, userId, resource, name, enabled, expiresAt, clientType, updatedAt, createdDate
n      }
n    }`;
n  const data = await graphileClient.request(query, { userId });\n  return data?.Calendar_Integration || [];\n};\n\n// Delete integration\nexport const deleteCalendarIntegration = async (\n  id: string\n): Promise<boolean> => {\n  const query = `\n    mutation DeleteCalendarIntegration($id: String!) {\n      update_Calendar_Integration_by_pk(pk_columns: { id: $id }, _set: { deleted: true }) { id }\n    }`;\n  const data = await graphileClient.request(query, { id });\n  return !!data?.update_Calendar_Integration_by_pk;\n};\n\n// Validation\nexport const validateCalendarIntegration = (\n  integration: Partial<CalendarIntegrationType>\n): { isValid: boolean; errors: string[] } => {\n  const errors: string[] = [];\n  if (!integration.userId) errors.push('User ID required');\n  if (!integration.resource) errors.push('Resource required');\n  if (!['google', 'outlook', 'zoom'].includes(integration.resource || '')) {\n    errors.push('Resource must be google, outlook, or zoom');\n  }\n  if (!integration.token) errors.push('Access token required');\n  return { isValid: errors.length === 0, errors };\n};\n
