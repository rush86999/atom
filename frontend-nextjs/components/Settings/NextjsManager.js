/**
 * Next.js Integration Settings Component
 * Settings UI for Next.js/Vercel integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Alert,
  AlertIcon,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  Divider,
  Switch,
  FormControl,
  FormLabel,
  Input,
  Select,
  useColorModeValue,
} from '@chakra-ui/react';
import {
  CodeIcon,
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  SettingsIcon,
  RepeatIcon,
} from '@chakra-ui/icons';
import dynamic from 'next/dynamic';

// Dynamically import the NextjsManager component from shared components
const NextjsManager = dynamic(
  () => import('../../../../../src/ui-shared/integrations/nextjs/components/NextjsManager'),
  { 
    ssr: false,
    loading: () => <Text>Loading Next.js integration...</Text>
  }
);

interface NextjsSettingsProps {
  atomIngestionPipeline?: any;
  onConfigurationChange?: (config: any) => void;
  onIngestionComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

export const NextjsSettings: React.FC<NextjsSettingsProps> = ({
  atomIngestionPipeline,
  onConfigurationChange,
  onIngestionComplete,
  onError,
}) => {
  const [health, setHealth] = useState<{ connected: boolean; errors: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [showIntegration, setShowIntegration] = useState(false);
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');

  // Check Next.js integration health
  const checkHealth = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/nextjs/health');
      const data = await response.json();
      
      if (data.services?.nextjs) {
        setHealth({
          connected: data.services.nextjs.status === 'healthy',
          errors: data.services.nextjs.error ? [data.services.nextjs.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        errors: ['Failed to check Next.js service health']
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={CodeIcon} w={6} h={6} color="blue.500" />
            <Heading size="md">Next.js Integration</Heading>
            <Badge colorScheme="blue">Vercel</Badge>
          </HStack>
          <HStack>
            <Badge
              colorScheme={health?.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={health?.connected ? CheckCircleIcon : WarningIcon} mr={1} />
              {health?.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={checkHealth}
              isLoading={loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Integration Overview */}
          <VStack align="start" spacing={3}>
            <Text>
              Connect your Vercel account to manage Next.js projects, deployments, and analytics directly from ATOM.
              This integration provides real-time monitoring of your applications and automated data ingestion.
            </Text>
            
            <HStack>
              <Button
                leftIcon={<ExternalLinkIcon />}
                variant="outline"
                onClick={() => window.open('https://vercel.com', '_blank')}
              >
                Visit Vercel
              </Button>
              <Button
                leftIcon={<SettingsIcon />}
                colorScheme="blue"
                onClick={() => setShowIntegration(!showIntegration)}
              >
                {showIntegration ? 'Hide Integration' : 'Configure Integration'}
              </Button>
            </HStack>
          </VStack>

          <Divider />

          {/* Health Status */}
          {health && (
            <Alert status={health.connected ? 'success' : 'warning'}>
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">
                  Next.js service {health.connected ? 'healthy' : 'unhealthy'}
                </Text>
                {health.errors.length > 0 && (
                  <Text fontSize="sm" color="red.500">
                    {health.errors.join(', ')}
                  </Text>
                )}
              </Box>
            </Alert>
          )}

          {/* Features Overview */}
          <VStack align="start" spacing={3}>
            <Text fontWeight="bold">Features Available:</Text>
            <VStack align="start" spacing={2} pl={4}>
              <Text>• 📊 Real-time project analytics and monitoring</Text>
              <Text>• 🚀 Deployment tracking and status updates</Text>
              <Text>• 🔧 Build history and log access</Text>
              <Text>• 🌐 Environment variable management</Text>
              <Text>• 📈 Performance metrics and insights</Text>
              <Text>• 🔔 Automated alerts and notifications</Text>
            </VStack>
          </VStack>

          {/* Integration Component */}
          {showIntegration && (
            <>
              <Divider />
              <NextjsManager
                atomIngestionPipeline={atomIngestionPipeline}
                onConfigurationChange={onConfigurationChange}
                onIngestionComplete={onIngestionComplete}
                onError={onError}
              />
            </>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
};

export default NextjsSettings;