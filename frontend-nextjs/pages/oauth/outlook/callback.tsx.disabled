import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import {
  Box,
  Container,
  VStack,
  HStack,
  Text,
  Heading,
  Alert,
  AlertIcon,
  Button,
  Progress,
  Spinner,
  useToast
} from '@chakra-ui/react';

const OutlookCallbackPage = () => {
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [tokens, setTokens] = useState<any>(null);
  const [userInfo, setUserInfo] = useState<any>(null);
  const toast = useToast();

  useEffect(() => {
    if (router.isReady) {
      handleOutlookCallback();
    }
  }, [router.isReady]);

  const handleOutlookCallback = async () => {
    try {
      const { code, state, error, error_description } = router.query;

      if (error) {
        setStatus('error');
        setMessage(error_description || error);
        return;
      }

      if (!code) {
        setStatus('error');
        setMessage('No authorization code received');
        return;
      }

      // Exchange code for tokens
      const tokenResponse = await fetch('/api/auth/outlook/callback', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include'
      });

      const tokenData = await tokenResponse.json();

      if (tokenData.success) {
        setStatus('success');
        setTokens(tokenData.tokens);
        setUserInfo(tokenData.user_info);
        setMessage('Outlook integration completed successfully!');

        // Store tokens in localStorage for Tauri to pick up
        if (typeof window !== 'undefined' && window.localStorage) {
          localStorage.setItem('outlook_tokens', JSON.stringify(tokenData.tokens));
          localStorage.setItem('outlook_user_info', JSON.stringify(tokenData.user_info));
        }

        // Notify Tauri if available
        if (window.__TAURI__) {
          try {
            await window.__TAURI__.invoke('outlook_oauth_completed', {
              tokens: tokenData.tokens,
              userInfo: tokenData.user_info
            });
          } catch (error) {
            console.log('Failed to notify Tauri:', error);
          }
        }

        // Show success notification
        toast({
          title: 'Outlook Connected',
          description: `Welcome ${tokenData.user_info?.displayName || 'User'}!`,
          status: 'success',
          duration: 5000
        });

        // Redirect to settings after a short delay
        setTimeout(() => {
          router.push('/settings?service=outlook&status=connected');
        }, 2000);

      } else {
        setStatus('error');
        setMessage(tokenData.error || 'Failed to complete OAuth flow');
      }
    } catch (error) {
      console.error('Outlook callback error:', error);
      setStatus('error');
      setMessage('An error occurred during OAuth callback');
    }
  };

  const renderContent = () => {
    switch (status) {
      case 'loading':
        return (
          <VStack spacing={6}>
            <Spinner size="xl" color="blue.500" thickness="4px" />
            <VStack spacing={2}>
              <Heading size="lg" color="blue.600">
                Connecting to Outlook
              </Heading>
              <Text color="gray.600">
                Please wait while we complete the OAuth process...
              </Text>
            </VStack>
            <Progress size="sm" isIndeterminate w="300px" color="blue.500" />
          </VStack>
        );

      case 'success':
        return (
          <VStack spacing={6}>
            <Box
              p={4}
              bg="green.50"
              rounded="full"
              color="green.500"
            >
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Box>
            <VStack spacing={4} textAlign="center">
              <Heading size="lg" color="green.600">
                Outlook Connected Successfully!
              </Heading>
              <Text color="gray.600">{message}</Text>
              
              {userInfo && (
                <Box
                  p={4}
                  bg="blue.50"
                  rounded="md"
                  border="1px solid"
                  borderColor="blue.200"
                >
                  <VStack spacing={2} align="start">
                    <Text fontWeight="bold" color="blue.800">
                      Connected User:
                    </Text>
                    <Text color="blue.700">
                      {userInfo.displayName}
                    </Text>
                    <Text color="blue.600" fontSize="sm">
                      {userInfo.mail || userInfo.userPrincipalName}
                    </Text>
                    {userInfo.jobTitle && (
                      <Text color="blue.600" fontSize="sm">
                        {userInfo.jobTitle}
                      </Text>
                    )}
                  </VStack>
                </Box>
              )}

              {tokens && (
                <Box
                  p={4}
                  bg="gray.50"
                  rounded="md"
                  border="1px solid"
                  borderColor="gray.200"
                >
                  <VStack spacing={2} align="start">
                    <Text fontWeight="bold" color="gray.800">
                      Connection Details:
                    </Text>
                    <Text color="gray.700" fontSize="sm">
                      Access Token: ✓ Obtained
                    </Text>
                    <Text color="gray.700" fontSize="sm">
                      Scopes: Mail, Calendar, User
                    </Text>
                    <Text color="gray.700" fontSize="sm">
                      Expires In: {tokens.expires_in || 3600} seconds
                    </Text>
                  </VStack>
                </Box>
              )}
            </VStack>
            <Progress size="sm" value={100} color="green.500" w="300px" />
            <Text fontSize="sm" color="gray.500">
              Redirecting to settings...
            </Text>
          </VStack>
        );

      case 'error':
        return (
          <VStack spacing={6}>
            <Alert status="error" rounded="md">
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">OAuth Failed</Text>
                <Text>{message}</Text>
              </Box>
            </Alert>
            <VStack spacing={4}>
              <Heading size="lg" color="red.600">
                Outlook Connection Failed
              </Heading>
              <Text color="gray.600" textAlign="center">
                We encountered an error while connecting to your Outlook account.
                Please try again or contact support if the issue persists.
              </Text>
            </VStack>
            <Button
              colorScheme="blue"
              onClick={() => router.push('/settings')}
              size="lg"
            >
              Return to Settings
            </Button>
          </VStack>
        );

      default:
        return null;
    }
  };

  return (
    <Container maxW="container.md" py={8}>
      <Box
        minH="70vh"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <Box
          w="full"
          maxW="500px"
          p={8}
          bg="white"
          rounded="xl"
          shadow="lg"
          border="1px solid"
          borderColor="gray.200"
        >
          <VStack spacing={6}>
            {/* Header */}
            <HStack justify="center">
              <Text fontSize="2xl">📧</Text>
              <Heading size="lg" color="blue.600">
                Microsoft Outlook
              </Heading>
            </HStack>

            {/* Content */}
            {renderContent()}

            {/* Footer */}
            <Box pt={4} borderTop="1px solid" borderColor="gray.200">
              <Text fontSize="sm" color="gray.500" textAlign="center">
                ATOM • Secure OAuth Integration
              </Text>
            </Box>
          </VStack>
        </Box>
      </Box>
    </Container>
  );
};

export default OutlookCallbackPage;