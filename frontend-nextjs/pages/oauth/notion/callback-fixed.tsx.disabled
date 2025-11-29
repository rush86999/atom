/**
 * Notion OAuth Callback Page
 * Handles OAuth 2.0 callback for Notion integration
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Container,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Alert,
  AlertIcon,
  Icon,
} from '@chakra-ui/react'
import { CheckCircleIcon, WarningTwoIcon, ArrowForwardIcon } from '@chakra-ui/icons'
import { useRouter } from 'next/router'

interface NotionCallbackData {
  code?: string
  state?: string
  error?: string
  token_info?: {
    access_token: string
    workspace_id: string
    workspace_name: string
    workspace_icon: string
    bot_id: string
    owner?: {
      type: 'user' | 'workspace'
      id: string
    }
    duplicated_template_id?: string
  }
}

const CallbackSuccess: React.FC<{
  workspaceName: string
  workspaceIcon: string
  onContinue: () => void
}> = ({ workspaceName, workspaceIcon, onContinue }) => {
  return (
    <VStack spacing={6} textAlign="center">
      <Box
        w={20}
        h={20}
        borderRadius="full"
        bg="green.100"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <CheckCircleIcon color="green.600" w={10} h={10} />
      </Box>

      <VStack spacing={3}>
        <Heading size="lg" color="gray.800">
          Successfully Connected!
        </Heading>

        <HStack spacing={3} justify="center" align="center">
          <Box
            w={10}
            h={10}
            borderRadius="md"
            bg="gray.100"
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <Icon as={workspaceIcon || '📄'} w={6} h={6} />
          </Box>
          <Text fontSize="lg" fontWeight="medium">
            {workspaceName}
          </Text>
        </HStack>

        <Text fontSize="md" color="gray.600">
          Your Notion workspace is now connected to ATOM.
        </Text>
      </VStack>

      <Button
        colorScheme="blue"
        rightIcon={<ArrowForwardIcon />}
        onClick={onContinue}
        size="lg"
        w="full"
        maxW="sm"
      >
        Continue to Dashboard
      </Button>
    </VStack>
  )
}

const CallbackError: React.FC<{
  error: string
  onRetry: () => void
}> = ({ error, onRetry }) => {
  return (
    <VStack spacing={6} textAlign="center">
      <Box
        w={20}
        h={20}
        borderRadius="full"
        bg="red.100"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <WarningTwoIcon color="red.600" w={10} h={10} />
      </Box>

      <VStack spacing={3}>
        <Heading size="lg" color="gray.800">
          Connection Failed
        </Heading>

        <Alert status="error" borderRadius="md" flexDirection="column" alignItems="center">
          <AlertIcon />
          <Text textAlign="center">{error}</Text>
        </Alert>

        <Text fontSize="md" color="gray.600">
          There was an error connecting your Notion workspace.
        </Text>
      </VStack>

      <HStack spacing={4}>
        <Button variant="outline" onClick={onRetry}>
          Try Again
        </Button>
        <Button
          colorScheme="gray"
          onClick={() => window.close()}
        >
          Close Window
        </Button>
      </HStack>
    </VStack>
  )
}

const NotionOAuthCallback: React.FC = () => {
  const router = useRouter()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [workspaceInfo, setWorkspaceInfo] = useState<{
    name: string
    icon: string
  } | null>(null)

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Parse URL parameters
        const urlParams = new URLSearchParams(window.location.search)
        const code = urlParams.get('code')
        const state = urlParams.get('state')
        const errorParam = urlParams.get('error')

        if (errorParam) {
          setError(`OAuth Error: ${errorParam}`)
          setStatus('error')
          return
        }

        if (!code) {
          setError('Authorization code not found')
          setStatus('error')
          return
        }

        // Exchange authorization code for access token
        const response = await fetch('/api/oauth/notion/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, state }),
        })

        const data: NotionCallbackData = await response.json()

        if (data.token_info) {
          setWorkspaceInfo({
            name: data.token_info.workspace_name,
            icon: data.token_info.workspace_icon,
          })
          setStatus('success')

          // Store tokens and redirect after delay
          setTimeout(() => {
            router.push('/integrations/notion?success=true')
          }, 3000)
        } else if (data.error) {
          setError(data.error)
          setStatus('error')
        } else {
          setError('Unknown error occurred')
          setStatus('error')
        }
      } catch (err) {
        setError('Failed to process OAuth callback')
        setStatus('error')
      }
    }

    handleCallback()
  }, [router])

  const handleRetry = () => {
    setStatus('loading')
    setError(null)
    window.location.href = '/oauth/notion/authorize'
  }

  const handleContinue = () => {
    router.push('/integrations/notion')
  }

  return (
    <Container maxW="md" py={16}>
      <VStack spacing={8}>
        <Heading size="2xl" textAlign="center" color="gray.800">
          Notion Integration
        </Heading>

        {status === 'loading' && (
          <VStack spacing={6} align="center">
            <Box
              w={20}
              h={20}
              borderRadius="full"
              bg="blue.100"
              display="flex"
              alignItems="center"
              justifyContent="center"
            >
              <Icon as="🔄" w={10} h={10} />
            </Box>
            <Text fontSize="lg" color="gray.600">
              Processing OAuth callback...
            </Text>
          </VStack>
        )}

        {status === 'success' && workspaceInfo && (
          <CallbackSuccess
            workspaceName={workspaceInfo.name}
            workspaceIcon={workspaceInfo.icon}
            onContinue={handleContinue}
          />
        )}

        {status === 'error' && error && (
          <CallbackError error={error} onRetry={handleRetry} />
        )}
      </VStack>
    </Container>
  )
}

export default NotionOAuthCallback
