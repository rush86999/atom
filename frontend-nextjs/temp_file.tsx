import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Badge,
  Button,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  SimpleGrid,
  Flex,
  Spinner,
  useToast,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Radio,
  RadioGroup,
  Stack
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon, CopyIcon, TimeIcon } from '@chakra-ui/icons';

interface TriggerDefinition {
  id: string;
  name: string;
  type: 'schedule' | 'webhook' | 'manual' | 'email' | 'file' | 'api' | 'database';
  description: string;
  enabled: boolean;
  config: Record<string, any>;
  conditions?: TriggerCondition[];
  lastTriggered?: Date;
  triggerCount: number;
  createdAt: Date;
  updatedAt: Date;
}

interface TriggerCondition {
  id: string;
  field: string;
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'matches';
  value: string;
}

interface TriggerSettingsProps {
  onTriggerCreate?: (trigger: TriggerDefinition) => void;
  onTriggerUpdate?: (triggerId: string, updates: Partial<TriggerDefinition>) => void;
  onTriggerDelete?: (triggerId: string) => void;
  onTriggerDuplicate?: (trigger: TriggerDefinition) => void;
  initialTriggers?: TriggerDefinition[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const TriggerSettings: React.FC<TriggerSettingsProps> = ({
  onTriggerCreate,
  onTriggerUpdate,
  onTriggerDelete,
  onTriggerDuplicate,
  initialTriggers = [],
  showNavigation = true,
  compactView = false
}) => {
  const [triggers, setTriggers] = useState<TriggerDefinition[]>(initialTriggers);
  const [selectedTrigger, setSelectedTrigger] = useState<TriggerDefinition | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'list' | 'templates'>('list');
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  // Trigger templates
  const triggerTemplates = [
    {
      id: 'daily_schedule',
      name: 'Daily Schedule',
      type: 'schedule' as const,
      description: 'Run workflow daily at specific time',
      config: {
        scheduleType: 'daily',
        time: '09:00',
        timezone: 'UTC'
      }
    },
    {
      id: 'webhook_trigger',
      name: 'Webhook Trigger',
      type: 'webhook' as const,
      description: 'Trigger workflow via webhook',
      config: {
        method: 'POST',
        path: '/webhook/',
        secret: ''
      }
    },
    {
      id: 'email_received',
      name: 'Email Received',
      type: 'email' as const,
      description: 'Trigger when new email arrives',
      config: {
        mailbox: 'INBOX',
        subjectFilter: '',
        senderFilter: ''
      }
    },
    {
      id: 'file_uploaded',
      name: 'File Uploaded',
      type: 'file' as const,
      description: 'Trigger when file is uploaded',
      config: {
        folder: '/uploads',
        filePattern: '*',
        watchSubfolders: true
      }
    },
    {
      id: 'api_call',
      name: 'API Call',
      type: 'api' as const,
      description: 'Trigger via API endpoint',
      config: {
        endpoint: '/api/trigger/',
        authentication: 'none'
      }
    }
  ];

  useEffect(() => {
    setTriggers(initialTriggers);
  }, [initialTriggers]);

  const handleCreateTrigger = (triggerData: Omit<TriggerDefinition, 'id' | 'createdAt' | 'updatedAt' | 'triggerCount'>) => {
    const newTrigger: TriggerDefinition = {
      ...triggerData,
      id: Date.now().toString(),
      triggerCount: 0,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setTriggers(prev => [...prev, newTrigger]);
    onTriggerCreate?.(newTrigger);
    toast({
      title: 'Trigger created',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUpdateTrigger = (triggerId: string, updates: Partial<TriggerDefinition>) => {
    setTriggers(prev => prev.map(trigger =>
      trigger.id === triggerId ? { ...trigger, ...updates, updatedAt: new Date() } : trigger
    ));
    onTriggerUpdate?.(triggerId, updates);
    toast({
      title: 'Trigger updated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteTrigger = (triggerId: string) => {
    setTriggers(prev => prev.filter(trigger => trigger.id !== triggerId));
    onTriggerDelete?.(triggerId);
    toast({
      title: 'Trigger deleted',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDuplicateTrigger = (trigger: TriggerDefinition) => {
    const duplicatedTrigger: TriggerDefinition = {
      ...trigger,
      id: Date.now().toString(),
      name: `${trigger.name} (Copy)`,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setTriggers(prev => [...prev, duplicatedTrigger]);
    onTriggerDuplicate?.(duplicatedTrigger);
    toast({
      title: 'Trigger duplicated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUseTemplate = (template: typeof triggerTemplates[0]) => {
    const newTrigger: Omit<TriggerDefinition, 'id' | 'createdAt' | 'updatedAt' | 'triggerCount'> = {
      name: template.name,
      type: template.type,
      description: template.description,
      enabled: true,
      config: { ...template.config },
      conditions: []
    };
    handleCreateTrigger(newTrigger);
    onClose();
  };

  const getTriggerTypeColor = (type: TriggerDefinition['type']) => {
    switch (type) {
      case 'schedule': return 'blue';
      case 'webhook': return 'green';
      case 'manual': return 'purple';
      case 'email': return 'orange';
      case 'file': return 'teal';
      case 'api': return 'cyan';
      case 'database': return 'pink';
      default: return 'gray';
    }
  };

  const getTriggerIcon = (type: TriggerDefinition['type']) => {
    switch (type) {
      case 'schedule': return <TimeIcon />;
      case 'webhook': return '🌐';
      case 'manual': return '👆';
      case 'email': return '📧';
      case 'file': return '📁';
      case 'api': return '🔌';
      case 'database': return '🗄️';
      default: return '⚡';
    }
  };

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>Trigger Settings</Heading>
            <Button
              leftIcon={<AddIcon />}
              colorScheme="blue"
              size={compactView ? "sm" : "md"}
              onClick={() => {
                setSelectedTrigger(null);
                onOpen();
              }}
            >
              New Trigger
            </Button>
          </Flex>
        )}

        {/* Triggers List */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Triggers</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={4} align="stretch">
              {triggers.map(trigger => (
                <Card key={trigger.id} size="sm">
                  <CardBody>
                    <Flex justify="space-between" align="center">
                      <VStack align="start" spacing={1}>
                        <Heading size="sm">{trigger.name}</Heading>
                        <Text fontSize="sm" color="gray.600">{trigger.description}</Text>
                        <HStack spacing={2}>
                          <Badge colorScheme={getTriggerTypeColor(trigger.type)}>
                            {trigger.type}
                          </Badge>
                          <Badge colorScheme={trigger.enabled ? 'green' : 'gray'}>
                            {trigger.enabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                        </HStack>
                      </VStack>
                      <HStack spacing={2}>
                        <IconButton
                          aria-label="Edit trigger"
                          icon={<EditIcon />}
                          size="sm"
                          onClick={() => {
                            setSelectedTrigger(trigger);
                            onOpen();
                          }}
                        />
                        <IconButton
                          aria-label="Duplicate trigger"
                          icon={<CopyIcon />}
                          size="sm"
                          onClick={() => handleDuplicateTrigger(trigger.id)}
                        />
                        <IconButton
                          aria-label="Delete trigger"
                          icon={<DeleteIcon />}
                          size="sm"
                          colorScheme="red"
                          onClick={() => handleDeleteTrigger(trigger.id)}
                        />
                      </HStack>
                    </Flex>
                  </CardBody>
                </Card>
              ))}
            </VStack>
          </CardBody>
        </Card>
      </VStack>

      {/* Trigger Form Modal */}
      {isOpen && (
        <Modal isOpen={isOpen} onClose={onClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              {selectedTrigger ? 'Edit Trigger' : 'Create New Trigger'}
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <TriggerForm
                trigger={selectedTrigger}
                onSubmit={(data) => {
                  if (selectedTrigger) {
                    handleUpdateTrigger(selectedTrigger.id, data);
                  } else {
                    handleCreateTrigger(data);
                  }
                }}
                onCancel={onClose}
              />
            </ModalBody>
          </ModalContent>
        </Modal>
      )}
    </Box>
  );
};

  const TriggerForm: React.FC<{
    trigger?: TriggerDefinition;
    onSubmit: (data: Omit<TriggerDefinition, 'id' | 'createdAt' | 'updatedAt' | 'triggerCount'>) => void;
    onCancel: () => void;
  }> = ({ trigger, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      name: trigger?.name || '',
      type: trigger?.type || 'schedule',
      description: trigger?.description || '',
      enabled: trigger?.enabled ?? true,
      config: trigger?.config || {},
      conditions: trigger?.conditions || []
    });

    const [newCondition, setNewCondition] = useState<TriggerCondition>({
      id: '',
      field: '',
      operator: 'equals',
      value: ''
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        name: formData.name,
        type: formData.type as TriggerDefinition['type'],
        description: formData.description,
        enabled: formData.enabled,
        config: formData.config,
        conditions: formData.conditions
      });
      onCancel();
    };

    const addCondition = () => {
      if (newCondition.field && newCondition.value) {
        const condition: TriggerCondition = {
          ...newCondition,
          id: Date.now().toString()
        };
        setFormData(prev => ({
          ...prev,
          conditions: [...prev.conditions, condition]
        }));
        setNewCondition({
          id: '',
          field: '',
          operator: 'equals',
          value: ''
        });
      }
    };

    const removeCondition = (conditionId: string) => {
      setFormData(prev => ({
        ...prev,
        conditions: prev.conditions.filter(cond => cond.id !== conditionId)
      }));
    };

    const renderTriggerConfig = () => {
      switch (formData.type) {
        case 'schedule':
          return (
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Schedule Type</FormLabel>
                <Select
                  value={formData.config.scheduleType || 'daily'}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, scheduleType: e.target.value }
                  }))}
                >
                  <option value="minutely">Every Minute</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="cron">Custom Cron</option>
                </Select>
              </FormControl>

              {formData.config.scheduleType === 'daily' && (
                <FormControl>
                  <FormLabel>Time</FormLabel>
                  <Input
                    type="time"
                    value={formData.config.time || '09:00'}
                    onChange={(e) => setFormData(prev => ({
                      ...prev,
                      config: { ...prev.config, time: e.target.value }
                    }))}
                  />
                </FormControl>
              )}

              {formData.config.scheduleType === 'cron' && (
                <FormControl>
                  <FormLabel>Cron Expression</FormLabel>
                  <Input
                    value={formData.config.cronExpression || '0 9 * * *'}
                    onChange={(e) => setFormData(prev => ({
                      ...prev,
                      config: { ...prev.config, cronExpression: e.target.value }
                    }))}
                    placeholder="0 9 * * *"
                  />
                  <Text fontSize="sm" color="gray.600" mt={1}>
                    Format: minute hour day month weekday
                  </Text>
                </FormControl>
              )}

              <FormControl>
                <FormLabel>Timezone</FormLabel>
                <Select
                  value={formData.config.timezone || 'UTC'}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, timezone: e.target.value }
                  }))}
                >
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">Eastern Time</option>
                  <option value="America/Chicago">Central Time</option>
                  <option value="America/Denver">Mountain Time</option>
                  <option value="America/Los_Angeles">Pacific Time</option>
                </Select>
              </FormControl>
            </VStack>
          );

        case 'webhook':
          return (
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>HTTP Method</FormLabel>
                <Select
                  value={formData.config.method || 'POST'}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, method: e.target.value }
                  }))}
                >
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="DELETE">DELETE</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Webhook Path</FormLabel>
                <Input
                  value={formData.config.path || '/webhook/'}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, path: e.target.value }
                  }))}
                  placeholder="/webhook/trigger-name"
                />
              </FormControl>

              <FormControl>
                <FormLabel>Secret Key (Optional)</FormLabel>
                <Input
                  type="password"
                  value={formData.config.secret || ''}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, secret: e.target.value }
                  }))}
                  placeholder="Secret for webhook verification"
                />
              </FormControl>
            </VStack>
          );

        case 'email':
          return (
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Mailbox</FormLabel>
                <Select
                  value={formData.config.mailbox || 'INBOX'}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, mailbox: e.target.value }
                  }))}
                >
                  <option value="INBOX">Inbox</option>
                  <option value="SENT">Sent</option>
                  <option value="DRAFTS">Drafts</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Subject Filter</FormLabel>
                <Input
                  value={formData.config.subjectFilter || ''}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, subjectFilter: e.target.value }
                  }))}
                  placeholder="Filter emails by subject"
                />
              </FormControl>

              <FormControl>
                <FormLabel>Sender Filter</FormLabel>
                <Input
                  value={formData.config.senderFilter || ''}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    config: { ...prev.config, senderFilter: e.target.value }
                  }))}
                  placeholder="Filter emails by sender"
                />
              </FormControl>
            </VStack>
          );

        default:
          return (
            <Alert status="info">
              <AlertIcon />
              Configuration options for this trigger type will be available soon.
            </Alert>
          );
      }
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={6} align="stretch">
          <SimpleGrid columns={2} spacing={4}>
            <FormControl isRequired>
              <FormLabel>Trigger Name</FormLabel>
              <Input
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Enter trigger name"
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Trigger Type</FormLabel>
              <Select
                value={formData.type}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  type: e.target.value as TriggerDefinition['type'],
                  config: {} // Reset config when type changes
                }))}
              >
                <option value="schedule">Schedule</option>
                <option value="webhook">Webhook</option>
                <option value="manual">Manual</option>
                <option value="email">Email</option>
                <option value="file">File</option>
                <option value="api">API</option>
                <option value="database">Database</option>
              </Select>
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe what this trigger does"
              rows={2}
            />
          </FormControl>

          <FormControl display="flex" alignItems="center">
            <FormLabel mb="0" flex="1">
              Enabled
            </FormLabel>
            <Switch
              isChecked={formData.enabled}
              onChange={(e) => setFormData(prev => ({ ...prev, enabled: e.target.checked }))}
            />
          </FormControl>

          <Accordion allowToggle>
            <AccordionItem>
              <AccordionButton>
                <Box flex="1" textAlign="left">
                  <Heading size="sm">Trigger Configuration</Heading>
                </Box>
                <AccordionIcon />
              </AccordionButton>
              <AccordionPanel pb={4}>
                {renderTriggerConfig()}
              </AccordionPanel>
            </AccordionItem>

            <AccordionItem>
              <AccordionButton>
                <Box flex="1" textAlign="left">
                  <Heading size="sm">Conditions</Heading>
                </Box>
                <AccordionIcon />
              </AccordionButton>
              <AccordionPanel pb={4}>
                <VStack spacing={4} align="stretch">
                  {formData.conditions.map(condition => (
                    <Card key={condition.id} size="sm">
                      <CardBody>
                        <Flex justify="space-between" align="center">
                          <VStack align="start" spacing={1}>
                            <Text fontWeight="medium">{condition.field}</Text>
                            <HStack spacing={2}>
                              <Badge>{condition.operator}</Badge>
                              <Text>{condition.value}</Text>
                            </HStack>
                          </VStack>
                          <IconButton
                            aria-label="Remove condition"
                            icon={<DeleteIcon />}
                            size="sm"
                            colorScheme="red"
                            onClick={() => handleRemoveCondition(condition.id)}
                          />
                        </Flex>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </AccordionPanel>
            </AccordionItem>
          </Accordion>

          {/* Actions */}
          <Card>
              <CardHeader>
                <HStack justify="space-between">
                  <Heading size="md">Actions</Heading>
                  <Button
                    leftIcon={<AddIcon />}
                    size="sm"
                    onClick={handleAddAction}
                  >
                    Add Action
                  </Button>
                </HStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  {formData.actions.map(action => (
                    <Card key={action.id} size="sm">
                      <CardBody>
                        <Flex justify="space-between" align="center">
                          <VStack align="start" spacing={1}>
                            <Text fontWeight="medium">{action.type}</Text>
                            <Text color="gray.600">{action.config}</Text>
                          </VStack>
                          <IconButton
                            aria-label="Remove action"
                            icon={<DeleteIcon />}
                            size="sm"
                            colorScheme="red"
                            onClick={() => handleRemoveAction(action.id)}
                          />
                        </Flex>
                      </CardBody>
                    </Card>
                  ))}
                </VStack>
              </CardBody>
            </Card>
          </VStack>

          <HStack spacing={3} mt={6}>
            <Button onClick={onCancel} variant="outline">
              Cancel
            </Button>
            <Button onClick={handleSaveTrigger} colorScheme="blue">
              Save Trigger
            </Button>
          </HStack>
        </form>
      </Box>
    );
  };
export default TriggerSettings;
