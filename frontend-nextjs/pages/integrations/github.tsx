import React from "react";
import { Box, VStack, Heading, Text } from "@chakra-ui/react";
import GitHubIntegration from "../../../src/ui-shared/integrations/github/components/GitHubIntegration";

const GitHubIntegrationPage: React.FC = () => {
  return (
    <Box minH="100vh" bg="white" p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        <VStack align="start" spacing={2}>
          <Heading size="2xl">GitHub Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete repository and project management platform
          </Text>
        </VStack>

        <GitHubIntegration />
      </VStack>
    </Box>
  );
};

export default GitHubIntegrationPage;
// Enhance existing GitHub frontend with enterprise features
// This will be appended to the existing github.tsx file

const GitHubEnhancedFeatures = ({ isConnected, integrationData, toast }) => {
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repoDetails, setRepoDetails] = useState(null);
  const [pullRequests, setPullRequests] = useState([]);
  const [issues, setIssues] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const { isOpen: isRepoOpen, onOpen: onRepoOpen, onClose: onRepoClose } = useDisclosure();
  const { isOpen: isAnalyticsOpen, onOpen: onAnalyticsOpen, onClose: onAnalyticsClose } = useDisclosure();

  // Load repository details
  const loadRepositoryDetails = useCallback(async (owner, repo) => {
    try {
      const response = await fetch("/api/integrations/github/repo/details", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repo, user_id: "current" })
      });
      
      const data = await response.json();
      if (data.success) {
        setRepoDetails(data.data);
      }
    } catch (error) {
      console.error("Failed to load repository details:", error);
      toast({
        title: "Failed to load repository details",
        status: "error",
        duration: 3000,
      });
    }
  }, [toast]);

  // Load pull requests
  const loadPullRequests = useCallback(async (owner, repo) => {
    try {
      const response = await fetch("/api/integrations/github/pull-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repo, state: "open", user_id: "current" })
      });
      
      const data = await response.json();
      if (data.success) {
        setPullRequests(data.data);
      }
    } catch (error) {
      console.error("Failed to load pull requests:", error);
    }
  }, []);

  // Load issues
  const loadIssues = useCallback(async (owner, repo) => {
    try {
      const response = await fetch("/api/integrations/github/issues", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repo, state: "open", user_id: "current" })
      });
      
      const data = await response.json();
      if (data.success) {
        setIssues(data.data);
      }
    } catch (error) {
      console.error("Failed to load issues:", error);
    }
  }, []);

  // Load analytics
  const loadAnalytics = useCallback(async (owner, repo) => {
    try {
      const response = await fetch("/api/integrations/github/analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner, repo, user_id: "current" })
      });
      
      const data = await response.json();
      if (data.success) {
        setAnalytics(data.data);
      }
    } catch (error) {
      console.error("Failed to load analytics:", error);
    }
  }, []);

  return (
    <>
      {/* Repository Details Modal */}
      <Modal isOpen={isRepoOpen} onClose={onRepoClose} size="4xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Repository Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {repoDetails && (
              <VStack spacing={6}>
                <HStack spacing={4}>
                  <Avatar
                    src={repoDetails.owner.avatar_url}
                    name={repoDetails.owner.login}
                    size="lg"
                  />
                  <Box>
                    <Heading size="lg">{repoDetails.full_name}</Heading>
                    <Text color="gray.600">{repoDetails.description}</Text>
                    <HStack spacing={4} mt={2}>
                      <Badge colorScheme={repoDetails.private ? "red" : "green"}>
                        {repoDetails.private ? "Private" : "Public"}
                      </Badge>
                      <Badge colorScheme="blue">
                        <FaCode /> {repoDetails.language}
                      </Badge>
                      <Badge colorScheme="purple">
                        <FaStar /> {repoDetails.stargazers_count}
                      </Badge>
                    </HStack>
                  </Box>
                </HStack>

                {/* Languages */}
                {Object.keys(repoDetails.languages).length > 0 && (
                  <Box>
                    <Heading size="md" mb={4}>Languages</Heading>
                    <HStack spacing={4} wrap="wrap">
                      {Object.entries(repoDetails.languages).map(([lang, bytes]) => (
                        <Badge key={lang} colorScheme="blue" variant="subtle">
                          {lang} {Math.round(bytes / 1024)}KB
                        </Badge>
                      ))}
                    </HStack>
                  </Box>
                )}

                {/* Stats */}
                <SimpleGrid columns={{ base: 2, md: 4 }} spacing={6}>
                  <Stat>
                    <StatLabel>Stars</StatLabel>
                    <StatNumber>{repoDetails.stargazers_count}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Forks</StatLabel>
                    <StatNumber>{repoDetails.forks_count}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Issues</StatLabel>
                    <StatNumber>{repoDetails.open_issues_count}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Contributors</StatLabel>
                    <StatNumber>{repoDetails.contributors_count}</StatNumber>
                  </Stat>
                </SimpleGrid>

                {/* Top Contributors */}
                <Box>
                  <Heading size="md" mb={4}>Top Contributors</Heading>
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                    {repoDetails.top_contributors.map((contributor) => (
                      <HStack key={contributor.login} spacing={3}>
                        <Avatar
                          src={contributor.avatar_url}
                          name={contributor.login}
                          size="sm"
                        />
                        <Box>
                          <Text fontWeight="medium">{contributor.login}</Text>
                          <Text fontSize="xs" color="gray.500">
                            {contributor.contributions} contributions
                          </Text>
                        </Box>
                      </HStack>
                    ))}
                  </SimpleGrid>
                </Box>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={onRepoClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
};

export default GitHubIntegration;
