/**
 * Notion Desktop OAuth Callback Page
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
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  BookIcon,
  InfoIcon,
  CopyIcon,
  DesktopIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface NotionDesktopCallbackProps {
  isDesktop?: boolean;
}

interface NotionCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    id: string;
    name: string;
    email?: string;
    avatar_url?: string;
    type: 'person' | 'bot';
    person?: {
      email: string;
    };
  };
  workspace_info?: {
    id: string;
    name: string;
    icon: string;
    domain?: string;
  };
  token_info?: {
    access_token: string;
    token_type: string;
    scope: string;
    workspace_id: string;
    workspace_name: string;
    workspace_icon: string;
    user_id: string;
    user_name: string;
    user_email: string;
    user_avatar: string;
    expires_at: string;
    created_at: string;
  };
  error?: string;
}

const NotionDesktopCallback: React.FC<NotionDesktopCallbackProps> = ({
  isDesktop = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<NotionCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(callbackData?.token_info?.access_token || '');

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
        const response = await fetch('/api/auth/notion/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            state: state,
          }),
        });

        const data: NotionCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          
          // Handle desktop app callback
          if (isDesktop) {
            try {
              // Send data to desktop app via custom protocol
              const callbackUrl = `atom://auth/notion/success?${new URLSearchParams({
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
            title: 'Notion Connected Successfully!',
            description: `Welcome, ${data.token_info?.user_name || data.token_info?.user_email}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'Notion Authentication Failed',
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
        window.location.href = `atom://auth/notion/close`;
      } catch (err) {
        console.error('Desktop redirect error:', err);
        window.close();
      }
    } else {
      // Web app: normal redirect
      if (window.opener) {
        window.opener.postMessage({
          type: 'notion_oauth_success',
          data: callbackData
        }, '*');
        window.close();
      } else {
        router.push('/integrations/notion');
      }
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="black" />
              <Heading size="lg">Processing Notion Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your Notion connection...
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
                  There was a problem connecting your Notion workspace. Please try again.
                </Text>
                
                <Button
                  colorScheme="black"
                  leftIcon={<BookIcon />}
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
                Notion Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.token_info?.user_name || callbackData?.token_info?.user_email}!
              </Text>
              {isDesktop && (
                <Badge size="sm" colorScheme="blue" ml={2}>
                  <DesktopIcon mr={1} />Desktop App
                </Badge>
              )}
            </VStack>

            {/* User Information */}
            {callbackData?.token_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Box
                      as="img"
                      src={callbackData.token_info.user_avatar || 
                             `https://ui-avatars.com/api/?name=${encodeURIComponent(callbackData.token_info.user_name)}&background=000000&color=fff&size=128`
                      }
                      alt={callbackData.token_info.user_name}
                      w={16}
                      h={16}
                      borderRadius="full"
                      border="2px solid"
                      borderColor="black"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.token_info.user_name}
                      </Text>
                      <Text color="gray.600">
                        {callbackData.token_info.user_email}
                      </Text>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Workspace Information */}
            {callbackData?.workspace_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Box
                      as="img"
                      src={callbackData.workspace_info.icon || 
                             `https://ui-avatars.com/api/?name=${encodeURIComponent(callbackData.workspace_info.name)}&background=000000&color=fff&size=64`
                      }
                      alt={callbackData.workspace_info.name}
                      w={12}
                      h={12}
                      borderRadius="md"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.workspace_info.name}
                      </Text>
                      {callbackData.workspace_info.domain && (
                        <Text color="gray.600">
                          {callbackData.workspace_info.domain}.notion.so
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
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Scope:</Text>
                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                    {callbackData.token_info.scope.split(',').join(', ')}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Workspace ID:</Text>
                  <Text fontSize="sm" color="gray.600" fontFamily="mono">
                    {callbackData.token_info.workspace_id}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Expires:</Text>
                  <Text fontSize="sm" color="gray.600">
                    {callbackData.token_info.expires_at ? 
                      new Date(callbackData.token_info.expires_at).toLocaleString() :
                      'No expiration'
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
                Your Notion workspace is now connected! You can:
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
                    colorScheme="black"
                    onClick={redirectToApp}
                    w="full"
                  >
                    Continue to ATOM
                  </Button>
                  
                  <Button
                    variant="outline"
                    leftIcon={<ExternalLinkIcon />}
                    onClick={() => {
                      window.open(callbackData?.workspace_info?.domain ? 
                        `https://${callbackData.workspace_info.domain}.notion.so` : 
                        'https://notion.so', '_blank');
                    }}
                    w="full"
                  >
                    Open Notion
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

export default NotionDesktopCallback;