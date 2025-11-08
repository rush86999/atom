import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  Button,
  Select,
  FormControl,
  FormLabel,
  FormHelperText,
  Switch,
  Badge,
  Progress,
  useColorModeValue,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Icon,
  Flex,
  Divider,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tooltip,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
} from '@chakra-ui/react';
import {
  FiTrendingUp,
  FiTrendingDown,
  FiTarget,
  FiDollarSign,
  FiUsers,
  FiCalendar,
  FiBarChart2,
  FiClock,
  FiAlertTriangle,
  FiCheckCircle,
} from 'react-icons/fi';

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

  const bgColor = useColorModeValue('white', 'gray.800');
  const cardBg = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

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
      case 'active': return 'green';
      case 'training': return 'yellow';
      case 'needs_attention': return 'red';
      default: return 'gray';
    }
  };

  const getModelStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return FiCheckCircle;
      case 'training': return FiClock;
      case 'needs_attention': return FiAlertTriangle;
      default: return FiAlertTriangle;
    }
  };

  const getPredictionColor = (prediction: number, modelType: string) => {
    if (modelType === 'churn') {
      return prediction > 0.7 ? 'red' : prediction > 0.3 ? 'orange' : 'green';
    }
    return prediction > 0.7 ? 'green' : prediction > 0.3 ? 'orange' : 'red';
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

  return (
    <VStack spacing={6} align="stretch">
      {/* Header */}
      <VStack align="start" spacing={2}>
        <Heading size="lg">Predictive Analytics</Heading>
        <Text color="gray.600">
          AI-powered predictions for conversions, churn, and customer lifetime value
        </Text>
      </VStack>

      {/* Model Selection & Controls */}
      <Card bg={bgColor}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <HStack justify="space-between">
              <Heading size="md">Analytics Configuration</Heading>
              <Button colorScheme="blue" size="sm">
                Train New Model
              </Button>
            </HStack>

            <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
              <FormControl>
                <FormLabel>Prediction Model</FormLabel>
                <Select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  placeholder="Select a model"
                >
                  {activeModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name} ({model.type})
                    </option>
                  ))}
                </Select>
                <FormHelperText>
                  Choose which predictive model to use
                </FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>Timeframe</FormLabel>
                <Select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value as any)}
                >
                  <option value="7d">7 Days</option>
                  <option value="30d">30 Days</option>
                  <option value="90d">90 Days</option>
                  <option value="1y">1 Year</option>
                </Select>
                <FormHelperText>
                  Prediction timeframe
                </FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>
                  Confidence Threshold: {confidenceThreshold}%
                </FormLabel>
                <Slider
                  value={confidenceThreshold}
                  onChange={setConfidenceThreshold}
                  min={50}
                  max={95}
                  step={5}
                >
                  <SliderTrack>
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb />
                </Slider>
                <FormHelperText>
                  Minimum confidence for predictions
                </FormHelperText>
              </FormControl>
            </SimpleGrid>
          </VStack>
        </CardBody>
      </Card>

      {/* Model Performance */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        {/* Active Models */}
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Heading size="md">Active Models</Heading>
              {models.length === 0 ? (
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>No Models Available</AlertTitle>
                    <AlertDescription>
                      Train your first predictive model to get started.
                    </AlertDescription>
                  </Box>
                </Alert>
              ) : (
                models.map(model => (
                  <Card key={model.id} bg={cardBg}>
                    <CardBody>
                      <VStack align="stretch" spacing={3}>
                        <HStack justify="space-between">
                          <VStack align="start" spacing={1}>
                            <HStack>
                              <Text fontWeight="semibold">{model.name}</Text>
                              <Badge colorScheme={getModelStatusColor(model.status)}>
                                {model.status.replace('_', ' ')}
                              </Badge>
                            </HStack>
                            <Text fontSize="sm" color="gray.600" textTransform="capitalize">
                              {model.type.replace('_', ' ')} prediction
                            </Text>
                          </VStack>
                          <Icon as={getModelStatusIcon(model.status)}
                                color={`${getModelStatusColor(model.status)}.500`} />
                        </HStack>

                        <VStack align="stretch" spacing={2}>
                          <HStack justify="space-between">
                            <Text fontSize="sm">Accuracy</Text>
                            <Text fontSize="sm" fontWeight="medium">
                              {model.accuracy}%
                            </Text>
                          </HStack>
                          <Progress value={model.accuracy} size="sm" colorScheme="blue" />
                        </VStack>

                        <SimpleGrid columns={2} spacing={2}>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="xs" color="gray.600">Precision</Text>
                            <Text fontSize="sm" fontWeight="medium">
                              {(model.performance.precision * 100).toFixed(1)}%
                            </Text>
                          </VStack>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="xs" color="gray.600">Recall</Text>
                            <Text fontSize="sm" fontWeight="medium">
                              {(model.performance.recall * 100).toFixed(1)}%
                            </Text>
                          </VStack>
                        </SimpleGrid>

                        <HStack justify="end">
                          <Button size="sm" variant="outline" colorScheme="blue">
                            Retrain
                          </Button>
                          <Button size="sm" colorScheme="blue">
                            Generate Predictions
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                ))
              )}
            </VStack>
          </CardBody>
        </Card>

        {/* Forecast Accuracy */}
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Heading size="md">Forecast Performance</Heading>

              <SimpleGrid columns={2} spacing={4}>
                <Stat>
                  <StatLabel>Forecast Accuracy</StatLabel>
                  <StatNumber>{forecastAccuracy.toFixed(1)}%</StatNumber>
                  <StatHelpText>
                    <StatArrow type={forecastAccuracy > 85 ? 'increase' : 'decrease'} />
                    Historical accuracy
                  </StatHelpText>
                </Stat>

                <Stat>
                  <StatLabel>Active Predictions</StatLabel>
                  <StatNumber>{highConfidencePredictions.length}</StatNumber>
                  <StatHelpText>
                    High confidence results
                  </StatHelpText>
                </Stat>
              </SimpleGrid>

              <Divider />

              <VStack align="stretch" spacing={3}>
                <Text fontWeight="semibold">Model Performance Metrics</Text>
                {selectedModel && (
                  (() => {
                    const model = models.find(m => m.id === selectedModel);
                    if (!model) return null;

                    return (
                      <SimpleGrid columns={2} spacing={4}>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color="gray.600">F1 Score</Text>
                          <Progress
                            value={model.performance.f1Score * 100}
                            size="sm"
                            colorScheme="green"
                            width="full"
                          />
                          <Text fontSize="sm">{(model.performance.f1Score * 100).toFixed(1)}%</Text>
                        </VStack>
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" color="gray.600">AUC Score</Text>
                          <Progress
                            value={model.performance.auc * 100}
                            size="sm"
                            colorScheme="purple"
                            width="full"
                          />
                          <Text fontSize="sm">{(model.performance.auc * 100).toFixed(1)}%</Text>
                        </VStack>
                      </SimpleGrid>
                    );
                  })()
                )}
              </VStack>

              <Divider />

              <VStack align="stretch" spacing={3}>
                <Text fontWeight="semibold">Key Insights</Text>
                <Alert status="info" size="sm">
                  <AlertIcon />
                  <Box>
                    <AlertTitle fontSize="sm">Conversion Trends</AlertTitle>
                    <AlertDescription fontSize="xs">
                      High-value leads are 3.2x more likely to convert when contacted within 24 hours
                    </AlertDescription>
                  </Box>
                </Alert>
                <Alert status="warning" size="sm">
                  <AlertIcon />
                  <Box>
                    <AlertTitle fontSize="sm">Churn Risk</AlertTitle>
                    <AlertDescription fontSize="xs">
                      15% of customers show elevated churn risk in next 30 days
                    </AlertDescription>
                  </Box>
                </Alert>
              </VStack>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Predictions Table */}
      {predictions.length > 0 && (
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Recent Predictions</Heading>
                <Badge colorScheme="blue">
                  {highConfidencePredictions.length} High Confidence
                </Badge>
              </HStack>

              <TableContainer>
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>Contact</Th>
                      <Th>Prediction</Th>
                      <Th>Confidence</Th>
                      <Th>Key Factors</Th>
                      <Th>Recommendation</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {predictions.slice(0, 10).map((prediction, index) => (
                      <Tr key={index}>
                        <Td>
                          <Text fontWeight="medium">Contact #{prediction.contactId.slice(-6)}</Text>
                        </Td>
                        <Td>
                          <Badge
                            colorScheme={getPredictionColor(prediction.prediction, 'conversion')}
                          >
                            {(prediction.prediction * 100).toFixed(1)}%
                          </Badge>
                        </Td>
                        <Td>
                          <HStack>
                            <Progress
                              value={prediction.confidence}
                              size="sm"
                              width="60px"
                              colorScheme={prediction.confidence >= 80 ? 'green' : 'yellow'}
                            />
                            <Text>{prediction.confidence}%</Text>
                          </HStack>
                        </Td>
                        <Td>
                          <Tooltip label={prediction.factors.map(f => `${f.feature}: ${f.value}`).join(', ')}>
                            <Text fontSize="sm" noOfLines={1}>
                              {prediction.factors.slice(0, 2).map(f => f.feature).join(', ')}
                            </Text>
                          </Tooltip>
                        </Td>
                        <Td>
                          <Text fontSize="sm" noOfLines={2}>
                            {prediction.recommendation}
                          </Text>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Forecast Visualization */}
      {forecast.length > 0 && (
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Heading size="md">Revenue Forecast</Heading>
              <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
                {forecast.slice(-4).map((period, index) => (
                  <Card key={index} bg={cardBg}>
                    <CardBody>
                      <VStack spacing={2} align="center">
                        <Text fontSize="sm" fontWeight="medium" color="gray.600">
                          {period.period}
                        </Text>
                        <Text fontSize="xl" fontWeight="bold" color="blue.500">
                          ${period.predicted.toLocaleString()}
                        </Text>
                        {period.actual && (
                          <HStack>
                            <Icon
                              as={period.actual >= period.predicted ? FiTrendingUp : FiTrendingDown}
                              color={period.actual >= period.predicted ? 'green.500' : 'red.500'}
                            />
                            <Text fontSize="sm" color="gray.600">
                              Actual: ${period.actual.toLocaleString()}
                            </Text>
                          </HStack>
                        )}
                        <Badge colorScheme={period.confidence >= 80 ? 'green' : 'yellow'}>
                          {period.confidence}% confidence
                        </Badge>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
            </VStack>
          </CardBody>
        </Card>
      )}
    </VStack>
  );
};

export default HubSpotPredictiveAnalytics;
