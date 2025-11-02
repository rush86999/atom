/**
 * GitHub OAuth Callback Page
 * Handles OAuth 2.0 callback for GitHub integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Stack,
  Badge,
  Alert,
  AlertIcon,
  Spinner,
  useToast,
  Icon,
  Container,
  Card,
  CardBody,
  useColorModeValue,
  Divider,
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  GitHubLogoIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface GitHubCallbackProps {
  // Component props
}

interface GitHubCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    login: string;
    name: string;
    email: string;
    avatar_url: string;
  };
  token_info?: {
    access_token: string;
    token_type: string;
    scope: string;
    expires_in: number;
  };
  error?: string;
}

const GitHubCallback: React.FC<GitHubCallbackProps> = () => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<GitHubCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Parse URL parameters
  useEffect(() => {
    const handleCallback = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const error = urlParams.get('error');
        const errorDescription = urlParams.get('error_description');

        if (error) {
          setError(errorDescription || error);
          setLoading(false);
          return;
        }

        if (!code) {
          setError('No authorization code received');
          setLoading(false);
          return;
        }

        // Exchange code for token
        setLoading(true);
        const response = await fetch('/api/auth/github/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            state: state,
          }),
        });

        const data: GitHubCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          toast({
            title: 'GitHub Connected Successfully!',
            description: `Welcome, ${data.user_info?.name || data.user_info?.login}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'GitHub Authentication Failed',
            description: data.error || data.message || 'Unknown error',
            status: 'error',
            duration: 5000,
          });
        }

        setLoading(false);
      } catch (err) {
        const error = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(error);
        setLoading(false);
        
        toast({
          title: 'Callback Error',
          description: error,
          status: 'error',
          duration: 5000,
        });
      }
    };

    handleCallback();
  }, []);

  // Auto-close popup window
  useEffect(() => {
    if (window.opener && !loading) {
      setTimeout(() => {
        window.close();
      }, 2000);
    }
  }, [loading]);

  // Redirect to main app
  const redirectToApp = () => {
    if (window.opener) {
      window.opener.postMessage({
        type: 'github_oauth_success',
        data: callbackData
      }, '*');
      window.close();
    } else {
      router.push('/integrations/github');
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="blue.500" />
              <Heading size="lg">Processing GitHub Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your GitHub connection...
              </Text>
            </VStack>
          </CardBody>
        </Card>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <Box textAlign="center">
                  <Heading size="md" mb={2}>Authentication Failed</Heading>
                  <Text>{error}</Text>
                </Box>
              </Alert>
              
              <VStack spacing={3}>
                <Text color="gray.600" textAlign="center">
                  There was a problem connecting your GitHub account. Please try again.
                </Text>
                
                <Button
                  colorScheme="red"
                  leftIcon={<GitHubLogoIcon />}
                  onClick={() => window.close()}
                >
                  Close Window
                </Button>
                
                <Button
                  variant="outline"
                  onClick={() => window.location.reload()}
                >
                  Try Again
                </Button>
              </VStack>
            </VStack>
          </CardBody>
        </Card>
      </Container>
    );
  }

  return (
    <Container maxW="md" py={10}>
      <Card>
        <CardBody>
          <VStack spacing={6} align="center" py={10}>
            <Icon as={CheckCircleIcon} w={20} h={20} color="green.500" />
            
            <VStack spacing={2}>
              <Heading size="lg" color="green.500">
                GitHub Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.user_info?.name || callbackData?.user_info?.login}!
              </Text>
            </VStack>

            {callbackData?.user_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Box
                      as="img"
                      src={callbackData.user_info.avatar_url}
                      alt={callbackData.user_info.name}
                      w={16}
                      h={16}
                      borderRadius="full"
                      border="2px solid"
                      borderColor="gray.200"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.user_info.name}
                      </Text>
                      <Text color="gray.600">
                        @{callbackData.user_info.login}
                      </Text>
                      {callbackData.user_info.email && (
                        <Text color="gray.500" fontSize="sm">
                          {callbackData.user_info.email}
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}

            <Divider />

            {/* Token Information */}
            {callbackData?.token_info && (
              <VStack spacing={3} w="full" align="start">
                <Heading size="sm">Connection Details</Heading>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Access Token:</Text>
                  <Badge colorScheme="green">
                    {callbackData.token_info.token_type}
                  </Badge>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Scope:</Text>
                  <Text fontSize="sm" color="gray.600">
                    {callbackData.token_info.scope.split(',').join(', ')}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Expires:</Text>
                  <Text fontSize="sm" color="gray.600">
                    {callbackData.token_info.expires_in} seconds
                  </Text>
                </HStack>
              </VStack>
            )}

            <Divider />

            {/* Success Actions */}
            <VStack spacing={4} w="full">
              <Heading size="sm">What's Next?</Heading>
              
              <Text color="gray.600" textAlign="center">
                Your GitHub account is now connected! You can:
              </Text>
              
              <Stack spacing={3} w="full">
                <Button
                  colorScheme="blue"
                  onClick={redirectToApp}
                  w="full"
                >
                  Continue to ATOM
                </Button>
                
                <Button
                  variant="outline"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() => {
                    window.open('https://github.com/settings/applications', '_blank');
                  }}
                  w="full"
                >
                  Manage GitHub Apps
                </Button>
              </Stack>
            </VStack>

            {/* Auto-close message */}
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <Box>
                <Text fontWeight="bold" mb={1}>Window will close automatically</Text>
                <Text fontSize="sm" color="gray.600">
                  This popup window will close in 2 seconds and return you to the main application.
                </Text>
              </Box>
            </Alert>
          </VStack>
        </CardBody>
      </Card>
    </Container>
  );
};

export default GitHubCallback;