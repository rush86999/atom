import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Card,
  CardBody,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Input,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Switch,
  Divider,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Progress,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Avatar,
  AvatarBadge,
  Flex,
  InputGroup,
  InputLeftElement,
  SearchIcon,
  PersonIcon,
  CalendarIcon,
  TimeIcon,
  CheckIcon,
  CloseIcon,
  EditIcon,
  DeleteIcon,
  SettingsIcon,
  InfoIcon,
  ExternalLinkIcon,
  Select
} from '@chakra-ui/react';

interface BambooHRConfig {
  subdomain?: string;
  api_key?: string;
  environment: 'production' | 'sandbox';
}

interface Employee {
  id: string;
  firstName: string;
  lastName: string;
  workEmail: string;
  jobTitle?: string;
  department?: string;
  location?: string;
  hireDate?: string;
  status?: string;
  avatar?: string;
}

const BambooHRIntegration: React.FC = () => {
  const [config, setConfig] = useState<BambooHRConfig>({ environment: 'production' });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const toast = useToast();

  // Data states
  const [employees, setEmployees] = useState<Employee[]>([]);

  // Modal states
  const [isEmployeeModalOpen, setIsEmployeeModalOpen] = useState(false);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  // Forms
  const [employeeForm, setEmployeeForm] = useState({
    firstName: '',
    lastName: '',
    workEmail: '',
    jobTitle: '',
    department: '',
    location: ''
  });

  const [configForm, setConfigForm] = useState({
    subdomain: '',
    api_key: ''
  });

  // Analytics state
  const [analytics, setAnalytics] = useState({
    totalEmployees: 0,
    pendingTimeOff: 0,
    activeEmployees: 0,
    departments: 0
  });

  const handleAuthentication = async () => {
    setLoading(true);
    try {
      // Check authentication status
      const response = await fetch('/api/auth/bamboohr/status');
      const data = await response.json();
      
      if (data.authenticated) {
        setIsAuthenticated(true);
        setConfig({
          subdomain: data.subdomain,
          environment: 'production'
        });
        toast({
          title: "BambooHR Connected",
          description: `Connected to ${data.subdomain}.bamboohr.com`,
          status: "success",
          duration: 3000,
          isClosable: true
        });
      } else {
        setIsConfigModalOpen(true);
      }
    } catch (error) {
      console.error('Authentication check failed:', error);
      toast({
        title: "Error",
        description: "Failed to check authentication status",
        status: "error",
        duration: 3000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/auth/bamboohr/save-api-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          subdomain: configForm.subdomain,
          api_key: configForm.api_key
        })
      });

      const data = await response.json();
      
      if (data.ok) {
        setIsAuthenticated(true);
        setIsConfigModalOpen(false);
        toast({
          title: "BambooHR Connected",
          description: "Successfully connected to BambooHR",
          status: "success",
          duration: 3000,
          isClosable: true
        });
        
        // Load data
        await handleLoadEmployees();
      } else {
        toast({
          title: "Connection Failed",
          description: data.error || "Invalid credentials",
          status: "error",
          duration: 3000,
          isClosable: true
        });
      }
    } catch (error) {
      console.error('Config save failed:', error);
      toast({
        title: "Error",
        description: "Failed to save configuration",
        status: "error",
        duration: 3000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleLoadEmployees = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/bamboohr/employees');
      const data = await response.json();
      
      if (data.ok) {
        setEmployees(data.data.data.employees || []);
        setAnalytics(prev => ({
          ...prev,
          totalEmployees: data.data.total || 0
        }));
      } else {
        toast({
          title: "Error",
          description: "Failed to load employees",
          status: "error",
          duration: 3000,
          isClosable: true
        });
      }
    } catch (error) {
      console.error('Failed to load employees:', error);
    } finally {
      setLoading(false);
    }
  };

  const getDepartmentColor = (dept: string) => {
    const colors: { [key: string]: string } = {
      'engineering': 'blue',
      'sales': 'green',
      'marketing': 'purple',
      'hr': 'orange',
      'finance': 'pink',
      'operations': 'yellow'
    };
    return colors[dept?.toLowerCase()] || 'gray';
  };

  if (!isAuthenticated) {
    return (
      <Box minH="100vh" bg="white" p={6}>
        <VStack spacing={8} maxW="800px" mx="auto">
          <VStack spacing={4} textAlign="center">
            <Heading size="2xl" color="orange.500">BambooHR Integration</Heading>
            <Text fontSize="lg" color="gray.600">
              Human Resources Management Platform
            </Text>
            <Text color="gray.500">
              Manage employees, time off, and HR operations
            </Text>
          </VStack>

          <Card borderWidth={2} borderColor="orange.200" maxW="md" w="full">
            <CardBody p={8}>
              <VStack spacing={6}>
                <VStack spacing={3}>
                  <Heading size="md" color="orange.600">
                    Connect to BambooHR
                  </Heading>
                  <Text textAlign="center" color="gray.600">
                    Enter your BambooHR credentials to access HR management features
                  </Text>
                </VStack>

                <Button
                  colorScheme="orange"
                  size="lg"
                  onClick={handleAuthentication}
                  isLoading={loading}
                  leftIcon={<SettingsIcon />}
                  w="full"
                >
                  Connect to BambooHR
                </Button>

                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  <Box>
                    <Text fontWeight="medium">Required Information:</Text>
                    <Text fontSize="sm" mt={1}>
                      • Company subdomain (e.g., companyname.bamboohr.com)<br/>
                      • API key credentials<br/>
                      • HR admin access permissions
                    </Text>
                  </Box>
                </Alert>
              </VStack>
            </CardBody>
          </Card>
        </VStack>

        {/* Configuration Modal */}
        <Modal isOpen={isConfigModalOpen} onClose={() => setIsConfigModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>BambooHR Configuration</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Company Subdomain</FormLabel>
                  <Input
                    value={configForm.subdomain}
                    onChange={(e) => setConfigForm({ ...configForm, subdomain: e.target.value })}
                    placeholder="companyname"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>API Key</FormLabel>
                  <Textarea
                    value={configForm.api_key}
                    onChange={(e) => setConfigForm({ ...configForm, api_key: e.target.value })}
                    placeholder="Enter your BambooHR API key"
                    rows={4}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsConfigModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleSaveConfig}
                isLoading={loading}
                isDisabled={!configForm.subdomain || !configForm.api_key}
              >
                Save Configuration
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg="white" p={6}>
      <VStack spacing={6} maxW="1200px" mx="auto">
        <HStack justify="space-between" w="full">
          <VStack align="start" spacing={1}>
            <Heading size="lg" color="orange.500">BambooHR</Heading>
            <Text fontSize="sm" color="gray.600">
              Human Resources Management
            </Text>
          </VStack>
          <Button
            variant="outline"
            onClick={() => window.open(`https://${config.subdomain}.bamboohr.com`, '_blank')}
            rightIcon={<ExternalLinkIcon />}
          >
            Open BambooHR
          </Button>
        </HStack>

        {/* Analytics Cards */}
        <SimpleGrid columns={4} spacing={6} w="full">
          <Card bg="orange.50" borderColor="orange.200">
            <CardBody>
              <VStack spacing={2}>
                <StatLabel>Total Employees</StatLabel>
                <StatNumber fontSize="2xl">{analytics.totalEmployees.toLocaleString()}</StatNumber>
                <StatHelpText>Active employees</StatHelpText>
              </VStack>
            </CardBody>
          </Card>

          <Card bg="yellow.50" borderColor="yellow.200">
            <CardBody>
              <VStack spacing={2}>
                <StatLabel>Pending Time Off</StatLabel>
                <StatNumber fontSize="2xl">{analytics.pendingTimeOff}</StatNumber>
                <StatHelpText>Awaiting approval</StatHelpText>
              </VStack>
            </CardBody>
          </Card>

          <Card bg="green.50" borderColor="green.200">
            <CardBody>
              <VStack spacing={2}>
                <StatLabel>Departments</StatLabel>
                <StatNumber fontSize="2xl">{analytics.departments}</StatNumber>
                <StatHelpText>Active departments</StatHelpText>
              </VStack>
            </CardBody>
          </Card>

          <Card bg="blue.50" borderColor="blue.200">
            <CardBody>
              <VStack spacing={2}>
                <StatLabel>Active Employees</StatLabel>
                <StatNumber fontSize="2xl">{analytics.activeEmployees}</StatNumber>
                <StatHelpText>Currently active</StatHelpText>
              </VStack>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Tabs variant="enclosed" colorScheme="orange">
          <TabList borderBottomWidth={2} borderColor="gray.200">
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <PersonIcon mr={2} /> Employees
            </Tab>
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <CalendarIcon mr={2} /> Time Off
            </Tab>
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <SettingsIcon mr={2} /> Company
            </Tab>
          </TabList>

          <TabPanels>
            {/* Employees Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Heading size="lg">Employee Directory</Heading>
                  <Button
                    colorScheme="orange"
                    onClick={() => setIsEmployeeModalOpen(true)}
                    leftIcon={<PersonIcon />}
                  >
                    Add Employee
                  </Button>
                </HStack>

                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Name</Th>
                        <Th>Email</Th>
                        <Th>Department</Th>
                        <Th>Location</Th>
                        <Th>Status</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {employees.map((employee) => (
                        <Tr key={employee.id}>
                          <Td>
                            <HStack spacing={3}>
                              <Avatar
                                name={`${employee.firstName} ${employee.lastName}`}
                                size="sm"
                                bg="orange.100"
                                color="orange.800"
                              >
                                {employee.firstName[0]}{employee.lastName[0]}
                              </Avatar>
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">
                                  {employee.firstName} {employee.lastName}
                                </Text>
                                <Text fontSize="sm" color="gray.600">
                                  {employee.jobTitle}
                                </Text>
                              </VStack>
                            </HStack>
                          </Td>
                          <Td>{employee.workEmail}</Td>
                          <Td>
                            <Badge colorScheme={getDepartmentColor(employee.department || '')}>
                              {employee.department}
                            </Badge>
                          </Td>
                          <Td>{employee.location}</Td>
                          <Td>
                            <Badge colorScheme="green">Active</Badge>
                          </Td>
                          <Td>
                            <HStack spacing={2}>
                              <IconButton
                                size="sm"
                                variant="outline"
                                icon={<EditIcon />}
                                aria-label="Edit employee"
                              />
                            </HStack>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Time Off Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <Heading size="lg">Time Off Management</Heading>
                <Text>Time off functionality coming soon...</Text>
              </VStack>
            </TabPanel>

            {/* Company Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <Heading size="lg">Company Information</Heading>
                <Text>Company management features coming soon...</Text>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>

      {/* Employee Modal */}
      <Modal isOpen={isEmployeeModalOpen} onClose={() => setIsEmployeeModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Add New Employee</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>First Name</FormLabel>
                <Input
                  value={employeeForm.firstName}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, firstName: e.target.value })}
                  placeholder="John"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Last Name</FormLabel>
                <Input
                  value={employeeForm.lastName}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, lastName: e.target.value })}
                  placeholder="Doe"
                />
              </FormControl>
              <FormControl isRequired>
                <FormLabel>Email</FormLabel>
                <Input
                  type="email"
                  value={employeeForm.workEmail}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, workEmail: e.target.value })}
                  placeholder="john.doe@company.com"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Job Title</FormLabel>
                <Input
                  value={employeeForm.jobTitle}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, jobTitle: e.target.value })}
                  placeholder="Software Engineer"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Department</FormLabel>
                <Input
                  value={employeeForm.department}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, department: e.target.value })}
                  placeholder="Engineering"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Location</FormLabel>
                <Input
                  value={employeeForm.location}
                  onChange={(e) => setEmployeeForm({ ...employeeForm, location: e.target.value })}
                  placeholder="San Francisco, CA"
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="ghost"
              mr={3}
              onClick={() => setIsEmployeeModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              colorScheme="orange"
              onClick={() => {
                // Create employee logic here
                setIsEmployeeModalOpen(false);
                toast({
                  title: "Employee Created",
                  description: "Employee created successfully",
                  status: "success",
                  duration: 3000,
                  isClosable: true
                });
              }}
              isLoading={loading}
              isDisabled={!employeeForm.firstName || !employeeForm.lastName || !employeeForm.workEmail}
            >
              Create Employee
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default BambooHRIntegration;