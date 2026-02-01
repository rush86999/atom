import { EventEmitter } from 'events';
import { Logger } from '../../utils/logger';

// Memory types for conversation memory
export interface ConversationMemory {
  id: string;
  userId: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  embedding?: number[];
  metadata: {
    messageType: 'text' | 'voice' | 'command';
    workflowId?: string;
    intent?: string;
    entities?: string[];
    sentiment?: number;
    importance: number; // 0-1 scale
    accessCount: number;
    lastAccessed: Date;
  };
}

export interface MemoryRetrievalResult {
  memories: ConversationMemory[];
  relevanceScores: number[];
  contextSummary: string;
  memoryType: 'short-term' | 'long-term' | 'mixed';
}

export interface MemoryContext {
  shortTermMemories: ConversationMemory[];
  longTermMemories: ConversationMemory[];
  userPatterns: UserPattern[];
  conversationSummary: string;
  relevanceScore: number;
}

export interface UserPattern {
  userId: string;
  patternType: 'behavior' | 'preference' | 'workflow' | 'communication';
  patternData: any;
  confidence: number;
  lastObserved: Date;
  frequency: number;
}

export interface MemorySystemConfig {
  shortTermMemorySize: number;
  longTermMemoryThreshold: number;
  patternDetectionWindow: number;
  embeddingDimension: number;
  similarityThreshold: number;
}

/**
 * ChatMemoryIntegration System
 *
 * Implements a human-brain-like memory system for conversations with:
 * - Short-term memory (working memory for current session)
 * - Long-term memory (persistent storage in LanceDB)
 * - Pattern recognition for user behavior
 * - Context-aware memory retrieval
 */
export class ChatMemoryIntegration extends EventEmitter {
  private logger: Logger;
  private config: MemorySystemConfig;

  // Memory stores
  private shortTermMemory: Map<string, ConversationMemory[]>; // sessionId -> memories
  private longTermMemoryCache: Map<string, ConversationMemory[]>; // userId -> cached memories
  private userPatterns: Map<string, UserPattern[]>; // userId -> patterns

  // Memory management
  private memoryAccessCounts: Map<string, number>; // memoryId -> access count
  private memoryImportanceScores: Map<string, number>; // memoryId -> importance score

  constructor(config?: Partial<MemorySystemConfig>) {
    super();
    this.logger = new Logger('ChatMemoryIntegration');
    this.config = {
      shortTermMemorySize: 50,
      longTermMemoryThreshold: 0.7,
      patternDetectionWindow: 1000 * 60 * 60 * 24 * 7, // 1 week
      embeddingDimension: 1536,
      similarityThreshold: 0.6,
      ...config
    };

    this.shortTermMemory = new Map();
    this.longTermMemoryCache = new Map();
    this.userPatterns = new Map();
    this.memoryAccessCounts = new Map();
    this.memoryImportanceScores = new Map();

    this.logger.info('ChatMemoryIntegration initialized');
  }

  /**
   * Store a conversation message in memory
   */
  async storeConversation(memory: Omit<ConversationMemory, 'id' | 'timestamp'>): Promise<string> {
    const memoryId = this.generateMemoryId();
    const fullMemory: ConversationMemory = {
      ...memory,
      id: memoryId,
      timestamp: new Date()
    };

    // Store in short-term memory
    await this.storeInShortTermMemory(fullMemory);

    // Check if important enough for long-term storage
    if (this.shouldStoreInLongTermMemory(fullMemory)) {
      await this.storeInLongTermMemory(fullMemory);
    }

    // Update user patterns
    await this.updateUserPatterns(fullMemory);

    this.emit('memory-stored', { memory: fullMemory, type: 'conversation' });
    return memoryId;
  }

  /**
   * Retrieve relevant memories for a conversation context
   */
  async retrieveRelevantMemories(
    userId: string,
    sessionId: string,
    currentMessage: string,
    contextWindow: number = 10
  ): Promise<MemoryRetrievalResult> {
    const shortTerm = await this.getShortTermMemories(sessionId, contextWindow);
    const longTerm = await this.searchLongTermMemories(userId, currentMessage);
    const patterns = await this.getRelevantPatterns(userId, currentMessage);

    // Combine and rank memories
    const allMemories = this.combineAndRankMemories(shortTerm, longTerm, patterns);

    // Generate context summary
    const contextSummary = this.generateContextSummary(allMemories, currentMessage);

    return {
      memories: allMemories.slice(0, contextWindow),
      relevanceScores: allMemories.map(m => this.calculateRelevanceScore(m, currentMessage)),
      contextSummary,
      memoryType: allMemories.length > 0 ?
        (allMemories[0].timestamp.getTime() > Date.now() - 1000 * 60 * 30 ? 'short-term' : 'long-term') :
        'mixed'
    };
  }

  /**
   * Get complete memory context for enhanced responses
   */
  async getMemoryContext(
    userId: string,
    sessionId: string,
    currentMessage: string
  ): Promise<MemoryContext> {
    const retrieval = await this.retrieveRelevantMemories(userId, sessionId, currentMessage);
    const patterns = this.userPatterns.get(userId) || [];

    return {
      shortTermMemories: retrieval.memories.filter(m =>
        m.timestamp.getTime() > Date.now() - 1000 * 60 * 30 // Last 30 minutes
      ),
      longTermMemories: retrieval.memories.filter(m =>
        m.timestamp.getTime() <= Date.now() - 1000 * 60 * 30
      ),
      userPatterns: patterns.slice(0, 5), // Top 5 patterns
      conversationSummary: retrieval.contextSummary,
      relevanceScore: retrieval.relevanceScores.length > 0 ?
        Math.max(...retrieval.relevanceScores) : 0
    };
  }

  /**
   * Store in short-term memory (working memory)
   */
  private async storeInShortTermMemory(memory: ConversationMemory): Promise<void> {
    const sessionMemories = this.shortTermMemory.get(memory.sessionId) || [];

    // Add to beginning (most recent first)
    sessionMemories.unshift(memory);

    // Limit short-term memory size
    if (sessionMemories.length > this.config.shortTermMemorySize) {
      sessionMemories.splice(this.config.shortTermMemorySize);
    }

    this.shortTermMemory.set(memory.sessionId, sessionMemories);

    this.logger.debug(`Stored in short-term memory: ${memory.content.substring(0, 50)}...`);
  }

  /**
   * Store in long-term memory (LanceDB)
   */
  private async storeInLongTermMemory(memory: ConversationMemory): Promise<void> {
    try {
      // TODO: Integrate with existing LanceDB service
      // This would call the Python backend's store_conversation_context
      const longTermMemories = this.longTermMemoryCache.get(memory.userId) || [];
      longTermMemories.push(memory);
      this.longTermMemoryCache.set(memory.userId, longTermMemories);

      this.logger.info(`Stored in long-term memory: ${memory.content.substring(0, 50)}...`);
    } catch (error) {
      this.logger.error('Failed to store in long-term memory:', error);
    }
  }

  /**
   * Search long-term memories using semantic similarity
   */
  private async searchLongTermMemories(userId: string, query: string): Promise<ConversationMemory[]> {
    try {
      // TODO: Integrate with existing LanceDB search_conversation_context
      // This would call the Python backend's search function
      const userMemories = this.longTermMemoryCache.get(userId) || [];

      // Simple text-based similarity for demo
      return userMemories
        .map(memory => ({
          memory,
          similarity: this.calculateTextSimilarity(query, memory.content)
        }))
        .filter(result => result.similarity > this.config.similarityThreshold)
        .sort((a, b) => b.similarity - a.similarity)
        .map(result => result.memory)
        .slice(0, 10); // Limit results

    } catch (error) {
      this.logger.error('Failed to search long-term memories:', error);
      return [];
    }
  }

  /**
   * Get short-term memories for session
   */
  private async getShortTermMemories(sessionId: string, limit: number): Promise<ConversationMemory[]> {
    const sessionMemories = this.shortTermMemory.get(sessionId) || [];
    return sessionMemories.slice(0, limit);
  }

  /**
   * Update user patterns based on new memory
   */
  private async updateUserPatterns(memory: ConversationMemory): Promise<void> {
    const userPatterns = this.userPatterns.get(memory.userId) || [];

    // Detect workflow patterns
    if (memory.metadata.workflowId) {
      const workflowPattern = userPatterns.find(p =>
        p.patternType === 'workflow' &&
        p.patternData.workflowId === memory.metadata.workflowId
      );

      if (workflowPattern) {
        workflowPattern.frequency++;
        workflowPattern.lastObserved = new Date();
        workflowPattern.confidence = Math.min(1, workflowPattern.confidence + 0.1);
      } else {
        userPatterns.push({
          userId: memory.userId,
          patternType: 'workflow',
          patternData: { workflowId: memory.metadata.workflowId },
          confidence: 0.5,
          lastObserved: new Date(),
          frequency: 1
        });
      }
    }

    // Detect communication patterns (time-based)
    const hour = memory.timestamp.getHours();
    const timePattern = userPatterns.find(p =>
      p.patternType === 'behavior' &&
      p.patternData.type === 'active_hours'
    );

    if (timePattern) {
      timePattern.patternData.hours[hour] = (timePattern.patternData.hours[hour] || 0) + 1;
      timePattern.frequency++;
    } else {
      userPatterns.push({
        userId: memory.userId,
        patternType: 'behavior',
        patternData: {
          type: 'active_hours',
          hours: { [hour]: 1 }
        },
        confidence: 0.3,
        lastObserved: new Date(),
        frequency: 1
      });
    }

    this.userPatterns.set(memory.userId, userPatterns);
  }

  /**
   * Get relevant user patterns for current context
   */
  private async getRelevantPatterns(userId: string, currentMessage: string): Promise<UserPattern[]> {
    const userPatterns = this.userPatterns.get(userId) || [];

    return userPatterns
      .filter(pattern => {
        // Filter patterns by recency and confidence
        const age = Date.now() - pattern.lastObserved.getTime();
        return age < this.config.patternDetectionWindow && pattern.confidence > 0.3;
      })
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 5);
  }

  /**
   * Combine and rank memories by relevance
   */
  private combineAndRankMemories(
    shortTerm: ConversationMemory[],
    longTerm: ConversationMemory[],
    patterns: UserPattern[]
  ): ConversationMemory[] {
    const allMemories = [...shortTerm, ...longTerm];

    return allMemories
      .map(memory => ({
        memory,
        score: this.calculateMemoryScore(memory, patterns)
      }))
      .sort((a, b) => b.score - a.score)
      .map(result => result.memory);
  }

  /**
   * Calculate memory relevance score
   */
  private calculateMemoryScore(memory: ConversationMemory, patterns: UserPattern[]): number {
    let score = memory.metadata.importance;

    // Boost score based on access frequency
    const accessCount = this.memoryAccessCounts.get(memory.id) || 0;
    score += Math.min(0.3, accessCount * 0.05);

    // Boost score for patterns that match current context
    const matchingPatterns = patterns.filter(pattern =>
      this.doesMemoryMatchPattern(memory, pattern)
    );
    score += matchingPatterns.length * 0.1;

    // Recency boost for short-term memories
    const age = Date.now() - memory.timestamp.getTime();
    if (age < 1000 * 60 * 30) { // Last 30 minutes
      score += 0.2 * (1 - age / (1000 * 60 * 30));
    }

    return Math.min(1, score);
  }

  /**
   * Check if memory matches a user pattern
   */
  private doesMemoryMatchPattern(memory: ConversationMemory, pattern: UserPattern): boolean {
    switch (pattern.patternType) {
      case 'workflow':
        return memory.metadata.workflowId === pattern.patternData.workflowId;
      case 'behavior':
        // Check if memory matches active hours pattern
        const memoryHour = memory.timestamp.getHours();
        const hourData = pattern.patternData.hours || {};
        return hourData[memoryHour] > 0;
      default:
        return false;
    }
  }

  /**
   * Calculate text similarity (simple implementation)
   */
  private calculateTextSimilarity(text1: string, text2: string): number {
    const words1 = new Set(text1.toLowerCase().split(/\s+/));
    const words2 = new Set(text2.toLowerCase().split(/\s+/));

    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);

    return union.size > 0 ? intersection.size / union.size : 0;
  }

  /**
   * Calculate relevance score for a memory
   */
  private calculateRelevanceScore(memory: ConversationMemory, currentMessage: string): number {
    const contentSimilarity = this.calculateTextSimilarity(currentMessage, memory.content);
    const importance = memory.metadata.importance;
    const recency = Math.max(0, 1 - (Date.now() - memory.timestamp.getTime()) / (1000 * 60 * 60 * 24)); // 24 hour decay

    return (contentSimilarity * 0.5) + (importance * 0.3) + (recency * 0.2);
  }

  /**
   * Generate context summary from memories
   */
  private generateContextSummary(memories: ConversationMemory[], currentMessage: string): string {
    if (memories.length === 0) {
      return 'No relevant conversation history found.';
    }

    const recentMemories = memories
      .filter(m => m.timestamp.getTime() > Date.now() - 1000 * 60 * 60) // Last hour
      .slice(0, 3);

    if (recentMemories.length === 0) {
      return 'Continuing conversation with fresh context.';
    }

    const summaryPoints = recentMemories.map(memory =>
      `${memory.role === 'user' ? 'User mentioned' : 'We discussed'}: ${memory.content.substring(0, 100)}...`
    );

    return `Recent context: ${summaryPoints.join(' | ')}`;
  }

  /**
   * Determine if memory should be stored long-term
   */
  private shouldStoreInLongTermMemory(memory: ConversationMemory): boolean {
    // High importance memories always go to long-term
    if (memory.metadata.importance > 0.8) return true;

    // Memories with workflows or specific intents
    if (memory.metadata.workflowId || memory.metadata.intent) return true;

    // User messages that are questions or commands
    if (memory.role === 'user' &&
        (memory.content.includes('?') ||
         memory.content.toLowerCase().includes('how to') ||
         memory.content.toLowerCase().includes('can you'))) {
      return true;
    }

    return false;
  }

  /**
   * Generate unique memory ID
   */
  private generateMemoryId(): string {
    return `memory_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Clear short-term memory for a session
   */
  clearSessionMemory(sessionId: string): void {
    this.shortTermMemory.delete(sessionId);
    this.logger.info(`Cleared short-term memory for session: ${sessionId}`);
  }

  /**
   * Get memory statistics
   */
  getMemoryStats(userId?: string): {
    shortTermCount: number;
    longTermCount: number;
    patternCount: number;
    totalAccesses: number;
  } {
    let shortTermCount = 0;
    let longTermCount = 0;

    if (userId) {
      shortTermCount = Array.from(this.shortTermMemory.values())
        .flat()
        .filter(m => m.userId === userId).length;
      longTermCount = (this.longTermMemoryCache.get(userId) || []).length;
    } else {
      shortTermCount = Array.from(this.shortTermMemory.values())
        .reduce((sum, memories) => sum + memories.length, 0);
      longTermCount = Array.from(this.longTermMemoryCache.values())
        .reduce((sum, memories) => sum + memories.length, 0);
    }

    const patternCount = userId ?
      (this.userPatterns.get(userId) || []).length :
      Array.from(this.userPatterns.values())
        .reduce((sum, patterns) => sum + patterns.length, 0);

    const totalAccesses = Array.from(this.memoryAccessCounts.values())
      .reduce((sum, count) => sum + count, 0);

    return {
      shortTermCount,
      longTermCount,
      patternCount,
      totalAccesses
    };
  }

  /**
   * Export memory data for backup
   */
  exportMemoryData(userId: string): {
    shortTerm: ConversationMemory[];
    longTerm: ConversationMemory[];
    patterns: UserPattern[];
  } {
    const shortTerm = Array.from(this.shortTermMemory.values())
      .flat()
      .filter(m => m.userId === userId);

    const
