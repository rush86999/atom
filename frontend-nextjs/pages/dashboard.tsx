/**
 * Main ATOM Dashboard with Integrations
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
  Divider,
  useColorModeValue,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Progress
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
  SettingsIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ArrowRightIcon
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

const DashboardPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    connected: 0,
    total: 9,
    healthy: 0,
    errors: 0
  });
  const toast = useToast();
  const router = useRouter();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const integrationIcons = {
    box: BoxIcon,
    dropbox: DropboxIcon,
    gdrive: GoogleDriveIcon,
    slack: SlackIcon,
    gmail: GmailIcon,
    notion: NotionIcon,
    jira: JiraIcon,
    github: GitHubIcon,
    nextjs: CodeIcon
  };

  const checkIntegrationsHealth = async () => {
    try {
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

      const integrationList = [
        { id: 'box', name: 'Box', category: 'storage' },
        { id: 'dropbox', name: 'Dropbox', category: 'storage' },
        { id: 'gdrive', name: 'Google Drive', category: 'storage' },
        { id: 'slack', name: 'Slack', category: 'communication' },
        { id: 'gmail', name: 'Gmail', category: 'communication' },
        { id: 'notion', name: 'Notion', category: 'productivity' },
        { id: 'jira', name: 'Jira', category: 'productivity' },
        { id: 'github', name: 'GitHub', category: 'development' },
        { id: 'nextjs', name: 'Next.js', category: 'development' }
      ];

      const updatedIntegrations = integrationList.map((integration, index) => {
        const healthResponse = healthChecks[index];
        const connected = healthResponse.ok;
        const health = healthResponse.ok ? 'healthy' : 'error';
        
        return {
          ...integration,
          connected,
          health,
          icon: integrationIcons[integration.id as keyof typeof integrationIcons],
          lastSync: new Date().toISOString()
        };
      });

      const connected = updatedIntegrations.filter(i => i.connected).length;
      const healthy = updatedIntegrations.filter(i => i.health === 'healthy').length;
      const errors = updatedIntegrations.filter(i => i.health === 'error').length;

      setIntegrations(updatedIntegrations);
      setStats({
        connected,
        total: updatedIntegrations.length,
        healthy,
        errors
      });
    } catch (error) {
      console.error('Health check failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleIntegrationClick = (integrationId: string) => {
    router.push(`/integrations/${integrationId}`);
  };

  const getStatusIcon = (health: string) => {
    switch (health) {
      case 'healthy':
        return <CheckCircleIcon color="green.500" />;
      case 'warning':
        return <WarningIcon color="yellow.500" />;
      case 'error':
        return <WarningIcon color="red.500" />;
      default:
        return <TimeIcon color="gray.500" />;
    }
  };

  const getStatusBadge = (health: string) => {
    const colorScheme = health === 'healthy' ? 'green' : health === 'warning' ? 'yellow' : 'red';
    return (
      <Badge colorScheme={colorScheme} size="sm">
        {health}
      </Badge>
    );
  };

  const getConnectionProgress = () => {
    return (stats.connected / stats.total) * 100;
  };

  const getHealthProgress = () => {
    return (stats.healthy / stats.total) * 100;
  };

  useEffect(() => {
    checkIntegrationsHealth();
    
    // Auto-refresh every 2 minutes
    const interval = setInterval(checkIntegrationsHealth, 120000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <Heading size="3xl">ATOM Dashboard</Heading>
          <Text color="gray.600" fontSize="xl">
            Manage your connected integrations and data pipeline
          </Text>
        </VStack>

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Connected Integrations</StatLabel>
                <StatNumber color="blue.500">{stats.connected}</StatNumber>
                <StatHelpText>
                  of {stats.total} available
                </StatHelpText>
              </Stat>
              <Progress
                value={getConnectionProgress()}
                colorScheme="blue"
                size="sm"
                mt={3}
              />
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Healthy Services</StatLabel>
                <StatNumber color="green.500">{stats.healthy}</StatNumber>
                <StatHelpText>
                  {stats.errors} issues detected
                </StatHelpText>
              </Stat>
              <Progress
                value={getHealthProgress()}
                colorScheme="green"
                size="sm"
                mt={3}
              />
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Data Ingestion</StatLabel>
                <StatNumber color="purple.500">Active</StatNumber>
                <StatHelpText>
                  Last sync: Just now
                </StatHelpText>
              </Stat>
              <Progress
                value={100}
                colorScheme="purple"
                size="sm"
                mt={3}
              />
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>AI Skills</StatLabel>
                <StatNumber color="orange.500">72</StatNumber>
                <StatHelpText>
                  Available commands
                </StatHelpText>
              </Stat>
              <Progress
                value={100}
                colorScheme="orange"
                size="sm"
                mt={3}
              />
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Quick Actions */}
        <HStack justify="space-between" w="full">
          <VStack align="start" spacing={2}>
            <Heading size="lg">Quick Actions</Heading>
            <Text color="gray.600">Common tasks and management</Text>
          </VStack>
          
          <HStack>
            <Button
              variant="outline"
              leftIcon={<SettingsIcon />}
              onClick={() => router.push('/integrations')}
            >
              Manage Integrations
            </Button>
            <Button
              colorScheme="blue"
              leftIcon={<TimeIcon />}
              onClick={checkIntegrationsHealth}
              isLoading={loading}
            >
              Refresh Status
            </Button>
          </HStack>
        </HStack>

        {/* Integration Grid */}
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <VStack align="start" spacing={0}>
                <Heading size="lg">Connected Integrations</Heading>
                <Text color="gray.600">
                  Click to manage individual integrations
                </Text>
              </VStack>
              <Button
                variant="ghost"
                size="sm"
                rightIcon={<ArrowRightIcon />}
                onClick={() => router.push('/integrations')}
              >
                View All
              </Button>
            </HStack>
          </CardHeader>
          
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
              {integrations.map((integration) => (
                <Card
                  key={integration.id}
                  cursor="pointer"
                  onClick={() => handleIntegrationClick(integration.id)}
                  bg={bgColor}
                  border="1px"
                  borderColor={borderColor}
                  _hover={{
                    shadow: 'md',
                    transform: 'translateY(-2px)',
                    transition: 'all 0.2s'
                  }}
                >
                  <CardBody>
                    <VStack spacing={4} align="start">
                      <HStack justify="space-between" w="full">
                        <HStack>
                          <Icon 
                            as={integration.icon} 
                            w={6} h={6} 
                            color={
                              integration.id === 'nextjs' ? 'gray.800' :
                              integration.id === 'github' ? 'black' :
                              integration.id === 'slack' ? 'purple.500' :
                              integration.id === 'gmail' ? 'red.500' :
                              integration.id === 'notion' ? 'gray.600' :
                              integration.id === 'jira' ? 'blue.500' :
                              integration.id === 'box' ? 'blue.500' :
                              integration.id === 'dropbox' ? 'blue.600' :
                              integration.id === 'gdrive' ? 'green.500' :
                              'gray.500'
                            } 
                          />
                          <VStack align="start" spacing={0}>
                            <Text fontWeight="bold" fontSize="lg">
                              {integration.name}
                            </Text>
                            <Badge size="sm" colorScheme="gray">
                              {integration.category}
                            </Badge>
                          </VStack>
                        </HStack>
                        {getStatusIcon(integration.health)}
                      </HStack>
                      
                      <HStack justify="space-between" w="full">
                        <Text fontSize="sm" color="gray.600">
                          Status:
                        </Text>
                        {getStatusBadge(integration.health)}
                      </HStack>
                      
                      <HStack justify="space-between" w="full">
                        <Text fontSize="sm" color="gray.600">
                          {integration.connected ? 'Connected' : 'Disconnected'}
                        </Text>
                        {integration.connected ? (
                          <CheckCircleIcon color="green.500" w={4} h={4} />
                        ) : (
                          <WarningIcon color="red.500" w={4} h={4} />
                        )}
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </SimpleGrid>
            
            {integrations.length === 0 && (
              <VStack spacing={4} py={8}>
                <Icon as={TimeIcon} w={12} h={12} color="gray.400" />
                <Text color="gray.600" textAlign="center">
                  No integrations connected yet
                </Text>
                <Button
                  colorScheme="blue"
                  onClick={() => router.push('/integrations')}
                >
                  Connect Integrations
                </Button>
              </VStack>
            )}
          </CardBody>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <VStack align="start" spacing={2}>
              <Heading size="lg">Recent Activity</Heading>
              <Text color="gray.600">Latest integration events and syncs</Text>
            </VStack>
          </CardHeader>
          
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <HStack>
                  <Icon as={CodeIcon} w={4} h={4} color="blue.500" />
                  <Text>Next.js integration connected</Text>
                </HStack>
                <Text fontSize="sm" color="gray.500">
                  2 minutes ago
                </Text>
              </HStack>
              
              <HStack justify="space-between">
                <HStack>
                  <Icon as={GitHubIcon} w={4} h={4} color="black" />
                  <Text>GitHub repositories synced</Text>
                </HStack>
                <Text fontSize="sm" color="gray.500">
                  15 minutes ago
                </Text>
              </HStack>
              
              <HStack justify="space-between">
                <HStack>
                  <Icon as={SlackIcon} w={4} h={4} color="purple.500" />
                  <Text>Slack channels updated</Text>
                </HStack>
                <Text fontSize="sm" color="gray.500">
                  1 hour ago
                </Text>
              </HStack>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default DashboardPage;