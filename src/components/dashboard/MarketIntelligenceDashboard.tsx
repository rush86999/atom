/**
 * ATOM Market Intelligence Dashboard
 * Competitive analysis, market share tracking, and market domination monitoring
 * Provides complete visibility into market position and competitive landscape
 */

import React, { useState, useEffect } from 'react';
import {
  Box, VStack, HStack, Grid, GridItem,
  Card, CardHeader, CardBody,
  Heading, Text, Stat, StatLabel, StatNumber, StatHelpText, StatArrow,
  SimpleGrid, Progress, Badge, Button, ButtonGroup,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Tabs, TabList, TabPanels, Tab, TabPanel,
  useColorModeValue, useToast, useBreakpointValue,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from '@chakra-ui/react';
import { 
  FiTrendingUp, FiTrendingDown, FiTarget, FiAward, FiGlobe, FiPieChart, FiActivity,
  FiBarChart2, FiRadar, FiZap, FiShield, FiFlag, FiUsers, FiDollarSign
} from 'react-icons/fi';

// Market Intelligence Types
interface MarketIntelligence {
  marketShare: {
    atom: number;
    competitors: Record<string, number>;
    total: number;
    growth: number;
    prediction: number[];
  };
  competitivePosition: {
    atom: {
      position: number;
      score: number;
      strengths: string[];
      weaknesses: string[];
      opportunities: string[];
      threats: string[];
    };
    competitors: Record<string, {
      position: number;
      score: number;
      strengths: string[];
      weaknesses: string[];
    }>;
  };
  brandAwareness: {
    atom: number;
    competitors: Record<string, number>;
    trend: number[];
    sentiment: {
      atom: number;
      competitors: Record<string, number>;
    };
  };
  pricingAnalysis: {
    atom: {
      starter: number;
      professional: number;
      business: number;
      enterprise: number;
      strategy: string;
      competitiveness: number;
    };
    competitors: Record<string, {
      starter: number;
      professional: number;
      business: number;
      enterprise: number;
      strategy: string;
    }>;
  };
  featureComparison: {
    atom: Record<string, number>;
    competitors: Record<string, Record<string, number>>;
    innovationScore: number;
    leadership: string[];
  };
  customerSegments: {
    enterprise: {
      atom: number;
      competitors: Record<string, number>;
      trend: number;
    };
    smb: {
      atom: number;
      competitors: Record<string, number>;
      trend: number;
    };
    startup: {
      atom: number;
      competitors: Record<string, number>;
      trend: number;
    };
    developer: {
      atom: number;
      competitors: Record<string, number>;
      trend: number;
    };
  };
  globalPresence: {
    northAmerica: {
      atom: number;
      competitors: Record<string, number>;
    };
    europe: {
      atom: number;
      competitors: Record<string, number>;
    };
    asiaPacific: {
      atom: number;
      competitors: Record<string, number>;
    };
    latinAmerica: {
      atom: number;
      competitors: Record<string, number>;
    };
    other: {
      atom: number;
      competitors: Record<string, number>;
    };
  };
  ecosystem: {
    integrations: {
      atom: number;
      competitors: Record<string, number>;
    };
    developerTools: {
      atom: number;
      competitors: Record<string, number>;
    };
    community: {
      atom: number;
      competitors: Record<string, number>;
    };
    marketplace: {
      atom: number;
      competitors: Record<string, number>;
    };
  };
}

// Market Domination Metrics
interface DominationMetrics {
  marketShare: number;
  revenueShare: number;
  customerShare: number;
  enterpriseShare: number;
  brandLeadership: number;
  competitiveAdvantage: number;
  innovationScore: number;
  globalReach: number;
  ecosystemStrength: number;
}

const MarketIntelligenceDashboard: React.FC = () => {
  const bgColor = useColorModeValue('white', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.200');
  const successColor = useColorModeValue('green.500', 'green.400');
  const warningColor = useColorModeValue('yellow.500', 'yellow.400');
  const errorColor = useColorModeValue('red.500', 'red.400');
  const dominationColor = useColorModeValue('purple.500', 'purple.400');
  const isMobile = useBreakpointValue({ base: true, md: false });
  
  const toast = useToast();
  const [marketIntelligence, setMarketIntelligence] = useState<MarketIntelligence | null>(null);
  const [dominationMetrics, setDominationMetrics] = useState<DominationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');
  const [refreshInterval, setRefreshInterval] = useState(30); // seconds

  // Mock data for demonstration
  useEffect(() => {
    const generateMockData = () => {
      const mockMarketIntelligence: MarketIntelligence = {
        marketShare: {
          atom: 5.2,
          competitors: {
            zapier: 35.5,
            make: 18.2,
            integromat: 12.8,
            tray: 8.5,
            automate: 6.2,
            workato: 4.8,
            n8n: 3.2,
            powerautomate: 25.5
          },
          total: 100,
          growth: 15.8,
          prediction: [4.5, 4.8, 5.2, 5.5, 5.8, 6.2, 6.8, 7.5, 8.2, 9.1, 10.2]
        },
        competitivePosition: {
          atom: {
            position: 3,
            score: 78.5,
            strengths: [
              'AI-Powered Automation',
              'Comprehensive Integration Suite',
              'Advanced Analytics',
              'Enterprise-Grade Security',
              'Predictive Workflows'
            ],
            weaknesses: [
              'Brand Awareness',
              'Market Share',
              'Partner Ecosystem',
              'Global Presence'
            ],
            opportunities: [
              'AI Market Leadership',
              'Enterprise Penetration',
              'Strategic Partnerships',
              'Global Expansion'
            ],
            threats: [
              'Established Competitors',
              'Pricing Pressure',
              'Market Consolidation',
              'Technology Disruption'
            ]
          },
          competitors: {
            zapier: { position: 1, score: 85.2, strengths: ['Brand', 'Ecosystem', 'Market Share'], weaknesses: ['AI Capabilities'] },
            make: { position: 2, score: 82.1, strengths: ['UI/UX', 'Features', 'Pricing'], weaknesses: ['Enterprise'] },
            integromat: { position: 4, score: 75.3, strengths: ['Automation', 'Integration'], weaknesses: ['Scalability'] },
            tray: { position: 5, score: 72.8, strengths: ['Enterprise', 'Security'], weaknesses: ['Innovation'] },
            automate: { position: 6, score: 68.5, strengths: ['UI', 'Simplicity'], weaknesses: ['Features'] }
          }
        },
        brandAwareness: {
          atom: 15.5,
          competitors: {
            zapier: 68.5,
            make: 45.2,
            integromat: 25.8,
            tray: 32.5,
            automate: 28.5
          },
          trend: [8.5, 10.2, 12.5, 14.8, 15.5, 16.2, 17.8, 19.5, 22.1, 25.2],
          sentiment: {
            atom: 78.5,
            competitors: {
              zapier: 82.1,
              make: 75.3,
              integromat: 68.5,
              tray: 71.2,
              automate: 72.8
            }
          }
        },
        pricingAnalysis: {
          atom: {
            starter: 0,
            professional: 29,
            business: 99,
            enterprise: 499,
            strategy: 'Value-Based',
            competitiveness: 85.5
          },
          competitors: {
            zapier: { starter: 19, professional: 49, business: 99, enterprise: 699, strategy: 'Market-Share' },
            make: { starter: 9, professional: 19, business: 49, enterprise: 299, strategy: 'Penetration' },
            integromat: { starter: 9, professional: 29, business: 79, enterprise: 399, strategy: 'Competitive' },
            tray: { starter: 29, professional: 59, business: 129, enterprise: 599, strategy: 'Premium' },
            automate: { starter: 0, professional: 19, business: 49, enterprise: 199, strategy: 'Freemium' }
          }
        },
        featureComparison: {
          atom: {
            integrations: 95,
            aiAutomation: 98,
            workflows: 92,
            analytics: 88,
            security: 95,
            scalability: 93,
            mobile: 75,
            api: 92,
            collaboration: 85,
            customization: 88
          },
          competitors: {
            zapier: { integrations: 85, aiAutomation: 65, workflows: 88, analytics: 75, security: 85, scalability: 82, mobile: 80, api: 88, collaboration: 82, customization: 75 },
            make: { integrations: 78, aiAutomation: 72, workflows: 92, analytics: 85, security: 78, scalability: 80, mobile: 85, api: 82, collaboration: 88, customization: 92 },
            integromat: { integrations: 75, aiAutomation: 68, workflows: 85, analytics: 70, security: 75, scalability: 72, mobile: 65, api: 78, collaboration: 75, customization: 70 },
            tray: { integrations: 80, aiAutomation: 62, workflows: 80, analytics: 82, security: 92, scalability: 88, mobile: 70, api: 85, collaboration: 80, customization: 82 },
            automate: { integrations: 72, aiAutomation: 70, workflows: 78, analytics: 68, security: 72, scalability: 75, mobile: 82, api: 75, collaboration: 85, customization: 88 }
          },
          innovationScore: 88.5,
          leadership: ['AI Automation', 'Predictive Workflows', 'Advanced Analytics', 'Enterprise Security']
        },
        customerSegments: {
          enterprise: {
            atom: 8.5,
            competitors: { zapier: 42.5, make: 15.2, integromat: 12.8, tray: 28.5, automate: 18.5 },
            trend: [4.2, 5.1, 6.2, 7.1, 8.5, 9.8, 11.2, 12.8, 14.5, 16.2]
          },
          smb: {
            atom: 12.5,
            competitors: { zapier: 38.2, make: 22.5, integromat: 15.8, tray: 18.5, automate: 20.5 },
            trend: [6.5, 8.1, 9.5, 11.2, 12.5, 13.8, 15.1, 16.5, 18.2, 19.8]
          },
          startup: {
            atom: 18.5,
            competitors: { zapier: 28.5, make: 32.5, integromat: 18.2, tray: 8.5, automate: 25.5 },
            trend: [12.2, 14.1, 15.8, 17.1, 18.5, 19.8, 21.1, 22.5, 23.8, 25.1]
          },
          developer: {
            atom: 22.5,
            competitors: { zapier: 32.5, make: 28.5, integromat: 22.8, tray: 12.5, automate: 18.5 },
            trend: [15.2, 17.1, 18.8, 20.1, 22.5, 24.8, 26.1, 27.5, 28.8, 30.1]
          }
        },
        globalPresence: {
          northAmerica: {
            atom: 8.5,
            competitors: { zapier: 42.5, make: 32.5, integromat: 12.8, tray: 28.5, automate: 25.5 }
          },
          europe: {
            atom: 12.5,
            competitors: { zapier: 38.2, make: 28.5, integromat: 18.2, tray: 25.5, automate: 22.5 }
          },
          asiaPacific: {
            atom: 6.5,
            competitors: { zapier: 28.5, make: 22.5, integromat: 15.8, tray: 12.5, automate: 18.5 }
          },
          latinAmerica: {
            atom: 4.5,
            competitors: { zapier: 22.5, make: 18.5, integromat: 8.5, tray: 8.5, automate: 12.5 }
          },
          other: {
            atom: 2.5,
            competitors: { zapier: 15.2, make: 12.5, integromat: 5.5, tray: 6.5, automate: 8.5 }
          }
        },
        ecosystem: {
          integrations: {
            atom: 95,
            competitors: { zapier: 85, make: 78, integromat: 75, tray: 80, automate: 72 }
          },
          developerTools: {
            atom: 88,
            competitors: { zapier: 82, make: 85, integromat: 68, tray: 75, automate: 70 }
          },
          community: {
            atom: 75,
            competitors: { zapier: 92, make: 85, integromat: 65, tray: 70, automate: 80 }
          },
          marketplace: {
            atom: 65,
            competitors: { zapier: 88, make: 72, integromat: 55, tray: 60, automate: 58 }
          }
        }
      };

      const mockDominationMetrics: DominationMetrics = {
        marketShare: 5.2,
        revenueShare: 8.5,
        customerShare: 12.5,
        enterpriseShare: 8.5,
        brandLeadership: 15.5,
        competitiveAdvantage: 88.5,
        innovationScore: 88.5,
        globalReach: 6.5,
        ecosystemStrength: 75.5
      };

      return { marketIntelligence: mockMarketIntelligence, dominationMetrics: mockDominationMetrics };
    };

    const loadData = async () => {
      setLoading(true);
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        const data = generateMockData();
        setMarketIntelligence(data.marketIntelligence);
        setDominationMetrics(data.dominationMetrics);
      } catch (error) {
        toast({
          title: "Error loading market intelligence",
          description: "Failed to load market intelligence data",
          status: "error",
          duration: 3000
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [timeRange, toast]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      window.location.reload();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (loading || !marketIntelligence || !dominationMetrics) {
    return (
      <Box p={8} textAlign="center">
        <Text fontSize="lg" color="gray.600">
          Loading ATOM Market Intelligence Dashboard...
        </Text>
      </Box>
    );
  }

  // Helper functions
  const getDominanceColor = (value: number, target: number) => {
    const percentage = (value / target) * 100;
    if (percentage >= 80) return dominationColor;
    if (percentage >= 60) return successColor;
    if (percentage >= 40) return warningColor;
    return errorColor;
  };

  const getDominanceValue = (value: number, target: number) => {
    return Math.min((value / target) * 100, 100);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('en-US').format(value);
  };

  return (
    <Box bg={bgColor} minH="100vh" p={4}>
      {/* Header */}
      <VStack align="stretch" spacing={6}>
        <HStack justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="2xl" color={textColor}>
              🏆 ATOM Market Intelligence Dashboard
            </Heading>
            <Text fontSize="lg" color="gray.600">
              Competitive analysis, market share tracking, and market domination monitoring
            </Text>
          </VStack>
          
          <HStack spacing={3}>
            <ButtonGroup size="sm" isAttached variant="outline">
              <Button onClick={() => setTimeRange('7d')}>7D</Button>
              <Button onClick={() => setTimeRange('30d')}>30D</Button>
              <Button onClick={() => setTimeRange('90d')}>90D</Button>
              <Button onClick={() => setTimeRange('365d')}>1Y</Button>
            </ButtonGroup>
            
            <ButtonGroup size="sm" variant="outline">
              <Button leftIcon={<FiZap />}>Domination Mode</Button>
              <Button onClick={() => window.location.reload()}>
                Refresh Now
              </Button>
            </ButtonGroup>
          </HStack>
        </HStack>

        {/* Market Domination Overview */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          {/* Market Share */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Market Share</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {marketIntelligence.marketShare.atom}%
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={marketIntelligence.marketShare.growth >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(marketIntelligence.marketShare.growth).toFixed(1)}% from last period
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getDominanceValue(marketIntelligence.marketShare.atom, 10)}
                color={getDominanceColor(marketIntelligence.marketShare.atom, 10)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: 10% (Market Leader)
              </Text>
            </CardBody>
          </Card>

          {/* Competitive Position */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Competitive Position</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  #{marketIntelligence.competitivePosition.atom.position}
                </StatNumber>
                <StatHelpText>
                  <FiAward /> Score: {marketIntelligence.competitivePosition.atom.score}/100
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getDominanceValue(6 - marketIntelligence.competitivePosition.atom.position + 1, 5)}
                color={getDominanceColor(6 - marketIntelligence.competitivePosition.atom.position + 1, 5)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: #1 (Market Leader)
              </Text>
            </CardBody>
          </Card>

          {/* Brand Awareness */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Brand Awareness</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {marketIntelligence.brandAwareness.atom}%
                </StatNumber>
                <StatHelpText>
                  <FiTrendingUp /> Growing 25% monthly
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getDominanceValue(marketIntelligence.brandAwareness.atom, 50)}
                color={getDominanceColor(marketIntelligence.brandAwareness.atom, 50)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: 50% (Brand Leader)
              </Text>
            </CardBody>
          </Card>

          {/* Innovation Score */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Innovation Score</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {marketIntelligence.featureComparison.innovationScore}
                </StatNumber>
                <StatHelpText>
                  <FiZap /> AI-Powered Innovation
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getDominanceValue(marketIntelligence.featureComparison.innovationScore, 100)}
                color={getDominanceColor(marketIntelligence.featureComparison.innovationScore, 100)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: 95 (Innovation Leader)
              </Text>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Detailed Market Intelligence Tabs */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardHeader>
            <Heading size="md">Market Intelligence Analysis</Heading>
          </CardHeader>
          <CardBody>
            <Tabs variant="enclosed">
              <TabList>
                <Tab>📊 Market Share</Tab>
                <Tab>🏆 Competitive Position</Tab>
                <Tab>🎯 Brand Awareness</Tab>
                <Tab>💰 Pricing Analysis</Tab>
                <Tab>🚀 Feature Comparison</Tab>
                <Tab>👥 Customer Segments</Tab>
                <Tab>🌍 Global Presence</Tab>
                <Tab>🛠️ Ecosystem</Tab>
              </TabList>

              <TabPanels>
                {/* Market Share Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={Object.entries(marketIntelligence.marketShare.competitors).map(([name, share]) => ({
                              name,
                              value: share,
                              color: name === 'atom' ? dominationColor : undefined
                            }))}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, value, color }) => (
                              <text fill={color ? color : textColor}>
                                {name}: {value}%
                              </text>
                            )}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                          >
                            {Object.entries(marketIntelligence.marketShare.competitors).map(([name, share], index) => (
                              <Cell key={`cell-${index}`} fill={name === 'atom' ? dominationColor : `hsl(${index * 45}, 70%, 50%)`} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </Box>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={marketIntelligence.marketShare.prediction.map((share, i) => ({
                          period: `Month ${i + 1}`,
                          atom: share,
                          target: 10
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="atom" stroke={dominationColor} name="ATOM" />
                          <Line type="monotone" dataKey="target" stroke="#805AD5" strokeDasharray="5 5" name="Target" />
                        </LineChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Competitive Position Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(300px, 1fr))" gap={4}>
                      {/* ATOM Position */}
                      <Box p={4} border="1px" borderColor={borderColor} borderRadius="md">
                        <Heading size="sm" color={textColor} mb={3}>ATOM Position</Heading>
                        <VStack align="start" spacing={2}>
                          <HStack>
                            <Text fontWeight="bold">Position:</Text>
                            <Badge colorScheme="purple">#{marketIntelligence.competitivePosition.atom.position}</Badge>
                          </HStack>
                          <HStack>
                            <Text fontWeight="bold">Score:</Text>
                            <Text>{marketIntelligence.competitivePosition.atom.score}/100</Text>
                          </HStack>
                        </VStack>
                        
                        <Box mt={3}>
                          <Text fontWeight="bold" mb={2}>Strengths:</Text>
                          <VStack align="start" spacing={1}>
                            {marketIntelligence.competitivePosition.atom.strengths.map((strength, i) => (
                              <HStack key={i}>
                                <Text fontSize="sm" color={successColor}>✓</Text>
                                <Text fontSize="sm">{strength}</Text>
                              </HStack>
                            ))}
                          </VStack>
                        </Box>
                      </Box>

                      {/* SWOT Analysis */}
                      <Box p={4} border="1px" borderColor={borderColor} borderRadius="md">
                        <Heading size="sm" color={textColor} mb={3}>SWOT Analysis</Heading>
                        <VStack align="start" spacing={3}>
                          <Box>
                            <Text fontWeight="bold" color={successColor}>Opportunities:</Text>
                            <VStack align="start" spacing={1}>
                              {marketIntelligence.competitivePosition.atom.opportunities.map((opp, i) => (
                                <Text key={i} fontSize="sm">• {opp}</Text>
                              ))}
                            </VStack>
                          </Box>
                          
                          <Box>
                            <Text fontWeight="bold" color={errorColor}>Threats:</Text>
                            <VStack align="start" spacing={1}>
                              {marketIntelligence.competitivePosition.atom.threats.map((threat, i) => (
                                <Text key={i} fontSize="sm">• {threat}</Text>
                              ))}
                            </VStack>
                          </Box>
                        </VStack>
                      </Box>
                    </Grid>
                    
                    {/* Competitor Comparison */}
                    <Box h={400}>
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart data={Object.keys(marketIntelligence.competitivePosition.competitors).map(name => ({
                          competitor: name,
                          score: marketIntelligence.competitivePosition.competitors[name].score,
                          atom: name === 'atom' ? marketIntelligence.competitivePosition.atom.score : null
                        }))}>
                          <PolarGrid />
                          <PolarAngleAxis dataKey="competitor" />
                          <PolarRadiusAxis domain={[0, 100]} />
                          <Radar name="Score" dataKey="score" stroke={dominationColor} fill={dominationColor} fillOpacity={0.6} />
                          <Tooltip />
                        </RadarChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Brand Awareness Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>ATOM Brand Awareness</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.brandAwareness.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing 25% monthly</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Brand Sentiment</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.brandAwareness.sentiment.atom}</Text>
                        <Text fontSize="sm" color="gray.600">Positive sentiment</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={Object.entries(marketIntelligence.brandAwareness.competitors).map(([name, awareness]) => ({
                          name,
                          awareness,
                          atom: name === 'atom' ? awareness : null
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="awareness" fill={dominationColor} />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Pricing Analysis Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>ATOM Pricing Strategy</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.pricingAnalysis.atom.strategy}</Text>
                        <Text fontSize="sm" color="gray.600">Value-Based Pricing</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Price Competitiveness</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.pricingAnalysis.atom.competitiveness}%</Text>
                        <Text fontSize="sm" color="gray.600">Highly Competitive</Text>
                      </Box>
                    </Grid>
                    
                    <TableContainer>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Plan</Th>
                            <Th>ATOM</Th>
                            <Th>Zapier</Th>
                            <Th>Make</Th>
                            <Th>Integromat</Th>
                            <Th>Tray</Th>
                            <Th>Automate</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          <Tr>
                            <Td>Starter</Td>
                            <Td color={successColor}>Free</Td>
                            <Td>$19</Td>
                            <Td>$9</Td>
                            <Td>$9</Td>
                            <Td>$29</Td>
                            <Td color={successColor}>Free</Td>
                          </Tr>
                          <Tr>
                            <Td>Professional</Td>
                            <Td color={dominationColor}>$29</Td>
                            <Td>$49</Td>
                            <Td>$19</Td>
                            <Td>$29</Td>
                            <Td>$59</Td>
                            <Td>$19</Td>
                          </Tr>
                          <Tr>
                            <Td>Business</Td>
                            <Td color={dominationColor}>$99</Td>
                            <Td>$99</Td>
                            <Td>$49</Td>
                            <Td>$79</Td>
                            <Td>$129</Td>
                            <Td>$49</Td>
                          </Tr>
                          <Tr>
                            <Td>Enterprise</Td>
                            <Td color={dominationColor}>$499</Td>
                            <Td>$699</Td>
                            <Td>$299</Td>
                            <Td>$399</Td>
                            <Td>$599</Td>
                            <Td>$199</Td>
                          </Tr>
                        </Tbody>
                      </Table>
                    </TableContainer>
                  </VStack>
                </TabPanel>

                {/* Feature Comparison Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Innovation Score</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.featureComparison.innovationScore}</Text>
                        <Text fontSize="sm" color="gray.600">AI-Powered Innovation</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Feature Leadership</Text>
                        <VStack align="start" spacing={1}>
                          {marketIntelligence.featureComparison.leadership.map((feature, i) => (
                            <HStack key={i}>
                              <Text fontSize="sm" color={dominationColor}>✓</Text>
                              <Text fontSize="sm">{feature}</Text>
                            </HStack>
                          ))}
                        </VStack>
                      </Box>
                    </Grid>
                    
                    <Box h={400}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={Object.entries(marketIntelligence.featureComparison.atom).map(([feature, score]) => ({
                          feature: feature.charAt(0).toUpperCase() + feature.slice(1),
                          atom: score,
                          zapier: marketIntelligence.featureComparison.competitors.zapier[feature],
                          make: marketIntelligence.featureComparison.competitors.make[feature]
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="feature" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="atom" fill={dominationColor} name="ATOM" />
                          <Bar dataKey="zapier" fill="#3182CE" name="Zapier" />
                          <Bar dataKey="make" fill="#805AD5" name="Make" />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Customer Segments Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Enterprise Segment</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.customerSegments.enterprise.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing 25% monthly</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>SMB Segment</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.customerSegments.smb.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing 18% monthly</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Startup Segment</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.customerSegments.startup.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing 22% monthly</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Developer Segment</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.customerSegments.developer.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing 30% monthly</Text>
                      </Box>
                    </Grid>
                  </VStack>
                </TabPanel>

                {/* Global Presence Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>North America</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.globalPresence.northAmerica.atom}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Europe</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.globalPresence.europe.atom}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Asia Pacific</Text>
                        <Text fontSize="2xl" color={warningColor}>{marketIntelligence.globalPresence.asiaPacific.atom}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Latin America</Text>
                        <Text fontSize="2xl" color={errorColor}>{marketIntelligence.globalPresence.latinAmerica.atom}%</Text>
                      </Box>
                    </Grid>
                  </VStack>
                </TabPanel>

                {/* Ecosystem Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Integrations</Text>
                        <Text fontSize="2xl" color={dominationColor}>{marketIntelligence.ecosystem.integrations.atom}</Text>
                        <Text fontSize="sm" color="gray.600">Most Comprehensive</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Developer Tools</Text>
                        <Text fontSize="2xl" color={successColor}>{marketIntelligence.ecosystem.developerTools.atom}</Text>
                        <Text fontSize="sm" color="gray.600">Excellent Coverage</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Community</Text>
                        <Text fontSize="2xl" color={warningColor}>{marketIntelligence.ecosystem.community.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Growing Fast</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Marketplace</Text>
                        <Text fontSize="2xl" color={warningColor}>{marketIntelligence.ecosystem.marketplace.atom}%</Text>
                        <Text fontSize="sm" color="gray.600">Expanding</Text>
                      </Box>
                    </Grid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </CardBody>
        </Card>

        {/* Market Domination Quick Actions */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardHeader>
            <Heading size="md">Market Domination Quick Actions</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
              <Button colorScheme="purple" size="sm" onClick={() => window.open('https://domination.atom-platform.com', '_blank')}>
                Domination Dashboard
              </Button>
              <Button colorScheme="blue" size="sm" onClick={() => window.open('https://competitive.atom-platform.com', '_blank')}>
                Competitive Intelligence
              </Button>
              <Button colorScheme="green" size="sm" onClick={() => window.open('https://global.atom-platform.com', '_blank')}>
                Global Expansion
              </Button>
              <Button colorScheme="orange" size="sm" onClick={() => window.open('https://ecosystem.atom-platform.com', '_blank')}>
                Ecosystem Development
              </Button>
            </Grid>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default MarketIntelligenceDashboard;