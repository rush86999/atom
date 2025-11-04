/**
 * Next.js Desktop OAuth Callback Handler Component
 * Enhanced version for Tauri desktop app with native features
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
  Divider,
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ExternalLinkIcon,
  DesktopIcon,
} from '@chakra-ui/icons';

interface NextjsDesktopCallbackProps {
  onSuccess?: (data: any) => void;
  onError?: (error: string) => void;
}

declare global {
  interface Window {
    __TAURI__?: {
      invoke: (command: string, args?: any) => Promise<any>;
      listen: (event: string, callback: (event: any) => void) => Promise<() => void>;
      notification: {
        isPermissionGranted: () => Promise<boolean>;
        requestPermission: () => Promise<boolean>;
        send: (notification: any) => void;
      };
      shell: {
        open: (url: string) => Promise<void>;
      };
      window: {
        close: () => Promise<void>;
        setFocus: () => Promise<void>;
      };
    };
  }
}

export const NextjsDesktopCallback: React.FC<NextjsDesktopCallbackProps> = ({
  onSuccess,
  onError,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [callbackData, setCallbackData] = useState<any>(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isTauri, setIsTauri] = useState(false);

  const bgColor = useColorModeValue('white', 'gray.800');

  useEffect(() => {
    // Check if running in Tauri
    setIsTauri(typeof window !== 'undefined' && window.__TAURI__);
    handleCallback();
  }, []);

  const sendDesktopNotification = async (title: string, body: string) => {
    if (isTauri && window.__TAURI__) {
      try {
        const permissionGranted = await window.__TAURI__.notification.isPermissionGranted();
        if (!permissionGranted) {
          await window.__TAURI__.notification.requestPermission();
        }
        
        await window.__TAURI__.notification.send({
          title,
          body,
          icon: 'nextjs-logo.png',
        });
      } catch (err) {
        console.error('Failed to send desktop notification:', err);
      }
    }
  };

  const closeWindow = async () => {
    if (isTauri && window.__TAURI__?.window) {
      try {
        await window.__TAURI__.window.close();
      } catch (err) {
        console.error('Failed to close window:', err);
        window.close();
      }
    } else {
      window.close();
    }
  };

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
        
        await sendDesktopNotification(
          'Next.js Authentication Failed',
          errorDescription || error
        );
        
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
          platform: 'tauri',
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

        // Send desktop notification
        await sendDesktopNotification(
          'Next.js Connected Successfully',
          `${data.projects?.length || 0} projects ready for synchronization`
        );

        // Auto-close window after delay
        setTimeout(() => {
          closeWindow();
        }, 3000);

      } else {
        setError(data.error || 'Failed to complete Next.js authentication');
        setProcessing(false);
        
        if (onError) {
          onError(data.error || 'Authentication failed');
        }
        
        await sendDesktopNotification(
          'Next.js Authentication Failed',
          data.error || 'Authentication failed'
        );
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      setProcessing(false);
      setProgress(0);
      
      if (onError) {
        onError(errorMessage);
      }
      
      await sendDesktopNotification(
        'Next.js Authentication Error',
        errorMessage
      );
    } finally {
      setLoading(false);
    }
  };

  const retryConnection = () => {
    setError(null);
    setSuccess(false);
    setCallbackData(null);
    handleCallback();
  };

  const openVercelDashboard = async () => {
    if (isTauri && window.__TAURI__?.shell) {
      try {
        await window.__TAURI__.shell.open('https://vercel.com/dashboard');
      } catch (err) {
        console.error('Failed to open URL:', err);
      }
    } else {
      window.open('https://vercel.com/dashboard', '_blank');
    }
  };

  if (loading) {
    return (
      <Box minH="100vh" bg={bgColor} display="flex" alignItems="center" justifyContent="center">
        <Card w="450px">
          <CardBody>
            <VStack spacing={4}>
              <Spinner size="xl" color="blue.500" />
              <Heading size="md">Connecting to Next.js...</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete the authentication process with Vercel
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
              {isTauri && (
                <HStack fontSize="sm" color="green.600">
                  <DesktopIcon />
                  <Text>Desktop App Enhanced</Text>
                </HStack>
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
        <Card w="500px">
          <CardBody>
            <VStack spacing={4}>
              <Icon as={WarningIcon} w={16} h={16} color="red.500" />
              <Heading size="md">Authentication Failed</Heading>
              <Alert status="error">
                <AlertIcon />
                <Text>{error}</Text>
              </Alert>
              
              {isTauri && (
                <Alert status="info">
                  <AlertIcon />
                  <Text fontSize="sm">
                    Desktop notification has been sent with more details
                  </Text>
                </Alert>
              )}
              
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
                  onClick={openVercelDashboard}
                  w="full"
                >
                  Open Vercel Dashboard
                </Button>
                <Button
                  variant="ghost"
                  onClick={closeWindow}
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
        <Card w="500px">
          <CardBody>
            <VStack spacing={4}>
              <Icon as={CheckCircleIcon} w={16} h={16} color="green.500" />
              <Heading size="md">Successfully Connected!</Heading>
              <Text color="gray.600" textAlign="center">
                Your Next.js integration has been set up successfully. 
                You can now manage your Next.js projects and deployments directly from ATOM Desktop.
              </Text>
              
              {isTauri && (
                <Alert status="success">
                  <AlertIcon />
                  <Box>
                    <Text fontWeight="bold">Desktop Features Enabled</Text>
                    <Text fontSize="sm">
                      Desktop notifications and background sync are now active
                    </Text>
                  </Box>
                </Alert>
              )}
              
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

              <Divider />

              <HStack fontSize="sm" color="gray.600">
                <TimeIcon />
                <Text>This window will close automatically in 3 seconds...</Text>
              </HStack>

              <VStack spacing={2} w="full">
                <Button
                  colorScheme="blue"
                  onClick={closeWindow}
                  leftIcon={<CheckCircleIcon />}
                  w="full"
                >
                  Continue to ATOM Desktop
                </Button>
                <Button
                  variant="outline"
                  onClick={openVercelDashboard}
                  leftIcon={<ExternalLinkIcon />}
                  w="full"
                >
                  Open Vercel Dashboard
                </Button>
              </VStack>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  return null;
};

export default NextjsDesktopCallback;