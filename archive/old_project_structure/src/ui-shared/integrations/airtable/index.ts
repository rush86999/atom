/**
 * Airtable Data Management Integration
 * Complete Airtable data management system
 */

export { default as AirtableDataManagementUI } from './AirtableDataManagementUI';
export { default as airtableSkills } from './skills/airtableSkillsComplete';

// Re-export types
export type {
  AirtableBase,
  AirtableTable,
  AirtableField,
  AirtableView,
  AirtableRecord,
  AirtableUser,
  AirtableMemorySettings
} from './AirtableDataManagementUI';