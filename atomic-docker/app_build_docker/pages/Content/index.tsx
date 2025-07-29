import React from "react";
import { Textarea, Button, Box, Heading, Text } from "@chakra-ui/react";

const Content = () => {
  return (
    <Box>
      <Heading>Content</Heading>
      <Text>This is the content page.</Text>
      <Textarea placeholder="Enter a topic to generate content" mt={4} />
      <Button mt={4}>Generate</Button>
    </Box>
  );
};

export default Content;
