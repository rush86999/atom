/**
 * ATOM OneDrive Manager Component
 * High-level management interface for OneDrive integration
 * Provides centralized control over OneDrive operations and ATOM synchronization
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardHeader,
  CardBody,
  Progress,
  Alert,
  AlertIcon,
  Badge,
  Icon,
  useColorModeValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Divider,
  FormControl,
  FormLabel,
  Switch,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Input,
  Textarea,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  List,
  ListItem,
  ListIcon,
  IconButton,
  Tooltip,
  Spinner,
  Center,
  Stack,
  Flex,
  Spacer,
} from '@chakra-ui/react';
import {
  FiCloud,
  FiFolder,
  FiFile,
  FiRefreshCw,
  FiDownload,
  FiUpload,
  FiSettings,
  FiDatabase,
  FiZap,
  FiClock,
  FiHardDrive,
  FiActivity,
  FiCpu,
  FiShield,
  FiCheck,
  FiX,
  FiAlertTriangle,
  FiTrendingUp,
  FiUsers,
  FiSearch,
  FiFilter,
  FiGrid,
  FiList,
  FiPlay,
  FiPause,
  FiStop,
  FiEdit,
  FiTrash2,
  FiCopy,
  FiExternalLink,
} from 'react-icons/fi';

import { OneDriveIntegration } from '../OneDriveIntegration';
import { OneDriveSkillsBundle } from '../skills/oneDriveSkills';
import {
  AtomOneDriveIngestionConfig,
  OneDriveFile,
  OneDriveFolder,
  ONEDRIVE_DEFAULT_CONFIG,
} from '../types';

interface AtomOneDriveManagerProps {
  // Authentication
  accessToken: string;
  refreshToken?: string;
  onTokenRefresh?: (newToken: string) => void;
  tenantId?: string;
  
  // ATOM Integration
  atomIngestionPipeline?: any;
  atomSkillRegistry?: any;
  atomOrchestrationEngine?: any;
  
  // Configuration
  initialConfig?: Partial<AtomOneDriveIngestionConfig>;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  
  // Events
  onReady?: (manager: AtomOneDriveManager) => void;
  onError?: (error: any) => void;
  onSyncStart?: (config: any) => void;
  onSyncComplete?: (results: any) => void;
  onSyncProgress?: (progress: any) => void;
}

interface SyncSession {
  id: string;
  startTime: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  config: AtomOneDriveIngestionConfig;
  progress: {
    total: number;
    processed: number;
    percentage: number;
    currentFile?: string;
    errors: number;
  };
  results?: any;
}

interface OneDriveStats {
  totalFiles: number;
  totalFolders: number;
  totalSize: number;
  lastSync: string | null;
  syncSessions: SyncSession[];
  activeConnections: number;
  processedByAtom: number;
  averageProcessingTime: number;
  errorRate: number;
}

export class AtomOneDriveManager {
  private config: AtomOneDriveIngestionConfig;
  private stats: OneDriveStats;
  private currentSyncSession: SyncSession | null = null;
  private syncHistory: SyncSession[] = [];
  private atomIngestionPipeline: any;
  private atomSkillRegistry: any;
  private listeners: Map<string, Function[]> = new Map();

  constructor(
    private accessToken: string,
    private options: AtomOneDriveManagerProps = {}
  ) {
    this.config = { ...ONEDRIVE_DEFAULT_CONFIG, ...options.initialConfig };
    this.atomIngestionPipeline = options.atomIngestionPipeline;
    this.atomSkillRegistry = options.atomSkillRegistry;
    
    this.stats = {
      totalFiles: 0,
      totalFolders: 0,
      totalSize: 0,
      lastSync: null,
      syncSessions: [],
      activeConnections: 0,
      processedByAtom: 0,
      averageProcessingTime: 0,
      errorRate: 0,
    };

    this.initializeSkills();
  }

  // Initialize OneDrive skills in ATOM registry
  private initializeSkills() {
    if (this.atomSkillRegistry) {
      this.atomSkillRegistry.registerSkills(OneDriveSkillsBundle.skills);
    }
  }

  // Event management
  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(callback => callback(data));
  }

  // Configuration management
  updateConfig(newConfig: Partial<AtomOneDriveIngestionConfig>) {
    this.config = { ...this.config, ...newConfig };
    this.emit('configUpdated', this.config);
  }

  getConfig(): AtomOneDriveIngestionConfig {
    return { ...this.config };
  }

  // Sync management
  async startSync(syncConfig?: Partial<AtomOneDriveIngestionConfig>) {
    const config = syncConfig ? { ...this.config, ...syncConfig } : this.config;
    
    const sessionId = `sync_${Date.now()}`;
    const session: SyncSession = {
      id: sessionId,
      startTime: new Date().toISOString(),
      status: 'running',
      config,
      progress: {
        total: 0,
        processed: 0,
        percentage: 0,
        errors: 0,
      },
    };

    this.currentSyncSession = session;
    this.syncHistory.push(session);
    this.emit('syncStart', session);

    try {
      // Implementation would go here
      // For now, simulate the sync process
      await this.simulateSync(session);
      
      session.status = 'completed';
      this.stats.lastSync = new Date().toISOString();
      this.emit('syncComplete', session);
      
    } catch (error) {
      session.status = 'failed';
      this.emit('syncError', { session, error });
    }

    this.currentSyncSession = null;
    return session;
  }

  pauseSync() {
    if (this.currentSyncSession) {
      this.currentSyncSession.status = 'paused';
      this.emit('syncPaused', this.currentSyncSession);
    }
  }

  resumeSync() {
    if (this.currentSyncSession) {
      this.currentSyncSession.status = 'running';
      this.emit('syncResumed', this.currentSyncSession);
    }
  }

  stopSync() {
    if (this.currentSyncSession) {
      this.currentSyncSession.status = 'failed';
      this.emit('syncStopped', this.currentSyncSession);
      this.currentSyncSession = null;
    }
  }

  // Simulate sync process (replace with actual implementation)
  private async simulateSync(session: SyncSession) {
    const totalFiles = Math.floor(Math.random() * 100) + 50;
    session.progress.total = totalFiles;

    for (let i = 0; i < totalFiles; i++) {
      if (session.status === 'paused') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        continue;
      }
      
      if (session.status === 'failed') {
        break;
      }

      // Simulate processing time
      await new Promise(resolve => setTimeout(resolve, Math.random() * 200 + 100));
      
      session.progress.processed = i + 1;
      session.progress.percentage = ((i + 1) / totalFiles) * 100;
      session.progress.currentFile = `file_${i + 1}.pdf`;
      
      // Simulate occasional errors
      if (Math.random() < 0.05) {
        session.progress.errors++;
      }
      
      this.emit('syncProgress', session);
    }
  }

  // Statistics
  getStats(): OneDriveStats {
    return { ...this.stats };
  }

  getSyncHistory(): SyncSession[] {
    return [...this.syncHistory];
  }

  getCurrentSyncSession(): SyncSession | null {
    return this.currentSyncSession;
  }

  // Skill execution
  async executeSkill(skillId: string, input: any) {
    if (this.atomSkillRegistry) {
      return await this.atomSkillRegistry.executeSkill(skillId, input, {
        graphClient: this.createGraphClient(),
        atomIngestionPipeline: this.atomIngestionPipeline,
        onedriveConfig: this.config,
      });
    }
    throw new Error('ATOM skill registry not available');
  }

  private createGraphClient() {
    return {
      get: async (endpoint: string) => {
        const response = await fetch(`https://graph.microsoft.com/v1.0${endpoint}`, {
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          throw new Error(`Microsoft Graph API error: ${response.status}`);
        }
        
        return response.json();
      },
    };
  }

  // Cleanup
  destroy() {
    this.stopSync();
    this.listeners.clear();
  }
}

const AtomOneDriveManagerComponent: React.FC<AtomOneDriveManagerProps> = (props) => {
  const [manager, setManager] = useState<AtomOneDriveManager | null>(null);
  const [stats, setStats] = useState<OneDriveStats | null>(null);
  const [currentSession, setCurrentSession] = useState<SyncSession | null>(null);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [currentConfig, setCurrentConfig] = useState<AtomOneDriveIngestionConfig>(
    () => ({ ...ONEDRIVE_DEFAULT_CONFIG, ...props.initialConfig })
  );
  const [loading, setLoading] = useState(false);

  // Theme colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Initialize manager
  useEffect(() => {
    const oneDriveManager = new AtomOneDriveManager(props.accessToken, props);
    
    // Set up event listeners
    oneDriveManager.on('configUpdated', setStats);
    oneDriveManager.on('syncStart', (session) => {
      setCurrentSession(session);
      props.onSyncStart?.(session);
    });
    oneDriveManager.on('syncProgress', (session) => {
      setCurrentSession(session);
      props.onSyncProgress?.(session);
    });
    oneDriveManager.on('syncComplete', (session) => {
      setCurrentSession(null);
      setStats(oneDriveManager.getStats());
      props.onSyncComplete?.(session);
    });
    oneDriveManager.on('syncError', ({ session, error }) => {
      setCurrentSession(null);
      props.onError?.(error);
    });

    setManager(oneDriveManager);
    setStats(oneDriveManager.getStats());
    props.onReady?.(oneDriveManager);

    return () => {
      oneDriveManager.destroy();
    };
  }, [props.accessToken]);

  // Update manager when config changes
  const handleConfigUpdate = useCallback((newConfig: Partial<AtomOneDriveIngestionConfig>) => {
    const updatedConfig = { ...currentConfig, ...newConfig };
    setCurrentConfig(updatedConfig);
    manager?.updateConfig(updatedConfig);
  }, [currentConfig, manager]);

  // Start sync
  const handleStartSync = useCallback(async () => {
    if (!manager) return;
    
    setLoading(true);
    try {
      await manager.startSync();
    } catch (error) {
      props.onError?.(error);
    } finally {
      setLoading(false);
    }
  }, [manager, props]);

  if (!manager || !stats) {
    return (
      <Center minH="400px">
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Initializing OneDrive Manager...</Text>
        </VStack>
      </Center>
    );
  }

  return (
    <Box p={6} bg={bgColor} minH="100vh">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Icon as={FiCloud} boxSize={8} color="blue.500" />
            <VStack align="start" spacing={0}>
              <Heading size="lg">OneDrive Manager</Heading>
              <Text fontSize="sm" color="gray.500">
                ATOM Integration & Synchronization Control
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Badge
              colorScheme={currentSession ? 'green' : 'gray'}
              variant={currentSession ? 'solid' : 'outline'}
            >
              {currentSession ? 'Active Sync' : 'Idle'}
            </Badge>
            
            <Button
              leftIcon={<FiSettings />}
              onClick={() => setConfigModalOpen(true)}
              variant="outline"
              size="sm"
            >
              Configure
            </Button>
          </HStack>
        </HStack>

        {/* Stats Dashboard */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Total Files</StatLabel>
                <StatNumber fontSize="2xl">{stats.totalFiles.toLocaleString()}</StatNumber>
                <StatHelpText>
                  <Icon as={FiFolder} mr={1} />
                  {stats.totalFolders} folders
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Processed by ATOM</StatLabel>
                <StatNumber fontSize="2xl">{stats.processedByAtom.toLocaleString()}</StatNumber>
                <StatHelpText>
                  <Icon as={FiCpu} mr={1} />
                  {stats.averageProcessingTime}ms avg
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Last Sync</StatLabel>
                <StatNumber fontSize="2xl">
                  {stats.lastSync ? 
                    new Date(stats.lastSync).toLocaleDateString() : 
                    'Never'
                  }
                </StatNumber>
                <StatHelpText>
                  <Icon as={FiClock} mr={1} />
                  {stats.lastSync ? 
                    new Date(stats.lastSync).toLocaleTimeString() : 
                    'No sync performed'
                  }
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Error Rate</StatLabel>
                <StatNumber fontSize="2xl">{(stats.errorRate * 100).toFixed(1)}%</StatNumber>
                <StatHelpText>
                  <Icon as={FiShield} mr={1} />
                  {stats.activeConnections} connections
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Current Sync Session */}
        {currentSession && (
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Active Sync Session</Heading>
                <Badge colorScheme={
                  currentSession.status === 'running' ? 'green' :
                  currentSession.status === 'paused' ? 'yellow' :
                  currentSession.status === 'completed' ? 'blue' : 'red'
                }>
                  {currentSession.status}
                </Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <Progress
                  value={currentSession.progress.percentage}
                  colorScheme="blue"
                  size="lg"
                  hasStripe
                  isAnimated
                />
                
                <HStack justify="space-between">
                  <Text fontSize="sm">
                    {currentSession.progress.processed} / {currentSession.progress.total} files
                  </Text>
                  <Text fontSize="sm">
                    {currentSession.progress.currentFile || 'Processing...'}
                  </Text>
                </HStack>
                
                {currentSession.progress.errors > 0 && (
                  <Alert status="warning">
                    <AlertIcon />
                    {currentSession.progress.errors} errors encountered
                  </Alert>
                )}
                
                <HStack spacing={2}>
                  {currentSession.status === 'running' && (
                    <Button
                      leftIcon={<FiPause />}
                      onClick={() => manager.pauseSync()}
                      variant="outline"
                      size="sm"
                    >
                      Pause
                    </Button>
                  )}
                  
                  {currentSession.status === 'paused' && (
                    <Button
                      leftIcon={<FiPlay />}
                      onClick={() => manager.resumeSync()}
                      colorScheme="green"
                      size="sm"
                    >
                      Resume
                    </Button>
                  )}
                  
                  <Button
                    leftIcon={<FiStop />}
                    onClick={() => manager.stopSync()}
                    colorScheme="red"
                    size="sm"
                  >
                    Stop
                  </Button>
                </HStack>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Control Panel */}
        <Card>
          <CardHeader>
            <Heading size="md">Sync Control</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack spacing={4}>
                <Button
                  leftIcon={<FiRefreshCw />}
                  onClick={handleStartSync}
                  isLoading={loading}
                  isDisabled={currentSession !== null}
                  colorScheme="blue"
                >
                  Start Full Sync
                </Button>
                
                <Button
                  leftIcon={<FiZap />}
                  onClick={() => manager.startSync({ incrementalSync: true })}
                  isDisabled={currentSession !== null}
                  variant="outline"
                >
                  Incremental Sync
                </Button>
                
                <Button
                  leftIcon={<FiDatabase />}
                  onClick={() => manager.executeSkill('onedrive_sync_with_atom_memory', {
                    folderId: 'root',
                    includeSubfolders: true,
                  })}
                  variant="outline"
                >
                  Sync with ATOM Memory
                </Button>
              </HStack>
              
              <Divider />
              
              <HStack spacing={4}>
                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="auto-sync" mb="0">
                    Auto Sync
                  </FormLabel>
                  <Switch
                    id="auto-sync"
                    isChecked={currentConfig.enableRealTimeSync}
                    onChange={(e) => handleConfigUpdate({ enableRealTimeSync: e.target.checked })}
                  />
                </FormControl>
                
                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="extract-text" mb="0">
                    Extract Text
                  </FormLabel>
                  <Switch
                    id="extract-text"
                    isChecked={currentConfig.extractTextContent}
                    onChange={(e) => handleConfigUpdate({ extractTextContent: e.target.checked })}
                  />
                </FormControl>
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Sync History */}
        <Card>
          <CardHeader>
            <Heading size="md">Sync History</Heading>
          </CardHeader>
          <CardBody>
            {manager.getSyncHistory().length > 0 ? (
              <List spacing={3}>
                {manager.getSyncHistory().slice(-5).reverse().map((session) => (
                  <ListItem key={session.id}>
                    <HStack justify="space-between">
                      <HStack spacing={3}>
                        <ListIcon
                          as={
                            session.status === 'completed' ? FiCheck :
                            session.status === 'failed' ? FiX :
                            FiAlertTriangle
                          }
                          color={
                            session.status === 'completed' ? 'green.500' :
                            session.status === 'failed' ? 'red.500' :
                            'yellow.500'
                          }
                        />
                        <VStack align="start" spacing={0}>
                          <Text fontWeight="medium">
                            {new Date(session.startTime).toLocaleString()}
                          </Text>
                          <Text fontSize="sm" color="gray.500">
                            {session.progress.processed} / {session.progress.total} files
                            {session.progress.errors > 0 && ` • ${session.progress.errors} errors`}
                          </Text>
                        </VStack>
                      </HStack>
                      
                      <Badge
                        colorScheme={
                          session.status === 'completed' ? 'green' :
                          session.status === 'failed' ? 'red' :
                          'yellow'
                        }
                      >
                        {session.status}
                      </Badge>
                    </HStack>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box textAlign="center" py={6}>
                <Icon as={FiClock} boxSize={8} color="gray.400" />
                <Text mt={2} color="gray.500">
                  No sync history available
                </Text>
              </Box>
            )}
          </CardBody>
        </Card>

        {/* Configuration Modal */}
        <Modal
          isOpen={configModalOpen}
          onClose={() => setConfigModalOpen(false)}
          size="2xl"
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>OneDrive Configuration</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="stretch">
                <FormControl>
                  <FormLabel>Batch Size</FormLabel>
                  <NumberInput
                    value={currentConfig.batchSize || 50}
                    onChange={(value) => handleConfigUpdate({ batchSize: parseInt(value) || 50 })}
                    min={1}
                    max={100}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Max File Size (MB)</FormLabel>
                  <NumberInput
                    value={(currentConfig.maxFileSize || 0) / (1024 * 1024)}
                    onChange={(value) => handleConfigUpdate({ 
                      maxFileSize: parseFloat(value) * 1024 * 1024 
                    })}
                    min={1}
                    max={1000}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Include File Types</FormLabel>
                  <Textarea
                    value={currentConfig.includeFileTypes?.join(', ') || ''}
                    onChange={(e) => handleConfigUpdate({
                      includeFileTypes: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                    })}
                    placeholder="text/plain,application/pdf,image/jpeg"
                  />
                </FormControl>

                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Real-time Sync</FormLabel>
                    <Switch
                      isChecked={currentConfig.enableRealTimeSync}
                      onChange={(e) => handleConfigUpdate({ enableRealTimeSync: e.target.checked })}
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Incremental Sync</FormLabel>
                    <Switch
                      isChecked={currentConfig.incrementalSync}
                      onChange={(e) => handleConfigUpdate({ incrementalSync: e.target.checked })}
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Generate Previews</FormLabel>
                    <Switch
                      isChecked={currentConfig.generatePreviews}
                      onChange={(e) => handleConfigUpdate({ generatePreviews: e.target.checked })}
                    />
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setConfigModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() => setConfigModalOpen(false)}
              >
                Save Configuration
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default AtomOneDriveManagerComponent;
export { AtomOneDriveManager };