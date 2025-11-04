/**
 * Figma Desktop OAuth Callback Page
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
  Image as ImageIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface FigmaDesktopCallbackProps {
  isDesktop?: boolean;
}

interface FigmaCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    id: string;
    name: string;
    username: string;
    email?: string;
    profile_picture_url?: string;
    department?: string;
    title?: string;
    organization_id?: string;
    role?: string;
    can_edit: boolean;
    has_guests: boolean;
    is_active: boolean;
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

const FigmaDesktopCallback: React.FC<FigmaDesktopCallbackProps> = ({
  isDesktop = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<FigmaCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(callbackData?.token_info?.access_token || '');

  // Parse URL parameters for Figma OAuth 2.0
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
        const response = await fetch('/api/auth/figma/callback', {
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

        const data: FigmaCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          
          // Handle desktop app callback
          if (isDesktop) {
            try {
              // Send data to desktop app via custom protocol
              const callbackUrl = `atom://auth/figma/success?${new URLSearchParams({
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
            title: 'Figma Connected Successfully!',
            description: `Welcome, ${data.user_info?.name || data.user_info?.username}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'Figma Authentication Failed',
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
        window.location.href = `atom://auth/figma/close`;
      } catch (err) {
        console.error('Desktop redirect error:', err);
        window.close();
      }
    } else {
      // Web app: normal redirect
      if (window.opener) {
        window.opener.postMessage({
          type: 'figma_oauth_success',
          data: callbackData
        }, '*');
        window.close();
      } else {
        router.push('/integrations/figma');
      }
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="purple" />
              <Heading size="lg">Processing Figma Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your Figma connection...
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
                  There was a problem connecting your Figma account. Please try again.
                </Text>
                
                <Button
                  colorScheme="purple"
                  leftIcon={<ViewListIcon />}
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
                Figma Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.user_info?.name || callbackData?.user_info?.username}!
              </Text>
              {isDesktop && (
                <Badge size="sm" colorScheme="purple" ml={2}>
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
                      src={callbackData.user_info.profile_picture_url || 
                             `https://ui-avatars.com/api/?name=${encodeURIComponent(callbackData.user_info.name)}&background=F24E1E&color=fff&size=128`
                      }
                      alt={callbackData.user_info.name}
                      size="xl"
                      border="3px solid"
                      borderColor="#F24E1E"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.user_info.name}
                      </Text>
                      <Text color="gray.600">
                        @{callbackData.user_info.username}
                      </Text>
                      {callbackData.user_info.email && (
                        <Text fontSize="sm" color="gray.600">
                          {callbackData.user_info.email}
                        </Text>
                      )}
                      {callbackData.user_info.title && (
                        <Text fontSize="sm" color="gray.600">
                          {callbackData.user_info.title}
                        </Text>
                      )}
                      {callbackData.user_info.department && (
                        <Text fontSize="sm" color="gray.600">
                          {callbackData.user_info.department}
                        </Text>
                      )}
                      <Badge size="sm" colorScheme={
                        callbackData.user_info.role === 'admin' ? 'red' :
                        callbackData.user_info.role === 'owner' ? 'orange' : 'green'
                      }>
                        {callbackData.user_info.role || 'member'}
                      </Badge>
                      {callbackData.user_info.organization_id && (
                        <Text fontSize="sm" color="gray.500">
                          Organization: {callbackData.user_info.organization_id}
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
                Your Figma account is now connected! You can:
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
                    colorScheme="purple"
                    onClick={redirectToApp}
                    w="full"
                  >
                    Continue to ATOM
                  </Button>
                  
                  <Button
                    variant="outline"
                    leftIcon={<ExternalLinkIcon />}
                    onClick={() => {
                      window.open('https://www.figma.com', '_blank');
                    }}
                    w="full"
                  >
                    Open Figma
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

export default FigmaDesktopCallback;