/**
 * Notion OAuth Callback Page
 * Handles OAuth 2.0 callback for Notion integration
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
interface NotionCallbackData {
  success: boolean;
  message?: string;
  workspace_info?: {
    id: string;
    name: string;
    icon?: string;
    owner?: {
      user: {
        name: string;
        email: string;
      };
    };
  };
  token_info?: {
    access_token: string;
    bot_id: string;
    workspace_name: string;
    workspace_icon?: string;
  };
}

const NotionCallback: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<NotionCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Parse URL parameters
  const { code, state, error: oauthError, error_description } = router.query;

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
        if (!code) {
          setError('Authorization code not found in callback URL');
          setLoading(false);
          return;
        }

        if (!state) {
          setError('State parameter not found in callback URL');
          setLoading(false);
          return;
        }

        // Exchange code for tokens and get workspace info
        const response = await fetch('/api/auth/notion/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code as string,
            state: state as string,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data: NotionCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);

          // Show success toast
          toast({
            title: 'Notion Connected Successfully',
            description: `Connected to ${data.workspace_info?.name || data.token_info?.workspace_name || 'Notion workspace'}`,
            status: 'success',
            duration: 5000,
            isClosable: true,
          });

          // Redirect to settings or dashboard after delay
          setTimeout(() => {
            router.push('/settings?service=notion&status=connected');
          }, 3000);
        } else {
          throw new Error(data.message || 'Failed to connect to Notion');
        }

      } catch (err) {
        console.error('Notion OAuth callback error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);

        toast({
          title: 'Notion Connection Failed',
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
    if (router.isReady && (code || oauthError)) {
      handleCallback();
    }
  }, [router.isReady, code, state, oauthError, error_description, toast, router]);

  const handleRetry = () => {
    setError(null);
    setCallbackData(null);
    setLoading(true);
    router.push('/settings?service=notion');
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
                  Connecting to Notion...
                </Heading>
                <Text color="gray.600">
                  Processing OAuth callback and connecting your workspace
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
    const workspaceName = callbackData.workspace_info?.name || callbackData.token_info?.workspace_name;
    const workspaceIcon = callbackData.workspace_info?.icon || callbackData.token_info?.workspace_icon;
    const ownerName = callbackData.workspace_info?.owner?.user?.name;

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
                  {workspaceName || 'Notion Workspace'}
                </Heading>
                {ownerName && (
                  <Text color="gray.600" fontSize="lg">
                    Owned by {ownerName}
                  </Text>
                )}
              </Box>

              <Alert status="success" borderRadius="md">
                <AlertIcon />
                <Box>
                  <AlertTitle>Notion Integration Active</AlertTitle>
                  <AlertDescription>
                    Your Notion workspace is now connected to ATOM. You can now sync pages,
                    databases, and collaborate seamlessly.
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

export default NotionCallback;
