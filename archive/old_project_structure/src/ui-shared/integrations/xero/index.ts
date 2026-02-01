/**
 * Xero Integration Index
 * Exports all Xero integration components and services
 */

import XeroIntegration from './XeroIntegration';

// Skills services
import { xeroSkills } from './skills/xeroSkills';

// Types
export type {
  XeroTokens,
  XeroInvoice,
  XeroContact,
  XeroBankAccount,
  XeroTransaction,
  XeroFinancialReport,
  XeroAccount,
  XeroPayment,
  XeroTaxRate,
  XeroTrackingCategory,
  XeroCreateOptions,
  XeroSearchOptions,
  XeroListOptions
} from './skills/xeroSkills';

// Main export
export default XeroIntegration;

// Skills exports
export { xeroSkills };