/**
 * Gmail Skills - Integration skills for Gmail platform
 * Provides AI agent capabilities for Gmail operations
 * Includes LanceDB memory integration for intelligent email processing
 */

import { Skill, SkillContext, SkillResult } from "../types";

export interface GmailEmail {
  id: string;
  threadId: string;
  labelIds: string[];
  snippet: string;
  payload: {
    headers: Array<{
      name: string;
      value: string;
    }>;
    parts?: Array<{
      mimeType: string;
      body: {
        data?: string;
        size: number;
      };
    }>;
  };
  sizeEstimate: number;
  historyId: string;
  internalDate: string;
}

export interface GmailLabel {
  id: string;
  name: string;
  messageListVisibility: string;
  labelListVisibility: string;
  type: string;
  messagesTotal?: number;
  messagesUnread?: number;
  threadsTotal?: number;
  threadsUnread?: number;
  color?: {
    textColor: string;
    backgroundColor: string;
  };
}

export interface GmailThread {
  id: string;
  historyId: string;
  messages: GmailEmail[];
  snippet: string;
}

export interface GmailProfile {
  emailAddress: string;
  messagesTotal: number;
  threadsTotal: number;
  historyId: string;
}

export interface GmailMemorySearchResult {
  id: string;
  subject: string;
  from_email: string;
  snippet: string;
  date: string;
  labels: string[];
  similarity_score: number;
  body_text: string;
}

export interface GmailMemoryStats {
  total_messages: number;
  total_threads: number;
  indexed_messages: number;
  last_sync: string;
  memory_size_mb: number;
  search_enabled: boolean;
}

/**
 * Gmail Skills - AI agent capabilities for Gmail operations
 */
export const gmailSkills: Skill[] = [
  {
    id: "gmail-get-profile",
    name: "Get Gmail Profile",
    description: "Get Gmail user profile information",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {},
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/profile", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(
            `Failed to fetch Gmail profile: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || {},
          message: `Retrieved Gmail profile for ${data.data?.emailAddress || "user"}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to get Gmail profile: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-list-emails",
    name: "List Gmail Emails",
    description: "List emails from Gmail inbox with filtering options",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        maxResults: {
          type: "number",
          description: "Maximum number of emails to return",
          default: 20,
        },
        labelIds: {
          type: "array",
          items: { type: "string" },
          description: "Filter by label IDs",
        },
        query: {
          type: "string",
          description: "Search query to filter emails",
        },
        includeSpamTrash: {
          type: "boolean",
          description: "Include emails from spam and trash",
          default: false,
        },
      },
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/emails", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            max_results: params.maxResults || 20,
            label_ids: params.labelIds,
            query: params.query,
            include_spam_trash: params.includeSpamTrash || false,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch emails: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} Gmail emails`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list Gmail emails: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-get-email",
    name: "Get Gmail Email",
    description: "Get detailed information about a specific email",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to retrieve",
        },
        format: {
          type: "string",
          description: "Format of the email content",
          enum: ["full", "metadata", "minimal"],
          default: "full",
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch(
          `/api/integrations/gmail/emails/${params.emailId}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch email: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Retrieved email with ID: ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to get Gmail email: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-send-email",
    name: "Send Gmail Email",
    description: "Send an email through Gmail",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        to: {
          type: "string",
          description: "Recipient email address",
        },
        subject: {
          type: "string",
          description: "Email subject",
        },
        body: {
          type: "string",
          description: "Email body content",
        },
        cc: {
          type: "string",
          description: "CC recipient email address",
        },
        bcc: {
          type: "string",
          description: "BCC recipient email address",
        },
        replyTo: {
          type: "string",
          description: "Reply-to email address",
        },
      },
      required: ["to", "subject", "body"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/send", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            to: params.to,
            subject: params.subject,
            body: params.body,
            cc: params.cc,
            bcc: params.bcc,
            reply_to: params.replyTo,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to send email: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Email sent successfully to ${params.to}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to send Gmail email: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-list-labels",
    name: "List Gmail Labels",
    description: "List all Gmail labels and categories",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {},
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/labels", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch labels: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} Gmail labels`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list Gmail labels: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-create-label",
    name: "Create Gmail Label",
    description: "Create a new Gmail label",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        name: {
          type: "string",
          description: "Label name",
        },
        labelListVisibility: {
          type: "string",
          description: "Label list visibility",
          enum: ["show", "showUnread", "hide"],
          default: "show",
        },
        messageListVisibility: {
          type: "string",
          description: "Message list visibility",
          enum: ["show", "hide"],
          default: "show",
        },
        color: {
          type: "object",
          description: "Label color settings",
          properties: {
            textColor: { type: "string" },
            backgroundColor: { type: "string" },
          },
        },
      },
      required: ["name"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/labels", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: params.name,
            label_list_visibility: params.labelListVisibility || "show",
            message_list_visibility: params.messageListVisibility || "show",
            color: params.color,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create label: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Created Gmail label: "${params.name}"`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to create Gmail label: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-search-emails",
    name: "Search Gmail Emails",
    description: "Search emails using Gmail search operators",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Gmail search query",
        },
        maxResults: {
          type: "number",
          description: "Maximum number of results",
          default: 20,
        },
        labelIds: {
          type: "array",
          items: { type: "string" },
          description: "Filter by label IDs",
        },
      },
      required: ["query"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/search", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: params.query,
            max_results: params.maxResults || 20,
            label_ids: params.labelIds,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to search emails: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} emails matching search criteria`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to search Gmail emails: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-mark-as-read",
    name: "Mark Gmail Email as Read",
    description: "Mark an email as read by removing the UNREAD label",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to mark as read",
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch(
          `/api/integrations/gmail/emails/${params.emailId}/read`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        if (!response.ok) {
          throw new Error(
            `Failed to mark email as read: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Marked email as read: ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to mark Gmail email as read: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-mark-as-unread",
    name: "Mark Gmail Email as Unread",
    description: "Mark an email as unread by adding the UNREAD label",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to mark as unread",
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch(
          `/api/integrations/gmail/emails/${params.emailId}/unread`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        if (!response.ok) {
          throw new Error(
            `Failed to mark email as unread: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Marked email as unread: ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to mark Gmail email as unread: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-star-email",
    name: "Star Gmail Email",
    description: "Add star to an email",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to star",
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch(
          `/api/integrations/gmail/emails/${params.emailId}/star`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        if (!response.ok) {
          throw new Error(`Failed to star email: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Starred email: ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to star Gmail email: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-unstar-email",
    name: "Unstar Gmail Email",
    description: "Remove star from an email",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to unstar",
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch(
          `/api/integrations/gmail/emails/${params.emailId}/unstar`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          },
        );

        if (!response.ok) {
          throw new Error(`Failed to unstar email: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Unstarred email: ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to unstar Gmail email: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-health-check",
    name: "Gmail Health Check",
    description: "Check Gmail integration health and connection status",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {},
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/health", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(
            `Failed to check Gmail health: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || {},
          message: `Gmail integration is ${data.data?.status || "unknown"}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to check Gmail health: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-search-memory",
    name: "Search Gmail Memory",
    description:
      "Search Gmail emails stored in LanceDB memory using semantic search",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query for semantic search",
        },
        limit: {
          type: "number",
          description: "Maximum number of results",
          default: 10,
        },
        includeBody: {
          type: "boolean",
          description: "Include full email body in results",
          default: false,
        },
        labels: {
          type: "array",
          items: { type: "string" },
          description: "Filter by specific labels",
        },
        dateRange: {
          type: "object",
          description: "Date range filter",
          properties: {
            start: { type: "string" },
            end: { type: "string" },
          },
        },
      },
      required: ["query"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/search", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: params.query,
            limit: params.limit || 10,
            include_body: params.includeBody || false,
            labels: params.labels,
            date_range: params.dateRange,
          }),
        });

        if (!response.ok) {
          throw new Error(
            `Failed to search Gmail memory: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} emails in memory matching your search`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to search Gmail memory: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-get-memory-stats",
    name: "Get Gmail Memory Stats",
    description: "Get statistics about Gmail emails stored in LanceDB memory",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {},
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/stats", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(
            `Failed to get Gmail memory stats: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || {},
          message: `Gmail memory contains ${data.data?.total_messages || 0} messages across ${data.data?.total_threads || 0} threads`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to get Gmail memory stats: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-sync-memory",
    name: "Sync Gmail Memory",
    description: "Trigger synchronization of Gmail emails to LanceDB memory",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        forceFullSync: {
          type: "boolean",
          description: "Force full synchronization instead of incremental",
          default: false,
        },
        maxMessages: {
          type: "number",
          description: "Maximum number of messages to sync",
          default: 1000,
        },
        labels: {
          type: "array",
          items: { type: "string" },
          description: "Specific labels to sync",
        },
      },
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/sync", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            force_full_sync: params.forceFullSync || false,
            max_messages: params.maxMessages || 1000,
            labels: params.labels,
          }),
        });

        if (!response.ok) {
          throw new Error(
            `Failed to sync Gmail memory: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Gmail memory sync completed: ${data.data?.synced_messages || 0} messages processed`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to sync Gmail memory: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-find-similar-emails",
    name: "Find Similar Emails",
    description:
      "Find emails similar to a specific email using semantic similarity",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to find similar emails for",
        },
        limit: {
          type: "number",
          description: "Maximum number of similar emails to return",
          default: 5,
        },
        minSimilarity: {
          type: "number",
          description: "Minimum similarity score (0-1)",
          default: 0.7,
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/similar", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email_id: params.emailId,
            limit: params.limit || 5,
            min_similarity: params.minSimilarity || 0.7,
          }),
        });

        if (!response.ok) {
          throw new Error(
            `Failed to find similar emails: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} similar emails`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to find similar emails: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-analyze-email-patterns",
    name: "Analyze Email Patterns",
    description: "Analyze email patterns and relationships in LanceDB memory",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        analysisType: {
          type: "string",
          description: "Type of analysis to perform",
          enum: ["contacts", "topics", "frequency", "relationships"],
          default: "topics",
        },
        timeRange: {
          type: "object",
          description: "Time range for analysis",
          properties: {
            start: { type: "string" },
            end: { type: "string" },
          },
        },
        limit: {
          type: "number",
          description: "Maximum number of patterns to return",
          default: 10,
        },
      },
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            analysis_type: params.analysisType || "topics",
            time_range: params.timeRange,
            limit: params.limit || 10,
          }),
        });

        if (!response.ok) {
          throw new Error(
            `Failed to analyze email patterns: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || {},
          message: `Completed ${params.analysisType} analysis on Gmail memory`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to analyze email patterns: ${error}`,
        };
      }
    },
  },
  {
    id: "gmail-get-context",
    name: "Get Email Context",
    description:
      "Get contextual information about emails and conversations from memory",
    category: "gmail",
    parameters: {
      type: "object",
      properties: {
        emailId: {
          type: "string",
          description: "Email ID to get context for",
        },
        includeThread: {
          type: "boolean",
          description: "Include entire conversation thread",
          default: true,
        },
        includeRelated: {
          type: "boolean",
          description: "Include related emails",
          default: false,
        },
        maxContext: {
          type: "number",
          description: "Maximum number of context emails to include",
          default: 10,
        },
      },
      required: ["emailId"],
    },
    execute: async (
      params: any,
      context: SkillContext,
    ): Promise<SkillResult> => {
      try {
        const response = await fetch("/api/integrations/gmail/memory/context", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email_id: params.emailId,
            include_thread: params.includeThread || true,
            include_related: params.includeRelated || false,
            max_context: params.maxContext || 10,
          }),
        });

        if (!response.ok) {
          throw new Error(
            `Failed to get email context: ${response.statusText}`,
          );
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || {},
          message: `Retrieved context for email ${params.emailId}`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to get email context: ${error}`,
        };
      }
    },
  },
];
