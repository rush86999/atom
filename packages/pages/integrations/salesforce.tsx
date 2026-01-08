/**
 * Salesforce CRM Integration Page
 * Complete CRM platform with sales, service, marketing, and customer relationship management
 */

import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { Box, Container, VStack, Heading, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';

import SalesforceManager, { SalesforceManagerProps } from '../../src/ui-shared/integrations/salesforce/components/SalesforceManager';
import { getIntegrationConfig, setIntegrationConfig } from '../../src/lib/integration-config';
import { validateEnvironmentConfig } from '../../src/lib/environment-validation';
import { createSalesforceSkillsService, SalesforceConfig } from '../../src/ui-shared/integrations/salesforce/skills/salesforceSkills';

// Page Props
interface SalesforcePageProps {
  initialConfig: Partial<SalesforceConfig>;
  isConfigured: boolean;
  environmentVars: Record<string, string>;
  error?: string;
}

// Main Page Component
const SalesforcePage: React.FC<SalesforcePageProps> = ({
  initialConfig,
  isConfigured,
  environmentVars,
  error
}) => {
  const [config, setConfig] = useState<Partial<SalesforceConfig>>(initialConfig);
  const [connected, setConnected] = useState(isConfigured);

  // Handle configuration updates
  const handleConfigUpdate = async (newConfig: Partial<SalesforceConfig>) => {
    try {
      await setIntegrationConfig('salesforce', newConfig);
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
      toast.success('Connected to Salesforce');
    } else {
      toast.error('Disconnected from Salesforce');
    }
  };

  // Handle errors
  const handleError = (error: Error) => {
    console.error('Salesforce Integration Error:', error);
    toast.error(error.message || 'An error occurred');
  };

  // Handle success events
  const handleSuccess = (message: string) => {
    console.log('Salesforce Integration Success:', message);
    toast.success(message);
  };

  // Check initial connection status
  useEffect(() => {
    const checkConnection = async () => {
      try {
        if (config.clientId && config.clientSecret) {
          const service = createSalesforceSkillsService(config as SalesforceConfig);
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
        <title>Salesforce CRM Integration | ATOM Platform</title>
        <meta name="description" content="Complete Salesforce CRM integration with sales, service, marketing, and customer relationship management" />
        <meta name="keywords" content="Salesforce, CRM, sales, service, marketing, customer relationship management, SaaS" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta property="og:title" content="Salesforce CRM Integration | ATOM Platform" />
        <meta property="og:description" content="Complete Salesforce CRM integration with sales, service, marketing, and customer relationship management" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://atom-platform.com/integrations/salesforce" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Salesforce CRM Integration | ATOM Platform" />
        <meta name="twitter:description" content="Complete Salesforce CRM integration with sales, service, marketing, and customer relationship management" />
      </Head>

      <Box minH="100vh" bg="gray.50">
        <Container maxW="container.xl" py={8}>
          <VStack spacing={8} align="stretch">
            {/* Page Header */}
            <VStack spacing={4} align="center" textAlign="center">
              <Heading size="2xl" color="blue.600" fontWeight="bold">
                Salesforce CRM Integration
              </Heading>
              <Text fontSize="lg" color="gray.600" maxW="3xl">
                Complete Salesforce CRM integration with sales, service, marketing, and customer relationship management. 
                Connect your entire CRM ecosystem in one unified interface.
              </Text>
              {connected && (
                <Box bg="green.100" color="green.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">✅ Connected to Salesforce</Text>
                </Box>
              )}
              {!connected && (
                <Box bg="orange.100" color="orange.800" px={4} py={2} borderRadius="md">
                  <Text fontWeight="medium">⚠️ Not Connected - Configure Salesforce</Text>
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
              <SalesforceManager
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
export const getServerSideProps: GetServerSideProps<SalesforcePageProps> = async ({ req }) => {
  try {
    // Validate environment configuration
    const envValidation = validateEnvironmentConfig('salesforce');
    
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
    const config = await getIntegrationConfig('salesforce');
    
    // Check if properly configured
    const isConfigured = !!(
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
    console.error('Error in getServerSideProps for Salesforce:', error);
    
    return {
      props: {
        initialConfig: {},
        isConfigured: false,
        environmentVars: {},
        error: 'Failed to load Salesforce configuration'
      }
    };
  }
};

export default SalesforcePage;