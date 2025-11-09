import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Text,
  Button,
  VStack,
  HStack,
  Spinner,
  Alert,
  AlertIcon,
  Badge,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  useDisclosure,
  useToast,
  Icon,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Avatar,
  Divider,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  SimpleGrid,
  Flex,
  Spacer
} from "@chakra-ui/react";
import {
  FaDiscord,
  FaPlug,
  FaUnlink,
  FaSync,
  FaServer,
  FaUsers,
  FaChartBar,
  FaCog,
  FaUserFriends,
  FaHashtag,
  FaEnvelope,
  FaBell,
  FaShieldAlt
} from "react-icons/fa";

const DiscordIntegration = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState({
    connect: false,
    data: false,
    save: false
  });
  const [integrationData, setIntegrationData] = useState({
    profile: null,
    guilds: [],
    channels: [],
    messages: [],
    analytics: null
  });
  const [selectedTab, setSelectedTab] = useState(0);
  
  const { isOpen: isConfigOpen, onOpen: onConfigOpen, onClose: onConfigClose } = useDisclosure();
  const toast = useToast();

  // Check connection status
  const checkConnectionStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/integrations/discord/health");
      const data = await response.json();
      
      setIsConnected(data.success);
    } catch (error) {
      console.error("Connection check failed:", error);
      setIsConnected(false);
    }
  }, []);

  // Load integration data
  const loadIntegrationData = useCallback(async () => {
    if (!isConnected) return;
    
    setLoading(prev => ({ ...prev, data: true }));
    
    try {
      const [profileResponse, guildsResponse] = await Promise.all([
        fetch("/api/integrations/discord/profile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: "current" })
        }),
        fetch("/api/integrations/discord/guilds", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: "current" })
        })
      ]);

      const [profileData, guildsData] = await Promise.all([
        profileResponse.json(),
        guildsResponse.json()
      ]);

      setIntegrationData({
        profile: profileData.success ? profileData.data : null,
        guilds: guildsData.success ? guildsData.data : [],
        channels: [],
        messages: [],
        analytics: null
      });
      
    } catch (error) {
      console.error("Failed to load integration data:", error);
      toast({
        title: "Failed to load data",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(prev => ({ ...prev, data: false }));
    }
  }, [isConnected, toast]);

  // Connect integration
  const connectIntegration = useCallback(async () => {
    setLoading(prev => ({ ...prev, connect: true }));
    
    try {
      const response = await fetch("/api/integrations/discord/auth/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "current" })
      });
      
      const data = await response.json();
      
      if (data.success) {
        window.location.href = data.authorization_url;
      } else {
        toast({
          title: "Connection failed",
          description: data.error,
          status: "error",
          duration: 3000,
        });
      }
    } catch (error) {
      console.error("Connection failed:", error);
      toast({
        title: "Connection failed",
        description: "An error occurred while connecting",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(prev => ({ ...prev, connect: false }));
    }
  }, [toast]);

  // Disconnect integration
  const disconnectIntegration = useCallback(async () => {
    try {
      const response = await fetch("/api/integrations/discord/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "current" })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setIsConnected(false);
        setIntegrationData({
          profile: null,
          guilds: [],
          channels: [],
          messages: [],
          analytics: null
        });
        toast({
          title: "Disconnected successfully",
          status: "success",
          duration: 3000,
        });
      }
    } catch (error) {
      console.error("Disconnection failed:", error);
      toast({
        title: "Disconnection failed",
        description: "An error occurred while disconnecting",
        status: "error",
        duration: 3000,
      });
    }
  }, [toast]);

  useEffect(() => {
    checkConnectionStatus();
  }, [checkConnectionStatus]);

  useEffect(() => {
    if (isConnected) {
      loadIntegrationData();
    }
  }, [isConnected, loadIntegrationData]);

  return (
    <Box p={6} maxW="1200px" mx="auto">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={4}>
            <Icon as={FaDiscord} w={10} h={10} color="#5865F2" />
            <Box>
              <Heading size="lg" color="gray.800">Discord Integration</Heading>
              <Text color="gray.600" fontSize="sm">
                Real-time communication and community platform
              </Text>
            </Box>
          </HStack>
          
          <HStack spacing={4}>
            <Badge
              colorScheme={isConnected ? "green" : "red"}
              variant="subtle"
              fontSize="sm"
              px={3}
              py={1}
            >
              {isConnected ? "Connected" : "Not Connected"}
            </Badge>
            
            {!isConnected ? (
              <Button
                colorScheme="discord"
                leftIcon={<FaPlug />}
                onClick={connectIntegration}
                isLoading={loading.connect}
              >
                Connect Discord
              </Button>
            ) : (
              <Button
                colorScheme="red"
                variant="outline"
                leftIcon={<FaUnlink />}
                onClick={disconnectIntegration}
              >
                Disconnect
              </Button>
            )}
            
            <Button
              leftIcon={<FaSync />}
              onClick={() => {
                checkConnectionStatus();
                loadIntegrationData();
              }}
              isLoading={loading.data}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>

        {isConnected ? (
          <>
            {/* Profile Card */}
            {integrationData.profile && (
              <Card>
                <CardHeader>
                  <HStack spacing={4}>
                    <Avatar
                      size="lg"
                      src={integrationData.profile.avatar_url}
                      name={integrationData.profile.username}
                    />
                    <Box>
                      <Heading size="md">{integrationData.profile.username}</Heading>
                      <Text color="gray.600">{integrationData.profile.discriminator}</Text>
                      <HStack spacing={4} mt={2}>
                        <Badge colorScheme="blue">
                          <FaUsers /> {integrationData.profile.servers_count} Servers
                        </Badge>
                        <Badge colorScheme="green">
                          <FaHashtag /> {integrationData.profile.channels_count} Channels
                        </Badge>
                      </HStack>
                    </Box>
                    <Spacer />
                    <Button variant="ghost" size="sm">
                      <FaCog />
                    </Button>
                  </HStack>
                </CardHeader>
              </Card>
            )}

            {/* Tabs */}
            <Tabs onChange={setSelectedTab} index={selectedTab}>
              <TabList>
                <Tab>
                  <HStack spacing={2}>
                    <Icon as={FaServer} />
                    <Text>Servers</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack spacing={2}>
                    <Icon as={FaHashtag} />
                    <Text>Channels</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack spacing={2}>
                    <Icon as={FaChartBar} />
                    <Text>Analytics</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack spacing={2}>
                    <Icon as={FaBell} />
                    <Text>Notifications</Text>
                  </HStack>
                </Tab>
              </TabList>

              <TabPanels>
                {/* Servers Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Heading size="md">Discord Servers</Heading>
                    
                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {integrationData.guilds.map((guild) => (
                        <Card key={guild.id} variant="outline">
                          <CardBody>
                            <HStack spacing={4}>
                              <Avatar
                                size="md"
                                src={guild.icon_url}
                                name={guild.name}
                              />
                              <VStack align="start" spacing={1}>
                                <Heading size="sm">{guild.name}</Heading>
                                <Text fontSize="xs" color="gray.500">
                                  {guild.member_count} members • {guild.channel_count} channels
                                </Text>
                                {guild.owner && (
                                  <Badge colorScheme="purple" variant="subtle" fontSize="xs">
                                    Owner
                                  </Badge>
                                )}
                              </VStack>
                            </HStack>
                          </CardBody>
                        </Card>
                      ))}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Channels Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info">
                      <AlertIcon />
                      Channel management coming soon
                    </Alert>
                  </VStack>
                </TabPanel>

                {/* Analytics Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Heading size="md">Discord Analytics</Heading>
                    
                    <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
                      <Stat>
                        <StatLabel>Total Servers</StatLabel>
                        <StatNumber>{integrationData.guilds.length}</StatNumber>
                        <StatHelpText>Connected servers</StatHelpText>
                      </Stat>
                      
                      <Stat>
                        <StatLabel>Active Channels</StatLabel>
                        <StatNumber>0</StatNumber>
                        <StatHelpText>Text & voice channels</StatHelpText>
                      </Stat>
                      
                      <Stat>
                        <StatLabel>Messages Today</StatLabel>
                        <StatNumber>0</StatNumber>
                        <StatHelpText>Messages sent</StatHelpText>
                      </Stat>
                      
                      <Stat>
                        <StatLabel>Active Users</StatLabel>
                        <StatNumber>0</StatNumber>
                        <StatHelpText>Users online</StatHelpText>
                      </Stat>
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Notifications Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info">
                      <AlertIcon />
                      Notification management coming soon
                    </Alert>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </>
        ) : (
          <Alert status="warning">
            <AlertIcon />
            <VStack align="start" spacing={2}>
              <Text fontWeight="medium">Discord not connected</Text>
              <Text fontSize="sm">
                Connect your Discord account to access servers, channels, and real-time communication features.
              </Text>
              <Button
                colorScheme="discord"
                leftIcon={<FaPlug />}
                onClick={connectIntegration}
                mt={2}
              >
                Connect Discord
              </Button>
            </VStack>
          </Alert>
        )}
      </VStack>
    </Box>
  );
};

export default DiscordIntegration;
