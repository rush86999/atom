/**
 * Simplified NLU Service for Tauri Desktop App
 * Browser-compatible implementation without Node.js dependencies
 */

export interface Intent {
  name: string;
  confidence: number;
  entities: Record<string, any>;
}

export interface Entity {
  entity: string;
  value: string;
  confidence: number;
}

export interface SkillExecutionContext {
  intent: Intent;
  entities: Entity[];
  userInput: string;
  sessionId?: string;
  userId?: string;
}

export interface NLUResponse {
  intent: Intent | null;
  entities: Entity[];
  confidence: number;
  action?: string;
  parameters?: Record<string, any>;
}

class NLUService {
  private patterns: Map<string, RegExp> = new Map();

  constructor() {
    this.initializePatterns();
  }

  private initializePatterns() {
    // GitHub patterns
    this.patterns.set(
      "github.create_repo",
      /create.*repo|new.*repository|make.*github.*project/i,
    );
    this.patterns.set(
      "github.list_repos",
      /list.*repos|show.*repositories|my.*github.*projects/i,
    );
    this.patterns.set(
      "github.search_repos",
      /search.*repos|find.*repository|look.*for.*github/i,
    );
    this.patterns.set(
      "github.create_issue",
      /create.*issue|new.*issue|report.*bug/i,
    );
    this.patterns.set(
      "github.list_issues",
      /list.*issues|show.*issues|my.*issues/i,
    );

    // Calendar patterns
    this.patterns.set(
      "calendar.create_event",
      /create.*event|schedule.*meeting|add.*to.*calendar/i,
    );
    this.patterns.set(
      "calendar.list_events",
      /list.*events|show.*calendar|my.*schedule/i,
    );
    this.patterns.set(
      "calendar.search_events",
      /search.*events|find.*meeting|look.*for.*event/i,
    );

    // Task patterns
    this.patterns.set("task.create", /create.*task|add.*todo|new.*task/i);
    this.patterns.set("task.list", /list.*tasks|show.*todos|my.*tasks/i);
    this.patterns.set(
      "task.complete",
      /complete.*task|finish.*task|mark.*done/i,
    );

    // Search patterns
    this.patterns.set(
      "search.document",
      /search.*documents|find.*files|look.*for.*documents/i,
    );
    this.patterns.set(
      "search.code",
      /search.*code|find.*code|look.*for.*code/i,
    );
    this.patterns.set("search.web", /search.*web|google.*search|find.*online/i);

    // General patterns
    this.patterns.set("help", /help|what.*can.*you.*do|how.*to.*use/i);
    this.patterns.set(
      "greeting",
      /hello|hi|hey|good.*morning|good.*afternoon/i,
    );
  }

  async processInput(userInput: string): Promise<NLUResponse> {
    const normalizedInput = userInput.toLowerCase().trim();

    // Extract entities first
    const entities = this.extractEntities(normalizedInput);

    // Find matching intent
    const intent = this.findIntent(normalizedInput);

    // Calculate overall confidence
    const confidence = intent ? intent.confidence : 0.3;

    // Determine action based on intent
    const action = intent ? this.mapIntentToAction(intent.name) : "unknown";

    return {
      intent,
      entities,
      confidence,
      action,
      parameters: this.extractParameters(normalizedInput, intent?.name),
    };
  }

  private findIntent(input: string): Intent | null {
    let bestMatch: { name: string; confidence: number } | null = null;

    for (const [intentName, pattern] of this.patterns.entries()) {
      if (pattern.test(input)) {
        const confidence = this.calculateConfidence(input, pattern);
        if (!bestMatch || confidence > bestMatch.confidence) {
          bestMatch = { name: intentName, confidence };
        }
      }
    }

    if (bestMatch) {
      return {
        name: bestMatch.name,
        confidence: bestMatch.confidence,
        entities: {},
      };
    }

    return null;
  }

  private extractEntities(input: string): Entity[] {
    const entities: Entity[] = [];

    // Extract time entities
    const timeMatch = input.match(
      /(\d{1,2}:\d{2}\s*(?:am|pm)?)|(today|tomorrow|next week|this weekend)/i,
    );
    if (timeMatch) {
      entities.push({
        entity: "time",
        value: timeMatch[0],
        confidence: 0.8,
      });
    }

    // Extract date entities
    const dateMatch = input.match(
      /\b(\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2})\b/,
    );
    if (dateMatch) {
      entities.push({
        entity: "date",
        value: dateMatch[0],
        confidence: 0.9,
      });
    }

    // Extract project/repo names (simple pattern)
    const projectMatch = input.match(
      /\b(?:project|repo|repository)\s+([a-zA-Z0-9-_]+)/i,
    );
    if (projectMatch) {
      entities.push({
        entity: "project_name",
        value: projectMatch[1],
        confidence: 0.7,
      });
    }

    // Extract issue titles
    const issueMatch = input.match(
      /\b(?:issue|bug)\s+(.+?)(?:\s+in|\s+for|$)/i,
    );
    if (issueMatch) {
      entities.push({
        entity: "issue_title",
        value: issueMatch[1].trim(),
        confidence: 0.6,
      });
    }

    return entities;
  }

  private extractParameters(
    input: string,
    intentName?: string,
  ): Record<string, any> {
    const parameters: Record<string, any> = {};

    if (!intentName) return parameters;

    // Extract parameters based on intent
    switch (intentName) {
      case "github.create_repo":
        const repoMatch = input.match(/\b(?:called|named)\s+([a-zA-Z0-9-_]+)/i);
        if (repoMatch) {
          parameters.repository_name = repoMatch[1];
        }
        break;

      case "github.create_issue":
        const titleMatch = input.match(
          /\b(?:titled|called)\s+(.+?)(?:\s+in|\s+for|$)/i,
        );
        if (titleMatch) {
          parameters.issue_title = titleMatch[1].trim();
        }
        break;

      case "calendar.create_event":
        const eventMatch = input.match(
          /\b(?:called|titled)\s+(.+?)(?:\s+at|\s+on|$)/i,
        );
        if (eventMatch) {
          parameters.event_title = eventMatch[1].trim();
        }
        break;
    }

    return parameters;
  }

  private mapIntentToAction(intentName: string): string {
    const actionMap: Record<string, string> = {
      "github.create_repo": "create_repository",
      "github.list_repos": "list_repositories",
      "github.search_repos": "search_repositories",
      "github.create_issue": "create_issue",
      "github.list_issues": "list_issues",
      "calendar.create_event": "create_event",
      "calendar.list_events": "list_events",
      "calendar.search_events": "search_events",
      "task.create": "create_task",
      "task.list": "list_tasks",
      "task.complete": "complete_task",
      "search.document": "search_documents",
      "search.code": "search_code",
      "search.web": "search_web",
      help: "show_help",
      greeting: "greet_user",
    };

    return actionMap[intentName] || "unknown";
  }

  private calculateConfidence(input: string, pattern: RegExp): number {
    const match = input.match(pattern);
    if (!match) return 0;

    const matchedText = match[0];
    const inputLength = input.length;
    const matchLength = matchedText.length;

    // Higher confidence for longer matches relative to input length
    const lengthRatio = matchLength / inputLength;

    // Higher confidence for exact matches
    const exactMatchBonus = input === matchedText ? 0.2 : 0;

    return Math.min(0.9, 0.7 + lengthRatio * 0.2 + exactMatchBonus);
  }

  async getSupportedIntents(): Promise<string[]> {
    return Array.from(this.patterns.keys());
  }

  async validateIntent(
    intentName: string,
    userInput: string,
  ): Promise<boolean> {
    const pattern = this.patterns.get(intentName);
    return pattern ? pattern.test(userInput.toLowerCase()) : false;
  }
}

// Export singleton instance
export const nlpService = new NLUService();
export const nluService = nlpService; // Alias for compatibility

export default nlpService;
