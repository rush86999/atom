import React, { useState, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Badge,
  Progress,
  Card,
  CardBody,
  Button,
  Input,
  Textarea,
  Select,
  FormControl,
  FormLabel,
  FormHelperText,
  Switch,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Tooltip,
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
} from '@chakra-ui/react';
import { FiTrendingUp, FiUsers, FiTarget, FiActivity, FiBrain, FiZap } from 'react-icons/fi';

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

  const bgColor = useColorModeValue('white', 'gray.800');
  const cardBg = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

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

  const getScoreColor = (score: number) => {
    if (score >= config.thresholds.hot) return 'red.500';
    if (score >= config.thresholds.warm) return 'orange.500';
    return 'blue.500';
  };

  const getScoreLabel = (score: number) => {
    if (score >= config.thresholds.hot) return 'Hot Lead';
    if (score >= config.thresholds.warm) return 'Warm Lead';
    return 'Cold Lead';
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
      <Card bg={cardBg}>
        <CardBody>
          <VStack spacing={4} align="center">
            <Icon as={FiBrain} boxSize={8} color="gray.400" />
            <Text textAlign="center" color="gray.600">
              AI-powered lead scoring is currently disabled
            </Text>
            <Button
              colorScheme="blue"
              onClick={() => setConfig(prev => ({ ...prev, enabled: true }))}
            >
              Enable AI Scoring
            </Button>
          </VStack>
        </CardBody>
      </Card>
    );
  }

  return (
    <VStack spacing={6} align="stretch">
      {/* AI Configuration Panel */}
      <Card bg={bgColor}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <HStack justify="space-between">
              <Heading size="md">AI Lead Scoring</Heading>
              <HStack>
                <Text fontSize="sm" color="gray.600">Enabled</Text>
                <Switch
                  isChecked={config.enabled}
                  onChange={(e) => setConfig(prev => ({ ...prev, enabled: e.target.checked }))}
                  colorScheme="blue"
                />
              </HStack>
            </HStack>

            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              <FormControl>
                <FormLabel>Scoring Model</FormLabel>
                <Select
                  value={config.model}
                  onChange={(e) => setConfig(prev => ({ ...prev, model: e.target.value as any }))}
                >
                  <option value="enhanced">Enhanced Scoring</option>
                  <option value="predictive">Predictive Analytics</option>
                  <option value="behavioral">Behavioral Analysis</option>
                </Select>
                <FormHelperText>
                  Choose the AI model for lead scoring
                </FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>Custom Analysis Prompt</FormLabel>
                <Textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Add specific criteria for AI analysis..."
                  size="sm"
                />
              </FormControl>
            </SimpleGrid>

            <Divider />

            <VStack align="stretch" spacing={4}>
              <Text fontWeight="semibold">Scoring Factors Weight</Text>
              {Object.entries(config.factors).map(([factor, weight]) => (
                <VStack key={factor} align="stretch" spacing={2}>
                  <HStack justify="space-between">
                    <Text fontSize="sm" textTransform="capitalize">
                      {factor}
                    </Text>
                    <Text fontSize="sm" fontWeight="medium">
                      {weight}%
                    </Text>
                  </HStack>
                  <Slider
                    value={weight}
                    onChange={(value) => updateFactorWeight(factor as any, value)}
                    min={0}
                    max={50}
                    step={5}
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                </VStack>
              ))}
            </VStack>

            <Divider />

            <VStack align="stretch" spacing={4}>
              <Text fontWeight="semibold">Score Thresholds</Text>
              <SimpleGrid columns={3} spacing={4}>
                {Object.entries(config.thresholds).map(([threshold, value]) => (
                  <FormControl key={threshold}>
                    <FormLabel textTransform="capitalize">
                      {threshold} Lead
                    </FormLabel>
                    <Input
                      type="number"
                      value={value}
                      onChange={(e) => updateThreshold(threshold as any, parseInt(e.target.value))}
                      min={0}
                      max={100}
                    />
                  </FormControl>
                ))}
              </SimpleGrid>
            </VStack>

            <Divider />

            <VStack align="stretch" spacing={3}>
              <Text fontWeight="semibold">Automation</Text>
              {Object.entries(config.automation).map(([automation, enabled]) => (
                <HStack key={automation} justify="space-between">
                  <Text fontSize="sm" textTransform="capitalize">
                    {automation.replace(/([A-Z])/g, ' $1').trim()}
                  </Text>
                  <Switch
                    isChecked={enabled}
                    onChange={() => toggleAutomation(automation as any)}
                    colorScheme="blue"
                  />
                </HStack>
              ))}
            </VStack>
          </VStack>
        </CardBody>
      </Card>

      {/* Analysis Controls */}
      {contact && (
        <Card bg={bgColor}>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Lead Analysis</Heading>
                <Button
                  colorScheme="blue"
                  leftIcon={<Icon as={FiBrain} />}
                  onClick={analyzeLead}
                  isLoading={isAnalyzing}
                  loadingText="Analyzing..."
                >
                  Analyze Lead
                </Button>
              </HStack>

              {prediction && (
                <VStack spacing={4} align="stretch">
                  {/* Score Display */}
                  <Card bg={cardBg}>
                    <CardBody>
                      <VStack spacing={3} align="center">
                        <Badge
                          fontSize="lg"
                          colorScheme={
                            prediction.leadScore >= config.thresholds.hot ? 'red' :
                            prediction.leadScore >= config.thresholds.warm ? 'orange' : 'blue'
                          }
                          px={4}
                          py={2}
                        >
                          {getScoreLabel(prediction.leadScore)}
                        </Badge>
                        <Text fontSize="4xl" fontWeight="bold" color={getScoreColor(prediction.leadScore)}>
                          {prediction.leadScore}
                        </Text>
                        <Progress
                          value={prediction.leadScore}
                          size="lg"
                          width="full"
                          colorScheme={
                            prediction.leadScore >= config.thresholds.hot ? 'red' :
                            prediction.leadScore >= config.thresholds.warm ? 'orange' : 'blue'
                          }
                        />
                        <Text fontSize="sm" color="gray.600">
                          Confidence: {prediction.confidence}% • Value: ${prediction.predictedValue.toLocaleString()}
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Key Factors */}
                  <Card bg={cardBg}>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        <Heading size="sm">Key Scoring Factors</Heading>
                        {prediction.keyFactors.map((factor, index) => (
                          <VStack key={index} align="stretch" spacing={1}>
                            <HStack justify="space-between">
                              <Text fontSize="sm" fontWeight="medium">
                                {factor.factor}
                              </Text>
                              <Badge colorScheme="blue">
                                {(factor.impact * 100).toFixed(0)}%
                              </Badge>
                            </HStack>
                            <Progress value={factor.impact * 100} size="sm" colorScheme="blue" />
                            <Text fontSize="xs" color="gray.600">
                              {factor.description}
                            </Text>
                          </VStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Recommendations */}
                  <Card bg={cardBg}>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        <Heading size="sm">AI Recommendations</Heading>
                        {prediction.recommendations.map((rec, index) => (
                          <Alert
                            key={index}
                            status={
                              rec.priority === 'high' ? 'warning' :
                              rec.priority === 'medium' ? 'info' : 'success'
                            }
                            borderRadius="md"
                          >
                            <AlertIcon />
                            <Box flex="1">
                              <AlertTitle fontSize="sm">
                                {rec.action}
                              </AlertTitle>
                              <AlertDescription fontSize="xs">
                                {rec.description}
                              </AlertDescription>
                            </Box>
                            <Badge
                              colorScheme={
                                rec.priority === 'high' ? 'red' :
                                rec.priority === 'medium' ? 'orange' : 'green'
                              }
                            >
                              {rec.priority}
                            </Badge>
                          </Alert>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>

                  {/* Prediction Stats */}
                  <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                    <Stat>
                      <StatLabel>Conversion Probability</StatLabel>
                      <StatNumber>{prediction.conversionProbability}%</StatNumber>
                      <StatHelpText>
                        <StatArrow type="increase" />
                        Likely to convert
                      </StatHelpText>
                    </Stat>

                    <Stat>
                      <StatLabel>Expected Timeline</StatLabel>
                      <StatNumber>{prediction.timeframe}</StatNumber>
                      <StatHelpText>
                        Estimated conversion window
                      </StatHelpText>
                    </Stat>

                    <Stat>
                      <StatLabel>Predicted Value</StatLabel>
                      <StatNumber>${prediction.predictedValue.toLocaleString()}</StatNumber>
                      <StatHelpText>
                        <StatArrow type="increase" />
                        Potential deal size
                      </StatHelpText>
                    </Stat>
                  </SimpleGrid>
                </VStack>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Automation Triggers */}
      <Card bg={bgColor}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <Heading size="md">AI Automation Triggers</Heading>
            <Text fontSize="sm" color="gray.600">
              Configure automated actions based on AI predictions
            </Text>

            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              <Card bg={cardBg}>
                <CardBody>
                  <VStack spacing={3} align="start">
                    <HStack>
                      <Icon as={FiZap} color="green.500" />
                      <Text fontWeight="semibold">Hot Lead Trigger</Text>
                    </HStack>
                    <Text fontSize="sm">
                      Automatically assign to sales team when lead score exceeds {config.thresholds.hot}
                    </Text>
                    <Switch
                      isChecked={config.automation.autoAssign}
                      onChange={() => toggleAutomation('autoAssign')}
                      colorScheme="green"
                    />
                  </VStack>
                </CardBody>
              </Card>

              <Card bg={cardBg}>
                <CardBody>
                  <VStack spacing={3} align="start">
                    <HStack>
                      <Icon as={FiActivity} color="blue.500" />
                      <Text fontWeight="semibold">Behavioral Trigger</Text>
                    </HStack>
                    <Text fontSize="sm">
                      Trigger follow-up sequences based on engagement patterns
                    </Text>
                    <Switch
                      isChecked={config.automation.autoFollowup}
                      onChange={() => toggleAutomation('autoFollowup')}
                      colorScheme="blue"
                    />
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>
          </VStack>
        </CardBody>
      </Card>
    </VStack>
  );
};

export default HubSpotAIService;
