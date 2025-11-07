import React from "react";
import { Box, VStack, Heading, Text } from "@chakra-ui/react";
import GitHubIntegration from "../../../src/ui-shared/integrations/github/components/GitHubIntegration";

const GitHubIntegrationPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="white" p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        <VStack align="start" spacing={2}>
          <Heading size="2xl">GitHub Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete repository and project management platform
          </Text>
        </VStack>

        <GitHubIntegration />
      </VStack>
    </Box>
  );
};

export default GitHubIntegrationPage;
