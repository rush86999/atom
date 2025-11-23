import React, { useState, useEffect } from "react";
import { signIn, getSession } from "next-auth/react";
import { useRouter } from "next/router";
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  useToast,
  Alert,
  AlertIcon,
  Link,
} from "@chakra-ui/react";
import { GetServerSideProps } from "next";

export default function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    const checkSession = async () => {
      const session = await getSession();
      if (session) {
        router.push("/");
      }
    };
    checkSession();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        setError(result.error);
      } else {
        toast({
          title: "Successfully signed in!",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        router.push("/");
      }
    } catch (err) {
      setError("An unexpected error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxW="md" py={12}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading size="xl" mb={2}>
            Sign In to ATOM
          </Heading>
          <Text color="gray.600">Access your personal automation platform</Text>
        </Box>

        <Box w="100%" p={8} bg="white" borderRadius="lg" boxShadow="md">
          <form onSubmit={handleSubmit}>
            <VStack spacing={4}>
              {error && (
                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  {error}
                </Alert>
              )}

              <FormControl isRequired>
                <FormLabel>Email</FormLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  size="lg"
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Password</FormLabel>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  size="lg"
                />
              </FormControl>

              <Box w="100%" textAlign="right">
                <Link href="/auth/forgot-password" color="blue.500" fontSize="sm">
                  Forgot password?
                </Link>
              </Box>

              <Button
                type="submit"
                colorScheme="blue"
                size="lg"
                w="100%"
                isLoading={isLoading}
                loadingText="Signing in..."
              >
                Sign In
              </Button>

              <Box w="100%" position="relative" py={2}>
                <Box
                  position="absolute"
                  top="50%"
                  left="0"
                  right="0"
                  borderTop="1px"
                  borderColor="gray.300"
                />
                <Text
                  position="relative"
                  bg="white"
                  px={2}
                  fontSize="sm"
                  color="gray.500"
                  textAlign="center"
                  display="inline-block"
                  mx="auto"
                  width="fit-content"
                >
                  Or continue with
                </Text>
              </Box>

              <VStack spacing={3} w="100%">
                <Button
                  w="100%"
                  variant="outline"
                  size="lg"
                  onClick={() => signIn('google', { callbackUrl: '/' })}
                >
                  <Box as="span" mr={2}>🔍</Box>
                  Sign in with Google
                </Button>

                <Button
                  w="100%"
                  variant="outline"
                  size="lg"
                  onClick={() => signIn('github', { callbackUrl: '/' })}
                >
                  <Box as="span" mr={2}>⚫</Box>
                  Sign in with GitHub
                </Button>
              </VStack>
            </VStack>
          </form>

          <Box mt={4} textAlign="center">
            <Text color="gray.600">
              Don&apos;t have an account?{" "}
              <Link
                href="/auth/signup"
                color="blue.500"
                fontWeight="medium"
                textDecoration="underline"
              >
                Sign up
              </Link>
            </Text>
          </Box>
        </Box>
      </VStack>
    </Container>
  );
}


