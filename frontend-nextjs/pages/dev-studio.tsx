import React from 'react';
import { Box, Heading, Text, VStack, Icon } from '@chakra-ui/react';
import { SettingsIcon } from '@chakra-ui/icons';

const DevStudio = () => {
    return (
        <Box p={8}>
            <VStack spacing={6} align="center" justify="center" minH="60vh">
                <Icon as={SettingsIcon} w={20} h={20} color="purple.500" />
                <Heading>Developer Studio</Heading>
                <Text fontSize="xl" color="gray.600">
                    Tools for extending and customizing the Atom platform are coming soon.
                </Text>
            </VStack>
        </Box>
    );
};

export default DevStudio;
