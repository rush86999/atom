/**
 * Next.js Integration Page
 * Dedicated page for Next.js/Vercel integration
 */

import React from "react";
import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  useColorModeValue,
} from "@chakra-ui/react";

const NextjsIntegrationPage: React.FC = () => {
  const bgColor = useColorModeValue("gray.50", "gray.900");
  const textColor = useColorModeValue("gray.800", "gray.100");

  return (
    <Box bg={bgColor} minH="100vh" py={8}>
      <Container maxW="container.xl">
        <VStack spacing={8} align="center" textAlign="center">
          <Heading as="h1" size="2xl" color={textColor}>
            Next.js Integration
          </Heading>
          <Text fontSize="xl" color="gray.600" maxW="2xl">
            Next.js and Vercel integration is coming soon. This page will allow
            you to:
          </Text>

          <Box
            bg="white"
            borderRadius="lg"
            boxShadow="sm"
            p={8}
            borderWidth="1px"
            borderColor="gray.200"
            maxW="2xl"
            w="full"
          >
            <VStack spacing={4} align="start">
              <Text>• Deploy and manage Next.js applications</Text>
              <Text>• Monitor Vercel deployments and performance</Text>
              <Text>• Configure environment variables and domains</Text>
              <Text>• View build logs and analytics</Text>
              <Text>• Integrate with CI/CD pipelines</Text>
            </VStack>
          </Box>

          <Text color="gray.500" fontSize="sm">
            Check back soon for updates on Next.js integration features.
          </Text>
        </VStack>
      </Container>
    </Box>
  );
};

export default NextjsIntegrationPage;
