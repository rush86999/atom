/**
 * Enhanced Zendesk Integration Skills with AI Integration
 * Advanced Zendesk API interactions with AI-powered customer support features
 * Following ATOM patterns for integration services
 */

import { api } from '../../../services/api';
import { zendeskSkills, ZendeskTokens, ZendeskTicket, ZendeskUser, ZendeskGroup, ZendeskOrganization } from './zendeskSkills';

export interface ZendeskAIPrediction {
  type: 'ticket_priority' | 'ticket_category' | 'churn_risk' | 'satisfaction' | 'response_time';
  confidence: number;
  prediction: any;
  reasoning: string;
  impact: 'high' | 'medium' | 'low';
  actionable: boolean;
}

export interface ZendeskAIInsight {
  type: 'sentiment' | 'trend' | 'anomaly' | 'recommendation' | 'performance';
  title: string;
  description: string;
  confidence: number;
  recommendation?: string;
  impact: 'high' | 'medium' | 'low';
  entityId?: number;
  entityType?: 'ticket' | 'user' | 'group' | 'organization';
  generatedAt: string;
  actionable: boolean;
}

export interface ZendeskSentiment {
  score: number; // -1 to 1 (negative to positive)
  label: 'very_negative' | 'negative' | 'neutral' | 'positive' | 'very_positive';
  confidence: number;
  emotions: {
    anger?: number;
    joy?: number;
    sadness?: number;
    fear?: number;
    disgust?: number;
    surprise?: number;
  };
  keywords: Array<{
    text: string;
    sentiment: number;
    importance: number;
  }>;
}

export interface ZendeskTicketAnalytics {
  ticketId: number;
  sentiment: ZendeskSentiment;
  priorityPrediction: {
    currentPriority: string;
    predictedPriority: string;
    confidence: number;
    factors: string[];
  };
  categoryPrediction: {
    currentType: string;
    predictedType: string;
    confidence: number;
    reasoning: string;
  };
  responseTimePrediction: {
    estimatedMinutes: number;
    confidence: number;
    factors: string[];
  };
  churnRiskAnalysis: {
    riskLevel: 'low' | 'medium' | 'high';
    riskScore: number;
    factors: Array<{
      factor: string;
      impact: number;
      description: string;
    }>;
    recommendations: string[];
  };
  satisfactionPrediction: {
    predictedScore: 'good' | 'bad';
    confidence: number;
    factors: Array<{
      factor: string;
      positive: boolean;
      weight: number;
    }>;
  };
}

export interface ZendeskUserAnalytics {
  userId: number;
  customerHealth: {
    score: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    trend: 'improving' | 'stable' | 'declining';
    factors: Array<{
      factor: string;
      value: number;
      impact: number;
    }>;
  };
  satisfactionHistory: Array<{
    ticketId: number;
    score: string;
    comment: string;
    date: string;
    sentiment: ZendeskSentiment;
  }>;
  churnRisk: {
    riskLevel: 'low' | 'medium' | 'high';
    riskScore: number;
    probability: number;
    warningSigns: string[];
    retentionActions: string[];
  };
  communicationProfile: {
    preferredChannel: string;
    averageResponseTime: number;
    sentimentBaseline: ZendeskSentiment;
    communicationStyle: 'formal' | 'casual' | 'technical' | 'emotional';
    interactionPatterns: Array<{
      pattern: string;
      frequency: number;
      impact: number;
    }>;
  };
  valueSegment: 'enterprise' | 'mid-market' | 'small-business' | 'starter';
  lifetimeValue: number;
  upgradePotential: {
    probability: number;
    targetPlan: string;
    reasoning: string;
    recommendedActions: string[];
  };
}

export interface ZendeskTeamAnalytics {
  groupId: number;
  performanceMetrics: {
    averageResponseTime: number;
    averageResolutionTime: number;
    customerSatisfactionScore: number;
    ticketsHandled: number;
    ticketsReopened: number;
    firstContactResolution: number;
  };
  efficiencyAnalysis: {
    score: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    strengths: string[];
    improvementAreas: string[];
    benchmarks: Array<{
      metric: string;
      current: number;
      target: number;
      industry: number;
    }>;
  };
  workDistribution: Array<{
    agentId: number;
    agentName: string;
    ticketsHandled: number;
    averageResolutionTime: number;
    satisfactionScore: number;
    efficiency: number;
  }>;
  workloadAnalysis: {
    currentLoad: number;
    capacityUtilization: number;
    forecastedLoad: Array<{
      date: string;
      predictedLoad: number;
      confidence: number;
    }>;
    recommendations: Array<{
      type: 'staffing' | 'routing' | 'automation' | 'training';
      priority: 'high' | 'medium' | 'low';
      description: string;
      expectedImpact: string;
    }>;
  };
  collaborationInsights: {
    collaborationScore: number;
    knowledgeSharing: number;
    teamworkEfficiency: number;
    bottlenecks: string[];
    improvementOpportunities: string[];
  };
}

export interface ZendeskBusinessIntelligence {
  overallMetrics: {
    totalTickets: number;
    resolvedTickets: number;
    customerSatisfaction: number;
    averageResponseTime: number;
    averageResolutionTime: number;
    firstContactResolution: number;
    ticketsReopened: number;
    escalationRate: number;
    abandonmentRate: number;
  };
  trendAnalysis: {
    ticketVolume: Array<{
      date: string;
      count: number;
      trend: 'increasing' | 'decreasing' | 'stable';
      seasonality: boolean;
    }>;
    satisfaction: Array<{
      date: string;
      score: number;
      trend: 'improving' | 'declining' | 'stable';
    }>;
    responseTime: Array<{
      date: string;
      average: number;
      trend: 'improving' | 'declining' | 'stable';
    }>;
  };
  sentimentAnalysis: {
    overallSentiment: ZendeskSentiment;
    sentimentTrend: Array<{
      date: string;
      sentiment: number;
      label: string;
    }>;
    emotionDistribution: {
      [emotion: string]: number;
    };
    sentimentByCategory: {
      [category: string]: ZendeskSentiment;
    };
    sentimentByPriority: {
      [priority: string]: ZendeskSentiment;
    };
  };
  predictiveAnalytics: {
    ticketVolumeForecast: Array<{
      date: string;
      predicted: number;
      confidence: number;
      factors: string[];
    }>;
    satisfactionForecast: Array<{
      date: string;
      predicted: number;
      confidence: number;
      factors: string[];
    }>;
    resourceRequirements: Array<{
      resourceType: string;
      currentCapacity: number;
      requiredCapacity: number;
      urgency: 'critical' | 'high' | 'medium' | 'low';
      timeframe: string;
    }>;
  };
  operationalInsights: {
    bottlenecks: Array<{
      type: 'process' | 'technology' | 'people' | 'knowledge';
      description: string;
      impact: 'high' | 'medium' | 'low';
      affectedMetrics: string[];
      recommendations: string[];
    }>;
    opportunities: Array<{
      type: 'automation' | 'process_improvement' | 'knowledge_enhancement' | 'staff_training';
      description: string;
      potentialSavings: number;
      implementationComplexity: 'low' | 'medium' | 'high';
      expectedROI: number;
    }>;
    riskFactors: Array<{
      type: 'operational' | 'customer_satisfaction' | 'compliance' | 'financial';
      description: string;
      probability: 'low' | 'medium' | 'high';
      impact: 'high' | 'medium' | 'low';
      mitigation: string[];
    }>;
  };
}

class ZendeskSkillsEnhanced {
  private readonly baseUrl = '/api/zendesk';
  private readonly authUrl = '/auth/zendesk';

  // Enhanced authentication methods
  async getStoredTokens(): Promise<ZendeskTokens | null> {
    return await zendeskSkills.getStoredTokens();
  }

  async initiateOAuth(): Promise<void> {
    return await zendeskSkills.initiateOAuth();
  }

  async handleOAuthCallback(code: string, state: string): Promise<ZendeskTokens> {
    return await zendeskSkills.handleOAuthCallback(code, state);
  }

  async revokeAuthentication(): Promise<void> {
    return await zendeskSkills.revokeAuthentication();
  }

  // Enhanced Ticket methods with AI
  async getTicketsWithAI(options: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: string;
    status?: string;
    priority?: string;
    type?: string;
    assigneeId?: number;
    groupId?: number;
    requesterId?: number;
    organizationId?: number;
    dateRange?: { from: string; to: string };
    includeAnalytics?: boolean;
    includePredictions?: boolean;
  } = {}): Promise<{
    tickets: ZendeskTicket[];
    count: number;
    analytics?: Array<{
      ticketId: number;
      analytics: ZendeskTicketAnalytics;
    }>;
    predictions?: Array<{
      ticketId: number;
      predictions: ZendeskAIPrediction[];
    }>;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      
      // Basic filters
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.sort) params.append('sort', options.sort);
      if (options.status) params.append('status', options.status);
      if (options.priority) params.append('priority', options.priority);
      if (options.type) params.append('type', options.type);
      if (options.assigneeId) params.append('assignee_id', options.assigneeId.toString());
      if (options.groupId) params.append('group_id', options.groupId.toString());
      if (options.requesterId) params.append('requester_id', options.requesterId.toString());
      if (options.organizationId) params.append('organization_id', options.organizationId.toString());
      
      // Date range
      if (options.dateRange) {
        params.append('from', options.dateRange.from);
        params.append('to', options.dateRange.to);
      }
      
      // AI features
      if (options.includeAnalytics) params.append('include_analytics', 'true');
      if (options.includePredictions) params.append('include_predictions', 'true');

      const response = await api.get(`${this.baseUrl}/tickets/ai?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get tickets with AI: ${error.message}`);
    }
  }

  async getTicketWithAI(ticketId: number, options: {
    includeAnalytics?: boolean;
    includePredictions?: boolean;
    includeHistory?: boolean;
    includeSimilarTickets?: boolean;
  } = {}): Promise<{
    ticket: ZendeskTicket;
    analytics?: ZendeskTicketAnalytics;
    predictions?: ZendeskAIPrediction[];
    history?: Array<{
      date: string;
      action: string;
      field: string;
      oldValue: any;
      newValue: any;
      userId: number;
      userName: string;
    }>;
    similarTickets?: Array<{
      ticket: ZendeskTicket;
      similarity: number;
      relevantFactors: string[];
    }>;
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.includeAnalytics) params.append('include_analytics', 'true');
      if (options.includePredictions) params.append('include_predictions', 'true');
      if (options.includeHistory) params.append('include_history', 'true');
      if (options.includeSimilarTickets) params.append('include_similar', 'true');

      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}/ai?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get ticket with AI: ${error.message}`);
    }
  }

  async createTicketWithAI(ticketData: any, options: {
    analyzeSentiment?: boolean;
    predictPriority?: boolean;
    suggestCategory?: boolean;
    optimizeRouting?: boolean;
  } = {}): Promise<{
    ticket: ZendeskTicket;
    aiAnalysis?: {
      sentiment: ZendeskSentiment;
      suggestedPriority: string;
      suggestedCategory: string;
      recommendedAssignee: {
        agentId: number;
        agentName: string;
        confidence: number;
      };
      routingOptimization: {
        group: string;
        reason: string;
        expectedReduction: number;
      };
    };
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.analyzeSentiment) params.append('analyze_sentiment', 'true');
      if (options.predictPriority) params.append('predict_priority', 'true');
      if (options.suggestCategory) params.append('suggest_category', 'true');
      if (options.optimizeRouting) params.append('optimize_routing', 'true');

      const response = await api.post(`${this.baseUrl}/tickets/ai?${params}`, ticketData);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create ticket with AI: ${error.message}`);
    }
  }

  async analyzeTicketContent(content: {
    subject: string;
    description: string;
    attachments?: Array<{
      content: string;
      filename: string;
    }>;
  }): Promise<{
    sentiment: ZendeskSentiment;
    suggestedPriority: {
      priority: string;
      confidence: number;
      factors: string[];
    };
    suggestedCategory: {
      type: string;
      confidence: number;
      reasoning: string;
    };
    urgencyIndicators: Array<{
      indicator: string;
      severity: 'high' | 'medium' | 'low';
      description: string;
    }>;
    suggestedResponses: Array<{
      response: string;
      confidence: number;
      tone: string;
    }>;
    detectedEntities: Array<{
      type: string;
      value: string;
      confidence: number;
    }>;
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/tickets/analyze`, content);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to analyze ticket content: ${error.message}`);
    }
  }

  // Enhanced User methods with AI
  async getUsersWithAI(options: {
    limit?: number;
    offset?: number;
    search?: string;
    role?: string;
    status?: string;
    organizationId?: number;
    includeAnalytics?: boolean;
    includeChurnRisk?: boolean;
    includeValueSegment?: boolean;
  } = {}): Promise<{
    users: ZendeskUser[];
    count: number;
    analytics?: Array<{
      userId: number;
      analytics: ZendeskUserAnalytics;
    }>;
    next_page?: string;
    previous_page?: string;
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.limit) params.append('limit', options.limit.toString());
      if (options.offset) params.append('offset', options.offset.toString());
      if (options.search) params.append('search', options.search);
      if (options.role) params.append('role', options.role);
      if (options.status) params.append('status', options.status);
      if (options.organizationId) params.append('organization_id', options.organizationId.toString());
      
      if (options.includeAnalytics) params.append('include_analytics', 'true');
      if (options.includeChurnRisk) params.append('include_churn_risk', 'true');
      if (options.includeValueSegment) params.append('include_value_segment', 'true');

      const response = await api.get(`${this.baseUrl}/users/ai?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get users with AI: ${error.message}`);
    }
  }

  async getUserWithAI(userId: number, options: {
    includeAnalytics?: boolean;
    includePredictions?: boolean;
    includeHistory?: boolean;
    includeInteractions?: boolean;
  } = {}): Promise<{
    user: ZendeskUser;
    analytics?: ZendeskUserAnalytics;
    predictions?: ZendeskAIPrediction[];
    history?: Array<{
      date: string;
      action: string;
      details: any;
    }>;
    interactions?: Array<{
      type: string;
      date: string;
      description: string;
      sentiment: ZendeskSentiment;
    }>;
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.includeAnalytics) params.append('include_analytics', 'true');
      if (options.includePredictions) params.append('include_predictions', 'true');
      if (options.includeHistory) params.append('include_history', 'true');
      if (options.includeInteractions) params.append('include_interactions', 'true');

      const response = await api.get(`${this.baseUrl}/users/${userId}/ai?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get user with AI: ${error.message}`);
    }
  }

  async analyzeCustomerProfile(userId: number): Promise<ZendeskUserAnalytics> {
    try {
      const response = await api.get(`${this.baseUrl}/users/${userId}/profile/ai`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to analyze customer profile: ${error.message}`);
    }
  }

  // Enhanced Team/Group methods with AI
  async getTeamAnalytics(groupId: number, dateRange?: { from: string; to: string }): Promise<ZendeskTeamAnalytics> {
    try {
      const params = new URLSearchParams();
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/groups/${groupId}/analytics/ai?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get team analytics: ${error.message}`);
    }
  }

  async optimizeTeamPerformance(groupId: number): Promise<{
    currentPerformance: ZendeskTeamAnalytics;
    optimizationRecommendations: Array<{
      type: string;
      description: string;
      expectedImprovement: number;
      implementationComplexity: 'low' | 'medium' | 'high';
      timeline: string;
      resources: string[];
    }>;
    quickWins: Array<{
      action: string;
      impact: string;
      effort: 'low' | 'medium' | 'high';
    }>;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/groups/${groupId}/optimize`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to optimize team performance: ${error.message}`);
    }
  }

  // Business Intelligence methods
  async getBusinessIntelligence(dateRange?: { from: string; to: string }, options: {
    includeTrends?: boolean;
    includePredictions?: boolean;
    includeSentimentAnalysis?: boolean;
    includeOperationalInsights?: boolean;
  } = {}): Promise<ZendeskBusinessIntelligence> {
    try {
      const params = new URLSearchParams();
      
      if (dateRange) {
        params.append('from', dateRange.from);
        params.append('to', dateRange.to);
      }
      
      if (options.includeTrends) params.append('include_trends', 'true');
      if (options.includePredictions) params.append('include_predictions', 'true');
      if (options.includeSentimentAnalysis) params.append('include_sentiment', 'true');
      if (options.includeOperationalInsights) params.append('include_insights', 'true');

      const response = await api.get(`${this.baseUrl}/intelligence?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get business intelligence: ${error.message}`);
    }
  }

  // AI Insights and Predictions
  async getAIInsights(options?: {
    type?: 'all' | 'sentiment' | 'trend' | 'anomaly' | 'recommendation' | 'performance';
    entityType?: 'all' | 'ticket' | 'user' | 'group' | 'organization';
    impact?: 'all' | 'high' | 'medium' | 'low';
    limit?: number;
    dateRange?: { from: string; to: string };
  } = {}): Promise<{
    insights: ZendeskAIInsight[];
    summary: {
      highImpactCount: number;
      actionableCount: number;
      byType: { [type: string]: number };
      byEntityType: { [entityType: string]: number };
    };
    trends: Array<{
      insightType: string;
      trend: 'increasing' | 'decreasing' | 'stable';
      changeRate: number;
      significance: 'high' | 'medium' | 'low';
    }>;
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.type && options.type !== 'all') params.append('type', options.type);
      if (options.entityType && options.entityType !== 'all') params.append('entity_type', options.entityType);
      if (options.impact && options.impact !== 'all') params.append('impact', options.impact);
      if (options.limit) params.append('limit', options.limit.toString());
      
      if (options.dateRange) {
        params.append('from', options.dateRange.from);
        params.append('to', options.dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/ai/insights?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get AI insights: ${error.message}`);
    }
  }

  async getPredictions(options: {
    type?: 'all' | 'ticket_priority' | 'ticket_category' | 'churn_risk' | 'satisfaction' | 'response_time';
    entityType?: 'all' | 'ticket' | 'user' | 'group';
    confidence?: number;
    limit?: number;
  } = {}): Promise<{
    predictions: ZendeskAIPrediction[];
    accuracy: {
      overall: number;
      byType: { [type: string]: number };
      byTimeframe: { [timeframe: string]: number };
    };
    modelPerformance: {
      precision: number;
      recall: number;
      f1Score: number;
      accuracy: number;
      lastTrained: string;
    };
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.type && options.type !== 'all') params.append('type', options.type);
      if (options.entityType && options.entityType !== 'all') params.append('entity_type', options.entityType);
      if (options.confidence) params.append('confidence', options.confidence.toString());
      if (options.limit) params.append('limit', options.limit.toString());

      const response = await api.get(`${this.baseUrl}/ai/predictions?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get predictions: ${error.message}`);
    }
  }

  // Automation and Workflow AI
  async getAutomationSuggestions(options: {
    type?: 'response' | 'routing' | 'escalation' | 'followup';
    groupId?: number;
    dateRange?: { from: string; to: string };
  } = {}): Promise<{
    suggestions: Array<{
      type: string;
      title: string;
      description: string;
      trigger: any;
      action: any;
      expectedImpact: string;
      implementationComplexity: 'low' | 'medium' | 'high';
      successProbability: number;
      potentialSavings: {
        time: number;
        cost: number;
        effort: number;
      };
    }>;
    priorities: Array<{
      suggestion: string;
      impact: 'high' | 'medium' | 'low';
      urgency: string;
    }>;
  }> {
    try {
      const params = new URLSearchParams();
      
      if (options.type) params.append('type', options.type);
      if (options.groupId) params.append('group_id', options.groupId.toString());
      
      if (options.dateRange) {
        params.append('from', options.dateRange.from);
        params.append('to', options.dateRange.to);
      }

      const response = await api.get(`${this.baseUrl}/ai/automation/suggestions?${params}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get automation suggestions: ${error.message}`);
    }
  }

  // Knowledge Base AI
  async generateKnowledgeSuggestions(ticketId: number): Promise<{
    suggestedArticles: Array<{
      title: string;
      url: string;
      relevanceScore: number;
      summary: string;
      whyRelevant: string;
    }>;
    suggestedMacros: Array<{
      title: string;
      description: string;
      relevanceScore: number;
      actions: any[];
    }>;
    suggestedResponses: Array<{
      response: string;
      tone: string;
      confidence: number;
      explanation: string;
    }>;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}/knowledge/suggestions`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to generate knowledge suggestions: ${error.message}`);
    }
  }

  // Quality Assurance AI
  async analyzeTicketQuality(ticketId: number): Promise<{
    qualityScore: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    dimensions: {
      clarity: { score: number; feedback: string[] };
      completeness: { score: number; feedback: string[] };
      professionalism: { score: number; feedback: string[] };
      efficiency: { score: number; feedback: string[] };
    };
    recommendations: Array<{
      area: string;
      improvement: string;
      priority: 'high' | 'medium' | 'low';
      expectedImpact: string;
    }>;
    bestPractices: Array<{
      practice: string;
      followed: boolean;
      importance: 'critical' | 'high' | 'medium' | 'low';
    }>;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/tickets/${ticketId}/quality`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to analyze ticket quality: ${error.message}`);
    }
  }

  // Advanced Search with AI
  async intelligentSearch(query: {
    text?: string;
    sentiment?: string;
    priority?: string;
    dateRange?: { from: string; to: string };
    customerId?: number;
    expectedOutcome?: string;
    useSemanticSearch?: boolean;
  }): Promise<{
    results: Array<{
      ticket: ZendeskTicket;
      relevanceScore: number;
      matchReasons: string[];
      semanticSimilarity?: number;
    }>;
    searchOptimizations: Array<{
      originalQuery: string;
      suggestedQuery: string;
      expectedBetterResults: number;
    }>;
    relatedInsights: Array<{
      insight: string;
      relatedResults: number;
    }>;
  }> {
    try {
      const response = await api.post(`${this.baseUrl}/search/intelligent`, query);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to perform intelligent search: ${error.message}`);
    }
  }

  // Utility methods with AI enhancements
  getStatusColor(status: string): string {
    return zendeskSkills.getStatusColor(status);
  }

  getPriorityColor(priority: string): string {
    return zendeskSkills.getPriorityColor(priority);
  }

  getTypeColor(type: string): string {
    return zendeskSkills.getTypeColor(type);
  }

  getRoleColor(role: string): string {
    return zendeskSkills.getRoleColor(role);
  }

  formatDate(dateString: string): string {
    return zendeskSkills.formatDate(dateString);
  }

  getRelativeTime(dateString: string): string {
    return zendeskSkills.getRelativeTime(dateString);
  }

  formatDuration(minutes: number): string {
    return zendeskSkills.formatDuration(minutes);
  }

  getSentimentColor(sentiment: number): string {
    if (sentiment >= 0.6) return 'green';
    if (sentiment >= 0.2) return 'yellow';
    if (sentiment >= -0.2) return 'gray';
    if (sentiment >= -0.6) return 'orange';
    return 'red';
  }

  getSentimentLabel(sentiment: number): string {
    if (sentiment >= 0.6) return 'Very Positive';
    if (sentiment >= 0.2) return 'Positive';
    if (sentiment >= -0.2) return 'Neutral';
    if (sentiment >= -0.6) return 'Negative';
    return 'Very Negative';
  }

  getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return 'green';
    if (confidence >= 0.6) return 'yellow';
    if (confidence >= 0.4) return 'orange';
    return 'red';
  }

  getRiskLevelColor(riskLevel: string): string {
    const colors: { [key: string]: string } = {
      'low': 'green',
      'medium': 'yellow',
      'high': 'red'
    };
    return colors[riskLevel] || 'gray';
  }

  getGradeColor(grade: string): string {
    const colors: { [key: string]: string } = {
      'A': 'green',
      'B': 'blue',
      'C': 'yellow',
      'D': 'orange',
      'F': 'red'
    };
    return colors[grade] || 'gray';
  }

  // Health check
  async getHealthStatus(): Promise<{
    status: 'healthy' | 'unhealthy';
    authenticated: boolean;
    lastSync?: string;
    message?: string;
    aiFeaturesEnabled: boolean;
    version: string;
    aiModelVersion: string;
    predictionAccuracy: number;
  }> {
    try {
      const response = await api.get(`${this.baseUrl}/health`);
      return response.data;
    } catch (error) {
      return {
        status: 'unhealthy',
        authenticated: false,
        message: error.message,
        aiFeaturesEnabled: false,
        version: 'unknown',
        aiModelVersion: 'unknown',
        predictionAccuracy: 0
      };
    }
  }
}

// Export singleton instances
export const zendeskSkillsEnhanced = new ZendeskSkillsEnhanced();
export default zendeskSkillsEnhanced;