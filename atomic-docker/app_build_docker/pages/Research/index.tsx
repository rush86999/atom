import React from "react";
import { Input, Button, Box, Heading, Text } from "@chakra-ui/react";

const Research = () => {
  return (
    <Box>
      <Heading>Research</Heading>
      <Text>This is the research page.</Text>
      <Input placeholder="Enter your research query" />
      <Button mt={4}>Search</Button>
      <Box mt={4}>
        <Heading size="md">Results</Heading>
        <Text>Search results will appear here.</Text>
      </Box>
    </Box>
  );
};

export default Research;
