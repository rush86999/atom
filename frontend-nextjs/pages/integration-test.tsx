/**
 * Integration Test Page - Verify frontend-backend connectivity
 */

import { useState } from 'react';
import {
  Box,
  Container,
  Heading,
  Text,
  Button,
  VStack,
  HStack,
  Badge,
  Code,
  Spinner,
} from '@chakra-ui/react';
import { useApiService } from '@shared-services/hooks/useApiService';

const IntegrationTestPage: React.FC = () => {
  const { health, loading, testIntegration, refetch } = useApiService();
  const [testResults, setTestResults] = useState<Record<string, any>>({});

  const services = [
    'gmail',
    'slack',
    'asana',
    'github',
    'notion',
    'trello',
    'outlook',
  ];

  const handleTestService = async (service: string) => {
    const result = await testIntegration(service);
    setTestResults(prev => ({
      ...prev,
      [service]: result,
    }));
  };

  const testAllServices = async () => {
    for (const service of services) {
      await handleTestService(service);
    }
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Box>
          <Heading size="lg" mb={4}>
            ATOM Integration Test Dashboard
          </Heading>
          <Text color="gray.600">
            Test connectivity between frontend and backend services
          </Text>
        </Box>

        {/* Backend Health Status */}
        <Box
          p={6}
          borderWidth={1}
          borderRadius="lg"
          bg={health.ok ? 'green.50' : 'red.50'}
          borderColor={health.ok ? 'green.200' : 'red.200'}
        >
          <HStack justify="space-between" align="center">
            <Box>
              <Heading size="md" mb={2}>
                Backend Health Status
              </Heading>
              <HStack>
                <Badge
                  colorScheme={health.ok ? 'green' : 'red'}
                  fontSize="sm"
                >
                  {health.ok ? 'Connected' : 'Disconnected'}
                </Badge>
                {loading && <Spinner size="sm" />}
              </HStack>
              {health.error && (
                <Text color="red.600" fontSize="sm" mt={2}>
                  Error: {health.error.message}
                </Text>
              )}
              {health.data && (
                <Text color="green.600" fontSize="sm" mt={2}>
                  Status: {health.data.status}
                </Text>
              )}
            </Box>
            <Button onClick={refetch} isLoading={loading}>
              Refresh
            </Button>
          </HStack>
        </Box>

        {/* Service Integration Tests */}
        <Box>
          <Heading size="md" mb={4}>
            Service Integration Tests
          </Heading>
          <VStack spacing={3} align="stretch">
            {services.map(service => (
              <Box
                key={service}
                p={4}
                borderWidth={1}
                borderRadius="md"
                bg="white"
              >
                <HStack justify="space-between" align="center">
                  <Box>
                    <Text fontWeight="medium" capitalize>
                      {service}
                    </Text>
                    {testResults[service] && (
                      <Badge
                        colorScheme={testResults[service].ok ? 'green' : 'red'}
                        fontSize="xs"
                        mt={1}
                      >
                        {testResults[service].ok ? 'Pass' : 'Fail'}
                      </Badge>
                    )}
                    {testResults[service]?.error && (
                      <Text color="red.600" fontSize="xs" mt={1}>
                        {testResults[service].error.message}
                      </Text>
                    )}
                  </Box>
                  <Button
                    size="sm"
                    onClick={() => handleTestService(service)}
                    isLoading={!testResults[service]}
                  >
                    Test
                  </Button>
                </HStack>
              </Box>
            ))}
          </VStack>
          
          <Button mt={4} onClick={testAllServices}>
            Test All Services
          </Button>
        </Box>

        {/* Configuration Info */}
        <Box>
          <Heading size="md" mb={4}>
            Configuration
          </Heading>
          <VStack align="start" spacing={2}>
            <Text fontSize="sm">
              <strong>Backend URL:</strong>{' '}
              <Code>
                {process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}
              </Code>
            </Text>
            <Text fontSize="sm">
              <strong>Python API:</strong>{' '}
              <Code>
                {process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058'}
              </Code>
            </Text>
            <Text fontSize="sm">
              <strong>Environment:</strong>{' '}
              <Code>{process.env.NODE_ENV || 'development'}</Code>
            </Text>
          </VStack>
        </Box>
      </VStack>
    </Container>
  );
};

export default IntegrationTestPage;