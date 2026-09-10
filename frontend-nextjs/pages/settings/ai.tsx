import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Box, Heading, Container, Text } from '@chakra-ui/react';
import AIProviderSettings from '@/src/components/AIProviders/AIProviderSettings';
import { useUserRole } from '@/lib/user-role';
const AISettingsPage = () => {
    // The routing dashboard reads workspace-wide model telemetry
    // (/api/chat/routing-stats is workspace_admin+). Unknown role → show
    // (backend enforces); a transient /api/auth/me failure must not hide nav.
    const { role, isAdmin } = useUserRole();
    const showRouting = !role || isAdmin;
    return (
        <>
            <Head>
                <title>AI Provider Settings | Atom</title>
            </Head>
            <Container maxW="container.xl" py={8}>
                <Box mb={8}>
                    <Heading as="h1" size="xl" mb={4}>AI Provider Settings</Heading>
                </Box>
                <AIProviderSettings baseApiUrl="/api" />
                {showRouting && (
                    <Box mt={8}>
                        <Link href="/settings/routing">
                            <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                                Routing &amp; Learning Dashboard →
                            </Text>
                        </Link>
                    </Box>
                )}
                <Box mt={4}>
                    <Link href="/settings/harness-evolution">
                        <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                            Self-Evolving Harness Dashboard →
                        </Text>
                    </Link>
                </Box>
                <Box mt={4}>
                    <Link href="/settings/local-models">
                        <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                            Local Models (Ollama, LM Studio, vLLM) →
                        </Text>
                    </Link>
                </Box>
            </Container>
        </>
    );
};

export default AISettingsPage;
