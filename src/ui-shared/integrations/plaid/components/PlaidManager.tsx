/**
 * ATOM Plaid Manager Component
 * Complete financial services UI management for ATOM's Plaid integration
 * Real-time banking data sync, transaction analytics, and financial insights
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, VStack, HStack, Heading, Text, Button, Card, CardBody, CardHeader,
  Tabs, TabList, TabPanels, Tab, TabPanel, Alert, AlertIcon, Badge,
  Progress, Stat, StatLabel, StatNumber, StatHelpText, Divider, FormControl,
  FormLabel, Switch, NumberInput, NumberInputField, NumberInputStepper,
  NumberIncrementStepper, NumberDecrementStepper, Input, Textarea, Modal,
  ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton,
  useDisclosure, useToast, SimpleGrid, Table, Thead, Tbody, Tr, Th, Td,
  TableContainer, Icon, Spinner, Center, Flex, Spacer, useColorModeValue,
  Tooltip, IconButton, Menu, MenuButton, MenuList, MenuItem, Tag,
  TagLabel, TagCloseButton, Accordion, AccordionItem, AccordionButton,
  AccordionPanel, AccordionIcon, Checkbox, Select, Link, Radio, RadioGroup,
  Stack, AlertTitle, AlertDescription, List, ListItem, ListIcon,
} from '@chakra-ui/react';
import {
  FiCreditCard, FiDollarSign, FiTrendingUp, FiTrendingDown,
  FiRefreshCw, FiSettings, FiDatabase, FiZap, FiClock,
  FiActivity, FiShield, FiCheck, FiX, FiAlertTriangle,
  FiFileText, FiPieChart, FiBarChart, FiSearch, FiFilter,
  FiGrid, FiList, FiPlay, FiPause, FiStop, FiDownload,
  FiUpload, FiCalendar, FiEye, FiEdit, FiTrash2, FiCopy,
  FiExternalLink, FiLock, FiUnlock, FiInfo, FiWifi,
  FiWifiOff, FiCpu, FiHardDrive, FiCloud, FiPlus,
  FiMinus, FiMoreVertical, FiArrowUp, FiArrowDown,
  FiChevronDown, FiChevronUp, FiChevronLeft, FiChevronRight,
  FiSkipBack, FiSkipForward, FiRepeat, FiShuffle, FiUser,
} from 'react-icons/fi';

import {
  PlaidAccount,
  PlaidTransaction,
  PlaidSpendingAnalytics,
  PlaidAccountSummary,
  AtomPlaidIngestionConfig,
  PLAID_DEFAULT_CONFIG,
} from '../types';

interface PlaidManagerProps {
  accessToken?: string;
  itemId?: string;
  environment?: 'sandbox' | 'development' | 'production';
  clientId?: string;
  atomIngestionPipeline?: any;
  atomSkillRegistry?: any;
  initialConfig?: Partial<AtomPlaidIngestionConfig>;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  onReady?: (manager: any) => void;
  onError?: (error: any) => void;
  onSyncStart?: (config: any) => void;
  onSyncComplete?: (results: any) => void;
  onSyncProgress?: (progress: any) => void;
}

interface SyncSession {
  id: string;
  startTime: string;
  status: 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: {
    total: number;
    processed: number;
    percentage: number;
    currentItem?: string;
    errors: number;
    warnings: number;
  };
  results?: any;
  error?: string;
}

export const PlaidManager: React.FC<PlaidManagerProps> = ({
  accessToken,
  itemId,
  environment = 'sandbox',
  atomIngestionPipeline,
  atomSkillRegistry,
  initialConfig,
  onReady,
  onError,
  onSyncStart,
  onSyncComplete,
  onSyncProgress,
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [currentSyncSession, setCurrentSyncSession] = useState<SyncSession | null>(null);
  
  // Data State
  const [accounts, setAccounts] = useState<PlaidAccount[]>([]);
  const [transactions, setTransactions] = useState<PlaidTransaction[]>([]);
  const [analytics, setAnalytics] = useState<PlaidSpendingAnalytics | null>(null);
  const [accountSummary, setAccountSummary] = useState<PlaidAccountSummary | null>(null);
  const [selectedAccount, setSelectedAccount] = useState<PlaidAccount | null>(null);
  const [selectedTransactions, setSelectedTransactions] = useState<string[]>([]);
  
  // Configuration
  const [currentConfig, setCurrentConfig] = useState<AtomPlaidIngestionConfig>(
    () => ({ ...PLAID_DEFAULT_CONFIG, ...initialConfig })
  );
  const [configModalOpen, setConfigModalOpen] = useState(false);
  
  // UI State
  const [searchQuery, setSearchQuery] = useState('');
  const [transactionFilter, setTransactionFilter] = useState({
    dateRange: { start: '', end: '' },
    categories: [],
    amountRange: { min: null, max: null },
  });
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const toast = useToast();

  // Theme colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Initialize Plaid connection
  useEffect(() => {
    if (accessToken && itemId) {
      initializePlaid();
    }
  }, [accessToken, itemId]);

  const initializePlaid = useCallback(async () => {
    setIsLoading(true);
    try {
      // Simulate Plaid connection
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      setIsConnected(true);
      
      // Load initial data
      await loadDashboardData();
      
      // Register skills with ATOM
      if (atomSkillRegistry) {
        try {
          // This would register the Plaid skills
          toast({
            title: 'Skills Registered',
            description: 'Plaid skills registered with ATOM',
            status: 'success',
            duration: 3000,
          });
        } catch (skillError) {
          console.warn('Failed to register skills:', skillError);
        }
      }
      
      onReady?.({ 
        isConnected: true, 
        hasAccounts: accounts.length > 0,
        totalAccounts: accounts.length,
      });
      
    } catch (error) {
      setIsConnected(false);
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: 'Failed to connect to Plaid services',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, itemId, atomSkillRegistry, onError, onReady]);

  const loadDashboardData = useCallback(async () => {
    try {
      // Simulate data loading - replace with actual Plaid API calls
      const [accountsData, transactionsData, analyticsData, summaryData] = await Promise.all([
        simulatePlaidAccounts(),
        simulatePlaidTransactions(),
        simulatePlaidAnalytics(),
        simulatePlaidAccountSummary(),
      ]);

      setAccounts(accountsData);
      setTransactions(transactionsData);
      setAnalytics(analyticsData);
      setAccountSummary(summaryData);
      
    } catch (error) {
      onError?.(error);
      toast({
        title: 'Data Load Failed',
        description: 'Failed to load financial data',
        status: 'error',
        duration: 5000,
      });
    }
  }, [onError]);

  // Start sync
  const handleStartSync = useCallback(async () => {
    if (!isConnected) {
      toast({
        title: 'Not Connected',
        description: 'Please connect to Plaid first',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setIsSyncing(true);
    const sessionId = `sync_${Date.now()}`;
    
    const session: SyncSession = {
      id: sessionId,
      startTime: new Date().toISOString(),
      status: 'running',
      progress: {
        total: transactions.length,
        processed: 0,
        percentage: 0,
        currentItem: '',
        errors: 0,
        warnings: 0,
      },
    };

    setCurrentSyncSession(session);
    onSyncStart?.(session);

    try {
      // Simulate sync process
      for (let i = 0; i < transactions.length; i++) {
        if (session.status === 'paused') {
          await new Promise(resolve => setTimeout(resolve, 1000));
          continue;
        }
        
        if (session.status === 'cancelled' || session.status === 'failed') {
          break;
        }

        const transaction = transactions[i];
        session.progress.processed = i + 1;
        session.progress.percentage = ((i + 1) / transactions.length) * 100;
        session.progress.currentItem = transaction.name;
        
        setCurrentSyncSession({ ...session });
        onSyncProgress?.(session);
        
        // Simulate processing time
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      session.status = 'completed';
      setCurrentSyncSession(null);
      onSyncComplete?.(session);
      
      toast({
        title: 'Sync Completed',
        description: `Successfully synced ${transactions.length} transactions`,
        status: 'success',
        duration: 3000,
      });
      
      // Reload data
      await loadDashboardData();
      
    } catch (error) {
      session.status = 'failed';
      session.error = error instanceof Error ? error.message : 'Sync failed';
      setCurrentSyncSession(null);
      onError?.(error);
      
      toast({
        title: 'Sync Failed',
        description: session.error,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSyncing(false);
    }
  }, [isConnected, transactions, onSyncStart, onSyncProgress, onSyncComplete, onError, loadDashboardData]);

  // Pause sync
  const handlePauseSync = useCallback(() => {
    if (currentSyncSession) {
      currentSyncSession.status = 'paused';
      setCurrentSyncSession({ ...currentSyncSession });
    }
  }, [currentSyncSession]);

  // Resume sync
  const handleResumeSync = useCallback(() => {
    if (currentSyncSession) {
      currentSyncSession.status = 'running';
      setCurrentSyncSession({ ...currentSyncSession });
    }
  }, [currentSyncSession]);

  // Cancel sync
  const handleCancelSync = useCallback(() => {
    if (currentSyncSession) {
      currentSyncSession.status = 'cancelled';
      setCurrentSyncSession({ ...currentSyncSession });
      setIsSyncing(false);
      setCurrentSyncSession(null);
    }
  }, [currentSyncSession]);

  // Execute skill
  const handleExecuteSkill = useCallback(async (skillId: string) => {
    if (!atomSkillRegistry) {
      toast({
        title: 'Skill Registry Not Available',
        description: 'ATOM skill registry is not configured',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    try {
      // This would execute the actual skill
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      toast({
        title: 'Skill Executed',
        description: `${skillId} completed successfully`,
        status: 'success',
        duration: 3000,
      });
      
      // Refresh data
      await loadDashboardData();
      
    } catch (error) {
      onError?.(error);
      toast({
        title: 'Skill Execution Failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  }, [atomSkillRegistry, onError, loadDashboardData]);

  // Format utilities
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(Math.abs(amount));
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  // Simulate functions (replace with actual Plaid API calls)
  const simulatePlaidAccounts = async (): Promise<PlaidAccount[]> => {
    return [
      {
        account_id: 'acc_1',
        balances: { current: 15000, available: 12000, limit: null },
        mask: '1234',
        name: 'Checking Account',
        official_name: 'Chase Checking',
        subtype: ['checking'],
        type: 'depository',
        verification_status: null,
      },
      {
        account_id: 'acc_2',
        balances: { current: -2500, available: 5000, limit: 10000 },
        mask: '5678',
        name: 'Credit Card',
        official_name: 'Chase Sapphire',
        subtype: ['credit card'],
        type: 'credit',
        verification_status: null,
      },
      {
        account_id: 'acc_3',
        balances: { current: 85000, available: 80000, limit: null },
        mask: '9012',
        name: 'Savings Account',
        official_name: 'Ally Savings',
        subtype: ['savings'],
        type: 'depository',
        verification_status: null,
      },
    ];
  };

  const simulatePlaidTransactions = async (): Promise<PlaidTransaction[]> => {
    const transactions: PlaidTransaction[] = [];
    const categories = ['Food and Drink', 'Shops', 'Transfer', 'Travel', 'Payment', 'Income'];
    const merchants = ['Starbucks', 'Amazon', 'Walmart', 'Target', 'Uber', 'Netflix', 'Salary Deposit'];
    
    for (let i = 0; i < 100; i++) {
      const date = new Date();
      date.setDate(date.getDate() - Math.floor(Math.random() * 90));
      
      const merchant = merchants[Math.floor(Math.random() * merchants.length)];
      const category = categories[Math.floor(Math.random() * categories.length)];
      const isIncome = merchant === 'Salary Deposit';
      
      transactions.push({
        transaction_id: `txn_${i}`,
        pending: Math.random() < 0.1,
        amount: isIncome ? (Math.random() * 3000 + 2000) : -(Math.random() * 200 + 10),
        iso_currency_code: 'USD',
        category: [category],
        category_id: `cat_${Math.floor(Math.random() * 100)}`,
        date: date.toISOString().split('T')[0],
        name: merchant,
        merchant_name: merchant,
        payment_channel: 'online',
        account_id: `acc_${Math.floor(Math.random() * 3) + 1}`,
      });
    }
    
    return transactions.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  };

  const simulatePlaidAnalytics = async (): Promise<PlaidSpendingAnalytics> => {
    return {
      total_spending: 4500,
      total_income: 7500,
      net_amount: 3000,
      spending_by_category: [
        { category: 'Food and Drink', amount: 1200, percentage: 26.7, transaction_count: 45 },
        { category: 'Shops', amount: 2000, percentage: 44.4, transaction_count: 25 },
        { category: 'Travel', amount: 800, percentage: 17.8, transaction_count: 8 },
        { category: 'Payment', amount: 500, percentage: 11.1, transaction_count: 15 },
      ],
      income_by_source: [
        { source: 'Salary', amount: 7000, percentage: 93.3 },
        { source: 'Investment', amount: 500, percentage: 6.7 },
      ],
      monthly_trends: [
        { month: '2024-01', income: 7500, spending: 4200, net: 3300 },
        { month: '2024-02', income: 7500, spending: 4800, net: 2700 },
        { month: '2024-03', income: 7500, spending: 4500, net: 3000 },
      ],
      top_merchants: [
        { merchant_name: 'Amazon', amount: 850, transaction_count: 12 },
        { merchant_name: 'Starbucks', amount: 320, transaction_count: 20 },
        { merchant_name: 'Walmart', amount: 650, transaction_count: 8 },
      ],
      recurring_transactions: [
        { name: 'Netflix', amount: 15.99, frequency: 'monthly', next_expected: '2024-02-01' },
        { name: 'Gym Membership', amount: 50.00, frequency: 'monthly', next_expected: '2024-02-01' },
        { name: 'Internet', amount: 79.99, frequency: 'monthly', next_expected: '2024-02-01' },
      ],
    };
  };

  const simulatePlaidAccountSummary = async (): Promise<PlaidAccountSummary> => {
    return {
      total_balance: 97500,
      available_balance: 87000,
      total_assets: 100000,
      total_liabilities: 2500,
      net_worth: 97500,
      accounts: [
        { id: 'acc_1', name: 'Checking Account', type: 'depository', balance: 15000, available_balance: 12000 },
        { id: 'acc_2', name: 'Credit Card', type: 'credit', balance: -2500, available_balance: 7500 },
        { id: 'acc_3', name: 'Savings Account', type: 'depository', balance: 85000, available_balance: 80000 },
      ],
    };
  };

  // Render loading state
  if (isLoading) {
    return (
      <Center minH="400px">
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Initializing Plaid Manager...</Text>
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
            <Icon as={FiCreditCard} boxSize={8} color="blue.500" />
            <VStack align="start" spacing={0}>
              <Heading size="lg">Plaid Manager</Heading>
              <Text fontSize="sm" color="gray.500">
                ATOM Financial Services Integration
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Badge
              colorScheme={isConnected ? 'green' : 'red'}
              variant={isConnected ? 'solid' : 'outline'}
            >
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
            
            {currentSyncSession && (
              <Badge colorScheme="blue" variant="solid">
                {currentSyncSession.status}
              </Badge>
            )}
            
            <Button
              leftIcon={<FiRefreshCw />}
              onClick={loadDashboardData}
              isLoading={isLoading}
              variant="outline"
              size="sm"
            >
              Refresh
            </Button>

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

        {/* Connection Status */}
        <Alert status={isConnected ? 'success' : 'warning'}>
          <AlertIcon />
          <Box flex="1">
            <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
            <AlertDescription>
              {isConnected 
                ? 'Plaid financial services are connected and ready for use'
                : 'Configure Plaid credentials to access banking services'
              }
            </AlertDescription>
          </Box>
          {!isConnected && (
            <Button colorScheme="blue" size="sm" onClick={initializePlaid}>
              Connect
            </Button>
          )}
        </Alert>

        {/* Current Sync Session */}
        {currentSyncSession && (
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Active Sync Session</Heading>
                <Badge colorScheme={
                  currentSyncSession.status === 'running' ? 'green' :
                  currentSyncSession.status === 'paused' ? 'yellow' :
                  currentSyncSession.status === 'completed' ? 'blue' : 'red'
                }>
                  {currentSyncSession.status}
                </Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <Progress
                  value={currentSyncSession.progress.percentage}
                  colorScheme="blue"
                  size="lg"
                  hasStripe
                  isAnimated
                />
                
                <HStack justify="space-between">
                  <Text fontSize="sm">
                    {currentSyncSession.progress.processed} / {currentSyncSession.progress.total} items
                  </Text>
                  <Text fontSize="sm">
                    {currentSyncSession.progress.currentItem || 'Processing...'}
                  </Text>
                </HStack>
                
                <SimpleGrid columns={3} spacing={4}>
                  <Stat>
                    <StatLabel fontSize="sm">Processed</StatLabel>
                    <StatNumber fontSize="xl">{currentSyncSession.progress.processed}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel fontSize="sm">Errors</StatLabel>
                    <StatNumber fontSize="xl" color="red.500">{currentSyncSession.progress.errors}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel fontSize="sm">Warnings</StatLabel>
                    <StatNumber fontSize="xl" color="yellow.500">{currentSyncSession.progress.warnings}</StatNumber>
                  </Stat>
                </SimpleGrid>
                
                <HStack spacing={2}>
                  {currentSyncSession.status === 'running' && (
                    <Button
                      leftIcon={<FiPause />}
                      onClick={handlePauseSync}
                      variant="outline"
                      size="sm"
                    >
                      Pause
                    </Button>
                  )}
                  
                  {currentSyncSession.status === 'paused' && (
                    <Button
                      leftIcon={<FiPlay />}
                      onClick={handleResumeSync}
                      colorScheme="green"
                      size="sm"
                    >
                      Resume
                    </Button>
                  )}
                  
                  <Button
                    leftIcon={<FiStop />}
                    onClick={handleCancelSync}
                    colorScheme="red"
                    size="sm"
                  >
                    Cancel
                  </Button>
                </HStack>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Account Summary Cards */}
        {accountSummary && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Total Balance</StatLabel>
                  <StatNumber fontSize="2xl">
                    {formatCurrency(accountSummary.total_balance)}
                  </StatNumber>
                  <StatHelpText>
                    <Icon as={FiDollarSign} mr={1} />
                    Net Worth: {formatCurrency(accountSummary.net_worth)}
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Available Balance</StatLabel>
                  <StatNumber fontSize="2xl">
                    {formatCurrency(accountSummary.available_balance)}
                  </StatNumber>
                  <StatHelpText>
                    <Icon as={FiHardDrive} mr={1} />
                    Ready to use
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Total Assets</StatLabel>
                  <StatNumber fontSize="2xl">
                    {formatCurrency(accountSummary.total_assets)}
                  </StatNumber>
                  <StatHelpText>
                    <Icon as={FiTrendingUp} mr={1} />
                    Positive holdings
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Total Liabilities</StatLabel>
                  <StatNumber fontSize="2xl">
                    {formatCurrency(accountSummary.total_liabilities)}
                  </StatNumber>
                  <StatHelpText>
                    <Icon as={FiTrendingDown} mr={1} />
                    Outstanding debts
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Tabs 
          value={activeTab}
          onChange={(value) => setActiveTab(value)}
          variant="enclosed"
          colorScheme="blue"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Accounts</Tab>
            <Tab>Transactions</Tab>
            <Tab>Analytics</Tab>
            <Tab>Skills</Tab>
            <Tab>Configuration</Tab>
          </TabList>
          
          <TabPanels>
            {/* Dashboard Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                {analytics && (
                  <Card>
                    <CardHeader>
                      <Heading size="md">Spending Overview</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={4} align="stretch">
                        <HStack justify="space-between">
                          <Text fontWeight="bold">Total Income</Text>
                          <Text color="green.500" fontWeight="bold">
                            {formatCurrency(analytics.total_income)}
                          </Text>
                        </HStack>
                        
                        <HStack justify="space-between">
                          <Text fontWeight="bold">Total Spending</Text>
                          <Text color="red.500" fontWeight="bold">
                            {formatCurrency(analytics.total_spending)}
                          </Text>
                        </HStack>
                        
                        <Divider />
                        
                        <HStack justify="space-between">
                          <Text fontWeight="bold">Net Amount</Text>
                          <Text color={analytics.net_amount >= 0 ? 'green.500' : 'red.500'} fontWeight="bold">
                            {formatCurrency(analytics.net_amount)}
                          </Text>
                        </HStack>
                        
                        <Box>
                          <Text fontWeight="bold" mb={2}>Top Spending Categories</Text>
                          <VStack spacing={2} align="stretch">
                            {analytics.spending_by_category.slice(0, 5).map((category, index) => (
                              <HStack key={index} justify="space-between">
                                <Text fontSize="sm">{category.category}</Text>
                                <HStack>
                                  <Text fontSize="sm" fontWeight="bold">
                                    {formatCurrency(category.amount)}
                                  </Text>
                                  <Badge fontSize="xs" colorScheme="blue">
                                    {category.percentage.toFixed(1)}%
                                  </Badge>
                                </HStack>
                              </HStack>
                            ))}
                          </VStack>
                        </Box>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Accounts Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontSize="lg" fontWeight="bold">Connected Accounts</Text>
                
                {accounts.length > 0 ? (
                  <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                    {accounts.map((account) => (
                      <Card 
                        key={account.account_id}
                        _hover={{ bg: 'gray.50', cursor: 'pointer' }}
                        onClick={() => setSelectedAccount(account)}
                        border={selectedAccount?.account_id === account.account_id ? '2px solid blue.500' : '1px solid gray.200'}
                      >
                        <CardBody>
                          <VStack spacing={2} align="start">
                            <HStack justify="space-between" width="100%">
                              <Text fontWeight="bold">{account.name}</Text>
                              <Badge 
                                colorScheme={account.type === 'depository' ? 'green' : 'orange'}
                                fontSize="xs"
                              >
                                {account.type}
                              </Badge>
                            </HStack>
                            
                            <Text fontSize="sm" color="gray.500">
                              {account.official_name}
                            </Text>
                            
                            <Text fontSize="sm">
                              ****{account.mask}
                            </Text>
                            
                            <HStack justify="space-between" width="100%">
                              <Text fontSize="sm" color="gray.500">Balance</Text>
                              <Text 
                                fontSize="md" 
                                fontWeight="bold"
                                color={account.balances.current >= 0 ? 'green.500' : 'red.500'}
                              >
                                {formatCurrency(account.balances.current)}
                              </Text>
                            </HStack>
                            
                            {account.balances.available !== null && (
                              <HStack justify="space-between" width="100%">
                                <Text fontSize="sm" color="gray.500">Available</Text>
                                <Text fontSize="sm">
                                  {formatCurrency(account.balances.available)}
                                </Text>
                              </HStack>
                            )}
                          </VStack>
                        </CardBody>
                      </Card>
                    ))}
                  </SimpleGrid>
                ) : (
                  <Box textAlign="center" py={10}>
                    <Icon as={FiCreditCard} boxSize={12} color="gray.400" />
                    <Text mt={4} color="gray.500">
                      No accounts connected yet
                    </Text>
                  </Box>
                )}
              </VStack>
            </TabPanel>

            {/* Transactions Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between" align="center">
                  <Text fontSize="lg" fontWeight="bold">Recent Transactions</Text>
                  <HStack spacing={2}>
                    <Button
                      leftIcon={<FiFilter />}
                      variant="outline"
                      size="sm"
                    >
                      Filter
                    </Button>
                    <Button
                      leftIcon={<FiSearch />}
                      variant="outline"
                      size="sm"
                    >
                      Search
                    </Button>
                  </HStack>
                </HStack>
                
                {transactions.length > 0 ? (
                  <TableContainer>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Date</Th>
                          <Th>Description</Th>
                          <Th>Category</Th>
                          <Th>Amount</Th>
                          <Th>Status</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {transactions.slice(0, 20).map((transaction) => (
                          <Tr key={transaction.transaction_id}>
                            <Td>{formatDate(transaction.date)}</Td>
                            <Td>
                              <VStack align="start" spacing={0}>
                                <Text>{transaction.name}</Text>
                                {transaction.merchant_name && (
                                  <Text fontSize="xs" color="gray.500">
                                    {transaction.merchant_name}
                                  </Text>
                                )}
                              </VStack>
                            </Td>
                            <Td>
                              {transaction.category.length > 0 ? (
                                <Badge fontSize="xs" colorScheme="blue">
                                  {transaction.category[0]}
                                </Badge>
                              ) : (
                                <Text fontSize="xs" color="gray.500">Uncategorized</Text>
                              )}
                            </Td>
                            <Td>
                              <Text 
                                color={transaction.amount >= 0 ? 'green.500' : 'red.500'}
                                fontWeight="bold"
                              >
                                {formatCurrency(transaction.amount)}
                              </Text>
                            </Td>
                            <Td>
                              {transaction.pending ? (
                                <Badge colorScheme="yellow" fontSize="xs">Pending</Badge>
                              ) : (
                                <Badge colorScheme="green" fontSize="xs">Completed</Badge>
                              )}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                ) : (
                  <Box textAlign="center" py={10}>
                    <Icon as={FiFileText} boxSize={12} color="gray.400" />
                    <Text mt={4} color="gray.500">
                      No transactions available
                    </Text>
                  </Box>
                )}
              </VStack>
            </TabPanel>

            {/* Analytics Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontSize="lg" fontWeight="bold">Financial Analytics</Text>
                
                {analytics ? (
                  <VStack spacing={6} align="stretch">
                    {/* Spending by Category Chart Placeholder */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Spending by Category</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          {analytics.spending_by_category.map((category, index) => (
                            <Box key={index}>
                              <HStack justify="space-between" mb={1}>
                                <Text>{category.category}</Text>
                                <Text fontWeight="bold">
                                  {formatCurrency(category.amount)} ({category.percentage.toFixed(1)}%)
                                </Text>
                              </HStack>
                              <Progress 
                                value={category.percentage} 
                                colorScheme="blue" 
                                size="sm" 
                              />
                            </Box>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>

                    {/* Recurring Transactions */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Recurring Transactions</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          {analytics.recurring_transactions.map((recurring, index) => (
                            <HStack key={index} justify="space-between">
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="bold">{recurring.name}</Text>
                                <Text fontSize="sm" color="gray.500">
                                  {recurring.frequency} • Next: {formatDate(recurring.next_expected)}
                                </Text>
                              </VStack>
                              <Text fontWeight="bold" color="red.500">
                                {formatCurrency(recurring.amount)}
                              </Text>
                            </HStack>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                ) : (
                  <Box textAlign="center" py={10}>
                    <Icon as={FiBarChart} boxSize={12} color="gray.400" />
                    <Text mt={4} color="gray.500">
                      Analytics not available yet
                    </Text>
                  </Box>
                )}
              </VStack>
            </TabPanel>

            {/* Skills Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontSize="lg" fontWeight="bold">ATOM Skills</Text>
                
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiDatabase} boxSize={8} color="blue.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Get Accounts</Text>
                          <Text fontSize="sm" color="gray.500">
                            Retrieve all connected accounts
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="blue" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('plaid_get_accounts')}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiFileText} boxSize={8} color="green.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Get Transactions</Text>
                          <Text fontSize="sm" color="gray.500">
                            Retrieve transactions with filters
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="green" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('plaid_get_transactions')}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiBarChart} boxSize={8} color="purple.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Generate Analytics</Text>
                          <Text fontSize="sm" color="gray.500">
                            Create spending insights and patterns
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="purple" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('plaid_generate_spending_analytics')}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiZap} boxSize={8} color="orange.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Sync with ATOM</Text>
                          <Text fontSize="sm" color="gray.500">
                            Synchronize data with ATOM memory
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="orange" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('plaid_sync_with_atom_memory')}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Configuration Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontSize="lg" fontWeight="bold">Configuration</Text>
                
                <Card>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <FormControl>
                        <FormLabel>Enable Real-time Sync</FormLabel>
                        <Switch
                          isChecked={currentConfig.enableRealTimeSync}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            enableRealTimeSync: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Include Pending Transactions</FormLabel>
                        <Switch
                          isChecked={currentConfig.includePendingTransactions}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            includePendingTransactions: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Generate Spending Insights</FormLabel>
                        <Switch
                          isChecked={currentConfig.generateSpendingInsights}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            generateSpendingInsights: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Categorize Transactions</FormLabel>
                        <Switch
                          isChecked={currentConfig.categorizeTransactions}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            categorizeTransactions: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Encrypt Sensitive Data</FormLabel>
                        <Switch
                          isChecked={currentConfig.encryptSensitiveData}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            encryptSensitiveData: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Mask Account Numbers</FormLabel>
                        <Switch
                          isChecked={currentConfig.maskAccountNumbers}
                          onChange={(e) => setCurrentConfig({ 
                            ...currentConfig, 
                            maskAccountNumbers: e.target.checked 
                          })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Batch Size</FormLabel>
                        <NumberInput
                          value={currentConfig.batchSize || 100}
                          onChange={(value) => setCurrentConfig({ 
                            ...currentConfig, 
                            batchSize: parseInt(value) || 100 
                          })}
                          min={1}
                          max={500}
                        >
                          <NumberInputField />
                          <NumberInputStepper>
                            <NumberIncrementStepper />
                            <NumberDecrementStepper />
                          </NumberInputStepper>
                        </NumberInput>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Max Retries</FormLabel>
                        <NumberInput
                          value={currentConfig.maxRetries || 3}
                          onChange={(value) => setCurrentConfig({ 
                            ...currentConfig, 
                            maxRetries: parseInt(value) || 3 
                          })}
                          min={0}
                          max={10}
                        >
                          <NumberInputField />
                          <NumberInputStepper>
                            <NumberIncrementStepper />
                            <NumberDecrementStepper />
                          </NumberInputStepper>
                        </NumberInput>
                      </FormControl>

                      <Button 
                        colorScheme="blue" 
                        onClick={handleStartSync}
                        isLoading={isSyncing}
                        isDisabled={!isConnected}
                      >
                        Start Sync
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default PlaidManager;