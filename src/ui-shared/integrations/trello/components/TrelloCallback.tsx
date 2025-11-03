/**
 * Trello OAuth Callback Page
 * Handles OAuth 2.0 callback for Trello integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardBody,
  VStack,
  Heading,
  Text,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Button,
  useToast,
  useColorModeValue,
  HStack,
  Badge,
  Icon,
} from '@chakra-ui/react';
import { CheckCircleIcon, WarningIcon, ExternalLinkIcon } from '@chakra-ui/icons';
import { useRouter } from 'next/router';

// Types
interface TrelloCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    id: string;
    username: string;
    fullName: string;
    avatarUrl?: string;
    email?: string;
  };
  token_info?: {
    access_token: string;
    token_type: string;
    expires_in?: number;
    scope: string;
  };
}

const TrelloCallback: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<TrelloCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Parse URL parameters
  const { token, error: oauthError, error_description } = router.query;

  useEffect(() => {
    const handleCallback = async () => {
      try {
        setLoading(true);

        // Check for OAuth errors
        if (oauthError) {
          setError(`OAuth Error: ${oauthError} - ${error_description || 'Unknown error'}`);
          setLoading(false);
          return;
        }

        // Check for required parameters
        if (!token) {
          setError('Access token not found in callback URL');
          setLoading(false);
          return;
        }

        // Process the token (Trello returns token directly in URL fragment)
        const response = await fetch('/api/trello/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token: token as string,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data: TrelloCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);

          // Show success toast
          toast({
            title: 'Trello Connected Successfully',
            description: `Connected as ${data.user_info?.fullName || data.user_info?.username || 'Trello user'}`,
            status: 'success',
            duration: 5000,
            isClosable: true,
          });

          // Redirect to settings or dashboard after delay
          setTimeout(() => {
            router.push('/settings?service=trello&status=connected');
          }, 3000);
        } else {
          throw new Error(data.message || 'Failed to connect to Trello');
        }

      } catch (err) {
        console.error('Trello OAuth callback error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);

        toast({
          title: 'Trello Connection Failed',
          description: errorMessage,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        setLoading(false);
      }
    };

    // Only process if we have query parameters
    if (router.isReady && (token || oauthError)) {
      handleCallback();
    }
  }, [router.isReady, token, oauthError, error_description, toast, router]);

  const handleRetry = () => {
    setError(null);
    setCallbackData(null);
    setLoading(true);
    router.push('/settings?service=trello');
  };

  const handleGoToSettings = () => {
    router.push('/settings');
  };

  if (loading) {
    return (
      <Box minH="50vh" display="flex" alignItems="center" justifyContent="center">
        <Card bg={bgColor} border="1px" borderColor={borderColor} maxW="md" w="full">
          <CardBody>
            <VStack spacing={6} textAlign="center">
              <Spinner size="xl" color="blue.500" thickness="4px" />
              <Box>
                <Heading size="md" mb={2}>
                  Connecting to Trello...
                </Heading>
                <Text color="gray.600">
                  Processing OAuth callback and connecting your account
                </Text>
              </Box>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  if (error) {
    return (
      <Box minH="50vh" display="flex" alignItems="center" justifyContent="center">
        <Card bg={bgColor} border="1px" borderColor={borderColor} maxW="md" w="full">
          <CardBody>
            <VStack spacing={6}>
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <Box>
                  <AlertTitle>Connection Failed</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Box>
              </Alert>

              <HStack spacing={4} w="full">
                <Button
                  colorScheme="blue"
                  onClick={handleRetry}
                  leftIcon={<ExternalLinkIcon />}
                  flex={1}
                >
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={handleGoToSettings}
                  flex={1}
                >
                  Go to Settings
                </Button>
              </HStack>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  if (callbackData?.success) {
    const userName = callbackData.user_info?.fullName || callbackData.user_info?.username;
    const userAvatar = callbackData.user_info?.avatarUrl;

    return (
      <Box minH="50vh" display="flex" alignItems="center" justifyContent="center">
        <Card bg={bgColor} border="1px" borderColor={borderColor} maxW="md" w="full">
          <CardBody>
            <VStack spacing={6} textAlign="center">
              <Badge
                colorScheme="green"
                display="flex"
                alignItems="center"
                px={3}
                py={1}
                borderRadius="full"
              >
                <Icon as={CheckCircleIcon} mr={2} />
                Successfully Connected
              </Badge>

              <Box>
                <Heading size="lg" mb={2}>
                  {userName || 'Trello Account'}
                </Heading>
                {callbackData.user_info?.username && (
                  <Text color="gray.600" fontSize="lg">
                    @{callbackData.user_info.username}
                  </Text>
                )}
              </Box>

              <Alert status="success" borderRadius="md">
                <AlertIcon />
                <Box>
                  <AlertTitle>Trello Integration Active</AlertTitle>
                  <AlertDescription>
                    Your Trello account is now connected to ATOM. You can now sync boards,
                    cards, and manage your projects seamlessly.
                  </AlertDescription>
                </Box>
              </Alert>

              <Text fontSize="sm" color="gray.500">
                Redirecting to settings in a few seconds...
              </Text>

              <Button
                colorScheme="blue"
                onClick={handleGoToSettings}
                w="full"
              >
                Go to Settings Now
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  return (
    <Box minH="50vh" display="flex" alignItems="center" justifyContent="center">
      <Card bg={bgColor} border="1px" borderColor={borderColor} maxW="md" w="full">
        <CardBody>
          <VStack spacing={6} textAlign="center">
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <Box>
                <AlertTitle>Processing Complete</AlertTitle>
                <AlertDescription>
                  The OAuth callback has been processed. Check your settings for connection status.
                </AlertDescription>
              </Box>
            </Alert>

            <Button
              colorScheme="blue"
              onClick={handleGoToSettings}
              w="full"
            >
              Go to Settings
            </Button>
          </VStack>
        </CardBody>
      </Card>
    </Box>
  );
};

export default TrelloCallback;
