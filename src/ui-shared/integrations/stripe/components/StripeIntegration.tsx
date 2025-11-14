import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Progress,
  Divider,
  useColorModeValue,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Input,
  Select,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Alert,
  AlertIcon,
  Spinner,
  Flex,
  Avatar,
  Tag,
  Switch,
  Textarea,
} from "@chakra-ui/react";
import {
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ArrowForwardIcon,
  PlusSquareIcon,
  // DollarIcon not available, using Star as alternative
  // Note: No money icon available in current version, using Star as placeholder
  StarIcon,
  GenericAvatarIcon as UserIcon,
  SettingsIcon,
  ChevronDownIcon,
  SearchIcon,
  ChevronUpIcon,
} from "@chakra-ui/icons";

interface StripePayment {
  id: string;
  amount: number;
  currency: string;
  status: "succeeded" | "failed" | "pending";
  customer: string;
  description: string;
  created: string;
  receipt_url?: string;
  metadata?: Record<string, string>;
}

interface StripeCustomer {
  id: string;
  email: string;
  name: string;
  description?: string;
  created: string;
  balance: number;
  currency: string;
  default_source?: string;
  metadata?: Record<string, string>;
}

interface StripeSubscription {
  id: string;
  customer: string;
  status: "active" | "canceled" | "past_due" | "unpaid";
  current_period_start: string;
  current_period_end: string;
  items: Array<{
    price: {
      product: string;
      unit_amount: number;
      currency: string;
    };
    quantity: number;
  }>;
  metadata?: Record<string, string>;
}

interface StripeProduct {
  id: string;
  name: string;
  description: string;
  active: boolean;
  metadata?: Record<string, string>;
  created: string;
}

interface StripeAnalytics {
  totalRevenue: number;
  monthlyRecurringRevenue: number;
  activeCustomers: number;
  totalPayments: number;
  paymentSuccessRate: number;
  averageOrderValue: number;
  revenueGrowth: number;
  customerGrowth: number;
}

const StripeIntegration: React.FC = () => {
  const [payments, setPayments] = useState<StripePayment[]>([]);
  const [customers, setCustomers] = useState<StripeCustomer[]>([]);
  const [subscriptions, setSubscriptions] = useState<StripeSubscription[]>([]);
  const [products, setProducts] = useState<StripeProduct[]>([]);
  const [analytics, setAnalytics] = useState<StripeAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [isCreatePaymentOpen, setIsCreatePaymentOpen] = useState(false);
  const [isCreateCustomerOpen, setIsCreateCustomerOpen] = useState(false);
  const [isCreateProductOpen, setIsCreateProductOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Mock data for demonstration
  const mockPayments: StripePayment[] = [
    {
      id: "pi_1Jk123456789",
      amount: 2500,
      currency: "usd",
      status: "succeeded",
      customer: "cus_LKJ123456",
      description: "Monthly subscription payment",
      created: "2024-01-15T10:30:00Z",
      receipt_url: "https://receipt.stripe.com/test",
      metadata: { invoice_id: "inv_12345" },
    },
    {
      id: "pi_1Jk987654321",
      amount: 4999,
      currency: "usd",
      status: "succeeded",
      customer: "cus_MNB456789",
      description: "One-time purchase",
      created: "2024-01-14T14:20:00Z",
      receipt_url: "https://receipt.stripe.com/test",
      metadata: { order_id: "ord_67890" },
    },
    {
      id: "pi_1Jk555555555",
      amount: 1500,
      currency: "usd",
      status: "failed",
      customer: "cus_XYZ789012",
      description: "Failed payment attempt",
      created: "2024-01-13T09:15:00Z",
    },
  ];

  const mockCustomers: StripeCustomer[] = [
    {
      id: "cus_LKJ123456",
      email: "premium@example.com",
      name: "Premium Customer",
      description: "Enterprise plan subscriber",
      created: "2024-01-10T08:00:00Z",
      balance: 0,
      currency: "usd",
      metadata: { company: "ACME Corp", tier: "enterprise" },
    },
    {
      id: "cus_MNB456789",
      email: "standard@example.com",
      name: "Standard Customer",
      description: "Basic plan subscriber",
      created: "2024-01-09T11:30:00Z",
      balance: 0,
      currency: "usd",
      metadata: { company: "Startup Inc", tier: "basic" },
    },
    {
      id: "cus_XYZ789012",
      email: "trial@example.com",
      name: "Trial User",
      description: "Free trial period",
      created: "2024-01-08T16:45:00Z",
      balance: 0,
      currency: "usd",
      metadata: { company: "Test Corp", tier: "trial" },
    },
  ];

  const mockSubscriptions: StripeSubscription[] = [
    {
      id: "sub_ABC123456",
      customer: "cus_LKJ123456",
      status: "active",
      current_period_start: "2024-01-01T00:00:00Z",
      current_period_end: "2024-02-01T00:00:00Z",
      items: [
        {
          price: {
            product: "prod_ENTERPRISE",
            unit_amount: 2500,
            currency: "usd",
          },
          quantity: 1,
        },
      ],
      metadata: { plan: "enterprise", billing_cycle: "monthly" },
    },
    {
      id: "sub_DEF789012",
      customer: "cus_MNB456789",
      status: "active",
      current_period_start: "2024-01-01T00:00:00Z",
      current_period_end: "2024-02-01T00:00:00Z",
      items: [
        {
          price: {
            product: "prod_BASIC",
            unit_amount: 999,
            currency: "usd",
          },
          quantity: 1,
        },
      ],
      metadata: { plan: "basic", billing_cycle: "monthly" },
    },
  ];

  const mockProducts: StripeProduct[] = [
    {
      id: "prod_ENTERPRISE",
      name: "Enterprise Plan",
      description: "Full feature access with premium support",
      active: true,
      created: "2024-01-01T00:00:00Z",
      metadata: { features: "all", support: "premium" },
    },
    {
      id: "prod_BASIC",
      name: "Basic Plan",
      description: "Essential features for small businesses",
      active: true,
      created: "2024-01-01T00:00:00Z",
      metadata: { features: "essential", support: "standard" },
    },
    {
      id: "prod_PREMIUM",
      name: "Premium Plan",
      description: "Advanced features with priority support",
      active: false,
      created: "2024-01-01T00:00:00Z",
      metadata: { features: "advanced", support: "priority" },
    },
  ];

  const mockAnalytics: StripeAnalytics = {
    totalRevenue: 125000,
    monthlyRecurringRevenue: 85000,
    activeCustomers: 245,
    totalPayments: 312,
    paymentSuccessRate: 98.5,
    averageOrderValue: 401.28,
    revenueGrowth: 15.2,
    customerGrowth: 8.7,
  };

  const loadStripeData = async () => {
    setLoading(true);
    try {
      // In a real implementation, these would be API calls
      await new Promise((resolve) => setTimeout(resolve, 1000));

      setPayments(mockPayments);
      setCustomers(mockCustomers);
      setSubscriptions(mockSubscriptions);
      setProducts(mockProducts);
      setAnalytics(mockAnalytics);

      toast({
        title: "Stripe data loaded",
        status: "success",
        duration: 2000,
      });
    } catch (error) {
      toast({
        title: "Failed to load Stripe data",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  const createPayment = async (paymentData: any) => {
    try {
      // In a real implementation, this would be an API call
      const newPayment: StripePayment = {
        id: `pi_${Math.random().toString(36).substr(2, 9)}`,
        ...paymentData,
        status: "succeeded",
        created: new Date().toISOString(),
        receipt_url: "https://receipt.stripe.com/test",
      };

      setPayments((prev) => [newPayment, ...prev]);
      setIsCreatePaymentOpen(false);

      toast({
        title: "Payment created successfully",
        status: "success",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Failed to create payment",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createCustomer = async (customerData: any) => {
    try {
      // In a real implementation, this would be an API call
      const newCustomer: StripeCustomer = {
        id: `cus_${Math.random().toString(36).substr(2, 9)}`,
        ...customerData,
        balance: 0,
        currency: "usd",
        created: new Date().toISOString(),
      };

      setCustomers((prev) => [newCustomer, ...prev]);
      setIsCreateCustomerOpen(false);

      toast({
        title: "Customer created successfully",
        status: "success",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Failed to create customer",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createProduct = async (productData: any) => {
    try {
      // In a real implementation, this would be an API call
      const newProduct: StripeProduct = {
        id: `prod_${Math.random().toString(36).substr(2, 9)}`,
        ...productData,
        active: true,
        created: new Date().toISOString(),
      };

      setProducts((prev) => [newProduct, ...prev]);
      setIsCreateProductOpen(false);

      toast({
        title: "Product created successfully",
        status: "success",
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: "Failed to create product",
        status: "error",
        duration: 3000,
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "succeeded":
      case "active":
        return "green";
      case "failed":
      case "canceled":
      case "unpaid":
        return "red";
      case "pending":
      case "past_due":
        return "yellow";
      default:
        return "gray";
    }
  };

  const formatCurrency = (amount: number, currency: string = "usd") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(amount / 100);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const filteredPayments = payments.filter((payment) => {
    const matchesSearch =
      payment.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      payment.customer.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || payment.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  useEffect(() => {
    loadStripeData();
  }, []);

  if (loading && payments.length === 0) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minH="400px"
      >
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading Stripe integration...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <Heading size="2xl">Stripe Integration</Heading>
          <Text color="gray.600" fontSize="lg">
            Complete payment processing and financial management
          </Text>
        </VStack>

        {/* Quick Stats */}
        {analytics && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Revenue</StatLabel>
                  <StatNumber>
                    {formatCurrency(analytics.totalRevenue)}
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow
                      type={
                        analytics.revenueGrowth > 0 ? "increase" : "decrease"
                      }
                    />
                    {Math.abs(analytics.revenueGrowth)}%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Monthly Recurring</StatLabel>
                  <StatNumber>
                    {formatCurrency(analytics.monthlyRecurringRevenue)}
                  </StatNumber>
                  <StatHelpText>Active subscriptions</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Active Customers</StatLabel>
                  <StatNumber>{analytics.activeCustomers}</StatNumber>
                  <StatHelpText>
                    <StatArrow
                      type={
                        analytics.customerGrowth > 0 ? "increase" : "decrease"
                      }
                    />
                    {Math.abs(analytics.customerGrowth)}%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Success Rate</StatLabel>
                  <StatNumber>{analytics.paymentSuccessRate}%</StatNumber>
                  <StatHelpText>
                    Of {analytics.totalPayments} payments
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Card>
          <CardHeader>
            <Tabs variant="enclosed" onChange={setActiveTab}>
              <TabList>
                <Tab>Payments</Tab>
                <Tab>Customers</Tab>
                <Tab>Subscriptions</Tab>
                <Tab>Products</Tab>
                <Tab>Analytics</Tab>
              </TabList>
            </Tabs>
          </CardHeader>

          <CardBody>
            <TabPanels>
              {/* Payments Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <HStack justify="space-between">
                    <Heading size="lg">Payment Management</Heading>
                    <Button
                      colorScheme="blue"
                      leftIcon={<PlusSquareIcon />}
                      onClick={() => setIsCreatePaymentOpen(true)}
                    >
                      Create Payment
                    </Button>
                  </HStack>

                  <HStack spacing={4}>
                    <Input
                      placeholder="Search payments..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    <Select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      width="200px"
                    >
                      <option value="all">All Status</option>
                      <option value="succeeded">Succeeded</option>
                      <option value="failed">Failed</option>
                      <option value="pending">Pending</option>
                    </Select>
                  </HStack>

                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>ID</Th>
                        <Th>Amount</Th>
                        <Th>Customer</Th>
                        <Th>Description</Th>
                        <Th>Status</Th>
                        <Th>Date</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {filteredPayments.map((payment) => (
                        <Tr key={payment.id}>
                          <Td>
                            <Text fontSize="sm" fontFamily="mono">
                              {payment.id.substring(0, 12)}...
                            </Text>
                          </Td>
                          <Td>{formatCurrency(payment.amount)}</Td>
                          <Td>
                            {payment.customer ? (
                              <HStack spacing={2}>
                                <Avatar
                                  size="xs"
                                  src={payment.customer.avatar_url}
                                />
                                <Text fontSize="sm">
                                  {payment.customer.name}
                                </Text>
                              </HStack>
                            ) : (
                              <Text color="gray.500">Anonymous</Text>
                            )}
                          </Td>
                          <Td>
                            <Text fontSize="sm" noOfLines={2}>
                              {payment.description}
                            </Text>
                          </Td>
                          <Td>
                            <Badge
                              colorScheme={
                                payment.status === "succeeded"
                                  ? "green"
                                  : payment.status === "failed"
                                    ? "red"
                                    : "yellow"
                              }
                            >
                              {payment.status}
                            </Badge>
                          </Td>
                          <Td>{formatDate(payment.created)}</Td>
                          <Td>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                window.open(payment.receipt_url, "_blank")
                              }
                            >
                              Receipt
                            </Button>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </VStack>
              </TabPanel>

              {/* Customers Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <HStack justify="space-between">
                    <Heading size="lg">Customer Management</Heading>
                    <Button
                      colorScheme="blue"
                      leftIcon={<PlusSquareIcon />}
                      onClick={() => setIsCreateCustomerOpen(true)}
                    >
                      Add Customer
                    </Button>
                  </HStack>

                  <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                    {customers.map((customer) => (
                      <Card key={customer.id}>
                        <CardBody>
                          <VStack spacing={4} align="start">
                            <HStack spacing={3} w="full">
                              <Avatar size="md" src={customer.avatar_url} />
                              <VStack align="start" spacing={0}>
                                <Heading size="md">{customer.name}</Heading>
                                <Text color="gray.600" fontSize="sm">
                                  {customer.email}
                                </Text>
                              </VStack>
                            </HStack>

                            <VStack spacing={2} align="start" w="full">
                              <HStack justify="space-between" w="full">
                                <Text fontWeight="medium">Balance:</Text>
                                <Text>{formatCurrency(customer.balance)}</Text>
                              </HStack>
                              <HStack justify="space-between" w="full">
                                <Text fontWeight="medium">Subscriptions:</Text>
                                <Text>{customer.subscriptions_count}</Text>
                              </HStack>
                              <HStack justify="space-between" w="full">
                                <Text fontWeight="medium">Created:</Text>
                                <Text fontSize="sm">
                                  {formatDate(customer.created)}
                                </Text>
                              </HStack>
                            </VStack>

                            <Button
                              size="sm"
                              colorScheme="blue"
                              variant="outline"
                              w="full"
                              onClick={() => setSelectedCustomer(customer)}
                            >
                              View Details
                            </Button>
                          </VStack>
                        </CardBody>
                      </Card>
                    ))}
                  </SimpleGrid>
                </VStack>
              </TabPanel>

              {/* Subscriptions Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Heading size="lg">Subscription Management</Heading>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Plan</Th>
                        <Th>Customer</Th>
                        <Th>Status</Th>
                        <Th>Amount</Th>
                        <Th>Next Payment</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {subscriptions.map((subscription) => (
                        <Tr key={subscription.id}>
                          <Td>
                            <Text fontWeight="medium">
                              {subscription.plan_name}
                            </Text>
                            <Text fontSize="sm" color="gray.600">
                              {subscription.plan_description}
                            </Text>
                          </Td>
                          <Td>
                            <HStack spacing={2}>
                              <Avatar
                                size="xs"
                                src={subscription.customer.avatar_url}
                              />
                              <Text fontSize="sm">
                                {subscription.customer.name}
                              </Text>
                            </HStack>
                          </Td>
                          <Td>
                            <Badge
                              colorScheme={
                                subscription.status === "active"
                                  ? "green"
                                  : subscription.status === "canceled"
                                    ? "red"
                                    : "yellow"
                              }
                            >
                              {subscription.status}
                            </Badge>
                          </Td>
                          <Td>{formatCurrency(subscription.amount)}</Td>
                          <Td>{formatDate(subscription.next_payment_date)}</Td>
                          <Td>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                handleSubscriptionAction(subscription)
                              }
                            >
                              Manage
                            </Button>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </VStack>
              </TabPanel>

              {/* Products Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <HStack justify="space-between">
                    <Heading size="lg">Product Catalog</Heading>
                    <Button
                      colorScheme="blue"
                      leftIcon={<PlusSquareIcon />}
                      onClick={() => setIsCreateProductOpen(true)}
                    >
                      Add Product
                    </Button>
                  </HStack>

                  <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                    {products.map((product) => (
                      <Card key={product.id}>
                        <CardBody>
                          <VStack spacing={4} align="start">
                            {product.images && product.images.length > 0 && (
                              <Box
                                as="img"
                                src={product.images[0]}
                                alt={product.name}
                                w="full"
                                h="120px"
                                objectFit="cover"
                                borderRadius="md"
                              />
                            )}
                            <VStack spacing={2} align="start" w="full">
                              <Heading size="md">{product.name}</Heading>
                              <Text color="gray.600" noOfLines={3}>
                                {product.description}
                              </Text>
                            </VStack>

                            <HStack justify="space-between" w="full">
                              <Text fontWeight="bold">
                                {formatCurrency(product.price)}
                              </Text>
                              <Badge
                                colorScheme={product.active ? "green" : "red"}
                              >
                                {product.active ? "Active" : "Inactive"}
                              </Badge>
                            </HStack>

                            <Button
                              size="sm"
                              colorScheme="blue"
                              variant="outline"
                              w="full"
                              onClick={() => setSelectedProduct(product)}
                            >
                              Edit Product
                            </Button>
                          </VStack>
                        </CardBody>
                      </Card>
                    ))}
                  </SimpleGrid>
                </VStack>
              </TabPanel>

              {/* Analytics Tab */}
              <TabPanel>
                <VStack spacing={6} align="stretch">
                  <Heading size="lg">Financial Analytics</Heading>
                  <Text color="gray.600">
                    Detailed analytics and insights for your Stripe account
                  </Text>
                  <Card>
                    <CardBody>
                      <VStack spacing={4} align="center">
                        <Text fontSize="lg" fontWeight="medium">
                          Analytics Dashboard
                        </Text>
                        <Text color="gray.600" textAlign="center">
                          Financial analytics and insights will be displayed
                          here. This feature is currently under development.
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                </VStack>
              </TabPanel>
            </TabPanels>
          </CardBody>
        </Card>

        {/* Create Payment Modal */}
        <Modal
          isOpen={isCreatePaymentOpen}
          onClose={() => setIsCreatePaymentOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create Payment</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Amount</FormLabel>
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={newPaymentAmount}
                    onChange={(e) => setNewPaymentAmount(e.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Currency</FormLabel>
                  <Select
                    value={newPaymentCurrency}
                    onChange={(e) => setNewPaymentCurrency(e.target.value)}
                  >
                    <option value="usd">USD</option>
                    <option value="eur">EUR</option>
                    <option value="gbp">GBP</option>
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    placeholder="Payment description..."
                    value={newPaymentDescription}
                    onChange={(e) => setNewPaymentDescription(e.target.value)}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsCreatePaymentOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() =>
                  createPayment(
                    parseFloat(newPaymentAmount),
                    newPaymentCurrency,
                    newPaymentDescription,
                  )
                }
                isDisabled={!newPaymentAmount}
              >
                Create Payment
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Customer Modal */}
        <Modal
          isOpen={isCreateCustomerOpen}
          onClose={() => setIsCreateCustomerOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add Customer</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Name</FormLabel>
                  <Input
                    placeholder="Customer name"
                    value={newCustomerName}
                    onChange={(e) => setNewCustomerName(e.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Email</FormLabel>
                  <Input
                    type="email"
                    placeholder="customer@example.com"
                    value={newCustomerEmail}
                    onChange={(e) => setNewCustomerEmail(e.target.value)}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsCreateCustomerOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() =>
                  createCustomer(newCustomerName, newCustomerEmail)
                }
                isDisabled={!newCustomerName || !newCustomerEmail}
              >
                Add Customer
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Product Modal */}
        <Modal
          isOpen={isCreateProductOpen}
          onClose={() => setIsCreateProductOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add Product</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Product Name</FormLabel>
                  <Input
                    placeholder="Product name"
                    value={newProductName}
                    onChange={(e) => setNewProductName(e.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    placeholder="Product description"
                    value={newProductDescription}
                    onChange={(e) => setNewProductDescription(e.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Price</FormLabel>
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={newProductPrice}
                    onChange={(e) => setNewProductPrice(e.target.value)}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsCreateProductOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() =>
                  createProduct(
                    newProductName,
                    newProductDescription,
                    parseFloat(newProductPrice),
                  )
                }
                isDisabled={!newProductName || !newProductPrice}
              >
                Add Product
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default StripeIntegration;
