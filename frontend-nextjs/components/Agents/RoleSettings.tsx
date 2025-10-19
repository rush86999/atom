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
  AccordionIcon
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon, CopyIcon } from '@chakra-ui/icons';

interface AgentRole {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  permissions: {
    canAccessFiles: boolean;
    canAccessWeb: boolean;
    canExecuteCode: boolean;
    canAccessDatabase: boolean;
    canSendEmails: boolean;
    canMakeAPICalls: boolean;
  };
  systemPrompt: string;
  modelConfig: {
    model: string;
    temperature: number;
    maxTokens: number;
    topP: number;
    frequencyPenalty: number;
    presencePenalty: number;
  };
  isDefault: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface RoleSettingsProps {
  onRoleCreate?: (role: AgentRole) => void;
  onRoleUpdate?: (roleId: string, updates: Partial<AgentRole>) => void;
  onRoleDelete?: (roleId: string) => void;
  onRoleDuplicate?: (role: AgentRole) => void;
  initialRoles?: AgentRole[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const RoleSettings: React.FC<RoleSettingsProps> = ({
  onRoleCreate,
  onRoleUpdate,
  onRoleDelete,
  onRoleDuplicate,
  initialRoles = [],
  showNavigation = true,
  compactView = false
}) => {
  const [roles, setRoles] = useState<AgentRole[]>(initialRoles);
  const [selectedRole, setSelectedRole] = useState<AgentRole | null>(null);
  const [loading, setLoading] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  // Default roles
  const defaultRoles: AgentRole[] = [
    {
      id: 'personal_assistant',
      name: 'Personal Assistant',
      description: 'General purpose assistant for daily tasks and scheduling',
      capabilities: ['scheduling', 'email_management', 'note_taking', 'web_search'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: false,
        canAccessDatabase: false,
        canSendEmails: true,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are a helpful personal assistant. Help with scheduling, email management, and general tasks.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.7,
        maxTokens: 2000,
        topP: 1.0,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    },
    {
      id: 'research_agent',
      name: 'Research Agent',
      description: 'Specialized in research and information gathering',
      capabilities: ['web_search', 'data_analysis', 'summarization', 'citation'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: false,
        canAccessDatabase: false,
        canSendEmails: false,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are a research specialist. Provide thorough, well-researched information with proper citations.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.3,
        maxTokens: 4000,
        topP: 1.0,
        frequencyPenalty: 0.1,
        presencePenalty: 0.1
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    },
    {
      id: 'coding_agent',
      name: 'Coding Agent',
      description: 'Software development and code assistance',
      capabilities: ['code_generation', 'debugging', 'code_review', 'documentation'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: true,
        canAccessDatabase: true,
        canSendEmails: false,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are an expert software developer. Write clean, efficient, and well-documented code.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.2,
        maxTokens: 4000,
        topP: 1.0,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    }
  ];

  // Initialize with default roles if no initial roles provided
  useEffect(() => {
    if (initialRoles.length === 0) {
      setRoles(defaultRoles);
    } else {
      setRoles(initialRoles);
    }
  }, [initialRoles]);

  const handleCreateRole = (roleData: Omit<AgentRole, 'id' | 'createdAt' | 'updatedAt' | 'isDefault'>) => {
    const newRole: AgentRole = {
      ...roleData,
      id: Date.now().toString(),
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setRoles(prev => [...prev, newRole]);
    onRoleCreate?.(newRole);
    toast({
      title: 'Role created',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUpdateRole = (roleId: string, updates: Partial<AgentRole>) => {
    setRoles(prev => prev.map(role =>
      role.id === roleId ? { ...role, ...updates, updatedAt: new Date() } : role
    ));
    onRoleUpdate?.(roleId, updates);
    toast({
      title: 'Role updated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteRole = (roleId: string) => {
    const role = roles.find(r => r.id === roleId);
    if (role?.isDefault) {
      toast({
        title: 'Cannot delete default role',
        status: 'error',
        duration: 2000,
        isClosable: true,
      });
      return;
    }
    setRoles(prev => prev.filter(role => role.id !== roleId));
    onRoleDelete?.(roleId);
    toast({
      title: 'Role deleted',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDuplicateRole = (role: AgentRole) => {
    const duplicatedRole: AgentRole = {
      ...role,
      id: Date.now().toString(),
      name: `${role.name} (Copy)`,
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setRoles(prev => [...prev, duplicatedRole]);
    onRoleDuplicate?.(duplicatedRole);
    toast({
      title: 'Role duplicated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const RoleForm: React.FC<{
    role?: AgentRole;
    onSubmit: (data: Omit<AgentRole, 'id' | 'createdAt' | 'updatedAt' | 'isDefault'>) => void;
    onCancel: () => void;
  }> = ({ role, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      name: role?.name || '',
      description: role?.description || '',
      capabilities: role?.capabilities?.join(', ') || '',
      permissions: {
        canAccessFiles: role?.permissions?.canAccessFiles || false,
        canAccessWeb: role?.permissions?.canAccessWeb || false,
        canExecuteCode: role?.permissions?.canExecuteCode || false,
        canAccessDatabase: role?.permissions?.canAccessDatabase || false,
        canSendEmails: role?.permissions?.canSendEmails || false,
        canMakeAPICalls: role?.permissions?.canMakeAPICalls || false
      },
      systemPrompt: role?.systemPrompt || '',
      modelConfig: {
        model: role?.modelConfig?.model || 'gpt-4',
        temperature: role?.modelConfig?.temperature || 0.7,
        maxTokens: role?.modelConfig?.maxTokens || 2000,
        topP: role?.modelConfig?.topP || 1.0,
        frequencyPenalty: role?.modelConfig?.frequencyPenalty || 0.0,
        presencePenalty: role?.modelConfig?.presencePenalty || 0.0
      }
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        name: formData.name,
        description: formData.description,
        capabilities: formData.capabilities.split(',').map(cap => cap.trim()).filter(Boolean),
        permissions: formData.permissions,
        systemPrompt: formData.systemPrompt,
        modelConfig: formData.modelConfig
      });
      onCancel();
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Role Name</FormLabel>
            <Input
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Enter role name"
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Description</FormLabel>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe the role's purpose and responsibilities"
              rows={2}
            />
          </FormControl>

          <FormControl>
            <FormLabel>Capabilities</FormLabel>
            <Input
              value={formData.capabilities}
              onChange={(e) => setFormData(prev => ({ ...prev, capabilities: e.target.value }))}
              placeholder="web_search, data_analysis, code_generation, etc."
            />
            <Text fontSize="sm" color="gray.600" mt={1}>
              Separate capabilities with commas
            </Text>
          </FormControl>

          <Accordion allowToggle width="100%">
            <AccordionItem>
              <AccordionButton>
                <Box flex="1" textAlign="left">
                  <Heading size="sm">Permissions</Heading>
                </Box>
                <AccordionIcon />
              </AccordionButton>
              <AccordionPanel pb={4}>
                <VStack spacing={3} align="stretch">
                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Access Files
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canAccessFiles}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canAccessFiles: e.target.checked }
                      }))}
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Access Web
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canAccessWeb}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canAccessWeb: e.target.checked }
                      }))}
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Execute Code
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canExecuteCode}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canExecuteCode: e.target.checked }
                      }))}
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Access Database
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canAccessDatabase}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canAccessDatabase: e.target.checked }
                      }))}
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Send Emails
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canSendEmails}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canSendEmails: e.target.checked }
                      }))}
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb="0" flex="1">
                      Make API Calls
                    </FormLabel>
                    <Switch
                      isChecked={formData.permissions.canMakeAPICalls}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, canMakeAPICalls: e.target.checked }
                      }))}
                    />
                  </FormControl>
                </VStack>
              </AccordionPanel>
            </AccordionItem>

            <AccordionItem>
              <AccordionButton>
                <Box flex="1" textAlign="left">
                  <Heading size="sm">Model Configuration</Heading>
                </Box>
                <AccordionIcon />
              </AccordionButton>
              <AccordionPanel pb={4}>
                <VStack spacing={4}>
                  <FormControl>
                    <FormLabel>Model</FormLabel>
                    <Select
                      value={formData.modelConfig.model}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        modelConfig: { ...prev.modelConfig, model: e.target.value }
                      }))}
                    >
                      <option value="gpt-4">GPT-4</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                      <option value="claude-3">Claude 3</option>
                      <option value="llama-2">Llama 2</option>
                    </Select>
                  </FormControl>

                  <SimpleGrid columns={2} spacing={4}>
                    <FormControl>
                      <FormLabel>Temperature</FormLabel>
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={formData.modelConfig.temperature}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          modelConfig: { ...prev.modelConfig, temperature: parseFloat(e.target.value) }
                        }))}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Max Tokens</FormLabel>
                      <Input
                        type="number"
                        value={formData.modelConfig.maxTokens}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          modelConfig: { ...prev.modelConfig, maxTokens: parseInt(e.target.value) }
                        }))}
                      />
                    </FormControl>
                  </SimpleGrid>

                  <SimpleGrid columns={2} spacing={4}>
                    <FormControl>
                      <FormLabel>Top P</FormLabel>
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={formData.modelConfig.topP}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          modelConfig: { ...prev.modelConfig, topP: parseFloat(e.target.value) }
                        }))}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Frequency Penalty</FormLabel>
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={formData.modelConfig.frequencyPenalty}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          modelConfig: { ...prev.modelConfig, frequencyPenalty: parseFloat(e.target.value) }
                        }))}
                      />
                    </FormControl>
                  </SimpleGrid>

                  <FormControl>
                    <FormLabel>Presence Penalty</FormLabel>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={formData.modelConfig.presencePenalty}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        modelConfig: { ...prev.modelConfig, presencePenalty: parseFloat(e.target.value) }
                      }))}
                    />
                  </FormControl>
                </VStack>
              </AccordionPanel>
            </AccordionItem>
          </Accordion>

          <FormControl isRequired>
            <FormLabel>System Prompt</FormLabel>
            <Textarea
              value={formData.systemPrompt}
              onChange={(e) => setFormData(prev => ({ ...prev, systemPrompt: e.target.value }))}
              placeholder="Define the agent's behavior, personality, and instructions..."
              rows={6}
            />
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {role ? 'Update Role' : 'Create Role'}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8
