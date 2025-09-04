import React, { useState } from 'react';
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  Badge,
  useToast,
  SimpleGrid,
  IconButton,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription
} from '@chakra-ui/react';
import { AddIcon, CheckIcon, TimeIcon, SettingsIcon } from '@chakra-ui/icons';

interface Workflow {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'paused' | 'error';
  lastRun: string;
  nextRun: string;
  triggerType: 'schedule' | 'event' | 'manual';
}

const SimpleAutomationsPage: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([
    {
      id: '1',
      name: 'Daily Email Digest',
      description: 'Send daily summary of important emails',
      status: 'active',
      lastRun: '2024-01-15T09:00:00Z',
      nextRun: '2024-01-16T09:00:00Z',
      triggerType: 'schedule'
    },
    {
      id: '2',
      name: 'Meeting Follow-ups',
      description: 'Create tasks from meeting notes',
      status: 'active',
      lastRun: '2024-01-15T14:30:00Z',
      nextRun: 'On meeting end',
      triggerType: 'event'
    },
    {
      id: '3',
      name: 'Weekly Financial Report',
      description: 'Generate weekly financial summary',
      status: 'paused',
      lastRun: '2024-01-08T09:00:00Z',
      nextRun: '2024-01-22T09:00:00Z',
      triggerType: 'schedule'
    }
  ]);

  const toast = useToast();

  const handleToggleWorkflow = (workflowId: string) => {
    setWorkflows(prev => prev.map(wf =>
      wf.id === workflowId
        ? { ...wf, status: wf.status === 'active' ? 'paused' : 'active' }
        : wf
    ));

    toast({
      title: 'Workflow updated',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleRunWorkflow = (workflowId: string) => {
    toast({
      title: 'Workflow started',
      description: 'Running workflow in background',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'green';
      case 'paused': return 'yellow';
      case 'error': return 'red';
      default: return 'gray';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <VStack align="start" spacing={1}>
            <Heading size="xl">Automations</Heading>
            <Text color="gray.600">
              Create and manage automated workflows
            </Text>
          </VStack>
          <Button leftIcon={<AddIcon />} colorScheme="blue">
            New Workflow
          </Button>
        </HStack>

        {/* Info Alert */}
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          <Box>
            <AlertTitle>Workflow Editor Coming Soon</AlertTitle>
            <AlertDescription>
              The visual workflow editor is temporarily unavailable. You can still manage existing automations here.
            </AlertDescription>
          </Box>
        </Alert>

        {/* Workflows Grid */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
          {workflows.map((workflow) => (
            <Card key={workflow.id} variant="outline">
              <CardHeader>
                <HStack justify="space-between">
                  <Heading size="md">{workflow.name}</Heading>
                  <Badge colorScheme={getStatusColor(workflow.status)}>
                    {workflow.status}
                  </Badge>
                </HStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={3} align="stretch">
                  <Text color="gray.600">{workflow.description}</Text>
                  <HStack spacing={4}>
                    <Badge variant="outline" colorScheme="blue">
                      {workflow.triggerType}
                    </Badge>
                    <Badge variant="outline" colorScheme="purple">
                      {workflow.triggerType === 'schedule' ? 'Scheduled' : 'Event-based'}
                    </Badge>
                  </HStack>
                  <VStack spacing={1} align="start">
                    <Text fontSize="sm" color="gray.500">
                      Last run: {formatDate(workflow.lastRun)}
                    </Text>
                    <Text fontSize="sm" color="gray.500">
                      Next run: {workflow.nextRun}
                    </Text>
                  </VStack>
                </VStack>
              </CardBody>
              <CardFooter>
                <HStack spacing={2} width="full">
                  <Button
                    size="sm"
                    variant={workflow.status === 'active' ? 'outline' : 'solid'}
                    colorScheme={workflow.status === 'active' ? 'red' : 'green'}
                    onClick={() => handleToggleWorkflow(workflow.id)}
                    flex={1}
                  >
                    {workflow.status === 'active' ? 'Pause' : 'Activate'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRunWorkflow(workflow.id)}
                    leftIcon={<TimeIcon />}
                    flex={1}
                  >
                    Run Now
                  </Button>
                  <IconButton
                    size="sm"
                    variant="ghost"
                    aria-label="Settings"
                    icon={<SettingsIcon />}
                  />
                </HStack>
              </CardFooter>
            </Card>
          ))}
        </SimpleGrid>

        {/* Empty State */}
        {workflows.length === 0 && (
          <Card>
            <CardBody>
              <VStack spacing={4} py={8} textAlign="center">
                <Heading size="md" color="gray.500">
                  No workflows yet
                </Heading>
                <Text color="gray.500">
                  Create your first automation to streamline your workflow
                </Text>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  Create Workflow
                </Button>
              </VStack>
            </CardBody>
          </Card>
        )}
      </VStack>
    </Box>
  );
};

export default SimpleAutomationsPage;
