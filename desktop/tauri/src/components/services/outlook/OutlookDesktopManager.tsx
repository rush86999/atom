/**
 * Outlook Desktop Manager for Tauri application
 * Following the same pattern as GitLab Desktop Manager
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  Text,
  VStack,
  HStack,
  Alert,
  AlertIcon,
  Progress,
  useToast,
  Divider,
  Heading,
  Badge,
  IconButton,
  Tooltip,
} from "@chakra-ui/react";
import {
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
} from "@chakra-ui/icons";

interface OutlookConnectionStatus {
  connected: boolean;
  user?: {
    displayName: string;
    mail: string;
    jobTitle?: string;
  };
  error?: string;
}

interface OutlookDesktopManagerProps {
  userId: string;
  onConnectionChange?: (connected: boolean) => void;
}

export const OutlookDesktopManager: React.FC<OutlookDesktopManagerProps> = ({
  userId,
  onConnectionChange,
}) => {
  const [status, setStatus] = useState<OutlookConnectionStatus>({
    connected: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [oauthUrl, setOAuthUrl] = useState<string>("");
  const toast = useToast();

  // Check connection status on mount
  useEffect(() => {
    checkConnectionStatus();
  }, [userId]);

  const checkConnectionStatus = async () => {
    try {
      setIsLoading(true);

      // Check if we have Tauri available
      if (window.__TAURI__) {
        const { invoke } = window.__TAURI__;

        // Check Outlook OAuth status
        const outlookStatus = await invoke("check_outlook_oauth_status", {
          userId,
        });

        setStatus(outlookStatus);

        if (onConnectionChange) {
          onConnectionChange(outlookStatus.connected);
        }
      } else {
        // Fallback to API check
        const response = await fetch(
          `/api/auth/outlook/status?user_id=${userId}`,
        );
        const data = await response.json();

        setStatus({
          connected: data.connected,
          error: data.error,
        });

        if (onConnectionChange) {
          onConnectionChange(data.connected);
        }
      }
    } catch (error) {
      console.error("Failed to check Outlook connection status:", error);
      setStatus({
        connected: false,
        error: "Failed to check connection status",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const initiateOutlookOAuth = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const { invoke } = window.__TAURI__;

        // Initiate OAuth via Tauri
        const result = await invoke("initiate_outlook_oauth", {
          userId,
        });

        if (result.success) {
          setOAuthUrl(result.oauth_url);

          // Open in system browser
          const { open } = window.__TAURI__.shell;
          await open(result.oauth_url);

          toast({
            title: "Outlook OAuth Started",
            description: "Please complete the OAuth process in your browser",
            status: "info",
            duration: 5000,
          });
        } else {
          throw new Error(result.error || "Failed to initiate OAuth");
        }
      } else {
        // Fallback to API
        const response = await fetch(
          `/api/auth/outlook/authorize?user_id=${userId}`,
        );
        const data = await response.json();

        if (data.success) {
          window.open(data.oauth_url, "_blank");

          toast({
            title: "Outlook OAuth Started",
            description: "Please complete the OAuth process in the new window",
            status: "info",
            duration: 5000,
          });
        } else {
          throw new Error(data.error || "Failed to initiate OAuth");
        }
      }
    } catch (error) {
      console.error("Failed to initiate Outlook OAuth:", error);
      toast({
        title: "OAuth Failed",
        description: error instanceof Error ? error.message : "Unknown error",
        status: "error",
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const disconnectOutlook = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const { invoke } = window.__TAURI__;

        const result = await invoke("disconnect_outlook", {
          userId,
        });

        if (result.success) {
          setStatus({ connected: false });

          if (onConnectionChange) {
            onConnectionChange(false);
          }

          toast({
            title: "Outlook Disconnected",
            description: "Your Outlook integration has been disconnected",
            status: "success",
            duration: 3000,
          });
        } else {
          throw new Error(result.error || "Failed to disconnect");
        }
      } else {
        // Fallback to API
        const response = await fetch("/api/auth/outlook/disconnect", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ user_id: userId }),
        });

        const data = await response.json();

        if (data.ok) {
          setStatus({ connected: false });

          if (onConnectionChange) {
            onConnectionChange(false);
          }

          toast({
            title: "Outlook Disconnected",
            description: "Your Outlook integration has been disconnected",
            status: "success",
            duration: 3000,
          });
        } else {
          throw new Error(data.error?.message || "Failed to disconnect");
        }
      }
    } catch (error) {
      console.error("Failed to disconnect Outlook:", error);
      toast({
        title: "Disconnection Failed",
        description: error instanceof Error ? error.message : "Unknown error",
        status: "error",
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const testOutlookConnection = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const { invoke } = window.__TAURI__;

        const result = await invoke("test_outlook_connection", {
          userId,
        });

        if (result.success) {
          toast({
            title: "Connection Test Successful",
            description: `Retrieved ${result.data?.emails?.length || 0} emails`,
            status: "success",
            duration: 3000,
          });
        } else {
          throw new Error(result.error || "Connection test failed");
        }
      } else {
        // Fallback to API
        const response = await fetch("/api/auth/outlook/emails", {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("outlook_access_token") || ""}`,
          },
        });

        const data = await response.json();

        if (data.success) {
          toast({
            title: "Connection Test Successful",
            description: `Retrieved ${data.total || 0} emails`,
            status: "success",
            duration: 3000,
          });
        } else {
          throw new Error(data.error || "Connection test failed");
        }
      }
    } catch (error) {
      console.error("Failed to test Outlook connection:", error);
      toast({
        title: "Connection Test Failed",
        description: error instanceof Error ? error.message : "Unknown error",
        status: "error",
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box p={6} borderWidth={1} borderRadius="lg" bg="white">
      <VStack spacing={4} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <Heading size="md" color="blue.600">
            📧 Outlook Integration
          </Heading>
          <Badge
            colorScheme={status.connected ? "green" : "gray"}
            variant="solid"
            px={3}
            py={1}
          >
            {status.connected ? "Connected" : "Disconnected"}
          </Badge>
        </HStack>

        <Divider />

        {/* Status Display */}
        {status.connected && status.user ? (
          <Alert status="success" borderRadius="md">
            <AlertIcon as={CheckCircleIcon} />
            <Box>
              <Text fontWeight="bold">
                Connected as {status.user.displayName}
              </Text>
              <Text fontSize="sm" color="gray.600">
                {status.user.mail}
                {status.user.jobTitle && ` • ${status.user.jobTitle}`}
              </Text>
            </Box>
          </Alert>
        ) : status.error ? (
          <Alert status="error" borderRadius="md">
            <AlertIcon as={WarningIcon} />
            <Box>
              <Text fontWeight="bold">Connection Error</Text>
              <Text fontSize="sm">{status.error}</Text>
            </Box>
          </Alert>
        ) : (
          <Alert status="info" borderRadius="md">
            <AlertIcon />
            <Text>
              Connect your Outlook account to enable email and calendar
              automation
            </Text>
          </Alert>
        )}

        {/* Loading State */}
        {isLoading && (
          <Box>
            <Text mb={2}>Processing...</Text>
            <Progress size="sm" isIndeterminate />
          </Box>
        )}

        {/* Action Buttons */}
        <VStack spacing={3}>
          {!status.connected ? (
            <Button
              colorScheme="blue"
              onClick={initiateOutlookOAuth}
              isLoading={isLoading}
              loadingText="Initiating OAuth..."
              width="full"
              size="lg"
            >
              Connect Outlook Account
            </Button>
          ) : (
            <>
              <Button
                colorScheme="green"
                onClick={testOutlookConnection}
                isLoading={isLoading}
                loadingText="Testing connection..."
                width="full"
                size="lg"
              >
                Test Connection
              </Button>

              <Button
                colorScheme="red"
                variant="outline"
                onClick={disconnectOutlook}
                isLoading={isLoading}
                loadingText="Disconnecting..."
                width="full"
              >
                Disconnect Outlook
              </Button>
            </>
          )}
        </VStack>

        {/* OAuth URL Display (for debugging) */}
        {oauthUrl && (
          <Box>
            <Text fontSize="sm" fontWeight="bold" mb={2}>
              OAuth URL (for manual opening):
            </Text>
            <HStack>
              <Text
                fontSize="xs"
                color="gray.600"
                fontFamily="monospace"
                p={2}
                bg="gray.50"
                borderRadius="md"
                flex={1}
                isTruncated
              >
                {oauthUrl}
              </Text>
              <Tooltip label="Open in browser">
                <IconButton
                  aria-label="Open OAuth URL"
                  icon={<ExternalLinkIcon />}
                  size="sm"
                  onClick={() => window.open(oauthUrl, "_blank")}
                />
              </Tooltip>
            </HStack>
          </Box>
        )}

        {/* Feature List */}
        <Box>
          <Text fontSize="sm" fontWeight="bold" mb={2}>
            Features Available:
          </Text>
          <VStack align="start" spacing={1}>
            <Text fontSize="sm">📧 Send and receive emails</Text>
            <Text fontSize="sm">📅 Access calendar events</Text>
            <Text fontSize="sm">🔍 Search emails and calendar</Text>
            <Text fontSize="sm">🤖 Email and calendar automation</Text>
          </VStack>
        </Box>
      </VStack>
    </Box>
  );
};

export default OutlookDesktopManager;
