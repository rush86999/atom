/**
 * Slack OAuth Callback Page
 * Handles OAuth 2.0 callback for Slack integration
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
  ChatIcon,
  InfoIcon,
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

interface SlackCallbackProps {
  // Component props
}

interface SlackCallbackData {
  success: boolean;
  message?: string;
  user_info?: {
    id: string;
    name: string;
    real_name: string;
    email?: string;
    image_24?: string;
    image_48?: string;
    image_72?: string;
    image_192?: string;
    team_id?: string;
    team_name?: string;
    is_admin?: boolean;
    is_owner?: boolean;
    is_primary_owner?: boolean;
  };
  workspace_info?: {
    id: string;
    name: string;
    domain: string;
    url: string;
    icon?: string;
    enterprise_id?: string;
    enterprise_name?: string;
  };
  token_info?: {
    access_token: string;
    token_type: string;
    scope: string;
    bot_user_id?: string;
    team_id?: string;
    expires_in?: number;
  };
  error?: string;
}

const SlackCallback: React.FC<SlackCallbackProps> = () => {
  const [loading, setLoading] = useState(true);
  const [callbackData, setCallbackData] = useState<SlackCallbackData | null>(null);
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
        const response = await fetch('/api/auth/slack/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code: code,
            state: state,
          }),
        });

        const data: SlackCallbackData = await response.json();

        if (data.success) {
          setCallbackData(data);
          toast({
            title: 'Slack Connected Successfully!',
            description: `Welcome, ${data.user_info?.real_name || data.user_info?.name}!`,
            status: 'success',
            duration: 5000,
          });
        } else {
          setError(data.error || data.message || 'Authentication failed');
          toast({
            title: 'Slack Authentication Failed',
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
        type: 'slack_oauth_success',
        data: callbackData
      }, '*');
      window.close();
    } else {
      router.push('/integrations/slack');
    }
  };

  if (loading) {
    return (
      <Container maxW="md" py={10}>
        <Card>
          <CardBody>
            <VStack spacing={6} align="center" py={10}>
              <Spinner size="xl" thickness="4px" speed="0.65s" color="purple.500" />
              <Heading size="lg">Processing Slack Authentication</Heading>
              <Text color="gray.600" textAlign="center">
                Please wait while we complete your Slack connection...
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
                  There was a problem connecting your Slack workspace. Please try again.
                </Text>
                
                <Button
                  colorScheme="purple"
                  leftIcon={<ChatIcon />}
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
                Slack Connected Successfully!
              </Heading>
              <Text fontSize="xl" fontWeight="medium">
                Welcome, {callbackData?.user_info?.real_name || callbackData?.user_info?.name}!
              </Text>
            </VStack>

            {/* User Information */}
            {callbackData?.user_info && (
              <Card bg={bgColor} border="1px" borderColor={borderColor} w="full">
                <CardBody>
                  <VStack spacing={4} align="center">
                    <Box
                      as="img"
                      src={callbackData.user_info.image_48 || callbackData.user_info.image_72}
                      alt={callbackData.user_info.name}
                      w={16}
                      h={16}
                      borderRadius="full"
                      border="2px solid"
                      borderColor="purple.200"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.user_info.real_name}
                      </Text>
                      <Text color="gray.600">
                        @{callbackData.user_info.name}
                      </Text>
                      {callbackData.user_info.email && (
                        <Text color="gray.500" fontSize="sm">
                          {callbackData.user_info.email}
                        </Text>
                      )}
                    </VStack>

                    {/* User Roles */}
                    <HStack spacing={2}>
                      {callbackData.user_info.is_admin && (
                        <Badge size="sm" colorScheme="blue">Admin</Badge>
                      )}
                      {callbackData.user_info.is_owner && (
                        <Badge size="sm" colorScheme="purple">Owner</Badge>
                      )}
                      {callbackData.user_info.is_primary_owner && (
                        <Badge size="sm" colorScheme="orange">Primary Owner</Badge>
                      )}
                    </HStack>

                    {/* Team Information */}
                    {callbackData.user_info.team_name && (
                      <HStack spacing={2}>
                        <Icon as={InfoIcon} w={4} h={4} color="purple.500" />
                        <Text fontSize="sm" color="gray.600">
                          Team: {callbackData.user_info.team_name}
                        </Text>
                      </HStack>
                    )}
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
                      src={callbackData.workspace_info.icon}
                      alt={callbackData.workspace_info.name}
                      w={12}
                      h={12}
                      borderRadius="md"
                    />
                    
                    <VStack spacing={1} align="center">
                      <Text fontWeight="bold" fontSize="lg">
                        {callbackData.workspace_info.name}
                      </Text>
                      <Text color="gray.600">
                        {callbackData.workspace_info.domain}.slack.com
                      </Text>
                    </VStack>

                    {/* Enterprise Information */}
                    {callbackData.workspace_info.enterprise_name && (
                      <HStack spacing={2}>
                        <Text fontSize="sm" color="gray.600">
                          Enterprise: {callbackData.workspace_info.enterprise_name}
                        </Text>
                      </HStack>
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

                {callbackData.token_info.expires_in && (
                  <HStack spacing={4} w="full">
                    <Text fontWeight="bold" minW="120px">Expires:</Text>
                    <Text fontSize="sm" color="gray.600">
                      {callbackData.token_info.expires_in} seconds
                    </Text>
                  </HStack>
                )}

                {callbackData.token_info.bot_user_id && (
                  <HStack spacing={4} w="full">
                    <Text fontWeight="bold" minW="120px">Bot User:</Text>
                    <Badge size="sm" colorScheme="purple">
                      ID: {callbackData.token_info.bot_user_id}
                    </Badge>
                  </HStack>
                )}
              </VStack>
            )}

            <Divider />

            {/* Success Actions */}
            <VStack spacing={4} w="full">
              <Heading size="sm">What's Next?</Heading>
              
              <Text color="gray.600" textAlign="center">
                Your Slack workspace is now connected! You can:
              </Text>
              
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
                    window.open(callbackData?.workspace_info?.url || 'https://slack.com', '_blank');
                  }}
                  w="full"
                >
                  Open Slack Workspace
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

export default SlackCallback;