#!/usr/bin/env node

/**
 * Atom Project - Phase 1: Chat Interface Foundation
 * NLU-Chat Bridge Service

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Connect existing NLU systems to chat interface
 * Timeline: 36 hours development + 8 hours testing

 * This service bridges the existing NLU systems (15+ specialized agents)
 * with the new chat interface, enabling conversational AI capabilities.
 * It integrates with the existing NLU agents in /dist/nlu_agents/ directory.
 */

import { EventEmitter } from 'events';
import { ChatMessage } from '../types/chat';

// Import existing NLU systems
import { AnalyticalAgent } from '../nlu_agents/analytical_agent';
import { CreativeAgent } from '../nlu_agents/creative_agent';
import { PracticalAgent } from '../nlu_agents/practical_agent';
import { SocialMediaAgent } from '../nlu_agents/socialMediaAgent';
import { TradingAgent } from '../nlu_agents/trading_agent';
import { WorkflowAgent } from '../nlu_agents/workflow_agent';

export interface NLUIntent {
  name: string;
  confidence: number;
  entities: any[];
  metadata?: {
    agent?: string;
    processing_time?: number;
    alternative_intents?: any[];
  };
}

export interface NLUEntity {
  text: string;
  type: string;
  confidence: number;
  start: number;
  end: number;
  metadata?: any;
}

export interface NLUContext {
  conversation_id: string;
  user_id: string;
  message_count: number;
  previous_intents: NLUIntent[];
  user_preferences: any;
  session_data: any;
}

export interface NLUResponse {
  intent: NLUIntent;
  entities: NLUEntity[];
  agent: string;
  response: string;
  confidence: number;
  processing_time: number;
  metadata?: {
    alternative_responses?: string[];
    reasoning?: string;
    context_used?: boolean;
    memory_retrieved?: boolean;
  };
}

export interface NLUChatBridgeConfig {
  conversationId: string;
  userId: string;
  enableMemory?: boolean;
  enableWorkflow?: boolean;
  defaultAgent?: string;
  responseTimeout?: number;
  maxRetries?: number;
}

/**
 * NLU-Chat Bridge Service
 * 
 * Bridges existing NLU systems with chat interface, enabling
 * conversational AI capabilities with intent recognition,
 * entity extraction, and agent coordination.
 */
export class NLUChatBridge extends EventEmitter {
  private config: Required<NLUChatBridgeConfig>;
  private context: NLUContext;
  private availableAgents: Map<string, any> = new Map();
  private activeAgent: string;
  private conversationHistory: ChatMessage[] = [];
  private processingQueue: Map<string, Promise<NLUResponse>> = new Map();

  constructor(config: NLUChatBridgeConfig) {
    super();
    
    // Set default configuration
    this.config = {
      conversationId: config.conversationId,
      userId: config.userId,
      enableMemory: config.enableMemory ?? true,
      enableWorkflow: config.enableWorkflow ?? true,
      defaultAgent: config.defaultAgent ?? 'general',
      responseTimeout: config.responseTimeout ?? 30000,
      maxRetries: config.maxRetries ?? 3,
      ...config
    };

    // Initialize context
    this.context = {
      conversation_id: this.config.conversationId,
      user_id: this.config.userId,
      message_count: 0,
      previous_intents: [],
      user_preferences: {},
      session_data: {}
    };

    // Initialize available agents
    this.initializeAgents();
    
    // Set default active agent
    this.activeAgent = this.config.defaultAgent;

    console.log('NLU-Chat Bridge initialized:', {
      conversationId: this.config.conversationId,
      userId: this.config.userId,
      availableAgents: Array.from(this.availableAgents.keys()),
      defaultAgent: this.config.defaultAgent
    });
  }

  /**
   * Initialize available NLU agents
   */
  private initializeAgents(): void {
    // Register available agents
    this.availableAgents.set('analytical', new AnalyticalAgent());
    this.availableAgents.set('creative', new CreativeAgent());
    this.availableAgents.set('practical', new PracticalAgent());
    this.availableAgents.set('social_media', new SocialMediaAgent());
    this.availableAgents.set('trading', new TradingAgent());
    this.availableAgents.set('workflow', new WorkflowAgent());
    this.availableAgents.set('general', new WorkflowAgent()); // Default general agent

    console.log('Available NLU agents:', Array.from(this.availableAgents.keys()));
  }

  /**
   * Process a chat message through NLU
   */
  public async processMessage(message: ChatMessage): Promise<NLUResponse> {
    const startTime = Date.now();
    
    try {
      console.log('Processing message through NLU:', {
        messageId: message.id,
        content: message.content,
        userId: this.config.userId
      });

      // Check if already processing
      if (this.processingQueue.has(message.id)) {
        console.log('Message already being processed:', message.id);
        return await this.processingQueue.get(message.id);
      }

      // Create processing promise
      const processingPromise = this.processMessageInternal(message);
      this.processingQueue.set(message.id, processingPromise);

      // Wait for processing with timeout
      const response = await Promise.race([
        processingPromise,
        new Promise<NLUResponse>((_, reject) => 
          setTimeout(() => reject(new Error('Processing timeout')), this.config.responseTimeout)
        )
      ]);

      // Calculate processing time
      const processingTime = Date.now() - startTime;
      response.processing_time = processingTime;

      // Update conversation history
      this.conversationHistory.push(message);
      
      // Update context
      this.updateContext(response);

      // Emit response
      this.emit('response-generated', {
        messageId: message.id,
        response,
        processingTime
      });

      // Clean up processing queue
      this.processingQueue.delete(message.id);

      console.log('Message processed successfully:', {
        messageId: message.id,
        intent: response.intent.name,
        agent: response.agent,
        confidence: response.confidence,
        processingTime
      });

      return response;

    } catch (error) {
      console.error('Error processing message:', error);
      
      // Clean up processing queue
      this.processingQueue.delete(message.id);

      // Return error response
      return {
        intent: {
          name: 'error',
          confidence: 1.0,
          entities: [],
          metadata: {
            error: error.message
          }
        },
        entities: [],
        agent: 'error',
        response: 'I apologize, but I encountered an error processing your message. Please try again.',
        confidence: 0.0,
        processing_time: Date.now() - startTime,
        metadata: {
          error: error.message,
          processing_failed: true
        }
      };
    }
  }

  /**
   * Internal message processing
   */
  private async processMessageInternal(message: ChatMessage): Promise<NLUResponse> {
    // Step 1: Intent recognition
    const intent = await this.recognizeIntent(message.content);
    
    // Step 2: Entity extraction
    const entities = await this.extractEntities(message.content, intent);
    
    // Step 3: Agent selection
    const selectedAgent = await this.selectAgent(intent, entities, message);
    
    // Step 4: Response generation
    const response = await this.generateResponse(message, intent, entities, selectedAgent);
    
    // Step 5: Context integration
    const contextualResponse = await this.integrateContext(response, message);
    
    return {
      intent,
      entities,
      agent: selectedAgent,
      response: contextualResponse,
      confidence: this.calculateConfidence(intent, entities, contextualResponse),
      processing_time: 0, // Will be set by caller
      metadata: {
        selected_agent: selectedAgent,
        alternative_agents: await this.getAlternativeAgents(intent),
        context_used: this.context.message_count > 0
      }
    };
  }

  /**
   * Recognize intent from message content
   */
  private async recognizeIntent(content: string): Promise<NLUIntent> {
    // Use multiple agents for intent recognition and select best match
    
    const intentResults = await Promise.all(
      Array.from(this.availableAgents.entries()).map(async ([name, agent]) => {
        try {
          const result = await agent.recognizeIntent(content);
          return {
            agent: name,
            intent: result,
            confidence: result.confidence || 0.0
          };
        } catch (error) {
          console.error(`Intent recognition failed for agent ${name}:`, error);
          return {
            agent: name,
            intent: {
              name: 'unknown',
              confidence: 0.0,
              entities: []
            },
            confidence: 0.0
          };
        }
      })
    );

    // Sort by confidence and select best match
    intentResults.sort((a, b) => b.confidence - a.confidence);
    const bestMatch = intentResults[0];

    return {
      name: bestMatch.intent.name,
      confidence: bestMatch.confidence,
      entities: bestMatch.intent.entities || [],
      metadata: {
        agent: bestMatch.agent,
        alternative_intents: intentResults.slice(1, 3).map(i => i.intent)
      }
    };
  }

  /**
   * Extract entities from message content
   */
  private async extractEntities(content: string, intent: NLUIntent): Promise<NLUEntity[]> {
    // Use the selected agent for entity extraction
    const selectedAgent = this.availableAgents.get(intent.metadata?.agent || this.activeAgent);
    
    if (!selectedAgent) {
      return [];
    }

    try {
      const entities = await selectedAgent.extractEntities(content);
      
      return entities.map(entity => ({
        text: entity.text || '',
        type: entity.type || 'unknown',
        confidence: entity.confidence || 0.0,
        start: entity.start || 0,
        end: entity.end || entity.text?.length || 0,
        metadata: entity.metadata
      }));
    } catch (error) {
      console.error('Entity extraction failed:', error);
      return [];
    }
  }

  /**
   * Select appropriate agent for handling the message
   */
  private async selectAgent(
    intent: NLUIntent,
    entities: NLUEntity[],
    message: ChatMessage
  ): Promise<string> {
    // Check if intent has agent preference
    if (intent.metadata?.agent) {
      const agentName = intent.metadata.agent;
      if (this.availableAgents.has(agentName)) {
        return agentName;
      }
    }

    // Check for specific entity types that suggest certain agents
    const entityTypes = entities.map(e => e.type);
    
    if (entityTypes.includes('workflow') || entityTypes.includes('task')) {
      return 'workflow';
    }
    
    if (entityTypes.includes('trade') || entityTypes.includes('stock') || entityTypes.includes('crypto')) {
      return 'trading';
    }
    
    if (entityTypes.includes('social') || entityTypes.includes('post') || entityTypes.includes('comment')) {
      return 'social_media';
    }
    
    if (entityTypes.includes('create') || entityTypes.includes('idea') || entityTypes.includes('brainstorm')) {
      return 'creative';
    }
    
    if (entityTypes.includes('analyze') || entityTypes.includes('data') || entityTypes.includes('report')) {
      return 'analytical';
    }
    
    if (entityTypes.includes('practical') || entityTypes.includes('help') || entityTypes.includes('how')) {
      return 'practical';
    }

    // Use active agent or default
    return this.activeAgent || this.config.defaultAgent;
  }

  /**
   * Generate response using selected agent
   */
  private async generateResponse(
    message: ChatMessage,
    intent: NLUIntent,
    entities: NLUEntity[],
    selectedAgent: string
  ): Promise<string> {
    const agent = this.availableAgents.get(selectedAgent);
    
    if (!agent) {
      return 'I apologize, but I\'m having trouble with that request. Please try rephrasing your message.';
    }

    try {
      // Prepare context for agent
      const agentContext = {
        conversation_id: this.config.conversationId,
        user_id: this.config.userId,
        previous_messages: this.conversationHistory.slice(-5), // Last 5 messages
        intent: intent,
        entities: entities,
        user_preferences: this.context.user_preferences
      };

      // Generate response
      const response = await agent.generateResponse(message.content, agentContext);
      
      return response || 'I\'m sorry, I couldn\'t generate a response. Could you please rephrase your request?';
      
    } catch (error) {
      console.error('Response generation failed:', error);
      return 'I apologize, but I encountered an error generating a response. Please try again.';
    }
  }

  /**
   * Integrate context and memory into response
   */
  private async integrateContext(response: string, message: ChatMessage): Promise<string> {
    // For now, return response as-is
    // In future, this will integrate with LanceDB memory system
    return response;
  }

  /**
   * Calculate overall confidence score
   */
  private calculateConfidence(
    intent: NLUIntent,
    entities: NLUEntity[],
    response: string
  ): number {
    // Weight confidence calculation
    const intentWeight = 0.5;
    const entityWeight = 0.3;
    const responseWeight = 0.2;

    const intentScore = intent.confidence;
    const entityScore = entities.length > 0 
      ? entities.reduce((sum, e) => sum + e.confidence, 0) / entities.length 
      : 0.5;
    const responseScore = response.length > 10 ? 0.8 : 0.5; // Simple heuristic

    return (intentScore * intentWeight) + (entityScore * entityWeight) + (responseScore * responseWeight);
  }

  /**
   * Get alternative agents for intent
   */
  private async getAlternativeAgents(intent: NLUIntent): Promise<string[]> {
    // Simple implementation - return agents that can handle similar intents
    const alternatives: string[] = [];
    
    switch (intent.name) {
      case 'workflow':
      case 'task':
        alternatives.push('practical', 'workflow');
        break;
      case 'analyze':
      case 'report':
        alternatives.push('analytical', 'workflow');
        break;
      case 'create':
      case 'idea':
        alternatives.push('creative', 'analytical');
        break;
      case 'help':
      case 'how':
        alternatives.push('practical', 'workflow');
        break;
    }
    
    return alternatives.filter(alt => alt !== this.activeAgent);
  }

  /**
   * Update conversation context
   */
  private updateContext(response: NLUResponse): void {
    this.context.message_count++;
    this.context.previous_intents.push(response.intent);
    
    // Keep only last 10 intents
    if (this.context.previous_intents.length > 10) {
      this.context.previous_intents = this.context.previous_intents.slice(-10);
    }

    // Update active agent if necessary
    if (response.agent !== this.activeAgent) {
      this.activeAgent = response.agent;
      this.emit('agent-changed', {
        previousAgent: this.activeAgent,
        newAgent: response.agent,
        reason: 'intent-based-selection'
      });
    }
  }

  /**
   * Get current context
   */
  public getContext(): NLUContext {
    return { ...this.context };
  }

  /**
   * Get conversation history
   */
  public getConversationHistory(): ChatMessage[] {
    return [...this.conversationHistory];
  }

  /**
   * Get active agent
   */
  public getActiveAgent(): string {
    return this.activeAgent;
  }

  /**
   * Set active agent
   */
  public setActiveAgent(agent: string): void {
    if (this.availableAgents.has(agent)) {
      this.activeAgent = agent;
      this.emit('agent-changed', {
        previousAgent: this.activeAgent,
        newAgent: agent,
        reason: 'manual-selection'
      });
    } else {
      throw new Error(`Agent ${agent} not available`);
    }
  }

  /**
   * Get available agents
   */
  public getAvailableAgents(): string[] {
    return Array.from(this.availableAgents.keys());
  }

  /**
   * Reset conversation context
   */
  public resetContext(): void {
    this.context = {
      conversation_id: this.config.conversationId,
      user_id: this.config.userId,
      message_count: 0,
      previous_intents: [],
      user_preferences: this.context.user_preferences,
      session_data: {}
    };
    
    this.conversationHistory = [];
    
    this.emit('context-reset', {
      conversationId: this.config.conversationId,
      userId: this.config.userId
    });
  }

  /**
   * Update user preferences
   */
  public updateUserPreferences(preferences: any): void {
    this.context.user_preferences = {
      ...this.context.user_preferences,
      ...preferences
    };
    
    this.emit('preferences-updated', {
      userId: this.config.userId,
      preferences: this.context.user_preferences
    });
  }

  /**
   * Get processing statistics
   */
  public getStatistics(): any {
    return {
      activeAgent: this.activeAgent,
      messageCount: this.context.message_count,
      processingQueueSize: this.processingQueue.size,
      conversationLength: this.conversationHistory.length,
      availableAgents: this.getAvailableAgents()
    };
  }

  /**
   * Cleanup resources
   */
  public destroy(): void {
    // Cancel pending processing
    this.processingQueue.clear();
    
    // Remove all event listeners
    this.removeAllListeners();
    
    console.log('NLU-Chat Bridge destroyed:', {
      conversationId: this.config.conversationId,
      userId: this.config.userId
    });
  }
}

export default NLUChatBridge;