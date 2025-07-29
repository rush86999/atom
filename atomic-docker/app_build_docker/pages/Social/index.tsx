import React from "react";
import { Textarea, Button, Box, Heading, Text, Select } from "@chakra-ui/react";

const Social = () => {
  return (
    <Box>
      <Heading>Social</Heading>
      <Text>This is the social page.</Text>
      <Select placeholder="Select account">
        <option value="twitter">Twitter</option>
        <option value="linkedin">LinkedIn</option>
      </Select>
      <Textarea placeholder="What's on your mind?" mt={4} />
      <Button mt={4}>Post</Button>
    </Box>
  );
};

export default Social;
