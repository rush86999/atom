import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  List,
  ListItem,
  Badge,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Input,
  FormControl,
  FormLabel,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Divider,
  SimpleGrid,
  Card,
  CardHeader,
  CardBody,
  Icon
} from '@chakra-ui/react';
import { SearchIcon, PlusIcon, DatabaseIcon, DocumentIcon, CheckCircleIcon, XCircleIcon, RefreshCwIcon } from 'lucide-react';
import { notionSkills } from '../../../skills/notionSkills';
import { SkillContext } from '../../../types';

interface NotionSkillsProps {
  userId: string;
  onClose: () => void;
}

export const NotionSkills: React.FC<NotionSkillsProps> = ({ userId, onClose }) => {
  const [isExecuting, setIsExecuting] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCommandModal, setShowCommandModal] = useState(false);
  const [selectedCommand, setSelectedCommand] = useState<any>(null);
  const [commandInput, setCommandInput] = useState('');
  const [notionConnected, setNotionConnected] = useState<boolean>(false);
  const [notionStatus, setNotionStatus] = useState<any>(null);
  const toast = useToast();

  // Check Notion connection status
  useEffect(() => {
    checkNotionStatus();
  }, [userId]);

  const checkNotionStatus = async () => {
    try {
      const response = await fetch('/api/real/notion/health', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();
      setNotionStatus(data);
      setNotionConnected(data.success && data.api_connected);
    } catch (error) {
      console.error('Error checking Notion status:', error);
      setNotionConnected(false);
    }
  };

  // Skill categories
  const skillCategories = [
    {
      name: 'Pages',
      description: 'Create, read, update, and delete Notion pages',
      icon: DocumentIcon,
      skills: notionSkills.filter(skill => 
        skill.id.includes('page') || skill.id.includes('create') || skill.id.includes('update')
      )
    },
    {
      name: 'Databases',
      description: 'Query and manage Notion databases',
      icon: DatabaseIcon,
      skills: notionSkills.filter(skill => 
        skill.id.includes('database') || skill.id.includes('query')
      )
    },
    {
      name: 'Search',
      description: 'Search across pages and databases',
      icon: SearchIcon,
      skills: notionSkills.filter(skill => 
        skill.id.includes('search')
      )
    }
  ];

  // Execute skill
  const executeSkill = async (skill: any, params?: any) => {
    setIsExecuting(skill.id);
    setResults(null);

    try {
      const context: SkillContext = {
        userId,
        sessionId: `notion-${Date.now()}`,
        timestamp: new Date().toISOString(),
      };

      const skillParams = params || {};
      
      // Add search query if provided
      if (searchQuery && skill.id.includes('search')) {
        skillParams.query = searchQuery;
      }

      const result = await skill.execute(skillParams, context);

      if (result.success) {
        setResults(result.data);
        toast({
          title: 'Success',
          description: result.message || 'Skill executed successfully',
          status: 'success',
          duration: 3000,
        });
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Skill execution failed',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error executing skill:', error);
      toast({
        title: 'Error',
        description: 'An unexpected error occurred',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsExecuting(null);
    }
  };

  // Execute natural language command
  const executeCommand = async () => {
    if (!commandInput.trim()) return;

    setIsExecuting('command');
    setResults(null);

    try {
      const context: SkillContext = {
        userId,
        sessionId: `notion-command-${Date.now()}`,
        timestamp: new Date().toISOString(),
      };

      // Find matching skill based on command
      let matchingSkill = null;
      let params = { query: commandInput };

      if (commandInput.toLowerCase().includes('search')) {
        matchingSkill = notionSkills.find(skill => skill.id === 'notion_search_pages');
      } else if (commandInput.toLowerCase().includes('database')) {
        matchingSkill = notionSkills.find(skill => skill.id === 'notion_list_databases');
      } else if (commandInput.toLowerCase().includes('page') && commandInput.toLowerCase().includes('create')) {
        matchingSkill = notionSkills.find(skill => skill.id === 'notion_create_page');
        params.title = commandInput.replace(/create page|new page/gi, '').trim();
      } else if (commandInput.toLowerCase().includes('workspace')) {
        matchingSkill = notionSkills.find(skill => skill.id === 'notion_get_workspaces');
      }

      if (matchingSkill) {
        const result = await matchingSkill.execute(params, context);

        if (result.success) {
          setResults(result.data);
          toast({
            title: 'Command Executed',
            description: result.message || 'Command completed successfully',
            status: 'success',
            duration: 3000,
          });
        } else {
          toast({
            title: 'Command Failed',
            description: result.error || 'Command execution failed',
            status: 'error',
            duration: 5000,
          });
        }
      } else {
        toast({
          title: 'Command Not Recognized',
          description: 'Try: "search [query]", "list databases", "create page [title]"',
          status: 'warning',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error executing command:', error);
      toast({
        title: 'Error',
        description: 'An unexpected error occurred',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsExecuting(null);
      setCommandInput('');
      setShowCommandModal(false);
    }
  };

  // Render connection status
  const renderConnectionStatus = () => {
    if (!notionStatus) {
      return (
        <Alert status="info">
          <AlertIcon as={RefreshCwIcon} />
          <AlertTitle>Checking Notion Connection</AlertTitle>
        </Alert>
      );
    }

    if (notionConnected) {
      return (
        <Alert status="success">
          <AlertIcon as={CheckCircleIcon} />
          <AlertTitle>Notion Connected</AlertTitle>
          <AlertDescription>
            Your Notion workspace is connected and ready for use.
          </AlertDescription>
        </Alert>
      );
    } else {
      return (
        <Alert status="error">
          <AlertIcon as={XCircleIcon} />
          <AlertTitle>Notion Not Connected</AlertTitle>
          <AlertDescription>
            Please connect your Notion account to use these skills.
          </AlertDescription>
        </Alert>
      );
    }
  };

  return (
    <VStack spacing={6} align="stretch">
      {/* Connection Status */}
      <Box>
        <Heading size="md" mb={4}>Notion Integration</Heading>
        {renderConnectionStatus()}
        
        {!notionConnected && (
          <Button
            colorScheme="blue"
            onClick={() => window.open('/api/auth/notion/authorize?user_id=' + userId, '_blank')}
            mt={4}
          >
            Connect Notion Account
          </Button>
        )}
      </Box>

      {notionConnected && (
        <>
          {/* Quick Actions */}
          <SimpleGrid columns={3} spacing={4}>
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <Icon as={SearchIcon} boxSize={6} color="blue.500" />
                  <Text fontSize="sm" fontWeight="medium">Search</Text>
                  <Input
                    placeholder="Search pages..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && searchQuery.trim()) {
                        executeSkill(notionSkills.find(s => s.id === 'notion_search_pages'));
                      }
                    }}
                  />
                </VStack>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <Icon as={DatabaseIcon} boxSize={6} color="green.500" />
                  <Text fontSize="sm" fontWeight="medium">Databases</Text>
                  <Button
                    colorScheme="green"
                    onClick={() => executeSkill(notionSkills.find(s => s.id === 'notion_list_databases'))}
                    isLoading={isExecuting === 'notion_list_databases'}
                  >
                    List Databases
                  </Button>
                </VStack>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <Icon as={PlusIcon} boxSize={6} color="purple.500" />
                  <Text fontSize="sm" fontWeight="medium">Create</Text>
                  <Button
                    colorScheme="purple"
                    onClick={() => setShowCommandModal(true)}
                  >
                    Create Page
                  </Button>
                </VStack>
              </CardBody>
            </Card>
          </SimpleGrid>

          {/* Natural Language Command */}
          <Box>
            <Heading size="sm" mb={3}>Natural Language Commands</Heading>
            <HStack spacing={2}>
              <Input
                placeholder="Try: 'search meeting notes', 'list databases', 'create page Project Plan'"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && commandInput.trim()) {
                    executeCommand();
                  }
                }}
                flex={1}
              />
              <Button
                colorScheme="blue"
                onClick={executeCommand}
                isLoading={isExecuting === 'command'}
                isDisabled={!commandInput.trim()}
              >
                Execute
              </Button>
            </HStack>
          </Box>

          {/* Skill Categories */}
          <Divider />
          <Box>
            <Heading size="sm" mb={4}>Available Skills</Heading>
            <SimpleGrid columns={1} spacing={4}>
              {skillCategories.map((category) => (
                <Card key={category.name}>
                  <CardHeader>
                    <HStack spacing={3}>
                      <Icon as={category.icon} boxSize={5} />
                      <Heading size="sm">{category.name}</Heading>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <Text fontSize="sm" color="gray.600" mb={3}>
                      {category.description}
                    </Text>
                    <VStack spacing={2} align="stretch">
                      {category.skills.map((skill) => (
                        <Button
                          key={skill.id}
                          variant="outline"
                          size="sm"
                          onClick={() => executeSkill(skill)}
                          isLoading={isExecuting === skill.id}
                          justifyContent="flex-start"
                        >
                          {skill.name}
                        </Button>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </SimpleGrid>
          </Box>

          {/* Results Display */}
          {results && (
            <Box>
              <Heading size="sm" mb={3}>Results</Heading>
              <Box 
                bg="gray.50" 
                p={4} 
                borderRadius="md" 
                maxHeight="400px" 
                overflowY="auto"
              >
                <pre style={{ fontSize: '12px', margin: 0 }}>
                  {JSON.stringify(results, null, 2)}
                </pre>
              </Box>
            </Box>
          )}
        </>
      )}

      {/* Create Page Modal */}
      <Modal 
        isOpen={showCommandModal} 
        onClose={() => setShowCommandModal(false)}
        size="lg"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create New Page</ModalHeader>
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Page Title</FormLabel>
                <Input
                  placeholder="Enter page title..."
                  value={commandInput}
                  onChange={(e) => setCommandInput(e.target.value)}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setShowCommandModal(false)}
            >
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={() => {
                const createSkill = notionSkills.find(s => s.id === 'notion_create_page');
                executeSkill(createSkill, { title: commandInput });
                setShowCommandModal(false);
                setCommandInput('');
              }}
              isLoading={isExecuting === 'notion_create_page'}
              isDisabled={!commandInput.trim()}
            >
              Create Page
            </Button>
          </ModalFooter>
          <ModalCloseButton />
        </ModalContent>
      </Modal>

      {/* Loading Spinner */}
      {isExecuting && (
        <Box
          position="fixed"
          top="50%"
          left="50%"
          transform="translate(-50%, -50%)"
          bg="white"
          p={4}
          borderRadius="md"
          boxShadow="lg"
          zIndex={9999}
        >
          <VStack spacing={3} align="center">
            <Spinner size="xl" color="blue.500" />
            <Text>Executing...</Text>
          </VStack>
        </Box>
      )}
    </VStack>
  );
};

export default NotionSkills;