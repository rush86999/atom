/**
 * ATOM Multi-Modal AI Integration Service
 * TypeScript integration layer for Python multimodal AI services
 */

import axios from 'axios';
import { EventEmitter } from 'events';

// Interfaces for multi-modal AI integration
export interface MultimodalContent {
  contentId: string;
  modalities: Record<string, string | Blob>; // modality -> data
  metadata: Record<string, any>;
  createdAt: string;
  processedAt?: string;
  analysisResults?: Record<string, any>;
}

export interface VisionAnalysis {
  analysis: string;
  model: string;
  confidence?: number;
  tokensUsed?: number;
  provider: string;
  objects?: Array<{
    name: string;
    confidence: number;
    boundingBox: any;
  }>;
  faces?: Array<{
    confidence: number;
    boundingBox: any;
    emotions: Record<string, number>;
  }>;
  texts?: Array<{
    text: string;
    confidence: number;
    boundingBox: any;
  }>;
  labels?: Array<{
    label: string;
    confidence: number;
  }>;
}

export interface AudioAnalysis {
  text: string;
  segments?: Array<{
    start: number;
    end: number;
    text: string;
    confidence: number;
    speakerId?: string;
  }>;
  speakerSegments?: Array<{
    text: string;
    start: number;
    end: number;
    speakerId: string;
    confidence: number;
  }>;
  audioClassification?: Array<{
    classId: string;
    className: string;
    confidence: number;
    features: Record<string, number>;
  }>;
  emotions?: Record<string, number>;
  musicAnalysis?: {
    tempo: number;
    key: string;
    mode: string;
    genre: string;
    energy: number;
    danceability: number;
  };
  provider: string;
  model: string;
}

export interface CrossModalInsight {
  insightId: string;
  taskType: string;
  modalityCombination: string[];
  primaryInsight: string;
  supportingEvidence: Record<string, any>;
  confidence: number;
  correlations: Record<string, number>;
  metadata: Record<string, any>;
  generatedAt: string;
}

export interface WorkflowDefinition {
  workflowId: string;
  name: string;
  description: string;
  triggers: Array<{
    triggerId: string;
    triggerType: string;
    contentModality?: string;
    conditions?: Record<string, any>;
    parameters?: Record<string, any>;
    enabled: boolean;
  }>;
  actions: Array<{
    actionId: string;
    actionType: string;
    parameters?: Record<string, any>;
    conditions?: Record<string, any>;
    enabled: boolean;
  }>;
  enabled: boolean;
  priority: number;
}

export interface WorkflowExecution {
  executionId: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  inputContent: MultimodalContent;
  outputData: Record<string, any>;
  startedAt: string;
  completedAt?: string;
  errorMessage?: string;
  metrics: Record<string, any>;
}

export interface BusinessInsight {
  insightId: string;
  insightType: string;
  title: string;
  description: string;
  confidence: number;
  impactLevel: 'low' | 'medium' | 'high' | 'critical';
  supportingData: Record<string, any>;
  recommendations: string[];
  timeWindow: {
    start: string;
    end: string;
  };
  kpiImpact: Record<string, number>;
  modalitiesUsed: string[];
  generatedAt: string;
}

export interface AnalyticsRequest {
  requestId: string;
  insightTypes: string[];
  timeWindow: {
    start: string;
    end: string;
  };
  granularity: 'real_time' | 'minute' | 'hour' | 'day' | 'week' | 'month';
  filters?: Record<string, any>;
  kpiNames?: string[];
  modalities?: string[];
  options?: Record<string, any>;
}

export interface MultimodalDashboard {
  dashboardId: string;
  name: string;
  description: string;
  widgets: Array<{
    widgetId: string;
    type: string;
    title: string;
    config: Record<string, any>;
  }>;
  dataSources: string[];
  timeFilters?: Record<string, any>;
  kpiDefinitions?: Record<string, any>;
  refreshInterval?: number;
  createdAt: string;
  updatedAt: string;
}

// Configuration
interface MultiModalAIConfig {
  pythonApiUrl: string;
  apiKey?: string;
  timeout?: number;
  retries?: number;
}

export class MultiModalAIIntegrationService extends EventEmitter {
  private config: MultiModalAIConfig;
  private pythonApiInstance: axios.AxiosInstance;

  constructor(config: MultiModalAIConfig) {
    super();
    this.config = {
      pythonApiUrl: config.pythonApiUrl,
      apiKey: config.apiKey,
      timeout: config.timeout || 30000,
      retries: config.retries || 3,
      ...config,
    };

    // Initialize Python API instance
    this.pythonApiInstance = axios.create({
      baseURL: this.config.pythonApiUrl,
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
        ...(this.config.apiKey && { 'X-API-Key': this.config.apiKey }),
      },
    });

    // Request/response interceptors
    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor
    this.pythonApiInstance.interceptors.request.use(
      (config) => {
        console.log(`[MultiModalAI] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('[MultiModalAI] Request error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.pythonApiInstance.interceptors.response.use(
      (response) => {
        console.log(`[MultiModalAI] Response ${response.status} from ${response.config.url}`);
        return response;
      },
      (error) => {
        console.error('[MultiModalAI] Response error:', error);
        return Promise.reject(error);
      }
    );
  }

  // Vision AI Services
  async analyzeImage(imageData: string | Blob, options?: {
    task?: 'image_analysis' | 'object_detection' | 'face_recognition' | 'text_recognition' | 'scene_understanding' | 'document_analysis';
    model?: 'openai_vision' | 'google_vision' | 'clip_vit' | 'blip_2' | 'llava';
    textPrompt?: string;
    context?: Record<string, any>;
  }): Promise<VisionAnalysis> {
    try {
      const formData = new FormData();
      
      if (typeof imageData === 'string') {
        // Base64 or URL
        if (imageData.startsWith('data:') || imageData.startsWith('http')) {
          formData.append('image_data', imageData);
        } else {
          // Assume base64
          formData.append('image_data', `data:image/jpeg;base64,${imageData}`);
        }
      } else {
        // Blob
        formData.append('image_data', imageData, 'image.jpg');
      }

      // Add parameters
      const params = {
        task_type: options?.task || 'image_analysis',
        vision_model: options?.model || 'openai_vision',
        text_prompt: options?.textPrompt,
        context: options?.context || {},
      };

      const response = await this.pythonApiInstance.post('/api/advanced-ai/ai-process', formData, {
        params,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data.results;
    } catch (error) {
      console.error('[MultiModalAI] Image analysis failed:', error);
      throw new Error(`Image analysis failed: ${error}`);
    }
  }

  // Audio AI Services
  async analyzeAudio(audioData: string | Blob, options?: {
    task?: 'speech_recognition' | 'speaker_identification' | 'audio_classification' | 'audio_analysis' | 'emotion_detection';
    model?: 'openai_whisper' | 'google_speech' | 'aws_transcribe' | 'whisper_local' | 'wav2vec2';
    language?: string;
    context?: Record<string, any>;
  }): Promise<AudioAnalysis> {
    try {
      const formData = new FormData();
      
      if (typeof audioData === 'string') {
        // Base64 or URL
        if (audioData.startsWith('data:') || audioData.startsWith('http')) {
          formData.append('audio_data', audioData);
        } else {
          // Assume base64
          formData.append('audio_data', `data:audio/wav;base64,${audioData}`);
        }
      } else {
        // Blob
        formData.append('audio_data', audioData, 'audio.wav');
      }

      // Add parameters
      const params = {
        task_type: options?.task || 'speech_recognition',
        audio_model: options?.model || 'openai_whisper',
        language: options?.language || 'en',
        context: options?.context || {},
      };

      const response = await this.pythonApiInstance.post('/api/multimodal/audio/analyze', formData, {
        params,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data.results;
    } catch (error) {
      console.error('[MultiModalAI] Audio analysis failed:', error);
      throw new Error(`Audio analysis failed: ${error}`);
    }
  }

  // Cross-Modal AI Services
  async analyzeCrossModal(contentData: Record<string, string | Blob>, options?: {
    task?: 'visual_question_answering' | 'audio_visual_correlation' | 'text_image_matching' | 'multimodal_summarization' | 'content_understanding' | 'emotion_analysis' | 'concept_extraction';
    textPrompt?: string;
    context?: Record<string, any>;
  }): Promise<{
    insights: CrossModalInsight[];
    correlations: Array<{
      correlationId: string;
      modality1: string;
      modality2: string;
      correlationScore: number;
      correlationType: string;
      explanation: string;
      confidence: number;
    }>;
    concepts: Array<{
      conceptId: string;
      conceptName: string;
      definition: string;
      modalitySources: string[];
      textEvidence?: string;
      visualEvidence?: any;
      audioEvidence?: any;
      confidence: number;
      relatedConcepts: string[];
    }>;
  }> {
    try {
      const formData = new FormData();
      
      // Add content for each modality
      for (const [modality, data] of Object.entries(contentData)) {
        if (typeof data === 'string') {
          formData.append(modality, data);
        } else {
          formData.append(modality, data, `${modality}.${modality === 'image' ? 'jpg' : 'wav'}`);
        }
      }

      // Add parameters
      const params = {
        task_type: options?.task || 'content_understanding',
        text_prompt: options?.textPrompt,
        context: options?.context || {},
      };

      const response = await this.pythonApiInstance.post('/api/multimodal/cross-modal/analyze', formData, {
        params,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Cross-modal analysis failed:', error);
      throw new Error(`Cross-modal analysis failed: ${error}`);
    }
  }

  // Workflow Engine Services
  async createWorkflow(workflow: Omit<WorkflowDefinition, 'workflowId'>): Promise<string> {
    try {
      const response = await this.pythonApiInstance.post('/api/multimodal/workflows', workflow);
      
      this.emit('workflowCreated', response.data.workflow_id);
      return response.data.workflow_id;
    } catch (error) {
      console.error('[MultiModalAI] Workflow creation failed:', error);
      throw new Error(`Workflow creation failed: ${error}`);
    }
  }

  async updateWorkflow(workflowId: string, updates: Partial<WorkflowDefinition>): Promise<boolean> {
    try {
      const response = await this.pythonApiInstance.put(`/api/multimodal/workflows/${workflowId}`, updates);
      
      if (response.data.success) {
        this.emit('workflowUpdated', workflowId);
      }
      
      return response.data.success;
    } catch (error) {
      console.error('[MultiModalAI] Workflow update failed:', error);
      throw new Error(`Workflow update failed: ${error}`);
    }
  }

  async deleteWorkflow(workflowId: string): Promise<boolean> {
    try {
      const response = await this.pythonApiInstance.delete(`/api/multimodal/workflows/${workflowId}`);
      
      if (response.data.success) {
        this.emit('workflowDeleted', workflowId);
      }
      
      return response.data.success;
    } catch (error) {
      console.error('[MultiModalAI] Workflow deletion failed:', error);
      throw new Error(`Workflow deletion failed: ${error}`);
    }
  }

  async submitContent(content: Omit<MultimodalContent, 'contentId'>): Promise<string> {
    try {
      const formData = new FormData();
      
      // Add content for each modality
      for (const [modality, data] of Object.entries(content.modalities)) {
        if (typeof data === 'string') {
          formData.append(modality, data);
        } else {
          formData.append(modality, data, `${modality}.${modality === 'image' ? 'jpg' : 'wav'}`);
        }
      }

      // Add metadata
      formData.append('metadata', JSON.stringify(content.metadata));

      const response = await this.pythonApiInstance.post('/api/multimodal/workflows/content', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const contentId = response.data.content_id;
      this.emit('contentSubmitted', contentId);
      return contentId;
    } catch (error) {
      console.error('[MultiModalAI] Content submission failed:', error);
      throw new Error(`Content submission failed: ${error}`);
    }
  }

  async getWorkflows(): Promise<WorkflowDefinition[]> {
    try {
      const response = await this.pythonApiInstance.get('/api/multimodal/workflows');
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get workflows:', error);
      throw new Error(`Failed to get workflows: ${error}`);
    }
  }

  async getWorkflowExecutions(limit: number = 100, workflowId?: string): Promise<WorkflowExecution[]> {
    try {
      const params: any = { limit };
      if (workflowId) {
        params.workflow_id = workflowId;
      }
      
      const response = await this.pythonApiInstance.get('/api/multimodal/workflows/executions', { params });
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get workflow executions:', error);
      throw new Error(`Failed to get workflow executions: ${error}`);
    }
  }

  async getActiveExecutions(): Promise<WorkflowExecution[]> {
    try {
      const response = await this.pythonApiInstance.get('/api/multimodal/workflows/executions/active');
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get active executions:', error);
      throw new Error(`Failed to get active executions: ${error}`);
    }
  }

  async cancelExecution(executionId: string): Promise<boolean> {
    try {
      const response = await this.pythonApiInstance.post(`/api/multimodal/workflows/executions/${executionId}/cancel`);
      
      if (response.data.success) {
        this.emit('executionCancelled', executionId);
      }
      
      return response.data.success;
    } catch (error) {
      console.error('[MultiModalAI] Execution cancellation failed:', error);
      throw new Error(`Execution cancellation failed: ${error}`);
    }
  }

  // Business Intelligence Services
  async generateAnalytics(request: AnalyticsRequest): Promise<{
    insights: BusinessInsight[];
    kpiAnalysis: Record<string, any>;
    crossModalCorrelations: Record<string, any>;
    dataPointsAnalyzed: number;
    modalitiesAnalyzed: string[];
    processingTime: number;
  }> {
    try {
      const response = await this.pythonApiInstance.post('/api/multimodal/analytics/generate', request);
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Analytics generation failed:', error);
      throw new Error(`Analytics generation failed: ${error}`);
    }
  }

  async createDashboard(dashboard: Omit<MultimodalDashboard, 'dashboardId' | 'createdAt' | 'updatedAt'>): Promise<string> {
    try {
      const response = await this.pythonApiInstance.post('/api/multimodal/analytics/dashboards', dashboard);
      
      const dashboardId = response.data.dashboard_id;
      this.emit('dashboardCreated', dashboardId);
      return dashboardId;
    } catch (error) {
      console.error('[MultiModalAI] Dashboard creation failed:', error);
      throw new Error(`Dashboard creation failed: ${error}`);
    }
  }

  async getDashboardData(dashboardId: string): Promise<{
    dashboardId: string;
    name: string;
    description: string;
    widgets: Array<{
      widgetId: string;
      type: string;
      title: string;
      data: any;
    }>;
    lastUpdated: string;
  }> {
    try {
      const response = await this.pythonApiInstance.get(`/api/multimodal/analytics/dashboards/${dashboardId}/data`);
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get dashboard data:', error);
      throw new Error(`Failed to get dashboard data: ${error}`);
    }
  }

  // Model Management Services
  async getAvailableModels(): Promise<{
    visionModels: Record<string, any>;
    audioModels: Record<string, any>;
    crossModalModels: Record<string, any>;
    totalModels: number;
  }> {
    try {
      const response = await this.pythonApiInstance.get('/api/advanced-ai/models');
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get available models:', error);
      throw new Error(`Failed to get available models: ${error}`);
    }
  }

  async getServiceStatus(): Promise<{
    advancedAI: any;
    multimodalWorkflow: any;
    businessIntelligence: any;
    visionAI: any;
    audioAI: any;
    crossModalAI: any;
    status: string;
    timestamp: string;
  }> {
    try {
      const response = await this.pythonApiInstance.get('/api/advanced-ai/dashboard');
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to get service status:', error);
      throw new Error(`Failed to get service status: ${error}`);
    }
  }

  // Real-time Services
  async startRealTimeStream(options?: {
    contentTypes?: string[];
    filters?: Record<string, any>;
  }): Promise<{
    streamId: string;
    url: string;
  }> {
    try {
      const response = await this.pythonApiInstance.post('/api/advanced-ai/streaming/events', {
        content_types: options?.contentTypes || [],
        filters: options?.filters || {},
      });
      
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Failed to start real-time stream:', error);
      throw new Error(`Failed to start real-time stream: ${error}`);
    }
  }

  // Batch Processing Services
  async processBatch(content: Array<{
    id: string;
    modalities: Record<string, string | Blob>;
    metadata?: Record<string, any>;
  }>, options?: {
    tasks?: string[];
    models?: Record<string, string>;
    parallel?: boolean;
  }): Promise<Array<{
    id: string;
    results: any;
    success: boolean;
    error?: string;
    processingTime: number;
  }>> {
    try {
      const formData = new FormData();
      
      // Add batch content
      formData.append('content', JSON.stringify(content));
      formData.append('options', JSON.stringify({
        tasks: options?.tasks || ['image_analysis', 'audio_analysis'],
        models: options?.models || {},
        parallel: options?.parallel !== false,
      }));

      const response = await this.pythonApiInstance.post('/api/multimodal/batch/process', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Batch processing failed:', error);
      throw new Error(`Batch processing failed: ${error}`);
    }
  }

  // Health and Monitoring
  async healthCheck(): Promise<{
    status: 'healthy' | 'degraded' | 'unhealthy';
    services: Record<string, any>;
    timestamp: string;
  }> {
    try {
      const response = await this.pythonApiInstance.get('/api/advanced-ai/health');
      return response.data;
    } catch (error) {
      console.error('[MultiModalAI] Health check failed:', error);
      return {
        status: 'unhealthy',
        services: {},
        timestamp: new Date().toISOString(),
      };
    }
  }

  // Utility Methods
  async convertToBase64(file: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async getFileMetadata(file: Blob): Promise<{
    size: number;
    type: string;
    lastModified?: number;
  }> {
    return {
      size: file.size,
      type: file.type,
      lastModified: (file as any).lastModified,
    };
  }

  // Event Handlers
  onWorkflowCreated(callback: (workflowId: string) => void): void {
    this.on('workflowCreated', callback);
  }

  onWorkflowUpdated(callback: (workflowId: string) => void): void {
    this.on('workflowUpdated', callback);
  }

  onWorkflowDeleted(callback: (workflowId: string) => void): void {
    this.on('workflowDeleted', callback);
  }

  onContentSubmitted(callback: (contentId: string) => void): void {
    this.on('contentSubmitted', callback);
  }

  onExecutionCancelled(callback: (executionId: string) => void): void {
    this.on('executionCancelled', callback);
  }

  onDashboardCreated(callback: (dashboardId: string) => void): void {
    this.on('dashboardCreated', callback);
  }

  // Cleanup
  disconnect(): void {
    this.removeAllListeners();
  }
}

// Factory function
export function createMultiModalAIIntegrationService(config: MultiModalAIConfig): MultiModalAIIntegrationService {
  return new MultiModalAIIntegrationService(config);
}

// Default export
export default MultiModalAIIntegrationService;