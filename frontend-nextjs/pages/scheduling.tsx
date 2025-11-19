import React from 'react';
import { Box, Heading, Text, VStack, Icon } from '@chakra-ui/react';
import { TimeIcon } from '@chakra-ui/icons';

const Scheduling = () => {
  return (
    <Box p={8}>
      <VStack spacing={6} align="center" justify="center" minH="60vh">
        <Icon as={TimeIcon} w={20} h={20} color="blue.500" />
        <Heading>Scheduling</Heading>
        <Text fontSize="xl" color="gray.600">
          Advanced scheduling and calendar management features are coming soon.
        </Text>
      </VStack>
    </Box>
  );
};

export default Scheduling;
