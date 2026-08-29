import React from "react";
import Head from "next/head";
import Link from "next/link";
import { Box, Heading, Container, Text } from "@chakra-ui/react";
import BPEManager from "@/src/components/BPE/BPEManager";

const BPESettingsPage = () => {
  return (
    <>
      <Head>
        <title>BPE Workspace | Atom</title>
      </Head>
      <Container maxW="container.xl" py={8}>
        <Box mb={8}>
          <Heading as="h1" size="xl" mb={4}>BPE Workspace</Heading>
        </Box>
        <BPEManager />
        <Box mt={8}>
          <Link href="/settings/ai">
            <Text color="blue.500" _hover={{ textDecoration: "underline" }} cursor="pointer">
              AI Provider Settings →
            </Text>
          </Link>
        </Box>
        <Box mt={4}>
          <Link href="/settings/harness-evolution">
            <Text color="blue.500" _hover={{ textDecoration: "underline" }} cursor="pointer">
              Self-Evolving Harness Dashboard →
            </Text>
          </Link>
        </Box>
        <Box mt={4}>
          <Link href="/admin/bpe">
            <Text color="blue.500" _hover={{ textDecoration: "underline" }} cursor="pointer">
              BPE Workspace (full admin surface) →
            </Text>
          </Link>
        </Box>
      </Container>
    </>
  );
};

export default BPESettingsPage;
