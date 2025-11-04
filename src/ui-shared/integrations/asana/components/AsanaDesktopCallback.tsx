/**
 * Asana Desktop OAuth Callback Page
 * Handles OAuth 2.0 callback for desktop app following GitLab pattern
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
  Code,
  useClipboard,
  Avatar,
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  ViewListIcon,
  InfoIcon,
  CopyIcon,
  DesktopIcon,
  CalendarIcon,
  ProjectIcon,
  TaskIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface AsanaDesktopCallbackProps {
  isDesktop?: boolean;
}

interface AsanaCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    gid: string;
    name: string;
    email: string;
    avatar_url_128x128: string;
    workspaces: Array<{
      gid: string;
      name: string;
    }>;
  };
  token_info?: {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
    token_type: string;
    scope: string;
    state?: string;
    created_at: string;
    expires_at: string;
  };
  error?: string;
}

const AsanaDesktopCallback: React.FC<AsanaDesktopCallbackProps> = ({
  isDesktop = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<AsanaCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(callbackData?.token_info?.access_token || '');

  // Parse URL parameters for Asana OAuth 2.0
  useEffect(() => {
    const handleCallback = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const errorParam = urlParams.get('error');
        const errorDescription = urlParams.get('error_description');

        if (errorParam) {
          setError(`${errorParam}: ${errorDescription || 'Unknown error'}`);
          setLoading(false);
          return;
        }

        if (!code || !state) {
          setError('OAuth code and state are required');
          setLoading(false);
          return;
        }

        // Exchange code for access token
        setLoading(true);
        const response = await fetch('/api/auth/asana/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            state: state,
            grant_type: 'authorization_code',
          }),
        });

        const data: AsanaCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          
          // Handle desktop app callback
          if (isDesktop) {
            try {
              // Send data to desktop app via custom protocol
              const callbackUrl = `atom://auth/asana/success?${new URLSearchParams({
                success: 'true',
                tokens: btoa(JSON.stringify(data.token_info))
              })}`;
              
              window.location.href = callbackUrl;
            } catch (err) {
              console.error('Desktop callback error:', err);
              // Fallback to web behavior
            }
          }
          
          toast({
            title: 'Asana Connected Successfully!',
            description: `Welcome, ${data.user_info?.name}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'Asana Authentication Failed',
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
  }, [isDesktop, toast]);

  // Auto-close for desktop app
  useEffect(() => {
    if (isDesktop && !loading && callbackData?.success) {
      // For desktop app, window will be redirected by custom protocol
      setTimeout(() => {
        window.close();
      }, 2000);
    }
  }, [isDesktop, loading, callbackData]);

  // Redirect for web app
  const redirectToApp = () => {
    if (isDesktop) {
      // Desktop app: send message via custom protocol
      try {
        window.location.href = `atom://auth/asana/close`;
      } catch (err) {
        console.error('Desktop redirect error:', err);
        window.close();
      }
    } else {
      // Web app: normal redirect
      if (window.opener) {
        window.opener.postMessage({
          type: 'asana_oauth_success',
          data: callbackData
        }, '*');
        window.close();
      } else {
        router.push('/integrations/asana');
      }
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="orange" />
              <Heading size="lg">Processing Asana Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your Asana connection...
              </Text>
              {isDesktop && (
                <Alert status="info" borderRadius="md" maxW="400px">
                  <DesktopIcon />
                  <Box>
                    <Text fontWeight="bold" mb={1}>Desktop App OAuth</Text>
                    <Text fontSize="sm" color="gray.600">
                      This will return to the desktop app after completion
                    </Text>
                  </Box>
                </Alert>
              )}
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
                  There was a problem connecting your Asana account. Please try again.
                </Text>
                
                <Button
                  colorScheme="orange"
                  leftIcon={<TaskIcon />}
                  onClick={() => isDesktop ? window.close() : window.location.reload()}
                >
                  {isDesktop ? 'Close Window' : 'Try Again'}
                </Button>
                
                <Button
                  variant="outline"
                  onClick={redirectToApp}
                >
                  {isDesktop ? 'Return to App' : 'Back to Dashboard'}
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
                Asana Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.user_info?.name}!
              </Text>
              {isDesktop && (
                <Badge size="sm" colorScheme="orange" ml={2}>
                  <DesktopIcon mr={1} />Desktop App
                </Badge>
              )}
            </VStack>

            {/* User Information */}
            {callbackData?.user_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Avatar
                      src={callbackData.user_info.avatar_url_128x128 || 
                             `https://ui-avatars.com/api/?name=${encodeURIComponent(callbackData.user_info.name)}&background=27334D&color=fff&size=128`
                      }
                      alt={callbackData.user_info.name}
                      size="xl"
                      border="3px solid"
                      borderColor="#27334D"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.user_info.name}
                      </Text>
                      <Text color="gray.600">
                        {callbackData.user_info.email}
                      </Text>
                    </VStack>
                    
                    {callbackData.user_info.workspaces && callbackData.user_info.workspaces.length > 0 && (
                      <VStack spacing={1} align="center">
                        <Text fontWeight="medium" fontSize="sm" color="gray.600">
                          Workspace(s)
                        </Text>
                        {callbackData.user_info.workspaces.map((workspace) => (
                          <Text key={workspace.gid} color="gray.800">
                            {workspace.name}
                          </Text>
                        ))}
                      </VStack>
                    )}
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
                  <HStack>
                    <Code fontSize="sm" p={1} borderRadius="md" noOfLines={1} maxW="200px">
                      {callbackData.token_info.access_token}
                    </Code>
                    <Button
                      size="sm"
                      variant="outline"
                      leftIcon={<CopyIcon />}
                      onClick={onCopy}
                    >
                      {hasCopied ? 'Copied!' : 'Copy'}
                    </Button>
                  </HStack>
                </HStack>
                
                {callbackData.token_info.refresh_token && (
                  <HStack spacing={4} w="full">
                    <Text fontWeight="bold" minW="120px">Refresh Token:</Text>
                    <HStack>
                      <Code fontSize="sm" p={1} borderRadius="md" noOfLines={1} maxW="200px">
                        {callbackData.token_info.refresh_token}
                      </Code>
                      <Button
                        size="sm"
                        variant="outline"
                        leftIcon={<CopyIcon />}
                        onClick={() => {
                          navigator.clipboard.writeText(callbackData.token_info?.refresh_token || '');
                        }}
                      >
                        Copy
                      </Button>
                    </HStack>
                  </HStack>
                )}
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Expires In:</Text>
                  <Text fontSize="sm" color="gray.600" fontFamily="mono">
                    {callbackData.token_info.expires_in} seconds
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Scope:</Text>
                  <Text fontSize="sm" color="gray.600" fontFamily="mono">
                    {callbackData.token_info.scope}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">User ID:</Text>
                  <Text fontSize="sm" color="gray.600" fontFamily="mono">
                    {callbackData.user_info?.gid}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Expires:</Text>
                  <Text fontSize="sm" color="gray.600">
                    {callbackData.token_info.expires_at ? 
                      new Date(callbackData.token_info.expires_at).toLocaleString() :
                      'Unknown'
                    }
                  </Text>
                </HStack>
              </VStack>
            )}

            <Divider />

            {/* Success Actions */}
            <VStack spacing={4} w="full">
              <Heading size="sm">What's Next?</Heading>
              
              <Text color="gray.600" textAlign="center">
                Your Asana account is now connected! You can:
              </Text>
              
              {isDesktop ? (
                <Alert status="success" borderRadius="md" maxW="400px">
                  <DesktopIcon />
                  <Box>
                    <Text fontWeight="bold" mb={1}>Desktop App Connected</Text>
                    <Text fontSize="sm" color="gray.600">
                      Your tokens will be stored securely in the desktop app.
                      This window will close automatically.
                    </Text>
                  </Box>
                </Alert>
              ) : (
                <Stack spacing={3} w="full">
                  <Button
                    colorScheme="orange"
                    onClick={redirectToApp}
                    w="full"
                  >
                    Continue to ATOM
                  </Button>
                  
                  <Button
                    variant="outline"
                    leftIcon={<ExternalLinkIcon />}
                    onClick={() => {
                      window.open('https://app.asana.com', '_blank');
                    }}
                    w="full"
                  >
                    Open Asana
                  </Button>
                </Stack>
              )}
            </VStack>

            {/* Auto-close message for desktop */}
            {isDesktop && (
              <Alert status="info" borderRadius="md" maxW="400px">
                <InfoIcon />
                <Box>
                  <Text fontWeight="bold" mb={1}>Returning to Desktop App</Text>
                  <Text fontSize="sm" color="gray.600">
                    This window will close in 2 seconds and return you to the desktop app.
                  </Text>
                </Box>
              </Alert>
            )}
          </VStack>
        </CardBody>
      </Card>
    </Container>
  );
};

export default AsanaDesktopCallback;