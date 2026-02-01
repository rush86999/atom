/**
 * ATOM Search Utilities
 * Helper functions for universal search
 */

import {
  AtomSearchResult,
  AtomSearchFilters,
  AtomSearchSort,
  AtomSearchStats,
  AtomSavedSearch,
  AtomSearchConfig,
  GitLabSearchResult,
  GitHubSearchResult,
  SlackSearchResult,
  NotionSearchResult,
  GmailSearchResult,
  JiraSearchResult,
  AtomSearchQuery,
  AtomSearchResponse,
  AtomSearchSuggestion,
  AtomSearchAnalytics
} from './searchTypes';

// Integration mapping for search
export const integrationIcons = {
  gitlab: '⚡',
  github: '💻',
  slack: '💬',
  gmail: '📧',
  notion: '📝',
  jira: '🐛',
  box: '📦',
  dropbox: '☁️',
  gdrive: '📂',
  nextjs: '⚛️'
};

export const integrationColors = {
  gitlab: '#FC6D26',
  github: '#24292e',
  slack: '#4A154B',
  gmail: '#EA4335',
  notion: '#000000',
  jira: '#0052CC',
  box: '#0061D5',
  dropbox: '#0061FF',
  gdrive: '#4285F4',
  nextjs: '#000000'
};

export const typeIcons = {
  file: '📄',
  issue: '🐛',
  commit: '📝',
  message: '💬',
  task: '✅',
  document: '📋',
  project: '📁',
  user: '👤'
};

export const typeColors = {
  file: '#718096',
  issue: '#E53E3E',
  commit: '#38A169',
  message: '#3182CE',
  task: '#805AD5',
  document: '#718096',
  project: '#DD6B20',
  user: '#319795'
};

// Search utility functions
export class AtomSearchUtils {
  /**
   * Generate search ID
   */
  static generateSearchId(): string {
    return `search_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Calculate relevance score
   */
  static calculateRelevanceScore(
    query: string,
    result: AtomSearchResult,
    weights: { [key: string]: number } = {}
  ): number {
    const defaultWeights = {
      title: 0.4,
      content: 0.3,
      author: 0.15,
      tags: 0.1,
      source: 0.05
    };

    const finalWeights = { ...defaultWeights, ...weights };
    let score = 0;

    // Title match
    if (result.title.toLowerCase().includes(query.toLowerCase())) {
      score += finalWeights.title;
      // Bonus for exact match
      if (result.title.toLowerCase() === query.toLowerCase()) {
        score += finalWeights.title * 0.5;
      }
    }

    // Content/description match
    if (result.description && result.description.toLowerCase().includes(query.toLowerCase())) {
      score += finalWeights.content;
    }

    // Author match
    if (result.author && result.author.name.toLowerCase().includes(query.toLowerCase())) {
      score += finalWeights.author;
    }

    // Tags match
    if (result.tags && result.tags.some(tag => tag.toLowerCase().includes(query.toLowerCase()))) {
      score += finalWeights.tags;
    }

    // Source match
    if (result.source.toLowerCase().includes(query.toLowerCase())) {
      score += finalWeights.source;
    }

    // Date recency bonus (more recent = higher score)
    const recencyBonus = Math.max(0, 1 - (Date.now() - new Date(result.updatedAt).getTime()) / (1000 * 60 * 60 * 24 * 30));
    score += recencyBonus * 0.1;

    return Math.min(100, score * 100);
  }

  /**
   * Highlight search terms in text
   */
  static highlightSearchTerms(
    text: string,
    query: string,
    className: string = 'highlight'
  ): string {
    if (!query || !text) return text;

    const words = query.toLowerCase().split(/\s+/);
    let highlightedText = text;

    words.forEach(word => {
      const regex = new RegExp(`(${word})`, 'gi');
      highlightedText = highlightedText.replace(regex, `<mark class="${className}">$1</mark>`);
    });

    return highlightedText;
  }

  /**
   * Filter search results
   */
  static filterSearchResults(
    results: AtomSearchResult[],
    filters: AtomSearchFilters
  ): AtomSearchResult[] {
    return results.filter(result => {
      // Source filter
      if (filters.sources.length > 0 && !filters.sources.includes(result.source)) {
        return false;
      }

      // Type filter
      if (filters.types.length > 0 && !filters.types.includes(result.type)) {
        return false;
      }

      // Date range filter
      if (filters.dateRange.from) {
        const resultDate = new Date(result.createdAt);
        const filterDate = new Date(filters.dateRange.from);
        if (resultDate < filterDate) {
          return false;
        }
      }

      if (filters.dateRange.to) {
        const resultDate = new Date(result.createdAt);
        const filterDate = new Date(filters.dateRange.to);
        if (resultDate > filterDate) {
          return false;
        }
      }

      // Author filter
      if (filters.authors.length > 0 && result.author) {
        const hasAuthor = filters.authors.includes(result.author.name) ||
                        filters.authors.includes(result.author.username || '');
        if (!hasAuthor) {
          return false;
        }
      }

      // Tag filter
      if (filters.tags.length > 0 && result.tags) {
        const hasAllTags = filters.tags.every(tag => result.tags!.includes(tag));
        if (!hasAllTags) {
          return false;
        }
      }

      // Status filter
      if (filters.status.length > 0 && result.status) {
        if (!filters.status.includes(result.status)) {
          return false;
        }
      }

      // Priority filter
      if (filters.priority.length > 0 && result.priority) {
        if (!filters.priority.includes(result.priority)) {
          return false;
        }
      }

      // Size range filter
      if (filters.sizeRange && result.size) {
        const { min, max } = filters.sizeRange;
        if (result.size < min || result.size > max) {
          return false;
        }
      }

      // Special filters
      if (!filters.includeArchived && result.status === 'archived') {
        return false;
      }

      if (!filters.includeDeleted && result.status === 'deleted') {
        return false;
      }

      // Integration-specific filters
      if (filters.integrationFilters) {
        const sourceFilters = filters.integrationFilters[result.source];
        if (sourceFilters) {
          if (!this.applyIntegrationSpecificFilters(result, sourceFilters)) {
            return false;
          }
        }
      }

      return true;
    });
  }

  /**
   * Apply integration-specific filters
   */
  static applyIntegrationSpecificFilters(
    result: AtomSearchResult,
    filters: Record<string, any>
  ): boolean {
    switch (result.source) {
      case 'gitlab':
        return this.applyGitLabFilters(result as GitLabSearchResult, filters);
      case 'github':
        return this.applyGitHubFilters(result as GitHubSearchResult, filters);
      case 'slack':
        return this.applySlackFilters(result as SlackSearchResult, filters);
      case 'gmail':
        return this.applyGmailFilters(result as GmailSearchResult, filters);
      case 'notion':
        return this.applyNotionFilters(result as NotionSearchResult, filters);
      case 'jira':
        return this.applyJiraFilters(result as JiraSearchResult, filters);
      default:
        return true;
    }
  }

  /**
   * Apply GitLab-specific filters
   */
  static applyGitLabFilters(
    result: GitLabSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Visibility filter
    if (filters.visibility && filters.visibility.length > 0) {
      if (!filters.visibility.includes(result.metadata.visibility)) {
        return false;
      }
    }

    // Archived filter
    if (filters.archived !== undefined) {
      if (result.metadata.archived !== filters.archived) {
        return false;
      }
    }

    // Star count filter
    if (filters.starRange) {
      const { min, max } = filters.starRange;
      const stars = result.metadata.starCount || 0;
      if (stars < min || stars > max) {
        return false;
      }
    }

    // Fork count filter
    if (filters.forkRange) {
      const { min, max } = filters.forkRange;
      const forks = result.metadata.forksCount || 0;
      if (forks < min || forks > max) {
        return false;
      }
    }

    return true;
  }

  /**
   * Apply GitHub-specific filters
   */
  static applyGitHubFilters(
    result: GitHubSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Private filter
    if (filters.private !== undefined) {
      if (result.metadata.private !== filters.private) {
        return false;
      }
    }

    // Language filter
    if (filters.language && result.metadata.language) {
      if (result.metadata.language.toLowerCase() !== filters.language.toLowerCase()) {
        return false;
      }
    }

    // Topics filter
    if (filters.topics && filters.topics.length > 0) {
      const hasAllTopics = filters.topics.every((topic: string) =>
        result.metadata.topics?.includes(topic)
      );
      if (!hasAllTopics) {
        return false;
      }
    }

    return true;
  }

  /**
   * Apply Slack-specific filters
   */
  static applySlackFilters(
    result: SlackSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Channel filter
    if (filters.channel && filters.channel.length > 0) {
      if (!filters.channel.includes(result.metadata.channelId)) {
        return false;
      }
    }

    // Team filter
    if (filters.team && filters.team.length > 0) {
      if (!filters.team.includes(result.metadata.teamId)) {
        return false;
      }
    }

    // Reaction filter
    if (filters.hasReactions && !result.metadata.reactions?.length) {
      return false;
    }

    return true;
  }

  /**
   * Apply Gmail-specific filters
   */
  static applyGmailFilters(
    result: GmailSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Label filter
    if (filters.labels && filters.labels.length > 0) {
      const hasAllLabels = filters.labels.every((label: string) =>
        result.metadata.labels.includes(label)
      );
      if (!hasAllLabels) {
        return false;
      }
    }

    // Starred filter
    if (filters.starred !== undefined) {
      if (result.metadata.starred !== filters.starred) {
        return false;
      }
    }

    // Unread filter
    if (filters.unread !== undefined) {
      if (result.metadata.unread !== filters.unread) {
        return false;
      }
    }

    // Attachment filter
    if (filters.hasAttachments) {
      if (!result.metadata.attachments?.length) {
        return false;
      }
    }

    return true;
  }

  /**
   * Apply Notion-specific filters
   */
  static applyNotionFilters(
    result: NotionSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Database filter
    if (filters.database && filters.database.length > 0) {
      if (!filters.database.includes(result.metadata.databaseId || '')) {
        return false;
      }
    }

    // Archived filter
    if (filters.archived !== undefined) {
      if (result.metadata.archived !== filters.archived) {
        return false;
      }
    }

    // Parent filter
    if (filters.parent && filters.parent.length > 0) {
      const parentType = result.metadata.parent?.type;
      if (!parentType || !filters.parent.includes(parentType)) {
        return false;
      }
    }

    return true;
  }

  /**
   * Apply Jira-specific filters
   */
  static applyJiraFilters(
    result: JiraSearchResult,
    filters: Record<string, any>
  ): boolean {
    // Issue type filter
    if (filters.issueTypes && filters.issueTypes.length > 0) {
      if (!filters.issueTypes.includes(result.metadata.issueType.name)) {
        return false;
      }
    }

    // Priority filter
    if (filters.priorities && filters.priorities.length > 0) {
      const priority = result.metadata.priority?.name;
      if (!priority || !filters.priorities.includes(priority)) {
        return false;
      }
    }

    // Component filter
    if (filters.components && filters.components.length > 0) {
      const hasComponent = result.metadata.components?.some((component: any) =>
        filters.components.includes(component.name)
      );
      if (!hasComponent) {
        return false;
      }
    }

    // Due date filter
    if (filters.dueDateRange) {
      if (result.metadata.dueDate) {
        const dueDate = new Date(result.metadata.dueDate);
        const { min, max } = filters.dueDateRange;
        if (dueDate < new Date(min) || dueDate > new Date(max)) {
          return false;
        }
      }
    }

    return true;
  }

  /**
   * Sort search results
   */
  static sortSearchResults(
    results: AtomSearchResult[],
    sort: AtomSearchSort
  ): AtomSearchResult[] {
    return [...results].sort((a, b) => {
      let aValue: any = a[sort.field];
      let bValue: any = b[sort.field];

      // Handle nested fields
      if (sort.field.includes('.')) {
        const nestedFields = sort.field.split('.');
        aValue = nestedFields.reduce((obj, key) => obj?.[key], a);
        bValue = nestedFields.reduce((obj, key) => obj?.[key], b);
      }

      // Handle score field
      if (sort.field === 'score') {
        aValue = a.score || 0;
        bValue = b.score || 0;
      }

      // Handle date fields
      if (sort.field.includes('At')) {
        aValue = new Date(aValue).getTime();
        bValue = new Date(bValue).getTime();
      }

      // Handle string comparison
      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (aValue < bValue) {
        return sort.direction === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sort.direction === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  }

  /**
   * Group search results
   */
  static groupSearchResults(
    results: AtomSearchResult[],
    groupBy: string
  ): { [key: string]: AtomSearchResult[] } {
    return results.reduce((groups, result) => {
      let key: string;

      switch (groupBy) {
        case 'source':
          key = result.source;
          break;
        case 'type':
          key = result.type;
          break;
        case 'date':
          key = new Date(result.updatedAt).toDateString();
          break;
        case 'author':
          key = result.author?.name || 'Unknown';
          break;
        default:
          key = 'default';
      }

      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push(result);
      return groups;
    }, {} as { [key: string]: AtomSearchResult[] });
  }

  /**
   * Generate search suggestions
   */
  static generateSearchSuggestions(
    query: string,
    history: string[],
    results: AtomSearchResult[]
  ): AtomSearchSuggestion[] {
    const suggestions: AtomSearchSuggestion[] = [];
    const lowerQuery = query.toLowerCase();

    // Query suggestions from history
    history.forEach(term => {
      if (term.toLowerCase().includes(lowerQuery) && term.toLowerCase() !== lowerQuery) {
        suggestions.push({
          text: term,
          type: 'query',
          count: 1,
          lastUsed: new Date().toISOString()
        });
      }
    });

    // Source suggestions
    const sources = [...new Set(results.map(r => r.source))];
    sources.forEach(source => {
      if (source.toLowerCase().includes(lowerQuery)) {
        suggestions.push({
          text: source,
          type: 'source',
          count: results.filter(r => r.source === source).length
        });
      }
    });

    // Type suggestions
    const types = [...new Set(results.map(r => r.type))];
    types.forEach(type => {
      if (type.toLowerCase().includes(lowerQuery)) {
        suggestions.push({
          text: type,
          type: 'type',
          count: results.filter(r => r.type === type).length
        });
      }
    });

    return suggestions
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }

  /**
   * Calculate search statistics
   */
  static calculateSearchStats(results: AtomSearchResult[], time: number): AtomSearchStats {
    const sources = new Set(results.map(r => r.source));
    const types = new Set(results.map(r => r.type));

    return {
      total: results.length,
      sources: sources.size,
      types: types.size,
      time,
      aggregated: Array.from(sources).reduce((acc, source) => {
        acc[source] = {
          count: results.filter(r => r.source === source).length,
          time: time / sources.size,
          types: [...new Set(results.filter(r => r.source === source).map(r => r.type))]
        };
        return acc;
      }, {} as { [source: string]: { count: number; time: number; types: string[] } })
    };
  }

  /**
   * Format search time
   */
  static formatSearchTime(time: number): string {
    if (time < 1000) {
      return `${time}ms`;
    } else if (time < 60000) {
      return `${(time / 1000).toFixed(1)}s`;
    } else {
      return `${(time / 60000).toFixed(1)}m`;
    }
  }

  /**
   * Get relative time string
   */
  static getRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return 'just now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}h ago`;
    } else if (diffInSeconds < 604800) {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}d ago`;
    } else if (diffInSeconds < 2629746) {
      const weeks = Math.floor(diffInSeconds / 604800);
      return `${weeks}w ago`;
    } else {
      const years = Math.floor(diffInSeconds / 2629746);
      return `${years}y ago`;
    }
  }

  /**
   * Format file size
   */
  static formatFileSize(bytes?: number): string {
    if (!bytes) return 'N/A';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  }

  /**
   * Validate search query
   */
  static validateSearchQuery(query: string): {
    isValid: boolean;
    errors: string[];
    suggestions: string[];
  } {
    const errors: string[] = [];
    const suggestions: string[] = [];

    // Check minimum length
    if (query.length < 2) {
      errors.push('Search query must be at least 2 characters long');
    }

    // Check for special operators
    if (query.includes('AND') || query.includes('OR') || query.includes('NOT')) {
      suggestions.push('Use advanced filters instead of operators for better results');
    }

    // Check for common typos
    const commonTypos: { [key: string]: string } = {
      'gitlub': 'gitlab',
      'guthub': 'github',
      'slak': 'slack',
      'gmaul': 'gmail',
      'notian': 'notion',
      'jirra': 'jira'
    };

    const words = query.toLowerCase().split(/\s+/);
    words.forEach(word => {
      if (commonTypos[word]) {
        suggestions.push(`Did you mean "${commonTypos[word]}"?`);
      }
    });

    return {
      isValid: errors.length === 0,
      errors,
      suggestions
    };
  }

  /**
   * Export search results
   */
  static exportSearchResults(
    results: AtomSearchResult[],
    format: 'json' | 'csv' | 'xml',
    query?: string
  ): string {
    switch (format) {
      case 'json':
        return JSON.stringify({
          query,
          timestamp: new Date().toISOString(),
          total: results.length,
          results: results.map(r => ({
            id: r.id,
            type: r.type,
            title: r.title,
            description: r.description,
            source: r.source,
            url: r.url,
            createdAt: r.createdAt,
            updatedAt: r.updatedAt,
            author: r.author,
            tags: r.tags,
            metadata: r.metadata
          }))
        }, null, 2);

      case 'csv':
        const headers = ['ID', 'Type', 'Title', 'Description', 'Source', 'URL', 'Created', 'Updated', 'Author', 'Tags'];
        const csvRows = [
          headers.join(','),
          ...results.map(r => [
            `"${r.id}"`,
            `"${r.type}"`,
            `"${r.title}"`,
            `"${r.description || ''}"`,
            `"${r.source}"`,
            `"${r.url || ''}"`,
            `"${r.createdAt}"`,
            `"${r.updatedAt}"`,
            `"${r.author?.name || ''}"`,
            `"${r.tags?.join(';') || ''}"`
          ].join(','))
        ];
        return csvRows.join('\n');

      case 'xml':
        const xmlItems = results.map(r => `
          <item>
            <id>${r.id}</id>
            <type>${r.type}</type>
            <title><![CDATA[${r.title}]]></title>
            <description><![CDATA[${r.description || ''}]]></description>
            <source>${r.source}</source>
            <url>${r.url || ''}</url>
            <created_at>${r.createdAt}</created_at>
            <updated_at>${r.updatedAt}</updated_at>
            <author>${r.author?.name || ''}</author>
            <tags>${r.tags?.join(',') || ''}</tags>
            <metadata>${JSON.stringify(r.metadata)}</metadata>
          </item>
        `);
        
        return `<?xml version="1.0" encoding="UTF-8"?>
          <search_results query="${query}" timestamp="${new Date().toISOString()}" total="${results.length}">
            ${xmlItems.join('')}
          </search_results>`;

      default:
        return JSON.stringify(results, null, 2);
    }
  }

  /**
   * Create search query from filters
   */
  static createSearchQueryFromFilters(filters: AtomSearchFilters): string {
    const queryParts: string[] = [];

    // Source filters
    if (filters.sources.length > 0) {
      queryParts.push(`source:(${filters.sources.join(' OR ')})`);
    }

    // Type filters
    if (filters.types.length > 0) {
      queryParts.push(`type:(${filters.types.join(' OR ')})`);
    }

    // Author filters
    if (filters.authors.length > 0) {
      queryParts.push(`author:(${filters.authors.join(' OR ')})`);
    }

    // Tag filters
    if (filters.tags.length > 0) {
      queryParts.push(`tag:(${filters.tags.join(' OR ')})`);
    }

    // Status filters
    if (filters.status.length > 0) {
      queryParts.push(`status:(${filters.status.join(' OR ')})`);
    }

    // Priority filters
    if (filters.priority.length > 0) {
      queryParts.push(`priority:(${filters.priority.join(' OR ')})`);
    }

    // Date range filters
    if (filters.dateRange.from) {
      queryParts.push(`after:${filters.dateRange.from}`);
    }
    if (filters.dateRange.to) {
      queryParts.push(`before:${filters.dateRange.to}`);
    }

    // Special filters
    if (filters.includeArchived) {
      queryParts.push('archived:true');
    }
    if (filters.includeDeleted) {
      queryParts.push('deleted:true');
    }

    return queryParts.join(' ');
  }

  /**
   * Parse search query string
   */
  static parseSearchQuery(query: string): {
    text: string;
    filters: Partial<AtomSearchFilters>;
  } {
    const filters: Partial<AtomSearchFilters> = {};
    let text = query;

    // Extract filter patterns like source:gitlab
    const filterPattern = /(\w+):(\([^)]+\)|[^\s]+)/g;
    const filterMatches = query.match(filterPattern);

    if (filterMatches) {
      filterMatches.forEach(match => {
        const [fullMatch, key, value] = match.match(/(\w+):(\([^)]+\)|[^\s]+)/) || [];
        
        // Remove the filter from the text
        text = text.replace(fullMatch, '').trim();

        // Parse the value
        let parsedValue = value;
        if (value.startsWith('(') && value.endsWith(')')) {
          // Remove parentheses and split by OR
          parsedValue = value.slice(1, -1).split(' OR ').map(v => v.trim()).filter(v => v);
        }

        // Apply filter based on key
        switch (key) {
          case 'source':
            filters.sources = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'type':
            filters.types = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'author':
            filters.authors = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'tag':
            filters.tags = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'status':
            filters.status = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'priority':
            filters.priority = Array.isArray(parsedValue) ? parsedValue : [parsedValue];
            break;
          case 'after':
            filters.dateRange = { ...filters.dateRange, from: parsedValue };
            break;
          case 'before':
            filters.dateRange = { ...filters.dateRange, to: parsedValue };
            break;
        }
      });
    }

    return { text, filters };
  }

  /**
   * Get default search configuration
   */
  static getDefaultSearchConfig(): AtomSearchConfig {
    return {
      maxResults: 50,
      defaultSort: { field: 'relevance', direction: 'desc' },
      enableFuzzySearch: true,
      enablePhoneticSearch: false,
      enableSemanticSearch: true,
      searchTimeout: 5000,
      showHighlights: true,
      showMetadata: true,
      showPreview: false,
      groupResults: false,
      groupBy: 'source',
      enableCaching: true,
      cacheTimeout: 300000, // 5 minutes
      enablePrefetch: true,
      batchSize: 20,
      trackSearches: true,
      retainHistory: 30, // days
      anonymizeHistory: true,
      enabledSources: [],
      sourcePriorities: {},
      sourceWeights: {}
    };
  }

  /**
   * Generate search analytics
   */
  static generateSearchAnalytics(
    query: string,
    results: AtomSearchResult[],
    userId?: string,
    sessionId?: string
  ): AtomSearchAnalytics {
    return {
      query,
      timestamp: new Date().toISOString(),
      userId: userId || 'anonymous',
      sessionId: sessionId || this.generateSearchId(),
      resultsCount: results.length,
      clickCount: 0, // Will be updated when user clicks results
      timeSpent: 0, // Will be tracked
      filters: [],
      sources: [...new Set(results.map(r => r.source))],
      types: [...new Set(results.map(r => r.type))],
      resultIds: results.map(r => r.id),
      clickedResultIds: [],
      bounced: results.length === 0,
      converted: false // Will be updated based on user actions
    };
  }
}

export default AtomSearchUtils;