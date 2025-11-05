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
  InputGroup,
  InputRightElement,
  InputLeftElement,
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
  EmailIcon,
  PhoneIcon,
  LocationIcon,
  TruckIcon,
  BoxIcon,
  InventoryIcon,
  StoreIcon,
  ShopIcon,
} from '@chakra-ui/icons';

interface ShopifyIntegrationProps {
  atomIngestionPipeline?: any;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: any) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface ShopifyProduct {
  id: number;
  title: string;
  body_html: string;
  vendor: string;
  product_type: string;
  created_at: string;
  handle: string;
  updated_at: string;
  published_at: string;
  template_suffix: string | null;
  status: string;
  published_scope: string;
  tags: string;
  admin_graphql_api_id: string;
  options: Array<{
    id: number;
    name: string;
    product_id: number;
    position: number;
    values: string[];
  }>;
  images: Array<{
    id: number;
    product_id: number;
    position: number;
    created_at: string;
    updated_at: string;
    alt: string | null;
    width: number;
    height: number;
    src: string;
    variant_ids: number[];
  }>;
  image: any;
  variants: Array<{
    id: number;
    product_id: number;
    title: string;
    price: string;
    sku: string;
    position: number;
    grams: number;
    inventory_policy: string;
    compare_at_price: string | null;
    fulfillment_service: string;
    inventory_management: string | null;
    option1: string;
    option2: string | null;
    option3: string | null;
    created_at: string;
    updated_at: string;
    taxable: boolean;
    barcode: string;
    image_id: number | null;
    inventory_quantity: number | null;
    weight: number;
    weight_unit: string;
    old_inventory_quantity: number | null;
    requires_shipping: boolean;
    admin_graphql_api_id: string;
  }>;
  metafields: any[];
}

interface ShopifyOrder {
  id: number;
  admin_graphql_api_id: string;
  app_id: number | null;
  browser_ip: string;
  buyer_accepts_marketing: boolean;
  cancel_reason: string | null;
  cancelled_at: string | null;
  cart_token: string | null;
  checkout_id: number;
  checkout_token: string;
  client_details: {
    browser_ip: string;
    accept_language: string;
    user_agent: string;
    session_hash: string | null;
    browser_width: number;
    browser_height: number;
  };
  closed_at: string | null;
  confirmed: boolean;
  contact_email: string;
  created_at: string;
  currency: string;
  current_subtotal_price: string;
  current_total_price: string;
  current_total_tax: string;
  customer_locale: string;
  device_id: number | null;
  discount_codes: any[];
  email: string;
  estimated_taxes: boolean;
  financial_status: string;
  fulfillment_status: string | null;
  gateway: string;
  landing_site: string;
  name: string;
  note: string | null;
  note_attributes: any[];
  number: number;
  order_number: number;
  order_status_url: string;
  payment_gateway_names: string[];
  phone: string;
  presentment_currency: string;
  processed_at: string | null;
  processing_method: string;
  reference: string | null;
  referring_site: string;
  source_identifier: string | null;
  source_name: string;
  source_url: string | null;
  subtotal_price: string;
  tags: string;
  tax_lines: any[];
  taxes_included: boolean;
  test: boolean;
  token: string;
  total_discounts: string;
  total_line_items_price: string;
  total_outstanding: string;
  total_price: string;
  total_tax: string;
  total_tip_received: string;
  total_weight: number;
  updated_at: string;
  user_id: number | null;
  billing_address: any;
  customer: any;
  discount_applications: any[];
  fulfillments: any[];
  line_items: any[];
  payment_details: any;
  refunds: any[];
  shipping_address: any;
  shipping_lines: any[];
}

interface ShopifyCustomer {
  id: number;
  email: string;
  created_at: string;
  updated_at: string;
  first_name: string;
  last_name: string;
  state: string;
  note: string | null;
  verified_email: boolean;
  multipass_identifier: string | null;
  tax_exempt: boolean;
  tags: string;
  last_order_id: number | null;
  last_order_name: string | null;
  currency: string;
  total_spent: string;
  phone: string;
  addresses: Array<{
    id: number;
    customer_id: number;
    first_name: string;
    last_name: string;
    company: string | null;
    address1: string;
    address2: string | null;
    city: string;
    province: string;
    country: string;
    country_code: string;
    province_code: string;
    postal_code: string;
    phone: string | null;
    name: string;
    province_name: string;
    country_name: string;
    default: boolean;
  }>;
  accepts_marketing: boolean;
  accepts_marketing_updated_at: string;
  marketing_opt_in_level: string;
  tax_exemptions: any[];
  sms_marketing_consent: any;
  admin_graphql_api_id: string;
}

interface ShopifyUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  account_owner: boolean;
  locale: string;
  collaborator: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

interface ShopifyShop {
  name: string;
  domain: string;
  currency: string;
  timezone: string;
  email: string;
  created_at: string;
  updated_at: string;
}

// Shopify scopes constant
const SHOPIFY_SCOPES = [
  'read_products',
  'write_products',
  'read_orders',
  'write_orders',
  'read_customers',
  'write_customers',
  'read_inventory',
  'write_inventory',
  'read_draft_orders',
  'write_draft_orders',
  'read_price_rules',
  'write_price_rules',
  'read_discounts',
  'write_discounts',
  'read_script_tags',
  'write_script_tags',
  'read_webhooks',
  'write_webhooks',
  'read_themes',
  'write_themes',
  'read_assets',
  'write_assets',
  'read_content',
  'write_content'
];

/**
 * Enhanced Shopify Integration Manager
 * Complete Shopify e-commerce and store management system
 */
export const ShopifyIntegrationManager: React.FC<ShopifyIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<any>({
    name: 'Shopify',
    platform: 'shopify',
    enabled: true,
    settings: {
      contentTypes: ['products', 'orders', 'customers', 'inventory'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeTestMode: true,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['order_created', 'order_cancelled', 'product_created', 'customer_created'],
      searchQueries: {
        products: '',
        orders: '',
        customers: ''
      },
      filters: {
        products: {
          status: 'active',
          product_type: '',
          vendor: '',
          created_min: '',
          created_max: '',
          limit: 30
        },
        orders: {
          status: 'any',
          fulfillment_status: '',
          created_min: '',
          created_max: '',
          limit: 30
        },
        customers: {
          email: '',
          limit: 30
        }
      }
    }
  });

  // Data states
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [orders, setOrders] = useState<ShopifyOrder[]>([]);
  const [customers, setCustomers] = useState<ShopifyCustomer[]>([]);
  const [currentUser, setCurrentUser] = useState<ShopifyUser | null>(null);
  const [currentShop, setCurrentShop] = useState<ShopifyShop | null>(null);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // Modal states
  const [createProductModalOpen, setCreateProductModalOpen] = useState(false);
  const [createOrderModalOpen, setCreateOrderModalOpen] = useState(false);
  const [createCustomerModalOpen, setCreateCustomerModalOpen] = useState(false);
  const [updateInventoryModalOpen, setUpdateInventoryModalOpen] = useState(false);
  
  // Form states
  const [productForm, setProductForm] = useState({
    title: '',
    body_html: '',
    vendor: '',
    product_type: '',
    tags: '',
    price: '',
    sku: '',
    inventory_quantity: '0',
    weight: '0',
    requires_shipping: true,
    taxable: true
  });
  
  const [orderForm, setOrderForm] = useState({
    customer_email: '',
    customer_name: '',
    line_items: [] as Array<{
      title: string;
      quantity: number;
      price: string;
    }>,
    shipping_address: {
      first_name: '',
      last_name: '',
      address1: '',
      city: '',
      province: '',
      country: '',
      postal_code: '',
      phone: ''
    },
    billing_address: {
      first_name: '',
      last_name: '',
      address1: '',
      city: '',
      province: '',
      country: '',
      postal_code: '',
      phone: ''
    },
    note: '',
    tags: ''
  });
  
  const [customerForm, setCustomerForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    addresses: [] as Array<{
      first_name: string;
      last_name: string;
      address1: string;
      city: string;
      province: string;
      country: string;
      postal_code: string;
      phone: string;
    }>,
    accepts_marketing: false,
    tags: '',
    note: ''
  });
  
  const [inventoryForm, setInventoryForm] = useState({
    product_id: '',
    variant_id: '',
    inventory_quantity: '',
    location_id: ''
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('shopify_access_token_placeholder');

  const { getInputProps, getIncrementButtonProps, getDecrementButtonProps } = useNumberInput({
    step: 0.01,
    precision: 2,
    defaultValue: 0,
    min: 0
  });
  
  const inc = getIncrementButtonProps();
  const dec = getDecrementButtonProps();

  useEffect(() => {
    checkShopifyHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadShopifyData();
    }
  }, [health]);

  const checkShopifyHealth = async () => {
    try {
      const response = await fetch('/api/integrations/shopify/health');
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
          errors: [data.error || 'Shopify service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Shopify service health']
      });
    }
  };

  const loadShopifyData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadProducts(),
        loadOrders(),
        loadCustomers(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Shopify data');
      toast({
        title: 'Error',
        description: 'Failed to load Shopify data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    try {
      const response = await fetch('/api/integrations/shopify/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          status: config.settings.filters.products.status,
          product_type: config.settings.filters.products.product_type,
          vendor: config.settings.filters.products.vendor,
          created_at_min: config.settings.filters.products.created_min,
          created_at_max: config.settings.filters.products.created_max,
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

  const loadOrders = async () => {
    try {
      const response = await fetch('/api/integrations/shopify/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          status: config.settings.filters.orders.status,
          fulfillment_status: config.settings.filters.orders.fulfillment_status,
          created_at_min: config.settings.filters.orders.created_min,
          created_at_max: config.settings.filters.orders.created_max,
          limit: 30
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setOrders(data.data.orders || []);
      }
    } catch (err) {
      console.error('Error loading orders:', err);
    }
  };

  const loadCustomers = async () => {
    try {
      const response = await fetch('/api/integrations/shopify/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          email: config.settings.filters.customers.email,
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

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/shopify/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCurrentUser(data.data.user);
        setCurrentShop(data.data.shop);
      }
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  };

  const createProduct = async () => {
    if (!productForm.title || !productForm.price) {
      toast({
        title: 'Error',
        description: 'Product title and price are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/shopify/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            title: productForm.title,
            body_html: productForm.body_html,
            vendor: productForm.vendor,
            product_type: productForm.product_type,
            tags: productForm.tags,
            price: productForm.price,
            sku: productForm.sku,
            inventory_quantity: parseInt(productForm.inventory_quantity),
            weight: parseFloat(productForm.weight),
            requires_shipping: productForm.requires_shipping,
            taxable: productForm.taxable,
            variants: [{
              title: 'Default Title',
              price: productForm.price,
              sku: productForm.sku,
              inventory_quantity: parseInt(productForm.inventory_quantity),
              weight: parseFloat(productForm.weight),
              requires_shipping: productForm.requires_shipping,
              taxable: productForm.taxable,
              inventory_policy: 'deny',
              fulfillment_service: 'manual',
              inventory_management: 'shopify',
              option1: 'Default Title',
              option2: null,
              option3: null,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              barcode: '',
              image_id: null,
              grams: Math.round(parseFloat(productForm.weight) * 1000),
              weight_unit: 'g',
              old_inventory_quantity: parseInt(productForm.inventory_quantity),
              admin_graphql_api_id: ''
            }],
            options: [{
              name: 'Title',
              product_id: 1,
              position: 1,
              values: ['Default Title']
            }],
            metafields: []
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Product created successfully',
          status: 'success',
          duration: 3000
        });
        
        setProductForm({
          title: '',
          body_html: '',
          vendor: '',
          product_type: '',
          tags: '',
          price: '',
          sku: '',
          inventory_quantity: '0',
          weight: '0',
          requires_shipping: true,
          taxable: true
        });
        setCreateProductModalOpen(false);
        await loadProducts();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create product',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create product',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const createOrder = async () => {
    if (!orderForm.customer_email || orderForm.line_items.length === 0) {
      toast({
        title: 'Error',
        description: 'Customer email and at least one line item are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/shopify/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            email: orderForm.customer_email,
            line_items: orderForm.line_items,
            shipping_address: orderForm.shipping_address,
            billing_address: orderForm.billing_address,
            customer: {
              first_name: orderForm.customer_name.split(' ')[0],
              last_name: orderForm.customer_name.split(' ').slice(1).join(' '),
              email: orderForm.customer_email
            },
            financial_status: 'pending',
            fulfillment_status: 'unfulfilled',
            currency: 'USD',
            note: orderForm.note,
            tags: orderForm.tags
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Order created successfully',
          status: 'success',
          duration: 3000
        });
        
        setOrderForm({
          customer_email: '',
          customer_name: '',
          line_items: [],
          shipping_address: {
            first_name: '',
            last_name: '',
            address1: '',
            city: '',
            province: '',
            country: '',
            postal_code: '',
            phone: ''
          },
          billing_address: {
            first_name: '',
            last_name: '',
            address1: '',
            city: '',
            province: '',
            country: '',
            postal_code: '',
            phone: ''
          },
          note: '',
          tags: ''
        });
        setCreateOrderModalOpen(false);
        await loadOrders();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create order',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create order',
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
      const response = await fetch('/api/integrations/shopify/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            email: customerForm.email,
            first_name: customerForm.first_name,
            last_name: customerForm.last_name,
            phone: customerForm.phone,
            addresses: customerForm.addresses,
            accepts_marketing: customerForm.accepts_marketing,
            tags: customerForm.tags,
            note: customerForm.note
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
          first_name: '',
          last_name: '',
          email: '',
          phone: '',
          addresses: [],
          accepts_marketing: false,
          tags: '',
          note: ''
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

  const searchShopify = async () => {
    if (!searchQuery.trim()) {
      await Promise.all([
        loadProducts(),
        loadOrders(),
        loadCustomers()
      ]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/shopify/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          type: 'all', // Can be 'products', 'orders', 'customers', 'all'
          limit: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        const searchResults = result.data.results || [];
        
        // Update data based on search results
        const productResults = searchResults.filter((r: any) => r.type === 'product');
        const orderResults = searchResults.filter((r: any) => r.type === 'order');
        const customerResults = searchResults.filter((r: any) => r.type === 'customer');
        
        if (productResults.length > 0) {
          const searchProducts = productResults.map((r: any) => ({
            id: r.id,
            title: r.title,
            body_html: `<p>${r.title}</p>`,
            vendor: r.vendor || 'Test Vendor',
            product_type: r.product_type || 'Test Type',
            created_at: r.created,
            handle: r.handle,
            updated_at: r.created,
            published_at: r.created,
            template_suffix: null,
            status: r.status || 'active',
            published_scope: 'global',
            tags: '',
            admin_graphql_api_id: `gid://shopify/Product/${r.id}`,
            options: [{
              id: 1,
              name: 'Title',
              product_id: r.id,
              position: 1,
              values: ['Default Title']
            }],
            images: [{
              id: 1,
              product_id: r.id,
              position: 1,
              created_at: r.created,
              updated_at: r.created,
              alt: r.title,
              width: 1200,
              height: 1200,
              src: r.image?.src || 'https://cdn.shopify.com/s/files/1/0000/0000/products/default.jpg',
              variant_ids: [1]
            }],
            image: {
              id: 1,
              product_id: r.id,
              position: 1,
              created_at: r.created,
              updated_at: r.created,
              alt: r.title,
              width: 1200,
              height: 1200,
              src: r.image?.src || 'https://cdn.shopify.com/s/files/1/0000/0000/products/default.jpg',
              variant_ids: [1]
            },
            variants: [{
              id: 1,
              product_id: r.id,
              title: 'Default Title',
              price: r.price || '0.00',
              sku: '',
              position: 1,
              grams: 0,
              inventory_policy: 'deny',
              compare_at_price: null,
              fulfillment_service: 'manual',
              inventory_management: 'shopify',
              option1: 'Default Title',
              option2: null,
              option3: null,
              created_at: r.created,
              updated_at: r.created,
              taxable: true,
              barcode: '',
              image_id: 1,
              inventory_quantity: null,
              weight: 0,
              weight_unit: 'g',
              old_inventory_quantity: null,
              requires_shipping: true,
              admin_graphql_api_id: `gid://shopify/ProductVariant/${r.id}`
            }],
            metafields: []
          }));
          setProducts(searchProducts);
        }
        
        if (orderResults.length > 0) {
          const searchOrders = orderResults.map((r: any) => ({
            id: r.id,
            name: r.name,
            order_number: parseInt(r.name.replace('#', '')),
            created_at: r.created,
            email: r.email,
            total_price: r.total_price,
            financial_status: r.financial_status || 'pending',
            fulfillment_status: r.fulfillment_status || 'unfulfilled',
            customer: {
              id: 1,
              email: r.email,
              first_name: r.email?.split('@')[0],
              last_name: 'Customer'
            },
            line_items: [],
            billing_address: null,
            shipping_address: null,
            tags: '',
            note: null,
            subtotal_price: r.total_price,
            total_tax: '0.00',
            currency: 'USD',
            confirmed: true,
            buyer_accepts_marketing: false,
            app_id: null,
            browser_ip: '',
            client_details: {
              browser_ip: '',
              accept_language: 'en',
              user_agent: '',
              session_hash: null,
              browser_width: 1200,
              browser_height: 800
            },
            cancel_reason: null,
            cancelled_at: null,
            cart_token: null,
            checkout_id: 123456,
            checkout_token: '',
            closed_at: null,
            contact_email: r.email,
            current_subtotal_price: r.total_price,
            current_total_price: r.total_price,
            current_total_tax: '0.00',
            customer_locale: 'en',
            device_id: null,
            discount_codes: [],
            estimated_taxes: false,
            gateway: 'manual',
            landing_site: '/',
            note_attributes: [],
            number: 1,
            order_status_url: '',
            payment_gateway_names: ['manual'],
            phone: '',
            presentment_currency: 'USD',
            processed_at: r.created,
            processing_method: 'manual',
            reference: null,
            referring_site: '',
            source_identifier: null,
            source_name: 'web',
            source_url: null,
            subtotal_price: r.total_price,
            tax_lines: [],
            taxes_included: false,
            test: false,
            token: '',
            total_discounts: '0.00',
            total_line_items_price: r.total_price,
            total_outstanding: r.total_price,
            total_price: r.total_price,
            total_tip_received: '0.00',
            total_weight: 0,
            updated_at: r.created,
            user_id: null,
            discount_applications: [],
            fulfillments: [],
            payment_details: {},
            refunds: [],
            shipping_lines: []
          }));
          setOrders(searchOrders);
        }
        
        if (customerResults.length > 0) {
          const searchCustomers = customerResults.map((r: any) => ({
            id: r.id,
            email: r.email,
            created_at: r.created,
            updated_at: r.created,
            first_name: r.first_name,
            last_name: r.last_name,
            state: 'enabled',
            note: null,
            verified_email: true,
            multipass_identifier: null,
            tax_exempt: false,
            tags: '',
            last_order_id: null,
            last_order_name: null,
            currency: 'USD',
            total_spent: r.total_spent || '0.00',
            phone: r.phone || '',
            addresses: [],
            accepts_marketing: false,
            accepts_marketing_updated_at: r.created,
            marketing_opt_in_level: 'single_opt_in',
            tax_exemptions: [],
            sms_marketing_consent: null,
            admin_graphql_api_id: `gid://shopify/Customer/${r.id}`
          }));
          setCustomers(searchCustomers);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Shopify',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startShopifyOAuth = async () => {
    try {
      const response = await fetch('/api/auth/shopify/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: SHOPIFY_SCOPES,
          redirect_uri: 'http://localhost:3000/oauth/shopify/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        const popup = window.open(
          data.authorization_url,
          'shopify-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkShopifyHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Shopify OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Shopify OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderProductCard = (product: ShopifyProduct) => (
    <Card key={product.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={PackageIcon} color="orange.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {product.title}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {product.product_type} by {product.vendor}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={product.status === 'active' ? 'green' : 'gray'}>
                {product.status}
              </Badge>
            </HStack>
          </HStack>
          
          {product.body_html && (
            <Text fontSize="sm" color="gray.600" noOfLines={2} dangerouslySetInnerHTML={{ __html: product.body_html }} />
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>💰 ${product.variants[0]?.price || '0.00'}</Text>
            <Text>📦 {product.variants[0]?.inventory_quantity || 0} in stock</Text>
            <Text>📅 {new Date(product.created_at).toLocaleDateString()}</Text>
          </HStack>
          
          {product.tags && (
            <HStack spacing={2} flexWrap="wrap">
              {product.tags.split(',').slice(0, 3).map((tag, index) => (
                <Tag key={index} size="sm" colorScheme="gray">
                  {tag.trim()}
                </Tag>
              ))}
              {product.tags.split(',').length > 3 && (
                <Text fontSize="xs" color="gray.500">
                  +{product.tags.split(',').length - 3} more
                </Text>
              )}
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              {product.variants.length} variant{product.variants.length !== 1 ? 's' : ''}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://${currentShop?.domain}.myshopify.com/admin/products/${product.id}`, '_blank')}>
                  View Product
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Product
                </MenuItem>
                <MenuItem icon={<DollarSignIcon />}>
                  View Prices
                </MenuItem>
                <MenuItem icon={<InventoryIcon />}>
                  Manage Inventory
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

  const renderOrderCard = (order: ShopifyOrder) => (
    <Card key={order.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={ShoppingCartIcon} color="blue.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {order.name}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {order.email}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={order.financial_status === 'paid' ? 'green' : order.financial_status === 'pending' ? 'yellow' : 'red'}>
                {order.financial_status}
              </Badge>
              <Badge colorScheme={order.fulfillment_status === 'fulfilled' ? 'green' : order.fulfillment_status === 'partial' ? 'yellow' : 'gray'}>
                {order.fulfillment_status || 'unfulfilled'}
              </Badge>
            </HStack>
          </HStack>
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>💰 ${order.total_price}</Text>
            <Text>📦 {order.line_items?.length || 0} items</Text>
            <Text>📅 {new Date(order.created_at).toLocaleDateString()}</Text>
          </HStack>
          
          {order.customer && (
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Customer:</Text>
              <Text fontSize="sm" color="gray.700">
                {order.customer.first_name} {order.customer.last_name}
              </Text>
            </VStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Payment: {order.gateway}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://${currentShop?.domain}.myshopify.com/admin/orders/${order.id}`, '_blank')}>
                  View Order
                </MenuItem>
                <MenuItem icon={<TruckIcon />}>
                  Fulfill Order
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Order
                </MenuItem>
                <MenuItem icon={<ReceiptIcon />}>
                  Send Invoice
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

  const renderCustomerCard = (customer: ShopifyCustomer) => (
    <Card key={customer.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={UserIcon} color="purple.500" />
              <VStack align="start" spacing={0}>
                <Heading size="sm" noOfLines={1}>
                  {customer.first_name} {customer.last_name}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {customer.email}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              <Badge colorScheme={customer.state === 'enabled' ? 'green' : 'gray'}>
                {customer.state}
              </Badge>
            </HStack>
          </HStack>
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            <Text>💰 ${customer.total_spent}</Text>
            <Text>📅 {new Date(customer.created_at).toLocaleDateString()}</Text>
            {customer.accepts_marketing && <Text>📧 Marketing</Text>}
          </HStack>
          
          {customer.addresses && customer.addresses.length > 0 && (
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Address:</Text>
              <Text fontSize="sm" color="gray.700">
                {customer.addresses[0].address1}, {customer.addresses[0].city}, {customer.addresses[0].province}
              </Text>
            </VStack>
          )}
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              {customer.addresses?.length || 0} address{customer.addresses?.length !== 1 ? 'es' : ''}
            </Text>
            
            <Menu>
              <MenuButton as={IconButton} icon={<ChevronDownIcon />} variant="ghost" size="sm">
              </MenuButton>
              <MenuList>
                <MenuItem icon={<ViewIcon />} onClick={() => window.open(`https://${currentShop?.domain}.myshopify.com/admin/customers/${customer.id}`, '_blank')}>
                  View Customer
                </MenuItem>
                <MenuItem icon={<EditIcon />}>
                  Edit Customer
                </MenuItem>
                <MenuItem icon={<ShoppingCartIcon />}>
                  View Orders
                </MenuItem>
                <MenuItem icon={<EmailIcon />}>
                  Send Email
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
            <AlertTitle>Shopify Not Connected</AlertTitle>
            <AlertDescription>
              Please connect your Shopify store to access products, orders, and customers.
            </AlertDescription>
          </Box>
        </Alert>
        <Button
          mt={4}
          colorScheme="blue"
          onClick={startShopifyOAuth}
        >
          Connect Shopify Store
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Shopify Integration</Heading>
          <Text color="gray.600">Manage products, orders, customers, and inventory</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search products, orders, customers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchShopify()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="blue"
            onClick={searchShopify}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<PlusIcon />}
            colorScheme="orange"
            onClick={() => setCreateProductModalOpen(true)}
          >
            New Product
          </Button>
          
          <Button
            leftIcon={<ShoppingCartIcon />}
            colorScheme="purple"
            onClick={() => setCreateOrderModalOpen(true)}
          >
            New Order
          </Button>
          
          <Button
            leftIcon={<UserIcon />}
            colorScheme="green"
            onClick={() => setCreateCustomerModalOpen(true)}
          >
            New Customer
          </Button>
        </HStack>

        {/* Stats Overview */}
        {currentShop && (
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>Total Products</StatLabel>
              <StatNumber>{products.length}</StatNumber>
              <StatHelpText>Active listings</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Total Orders</StatLabel>
              <StatNumber>{orders.length}</StatNumber>
              <StatHelpText>All time orders</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Total Customers</StatLabel>
              <StatNumber>{customers.length}</StatNumber>
              <StatHelpText>Registered customers</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Shop</StatLabel>
              <StatNumber>{currentShop.name}</StatNumber>
              <StatHelpText>{currentShop.currency}</StatHelpText>
            </Stat>
          </SimpleGrid>
        )}

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <PackageIcon />
                <Text>Products ({products.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <ShoppingCartIcon />
                <Text>Orders ({orders.length})</Text>
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
                <StoreIcon />
                <Text>Shop Info</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
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

            {/* Orders Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : orders.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <ShoppingCartIcon fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No orders found</Text>
                  <Button
                    mt={4}
                    colorScheme="purple"
                    onClick={() => setCreateOrderModalOpen(true)}
                  >
                    Create Your First Order
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {orders.map(renderOrderCard)}
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
                    colorScheme="green"
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

            {/* Shop Info Tab */}
            <TabPanel>
              {currentShop && currentUser && (
                <Card>
                  <CardBody p={6}>
                    <VStack spacing={4} align="center">
                      <Avatar
                        name={currentShop.name}
                        size="2xl"
                        bg="blue.500"
                        color="white"
                      />
                      <VStack align="center" spacing={2}>
                        <Heading size="lg">{currentShop.name}</Heading>
                        <Text color="gray.600">{currentShop.domain}</Text>
                        <Text fontSize="sm" color="gray.500">
                          Shop ID: {currentUser.id}
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
                            <Badge colorScheme="orange">Products</Badge>
                            <Badge colorScheme="purple">Orders</Badge>
                            <Badge colorScheme="green">Customers</Badge>
                            <Badge colorScheme="blue">Inventory</Badge>
                            <Badge colorScheme="teal">Shipping</Badge>
                          </HStack>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Domain</Text>
                          <Text>{currentShop.domain}.myshopify.com</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Currency</Text>
                          <Text>{currentShop.currency}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Timezone</Text>
                          <Text>{currentShop.timezone}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Shop Email</Text>
                          <Text>{currentShop.email}</Text>
                        </HStack>
                        
                        <HStack justify="space-between" w="full">
                          <Text>Account Owner</Text>
                          <Badge colorScheme={currentUser.account_owner ? 'green' : 'gray'}>
                            {currentUser.account_owner ? 'Owner' : 'Collaborator'}
                          </Badge>
                        </HStack>
                        
                        <Button
                          colorScheme="blue"
                          onClick={() => window.open(`https://${currentShop.domain}.myshopify.com/admin`, '_blank')}
                        >
                          Open Shopify Admin
                        </Button>
                      </VStack>
                    </VStack>
                  </CardBody>
                </Card>
              )}
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Product Modal */}
        <Modal isOpen={createProductModalOpen} onClose={() => setCreateProductModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Product</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Product Title</FormLabel>
                  <Input
                    value={productForm.title}
                    onChange={(e) => setProductForm({...productForm, title: e.target.value})}
                    placeholder="Enter product title"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={productForm.body_html}
                    onChange={(e) => setProductForm({...productForm, body_html: e.target.value})}
                    placeholder="Enter product description"
                    rows={4}
                  />
                </FormControl>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Vendor</FormLabel>
                    <Input
                      value={productForm.vendor}
                      onChange={(e) => setProductForm({...productForm, vendor: e.target.value})}
                      placeholder="Enter vendor name"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Product Type</FormLabel>
                    <Select
                      value={productForm.product_type}
                      onChange={(e) => setProductForm({...productForm, product_type: e.target.value})}
                      placeholder="Select product type"
                    >
                      <option value="">Select type</option>
                      <option value="Electronics">Electronics</option>
                      <option value="Clothing">Clothing</option>
                      <option value="Home">Home & Garden</option>
                      <option value="Beauty">Beauty & Health</option>
                      <option value="Sports">Sports & Outdoors</option>
                      <option value="Books">Books & Media</option>
                    </Select>
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl isRequired>
                    <FormLabel>Price</FormLabel>
                    <InputGroup>
                      <InputLeftElement>$</InputLeftElement>
                      <Input
                        value={productForm.price}
                        onChange={(e) => setProductForm({...productForm, price: e.target.value})}
                        placeholder="0.00"
                        type="number"
                        step="0.01"
                      />
                    </InputGroup>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>SKU</FormLabel>
                    <Input
                      value={productForm.sku}
                      onChange={(e) => setProductForm({...productForm, sku: e.target.value})}
                      placeholder="Enter SKU"
                    />
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Inventory Quantity</FormLabel>
                    <Input
                      value={productForm.inventory_quantity}
                      onChange={(e) => setProductForm({...productForm, inventory_quantity: e.target.value})}
                      placeholder="0"
                      type="number"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Weight (kg)</FormLabel>
                    <Input
                      value={productForm.weight}
                      onChange={(e) => setProductForm({...productForm, weight: e.target.value})}
                      placeholder="0.0"
                      type="number"
                      step="0.1"
                    />
                  </FormControl>
                </HStack>
                
                <HStack>
                  <FormControl>
                    <FormLabel>Shipping</FormLabel>
                    <Switch
                      isChecked={productForm.requires_shipping}
                      onChange={(e) => setProductForm({...productForm, requires_shipping: e.target.checked})}
                    >
                      Requires shipping
                    </Switch>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Taxable</FormLabel>
                    <Switch
                      isChecked={productForm.taxable}
                      onChange={(e) => setProductForm({...productForm, taxable: e.target.checked})}
                    >
                      Taxable
                    </Switch>
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Tags</FormLabel>
                  <Input
                    value={productForm.tags}
                    onChange={(e) => setProductForm({...productForm, tags: e.target.value})}
                    placeholder="Enter tags (comma separated)"
                  />
                  <FormHelperText>Separate multiple tags with commas</FormHelperText>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateProductModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={createProduct}
                isLoading={loading}
              >
                Create Product
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Order Modal */}
        <Modal isOpen={createOrderModalOpen} onClose={() => setCreateOrderModalOpen(false)} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Order</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <HStack>
                  <FormControl isRequired>
                    <FormLabel>Customer Email</FormLabel>
                    <Input
                      value={orderForm.customer_email}
                      onChange={(e) => setOrderForm({...orderForm, customer_email: e.target.value})}
                      placeholder="Enter customer email"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Customer Name</FormLabel>
                    <Input
                      value={orderForm.customer_name}
                      onChange={(e) => setOrderForm({...orderForm, customer_name: e.target.value})}
                      placeholder="Enter customer name"
                    />
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Order Note</FormLabel>
                  <Textarea
                    value={orderForm.note}
                    onChange={(e) => setOrderForm({...orderForm, note: e.target.value})}
                    placeholder="Enter order note"
                    rows={3}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Tags</FormLabel>
                  <Input
                    value={orderForm.tags}
                    onChange={(e) => setOrderForm({...orderForm, tags: e.target.value})}
                    placeholder="Enter tags (comma separated)"
                  />
                </FormControl>
                
                <Box w="full">
                  <HStack justify="space-between" mb={2}>
                    <Text fontWeight="medium">Order Items</Text>
                    <Button
                      size="sm"
                      colorScheme="blue"
                      onClick={() => setOrderForm({
                        ...orderForm,
                        line_items: [...orderForm.line_items, {
                          title: '',
                          quantity: 1,
                          price: '0.00'
                        }]
                      })}
                    >
                      Add Item
                    </Button>
                  </HStack>
                  
                  <VStack spacing={2} w="full">
                    {orderForm.line_items.map((item, index) => (
                      <HStack key={index} w="full">
                        <FormControl>
                          <FormLabel fontSize="sm">Product</FormLabel>
                          <Input
                            value={item.title}
                            onChange={(e) => {
                              const newItems = [...orderForm.line_items];
                              newItems[index].title = e.target.value;
                              setOrderForm({...orderForm, line_items: newItems});
                            }}
                            placeholder="Product title"
                            size="sm"
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel fontSize="sm">Quantity</FormLabel>
                          <Input
                            value={item.quantity}
                            onChange={(e) => {
                              const newItems = [...orderForm.line_items];
                              newItems[index].quantity = parseInt(e.target.value) || 1;
                              setOrderForm({...orderForm, line_items: newItems});
                            }}
                            type="number"
                            min="1"
                            placeholder="1"
                            size="sm"
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel fontSize="sm">Price</FormLabel>
                          <Input
                            value={item.price}
                            onChange={(e) => {
                              const newItems = [...orderForm.line_items];
                              newItems[index].price = e.target.value;
                              setOrderForm({...orderForm, line_items: newItems});
                            }}
                            placeholder="0.00"
                            size="sm"
                          />
                        </FormControl>
                        
                        <IconButton
                          icon={<CloseIcon />}
                          aria-label="Remove item"
                          colorScheme="red"
                          size="sm"
                          onClick={() => {
                            const newItems = orderForm.line_items.filter((_, i) => i !== index);
                            setOrderForm({...orderForm, line_items: newItems});
                          }}
                        />
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateOrderModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={createOrder}
                isLoading={loading}
              >
                Create Order
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
                <HStack>
                  <FormControl>
                    <FormLabel>First Name</FormLabel>
                    <Input
                      value={customerForm.first_name}
                      onChange={(e) => setCustomerForm({...customerForm, first_name: e.target.value})}
                      placeholder="Enter first name"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Last Name</FormLabel>
                    <Input
                      value={customerForm.last_name}
                      onChange={(e) => setCustomerForm({...customerForm, last_name: e.target.value})}
                      placeholder="Enter last name"
                    />
                  </FormControl>
                </HStack>
                
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
                    placeholder="Enter phone number"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Customer Note</FormLabel>
                  <Textarea
                    value={customerForm.note}
                    onChange={(e) => setCustomerForm({...customerForm, note: e.target.value})}
                    placeholder="Enter customer note"
                    rows={3}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Tags</FormLabel>
                  <Input
                    value={customerForm.tags}
                    onChange={(e) => setCustomerForm({...customerForm, tags: e.target.value})}
                    placeholder="Enter tags (comma separated)"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Marketing</FormLabel>
                  <Switch
                    isChecked={customerForm.accepts_marketing}
                    onChange={(e) => setCustomerForm({...customerForm, accepts_marketing: e.target.checked})}
                  >
                    Accepts marketing emails
                  </Switch>
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
                colorScheme="green"
                onClick={createCustomer}
                isLoading={loading}
              >
                Create Customer
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default ShopifyIntegrationManager;