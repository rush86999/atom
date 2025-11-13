import React from "react";
import { Box, Heading, Text, Button } from "@chakra-ui/react";

const BoxEnhanced = () => {
  return (
    <Box p={6}>
      <Heading size="lg">Box Enhanced Integration</Heading>
      <Text>Enterprise integration for box services</Text>
      <Button colorScheme="purple" mt={4}>
        Connect Box
      </Button>
    </Box>
  );
};

export default BoxEnhanced;
