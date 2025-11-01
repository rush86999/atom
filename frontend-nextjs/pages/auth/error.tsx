import React from "react";
import { useRouter } from "next/router";
import {
  Box,
  Container,
  VStack,
  Heading,
  Text,
  Button,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from "@chakra-ui/react";

export default function AuthError() {
  const router = useRouter();
  const { error } = router.query;

  const getErrorMessage = (errorType: string) => {
    switch (errorType) {
      case "Configuration":
        return "There is a problem with the server configuration. Please contact support.";
      case "AccessDenied":
        return "Access denied. You do not have permission to sign in.";
      case "Verification":
        return "The verification link has expired or has already been used.";
      case "Default":
      default:
        return "An unexpected error occurred during authentication. Please try again.";
    }
  };

  const errorMessage = getErrorMessage(error as string);

  return (
    <Container maxW="md" py={12}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading size="xl" mb={2}>
            Authentication Error
          </Heading>
          <Text color="gray.600">There was a problem signing you in</Text>
        </Box>

        <Box w="100%">
          <Alert status="error" borderRadius="lg">
            <AlertIcon />
            <Box>
              <AlertTitle>Authentication Failed</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Box>
          </Alert>
        </Box>

        <VStack spacing={4} w="100%">
          <Button
            colorScheme="blue"
            size="lg"
            w="100%"
            onClick={() => router.push("/auth/signin")}
          >
            Try Again
          </Button>

          <Button
            variant="outline"
            size="lg"
            w="100%"
            onClick={() => router.push("/")}
          >
            Return Home
          </Button>
        </VStack>

        <Box textAlign="center">
          <Text fontSize="sm" color="gray.600">
            If this problem persists, please contact support.
          </Text>
        </Box>
      </VStack>
    </Container>
  );
}
