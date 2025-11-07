import React from 'react';
import { Box, VStack, Heading, Text } from '@chakra-ui/react';
import StripeIntegration from '../../../src/ui-shared/integrations/stripe/components/StripeIntegration';

const StripeIntegrationPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="white" p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        <VStack align="start" spacing={2}>
          <Heading size="2xl">Stripe Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete payment processing and financial management platform
          </Text>
        </VStack>

        <StripeIntegration />
      </VStack>
    </Box>
  );
};

export default StripeIntegrationPage;
