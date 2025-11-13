import React from "react";
import {
  Box,
  Container,
  Heading,
  Text,
  useColorModeValue,
} from "@chakra-ui/react";

/**
 * Airtable Integration Page
 * Next.js page component for Airtable data management integration
 */
const AirtableIntegrationPage: React.FC = () => {
  const bgColor = useColorModeValue("gray.50", "gray.900");
  const textColor = useColorModeValue("gray.800", "gray.100");

  return (
    <Box bg={bgColor} minH="100vh" py={8}>
      <Container maxW="container.xl">
        <Box textAlign="center" mb={8}>
          <Heading as="h1" size="2xl" color={textColor} mb={4}>
            Airtable Integration
          </Heading>
          <Text fontSize="xl" color="gray.600">
            Connect and manage your Airtable bases
          </Text>
        </Box>

        <Box
          bg="white"
          borderRadius="lg"
          boxShadow="sm"
          p={8}
          borderWidth="1px"
          borderColor="gray.200"
        >
          <Heading size="lg" mb={4}>
            Airtable Data Management
          </Heading>
          <Text mb={6}>
            Airtable integration is coming soon. This page will allow you to:
          </Text>
          <Box as="ul" pl={4}>
            <Text as="li" mb={2}>
              • Connect to your Airtable bases
            </Text>
            <Text as="li" mb={2}>
              • View and manage tables and records
            </Text>
            <Text as="li" mb={2}>
              • Sync data between Airtable and other services
            </Text>
            <Text as="li" mb={2}>
              • Create automated workflows with Airtable data
            </Text>
          </Box>
        </Box>
      </Container>
    </Box>
  );
};

export default AirtableIntegrationPage;
