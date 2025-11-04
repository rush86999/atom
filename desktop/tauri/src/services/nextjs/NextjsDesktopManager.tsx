/**
 * Next.js Desktop Integration Service
 * Enhanced Next.js/Vercel management for desktop app
 */

import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { open } from '@tauri-apps/api/shell';
import { listen } from '@tauri-apps/api/event';
import { 
  Box, 
  VStack, 
  HStack, 
  Text, 
  Button, 
  Heading, 
  Badge,
  Card,
  CardBody,
  CardHeader,
  Alert,
  AlertIcon,
  Icon,
  useToast,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Checkbox,
  Divider,
  SimpleGrid,
  Progress,
  Stack,
  Switch,
  Select
} from '@chakra-ui/react';
import {
  CodeIcon,
  CheckCircleIcon,
  WarningIcon,
  ExternalLinkIcon,
  RocketIcon,
  BuildIcon,
  AnalyticsIcon,
  SettingsIcon,
  DesktopIcon,
  BellIcon,
  RepeatIcon,
  AddIcon,
  ViewIcon
} from '@chakra-ui/icons';

interface NextjsProject {
  id: string;
  name: string;
  framework: string;
  status: string;
  domains: string[];
  created_at: string;
  updated_at: string;
  build_status?: string;
  deployment_url?: string;
}

interface NextjsDesktopManagerProps {
  userId: string;
}

const NextjsDesktopManager: React.FC<NextjsDesktopManagerProps> = ({ userId }) => {
  const [projects, setProjects] = useState<NextjsProject[]>([]);
  const [health, setHealth] = useState<{ connected: boolean; error?: string }>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<NextjsProject | null>(null);
  const [showProjectDetails, setShowProjectDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState({ running: false, progress: 0 });
  const [settings, setSettings] = useState({
    enableNotifications: true,
    backgroundSync: true,
    realTimeSync: true,
    syncFrequency: 'realtime',
    maxProjects: 50
  });

  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Check Next.js service health
  const checkHealth = async () => {
    try {
      const result = await invoke('check_nextjs_health');
      setHealth(result);
    } catch (err) {
      console.error('Health check failed:', err);
      setHealth({ connected: false, error: 'Service unavailable' });
    }
  };

  // Load Next.js projects
  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await invoke('load_nextjs_projects', {
        userId,
        limit: settings.maxProjects
      });
      
      if (result.success) {
        setProjects(result.projects || []);
      } else {
        setError(result.error || 'Failed to load projects');
      }
    } catch (err) {
      setError('Failed to load Next.js projects');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Start OAuth flow
  const startOAuth = async () => {
    try {
      const result = await invoke('start_nextjs_oauth', {
        userId,
        scopes: ['read', 'write', 'projects', 'deployments', 'builds']
      });
      
      if (result.success) {
        // Open browser for OAuth
        await open(result.auth_url);
        
        // Show success message
        toast({
          title: 'OAuth Started',
          description: 'Please complete the authentication in your browser',
          status: 'info',
          duration: 5000,
        });
        
        // Poll for authentication completion
        setTimeout(() => {
          checkHealth();
          loadProjects();
        }, 5000);
      } else {
        throw new Error(result.error || 'OAuth initiation failed');
      }
    } catch (err) {
      toast({
        title: 'OAuth Failed',
        description: err instanceof Error ? err.message : 'Authentication failed',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Trigger deployment
  const triggerDeployment = async (projectId: string) => {
    try {
      const result = await invoke('trigger_nextjs_deployment', {
        userId,
        projectId,
        branch: 'main'
      });
      
      if (result.success) {
        toast({
          title: 'Deployment Triggered',
          description: 'Deployment started successfully',
          status: 'success',
          duration: 3000,
        });
        
        // Refresh projects
        loadProjects();
      } else {
        throw new Error(result.error || 'Deployment failed');
      }
    } catch (err) {
      toast({
        title: 'Deployment Failed',
        description: err instanceof Error ? err.message : 'Deployment failed',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Start data ingestion
  const startIngestion = async () => {
    setIngestionStatus({ running: true, progress: 0 });
    
    try {
      const result = await invoke('start_nextjs_ingestion', {
        userId,
        settings
      });
      
      if (result.success) {
        toast({
          title: 'Ingestion Started',
          description: 'Next.js data ingestion has begun',
          status: 'success',
          duration: 3000,
        });
      } else {
        throw new Error(result.error || 'Ingestion failed');
      }
    } catch (err) {
      toast({
        title: 'Ingestion Failed',
        description: err instanceof Error ? err.message : 'Ingestion failed',
        status: 'error',
        duration: 5000,
      });
      setIngestionStatus({ running: false, progress: 0 });
    }
  };

  // Handle project selection
  const handleProjectSelect = (project: NextjsProject) => {
    setSelectedProject(project);
    setShowProjectDetails(true);
  };

  // Update settings
  const updateSetting = (key: string, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  useEffect(() => {
    checkHealth();
    loadProjects();
    
    // Setup background monitoring
    if (settings.backgroundSync) {
      const interval = setInterval(() => {
        if (health.connected) {
          loadProjects();
        }
      }, 60000); // Every minute
      
      return () => clearInterval(interval);
    }
  }, [settings.backgroundSync, health.connected]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={CodeIcon} w={6} h={6} color="blue.500" />
            <Heading size="md">Next.js Integration</Heading>
            <Badge colorScheme="blue">Vercel</Badge>
            <Icon as={DesktopIcon} w={4} h={4} color="green.500" />
          </HStack>
          <HStack>
            <Badge
              colorScheme={health.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={health.connected ? CheckCircleIcon : WarningIcon} mr={1} />
              {health.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={() => {
                checkHealth();
                loadProjects();
              }}
              isLoading={loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Authentication */}
          {!health.connected && (
            <VStack>
              <Button
                colorScheme="blue"
                leftIcon={<CodeIcon />}
                onClick={startOAuth}
                width="full"
                size="lg"
              >
                Connect to Next.js/Vercel
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Connect your Vercel account to manage Next.js projects in the desktop app
              </Text>
            </VStack>
          )}

          {/* Health Status */}
          {health.error && (
            <Alert status="error">
              <AlertIcon />
              <Text>{health.error}</Text>
            </Alert>
          )}

          {/* Projects Grid */}
          {projects.length > 0 && (
            <VStack align="stretch">
              <HStack justify="space-between">
                <Text fontWeight="bold" fontSize="lg">
                  Projects ({projects.length})
                </Text>
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() => open('https://vercel.com/dashboard')}
                >
                  Open Vercel
                </Button>
              </HStack>

              <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                {projects.map((project) => (
                  <Card 
                    key={project.id} 
                    cursor="pointer" 
                    onClick={() => handleProjectSelect(project)}
                    _hover={{ shadow: 'md' }}
                  >
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <HStack justify="space-between" w="full">
                          <Badge
                            colorScheme={
                              project.status === 'ready' ? 'green' :
                              project.status === 'building' ? 'blue' : 'red'
                            }
                          >
                            {project.status}
                          </Badge>
                          {project.build_status && (
                            <Badge size="sm" colorScheme="orange">
                              {project.build_status}
                            </Badge>
                          )}
                        </HStack>
                        
                        <HStack>
                          <Icon as={CodeIcon} color="blue.500" />
                          <Text fontWeight="bold" noOfLines={1}>
                            {project.name}
                          </Text>
                        </HStack>
                        
                        <Text fontSize="sm" color="gray.600">
                          {project.framework}
                        </Text>

                        {project.domains.length > 0 && (
                          <Text fontSize="xs" color="gray.500" noOfLines={1}>
                            {project.domains[0]}
                          </Text>
                        )}

                        <Text fontSize="xs" color="gray.500">
                          Updated {new Date(project.updated_at).toLocaleDateString()}
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
            </VStack>
          )}

          <Divider />

          {/* Settings */}
          <VStack align="start" spacing={4}>
            <Text fontWeight="bold">Desktop Settings</Text>
            <VStack align="start" spacing={3} pl={4}>
              <HStack>
                <Checkbox
                  isChecked={settings.enableNotifications}
                  onChange={(e) => updateSetting('enableNotifications', e.target.checked)}
                >
                  Enable Desktop Notifications
                </Checkbox>
                <BellIcon />
              </HStack>
              
              <HStack>
                <Checkbox
                  isChecked={settings.backgroundSync}
                  onChange={(e) => updateSetting('backgroundSync', e.target.checked)}
                >
                  Enable Background Sync
                </Checkbox>
                <RepeatIcon />
              </HStack>
              
              <Checkbox
                isChecked={settings.realTimeSync}
                onChange={(e) => updateSetting('realTimeSync', e.target.checked)}
              >
                Enable Real-time Sync
              </Checkbox>
              
              <FormControl>
                <FormLabel>Sync Frequency</FormLabel>
                <Select
                  value={settings.syncFrequency}
                  onChange={(e) => updateSetting('syncFrequency', e.target.value)}
                  w="200px"
                >
                  <option value="realtime">Real-time</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>Max Projects</FormLabel>
                <Input
                  type="number"
                  value={settings.maxProjects}
                  onChange={(e) => updateSetting('maxProjects', parseInt(e.target.value))}
                  w="200px"
                />
              </FormControl>
            </VStack>
          </VStack>

          {/* Action Buttons */}
          <HStack justify="space-between" w="full">
            <Button
              variant="outline"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => open('https://vercel.com/dashboard')}
            >
              Open Vercel
            </Button>

            <Button
              colorScheme="green"
              leftIcon={<RocketIcon />}
              onClick={startIngestion}
              isDisabled={!health.connected || projects.length === 0 || ingestionStatus.running}
              isLoading={ingestionStatus.running}
            >
              {ingestionStatus.running ? 'Ingesting...' : 'Start Data Ingestion'}
            </Button>
          </HStack>

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting Next.js data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Desktop sync running in background
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          )}
        </VStack>
      </CardBody>

      {/* Project Details Modal */}
      <Modal
        isOpen={showProjectDetails}
        onClose={() => setShowProjectDetails(false)}
        size="xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <Icon as={CodeIcon} color="blue.500" />
              <Text>{selectedProject?.name}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedProject && (
              <VStack spacing={4} align="start">
                <Text>
                  <strong>Status:</strong> {selectedProject.status}
                </Text>
                <Text>
                  <strong>Framework:</strong> {selectedProject.framework}
                </Text>
                <Text>
                  <strong>Created:</strong> {new Date(selectedProject.created_at).toLocaleDateString()}
                </Text>
                <Text>
                  <strong>Updated:</strong> {new Date(selectedProject.updated_at).toLocaleDateString()}
                </Text>
                
                {selectedProject.domains.length > 0 && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Domains:</Text>
                    <VStack align="start">
                      {selectedProject.domains.map((domain, index) => (
                        <Text
                          key={index}
                          color="blue.600"
                          cursor="pointer"
                          onClick={() => open(`https://${domain}`)}
                        >
                          {domain}
                        </Text>
                      ))}
                    </VStack>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button
              colorScheme="blue"
              onClick={() => {
                if (selectedProject?.deployment_url) {
                  open(selectedProject.deployment_url);
                }
              }}
            >
              View Live Site
            </Button>
            <Button
              colorScheme="green"
              onClick={() => {
                if (selectedProject) {
                  triggerDeployment(selectedProject.id);
                }
              }}
              mr={3}
            >
              Deploy Project
            </Button>
            <Button onClick={() => setShowProjectDetails(false)}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Card>
  );
};

export default NextjsDesktopManager;