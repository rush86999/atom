import React from 'react';
import { Box, Heading, Text, Button } from "@chakra-ui/react";

const GitlabEnhanced = () => {
  return (
    <Box p=6>
      <Heading size="lg">Gitlab Enhanced Integration</Heading>
      <Text>Enterprise integration for gitlab services</Text>
      <Button colorScheme="purple" mt=4>
        Connect Gitlab
      </Button>
    </Box>
  );
};

export default GitlabEnhanced;
