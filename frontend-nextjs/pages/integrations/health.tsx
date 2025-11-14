import React from "react";
import { Box, VStack, Heading, Text, Breadcrumb, BreadcrumbItem, BreadcrumbLink } from "@chakra-ui/react";
import { ChevronRightIcon } from "@chakra-ui/icons";
import IntegrationHealthDashboard from "../../components/integrations/IntegrationHealthDashboard";

const IntegrationHealthPage: React.FC = () => {
  return (
    <Box maxW="1200px" mx="auto" p={6}>
      {/* Breadcrumb Navigation */}
      <Breadcrumb spacing="8px" separator={<ChevronRightIcon color="gray.500" />} mb={6}>
        <BreadcrumbItem>
          <BreadcrumbLink href="/">Home</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem>
          <BreadcrumbLink href="/integrations">Integrations</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <BreadcrumbLink href="/integrations/health">Health Status</BreadcrumbLink>
        </BreadcrumbItem>
      </Breadcrumb>

      {/* Page Header */}
      <VStack spacing={4} align="start" mb={8}>
        <Heading size="xl">Integration Health Dashboard</Heading>
        <Text color="gray.600" fontSize="lg">
          Monitor the health and status of all your connected integrations in real-time.
          This dashboard provides comprehensive visibility into integration performance,
          connection status, and potential issues.
        </Text>
      </VStack>

      {/* Health Dashboard Component */}
      <IntegrationHealthDashboard
        autoRefresh={true}
        refreshInterval={30000}
        showDetails={true}
      />

      {/* Additional Information */}
      <Box mt={8} p={6} bg="blue.50" borderRadius="lg" border="1px" borderColor="blue.200">
        <Heading size="md" mb={3} color="blue.800">About This Dashboard</Heading>
        <VStack spacing={3} align="start" color="blue.700">
          <Text>
            • <strong>Auto-refresh:</strong> Health status automatically updates every 30 seconds
          </Text>
          <Text>
            • <strong>Status Indicators:</strong> Green = Healthy, Yellow = Warning, Red = Error
          </Text>
          <Text>
            • <strong>Response Time:</strong> Measures API response time for each integration
          </Text>
          <Text>
            • <strong>Last Sync:</strong> Shows when each integration was last checked
          </Text>
          <Text>
            • <strong>Connection Status:</strong> Indicates if the integration is actively connected
          </Text>
        </VStack>
      </Box>
    </Box>
  );
};

export default IntegrationHealthPage;
