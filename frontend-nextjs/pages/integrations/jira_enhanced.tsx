import React from 'react';
import { Box, Heading, Text, Button } from "@chakra-ui/react";

const JiraEnhanced = () => {
  return (
    <Box p={6}>
      <Heading size="lg">Jira Enhanced Integration</Heading>
      <Text>Enterprise integration for jira services</Text>
      <Button colorScheme="purple" mt={4}>
        Connect Jira
      </Button>
    </Box>
  );
};

export default JiraEnhanced;
