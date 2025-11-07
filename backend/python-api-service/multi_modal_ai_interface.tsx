/**
 * ATOM Multi-Modal AI Interface
 * Comprehensive React component for multi-modal AI integration
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Upload, 
  Play, 
  Pause, 
  Square, 
  Download, 
  RefreshCw, 
  BarChart3, 
  Brain, 
  Eye, 
  Mic, 
  Zap,
  Settings,
  Activity,
  Database,
  Workflow
} from 'lucide-react';

// Import multi-modal AI service
import { createMultiModalAIIntegrationService, MultiModalAIIntegrationService } from './multi_modal_ai_integration_service';

// Types
interface MultiModalContent {
  contentId: string;
  modalities: Record<string, string | File>;
  metadata: Record<string, any>;
  createdAt: string;
  processedAt?: string;
  analysisResults?: Record<string, any>;
}

interface WorkflowExecution {
  executionId: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  inputContent: MultiModalContent;
  outputData: Record<string, any>;
  startedAt: string;
  completedAt?: string;
  errorMessage?: string;
  metrics: Record<string, any>;
}

interface BusinessInsight {
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

interface ServiceStatus {
  vision_ai: { available: boolean; models: number };
  audio_ai: { available: boolean; models: number };
  cross_modal: { available: boolean; tasks: number };
  workflow_engine: { status: string; workflows: number; active_executions: number };
  business_intelligence: { status: string; insights: number; dashboards: number };
}

// Props
interface MultiModalAIInterfaceProps {
  config?: {
    pythonApiUrl: string;
    apiKey?: string;
  };
  className?: string;
}

// Main Component
export const MultiModalAIInterface: React.FC<MultiModalAIInterfaceProps> = ({
  config = { pythonApiUrl: 'http://localhost:8000' },
  className
}) => {
  // State
  const [service, setService] = useState<MultiModalAIIntegrationService | null>(null);
  const [activeTab, setActiveTab] = useState('content-analysis');
  const [uploadedContent, setUploadedContent] = useState<MultiModalContent | null>(null);
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  const [workflowExecutions, setWorkflowExecutions] = useState<WorkflowExecution[]>([]);
  const [businessInsights, setBusinessInsights] = useState<BusinessInsight[]>([]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // File input refs
  const imageInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);
  const textInputRef = useRef<HTMLTextAreaElement>(null);

  // Initialize service
  useEffect(() => {
    const multiModalService = createMultiModalAIIntegrationService(config);
    setService(multiModalService);

    // Set up event listeners
    multiModalService.onContentSubmitted((contentId) => {
      console.log('Content submitted:', contentId);
      refreshExecutions();
    });

    multiModalService.onExecutionCancelled((executionId) => {
      console.log('Execution cancelled:', executionId);
      refreshExecutions();
    });

    // Load initial data
    loadInitialData();

    return () => {
      multiModalService.disconnect();
    };
  }, [config]);

  // Load initial data
  const loadInitialData = async () => {
    try {
      const [status, executions] = await Promise.all([
        fetchServiceStatus(),
        fetchWorkflowExecutions()
      ]);
      
      setServiceStatus(status);
      setWorkflowExecutions(executions);
    } catch (err) {
      setError('Failed to load initial data');
      console.error('Initial data load error:', err);
    }
  };

  // Fetch service status
  const fetchServiceStatus = async (): Promise<ServiceStatus> => {
    if (!service) return {} as ServiceStatus;
    
    const status = await service.getServiceStatus();
    return status.services;
  };

  // Fetch workflow executions
  const fetchWorkflowExecutions = async (): Promise<WorkflowExecution[]> => {
    if (!service) return [];
    
    return await service.getWorkflowExecutions(20);
  };

  // Refresh executions
  const refreshExecutions = useCallback(async () => {
    if (!service) return;
    
    const executions = await service.getWorkflowExecutions(20);
    setWorkflowExecutions(executions);
  }, [service]);

  // Handle content upload
  const handleContentUpload = useCallback(async (modalities: Record<string, File | string>) => {
    if (!service) return;

    setIsLoading(true);
    setError(null);

    try {
      const contentId = await service.submitContent({
        modalities,
        metadata: {
          uploaded_at: new Date().toISOString(),
          user_id: 'current_user' // Would get from auth context
        }
      });

      const content: MultiModalContent = {
        contentId,
        modalities,
        metadata: {
          uploaded_at: new Date().toISOString()
        },
        createdAt: new Date().toISOString()
      };

      setUploadedContent(content);
      
      // Start analysis
      await analyzeContent(content);
      
    } catch (err) {
      setError(`Upload failed: ${err}`);
      console.error('Upload error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [service]);

  // Analyze content
  const analyzeContent = useCallback(async (content: MultiModalContent) => {
    if (!service) return;

    setIsLoading(true);
    setError(null);

    try {
      const modalities = Object.keys(content.modalities);
      const formData = new FormData();

      // Add content to form data
      for (const [modality, data] of Object.entries(content.modalities)) {
        if (data instanceof File) {
          formData.append(modality, data);
        } else {
          formData.append(modality, data);
        }
      }

      let analysisResult;
      
      if (modalities.includes('image') && modalities.length === 1) {
        // Vision analysis
        const imageBlob = content.modalities.image as File;
        analysisResult = await service.analyzeImage(imageBlob, {
          task: 'image_analysis',
          model: 'openai_vision'
        });
      } else if (modalities.includes('audio') && modalities.length === 1) {
        // Audio analysis
        const audioBlob = content.modalities.audio as File;
        analysisResult = await service.analyzeAudio(audioBlob, {
          task: 'speech_recognition',
          model: 'openai_whisper'
        });
      } else {
        // Cross-modal analysis
        analysisResult = await service.analyzeCrossModal(content.modalities, {
          task: 'content_understanding'
        });
      }

      setAnalysisResults(analysisResult);
      
    } catch (err) {
      setError(`Analysis failed: ${err}`);
      console.error('Analysis error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [service]);

  // Handle image upload
  const handleImageUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    handleContentUpload({ image: file });
  }, [handleContentUpload]);

  // Handle audio upload
  const handleAudioUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    handleContentUpload({ audio: file });
  }, [handleContentUpload]);

  // Handle text input
  const handleTextInput = useCallback(() => {
    const text = textInputRef.current?.value;
    if (!text) return;

    handleContentUpload({ text });
  }, [handleContentUpload]);

  // Cancel execution
  const cancelExecution = useCallback(async (executionId: string) => {
    if (!service) return;

    try {
      await service.cancelExecution(executionId);
      refreshExecutions();
    } catch (err) {
      setError(`Failed to cancel execution: ${err}`);
      console.error('Cancel error:', err);
    }
  }, [service, refreshExecutions]);

  // Generate analytics
  const generateAnalytics = useCallback(async () => {
    if (!service) return;

    setIsLoading(true);
    setError(null);

    try {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - 24 * 60 * 60 * 1000); // Last 24 hours

      const analytics = await service.generateAnalytics({
        requestId: `analytics_${Date.now()}`,
        insightTypes: ['trend_analysis', 'anomaly_detection', 'correlation_analysis', 'cross_modal_insights'],
        timeWindow: {
          start: startTime.toISOString(),
          end: endTime.toISOString()
        },
        granularity: 'hour',
        kpiNames: ['text_sentiment', 'insight_confidence', 'cross_modal_engagement'],
        modalities: ['text', 'image', 'audio']
      });

      setBusinessInsights(analytics.insights);
      
    } catch (err) {
      setError(`Analytics generation failed: ${err}`);
      console.error('Analytics error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [service]);

  // Format confidence
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'running': return 'text-blue-600';
      case 'failed': return 'text-red-600';
      case 'cancelled': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  // Get impact color
  const getImpactColor = (impact: string): string => {
    switch (impact) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Render content analysis
  const renderContentAnalysis = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="w-5 h-5" />
            Content Upload
          </CardTitle>
          <CardDescription>
            Upload images, audio, or text for multi-modal analysis
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Image Upload */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Image Analysis</label>
            <Button
              onClick={() => imageInputRef.current?.click()}
              variant="outline"
              className="w-full"
            >
              <Eye className="w-4 h-4 mr-2" />
              Upload Image
            </Button>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
          </div>

          {/* Audio Upload */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Audio Analysis</label>
            <Button
              onClick={() => audioInputRef.current?.click()}
              variant="outline"
              className="w-full"
            >
              <Mic className="w-4 h-4 mr-2" />
              Upload Audio
            </Button>
            <input
              ref={audioInputRef}
              type="file"
              accept="audio/*"
              onChange={handleAudioUpload}
              className="hidden"
            />
          </div>

          {/* Text Input */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Text Analysis</label>
            <textarea
              ref={textInputRef}
              className="w-full p-2 border rounded-md"
              rows={4}
              placeholder="Enter text for analysis..."
            />
            <Button
              onClick={handleTextInput}
              variant="outline"
              className="w-full"
            >
              <Brain className="w-4 h-4 mr-2" />
              Analyze Text
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Results */}
      {analysisResults && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="w-5 h-5" />
              Analysis Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-96">
              <pre className="text-xs bg-gray-50 p-4 rounded">
                {JSON.stringify(analysisResults, null, 2)}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );

  // Render workflow status
  const renderWorkflowStatus = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Workflow className="w-5 h-5" />
          Workflow Executions
        </h3>
        <Button
          onClick={refreshExecutions}
          variant="outline"
          size="sm"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4">
        {workflowExecutions.map((execution) => (
          <Card key={execution.executionId}>
            <CardContent className="p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h4 className="font-medium">{execution.workflowId}</h4>
                  <p className="text-sm text-gray-500">
                    Started: {new Date(execution.startedAt).toLocaleString()}
                  </p>
                </div>
                <Badge className={getStatusColor(execution.status)}>
                  {execution.status}
                </Badge>
              </div>

              <div className="flex gap-2 mb-2">
                {Object.keys(execution.inputContent.modalities).map((modality) => (
                  <Badge key={modality} variant="secondary">
                    {modality}
                  </Badge>
                ))}
              </div>

              {execution.status === 'running' && (
                <Button
                  onClick={() => cancelExecution(execution.executionId)}
                  variant="destructive"
                  size="sm"
                >
                  <Square className="w-4 h-4 mr-2" />
                  Cancel
                </Button>
              )}

              {execution.errorMessage && (
                <Alert className="mt-2">
                  <AlertDescription>{execution.errorMessage}</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );

  // Render business intelligence
  const renderBusinessIntelligence = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Business Intelligence
        </h3>
        <Button
          onClick={generateAnalytics}
          disabled={isLoading}
        >
          <Zap className="w-4 h-4 mr-2" />
          {isLoading ? 'Generating...' : 'Generate Analytics'}
        </Button>
      </div>

      <div className="grid gap-4">
        {businessInsights.map((insight) => (
          <Card key={insight.insightId}>
            <CardContent className="p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h4 className="font-medium">{insight.title}</h4>
                  <p className="text-sm text-gray-600 mt-1">
                    {insight.description}
                  </p>
                </div>
                <div className="flex flex-col gap-1">
                  <Badge className={getImpactColor(insight.impactLevel)}>
                    {insight.impactLevel}
                  </Badge>
                  <span className="text-xs text-gray-500">
                    {formatConfidence(insight.confidence)}
                  </span>
                </div>
              </div>

              <div className="flex gap-2 mb-2">
                {insight.modalitiesUsed.map((modality) => (
                  <Badge key={modality} variant="outline">
                    {modality}
                  </Badge>
                ))}
              </div>

              {insight.recommendations.length > 0 && (
                <div className="mt-3">
                  <h5 className="text-sm font-medium mb-1">Recommendations:</h5>
                  <ul className="text-sm list-disc list-inside text-gray-600">
                    {insight.recommendations.map((rec, index) => (
                      <li key={index}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );

  // Render service status
  const renderServiceStatus = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <Activity className="w-5 h-5" />
        Service Status
      </h3>

      {serviceStatus && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="w-4 h-4" />
                Vision AI
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <Badge className={serviceStatus.vision_ai?.available ? 'text-green-600' : 'text-red-600'}>
                    {serviceStatus.vision_ai?.available ? 'Available' : 'Unavailable'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Models:</span>
                  <span>{serviceStatus.vision_ai?.models || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mic className="w-4 h-4" />
                Audio AI
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <Badge className={serviceStatus.audio_ai?.available ? 'text-green-600' : 'text-red-600'}>
                    {serviceStatus.audio_ai?.available ? 'Available' : 'Unavailable'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Models:</span>
                  <span>{serviceStatus.audio_ai?.models || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-4 h-4" />
                Cross-Modal AI
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <Badge className={serviceStatus.cross_modal?.available ? 'text-green-600' : 'text-red-600'}>
                    {serviceStatus.cross_modal?.available ? 'Available' : 'Unavailable'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Tasks:</span>
                  <span>{serviceStatus.cross_modal?.tasks || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Workflow className="w-4 h-4" />
                Workflow Engine
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span>Status:</span>
                  <Badge className="text-green-600">
                    {serviceStatus.workflow_engine?.status || 'Unknown'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Workflows:</span>
                  <span>{serviceStatus.workflow_engine?.workflows || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>Active:</span>
                  <span>{serviceStatus.workflow_engine?.active_executions || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );

  return (
    <div className={`w-full max-w-7xl mx-auto p-6 ${className}`}>
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">ATOM Multi-Modal AI Platform</h1>
        <p className="text-gray-600">
          Advanced AI integration with vision, audio, and cross-modal capabilities
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert className="mb-6 border-red-200 bg-red-50">
          <AlertDescription className="text-red-800">
            {error}
          </AlertDescription>
        </Alert>
      )}

      {/* Loading Progress */}
      {isLoading && (
        <div className="mb-6">
          <Progress value={undefined} className="w-full" />
          <p className="text-sm text-gray-500 mt-2">Processing...</p>
        </div>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="content-analysis" className="flex items-center gap-2">
            <Brain className="w-4 h-4" />
            Analysis
          </TabsTrigger>
          <TabsTrigger value="workflow-status" className="flex items-center gap-2">
            <Workflow className="w-4 h-4" />
            Workflows
          </TabsTrigger>
          <TabsTrigger value="business-intelligence" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="service-status" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Status
          </TabsTrigger>
        </TabsList>

        <TabsContent value="content-analysis" className="mt-6">
          {renderContentAnalysis()}
        </TabsContent>

        <TabsContent value="workflow-status" className="mt-6">
          {renderWorkflowStatus()}
        </TabsContent>

        <TabsContent value="business-intelligence" className="mt-6">
          {renderBusinessIntelligence()}
        </TabsContent>

        <TabsContent value="service-status" className="mt-6">
          {renderServiceStatus()}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MultiModalAIInterface;