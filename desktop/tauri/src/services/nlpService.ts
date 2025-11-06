/**
 * NLP Service for Intent Recognition and Entity Extraction
 */

export interface Intent {
  name: string;
  confidence: number;
}

export interface Entity {
  type: string;
  value: any;
  confidence: number;
  start?: number;
  end?: number;
}

export interface SkillExecutionContext {
  userId: string;
  sessionId: string;
  timestamp: string;
  intent: string;
  entities: Entity[];
  confidence: number;
}

export interface NLPResult {
  intent: Intent;
  entities: Entity[];
  confidence: number;
  processedText: string;
}

export class NLPService {
  private intentPatterns = {
    outlook_send_email: [
      /send.*email/i,
      /email.*send/i,
      /mail.*to/i,
      /compose.*email/i,
      /write.*email/i,
    ],
    outlook_get_emails: [
      /show.*emails?/i,
      /get.*emails?/i,
      /recent.*emails?/i,
      /unread.*emails?/i,
      /emails?.*list/i,
    ],
    outlook_search_emails: [
      /search.*emails?/i,
      /emails?.*search/i,
      /find.*emails?/i,
      /look for.*emails?/i,
    ],
    outlook_triage_emails: [
      /triage.*emails?/i,
      /organize.*emails?/i,
      /categorize.*emails?/i,
      /priority.*emails?/i,
    ],
    outlook_create_event: [
      /create.*event/i,
      /schedule.*meeting/i,
      /add.*calendar/i,
      /book.*appointment/i,
      /new.*event/i,
    ],
    outlook_get_calendar: [
      /show.*calendar/i,
      /get.*events?/i,
      /upcoming.*events?/i,
      /my.*schedule/i,
      /calendar.*list/i,
    ],
    outlook_search_events: [
      /search.*events?/i,
      /find.*events?/i,
      /calendar.*search/i,
      /events?.*search/i,
    ],
    outlook_help: [
      /outlook.*help/i,
      /help.*outlook/i,
      /outlook.*commands/i,
      /what.*can.*outlook/i,
    ],
    outlook_status: [
      /outlook.*status/i,
      /is.*outlook.*connected/i,
      /check.*outlook/i,
      /outlook.*working/i,
    ],
    // GitHub Intents
    github_list_repos: [
      /list.*repo/i,
      /show.*repo/i,
      /my.*repo/i,
      /repo.*list/i,
      /github.*repo/i,
      /show.*repositories/i,
    ],
    github_create_repo: [
      /create.*repo/i,
      /new.*repo/i,
      /make.*repo/i,
      /repo.*create/i,
      /github.*create/i,
    ],
    github_search_repos: [
      /search.*repo/i,
      /find.*repo/i,
      /repo.*search/i,
      /search.*repositories/i,
    ],
    github_list_issues: [
      /list.*issue/i,
      /show.*issue/i,
      /my.*issues?/i,
      /issue.*list/i,
      /github.*issue/i,
    ],
    github_create_issue: [
      /create.*issue/i,
      /new.*issue/i,
      /make.*issue/i,
      /issue.*create/i,
      /report.*bug/i,
      /github.*create.*issue/i,
    ],
    github_search_issues: [/search.*issue/i, /find.*issue/i, /issue.*search/i],
    github_list_prs: [
      /list.*pr/i,
      /show.*pr/i,
      /my.*pr/i,
      /pull.*request/i,
      /pr.*list/i,
      /github.*pr/i,
    ],
    github_create_pr: [
      /create.*pr/i,
      /new.*pr/i,
      /make.*pr/i,
      /pr.*create/i,
      /pull.*request.*create/i,
      /github.*create.*pr/i,
    ],
    github_search_prs: [
      /search.*pr/i,
      /find.*pr/i,
      /pr.*search/i,
      /pull.*request.*search/i,
    ],
    github_help: [
      /github.*help/i,
      /help.*github/i,
      /github.*commands/i,
      /what.*can.*github/i,
    ],
    github_status: [
      /github.*status/i,
      /is.*github.*connected/i,
      /check.*github/i,
      /github.*working/i,
    ],
  };

  private entityPatterns = {
    recipient: [
      /to\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i,
      /email\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i,
      /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s+email/i,
    ],
    subject: [
      /subject\s+['"`]([^'"`]+)['"`]/i,
      /['"`]([^'"`]+)['"`]\s+subject/i,
      /with\s+subject\s+['"`]([^'"`]+)['"`]/i,
    ],
    message: [
      /message\s+['"`]([^'"`]+)['"`]/i,
      /body\s+['"`]([^'"`]+)['"`]/i,
      /content\s+['"`]([^'"`]+)['"`]/i,
      /saying\s+['"`]([^'"`]+)['"`]/i,
    ],
    search_query: [
      /search\s+(?:for\s+)?['"`]([^'"`]+)['"`]/i,
      /['"`]([^'"`]+)['"`]\s+(?:search|find)/i,
      /(?:search|find)\s+(?:for\s+)?([^'"`\s]+)/i,
    ],
    count: [
      /(?:count|limit|number)\s+(?:of\s+)?(\d+)/i,
      /(\d+)\s+(?:emails?|events?)/i,
      /(?:top|first)\s+(\d+)/i,
    ],

    start_time: [
      /(?:at|on)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|a|p)?\s*(?:today|tomorrow|mon|tue|wed|thu|fri|sat|sun)?)/i,
      /time\s+['"`]([^'"`]+)['"`]/i,
      /start\s+['"`]([^'"`]+)['"`]/i,
    ],
    end_time: [
      /(?:until|till|to)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|a|p)?)/i,
      /end\s+['"`]([^'"`]+)['"`]/i,
    ],
    location: [
      /(?:at|in)\s+['"`]([^'"`]+)['"`]/i,
      /location\s+['"`]([^'"`]+)['"`]/i,
      /['"`]([^'"`]+)['"`]\s+(?:room|location)/i,
    ],
    attendees: [
      /(?:with|invite)\s+([^,]+)/i,
      /attendees?\s+['"`]([^'"`]+)['"`]/i,
    ],
    cc: [
      /cc\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i,
      /carbon.*copy\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i,
    ],
    unread: [/unread/i, /not.*read/i, /new.*emails?/i],
    // GitHub Entities
    owner: [
      /owner\s+([a-zA-Z0-9._-]+)/i,
      /([a-zA-Z0-9._-]+)\/([a-zA-Z0-9._-]+)/i,
      /user\s+([a-zA-Z0-9._-]+)/i,
    ],
    repo_name: [
      /repo\s+([a-zA-Z0-9._-]+)/i,
      /repository\s+([a-zA-Z0-9._-]+)/i,
      /([a-zA-Z0-9._-]+)\s+repo/i,
      /([a-zA-Z0-9._-]+)\s+repository/i,
      /([a-zA-Z0-9._-]+)\/([a-zA-Z0-9._-]+)/i,
    ],
    issue_number: [/issue\s+#(\d+)/i, /#(\d+)\s+issue/i],
    pr_number: [/pr\s+#(\d+)/i, /#(\d+)\s+pr/i, /pull\s+request\s+#(\d+)/i],
    issue_title: [
      /title\s+['"`]([^'"`]+)['"`]/i,
      /title\s+(.+)/i,
      /issue\s+(.+)/i,
    ],
    pr_title: [
      /pr\s+title\s+['"`]([^'"`]+)['"`]/i,
      /pull\s+request\s+title\s+(.+)/i,
    ],
    head: [
      /from\s+([a-zA-Z0-9._/-]+)/i,
      /head\s+([a-zA-Z0-9._/-]+)/i,
      /source\s+([a-zA-Z0-9._/-]+)/i,
      /branch\s+([a-zA-Z0-9._/-]+)/i,
    ],
    base: [
      /to\s+([a-zA-Z0-9._/-]+)/i,
      /base\s+([a-zA-Z0-9._/-]+)/i,
      /target\s+([a-zA-Z0-9._/-]+)/i,
    ],
    labels: [/labels?\s+(.+)/i, /tag(s)?\s+(.+)/i],
    assignees: [/assigne(es)?\s+(.+)/i, /assign\s+to\s+(.+)/i],
    reviewers: [/reviewer(s)?\s+(.+)/i, /review\s+by\s+(.+)/i],
    milestone: [/milestone\s+(.+)/i],
  };

  async processMessage(message: string): Promise<NLPResult> {
    const processedText = message.toLowerCase();
    const intent = this.detectIntent(processedText);
    const entities = this.extractEntities(processedText);
    const confidence = intent.confidence;

    return {
      intent,
      entities,
      confidence,
      processedText,
    };
  }

  private detectIntent(text: string): Intent {
    let bestMatch: Intent = {
      name: "general",
      confidence: 0,
    };

    for (const [intentName, patterns] of Object.entries(this.intentPatterns)) {
      for (const pattern of patterns) {
        if (pattern.test(text)) {
          const confidence = this.calculateConfidence(text, pattern);
          if (confidence > bestMatch.confidence) {
            bestMatch = {
              name: intentName,
              confidence,
            };
          }
        }
      }
    }

    return bestMatch;
  }

  private extractEntities(text: string): Entity[] {
    const entities: Entity[] = [];

    for (const [entityType, patterns] of Object.entries(this.entityPatterns)) {
      for (const pattern of patterns) {
        const matches = text.matchAll(pattern);
        for (const match of matches) {
          const value = match[1] || match[0];
          if (value) {
            entities.push({
              type: entityType,
              value: this.processEntityValue(entityType, value),
              confidence: 0.8,
              start: match.index,
              end: match.index + match[0].length,
            });
          }
        }
      }
    }

    return this.deduplicateEntities(entities);
  }

  private processEntityValue(entityType: string, value: string): any {
    switch (entityType) {
      case "count":
        return parseInt(value) || 10;
      case "unread":
        return true;
      case "start_time":
      case "end_time":
        return this.parseDateTime(value);
      case "recipients":
      case "cc":
        if (Array.isArray(value)) {
          return value;
        }
        return value ? [value] : [];
      default:
        return value;
    }
  }

  private parseDateTime(value: string): string {
    // Basic date parsing - in production, use a proper date library
    const now = new Date();

    if (value.includes("today")) {
      return now.toISOString();
    } else if (value.includes("tomorrow")) {
      const tomorrow = new Date(now);
      tomorrow.setDate(now.getDate() + 1);
      return tomorrow.toISOString();
    } else if (value.includes("next week")) {
      const nextWeek = new Date(now);
      nextWeek.setDate(now.getDate() + 7);
      return nextWeek.toISOString();
    }

    // Try to parse specific time
    const timeMatch = value.match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?/i);
    if (timeMatch) {
      let hours = parseInt(timeMatch[1]);
      const minutes = timeMatch[2] ? parseInt(timeMatch[2]) : 0;
      const period = timeMatch[3]?.toLowerCase();

      if (period === "pm" || period === "p") {
        hours = (hours % 12) + 12;
      } else if (period === "am" || period === "a") {
        hours = hours % 12;
      }

      const date = new Date(now);
      date.setHours(hours, minutes, 0, 0);
      return date.toISOString();
    }

    return value;
  }

  private calculateConfidence(text: string, pattern: RegExp): number {
    const match = text.match(pattern);
    if (!match) return 0;

    const matchLength = match[0].length;
    const textLength = text.length;
    const confidence = matchLength / textLength;

    return Math.min(confidence * 1.5, 1); // Boost confidence slightly
  }

  private deduplicateEntities(entities: Entity[]): Entity[] {
    const seen = new Map<string, Entity>();

    for (const entity of entities) {
      const key = `${entity.type}:${entity.value}`;
      if (!seen.has(key) || entity.confidence > seen.get(key)!.confidence) {
        seen.set(key, entity);
      }
    }

    return Array.from(seen.values());
  }
}

export const nlpService = new NLPService();
