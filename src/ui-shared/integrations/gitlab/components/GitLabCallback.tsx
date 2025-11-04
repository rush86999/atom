/**
 * GitLab OAuth Callback Component
 * Handles OAuth callback for GitLab integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Icon,
  useToast,
  Button,
  Progress,
  Alert,
  AlertIcon,
  useColorModeValue
} from '@chakra-ui/react';
import {
  GitlabIcon,
  CheckCircleIcon,
  WarningIcon,
  ArrowForwardIcon,
  RefreshIcon
} from '@chakra-ui/icons';
import { useRouter } from 'next/router';

const GitLabCallback: React.FC = () => {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [userInfo, setUserInfo] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [progress, setProgress] = useState(0);
  
  const toast = useToast();
  const router = useRouter();
  const bgColor = useColorModeValue('white', 'gray.800');
  
  // Handle OAuth callback
  useEffect(() => {
    const handleCallback = async () => {
      const { code, state, error } = router.query;
      
      if (error) {
        setStatus('error');
        setMessage(`Authentication failed: ${error}`);
        return;
      }
      
      if (!code || !state) {
        setStatus('error');
        setMessage('Invalid OAuth response');
        return;
      }
      
      try {
        setProgress(20);
        
        // Exchange code for tokens
        const response = await fetch('/api/integrations/gitlab/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: code as string,
            state: state as string
          })
        });
        
        setProgress(40);
        
        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.error || 'OAuth callback failed');
        }
        
        setProgress(60);
        
        // Get user information
        const userResponse = await fetch('/api/integrations/gitlab/user', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: data.user_id
          })
        });
        
        setProgress(80);
        
        const userData = await userResponse.json();
        
        if (userResponse.ok) {
          setUserInfo(userData.user);
          setProjects(userData.projects || []);
        }
        
        setProgress(100);
        setStatus('success');
        setMessage(`Successfully connected to GitLab as ${userData.user?.name || 'user'}!`);
        
        // Show success toast
        toast({
          title: 'GitLab Connected',
          description: 'Successfully connected to your GitLab account',
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        
        // Close popup after 2 seconds
        setTimeout(() => {
          if (window.opener) {
            window.opener.postMessage({
              type: 'gitlab-oauth-success',
              user: userData.user,
              projects: userData.projects
            }, '*');
          }
        }, 2000);
        
      } catch (error) {
        setStatus('error');
        setMessage(error instanceof Error ? error.message : 'Authentication failed');
        
        toast({
          title: 'GitLab Authentication Failed',
          description: error instanceof Error ? error.message : 'Unknown error occurred',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    };
    
    if (router.isReady) {
      handleCallback();
    }
  }, [router.isReady, router.query, toast]);
  
  const handleContinue = () => {
    if (window.opener) {
      window.close();
    } else {
      router.push('/integrations/gitlab');
    }
  };
  
  const handleRetry = () => {
    router.push('/integrations/gitlab');
  };
  
  const getStatusIcon = () => {
    switch (status) {
      case 'success':
        return <CheckCircleIcon w={16} h={16} color="green.500" />;
      case 'error':
        return <WarningIcon w={16} h={16} color="red.500" />;
      default:
        return <GitlabIcon w={16} h={16} color="orange.500" />;
    }
  };
  
  const getStatusColor = () => {
    switch (status) {
      case 'success':
        return 'green';
      case 'error':
        return 'red';
      default:
        return 'orange';
    }
  };
  
  const getStatusMessage = () => {
    if (status === 'loading') {
      return 'Connecting to GitLab...';
    }
    return message;
  };
  
  return (
    <Box minH="100vh" bg={bgColor} p={8}>
      <VStack spacing={8} align="center" justify="center" minH="100vh">
        <Card maxW="500px" w="full">
          <CardHeader>
            <VStack spacing={4} align="center">
              <HStack spacing={4}>
                <Icon as={GitlabIcon} w={12} h={12} color="orange.500" />
                <Heading size="xl" color="orange.500">
                  GitLab Integration
                </Heading>
              </HStack>
              
              <HStack spacing={2}>
                {getStatusIcon()}
                <Text fontSize="lg" fontWeight="bold" color={`${getStatusColor()}.500`}>
                  {status === 'success' ? 'Connected!' : 
                   status === 'error' ? 'Authentication Failed' :
                   'Connecting...'}
                </Text>
              </HStack>
            </VStack>
          </CardHeader>
          
          <CardBody>
            <VStack spacing={6} align="stretch">
              <Alert
                status={status === 'error' ? 'error' : status === 'success' ? 'success' : 'info'}
                variant="subtle"
                borderRadius="md"
              >
                <AlertIcon />
                <Text>{getStatusMessage()}</Text>
              </Alert>
              
              {status === 'loading' && (
                <VStack spacing={3} align="stretch">
                  <Text fontSize="sm" color="gray.600" textAlign="center">
                    Please wait while we connect to your GitLab account...
                  </Text>
                  <Progress value={progress} colorScheme="orange" size="lg" w="full" />
                  <Text fontSize="sm" color="gray.500">
                    {progress}% Complete
                  </Text>
                </VStack>
              )}
              
              {status === 'success' && userInfo && (
                <VStack spacing={4} align="stretch">
                  <HStack spacing={4} p={4} bg="green.50" borderRadius="md">
                    <Icon as={CheckCircleIcon} w={6} h={6} color="green.500" />
                    <VStack align="start" spacing={1">
                      <Text fontWeight="bold" color="green.800">
                        Successfully Connected!
                      </Text>
                      <Text fontSize="sm" color="green.700">
                        Logged in as {userInfo.name} (@{userInfo.username})
                      </Text>
                    </VStack>
                  </HStack>
                  
                  {projects.length > 0 && (
                    <VStack align="stretch">
                      <Text fontWeight="bold" fontSize="md">
                        Found {projects.length} projects
                      </Text>
                      <Box maxH="150px" overflowY="auto" w="full">
                        {projects.slice(0, 5).map((project, index) => (
                          <HStack key={index} p={2} bg="gray.50" borderRadius="md">
                            <Icon as={GitlabIcon} w={4} h={4" color="orange.500" />
                            <Text fontSize="sm" noOfLines={1}>
                              {project.name || project.path}
                            </Text>
                          </HStack>
                        ))}
                        {projects.length > 5 && (
                          <Text fontSize="sm" color="gray.500" textAlign="center">
                            ... and {projects.length - 5} more
                          </Text>
                        )}
                      </Box>
                    </VStack>
                  )}
                  
                  <Button
                    colorScheme="green"
                    leftIcon={<ArrowForwardIcon />}
                    onClick={handleContinue}
                    w="full"
                  >
                    Continue to Integration
                  </Button>
                </VStack>
              )}
              
              {status === 'error' && (
                <VStack spacing={4} align="stretch">
                  <Alert status="error" variant="subtle" borderRadius="md">
                    <AlertIcon />
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="bold" color="red.800">
                        Authentication Failed
                      </Text>
                      <Text fontSize="sm" color="red.700">
                        {message}
                      </Text>
                    </VStack>
                  </Alert>
                  
                  <VStack align="stretch" spacing={2}>
                    <Button
                      colorScheme="blue"
                      leftIcon={<RefreshIcon />}
                      onClick={handleRetry}
                      w="full"
                    >
                      Try Again
                    </Button>
                    
                    <Button
                      variant="outline"
                      onClick={handleContinue}
                      w="full"
                    >
                      Close Window
                    </Button>
                  </VStack>
                </VStack>
              )}
              
              <Box mt={4} pt={4} borderTop="1px" borderColor="gray.200">
                <VStack spacing={2}>
                  <Text fontSize="xs" color="gray.500" textAlign="center">
                    Powered by ATOM Integration Platform
                  </Text>
                  <HStack spacing={4} justify="center">
                    <Text fontSize="xs" color="gray.500">
                      Privacy Policy
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      •
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      Terms of Service
                    </Text>
                  </HStack>
                </VStack>
              </Box>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default GitLabCallback;