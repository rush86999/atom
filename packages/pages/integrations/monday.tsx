/**
 * Monday.com Integration Page
 * Complete Work OS platform integration with boards, items, columns, groups, workflows, and team collaboration
 */

import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { Box, Container, VStack, Heading, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';

import MondayManager, { MondayManagerProps } from '../../src/ui-shared/integrations/monday/components/MondayManager';
import { getIntegrationConfig, setIntegrationConfig } from '../../src/lib/integration-config';
import { validateEnvironmentConfig } from '../../src/lib/environment-validation';
import { createMondaySkillsService, MondayConfig } from '../../src/ui-shared/integrations/monday/skills/mondaySkills';

// Page Props
interface MondayPageProps {
  initialConfig: Partial<MondayConfig>;
  isConfigured: boolean;
  environmentVars: Record<string, string>;
  error?: string;
}

// Main Page Component
const MondayPage: React.FC<MondayPageProps> = ({
  initialConfig,
  isConfigured,
  environmentVars,
  error
}) => {
  const [config, setConfig] = useState<Partial<MondayConfig>>(initialConfig);
  const [connected, setConnected] = useState(isConfigured);

  // Handle configuration updates
  const handleConfigUpdate = async (newConfig: Partial<MondayConfig>) => {
    try {
      await setIntegrationConfig('monday', newConfig);
      setConfig(newConfig);
      toast.success('Configuration updated successfully');
    } catch (error) {
      console.error('Error updating configuration:', error);
      toast.error('Failed to update configuration');
    }
  };

  // Handle connection events
  const handleConnectionChange = (isConnected: boolean) => {
    setConnected(isConnected);
    if (isConnected) {
      toast.success('Connected to Monday.com');
    } else {
      toast.error('Disconnected from Monday.com');
    }
  };

  // Handle errors
  const handleError = (error: Error) => {
    console.error('Monday.com Integration Error:', error);
    toast.error(error.message || 'An error occurred');
  };

  // Handle success events
  const handleSuccess = (message: string) => {
    console.log('Monday.com Integration Success:', message);
    toast.success(message);
  };

  // Check initial connection status
  useEffect(() => {
    const checkConnection = async () => {
      try {
        if (config.apiToken) {
          const service = createMondaySkillsService(config as MondayConfig);
          const status = await service.checkAuthStatus();
          setConnected(status.authenticated);
        }
      } catch (error) {
        console.error('Error checking connection:', error);
      }
    };

    checkConnection();
  }, [config]);

  return (
    <>
      <Head>
        <title>Monday.com Integration | ATOM Platform</title>
        <meta name="description" content="Complete Monday.com Work OS integration with boards, items, columns, groups, automations, forms, and team collaboration features" />
        <meta name="keywords" content="Monday.com, Work OS, project management, team collaboration, boards, items, automation, forms" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta property="og:title" content="Monday.com Integration | ATOM Platform" />
        <meta property="og:description" content="Complete Monday.com Work OS integration with boards, items, columns, groups, automations, forms, and team collaboration features" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://atom-platform.com/integrations/monday" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Monday.com Integration | ATOM Platform" />
        <meta name="twitter:description" content="Complete Monday.com Work OS integration with boards, items, columns, groups, automations, forms, and team collaboration features" />
      </Head>

      <Box minH="100vh" bg="gray.50">
        <Container maxW="container.xl" py={8}>
          <VStack spacing={8} align="stretch">
            {/* Page Header */}
            <VStack spacing={4} align="center" textAlign="center">
              <Heading size="2xl" color="blue.600" fontWeight="bold">
                Monday.com Integration
              </Heading>
              <Text fontSize="lg" color="gray.600" maxW="3xl">
                Complete Monday.com Work OS integration with boards, items, columns, groups, automations, forms, 
                and team collaboration. Connect your entire Work OS ecosystem in one unified interface.
              </Text>
              {connected && (
                <Box bg="green.100" color="green.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">✅ Connected to Monday.com</Text>
                </Box>
              )}
              {!connected && (
                <Box bg="orange.100" color="orange.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">⚠️ Not Connected - Configure Monday.com</Text>
                </Box>
              )}
            </VStack>

            {/* Error Display */}
            {error && (
              <Box bg="red.100" color="red.800" p={4} borderRadius="md" borderWidth="1px" borderColor="red.200">
                <Heading size="md" mb={2}>Configuration Error</Heading>
                <Text>{error}</Text>
              </Box>
            )}

            {/* Integration Manager */}
            <Box>
              <MondayManager
                config={config}
                onError={handleError}
                onSuccess={handleSuccess}
                theme="light"
                compact={false}
              />
            </Box>

            {/* Environment Information */}
            {process.env.NODE_ENV === 'development' && (
              <Box bg="gray.100" p={4} borderRadius="md">
                <Heading size="sm" mb={2}>Environment Variables</Heading>
                <VStack align="start" spacing={1}>
                  {Object.entries(environmentVars).map(([key, value]) => (
                    <Text key={key} fontSize="xs">
                      <strong>{key}:</strong> {value ? '✅ Set' : '❌ Not Set'}
                    </Text>
                  ))}
                </VStack>
              </Box>
            )}
          </VStack>
        </Container>
      </Box>
    </>
  );
};

// Get Server Side Props
export const getServerSideProps: GetServerSideProps<MondayPageProps> = async ({ req }) => {
  try {
    // Validate environment configuration
    const envValidation = validateEnvironmentConfig('monday');
    
    if (!envValidation.isValid) {
      return {
        props: {
          initialConfig: {},
          isConfigured: false,
          environmentVars: envValidation.environmentVars,
          error: envValidation.error
        }
      };
    }

    // Get existing configuration
    const config = await getIntegrationConfig('monday');
    
    // Check if properly configured
    const isConfigured = !!(
      config?.apiToken
    );

    // Return props
    return {
      props: {
        initialConfig: config || {},
        isConfigured,
        environmentVars: envValidation.environmentVars,
        error: null
      }
    };

  } catch (error) {
    console.error('Error in getServerSideProps for Monday.com:', error);
    
    return {
      props: {
        initialConfig: {},
        isConfigured: false,
        environmentVars: {},
        error: 'Failed to load Monday.com configuration'
      }
    };
  }
};

export default MondayPage;