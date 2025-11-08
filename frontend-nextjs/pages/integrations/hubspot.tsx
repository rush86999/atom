import React from "react";
import { Box, VStack, Heading, Text } from "@chakra-ui/react";
import HubSpotIntegration from "../../../components/integrations/hubspot/HubSpotIntegration";

const HubSpotIntegrationPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="white" p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        <VStack align="start" spacing={2}>
          <Heading size="2xl">HubSpot Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete CRM and marketing automation platform with advanced search
            capabilities
          </Text>
        </VStack>

        <HubSpotIntegration />
      </VStack>
    </Box>
  );
};

export default HubSpotIntegrationPage;
