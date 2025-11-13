import React from 'react';
import { Box, Heading, Text, Button } from "@chakra-ui/react";

const XeroEnhanced = () => {
  return (
    <Box p={6}>
      <Heading size="lg">Xero Enhanced Integration</Heading>
      <Text>Enterprise integration for xero services</Text>
      <Button colorScheme="purple" mt={4}>
        Connect Xero
      </Button>
    </Box>
  );
};

export default XeroEnhanced;
