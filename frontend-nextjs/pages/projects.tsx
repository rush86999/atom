import React from 'react';
import { Box, Heading, Text, VStack, Icon } from '@chakra-ui/react';
import { ViewIcon } from '@chakra-ui/icons';

const Projects = () => {
    return (
        <Box p={8}>
            <VStack spacing={6} align="center" justify="center" minH="60vh">
                <Icon as={ViewIcon} w={20} h={20} color="teal.500" />
                <Heading>Project Management</Heading>
                <Text fontSize="xl" color="gray.600">
                    Unified project tracking and task management features are coming soon.
                </Text>
            </VStack>
        </Box>
    );
};

export default Projects;
