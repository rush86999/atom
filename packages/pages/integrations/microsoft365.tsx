/**
 * Microsoft 365 Integration Page
 * Complete Microsoft 365 unified platform integration page
 */

import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { Box, Container, VStack, Heading, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';

import Microsoft365Manager, { Microsoft365ManagerProps } from '../../src/ui-shared/integrations/microsoft365/components/Microsoft365Manager';
import { getIntegrationConfig, setIntegrationConfig } from '../../src/lib/integration-config';
import { validateEnvironmentConfig } from '../../src/lib/environment-validation';
import { createMicrosoft365SkillsService, Microsoft365Config } from '../../src/ui-shared/integrations/microsoft365/skills/microsoft365Skills';

// Page Props
interface Microsoft365PageProps {
  initialConfig: Partial<Microsoft365Config>;
  isConfigured: boolean;
  environmentVars: Record<string, string>;
  error?: string;
}

// Main Page Component
const Microsoft365Page: React.FC<Microsoft365PageProps> = ({
  initialConfig,
  isConfigured,
  environmentVars,
  error
}) => {
  const [config, setConfig] = useState<Partial<Microsoft365Config>>(initialConfig);
  const [connected, setConnected] = useState(isConfigured);

  // Handle configuration updates
  const handleConfigUpdate = async (newConfig: Partial<Microsoft365Config>) => {
    try {
      await setIntegrationConfig('microsoft365', newConfig);
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
      toast.success('Connected to Microsoft 365');
    } else {
      toast.error('Disconnected from Microsoft 365');
    }
  };

  // Handle errors
  const handleError = (error: Error) => {
    console.error('Microsoft 365 Integration Error:', error);
    toast.error(error.message || 'An error occurred');
  };

  // Handle success events
  const handleSuccess = (message: string) => {
    console.log('Microsoft 365 Integration Success:', message);
    toast.success(message);
  };

  // Check initial connection status
  useEffect(() => {
    const checkConnection = async () => {
      try {
        if (config.tenantId && config.clientId && config.clientSecret) {
          const service = createMicrosoft365SkillsService(config as Microsoft365Config);
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
        <title>Microsoft 365 Integration | ATOM Platform</title>
        <meta name="description" content="Complete Microsoft 365 unified platform integration with Teams, Outlook, OneDrive, SharePoint, Power Platform, and enterprise productivity tools" />
        <meta name="keywords" content="Microsoft 365, Teams, Outlook, OneDrive, SharePoint, Power Platform, Office 365, enterprise productivity, integration" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta property="og:title" content="Microsoft 365 Integration | ATOM Platform" />
        <meta property="og:description" content="Complete Microsoft 365 unified platform integration with Teams, Outlook, OneDrive, SharePoint, Power Platform, and enterprise productivity tools" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://atom-platform.com/integrations/microsoft365" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Microsoft 365 Integration | ATOM Platform" />
        <meta name="twitter:description" content="Complete Microsoft 365 unified platform integration with Teams, Outlook, OneDrive, SharePoint, Power Platform, and enterprise productivity tools" />
      </Head>

      <Box minH="100vh" bg="gray.50">
        <Container maxW="container.xl" py={8}>
          <VStack spacing={8} align="stretch">
            {/* Page Header */}
            <VStack spacing={4} align="center" textAlign="center">
              <Heading size="2xl" color="blue.600" fontWeight="bold">
                Microsoft 365 Integration
              </Heading>
              <Text fontSize="lg" color="gray.600" maxW="3xl">
                Complete Microsoft 365 unified platform integration with Teams, Outlook, OneDrive, SharePoint, 
                Power Platform, and enterprise productivity tools. Connect all your Microsoft services 
                in one unified interface.
              </Text>
              {connected && (
                <Box bg="green.100" color="green.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">✅ Connected to Microsoft 365</Text>
                </Box>
              )}
              {!connected && (
                <Box bg="orange.100" color="orange.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">⚠️ Not Connected - Configure Microsoft 365</Text>
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
              <Microsoft365Manager
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
export const getServerSideProps: GetServerSideProps<Microsoft365PageProps> = async ({ req }) => {
  try {
    // Validate environment configuration
    const envValidation = validateEnvironmentConfig('microsoft365');
    
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
    const config = await getIntegrationConfig('microsoft365');
    
    // Check if properly configured
    const isConfigured = !!(
      config?.tenantId && 
      config?.clientId && 
      config?.clientSecret && 
      config?.redirectUri
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
    console.error('Error in getServerSideProps for Microsoft 365:', error);
    
    return {
      props: {
        initialConfig: {},
        isConfigured: false,
        environmentVars: {},
        error: 'Failed to load Microsoft 365 configuration'
      }
    };
  }
};

export default Microsoft365Page;