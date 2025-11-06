/**
 * Outlook Desktop Manager
 * GitLab pattern implementation
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
  Spinner,
  SimpleGrid,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
} from "@chakra-ui/react";
import {
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  RefreshIcon,
} from "@chakra-ui/icons";

interface OutlookConnectionStatus {
  connected: boolean;
  user?: {
    displayName: string;
    mail: string;
    jobTitle?: string;
    officeLocation?: string;
  };
  error?: string;
  tokens?: {
    expires_in: number;
    scope: string;
  };
}

interface OutlookEmail {
  id: string;
  subject: string;
  from: { name: string; address: string };
  to: Array<{ name: string; address: string }>;
  body: string;
  receivedDateTime: string;
  isRead: boolean;
  importance: string;
}

interface OutlookCalendarEvent {
  id: string;
  subject: string;
  start: { dateTime: string; timeZone: string };
  end: { dateTime: string; timeZone: string };
  location?: string;
  body?: string;
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
  const [emails, setEmails] = useState<OutlookEmail[]>([]);
  const [events, setEvents] = useState<OutlookCalendarEvent[]>([]);
  const [oauthUrl, setOAuthUrl] = useState<string>("");
  const [showDashboard, setShowDashboard] = useState(false);
  const toast = useToast();

  // Check connection status on mount
  useEffect(() => {
    checkConnectionStatus();
  }, [userId]);

  const checkConnectionStatus = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const response = await window.__TAURI__.invoke("check_outlook_tokens", {
          userId,
        });

        const valid = response.valid;
        const expired = response.expired;

        setStatus({
          connected: valid && !expired,
          error: response.message,
        });

        if (onConnectionChange) {
          onConnectionChange(valid && !expired);
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
        const response = await window.__TAURI__.invoke(
          "get_outlook_oauth_url",
          {
            userId,
          },
        );

        if (response.success) {
          setOAuthUrl(response.oauth_url);

          toast({
            title: "Outlook OAuth Started",
            description: "Please complete OAuth process in your browser",
            status: "info",
            duration: 5000,
          });
        } else {
          throw new Error("Failed to initiate OAuth");
        }
      } else {
        // Fallback to API
        const response = await fetch(
          `/api/oauth/outlook/url?user_id=${userId}`,
        );
        const data = await response.json();

        if (data.success) {
          window.open(data.oauth_url, "_blank");

          toast({
            title: "Outlook OAuth Started",
            description: "Please complete OAuth process in new window",
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

  const testOutlookConnection = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const response = await window.__TAURI__.invoke(
          "test_outlook_connection",
          {
            userId,
          },
        );

        if (response.success) {
          const mockEmails = response.emails || [];
          setEmails(mockEmails);
          setShowDashboard(true);

          toast({
            title: "Connection Test Successful",
            description: `Retrieved ${mockEmails.length} emails`,
            status: "success",
            duration: 3000,
          });
        } else {
          throw new Error("Connection test failed");
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
          setEmails(data.emails || []);
          setShowDashboard(true);

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

  const loadOutlookData = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const [emailsResponse, eventsResponse] = await Promise.all([
          window.__TAURI__.invoke("get_outlook_emails", { userId, limit: 10 }),
          window.__TAURI__.invoke("get_outlook_calendar_events", {
            userId,
            limit: 5,
          }),
        ]);

        setEmails(emailsResponse || []);
        setEvents(eventsResponse || []);
      }
    } catch (error) {
      console.error("Failed to load Outlook data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const disconnectOutlook = async () => {
    try {
      setIsLoading(true);

      if (window.__TAURI__) {
        const response = await window.__TAURI__.invoke("disconnect_outlook", {
          userId,
        });

        if (response.success) {
          setStatus({ connected: false });
          setEmails([]);
          setEvents([]);
          setShowDashboard(false);

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
          throw new Error("Failed to disconnect");
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
          setEmails([]);
          setEvents([]);
          setShowDashboard(false);

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

  const formatDateTime = (dateTimeStr: string) => {
    return new Date(dateTimeStr).toLocaleString();
  };

  return (
    <Box p={6} borderWidth={1} borderRadius="lg" bg="white">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Text fontSize="2xl">📧</Text>
            <Heading size="md" color="blue.600">
              Outlook Integration
            </Heading>
          </HStack>
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
            <Box flex={1}>
              <Text fontWeight="bold">
                Connected as {status.user.displayName}
              </Text>
              <Text fontSize="sm" color="gray.600">
                {status.user.mail}
                {status.user.jobTitle && ` • ${status.user.jobTitle}`}
                {status.user.officeLocation &&
                  ` • ${status.user.officeLocation}`}
              </Text>
            </Box>
            <Tooltip label="Refresh connection">
              <IconButton
                aria-label="Refresh"
                icon={<RefreshIcon />}
                size="sm"
                onClick={checkConnectionStatus}
                isLoading={isLoading}
              />
            </Tooltip>
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
            <HStack>
              <Spinner size="sm" />
              <Text>Processing...</Text>
            </HStack>
            <Progress size="sm" isIndeterminate />
          </Box>
        )}

        {/* Action Buttons */}
        {!status.connected ? (
          <VStack spacing={3}>
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
          </VStack>
        ) : (
          <VStack spacing={3}>
            <HStack>
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
                colorScheme="blue"
                onClick={loadOutlookData}
                isLoading={isLoading}
                width="full"
                size="lg"
              >
                Load Dashboard
              </Button>
            </HStack>

            <Button
              colorScheme="red"
              variant="outline"
              onClick={disconnectOutlook}
              isLoading={isLoading}
              width="full"
            >
              Disconnect Outlook
            </Button>
          </VStack>
        )}

        {/* OAuth URL Display */}
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

        {/* Dashboard View */}
        {showDashboard && status.connected && (
          <VStack spacing={6}>
            <Divider />
            <Heading size="sm" color="blue.600">
              Outlook Dashboard
            </Heading>

            <SimpleGrid columns={3} spacing={4}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Emails</StatLabel>
                    <StatNumber>{emails.length}</StatNumber>
                    <StatHelpText>Last 24 hours</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>

              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Unread Emails</StatLabel>
                    <StatNumber>
                      {emails.filter((e) => !e.isRead).length}
                    </StatNumber>
                    <StatHelpText>Requires attention</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>

              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Calendar Events</StatLabel>
                    <StatNumber>{events.length}</StatNumber>
                    <StatHelpText>Upcoming</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Recent Emails */}
            {emails.length > 0 && (
              <Box>
                <Heading size="sm" mb={4}>
                  Recent Emails
                </Heading>
                <Box overflowX="auto">
                  <Table size="sm">
                    <Thead>
                      <Tr>
                        <Th>Subject</Th>
                        <Th>From</Th>
                        <Th>Date</Th>
                        <Th>Status</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {emails.slice(0, 5).map((email) => (
                        <Tr key={email.id}>
                          <Td fontWeight="medium">{email.subject}</Td>
                          <Td>{email.from.name}</Td>
                          <Td>{formatDateTime(email.receivedDateTime)}</Td>
                          <Td>
                            {email.isRead ? (
                              <Badge colorScheme="green">Read</Badge>
                            ) : (
                              <Badge colorScheme="orange">Unread</Badge>
                            )}
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>
              </Box>
            )}

            {/* Calendar Events */}
            {events.length > 0 && (
              <Box>
                <Heading size="sm" mb={4}>
                  Upcoming Events
                </Heading>
                <VStack spacing={3} align="stretch">
                  {events.slice(0, 3).map((event) => (
                    <Box key={event.id} p={3} bg="gray.50" rounded="md">
                      <HStack justify="space-between">
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">{event.subject}</Text>
                          <Text fontSize="sm" color="gray.600">
                            {event.location || "No location"}
                          </Text>
                        </VStack>
                        <VStack align="end" spacing={1}>
                          <Text fontSize="sm" color="blue.600">
                            {formatDateTime(event.start.dateTime)}
                          </Text>
                          <Text fontSize="xs" color="gray.500">
                            to {formatDateTime(event.end.dateTime)}
                          </Text>
                        </VStack>
                      </HStack>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}
          </VStack>
        )}

        {/* Feature List */}
        <Box>
          <Text fontSize="sm" fontWeight="bold" mb={2}>
            Features Available:
          </Text>
          <SimpleGrid columns={2} spacing={2}>
            <Text fontSize="sm">📧 Send and receive emails</Text>
            <Text fontSize="sm">📅 Access calendar events</Text>
            <Text fontSize="sm">🔍 Search emails and calendar</Text>
            <Text fontSize="sm">🤖 Email and calendar automation</Text>
          </SimpleGrid>
        </Box>
      </VStack>
    </Box>
  );
};

export default OutlookDesktopManager;
