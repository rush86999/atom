import React from 'react';
import { Box, Container, Heading, Text, useColorModeValue } from '@chakra-ui/react';
import { AirtableDataManagementUI } from '@atom-integrations/ui-shared';

/**
 * Airtable Integration Page
 * Next.js page component for Airtable data management integration
 */
const AirtableIntegrationPage: React.FC = () => {
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const textColor = useColorModeValue('gray.800', 'gray.100');

  return (
    <Box bg={bgColor} minH="100vh" py={8}>
      <Container maxW="container.xl">
        <Box textAlign="center" mb={8}>
          <Heading
            as="h1"
            size="2xl"
            color={textColor}
            mb={4}
          >
            Airtable Integration
          </Heading>
          <Text
            fontSize="lg"
            color={textColor}
            maxW="3xl"
            mx="auto"
          >
            Complete data management and workflow automation platform
          </Text>
        </Box>

        {/* Airtable Data Management UI */}
        <AirtableDataManagementUI />
      </Container>
    </Box>
  );
};

export default AirtableIntegrationPage;