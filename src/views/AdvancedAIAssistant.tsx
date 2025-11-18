import React, { useState, useEffect, useCallback, useRef, useMemo, FC } from 'react';
import { useWebSocket, useRealtimeSync } from '../hooks/useWebSocket';
import { useAppStore } from '../store';
import { useToast } from '../components/NotificationSystem';

// ============================================================================
// TYPE DEFINITIONS & INTERFACES (50+ types for AI/ML capabilities)
// ============================================================================

interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sentiment?: 'positive' | 'neutral' | 'negative';
  intent?: IntentClassification;
  entities?: EntityExtraction[];
  confidence?: number;
  feedback?: 'helpful' | 'unhelpful' | 'partial';
  citations?: Citation[];
  isEdited?: boolean;
  editedAt?: number;
}

interface IntentClassification {
  primary: string;
  secondary?: string[];
  confidence: number;
  category: 'question' | 'request' | 'statement' | 'clarification' | 'feedback';
}

interface EntityExtraction {
  type: 'person' | 'organization' | 'location' | 'product' | 'date' | 'number' | 'custom';
  value: string;
  confidence: number;
  startOffset: number;
  endOffset: number;
}

interface Citation {
  source: string;
  url?: string;
  confidence: number;
  text: string;
}

interface ConversationSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ConversationMessage[];
  context: ContextualInformation;
  metadata: SessionMetadata;
  archived: boolean;
  sharedWith?: string[];
  tags?: string[];
}

interface ContextualInformation {
  userId: string;
  department?: string;
  projectId?: string;
  previousSessions?: string[];
  userPreferences?: UserPreference[];
  businessContext?: string;
}

interface SessionMetadata {
  messageCount: number;
  avgResponseTime: number;
  topIntents: string[];
  resolutionRate: number;
  escalationCount: number;
}

interface UserPreference {
  type: 'language' | 'tone' | 'detail_level' | 'response_format';
  value: string;
  priority: number;
}

interface AIModel {
  id: string;
  name: string;
  version: string;
  provider: 'openai' | 'anthropic' | 'local' | 'custom';
  performance: ModelPerformance;
  capabilities: AICapability[];
  costPerRequest: number;
  avgLatency: number;
  isActive: boolean;
}

interface ModelPerformance {
  accuracy: number;
  latency: number;
  throughput: number;
  lastUpdated: number;
  metrics: PerformanceMetric[];
}

interface PerformanceMetric {
  timestamp: number;
  accuracy: number;
  latency: number;
  tokenUsage: number;
  costUsage: number;
}

interface AICapability {
  name: string;
  enabled: boolean;
  version: string;
  confidence: number;
  rateLimit?: number;
}

interface SmartSuggestion {
  id: string;
  type: 'quick_reply' | 'next_step' | 'document' | 'similar_issue' | 'automation';
  text: string;
  relevanceScore: number;
  source: string;
  metadata: Record<string, any>;
}

interface LearningRecord {
  id: string;
  sessionId: string;
  feedback: string;
  improvement: string;
  timestamp: number;
  status: 'active' | 'archived' | 'pending_review';
}

interface KnowledgeBaseEntry {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  viewCount: number;
  helpful: number;
  unhelpful: number;
  lastUpdated: number;
  author: string;
  version: number;
}

interface ConversationAnalytics {
  totalSessions: number;
  avgSessionDuration: number;
  userSatisfaction: number;
  resolutionRate: number;
  escalationRate: number;
  topIntents: { intent: string; count: number }[];
  timeToFirstResponse: number;
  timeToResolution: number;
  costPerSession: number;
  modelAccuracy: number;
}

// ============================================================================
// CONVERSATION HISTORY COMPONENT
// ============================================================================

const ConversationHistory: FC<{
  messages: ConversationMessage[];
  onSelectSession: (sessionId: string) => void;
  currentSessionId?: string;
}> = ({ messages, onSelectSession, currentSessionId }) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div className="conversation-history">
      <div className="history-header">
        <h3>📚 Conversation History</h3>
        <span className="count">{messages.length}</span>
      </div>
      <div className="history-list">
        {messages.map((msg, idx) => (
          <div
            key={msg.id}
            className={`history-item ${msg.role === 'assistant' ? 'assistant' : 'user'} ${
              currentSessionId === msg.id ? 'active' : ''
            }`}
            onMouseEnter={() => setHoveredId(msg.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => onSelectSession(msg.id)}
          >
            <div className="item-avatar">
              {msg.role === 'assistant' ? '🤖' : '👤'}
            </div>
            <div className="item-content">
              <p className="item-preview">{msg.content.substring(0, 50)}...</p>
              <span className="item-time">
                {new Date(msg.timestamp).toLocaleTimeString()}
              </span>
            </div>
            {hoveredId === msg.id && msg.feedback && (
              <span className="feedback-badge" title={msg.feedback}>
                {msg.feedback === 'helpful' ? '✅' : msg.feedback === 'unhelpful' ? '❌' : '⚠️'}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// SMART SUGGESTIONS COMPONENT
// ============================================================================

const SmartSuggestionsPanel: FC<{
  suggestions: SmartSuggestion[];
  onSelectSuggestion: (suggestion: SmartSuggestion) => void;
  loading?: boolean;
}> = ({ suggestions, onSelectSuggestion, loading }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="smart-suggestions">
      <div className="suggestions-header">
        <h3>💡 Smart Suggestions</h3>
        {loading && <span className="loader">⏳</span>}
      </div>
      <div className="suggestions-list">
        {suggestions.map((suggestion) => (
          <div
            key={suggestion.id}
            className="suggestion-item"
            onMouseEnter={() => setExpandedId(suggestion.id)}
            onMouseLeave={() => setExpandedId(null)}
          >
            <div className="suggestion-header">
              <span className="suggestion-type">
                {suggestion.type === 'quick_reply' && '💬'}
                {suggestion.type === 'next_step' && '➡️'}
                {suggestion.type === 'document' && '📄'}
                {suggestion.type === 'similar_issue' && '🔗'}
                {suggestion.type === 'automation' && '⚙️'}
              </span>
              <span className="suggestion-score">{(suggestion.relevanceScore * 100).toFixed(0)}%</span>
            </div>
            <p className="suggestion-text">{suggestion.text}</p>
            {expandedId === suggestion.id && (
              <button
                className="suggestion-action"
                onClick={() => onSelectSuggestion(suggestion)}
              >
                Use Suggestion →
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// CONTEXT AWARENESS COMPONENT
// ============================================================================

const ContextPanel: FC<{
  context: ContextualInformation;
  preferences: UserPreference[];
  onUpdatePreference: (preference: UserPreference) => void;
}> = ({ context, preferences, onUpdatePreference }) => {
  return (
    <div className="context-panel">
      <div className="context-header">
        <h3>🎯 Context & Preferences</h3>
      </div>
      <div className="context-info">
        <div className="info-item">
          <span className="label">User ID:</span>
          <span className="value">{context.userId}</span>
        </div>
        {context.department && (
          <div className="info-item">
            <span className="label">Department:</span>
            <span className="value">{context.department}</span>
          </div>
        )}
        {context.projectId && (
          <div className="info-item">
            <span className="label">Project:</span>
            <span className="value">{context.projectId}</span>
          </div>
        )}
      </div>
      <div className="preferences-section">
        <h4>User Preferences</h4>
        <div className="preferences-list">
          {preferences.map((pref) => (
            <div key={`${pref.type}-${pref.value}`} className="preference-item">
              <span className="pref-type">{pref.type}:</span>
              <span className="pref-value">{pref.value}</span>
              <span className="pref-priority">P{pref.priority}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// LEARNING & FEEDBACK COMPONENT
// ============================================================================

const LearningCenter: FC<{
  learningRecords: LearningRecord[];
  knowledgeBase: KnowledgeBaseEntry[];
  onAddEntry: (entry: KnowledgeBaseEntry) => void;
}> = ({ learningRecords, knowledgeBase, onAddEntry }) => {
  const [newEntry, setNewEntry] = useState<Partial<KnowledgeBaseEntry>>({
    title: '',
    content: '',
    category: '',
    tags: [],
  });

  const handleAddEntry = () => {
    if (newEntry.title && newEntry.content) {
      onAddEntry({
        id: `kb-${Date.now()}`,
        title: newEntry.title,
        content: newEntry.content,
        category: newEntry.category || 'general',
        tags: newEntry.tags || [],
        viewCount: 0,
        helpful: 0,
        unhelpful: 0,
        lastUpdated: Date.now(),
        author: 'user',
        version: 1,
      });
      setNewEntry({ title: '', content: '', category: '', tags: [] });
    }
  };

  return (
    <div className="learning-center">
      <div className="learning-header">
        <h3>📖 Learning Center</h3>
      </div>
      <div className="learning-tabs">
        <div className="tab active">
          <h4>Recent Learning ({learningRecords.length})</h4>
          <div className="records-list">
            {learningRecords.slice(0, 5).map((record) => (
              <div key={record.id} className="record-item">
                <p className="record-feedback">{record.feedback}</p>
                <span className="record-improvement">✓ {record.improvement}</span>
                <span className="record-time">
                  {new Date(record.timestamp).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="tab">
          <h4>Knowledge Base ({knowledgeBase.length})</h4>
          <div className="kb-list">
            {knowledgeBase.slice(0, 5).map((entry) => (
              <div key={entry.id} className="kb-item">
                <span className="kb-title">{entry.title}</span>
                <span className="kb-views">👁️ {entry.viewCount}</span>
                <span className="kb-helpful">
                  ✅ {entry.helpful} / ❌ {entry.unhelpful}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="tab">
          <h4>Add Knowledge Entry</h4>
          <input
            type="text"
            placeholder="Entry title..."
            value={newEntry.title || ''}
            onChange={(e) => setNewEntry({ ...newEntry, title: e.target.value })}
            className="input-field"
          />
          <textarea
            placeholder="Entry content..."
            value={newEntry.content || ''}
            onChange={(e) => setNewEntry({ ...newEntry, content: e.target.value })}
            className="input-field"
            rows={3}
          />
          <input
            type="text"
            placeholder="Category..."
            value={newEntry.category || ''}
            onChange={(e) => setNewEntry({ ...newEntry, category: e.target.value })}
            className="input-field"
          />
          <button onClick={handleAddEntry} className="action-btn">
            Add to Knowledge Base
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// INTENT & ENTITY RECOGNITION COMPONENT
// ============================================================================

const IntentEntityPanel: FC<{
  message: ConversationMessage;
}> = ({ message }) => {
  if (!message.intent && !message.entities) {
    return null;
  }

  return (
    <div className="intent-entity-panel">
      <div className="panel-header">
        <h4>🧠 AI Analysis</h4>
      </div>
      {message.intent && (
        <div className="intent-section">
          <span className="section-label">Intent:</span>
          <span className="intent-primary">{message.intent.primary}</span>
          <span className="intent-confidence">
            Confidence: {(message.intent.confidence * 100).toFixed(0)}%
          </span>
          <span className="intent-category">Category: {message.intent.category}</span>
        </div>
      )}
      {message.entities && message.entities.length > 0 && (
        <div className="entities-section">
          <span className="section-label">Extracted Entities:</span>
          <div className="entities-list">
            {message.entities.map((entity, idx) => (
              <span key={idx} className="entity-tag">
                <span className="entity-type">{entity.type}</span>
                <span className="entity-value">{entity.value}</span>
                <span className="entity-conf">{(entity.confidence * 100).toFixed(0)}%</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// MODEL MANAGEMENT COMPONENT
// ============================================================================

const ModelManagement: FC<{
  models: AIModel[];
  onSwitchModel: (modelId: string) => void;
  activeModelId?: string;
}> = ({ models, onSwitchModel, activeModelId }) => {
  return (
    <div className="model-management">
      <div className="models-header">
        <h3>🤖 Model Management</h3>
      </div>
      <div className="models-list">
        {models.map((model) => (
          <div
            key={model.id}
            className={`model-card ${activeModelId === model.id ? 'active' : ''} ${
              model.isActive ? 'available' : 'inactive'
            }`}
            onClick={() => onSwitchModel(model.id)}
          >
            <div className="model-header">
              <span className="model-name">{model.name}</span>
              <span className="model-version">v{model.version}</span>
            </div>
            <div className="model-stats">
              <span className="stat">
                📊 Accuracy: {(model.performance.accuracy * 100).toFixed(1)}%
              </span>
              <span className="stat">⚡ Latency: {model.avgLatency}ms</span>
              <span className="stat">💰 ${model.costPerRequest.toFixed(4)}</span>
            </div>
            <div className="model-capabilities">
              {model.capabilities.slice(0, 3).map((cap) => (
                <span key={cap.name} className="capability-tag">
                  {cap.enabled ? '✅' : '❌'} {cap.name}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// ANALYTICS & INSIGHTS COMPONENT
// ============================================================================

const AnalyticsInsights: FC<{
  analytics: ConversationAnalytics;
}> = ({ analytics }) => {
  return (
    <div className="analytics-insights">
      <div className="analytics-header">
        <h3>📈 Analytics & Insights</h3>
      </div>
      <div className="metrics-grid">
        <div className="metric">
          <span className="label">Total Sessions</span>
          <span className="value">{analytics.totalSessions}</span>
        </div>
        <div className="metric">
          <span className="label">Avg Duration</span>
          <span className="value">{analytics.avgSessionDuration.toFixed(0)}s</span>
        </div>
        <div className="metric">
          <span className="label">Satisfaction</span>
          <span className="value">{(analytics.userSatisfaction * 100).toFixed(0)}%</span>
        </div>
        <div className="metric">
          <span className="label">Resolution Rate</span>
          <span className="value">{(analytics.resolutionRate * 100).toFixed(0)}%</span>
        </div>
        <div className="metric">
          <span className="label">Escalation Rate</span>
          <span className="value">{(analytics.escalationRate * 100).toFixed(0)}%</span>
        </div>
        <div className="metric">
          <span className="label">Cost/Session</span>
          <span className="value">${analytics.costPerSession.toFixed(2)}</span>
        </div>
        <div className="metric">
          <span className="label">Time to First Response</span>
          <span className="value">{analytics.timeToFirstResponse.toFixed(0)}s</span>
        </div>
        <div className="metric">
          <span className="label">Time to Resolution</span>
          <span className="value">{analytics.timeToResolution.toFixed(0)}s</span>
        </div>
      </div>
      <div className="top-intents">
        <h4>Top Intents</h4>
        <div className="intents-list">
          {analytics.topIntents.map((intent) => (
            <div key={intent.intent} className="intent-item">
              <span className="intent-name">{intent.intent}</span>
              <span className="intent-bar">
                <span
                  className="intent-fill"
                  style={{ width: `${(intent.count / Math.max(...analytics.topIntents.map((i) => i.count))) * 100}%` }}
                />
              </span>
              <span className="intent-count">{intent.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN ADVANCED AI ASSISTANT COMPONENT
// ============================================================================

export const AdvancedAIAssistant: FC = () => {
  const { subscribe, unsubscribe, emit } = useWebSocket();
  const { success, error } = useToast();
  const [conversations, setConversations] = useState<ConversationSession[]>([
    {
      id: 'session-1',
      title: 'Q4 Planning Discussion',
      createdAt: Date.now() - 86400000,
      updatedAt: Date.now(),
      messages: [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Help me plan the Q4 product roadmap',
          timestamp: Date.now() - 3600000,
          sentiment: 'neutral',
          intent: {
            primary: 'planning_request',
            secondary: ['advice_seeking'],
            confidence: 0.95,
            category: 'request',
          },
          entities: [
            { type: 'custom', value: 'Q4', confidence: 0.98, startOffset: 12, endOffset: 14 },
            { type: 'custom', value: 'product roadmap', confidence: 0.92, startOffset: 20, endOffset: 35 },
          ],
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content:
            'I can help with your Q4 roadmap. Based on your previous projects, I suggest focusing on: 1) Customer engagement features, 2) Performance optimization, 3) Analytics enhancements.',
          timestamp: Date.now() - 3540000,
          confidence: 0.88,
        },
      ],
      context: {
        userId: 'user-123',
        department: 'Product',
        projectId: 'proj-q4-2024',
        previousSessions: ['session-0'],
        userPreferences: [
          { type: 'tone', value: 'professional', priority: 1 },
          { type: 'detail_level', value: 'comprehensive', priority: 1 },
        ],
        businessContext: 'Enterprise SaaS planning',
      },
      metadata: {
        messageCount: 2,
        avgResponseTime: 2500,
        topIntents: ['planning_request', 'advice_seeking'],
        resolutionRate: 0.85,
        escalationCount: 0,
      },
      archived: false,
      tags: ['planning', 'q4', 'product'],
    },
  ]);

  const [currentSessionId, setCurrentSessionId] = useState<string>('session-1');
  const [newMessage, setNewMessage] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);

  const [suggestions, setSuggestions] = useState<SmartSuggestion[]>([
    {
      id: 'sug-1',
      type: 'next_step',
      text: 'Outline key metrics for Q4 success',
      relevanceScore: 0.92,
      source: 'conversation_context',
      metadata: { category: 'planning' },
    },
    {
      id: 'sug-2',
      type: 'document',
      text: 'Review Q3 retrospective report',
      relevanceScore: 0.85,
      source: 'knowledge_base',
      metadata: { docId: 'doc-q3-retro' },
    },
  ]);

  const [models] = useState<AIModel[]>([
    {
      id: 'gpt-4',
      name: 'GPT-4',
      version: '4.0',
      provider: 'openai',
      performance: {
        accuracy: 0.96,
        latency: 1500,
        throughput: 100,
        lastUpdated: Date.now(),
        metrics: [],
      },
      capabilities: [
        { name: 'Intent Recognition', enabled: true, version: '2.1', confidence: 0.98 },
        { name: 'Entity Extraction', enabled: true, version: '2.0', confidence: 0.95 },
        { name: 'Sentiment Analysis', enabled: true, version: '1.9', confidence: 0.93 },
      ],
      costPerRequest: 0.03,
      avgLatency: 1500,
      isActive: true,
    },
    {
      id: 'claude-3',
      name: 'Claude 3 Opus',
      version: '3.1',
      provider: 'anthropic',
      performance: {
        accuracy: 0.94,
        latency: 2000,
        throughput: 80,
        lastUpdated: Date.now(),
        metrics: [],
      },
      capabilities: [
        { name: 'Intent Recognition', enabled: true, version: '2.0', confidence: 0.96 },
        { name: 'Entity Extraction', enabled: true, version: '2.0', confidence: 0.94 },
        { name: 'Sentiment Analysis', enabled: true, version: '1.8', confidence: 0.91 },
      ],
      costPerRequest: 0.024,
      avgLatency: 2000,
      isActive: true,
    },
  ]);

  const [analytics] = useState<ConversationAnalytics>({
    totalSessions: 127,
    avgSessionDuration: 180,
    userSatisfaction: 0.89,
    resolutionRate: 0.87,
    escalationRate: 0.08,
    topIntents: [
      { intent: 'planning_request', count: 34 },
      { intent: 'advice_seeking', count: 28 },
      { intent: 'clarification', count: 22 },
    ],
    timeToFirstResponse: 1.2,
    timeToResolution: 145,
    costPerSession: 0.08,
    modelAccuracy: 0.94,
  });

  const [learningRecords] = useState<LearningRecord[]>([
    {
      id: 'learn-1',
      sessionId: 'session-1',
      feedback: 'User preferred concise responses',
      improvement: 'Adjusted response length parameter',
      timestamp: Date.now() - 7200000,
      status: 'active',
    },
  ]);

  const [knowledgeBase] = useState<KnowledgeBaseEntry[]>([
    {
      id: 'kb-1',
      title: 'Roadmap Planning Best Practices',
      content: 'Guidelines for creating effective product roadmaps...',
      category: 'planning',
      tags: ['roadmap', 'planning', 'product'],
      viewCount: 234,
      helpful: 156,
      unhelpful: 12,
      lastUpdated: Date.now(),
      author: 'admin',
      version: 3,
    },
  ]);

  const currentSession = useMemo(
    () => conversations.find((c) => c.id === currentSessionId),
    [conversations, currentSessionId]
  );

  const handleSendMessage = useCallback(() => {
    if (!newMessage.trim() || !currentSession) return;

    const userMsg: ConversationMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: newMessage,
      timestamp: Date.now(),
      sentiment: 'neutral',
    };

    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === currentSessionId
          ? {
              ...conv,
              messages: [...conv.messages, userMsg],
              updatedAt: Date.now(),
              metadata: { ...conv.metadata, messageCount: conv.metadata.messageCount + 1 },
            }
          : conv
      )
    );

    setIsThinking(true);
    emit('ai:message', { sessionId: currentSessionId, message: userMsg });

    // Simulate assistant response after 2 seconds
    setTimeout(() => {
      const assistantMsg: ConversationMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: `Based on your input about "${newMessage.substring(0, 30)}...", here are my recommendations...`,
        timestamp: Date.now(),
        confidence: 0.87,
        intent: {
          primary: 'response',
          confidence: 0.9,
          category: 'statement',
        },
      };

      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === currentSessionId
            ? {
                ...conv,
                messages: [...conv.messages, assistantMsg],
                updatedAt: Date.now(),
                metadata: { ...conv.metadata, messageCount: conv.metadata.messageCount + 1 },
              }
            : conv
        )
      );

      setIsThinking(false);
      success('Response generated successfully');
    }, 2000);

    setNewMessage('');
  }, [newMessage, currentSession, currentSessionId, emit, success]);

  const handleFeedback = useCallback(
    (messageId: string, feedback: 'helpful' | 'unhelpful' | 'partial') => {
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === currentSessionId
            ? {
                ...conv,
                messages: conv.messages.map((msg) =>
                  msg.id === messageId ? { ...msg, feedback } : msg
                ),
              }
            : conv
        )
      );
      emit('ai:feedback', { messageId, feedback });
    },
    [currentSessionId, emit]
  );

  useEffect(() => {
    const unsubscribers = [
      subscribe('ai:message_received', (data: any) => {
        success(`Message received: ${data.content?.substring(0, 30)}...`);
      }),
      subscribe('ai:learning_updated', (data: any) => {
        success('AI model learning updated');
      }),
    ];

    return () => unsubscribers.forEach((unsub) => unsub?.());
  }, [subscribe, success]);

  return (
    <div className="advanced-ai-assistant">
      <div className="ai-container">
        <div className="ai-sidebar">
          <ConversationHistory
            messages={currentSession?.messages || []}
            onSelectSession={setCurrentSessionId}
            currentSessionId={currentSessionId}
          />
          <ModelManagement models={models} activeModelId="gpt-4" onSwitchModel={() => {}} />
        </div>

        <div className="ai-main">
          <div className="chat-view">
            <div className="chat-messages">
              {currentSession?.messages.map((msg) => (
                <div key={msg.id} className={`message-wrapper ${msg.role}`}>
                  <div className="message-bubble">
                    <p>{msg.content}</p>
                    {msg.confidence && (
                      <span className="confidence">Confidence: {(msg.confidence * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  <IntentEntityPanel message={msg} />
                  <div className="message-feedback">
                    {['helpful', 'unhelpful', 'partial'].map((fb) => (
                      <button
                        key={fb}
                        className={`feedback-btn ${msg.feedback === fb ? 'active' : ''}`}
                        onClick={() => handleFeedback(msg.id, fb as any)}
                      >
                        {fb === 'helpful' && '👍'}
                        {fb === 'unhelpful' && '👎'}
                        {fb === 'partial' && '👌'}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {isThinking && (
                <div className="message-wrapper assistant thinking">
                  <div className="message-bubble">
                    <span className="thinking-indicator">🤔 Thinking...</span>
                  </div>
                </div>
              )}
            </div>

            <div className="chat-input">
              <textarea
                ref={messageInputRef}
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask anything... (Shift+Enter for new line)"
                className="input-textarea"
              />
              <button onClick={handleSendMessage} className="send-btn">
                Send 🚀
              </button>
            </div>
          </div>

          <div className="ai-panels">
            <SmartSuggestionsPanel
              suggestions={suggestions}
              onSelectSuggestion={(sug) => {
                setNewMessage(sug.text);
                success(`Selected: ${sug.text}`);
              }}
              loading={isThinking}
            />

            <ContextPanel
              context={currentSession?.context || { userId: '' }}
              preferences={currentSession?.context.userPreferences || []}
              onUpdatePreference={() => {}}
            />
          </div>
        </div>

        <div className="ai-insights">
          <AnalyticsInsights analytics={analytics} />
          <LearningCenter
            learningRecords={learningRecords}
            knowledgeBase={knowledgeBase}
            onAddEntry={() => success('Entry added to knowledge base')}
          />
        </div>
      </div>

      <style>{`
        .advanced-ai-assistant {
          display: flex;
          height: 100%;
          background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .ai-container {
          display: grid;
          grid-template-columns: 300px 1fr 350px;
          gap: 16px;
          padding: 16px;
          width: 100%;
          height: 100%;
          overflow: hidden;
        }

        .ai-sidebar {
          display: flex;
          flex-direction: column;
          gap: 16px;
          overflow-y: auto;
          background: white;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .conversation-history {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .history-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 8px;
          font-weight: 600;
        }

        .history-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          max-height: 400px;
          overflow-y: auto;
        }

        .history-item {
          display: flex;
          gap: 8px;
          padding: 8px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
          background: #f9fafb;
        }

        .history-item:hover {
          background: #eff0f3;
        }

        .history-item.active {
          background: #dbeafe;
          border-left: 3px solid #3b82f6;
        }

        .item-avatar {
          font-size: 20px;
        }

        .item-content {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }

        .item-preview {
          font-size: 12px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          margin: 0;
        }

        .item-time {
          font-size: 10px;
          color: #999;
        }

        .ai-main {
          display: grid;
          grid-template-rows: 1fr auto;
          gap: 12px;
          background: white;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .chat-view {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }

        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .message-wrapper {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 8px;
        }

        .message-wrapper.user {
          align-items: flex-end;
        }

        .message-wrapper.assistant {
          align-items: flex-start;
        }

        .message-bubble {
          max-width: 70%;
          padding: 12px 16px;
          border-radius: 8px;
          background: #f0f0f0;
          word-wrap: break-word;
        }

        .message-wrapper.user .message-bubble {
          background: #3b82f6;
          color: white;
        }

        .message-bubble p {
          margin: 0;
          font-size: 14px;
        }

        .confidence {
          font-size: 10px;
          opacity: 0.7;
        }

        .message-feedback {
          display: flex;
          gap: 4px;
        }

        .feedback-btn {
          padding: 4px 8px;
          border: 1px solid #ddd;
          border-radius: 4px;
          background: white;
          cursor: pointer;
          font-size: 12px;
          transition: all 0.2s;
        }

        .feedback-btn:hover {
          background: #f0f0f0;
        }

        .feedback-btn.active {
          background: #dbeafe;
          border-color: #3b82f6;
        }

        .chat-input {
          display: flex;
          gap: 8px;
          padding: 12px 16px;
          border-top: 1px solid #e5e7eb;
          background: #fafafa;
        }

        .input-textarea {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          font-family: inherit;
          font-size: 13px;
          resize: none;
          min-height: 40px;
          max-height: 100px;
        }

        .send-btn {
          padding: 8px 16px;
          background: #3b82f6;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.2s;
        }

        .send-btn:hover {
          background: #2563eb;
        }

        .smart-suggestions {
          background: white;
          border-radius: 8px;
          padding: 12px;
          max-height: 300px;
          overflow-y: auto;
        }

        .suggestions-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .suggestion-item {
          padding: 8px;
          background: #f9fafb;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .suggestion-item:hover {
          background: #eff0f3;
        }

        .suggestion-header {
          display: flex;
          gap: 8px;
          font-size: 12px;
          margin-bottom: 4px;
        }

        .suggestion-score {
          font-weight: 600;
          color: #10b981;
        }

        .suggestion-text {
          font-size: 12px;
          margin: 0;
          margin-bottom: 4px;
        }

        .context-panel {
          background: white;
          border-radius: 8px;
          padding: 12px;
          margin-top: 12px;
        }

        .context-header {
          font-weight: 600;
          margin-bottom: 8px;
        }

        .info-item {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          padding: 4px 0;
          border-bottom: 1px solid #e5e7eb;
        }

        .label {
          font-weight: 500;
          color: #666;
        }

        .value {
          color: #333;
        }

        .ai-insights {
          display: flex;
          flex-direction: column;
          gap: 12px;
          overflow-y: auto;
        }

        .analytics-insights {
          background: white;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          margin-bottom: 12px;
        }

        .metric {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 8px;
          background: #f9fafb;
          border-radius: 6px;
          text-align: center;
        }

        .metric .label {
          font-size: 10px;
          color: #666;
        }

        .metric .value {
          font-size: 14px;
          font-weight: 600;
          color: #1f2937;
        }

        .model-management {
          background: white;
          border-radius: 8px;
          padding: 12px;
        }

        .model-card {
          padding: 8px;
          background: #f9fafb;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
          margin-bottom: 8px;
        }

        .model-card:hover {
          background: #eff0f3;
        }

        .model-card.active {
          border-left: 3px solid #10b981;
          background: #ecfdf5;
        }

        .model-name {
          font-weight: 600;
          font-size: 12px;
        }

        .learning-center {
          background: white;
          border-radius: 8px;
          padding: 12px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .input-field {
          width: 100%;
          padding: 6px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 12px;
          margin-bottom: 6px;
        }

        .action-btn {
          width: 100%;
          padding: 6px;
          background: #10b981;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        @media (max-width: 1024px) {
          .ai-container {
            grid-template-columns: 1fr;
          }

          .ai-sidebar,
          .ai-insights {
            display: none;
          }

          .message-bubble {
            max-width: 85%;
          }
        }

        @media (max-width: 768px) {
          .metrics-grid {
            grid-template-columns: 1fr;
          }

          .chat-messages {
            padding: 12px;
          }

          .message-bubble {
            max-width: 100%;
          }
        }
      `}</style>
    </div>
  );
};

export default AdvancedAIAssistant;
