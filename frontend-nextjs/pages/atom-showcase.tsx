/**
 * ATOM Integration Showcase Page
 * Highlight Next.js integration and all available integrations
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Progress,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  UnorderedList,
  ListItem,
  ListIcon,
  Alert,
  AlertIcon
} from '@chakra-ui/react';
import {
  CodeIcon,
  BoxIcon,
  DropboxIcon,
  GoogleDriveIcon,
  SlackIcon,
  GmailIcon,
  NotionIcon,
  JiraIcon,
  GitHubIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ArrowRightIcon,
  RocketIcon,
  StarIcon,
  SettingsIcon,
  LightningIcon,
  ShieldIcon,
  CpuIcon,
  DatabaseIcon
} from '@chakra-ui/icons';

const ATOMIntegrationShowcase: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    connected: 0,
    total: 9,
    healthy: 0,
    skills: 72,
    processing: false
  });
  const [nextjsStatus, setNextjsStatus] = useState({
    connected: false,
    projects: 0,
    deployments: 0,
    builds: 0
  });
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const integrations = [
    {
      id: 'box',
      name: 'Box',
      description: 'Secure file storage and collaboration',
      category: 'storage',
      status: 'complete',
      icon: BoxIcon,
      color: 'blue'
    },
    {
      id: 'dropbox',
      name: 'Dropbox',
      description: 'Cloud storage and file sharing',
      category: 'storage',
      status: 'complete',
      icon: DropboxIcon,
      color: 'blue'
    },
    {
      id: 'gdrive',
      name: 'Google Drive',
      description: 'Cloud storage and document management',
      category: 'storage',
      status: 'complete',
      icon: GoogleDriveIcon,
      color: 'green'
    },
    {
      id: 'slack',
      name: 'Slack',
      description: 'Team communication and collaboration',
      category: 'communication',
      status: 'complete',
      icon: SlackIcon,
      color: 'purple'
    },
    {
      id: 'gmail',
      name: 'Gmail',
      description: 'Email communication and organization',
      category: 'communication',
      status: 'complete',
      icon: GmailIcon,
      color: 'red'
    },
    {
      id: 'notion',
      name: 'Notion',
      description: 'Document management and knowledge base',
      category: 'productivity',
      status: 'complete',
      icon: NotionIcon,
      color: 'gray'
    },
    {
      id: 'jira',
      name: 'Jira',
      description: 'Project management and issue tracking',
      category: 'productivity',
      status: 'complete',
      icon: JiraIcon,
      color: 'blue'
    },
    {
      id: 'github',
      name: 'GitHub',
      description: 'Code repository and development tools',
      category: 'development',
      status: 'complete',
      icon: GitHubIcon,
      color: 'black'
    },
    {
      id: 'nextjs',
      name: 'Next.js',
      description: 'Vercel project management and deployment',
      category: 'development',
      status: 'complete',
      icon: CodeIcon,
      color: 'black',
      featured: true
    }
  ];

  const nextjsFeatures = [
    'Complete OAuth 2.0 authentication with Vercel',
    'Real-time project monitoring and management',
    'Build tracking with live status updates',
    'Deployment automation and management',
    'Performance analytics and insights',
    'Environment variable management',
    'Webhook integration for real-time updates',
    'Cross-platform support (Web + Desktop)',
    '8 AI skills for automation',
    'Secure token encryption and storage'
  ];

  const checkIntegrationsHealth = async () => {
    try {
      setStats(prev => ({ ...prev, processing: true }));
      
      const healthChecks = await Promise.all([
        fetch('/api/integrations/box/health'),
        fetch('/api/integrations/dropbox/health'),
        fetch('/api/integrations/gdrive/health'),
        fetch('/api/integrations/slack/health'),
        fetch('/api/integrations/gmail/health'),
        fetch('/api/integrations/notion/health'),
        fetch('/api/integrations/jira/health'),
        fetch('/api/integrations/github/health'),
        fetch('/api/nextjs/health')
      ]);

      const connected = healthChecks.filter(check => check.ok).length;
      const healthy = healthChecks.filter(check => check.ok).length;

      // Check Next.js specific status
      const nextjsResponse = healthChecks[8];
      let nextjsData = { connected: false, projects: 0, deployments: 0, builds: 0 };
      
      if (nextjsResponse.ok) {
        const nextjsHealth = await nextjsResponse.json();
        nextjsData = {
          connected: nextjsHealth.status === 'healthy',
          projects: Math.floor(Math.random() * 10) + 1, // Demo data
          deployments: Math.floor(Math.random() * 50) + 10, // Demo data
          builds: Math.floor(Math.random() * 100) + 20 // Demo data
        };
      }

      setStats(prev => ({
        ...prev,
        connected,
        healthy,
        processing: false
      }));

      setNextjsStatus(nextjsData);

    } catch (error) {
      console.error('Health check failed:', error);
      setStats(prev => ({ ...prev, processing: false }));
    } finally {
      setLoading(false);
    }
  };

  const getConnectionProgress = () => {
    return (stats.connected / stats.total) * 100;
  };

  const getNextjsIntegrationStatus = () => {
    if (nextjsStatus.connected) return 'connected';
    return 'available';
  };

  const handleConnectNextjs = () => {
    onOpen();
  };

  const handleViewIntegrations = () => {
    window.location.href = '/integrations';
  };

  const handleViewDashboard = () => {
    window.location.href = '/dashboard';
  };

  useEffect(() => {
    checkIntegrationsHealth();
    
    // Simulate processing
    setTimeout(() => {
      setStats(prev => ({ ...prev, processing: true }));
      setTimeout(() => {
        checkIntegrationsHealth();
      }, 2000);
    }, 1000);
  }, []);

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={12} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack spacing={6} textAlign="center" py={12}>
          <HStack justify="center" spacing={4}>
            <Icon as={StarIcon} w={8} h={8} color="yellow.500" />
            <Icon as={CpuIcon} w={8} h={8} color="blue.500" />
            <Icon as={DatabaseIcon} w={8} h={8} color="green.500" />
          </HStack>
          <Heading size="4xl" fontWeight="bold" color="gray.800">
            ATOM Integration Platform
          </Heading>
          <Text fontSize="xl" color="gray.600" maxW="800px">
            Connect your favorite tools, automate workflows, and unlock intelligent insights 
            with our comprehensive integration ecosystem
          </Text>
        </VStack>

        {/* Featured Integration - Next.js */}
        <Card 
          border="3px" 
          borderColor="blue.500" 
          shadow="2xl"
          bg="blue.50"
        >
          <CardBody>
            <VStack spacing={8} align="stretch">
              <HStack justify="space-between" align="start">
                <VStack align="start" spacing={4}>
                  <HStack spacing={4}>
                    <Icon as={CodeIcon} w={12} h={12} color="blue.600" />
                    <VStack align="start" spacing={1}>
                      <Heading size="2xl" color="blue.700">
                        Next.js Integration
                      </Heading>
                      <HStack spacing={2}>
                        <Badge colorScheme="green" variant="solid" size="md">
                          COMPLETE
                        </Badge>
                        <Badge colorScheme="blue" variant="solid" size="md">
                          NEW
                        </Badge>
                        <Badge colorScheme="orange" variant="solid" size="md">
                          FEATURED
                        </Badge>
                      </HStack>
                    </VStack>
                  </HStack>
                  
                  <VStack align="start" spacing={2}>
                    <Text fontSize="lg" fontWeight="bold" color="blue.700">
                      Complete Vercel Project Management
                    </Text>
                    <Text color="gray.700" maxW="600px">
                      Connect your Vercel account to manage Next.js projects, monitor deployments, 
                      track builds, and access performance analytics. Real-time updates and 
                      automation included.
                    </Text>
                  </VStack>
                  
                  <HStack spacing={4}>
                    <Button
                      colorScheme="blue"
                      size="lg"
                      leftIcon={<RocketIcon />}
                      onClick={handleConnectNextjs}
                    >
                      Connect Next.js
                    </Button>
                    <Button
                      variant="outline"
                      size="lg"
                      leftIcon={<ExternalLinkIcon />}
                      onClick={() => window.location.href = '/integrations/nextjs'}
                    >
                      Learn More
                    </Button>
                  </HStack>
                </VStack>
                
                <VStack spacing={4} align="center">
                  <Icon as={ShieldIcon} w={16} h={16} color="blue.500" />
                  <Text fontSize="lg" fontWeight="bold" color="blue.700">
                    Production Ready
                  </Text>
                  <Badge colorScheme="green" variant="solid" size="lg">
                    Enterprise Grade
                  </Badge>
                </VStack>
              </HStack>
              
              {/* Next.js Stats */}
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={6}>
                <Card bg="white" border="1px" borderColor="gray.200">
                  <CardBody>
                    <VStack spacing={2} align="center">
                      <Icon as={CheckCircleIcon} w={8} h={8} color="green.500" />
                      <Text fontSize="2xl" fontWeight="bold" color="green.500">
                        {nextjsStatus.connected ? 'Connected' : 'Available'}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Integration Status
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>
                
                <Card bg="white" border="1px" borderColor="gray.200">
                  <CardBody>
                    <VStack spacing={2} align="center">
                      <Icon as={CodeIcon} w={8} h={8} color="blue.500" />
                      <Text fontSize="2xl" fontWeight="bold" color="blue.500">
                        {nextjsStatus.projects}+
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Projects Managed
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>
                
                <Card bg="white" border="1px" borderColor="gray.200">
                  <CardBody>
                    <VStack spacing={2} align="center">
                      <Icon as={RocketIcon} w={8} h={8" color="purple.500" />
                      <Text fontSize="2xl" fontWeight="bold" color="purple.500">
                        {nextjsStatus.deployments}+
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        Deployments Tracked
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>
                
                <Card bg="white" border="1px" borderColor="gray.200">
                  <CardBody>
                    <VStack spacing={2} align="center">
                      <Icon as={LightningIcon} w={8} h={8" color="orange.500" />
                      <Text fontSize="2xl" fontWeight="bold" color="orange.500">
                        8
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        AI Skills Available
                      </Text>
                    </VStack>
                  </CardBody>
                </Card>
              </SimpleGrid>
            </VStack>
          </CardBody>
        </Card>

        {/* Features Modal */}
        <Modal isOpen={isOpen} onClose={onClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              <HStack spacing={3}>
                <Icon as={CodeIcon} w={8} h={8} color="blue.600" />
                <Heading size="lg">Next.js Integration Features</Heading>
              </HStack>
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="stretch">
                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  <Text>Complete enterprise-grade Next.js/Vercel integration</Text>
                </Alert>
                
                <UnorderedList spacing={3}>
                  {nextjsFeatures.map((feature, index) => (
                    <ListItem key={index} fontSize="md">
                      <ListIcon as={CheckCircleIcon} color="green.500" />
                      {feature}
                    </ListItem>
                  ))}
                </UnorderedList>
                
                <Divider />
                
                <HStack justify="space-between">
                  <Text fontWeight="bold">Status:</Text>
                  <Badge colorScheme="green" variant="solid">
                    Production Ready
                  </Badge>
                </HStack>
                
                <Button
                  colorScheme="blue"
                  size="lg"
                  onClick={() => {
                    window.location.href = '/integrations/nextjs';
                  }}
                  width="full"
                >
                  Connect Next.js Now
                </Button>
              </VStack>
            </ModalBody>
          </ModalContent>
        </Modal>

        {/* Overall Stats */}
        <Card>
          <CardBody>
            <VStack spacing={6} align="stretch">
              <VStack spacing={3}>
                <Heading size="xl">Integration Ecosystem</Heading>
                <Text color="gray.600">
                  Comprehensive connectivity across your favorite tools
                </Text>
              </VStack>
              
              <SimpleGrid columns={{ base: 1, md: 4 }} spacing={6}>
                <VStack spacing={3} align="center">
                  <Icon as={CheckCircleIcon} w={10} h={10} color="blue.500" />
                  <Text fontSize="3xl" fontWeight="bold" color="blue.500">
                    {stats.connected}
                  </Text>
                  <Text fontSize="sm" color="gray.600" textAlign="center">
                    of {stats.total} Integrations Connected
                  </Text>
                </VStack>
                
                <VStack spacing={3} align="center">
                  <Icon as={StarIcon} w={10} h={10} color="green.500" />
                  <Text fontSize="3xl" fontWeight="bold" color="green.500">
                    {stats.healthy}
                  </Text>
                  <Text fontSize="sm" color="gray.600" textAlign="center">
                    Healthy Services
                  </Text>
                </VStack>
                
                <VStack spacing={3" align="center">
                  <Icon as={CpuIcon} w={10} h={10} color="purple.500" />
                  <Text fontSize="3xl" fontWeight="bold" color="purple.500">
                    {stats.skills}
                  </Text>
                  <Text fontSize="sm" color="gray.600" textAlign="center">
                    AI Skills Available
                  </Text>
                </VStack>
                
                <VStack spacing={3" align="center">
                  <Icon as={TimeIcon} w={10} h={10" color="orange.500" />
                  <Text fontSize="3xl" fontWeight="bold" color="orange.500">
                    {stats.processing ? 'Syncing...' : 'Ready'}
                  </Text>
                  <Text fontSize="sm" color="gray.600" textAlign="center">
                    Data Pipeline Status
                  </Text>
                </VStack>
              </SimpleGrid>
              
              <VStack spacing={3" w="full">
                <HStack justify="space-between" w="full">
                  <Text fontSize="lg" fontWeight="bold">
                    Connection Progress
                  </Text>
                  <Text fontSize="lg" fontWeight="bold" color="blue.500">
                    {Math.round(getConnectionProgress())}%
                  </Text>
                </HStack>
                <Progress
                  value={getConnectionProgress()}
                  colorScheme="blue"
                  size="lg"
                  borderRadius="md"
                />
              </VStack>
            </VStack>
          </CardBody>
        </Card>

        {/* All Integrations Grid */}
        <VStack spacing={6} align="stretch">
          <VStack spacing={3">
            <Heading size="xl">Available Integrations</Heading>
            <Text color="gray.600">
              Click to connect any integration to your ATOM workspace
            </Text>
          </VStack>
          
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
            {integrations.map((integration) => (
              <Card
                key={integration.id}
                cursor="pointer"
                onClick={() => {
                  if (integration.id === 'nextjs') {
                    handleConnectNextjs();
                  } else {
                    window.location.href = `/integrations/${integration.id}`;
                  }
                }}
                bg={bgColor}
                border="1px"
                borderColor={borderColor}
                _hover={{
                  shadow: 'lg',
                  transform: 'translateY(-4px)',
                  transition: 'all 0.3s'
                }}
                position="relative"
              >
                {integration.featured && (
                  <Badge
                    colorScheme="orange"
                    variant="solid"
                    size="sm"
                    position="absolute"
                    top="2"
                    right="2"
                    zIndex={1}
                  >
                    FEATURED
                  </Badge>
                )}
                
                <CardBody>
                  <VStack spacing={4} align="start">
                    <HStack spacing={4}>
                      <Icon 
                        as={integration.icon} 
                        w={10} h={10} 
                        color={integration.color}
                      />
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold" fontSize="lg">
                          {integration.name}
                        </Text>
                        <Badge colorScheme={
                          integration.id === 'nextjs' ? 'orange' :
                          integration.status === 'complete' ? 'green' : 'gray'
                        } size="sm">
                          {integration.status.toUpperCase()}
                        </Badge>
                      </VStack>
                    </HStack>
                    
                    <Text color="gray.600" fontSize="sm">
                      {integration.description}
                    </Text>
                    
                    <HStack justify="space-between" w="full">
                      <Text fontSize="xs" color="gray.500">
                        Category: {integration.category}
                      </Text>
                      {integration.id === 'nextjs' && (
                        <HStack>
                          <CheckCircleIcon color="green.500" w={4} h={4} />
                          <Text fontSize="xs" color="green.500" fontWeight="bold">
                            COMPLETE
                          </Text>
                        </HStack>
                      )}
                    </HStack>
                    
                    <Button
                      variant={integration.id === 'nextjs' ? 'solid' : 'outline'}
                      colorScheme={integration.id === 'nextjs' ? 'orange' : 'gray'}
                      size="sm"
                      width="full"
                      leftIcon={<ArrowRightIcon />}
                    >
                      {integration.id === 'nextjs' ? 'Learn More' : 'Connect'}
                    </Button>
                  </VStack>
                </CardBody>
              </Card>
            ))}
          </SimpleGrid>
        </VStack>

        {/* Call to Action */}
        <Card bg="gradient-to-r" bgGradient="linear(to-r, blue.500, purple.600)" color="white">
          <CardBody>
            <HStack justify="space-between" align="center">
              <VStack align="start" spacing={3" maxW="600px">
                <Heading size="xl" color="white">
                  Ready to Transform Your Workflow?
                </Heading>
                <Text color="white" fontSize="lg" opacity={0.9}>
                  Start with Next.js integration and experience the full power of ATOM's 
                  intelligent automation and insights.
                </Text>
              </VStack>
              
              <VStack spacing={3" align="end">
                <Button
                  colorScheme="white"
                  variant="solid"
                  size="lg"
                  leftIcon={<RocketIcon />}
                  onClick={handleConnectNextjs}
                  boxShadow="lg"
                >
                  Get Started Now
                </Button>
                <Button
                  colorScheme="white"
                  variant="outline"
                  size="md"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={handleViewIntegrations}
                >
                  View All Integrations
                </Button>
              </VStack>
            </HStack>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default ATOMIntegrationShowcase;