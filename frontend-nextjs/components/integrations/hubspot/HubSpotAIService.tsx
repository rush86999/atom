import React, { useState, useCallback } from 'react';
import { TrendingUp, Users, Target, Activity, Brain, Zap, ArrowUp } from 'lucide-react';
import { Card, CardContent } from '../../ui/card';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';
import { Input } from '../../ui/input';
import { Alert, AlertDescription, AlertTitle } from '../../ui/alert';
import { Slider } from '../../ui/slider';

export interface AILeadScoringConfig {
  enabled: boolean;
  model: 'enhanced' | 'predictive' | 'behavioral';
  factors: {
    engagement: number;
    demographics: number;
    behavior: number;
    company: number;
    timing: number;
  };
  thresholds: {
    hot: number;
    warm: number;
    cold: number;
  };
  automation: {
    autoAssign: boolean;
    autoFollowup: boolean;
    smartSegmentation: boolean;
  };
}

export interface AIPrediction {
  leadScore: number;
  confidence: number;
  predictedValue: number;
  conversionProbability: number;
  timeframe: string;
  keyFactors: Array<{
    factor: string;
    impact: number;
    description: string;
  }>;
  recommendations: Array<{
    action: string;
    priority: 'high' | 'medium' | 'low';
    description: string;
  }>;
}

export interface AIWorkflowTrigger {
  id: string;
  name: string;
  type: 'lead_score' | 'behavior' | 'engagement' | 'company';
  condition: string;
  actions: string[];
  enabled: boolean;
}

interface HubSpotAIServiceProps {
  contact?: any;
  company?: any;
  activities?: any[];
  onScoreUpdate?: (score: AIPrediction) => void;
  onWorkflowTrigger?: (trigger: AIWorkflowTrigger) => void;
}

const HubSpotAIService: React.FC<HubSpotAIServiceProps> = ({
  contact,
  company,
  activities = [],
  onScoreUpdate,
  onWorkflowTrigger,
}) => {
  const [config, setConfig] = useState<AILeadScoringConfig>({
    enabled: true,
    model: 'enhanced',
    factors: {
      engagement: 35,
      demographics: 20,
      behavior: 25,
      company: 15,
      timing: 5,
    },
    thresholds: {
      hot: 75,
      warm: 50,
      cold: 25,
    },
    automation: {
      autoAssign: true,
      autoFollowup: false,
      smartSegmentation: true,
    },
  });

  const [prediction, setPrediction] = useState<AIPrediction | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');

  const analyzeLead = useCallback(async () => {
    if (!contact) return;

    setIsAnalyzing(true);
    try {
      // Simulate AI analysis - in production, this would call your AI service
      await new Promise(resolve => setTimeout(resolve, 2000));

      const mockPrediction: AIPrediction = {
        leadScore: Math.floor(Math.random() * 40) + 60, // 60-100 range
        confidence: Math.floor(Math.random() * 30) + 70, // 70-100% confidence
        predictedValue: Math.floor(Math.random() * 50000) + 50000,
        conversionProbability: Math.floor(Math.random() * 40) + 60,
        timeframe: '2-4 weeks',
        keyFactors: [
          {
            factor: 'Email Engagement',
            impact: 0.85,
            description: 'High open and click rates on marketing emails',
          },
          {
            factor: 'Website Activity',
            impact: 0.72,
            description: 'Multiple page views and form submissions',
          },
          {
            factor: 'Company Size',
            impact: 0.65,
            description: 'Enterprise-level company with matching budget',
          },
          {
            factor: 'Industry Fit',
            impact: 0.58,
            description: 'Strong alignment with target customer profile',
          },
        ],
        recommendations: [
          {
            action: 'Schedule Discovery Call',
            priority: 'high',
            description: 'Contact within 24 hours for maximum conversion',
          },
          {
            action: 'Send Case Studies',
            priority: 'medium',
            description: 'Share relevant success stories and ROI data',
          },
          {
            action: 'Add to Nurture Sequence',
            priority: 'low',
            description: 'Continue educational content delivery',
          },
        ],
      };

      setPrediction(mockPrediction);
      onScoreUpdate?.(mockPrediction);
    } catch (error) {
      console.error('AI analysis failed:', error);
    } finally {
      setIsAnalyzing(false);
    }
  }, [contact, onScoreUpdate]);

  const getScoreColorClass = (score: number) => {
    if (score >= config.thresholds.hot) return 'text-red-500';
    if (score >= config.thresholds.warm) return 'text-orange-500';
    return 'text-blue-500';
  };

  const getScoreLabel = (score: number) => {
    if (score >= config.thresholds.hot) return 'Hot Lead';
    if (score >= config.thresholds.warm) return 'Warm Lead';
    return 'Cold Lead';
  };

  const getScoreBadgeColor = (score: number) => {
    if (score >= config.thresholds.hot) return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
    if (score >= config.thresholds.warm) return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300';
    return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300';
  };

  const updateFactorWeight = (factor: keyof AILeadScoringConfig['factors'], value: number) => {
    setConfig(prev => ({
      ...prev,
      factors: {
        ...prev.factors,
        [factor]: value,
      },
    }));
  };

  const updateThreshold = (threshold: keyof AILeadScoringConfig['thresholds'], value: number) => {
    setConfig(prev => ({
      ...prev,
      thresholds: {
        ...prev.thresholds,
        [threshold]: value,
      },
    }));
  };

  const toggleAutomation = (automation: keyof AILeadScoringConfig['automation']) => {
    setConfig(prev => ({
      ...prev,
      automation: {
        ...prev.automation,
        [automation]: !prev.automation[automation],
      },
    }));
  };

  if (!config.enabled) {
    return (
      <Card className="bg-gray-50 dark:bg-gray-800">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center space-y-4">
            <Brain className="h-8 w-8 text-gray-400" />
            <p className="text-center text-gray-600 dark:text-gray-400">
              AI-powered lead scoring is currently disabled
            </p>
            <Button
              onClick={() => setConfig(prev => ({ ...prev, enabled: true }))}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Enable AI Scoring
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* AI Configuration Panel */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Lead Scoring</h3>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600 dark:text-gray-400">Enabled</span>
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(e) => setConfig(prev => ({ ...prev, enabled: e.target.checked }))}
                  className="w-10 h-6 bg-gray-200 rounded-full relative cursor-pointer appearance-none checked:bg-blue-600"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Scoring Model</label>
                <select
                  className="w-full h-10 rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={config.model}
                  onChange={(e) => setConfig(prev => ({ ...prev, model: e.target.value as any }))}
                >
                  <option value="enhanced">Enhanced Scoring</option>
                  <option value="predictive">Predictive Analytics</option>
                  <option value="behavioral">Behavioral Analysis</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400">Choose the AI model for lead scoring</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Custom Analysis Prompt</label>
                <textarea
                  className="w-full h-20 rounded-md border border-input bg-transparent px-3 py-2 text-sm resize-none"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Add specific criteria for AI analysis..."
                />
              </div>
            </div>

            <hr className="border-gray-200 dark:border-gray-700" />

            <div className="space-y-4">
              <p className="font-semibold text-gray-900 dark:text-gray-100">Scoring Factors Weight</p>
              {Object.entries(config.factors).map(([factor, weight]) => (
                <div key={factor} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <p className="text-sm capitalize text-gray-900 dark:text-gray-100">{factor}</p>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{weight}%</p>
                  </div>
                  <Slider
                    value={weight}
                    onValueChange={(value) => updateFactorWeight(factor as any, value)}
                    min={0}
                    max={50}
                    step={5}
                  />
                </div>
              ))}
            </div>

            <hr className="border-gray-200 dark:border-gray-700" />

            <div className="space-y-4">
              <p className="font-semibold text-gray-900 dark:text-gray-100">Score Thresholds</p>
              <div className="grid grid-cols-3 gap-4">
                {Object.entries(config.thresholds).map(([threshold, value]) => (
                  <div key={threshold} className="space-y-2">
                    <label className="text-sm font-medium capitalize text-gray-900 dark:text-gray-100">
                      {threshold} Lead
                    </label>
                    <Input
                      type="number"
                      value={value}
                      onChange={(e) => updateThreshold(threshold as any, parseInt(e.target.value))}
                      min={0}
                      max={100}
                    />
                  </div>
                ))}
              </div>
            </div>

            <hr className="border-gray-200 dark:border-gray-700" />

            <div className="space-y-3">
              <p className="font-semibold text-gray-900 dark:text-gray-100">Automation</p>
              {Object.entries(config.automation).map(([automation, enabled]) => (
                <div key={automation} className="flex justify-between items-center">
                  <p className="text-sm capitalize text-gray-900 dark:text-gray-100">
                    {automation.replace(/([A-Z])/g, ' $1').trim()}
                  </p>
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleAutomation(automation as any)}
                    className="w-10 h-6 bg-gray-200 rounded-full relative cursor-pointer appearance-none checked:bg-blue-600"
                  />
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Controls */}
      {contact && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Lead Analysis</h3>
                <Button
                  onClick={analyzeLead}
                  disabled={isAnalyzing}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  <Brain className="mr-2 h-4 w-4" />
                  {isAnalyzing ? 'Analyzing...' : 'Analyze Lead'}
                </Button>
              </div>

              {prediction && (
                <div className="space-y-4">
                  {/* Score Display */}
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center space-y-3">
                        <Badge className={`text-lg px-4 py-2 ${getScoreBadgeColor(prediction.leadScore)}`}>
                          {getScoreLabel(prediction.leadScore)}
                        </Badge>
                        <p className={`text-4xl font-bold ${getScoreColorClass(prediction.leadScore)}`}>
                          {prediction.leadScore}
                        </p>
                        <Progress value={prediction.leadScore} className="w-full h-3" />
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          Confidence: {prediction.confidence}% • Value: ${prediction.predictedValue.toLocaleString()}
                        </p>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Key Factors */}
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="space-y-3">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Key Scoring Factors</h4>
                        {prediction.keyFactors.map((factor, index) => (
                          <div key={index} className="space-y-1">
                            <div className="flex justify-between items-center">
                              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{factor.factor}</p>
                              <Badge variant="secondary" className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                                {(factor.impact * 100).toFixed(0)}%
                              </Badge>
                            </div>
                            <Progress value={factor.impact * 100} className="h-2" />
                            <p className="text-xs text-gray-600 dark:text-gray-400">{factor.description}</p>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Recommendations */}
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="space-y-3">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI Recommendations</h4>
                        {prediction.recommendations.map((rec, index) => {
                          const alertColor = rec.priority === 'high' ? 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800' :
                            rec.priority === 'medium' ? 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800' :
                              'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800';
                          const badgeColor = rec.priority === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300' :
                            rec.priority === 'medium' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300' :
                              'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';

                          return (
                            <Alert key={index} className={alertColor}>
                              <div className="flex items-start justify-between flex-1">
                                <div className="flex-1">
                                  <AlertTitle className="text-sm">{rec.action}</AlertTitle>
                                  <AlertDescription className="text-xs">{rec.description}</AlertDescription>
                                </div>
                                <Badge className={badgeColor}>{rec.priority}</Badge>
                              </div>
                            </Alert>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Prediction Stats */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Conversion Probability</p>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{prediction.conversionProbability}%</p>
                      <div className="flex items-center text-xs">
                        <ArrowUp className="mr-1 h-3 w-3 text-green-500" />
                        <span className="text-gray-600 dark:text-gray-400">Likely to convert</span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Expected Timeline</p>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{prediction.timeframe}</p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">Estimated conversion window</p>
                    </div>

                    <div className="space-y-1">
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Predicted Value</p>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">${prediction.predictedValue.toLocaleString()}</p>
                      <div className="flex items-center text-xs">
                        <ArrowUp className="mr-1 h-3 w-3 text-green-500" />
                        <span className="text-gray-600 dark:text-gray-400">Potential deal size</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Automation Triggers */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Automation Triggers</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configure automated actions based on AI predictions
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Zap className="h-4 w-4 text-green-500" />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">Hot Lead Trigger</p>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Automatically assign to sales team when lead score exceeds {config.thresholds.hot}
                    </p>
                    <input
                      type="checkbox"
                      checked={config.automation.autoAssign}
                      onChange={() => toggleAutomation('autoAssign')}
                      className="w-10 h-6 bg-gray-200 rounded-full relative cursor-pointer appearance-none checked:bg-green-600"
                    />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Activity className="h-4 w-4 text-blue-500" />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">Behavioral Trigger</p>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Trigger follow-up sequences based on engagement patterns
                    </p>
                    <input
                      type="checkbox"
                      checked={config.automation.autoFollowup}
                      onChange={() => toggleAutomation('autoFollowup')}
                      className="w-10 h-6 bg-gray-200 rounded-full relative cursor-pointer appearance-none checked:bg-blue-600"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default HubSpotAIService;
