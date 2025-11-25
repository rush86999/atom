import React, { useState, useCallback, useMemo } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Target,
  DollarSign,
  Users,
  Calendar,
  BarChart2,
  Clock,
  AlertTriangle,
  CheckCircle,
  Info,
} from 'lucide-react';
import { Card, CardContent } from '../../ui/card';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';
import { Alert, AlertDescription, AlertTitle } from '../../ui/alert';
import { Slider } from '../../ui/slider';

export interface PredictiveModel {
  id: string;
  name: string;
  type: 'conversion' | 'churn' | 'lifetime_value' | 'lead_scoring';
  accuracy: number;
  lastTrained: string;
  status: 'active' | 'training' | 'needs_attention';
  features: string[];
  performance: {
    precision: number;
    recall: number;
    f1Score: number;
    auc: number;
  };
}

export interface PredictionResult {
  contactId: string;
  prediction: number;
  confidence: number;
  factors: Array<{
    feature: string;
    impact: number;
    value: any;
  }>;
  recommendation: string;
  timeframe: string;
}

export interface ForecastData {
  period: string;
  actual?: number;
  predicted: number;
  lowerBound: number;
  upperBound: number;
  confidence: number;
}

interface HubSpotPredictiveAnalyticsProps {
  models?: PredictiveModel[];
  predictions?: PredictionResult[];
  forecast?: ForecastData[];
  onModelTrain?: (modelId: string) => void;
  onPredictionGenerate?: (modelId: string, contactIds: string[]) => void;
}

const HubSpotPredictiveAnalytics: React.FC<HubSpotPredictiveAnalyticsProps> = ({
  models = [],
  predictions = [],
  forecast = [],
  onModelTrain,
  onPredictionGenerate,
}) => {
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [timeframe, setTimeframe] = useState<'7d' | '30d' | '90d' | '1y'>('30d');
  const [confidenceThreshold, setConfidenceThreshold] = useState(80);

  const activeModels = useMemo(() =>
    models.filter(model => model.status === 'active'),
    [models]
  );

  const highConfidencePredictions = useMemo(() =>
    predictions.filter(pred => pred.confidence >= confidenceThreshold),
    [predictions, confidenceThreshold]
  );

  const getModelStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
      case 'training': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300';
      case 'needs_attention': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300';
    }
  };

  const getModelStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return CheckCircle;
      case 'training': return Clock;
      case 'needs_attention': return AlertTriangle;
      default: return AlertTriangle;
    }
  };

  const getPredictionColorScheme = (prediction: number, modelType: string) => {
    if (modelType === 'churn') {
      return prediction > 0.7 ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300' :
        prediction > 0.3 ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300' :
          'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
    }
    return prediction > 0.7 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' :
      prediction > 0.3 ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300' :
        'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
  };

  const calculateForecastAccuracy = useCallback(() => {
    if (!forecast.length) return 0;

    const actualValues = forecast.filter(f => f.actual !== undefined).map(f => f.actual!);
    const predictedValues = forecast.filter(f => f.actual !== undefined).map(f => f.predicted);

    if (actualValues.length === 0) return 0;

    const mape = actualValues.reduce((sum, actual, index) => {
      return sum + Math.abs((actual - predictedValues[index]) / actual);
    }, 0) / actualValues.length;

    return Math.max(0, 100 - (mape * 100));
  }, [forecast]);

  const forecastAccuracy = calculateForecastAccuracy();
  const StatusIcon = (status: string) => getModelStatusIcon(status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Predictive Analytics</h2>
        <p className="text-gray-600 dark:text-gray-400">
          AI-powered predictions for conversions, churn, and customer lifetime value
        </p>
      </div>

      {/* Model Selection & Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Analytics Configuration</h3>
              <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
                Train New Model
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Prediction Model</label>
                <select
                  className="w-full h-10 rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  <option value="">Select a model</option>
                  {activeModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name} ({model.type})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400">Choose which predictive model to use</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Timeframe</label>
                <select
                  className="w-full h-10 rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value as any)}
                >
                  <option value="7d">7 Days</option>
                  <option value="30d">30 Days</option>
                  <option value="90d">90 Days</option>
                  <option value="1y">1 Year</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400">Prediction timeframe</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  Confidence Threshold: {confidenceThreshold}%
                </label>
                <Slider
                  value={confidenceThreshold}
                  onValueChange={setConfidenceThreshold}
                  min={50}
                  max={95}
                  step={5}
                  className="mt-2"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">Minimum confidence for predictions</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Model Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Models */}
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text gray-900 dark:text-gray-100">Active Models</h3>
              {models.length === 0 ? (
                <Alert variant="default" className="bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800">
                  <Info className="h-4 w-4" />
                  <AlertTitle>No Models Available</AlertTitle>
                  <AlertDescription>
                    Train your first predictive model to get started.
                  </AlertDescription>
                </Alert>
              ) : (
                models.map(model => {
                  const Icon = getModelStatusIcon(model.status);
                  return (
                    <Card key={model.id} className="bg-gray-50 dark:bg-gray-800">
                      <CardContent className="pt-6">
                        <div className="space-y-3">
                          <div className="flex justify-between items-start">
                            <div className="space-y-1">
                              <div className="flex items-center space-x-2">
                                <p className="font-semibold text-gray-900 dark:text-gray-100">{model.name}</p>
                                <Badge className={getModelStatusColor(model.status)}>
                                  {model.status.replace('_', ' ')}
                                </Badge>
                              </div>
                              <p className="text-sm text-gray-600 dark:text-gray-400 capitalize">
                                {model.type.replace('_', ' ')} prediction
                              </p>
                            </div>
                            <Icon className="h-5 w-5 text-current" />
                          </div>

                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <p className="text-sm text-gray-900 dark:text-gray-100">Accuracy</p>
                              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{model.accuracy}%</p>
                            </div>
                            <Progress value={model.accuracy} className="h-2" />
                          </div>

                          <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-0">
                              <p className="text-xs text-gray-600 dark:text-gray-400">Precision</p>
                              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {(model.performance.precision * 100).toFixed(1)}%
                              </p>
                            </div>
                            <div className="space-y-0">
                              <p className="text-xs text-gray-600 dark:text-gray-400">Recall</p>
                              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {(model.performance.recall * 100).toFixed(1)}%
                              </p>
                            </div>
                          </div>

                          <div className="flex justify-end space-x-2">
                            <Button size="sm" variant="outline">Retrain</Button>
                            <Button size="sm" className="bg-blue-600 hover:bg-blue-700">Generate Predict ions</Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        {/* Forecast Accuracy */}
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Forecast Performance</h3>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Forecast Accuracy</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{forecastAccuracy.toFixed(1)}%</p>
                  <div className="flex items-center text-xs">
                    {forecastAccuracy > 85 ? (
                      <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                    ) : (
                      <TrendingDown className="mr-1 h-3 w-3 text-red-500" />
                    )}
                    <span className="text-gray-600 dark:text-gray-400">Historical accuracy</span>
                  </div>
                </div>

                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Predictions</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{highConfidencePredictions.length}</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400">High confidence results</p>
                </div>
              </div>

              <hr className="border-gray-200 dark:border-gray-700" />

              <div className="space-y-3">
                <p className="font-semibold text-gray-900 dark:text-gray-100">Model Performance Metrics</p>
                {selectedModel && (() => {
                  const model = models.find(m => m.id === selectedModel);
                  if (!model) return null;

                  return (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600 dark:text-gray-400">F1 Score</p>
                        <Progress value={model.performance.f1Score * 100} className="h-2" />
                        <p className="text-sm text-gray-900 dark:text-gray-100">{(model.performance.f1Score * 100).toFixed(1)}%</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-gray-600 dark:text-gray-400">AUC Score</p>
                        <Progress value={model.performance.auc * 100} className="h-2" />
                        <p className="text-sm text-gray-900 dark:text-gray-100">{(model.performance.auc * 100).toFixed(1)}%</p>
                      </div>
                    </div>
                  );
                })()}
              </div>

              <hr className="border-gray-200 dark:border-gray-700" />

              <div className="space-y-3">
                <p className="font-semibold text-gray-900 dark:text-gray-100">Key Insights</p>
                <Alert variant="default" className="bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800">
                  <Info className="h-4 w-4" />
                  <AlertTitle className="text-sm">Conversion Trends</AlertTitle>
                  <AlertDescription className="text-xs">
                    High-value leads are 3.2x more likely to convert when contacted within 24 hours
                  </AlertDescription>
                </Alert>
                <Alert variant="default" className="bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle className="text-sm">Churn Risk</AlertTitle>
                  <AlertDescription className="text-xs">
                    15% of customers show elevated churn risk in next 30 days
                  </AlertDescription>
                </Alert>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Predictions Table */}
      {predictions.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Recent Predictions</h3>
                <Badge variant="secondary" className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                  {highConfidencePredictions.length} High Confidence
                </Badge>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left p-2 font-medium text-gray-900 dark:text-gray-100">Contact</th>
                      <th className="text-left p-2 font-medium text-gray-900 dark:text-gray-100">Prediction</th>
                      <th className="text-left p-2 font-medium text-gray-900 dark:text-gray-100">Confidence</th>
                      <th className="text-left p-2 font-medium text-gray-900 dark:text-gray-100">Key Factors</th>
                      <th className="text-left p-2 font-medium text-gray-900 dark:text-gray-100">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions.slice(0, 10).map((prediction, index) => (
                      <tr key={index} className="border-b border-gray-100 dark:border-gray-800">
                        <td className="p-2">
                          <p className="font-medium text-gray-900 dark:text-gray-100">Contact #{prediction.contactId.slice(-6)}</p>
                        </td>
                        <td className="p-2">
                          <Badge className={getPredictionColorScheme(prediction.prediction, 'conversion')}>
                            {(prediction.prediction * 100).toFixed(1)}%
                          </Badge>
                        </td>
                        <td className="p-2">
                          <div className="flex items-center space-x-2">
                            <Progress value={prediction.confidence} className="h-2 w-16" />
                            <span className="text-gray-900 dark:text-gray-100">{prediction.confidence}%</span>
                          </div>
                        </td>
                        <td className="p-2">
                          <p className="text-gray-600 dark:text-gray-400 truncate max-w-[200px]" title={prediction.factors.map(f => `${f.feature}: ${f.value}`).join(', ')}>
                            {prediction.factors.slice(0, 2).map(f => f.feature).join(', ')}
                          </p>
                        </td>
                        <td className="p-2">
                          <p className="text-gray-600 dark:text-gray-400 line-clamp-2">
                            {prediction.recommendation}
                          </p>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Forecast Visualization */}
      {forecast.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Revenue Forecast</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {forecast.slice(-4).map((period, index) => (
                  <Card key={index} className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center space-y-2">
                        <p className="text-sm font-medium text-gray-600 dark:text-gray-400">{period.period}</p>
                        <p className="text-xl font-bold text-blue-500">${period.predicted.toLocaleString()}</p>
                        {period.actual && (
                          <div className="flex items-center space-x-1">
                            {period.actual >= period.predicted ? (
                              <TrendingUp className="h-4 w-4 text-green-500" />
                            ) : (
                              <TrendingDown className="h-4 w-4 text-red-500" />
                            )}
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              Actual: ${period.actual.toLocaleString()}
                            </p>
                          </div>
                        )}
                        <Badge className={period.confidence >= 80 ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'}>
                          {period.confidence}% confidence
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default HubSpotPredictiveAnalytics;
