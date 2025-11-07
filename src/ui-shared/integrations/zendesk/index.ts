/**
 * Zendesk Integration Index
 * Exports all Zendesk integration components and services
 */

import ZendeskIntegration from './ZendeskIntegration';

// Skills services
import { zendeskSkills } from './skills/zendeskSkills';
import { zendeskSkillsEnhanced } from './skills/zendeskSkillsEnhanced';

// Types
export type {
  ZendeskTokens,
  ZendeskTicket,
  ZendeskUser,
  ZendeskGroup,
  ZendeskOrganization,
  ZendeskMetric,
  ZendeskMacro,
  ZendeskTrigger,
  ZendeskAutomation,
  ZendeskSLA,
  ZendeskArticle,
  ZendeskCategory,
  ZendeskSection,
  ZendeskSearchOptions,
  ZendeskListOptions,
  ZendeskCreateOptions,
  ZendeskUpdateOptions
} from './skills/zendeskSkills';

export type {
  ZendeskAIPrediction,
  ZendeskAIInsight,
  ZendeskSentiment,
  ZendeskTicketAnalytics,
  ZendeskUserAnalytics,
  ZendeskTeamAnalytics,
  ZendeskBusinessIntelligence
} from './skills/zendeskSkillsEnhanced';

// Main export
export default ZendeskIntegration;

// Skills exports
export { zendeskSkills, zendeskSkillsEnhanced };