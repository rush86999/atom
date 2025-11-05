import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Stack,
  Badge,
  Progress,
  Alert,
  AlertIcon,
  Divider,
  Flex,
  Icon,
  Tooltip,
  useToast,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Select,
  Switch,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useColorModeValue,
  SimpleGrid,
  Avatar,
  useBreakpointValue,
  Tabs,
  TabList,
  TabPanels,
  TabPanel,
  Tag,
  TagLabel,
  TagLeftIcon,
  useClipboard,
  Textarea,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Spinner,
  Checkbox,
  RadioGroup,
  Radio,
  CheckboxGroup,
  Stack as CheckboxStack,
  Code,
  Text as ChakraText,
  Link,
  Stat,
  StatLabel,
  StatNumber,
  StatArrow,
  StatHelpText,
  StatGroup,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  MenuDivider,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  useNumberInput,
  Collapse,
  ButtonGroup,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverHeader,
  PopoverBody,
  PopoverArrow,
  PopoverCloseButton,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  InfoIcon,
  ViewListIcon,
  ArchiveIcon,
  UserIcon,
  CopyIcon,
  DesktopIcon,
  CheckIcon,
  CloseIcon,
  CommentIcon,
  CalendarIcon,
  ClockIcon,
  UserGroupIcon,
  TeamIcon,
  FolderIcon,
  FilterIcon,
  SearchIcon,
  EditIcon as EditTaskIcon,
  DeleteIcon,
  PlusIcon,
  StarIcon,
  RepeatIcon,
  DollarSignIcon,
  CreditCardIcon,
  ShoppingCartIcon,
  ChartIcon,
  PackageIcon,
  SubscriptionIcon,
  MoneyWaveIcon,
  TagIcon,
  ReceiptIcon,
  WalletIcon,
  CashIcon,
  BarChartIcon,
  ActivityIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ViewIcon as ViewIcon2,
  EditIcon as EditIcon2,
  LinkIcon,
  CopyIcon as CopyIcon2,
  ExternalLinkIcon as ExternalLinkIcon2,
  Search2Icon,
  FilterIcon as FilterIcon2,
  DownloadIcon,
  UploadIcon,
  RefreshIcon,
  SettingsIcon as SettingsIcon2,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface StripeIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface StripePayment {
  id: string;
  object: string;
  amount: number;
  amount_captured: number;
  amount_refunded: number;
  amount_received: number;
  application?: string;
  application_fee?: string;
  application_fee_amount?: number;
  balance_transaction: string;
  billing_details: {
    address?: {
      city?: string;
      country?: string;
      line1?: string;
      line2?: string;
      postal_code?: string;
      state?: string;
    };
    email?: string;
    name?: string;
    phone?: string;
  };
  calculated_statement_descriptor?: string;
  canceled_at?: number;
  cancellation_reason?: string;
  capture_method: 'automatic' | 'manual';
  created: number;
  currency: string;
  customer?: string;
  description?: string;
  destination?: string;
  dispute?: string;
  disputed: boolean;
  failure_balance_transaction?: string;
  failure_code?: string;
  failure_message?: string;
  invoice?: string;
  livemode: boolean;
  metadata: Record<string, string>;
  on_behalf_of?: string;
  outcome: {
    network_status: string;
    reason?: string;
    risk_level: string;
    risk_score: number;
    seller_message: string;
    type: string;
  };
  paid: boolean;
  payment_intent: string;
  payment_method: string;
  payment_method_details: {
    card?: {
      brand: string;
      checks?: {
        address_line1_check?: string;
        address_postal_code_check?: string;
        cvc_check?: string;
      };
      country?: string;
      exp_month: number;
      exp_year: number;
      fingerprint: string;
      funding: string;
      generated_from?: string;
      last4: string;
      network: string;
      three_d_secure?: string;
      wallet?: string;
    };
    type: string;
  };
  radar_options: Record<string, any>;
  receipt_email?: string;
  receipt_number?: string;
  receipt_url: string;
  refunded: boolean;
  refunds: {
    object: string;
    data: any[];
    has_more: boolean;
    total_count: number;
    url: string;
  };
  review?: string;
  shipping?: any;
  source: string;
  source_transfer?: string;
  statement_descriptor: string;
  statement_descriptor_suffix?: string;
  status: 'succeeded' | 'pending' | 'failed' | 'canceled';
  transfer_data?: any;
  transfer_group?: string;
  type: string;
  ui_mode?: string;
}

interface StripeCustomer {
  id: string;
  object: string;
  address?: {
    city?: string;
    country?: string;
    line1?: string;
    line2?: string;
    postal_code?: string;
    state?: string;
  };
  balance: number;
  created: number;
  currency?: string;
  default_source?: string;
  delinquent: boolean;
  description?: string;
  discount?: any;
  email?: string;
  invoice_prefix?: string;
  invoice_settings: {
    custom_fields?: any;
    default_payment_method?: string;
    footer?: string;
    rendering_options?: string;
  };
  livemode: boolean;
  metadata: Record<string, string>;
  name?: string;
  next_invoice_sequence?: number;
  phone?: string;
  preferred_locales?: string[];
  shipping?: {
    address?: {
      city?: string;
      country?: string;
      line1?: string;
      line2?: string;
      postal_code?: string;
      state?: string;
    };
    name?: string;
    phone?: string;
  };
  sources?: {
    object: string;
    data: any[];
    has_more: boolean;
    total_count: number;
    url: string;
  };
  subscriptions?: {
    object: string;
    data: any[];
    has_more: boolean;
    total_count: number;
    url: string;
  };
  tax_exempt: string;
  tax_ids?: {
    object: string;
    data: any[];
    has_more: boolean;
    total_count: number;
    url: string;
  };
  test_clock?: string;
}

interface StripeSubscription {
  id: string;
  object: string;
  application_fee_percent?: number;
  automatic_tax: {
    enabled: boolean;
    liability: {
      account?: string;
      type: string;
    };
  };
  billing_cycle_anchor: number;
  billing_thresholds?: any;
  cancel_at_period_end: boolean;
  canceled_at?: number;
  collection_method: 'charge_automatically' | 'send_invoice';
  created: number;
  current_period_end: number;
  current_period_start: number;
  customer: string;
  days_until_due?: number;
  default_payment_method?: string;
  default_source?: string;
  default_tax_rates: any[];
  description?: string;
  discount?: any;
  ended_at?: number;
  items: {
    object: string;
    data: any[];
    has_more: boolean;
    total_count: number;
    url: string;
  };
  latest_invoice: string;
  livemode: boolean;
  metadata: Record<string, string>;
  next_pending_invoice_item_invoice?: string;
  pause_collection?: any;
  payment_settings: {
    payment_method_options?: any;
    payment_method_types: string[];
    save_default_payment_method: string;
  };
  pending_invoice_item_interval?: any;
  pending_setup_intent?: string;
  pending_update?: any;
  plan: {
    id: string;
    object: string;
    active: boolean;
    aggregate_usage?: string;
    amount: number;
    amount_decimal: string;
    billing_scheme: string;
    created: number;
    currency: string;
    interval: 'day' | 'week' | 'month' | 'year';
    interval_count: number;
    livemode: boolean;
    metadata: Record<string, string>;
    nickname?: string;
    product: string;
    tiers_mode?: string;
    transform_usage?: any;
    trial_period_days?: number;
    usage_type: string;
  };
  quantity: number;
  schedule?: any;
  start_date: number;
  status: 'active' | 'canceled' | 'past_due' | 'trialing' | 'incomplete' | 'incomplete_expired' | 'unpaid';
  test_clock?: string;
  trial_end?: number;
  trial_start?: number;
  transfer_data?: any;
  trial_settings?: {
    end_behavior: {
      missing_payment_method: string;
    };
  };
}

interface StripeProduct {
  id: string;
  object: string;
  active: boolean;
  created: number;
  default_price?: string;
  description?: string;
  images: string[];
  livemode: boolean;
  metadata: Record<string, string>;
  name: string;
  package_dimensions?: any;
  shippable: boolean;
  statement_descriptor?: string;
  tax_code?: string;
  unit_label?: string;
  updated: number;
  url?: string;
}

interface StripeUser {
  id: string;
  email: string;
  business_name: string;
  display_name: string;
  country: string;
  currency: string;
  balance: {
    available: Array<{ amount: number; currency: string }>;
    pending: Array<{ amount: number; currency: string }>;
    connect_reserved: Array<{ amount: number; currency: string }>;
  };
  charges_enabled: boolean;
  payouts_enabled: boolean;
  requirements: {
    currently_due: string[];
    past_due: string[];
    eventually_due: string[];
    disabled_reason?: string;
  };
  created: string;
  created_utc: number;
  metadata: Record<string, string>;
}

// Stripe scopes constant
const STRIPE_SCOPES = [
  'read_write',
  'charges',
  'customers',
  'subscriptions',
  'invoices',
  'payment_intents',
  'payment_methods',
  'products',
  'prices',
  'coupons',
  'discounts',
  'checkout_sessions',
  'billing_portal_sessions',
  'webhooks',
  'account',
  'balance',
  'transfers',
  'payouts',
  'events',
  'disputes',
  'refunds',
  'setup_intents',
  'terminal',
  'radar',
  'issuing',
  'connect',
  'sigma'
];

/**
 * Enhanced Stripe Integration Manager
 * Complete Stripe payment processing and financial management system
 */
export const StripeIntegrationManager: React.FC<StripeIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Stripe',
    platform: 'stripe',
    enabled: true,
    settings: {
      contentTypes: ['payments', 'customers', 'subscriptions', 'products'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeTestMode: true,
      includeLiveMode: false,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['payment_succeeded', 'payment_failed', 'invoice_created', 'subscription_created'],
      searchQueries: {
        payments: '',
        customers: '',
        subscriptions: '',
        products: ''
      },
      filters: {
        payments: {
          customer_id: '',
          status: '',
          created_min: '',
          created_max: '',
          limit: 30
        },
        customers: {
          email: '',
          description: '',
          created_min: '',
          created_max: '',
          limit: 30
        },
        subscriptions: {
          customer_id: '',
          status: '',
          created_min: '',
          created_max: '',
          limit: 30
        },
        products: {
          active: true,
          limit: 30
        }
      }
    }
  });

  // Data states
  const [payments, setPayments] = useState<StripePayment[]>([]);
  const [customers, setCustomers] = useState<StripeCustomer[]>([]);
  const [subscriptions, setSubscriptions] = useState<StripeSubscription[]>([]);
  const [products, setProducts] = useState<StripeProduct[]>([]);
  const [currentUser, setCurrentUser] = useState<StripeUser | null>(null);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    paymentsProcessed: 0,
    customersProcessed: 0,
    subscriptionsProcessed: 0,
    errors: []
  });

  // Modal states
  const [createPaymentModalOpen, setCreatePaymentModalOpen] = useState(false);
  const [createCustomerModalOpen, setCreateCustomerModalOpen] = useState(false);
  const [createSubscriptionModalOpen, setCreateSubscriptionModalOpen] = useState(false);
  const [createProductModalOpen, setCreateProductModalOpen] = useState(false);
  const [refundPaymentModalOpen, setRefundPaymentModalOpen] = useState(false);
  
  // Form states
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    currency: 'USD',
    customer_id: '',
    description: '',
    capture_method: 'automatic'
  });
  
  const [customerForm, setCustomerForm] = useState({
    name: '',
    email: '',
    description: '',
    phone: '',
    address: {
      line1: '',
      city: '',
      state: '',
      postal_code: '',
      country: ''
    }
  });
  
  const [subscriptionForm, setSubscriptionForm] = useState({
    customer_id: '',
    product_id: '',
    price: '',
    interval: 'month',
    trial_period_days: 0,
    description: ''
  });
  
  const [productForm, setProductForm] = useState({
    name: '',
    description: '',
    active: true,
    images: [] as string[]
  });
  
  const [refundForm, setRefundForm] = useState({
    payment_id: '',
    amount: '',
    reason: ''
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('stripe_access_token_placeholder');

  const { getInputProps, getIncrementButtonProps, getDecrementButtonProps } = useNumberInput({
    step: 0.01,
    precision: 2,
    defaultValue: 0,
    min: 0.5
  });
  
  const inc = getIncrementButtonProps();
  const dec = getDecrementButtonProps();

  useEffect(() => {
    checkStripeHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadStripeData();
    }
  }, [health]);

  const checkStripeHealth = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setHealth({
          connected: true,
          lastSync: new Date().toISOString(),
          errors: []
        });
      } else {
        setHealth({
          connected: false,
          lastSync: new Date().toISOString(),
          errors: [data.error || 'Stripe service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Stripe service health']
      });
    }
  };

  const loadStripeData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadPayments(),
        loadCustomers(),
        loadSubscriptions(),
        loadProducts(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Stripe data');
      toast({
        title: 'Error',
        description: 'Failed to load Stripe data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadPayments = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/payments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          customer: config.settings.filters.payments.customer_id,
          status: config.settings.filters.payments.status,
          created: {
            gte: config.settings.filters.payments.created_min,
            lte: config.settings.filters.payments.created_max
          },
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setPayments(data.data.payments || []);
      }
    } catch (err) {
      console.error('Error loading payments:', err);
    }
  };

  const loadCustomers = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          email: config.settings.filters.customers.email,
          description: config.settings.filters.customers.description,
          created: {
            gte: config.settings.filters.customers.created_min,
            lte: config.settings.filters.customers.created_max
          },
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCustomers(data.data.customers || []);
      }
    } catch (err) {
      console.error('Error loading customers:', err);
    }
  };

  const loadSubscriptions = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          customer: config.settings.filters.subscriptions.customer_id,
          status: config.settings.filters.subscriptions.status,
          created: {
            gte: config.settings.filters.subscriptions.created_min,
            lte: config.settings.filters.subscriptions.created_max
          },
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setSubscriptions(data.data.subscriptions || []);
      }
    } catch (err) {
      console.error('Error loading subscriptions:', err);
    }
  };

  const loadProducts = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          active: config.settings.filters.products.active,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setProducts(data.data.products || []);
      }
    } catch (err) {
      console.error('Error loading products:', err);
    }
  };

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/stripe/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCurrentUser(data.data.user);
      }
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  };

  const createPayment = async () => {
    if (!paymentForm.amount || !paymentForm.currency) {
      toast({
        title: 'Error',
        description: 'Payment amount and currency are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/stripe/payments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            amount: Math.round(parseFloat(paymentForm.amount) * 100),
            currency: paymentForm.currency.toLowerCase(),
            customer: paymentForm.customer_id,
            description: paymentForm.description,
            capture_method: paymentForm.capture_method,
            metadata: {
              source: 'stripe_integration',
              created_at: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Payment created successfully',
          status: 'success',
          duration: 3000
        });
        
        setPaymentForm({
          amount: '',
          currency: 'USD',
          customer_id: '',
          description: '',
          capture_method: 'automatic'
        });
        setCreatePaymentModalOpen(false);
        await loadPayments();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create payment',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create payment',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const createCustomer = async () => {
    if (!customerForm.email) {
      toast({
        title: 'Error',
        description: 'Customer email is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/stripe/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            name: customerForm.name,
            email: customerForm.email,
            description: customerForm.description,
            phone: customerForm.phone,
            address: customerForm.address.line1 ? {
              line1: customerForm.address.line1,
              line2: '',
              city: customerForm.address.city,
              state: customerForm.address.state,
              postal_code: customerForm.address.postal_code,
              country: customerForm.address.country
            } : undefined,
            metadata: {
              source: 'stripe_integration',
              created_at: new Date().toISOString()
            }
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Customer created successfully',
          status: 'success',
          duration: 3000
        });
        
        setCustomerForm({
          name: '',
          email: '',
          description: '',
          phone: '',
          address: {
            line1: '',
            city: '',
            state: '',
            postal_code: '',
            country: ''
          }
        });
        setCreateCustomerModalOpen(false);
        await loadCustomers();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create customer',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create customer',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const searchStripe = async () => {
    if (!searchQuery.trim()) {
      await Promise.all([
        loadPayments(),
        loadCustomers(),
        loadSubscriptions(),
        loadProducts()
      ]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/stripe/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          type: 'all', // Can be 'payments', 'customers', 'subscriptions', 'products', 'all'
          limit: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        const searchResults = result.data.results || [];
        
        // Update data based on search results
        const paymentResults = searchResults.filter((r: any) => r.type === 'payment');
        const customerResults = searchResults.filter((r: any) => r.type === 'customer');
        const subscriptionResults = searchResults.filter((r: any) => r.type === 'subscription');
        const productResults = searchResults.filter((r: any) => r.type === 'product');
        
        if (paymentResults.length > 0) {
          const searchPayments = paymentResults.map((r: any) => ({
            id: r.id,
            object: 'charge',
            amount: r.amount * 100,
            amount_captured: r.amount * 100,
            amount_refunded: 0,
            amount_received: r.amount * 100,
            created: Math.floor(new Date(r.created).getTime() / 1000),
            currency: r.currency,
            description: r.description,
            status: r.status,
            receipt_url: `https://pay.stripe.com/receipts/mock_${r.id}`,
            payment_intent: `pi_mock_${r.id}`,
            payment_method: `pm_mock_${r.id}`,
            billing_details: {
              email: r.customer_email,
              name: r.customer_name
            },
            paid: r.status === 'succeeded',
            refunded: false,
            outcomes: {
              network_status: r.status === 'succeeded' ? 'approved_by_network' : 'failed',
              reason: null,
              risk_level: 'normal',
              risk_score: 20,
              seller_message: 'Payment complete.',
              type: 'authorized'
            },
            metadata: {},
            payment_method_details: {
              type: 'card',
              card: {
                brand: 'visa',
                last4: '4242',
                exp_month: 12,
                exp_year: 2024,
                country: 'US',
                funding: 'credit'
              }
            },
            refunds: {
              object: 'list',
              data: [],
              has_more: false,
              total_count: 0,
              url: `/v1/charges/ch_${r.id}/refunds`
            }
          }));
          setPayments(searchPayments);
        }
        
        if (customerResults.length > 0) {
          const searchCustomers = customerResults.map((r: any) => ({
            id: r.id,
            object: 'customer',
            created: Math.floor(new Date(r.created).getTime() / 1000),
            email: r.email,
            name: r.name,
            description: r.description,
            balance: 0,
            delinquent: false,
            livemode: false,
            metadata: {},
            invoice_settings: {
              custom_fields: null,
              default_payment_method: null,
              footer: null,
              rendering_options: null
            },
            preferred_locales: ['en-US']
          }));
          setCustomers(searchCustomers);
        }
        
        if (subscriptionResults.length > 0) {
          const searchSubscriptions = subscriptionResults.map((r: any) => ({
            id: r.id,
            object: 'subscription',
            created: Math.floor(new Date(r.created).getTime() / 1000),
            current_period_end: Math.floor((new Date().getTime() + 30 * 24 * 60 * 60 * 1000) / 1000),
            current_period_start: Math.floor(new Date().getTime() / 1000),
            customer: r.customer_id,
            status: r.status,
            items: {
              object: 'list',
              data: [],
              has_more: false,
              total_count: 0,
              url: `/v1/subscriptions/${r.id}/items`
            },
            plan: {
              id: `price_${r.id}`,
              object: 'plan',
              amount: r.amount * 100,
              currency: r.currency,
              interval: r.interval,
              interval_count: 1,
              product: `prod_${r.id}`,
              active: true,
              billing_scheme: 'per_unit',
              created: Math.floor(new Date(r.created).getTime() / 1000),
              livemode: false,
              metadata: {},
              nickname: r.product_name,
              usage_type: 'licensed'
            },
            quantity: 1,
            start_date: Math.floor(new Date(r.created).getTime() / 1000),
            livemode: false,
            metadata: {}
          }));
          setSubscriptions(searchSubscriptions);
        }
        
        if (productResults.length > 0) {
          const searchProducts = productResults.map((r: any) => ({
            id: r.id,
            object: 'product',
            created: Math.floor(new Date(r.created).getTime() / 1000),
            updated: Math.floor(new Date().getTime() / 1000),
            name: r.name,
            description: r.description,
            active: r.active,
            livemode: false,
            metadata: {},
            package_dimensions: null,
            shippable: false,
            images: []
          }));
          setProducts(searchProducts);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Stripe',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startStripeOAuth = async () => {
    try {
      const response = await fetch('/api/auth/stripe/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: STRIPE_SCOPES,
          redirect_uri: 'http://localhost:3000/oauth/stripe/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        const popup = window.open(
          data.authorization_url,
          'stripe-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkStripeHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Stripe OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Stripe OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderPaymentCard = (payment: StripePayment) => (
    <Card key={payment.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={CreditCardIcon} color="green.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  ${((payment.amount || 0) / 100).toFixed(2)} {payment.currency?.toUpperCase()}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {payment.payment_intent}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={payment.status === 'succeeded' ? 'green' : payment.status === 'failed' ? 'red' : 'yellow'}>
                {payment.status}
              </Badge>
              {payment.refunded && <Badge colorScheme="orange">Refunded</Badge>}
              {payment.disputed && <Badge colorScheme="red">Disputed</Badge>}
            </HStack>
          </HStack>
          
          {payment.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {payment.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>💳 {payment.payment_method_details.card?.brand}</Text>
            <Text>****{payment.payment_method_details.card?.last4}</Text>
            <Text>📅 {new Date(payment.created * 1000).toLocaleDateString()}</Text>
          </HStack>
          
          {payment.billing_details && (
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Customer:</Text>
              <HStack>
                <Text fontSize="sm" color="gray.700">
                  {payment.billing_details.name || 'Unknown'}
                </Text>
                {payment.billing_details.email && (
                  <Text fontSize="sm" color="gray.500">
                    ({payment.billing_details.email})
                  </Text>
                )}
              </HStack>
            </VStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Risk Score: {payment.outcome?.risk_score || 0}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(payment.receipt_url, '_blank')}>
                  View Receipt
                </MenuItem>
                <MenuItem icon={<ExternalLinkIcon />} onClick={() => window.open(`https://dashboard.stripe.com/payments/${payment.id}`, '_blank')}>
                  View in Stripe Dashboard
                </MenuItem>
                {payment.status === 'succeeded' && !payment.refunded && (
                  <MenuItem icon={<RefreshIcon />} onClick={() => {
                    setRefundForm({
                      payment_id: payment.id,
                      amount: ((payment.amount || 0) / 100).toFixed(2),
                      reason: ''
                    });
                    setRefundPaymentModalOpen(true);
                  }}>
                    Issue Refund
                  </MenuItem>
                )}
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderCustomerCard = (customer: StripeCustomer) => (
    <Card key={customer.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={UserIcon} color="blue.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {customer.name || customer.email || 'Unknown Customer'}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {customer.id}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              {customer.delinquent && <Badge colorScheme="red">Delinquent</Badge>}
              {customer.balance !== 0 && (
                <Badge colorScheme={customer.balance > 0 ? 'green' : 'orange'}>
                  {customer.balance > 0 ? 'Credit' : 'Debt'}
                </Badge>
              )}
            </HStack>
          </HStack>
          
          {customer.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {customer.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>📧 {customer.email}</Text>
            <Text>📅 {new Date(customer.created * 1000).toLocaleDateString()}</Text>
          </HStack>
          
          {(customer.address || customer.shipping) && (
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Address:</Text>
              <Text fontSize="sm" color="gray.700">
                {customer.address?.line1 || customer.shipping?.address?.line1 || 'No address'}
              </Text>
              {(customer.address?.city || customer.shipping?.address?.city) && (
                <Text fontSize="sm" color="gray.600">
                  {customer.address?.city || customer.shipping?.address?.city}, {customer.address?.state || customer.shipping?.address?.state} {customer.address?.postal_code || customer.shipping?.address?.postal_code}
                </Text>
              )}
            </VStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Tax Exempt: {customer.tax_exempt}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://dashboard.stripe.com/customers/${customer.id}`, '_blank')}>
                  View Customer
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Customer
                </MenuItem>
                <MenuItem icon={<CreditCardIcon />}>
                  View Payment Methods
                </MenuItem>
                <MenuItem icon={<ReceiptIcon />}>
                  View Invoices
                </MenuItem>
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderSubscriptionCard = (subscription: StripeSubscription) => (
    <Card key={subscription.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={SubscriptionIcon} color="purple.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {subscription.plan?.nickname || subscription.plan?.product || 'Subscription'}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {subscription.id}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={subscription.status === 'active' ? 'green' : subscription.status === 'canceled' ? 'red' : subscription.status === 'past_due' ? 'orange' : 'yellow'}>
                {subscription.status}
              </Badge>
              {subscription.cancel_at_period_end && <Badge colorScheme="orange">Canceling</Badge>}
            </HStack>
          </HStack>
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>💰 ${((subscription.plan?.amount || 0) / 100).toFixed(2)} {subscription.plan?.currency?.toUpperCase()}</Text>
            <Text>🔄 {subscription.plan?.interval}</Text>
            <Text>📅 {new Date(subscription.current_period_end * 1000).toLocaleDateString()}</Text>
          </HStack>
          
          <VStack align="start" spacing={1}>
            <Text fontSize="xs" color="gray.500">Billing Period:</Text>
            <Text fontSize="sm" color="gray.700">
              {new Date(subscription.current_period_start * 1000).toLocaleDateString()} - {new Date(subscription.current_period_end * 1000).toLocaleDateString()}
            </Text>
          </VStack>
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Customer: {subscription.customer}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://dashboard.stripe.com/subscriptions/${subscription.id}`, '_blank')}>
                  View Subscription
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Subscription
                </MenuItem>
                {subscription.status === 'active' && (
                  <MenuItem icon={<CloseIcon />}>
                    Cancel Subscription
                  </MenuItem>
                )}
                {subscription.status === 'active' && (
                  <MenuItem icon={<TimeIcon />}>
                    Pause Subscription
                  </MenuItem>
                )}
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderProductCard = (product: StripeProduct) => (
    <Card key={product.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={PackageIcon} color="orange.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {product.name}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {product.id}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={product.active ? 'green' : 'gray'}>
                {product.active ? 'Active' : 'Inactive'}
              </Badge>
            </HStack>
          </HStack>
          
          {product.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={2}>
              {product.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>📅 Created {new Date(product.created * 1000).toLocaleDateString()}</Text>
            <Text>📝 Updated {new Date(product.updated * 1000).toLocaleDateString()}</Text>
          </HStack>
          
          {product.images && product.images.length > 0 && (
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Images:</Text>
              <HStack spacing={2}>
                {product.images.slice(0, 3).map((image, index) => (
                  <Box key={index} w="12" h="12" bg="gray.200" rounded="md">
                    <Text fontSize="xs" color="gray.500" textAlign="center" lineHeight="12">
                      {index + 1}
                    </Text>
                  </Box>
                ))}
                {product.images.length > 3 && (
                  <Text fontSize="xs" color="gray.500">+{product.images.length - 3}</Text>
                )}
              </HStack>
            </VStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              {product.shippable ? 'Shippable' : 'Digital'}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://dashboard.stripe.com/products/${product.id}`, '_blank')}>
                  View Product
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Product
                </MenuItem>
                <MenuItem icon={<DollarSignIcon />}>
                  View Prices
                </MenuItem>
                <MenuItem icon={<StarIcon />}>
                  Add to Favorites
                </MenuItem>
              </MenuList>
            </Menu>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  if (!health?.connected) {
    return (
      <Box p={6}>
        <Alert status="warning">
          <AlertIcon />
          <Box>
            <AlertTitle>Stripe Not Connected</AlertTitle>
            <AlertDescription>
              Please connect your Stripe account to access payments, customers, and subscriptions.
            </AlertDescription>
          </Box>
        </Alert>
        <Button
          mt={4}
          colorScheme="green"
          onClick={startStripeOAuth}
        >
          Connect Stripe Account
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Stripe Integration</Heading>
          <Text color="gray.600">Manage payments, customers, subscriptions, and products</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search payments, customers, subscriptions, products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchStripe()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="green"
            onClick={searchStripe}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<PlusIcon />}
            colorScheme="blue"
            onClick={() => setCreatePaymentModalOpen(true)}
          >
            New Payment
          </Button>
          
          <Button
            leftIcon={<UserIcon />}
            colorScheme="purple"
            onClick={() => setCreateCustomerModalOpen(true)}
          >
            New Customer
          </Button>
          
          <Button
            leftIcon={<SubscriptionIcon />}
            colorScheme="orange"
            onClick={() => setCreateSubscriptionModalOpen(true)}
          >
            New Subscription
          </Button>
        </HStack>

        {/* Stats Overview */}
        {currentUser && (
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>Available Balance</StatLabel>
              <StatNumber>${(currentUser.balance.available[0]?.amount / 100000).toFixed(2)}</StatNumber>
              <StatHelpText>{currentUser.balance.available[0]?.currency?.toUpperCase()}</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Pending Balance</StatLabel>
              <StatNumber>${(currentUser.balance.pending[0]?.amount / 100000).toFixed(2)}</StatNumber>
              <StatHelpText>{currentUser.balance.pending[0]?.currency?.toUpperCase()}</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Payments</StatLabel>
              <StatNumber>{payments.length}</StatNumber>
              <StatHelpText>Last 30 days</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Customers</StatLabel>
              <StatNumber>{customers.length}</StatNumber>
              <StatHelpText>Total customers</StatHelpText>
            </Stat>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <CreditCardIcon />
                <Text>Payments ({payments.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <UserIcon />
                <Text>Customers ({customers.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <SubscriptionIcon />
                <Text>Subscriptions ({subscriptions.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <PackageIcon />
                <Text>Products ({products.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <WalletIcon />
                <Text>Balance</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Payments Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : payments.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <CreditCardIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No payments found</Text>
                  <Button
                    mt={4}
                    colorScheme="blue"
                    onClick={() => setCreatePaymentModalOpen(true)}
                  >
                    Create Your First Payment
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {payments.map(renderPaymentCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Customers Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : customers.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <UserIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No customers found</Text>
                  <Button
                    mt={4}
                    colorScheme="purple"
                    onClick={() => setCreateCustomerModalOpen(true)}
                  >
                    Create Your First Customer
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {customers.map(renderCustomerCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Subscriptions Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : subscriptions.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <SubscriptionIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No subscriptions found</Text>
                  <Button
                    mt={4}
                    colorScheme="orange"
                    onClick={() => setCreateSubscriptionModalOpen(true)}
                  >
                    Create Your First Subscription
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {subscriptions.map(renderSubscriptionCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Products Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : products.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <PackageIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No products found</Text>
                  <Button
                    mt={4}
                    colorScheme="orange"
                    onClick={() => setCreateProductModalOpen(true)}
                  >
                    Create Your First Product
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {products.map(renderProductCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Balance Tab */}
            <TabPanel>
              {currentUser && (
                <Card>
                  <CardBody p={6}>
                    <VStack spacing={4} align="center">
                      <Avatar
                        name={currentUser.business_name}
                        size="2xl"
                        bg="green.500"
                        color="white"
                      />
                      <VStack align="center" spacing={2}>
                        <Heading size="lg">{currentUser.business_name}</Heading>
                        <Text color="gray.600">{currentUser.display_name}</Text>
                        <Text fontSize="sm" color="gray.500">
                          Account ID: {currentUser.id}
                        </Text>
                        <Text fontSize="sm" color="gray.500">
                          Email: {currentUser.email}
                        </Text>
                      </VStack>
                      
                      <Divider />
                      
                      <VStack align="start" spacing={2} w="full">
                        <HStack justify="space-between" w="full">
                          <Text>Services</Text>
                          <HStack>
                            <Badge colorScheme="blue">Payments</Badge>
                            <Badge colorScheme="purple">Customers</Badge>
                            <Badge colorScheme="orange">Subscriptions</Badge>
                            <Badge colorScheme="green">Products</Badge>
                            <Badge colorScheme="red">Billing</Badge>
                            <Badge colorScheme="teal">Webhooks</Badge>
                          </HStack>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Country</Text>
                          <Text>{currentUser.country}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Currency</Text>
                          <Text>{currentUser.currency?.toUpperCase()}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Available Balance</Text>
                          <Text color="green.600">${(currentUser.balance.available[0]?.amount / 100000).toFixed(2)} {currentUser.balance.available[0]?.currency?.toUpperCase()}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Pending Balance</Text>
                          <Text color="orange.600">${(currentUser.balance.pending[0]?.amount / 100000).toFixed(2)} {currentUser.balance.pending[0]?.currency?.toUpperCase()}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Charges Enabled</Text>
                          <Badge colorScheme={currentUser.charges_enabled ? 'green' : 'red'}>
                            {currentUser.charges_enabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Payouts Enabled</Text>
                          <Badge colorScheme={currentUser.payouts_enabled ? 'green' : 'red'}>
                            {currentUser.payouts_enabled ? 'Enabled' : 'Disabled'}
                          </Badge>
                        </HStack>
                        
                        <Button
                          colorScheme="green"
                          onClick={() => window.open('https://dashboard.stripe.com', '_blank')}
                        >
                          Open Stripe Dashboard
                        </Button>
                      </VStack>
                    </VStack>
                  </CardBody>
                </Card>
              )}
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Payment Modal */}
        <Modal isOpen={createPaymentModalOpen} onClose={() => setCreatePaymentModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Payment</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Amount</FormLabel>
                  <NumberInput min={0.5} precision={2} step={0.01}>
                    <NumberInputField
                      value={paymentForm.amount}
                      onChange={(value) => setPaymentForm({...paymentForm, amount: value})}
                      placeholder="0.00"
                    />
                    <NumberInputStepper>
                      <NumberIncrementStepper {...inc} />
                      <NumberDecrementStepper {...dec} />
                    </NumberInputStepper>
                  </NumberInput>
                  <FormHelperText>Amount to charge (in {paymentForm.currency})</FormHelperText>
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Currency</FormLabel>
                  <Select
                    value={paymentForm.currency}
                    onChange={(e) => setPaymentForm({...paymentForm, currency: e.target.value})}
                  >
                    <option value="USD">USD - US Dollar</option>
                    <option value="EUR">EUR - Euro</option>
                    <option value="GBP">GBP - British Pound</option>
                    <option value="CAD">CAD - Canadian Dollar</option>
                    <option value="AUD">AUD - Australian Dollar</option>
                    <option value="JPY">JPY - Japanese Yen</option>
                    <option value="CHF">CHF - Swiss Franc</option>
                  </Select>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Customer</FormLabel>
                  <Select
                    value={paymentForm.customer_id}
                    onChange={(e) => setPaymentForm({...paymentForm, customer_id: e.target.value})}
                    placeholder="Select customer (optional)"
                  >
                    <option value="">No customer</option>
                    {customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name || customer.email}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={paymentForm.description}
                    onChange={(e) => setPaymentForm({...paymentForm, description: e.target.value})}
                    placeholder="Enter payment description"
                    rows={4}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Capture Method</FormLabel>
                  <Select
                    value={paymentForm.capture_method}
                    onChange={(e) => setPaymentForm({...paymentForm, capture_method: e.target.value as 'automatic' | 'manual'})}
                  >
                    <option value="automatic">Automatic</option>
                    <option value="manual">Manual</option>
                  </Select>
                  <FormHelperText>Automatic captures funds immediately, manual requires authorization</FormHelperText>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreatePaymentModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={createPayment}
                isLoading={loading}
              >
                Create Payment
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Customer Modal */}
        <Modal isOpen={createCustomerModalOpen} onClose={() => setCreateCustomerModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Customer</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Name</FormLabel>
                  <Input
                    value={customerForm.name}
                    onChange={(e) => setCustomerForm({...customerForm, name: e.target.value})}
                    placeholder="Enter customer name"
                  />
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Email</FormLabel>
                  <Input
                    value={customerForm.email}
                    onChange={(e) => setCustomerForm({...customerForm, email: e.target.value})}
                    placeholder="Enter customer email"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Phone</FormLabel>
                  <Input
                    value={customerForm.phone}
                    onChange={(e) => setCustomerForm({...customerForm, phone: e.target.value})}
                    placeholder="Enter customer phone"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={customerForm.description}
                    onChange={(e) => setCustomerForm({...customerForm, description: e.target.value})}
                    placeholder="Enter customer description"
                    rows={4}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Address</FormLabel>
                  <VStack spacing={2}>
                    <Input
                      value={customerForm.address.line1}
                      onChange={(e) => setCustomerForm({...customerForm, address: {...customerForm.address, line1: e.target.value}})}
                      placeholder="Street Address"
                    />
                    <HStack>
                      <Input
                        value={customerForm.address.city}
                        onChange={(e) => setCustomerForm({...customerForm, address: {...customerForm.address, city: e.target.value}})}
                        placeholder="City"
                      />
                      <Input
                        value={customerForm.address.state}
                        onChange={(e) => setCustomerForm({...customerForm, address: {...customerForm.address, state: e.target.value}})}
                        placeholder="State"
                      />
                    </HStack>
                    <HStack>
                      <Input
                        value={customerForm.address.postal_code}
                        onChange={(e) => setCustomerForm({...customerForm, address: {...customerForm.address, postal_code: e.target.value}})}
                        placeholder="Postal Code"
                      />
                      <Input
                        value={customerForm.address.country}
                        onChange={(e) => setCustomerForm({...customerForm, address: {...customerForm.address, country: e.target.value}})}
                        placeholder="Country"
                      />
                    </HStack>
                  </VStack>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateCustomerModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={createCustomer}
                isLoading={loading}
              >
                Create Customer
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Refund Payment Modal */}
        <Modal isOpen={refundPaymentModalOpen} onClose={() => setRefundPaymentModalOpen(false)} size="md">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Refund Payment</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Payment ID</FormLabel>
                  <Input
                    value={refundForm.payment_id}
                    onChange={(e) => setRefundForm({...refundForm, payment_id: e.target.value})}
                    placeholder="Payment ID"
                    isDisabled
                  />
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Refund Amount</FormLabel>
                  <NumberInput min={0.5} precision={2} step={0.01}>
                    <NumberInputField
                      value={refundForm.amount}
                      onChange={(value) => setRefundForm({...refundForm, amount: value})}
                      placeholder="0.00"
                    />
                    <NumberInputStepper>
                      <NumberIncrementStepper {...inc} />
                      <NumberDecrementStepper {...dec} />
                    </NumberInputStepper>
                  </NumberInput>
                  <FormHelperText>Amount to refund</FormHelperText>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Reason</FormLabel>
                  <Select
                    value={refundForm.reason}
                    onChange={(e) => setRefundForm({...refundForm, reason: e.target.value})}
                    placeholder="Select reason (optional)"
                  >
                    <option value="">Select reason</option>
                    <option value="duplicate">Duplicate</option>
                    <option value="fraudulent">Fraudulent</option>
                    <option value="requested_by_customer">Requested by customer</option>
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setRefundPaymentModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={() => {/* Refund logic */}}
                isLoading={loading}
              >
                Process Refund
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default StripeIntegrationManager;