import React from "react";
import { Input, Button, Box, Heading, Text } from "@chakra-ui/react";

const Shopping = () => {
  return (
    <Box>
      <Heading>Shopping</Heading>
      <Text>This is the shopping page.</Text>
      <Input placeholder="Search for products" />
      <Button mt={4}>Search</Button>
      <Box mt={4}>
        <Heading size="md">Results</Heading>
        <Text>Product results will appear here.</Text>
      </Box>
    </Box>
  );
};

export default Shopping;
