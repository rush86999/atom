import React from 'react';
import { Box, Heading, Text, Button } from "@chakra-ui/react";

const HubspotEnhanced = () => {
  return (
    <Box p={6}>
      <Heading size="lg">Hubspot Enhanced Integration</Heading>
      <Text>Enterprise integration for hubspot services</Text>
      <Button colorScheme="purple" mt={4}>
        Connect Hubspot
      </Button>
    </Box>
  );
};

export default HubspotEnhanced;
