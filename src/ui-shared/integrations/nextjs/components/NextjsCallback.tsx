/**
 * Next.js OAuth Callback Handler Component
 * Handles OAuth callback from Next.js/Vercel
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Alert,
  AlertIcon,
  Spinner,
  Icon,
  useColorModeValue,
  Card,
  CardBody,
  Progress,
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ExternalLinkIcon,
} from '@chakra-ui/icons';
import { detectPlatform } from '@shared/ui-shared/integrations/_template/baseIntegration';

interface NextjsCallbackProps {
  onSuccess?: (data: any) => void;
  onError?: (error: string) => void;
}

export const NextjsCallback: React.FC<NextjsCallbackProps> = ({
  onSuccess,
  onError,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [callbackData, setCallbackData] = useState<any>(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);

  const bgColor = useColorModeValue('white', 'gray.800');
  const platform = detectPlatform();

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = async () => {
    try {
      setLoading(true);
      setProgress(10);

      // Parse URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');
      const error = urlParams.get('error');
      const errorDescription = urlParams.get('error_description');

      setProgress(30);

      if (error) {
        setError(errorDescription || error);
        setProcessing(false);
        if (onError) {
          onError(errorDescription || error);
        }
        return;
      }

      if (!code) {
        setError('Authorization code not found');
        setProcessing(false);
        return;
      }

      setProgress(50);
      setProcessing(true);

      // Exchange code for access token
      const response = await fetch('/api/auth/nextjs/callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          code,
          state,
          platform,
        }),
      });

      setProgress(70);

      const data = await response.json();

      if (data.ok) {
        setCallbackData(data);
        setSuccess(true);
        setProgress(100);
        
        if (onSuccess) {
          onSuccess(data);
        }

        // Auto-close popup window and redirect to main app
        setTimeout(() => {
          redirectToApp();
        }, 2000);

      } else {
        setError(data.error || 'Failed to complete Next.js authentication');
        setProcessing(false);
        
        if (onError) {
          onError(data.error || 'Authentication failed');
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      setProcessing(false);
      setProgress(0);
      
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const redirectToApp = () => {
    if (window.opener) {
      // Send success message to parent window
      window.opener.postMessage({
        type: 'nextjs_oauth_success',
        data: callbackData
      }, '*');
      window.close();
    } else {
      // Redirect to main app if not in popup
      window.location.href = '/settings?nextjs=connected';
    }
  };

  const retryConnection = () => {
    setError(null);
    setSuccess(false);
    setCallbackData(null);
    handleCallback();
  };

  if (loading) {
    return (
      <Box minH="100vh" bg={bgColor} display="flex" alignItems="center" justifyContent="center">
        <Card w="400px">
          <CardBody>
            <VStack spacing={4}>
              <Spinner size="xl" color="blue.500" />
              <Heading size="md">Connecting to Next.js...</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete the authentication process
              </Text>
              <Progress
                value={progress}
                size="sm"
                colorScheme="blue"
                w="full"
                hasStripe
                isAnimated
              />
              {processing && (
                <Text fontSize="sm" color="blue.600">
                  {progress < 50 ? 'Verifying authorization...' :
                   progress < 70 ? 'Exchanging code for token...' :
                   progress < 90 ? 'Setting up integration...' :
                   'Almost done...'}
                </Text>
              )}
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  if (error) {
    return (
      <Box minH="100vh" bg={bgColor} display="flex" alignItems="center" justifyContent="center">
        <Card w="450px">
          <CardBody>
            <VStack spacing={4}>
              <Icon as={WarningIcon} w={16} h={16} color="red.500" />
              <Heading size="md">Authentication Failed</Heading>
              <Alert status="error">
                <AlertIcon />
                <Text>{error}</Text>
              </Alert>
              <VStack spacing={2} w="full">
                <Button
                  colorScheme="blue"
                  onClick={retryConnection}
                  w="full"
                >
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={() => window.close()}
                  w="full"
                >
                  Close Window
                </Button>
              </VStack>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  if (success) {
    return (
      <Box minH="100vh" bg={bgColor} display="flex" alignItems="center" justifyContent="center">
        <Card w="450px">
          <CardBody>
            <VStack spacing={4}>
              <Icon as={CheckCircleIcon} w={16} h={16} color="green.500" />
              <Heading size="md">Successfully Connected!</Heading>
              <Text color="gray.600" textAlign="center">
                Your Next.js integration has been set up successfully. 
                You can now manage your Next.js projects and deployments directly from ATOM.
              </Text>
              
              {callbackData?.projects && (
                <Alert status="success">
                  <AlertIcon />
                  <Box>
                    <Text fontWeight="bold">Projects Found</Text>
                    <Text fontSize="sm">
                      {callbackData.projects.length} Next.js projects are ready for synchronization
                    </Text>
                  </Box>
                </Alert>
              )}

              <HStack spacing={2} w="full">
                <Button
                  colorScheme="blue"
                  onClick={redirectToApp}
                  leftIcon={<ExternalLinkIcon />}
                  w="full"
                >
                  Continue to ATOM
                </Button>
                <Button
                  variant="outline"
                  onClick={() => window.open('https://vercel.com/dashboard', '_blank')}
                  w="full"
                >
                  Open Vercel
                </Button>
              </HStack>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  return null;
};

export default NextjsCallback;