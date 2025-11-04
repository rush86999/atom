/**
 * Trello Desktop OAuth Callback Page
 * Handles OAuth 1.0a callback for desktop app following GitLab pattern
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
  ViewListIcon,
  InfoIcon,
  CopyIcon,
  DesktopIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface TrelloDesktopCallbackProps {
  isDesktop?: boolean;
}

interface TrelloCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    id: string;
    fullName: string;
    username: string;
    email?: string;
    avatarUrl?: string;
    bio?: string;
    bioData?: any;
    confirmed: boolean;
    idEnterprise?: string;
    status?: string;
    enterpriseId?: string;
    enterpriseName?: string;
    memberType: string;
    marketingOptIn?: boolean;
    emailVerified: boolean;
    loginTypes: string[];
    oneTimeMessagesDismissed: string[];
    trophies: string[];
    uploadedAvatar: boolean;
    uploadedAvatarUrl?: string;
    premiumFeatures: string[];
    idEnterprises?: string[];
    idTeams?: string[];
  };
  token_info?: {
    token: string;
    tokenSecret: string;
    expiration: string;
    verification_code?: string;
    app_id?: string;
    app_name?: string;
    app_type?: string;
    app_website?: string;
    domain?: string;
    memberId?: string;
    memberName?: string;
    memberEmail?: string;
    memberUsername?: string;
    memberAvatar?: string;
    enterpriseId?: string;
    enterpriseName?: string;
    created_at: string;
    expires_at: string;
  };
  error?: string;
}

const TrelloDesktopCallback: React.FC<TrelloDesktopCallbackProps> = ({
  isDesktop = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<TrelloCallbackData | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const router = useRouter();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { hasCopied, onCopy } = useClipboard(callbackData?.token_info?.token || '');

  // Parse URL parameters for Trello OAuth 1.0a
  useEffect(() => {
    const handleCallback = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const oauth_token = urlParams.get('oauth_token');
        const oauth_verifier = urlParams.get('oauth_verifier');
        const app_id = urlParams.get('app_id');
        const app_name = urlParams.get('app_name');
        const app_type = urlParams.get('app_type');
        const app_website = urlParams.get('app_website');
        const domain = urlParams.get('domain');

        if (!oauth_token || !oauth_verifier) {
          setError('OAuth token and verifier are required');
          setLoading(false);
          return;
        }

        // Exchange token for access token
        setLoading(true);
        const response = await fetch('/api/auth/trello/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token: oauth_token,
            verifier: oauth_verifier,
            app_id: app_id,
            app_name: app_name,
            app_type: app_type,
            app_website: app_website,
            domain: domain,
          }),
        });

        const data: TrelloCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          
          // Handle desktop app callback
          if (isDesktop) {
            try {
              // Send data to desktop app via custom protocol
              const callbackUrl = `atom://auth/trello/success?${new URLSearchParams({
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
            title: 'Trello Connected Successfully!',
            description: `Welcome, ${data.token_info?.memberName || data.token_info?.memberUsername}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'Trello Authentication Failed',
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
        window.location.href = `atom://auth/trello/close`;
      } catch (err) {
        console.error('Desktop redirect error:', err);
        window.close();
      }
    } else {
      // Web app: normal redirect
      if (window.opener) {
        window.opener.postMessage({
          type: 'trello_oauth_success',
          data: callbackData
        }, '*');
        window.close();
      } else {
        router.push('/integrations/trello');
      }
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="blue" />
              <Heading size="lg">Processing Trello Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your Trello connection...
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
                  There was a problem connecting your Trello account. Please try again.
                </Text>
                
                <Button
                  colorScheme="blue"
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
                Trello Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.token_info?.memberName || callbackData?.token_info?.memberUsername}!
              </Text>
              {isDesktop && (
                <Badge size="sm" colorScheme="blue" ml={2}>
                  <DesktopIcon mr={1} />Desktop App
                </Badge>
              )}
            </VStack>

            {/* User Information */}
            {callbackData?.user_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Box
                      as="img"
                      src={callbackData.user_info.avatarUrl || 
                             `https://ui-avatars.com/api/?name=${encodeURIComponent(callbackData.user_info.fullName)}&background=0079BF&color=fff&size=128`
                      }
                      alt={callbackData.user_info.fullName}
                      w={16}
                      h={16}
                      borderRadius="full"
                      border="2px solid"
                      borderColor="#0079BF"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.user_info.fullName}
                      </Text>
                      <Text color="gray.600">
                        @{callbackData.user_info.username}
                      </Text>
                      {callbackData.user_info.email && (
                        <Text fontSize="sm" color="gray.600">
                          {callbackData.user_info.email}
                        </Text>
                      )}
                      <Badge size="sm" colorScheme={
                        callbackData.user_info.memberType === 'admin' ? 'red' :
                        callbackData.user_info.memberType === 'owner' ? 'orange' : 'green'
                      }>
                        {callbackData.user_info.memberType}
                      </Badge>
                      {callbackData.user_info.idEnterprise && (
                        <Text fontSize="sm" color="gray.500">
                          Enterprise: {callbackData.user_info.enterpriseName || 'Business'}
                        </Text>
                      )}
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Workspace Information */}
            {callbackData?.token_info?.enterpriseId && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Icon as={ViewListIcon} w={12} h={12} color="#0079BF" />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.token_info.enterpriseName || 'Business Workspace'}
                      </Text>
                      <Text color="gray.600">
                        Enterprise ID: {callbackData.token_info.enterpriseId}
                      </Text>
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
                      {callbackData.token_info.token}
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
                  <Text fontWeight="bold" minW="120px">Token Secret:</Text>
                  <HStack>
                    <Code fontSize="sm" p={1} borderRadius="md" noOfLines={1} maxW="200px">
                      {callbackData.token_info.tokenSecret}
                    </Code>
                    <Button
                      size="sm"
                      variant="outline"
                      leftIcon={<CopyIcon />}
                      onClick={() => {
                        navigator.clipboard.writeText(callbackData.token_info?.tokenSecret || '');
                      }}
                    >
                      Copy
                    </Button>
                  </HStack>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">App Name:</Text>
                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                    {callbackData.token_info.app_name}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Member ID:</Text>
                  <Text fontSize="sm" color="gray.600" fontFamily="mono">
                    {callbackData.token_info.memberId}
                  </Text>
                </HStack>
                
                <HStack spacing={4} w="full">
                  <Text fontWeight="bold" minW="120px">Expires:</Text>
                  <Text fontSize="sm" color="gray.600">
                    {callbackData.token_info.expires_at ? 
                      new Date(callbackData.token_info.expires_at).toLocaleString() :
                      'Never'
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
                Your Trello account is now connected! You can:
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
                      window.open('https://trello.com', '_blank');
                    }}
                    w="full"
                  >
                    Open Trello
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

export default TrelloDesktopCallback;