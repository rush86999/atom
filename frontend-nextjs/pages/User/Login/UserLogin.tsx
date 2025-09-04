import React, { useState } from 'react';
import {
  Box,
  Button,
  VStack,
  Heading,
  Text,
  Input,
  FormControl,
  FormLabel,
  useToast
} from '@chakra-ui/react';

const UserLogin: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    // For development purposes, create a mock session
    try {
      // Simulate login process
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Set a mock session cookie (this is just for development)
      document.cookie = 'atom-dev-session=authenticated; path=/; max-age=3600';

      toast({
        title: 'Logged in successfully',
        status: 'success',
        duration: 2000,
        isClosable: true,
      });

      // Redirect to dashboard
      window.location.href = '/';

    } catch (error) {
      toast({
        title: 'Login failed',
        description: 'Please try again',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDevBypass = () => {
    // Direct bypass for development
    document.cookie = 'atom-dev-session=authenticated; path=/; max-age=3600';
    window.location.href = '/';
  };

  return (
    <Box
      minH="100vh"
      bg="gray.50"
      display="flex"
      alignItems="center"
      justifyContent="center"
      p={4}
    >
      <Box
        bg="white"
        p={8}
        borderRadius="lg"
        boxShadow="lg"
        maxW="md"
        w="full"
      >
        <VStack spacing={6} align="stretch">
          <Heading size="lg" textAlign="center">
            Sign in to Atom
          </Heading>

          <Text color="gray.600" textAlign="center">
            Your personal assistant for managing work and life
          </Text>

          <form onSubmit={handleLogin}>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Email address</FormLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  required
                />
              </FormControl>

              <FormControl>
                <FormLabel>Password</FormLabel>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </FormControl>

              <Button
                type="submit"
                colorScheme="blue"
                width="full"
                isLoading={loading}
                loadingText="Signing in..."
              >
                Sign in
              </Button>
            </VStack>
          </form>

          <Text textAlign="center" color="gray.500" fontSize="sm">
            Or
          </Text>

          <Button
            variant="outline"
            colorScheme="green"
            width="full"
            onClick={handleDevBypass}
          >
            Development Bypass
          </Button>

          <Text fontSize="sm" color="gray.500" textAlign="center">
            For development purposes only. This bypasses authentication.
          </Text>
        </VStack>
      </Box>
    </Box>
  );
};

export default UserLogin;
