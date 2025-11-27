import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, CheckCircle, AlertTriangle, Clock, ArrowRight, PlusSquare, Star, User, Settings, ChevronDown, Search, ChevronUp, Trash2, Edit, Eye, Mail, Phone, Calendar, MessageSquare } from "lucide-react";
import { Switch } from "@/components/ui/switch";

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

  const { toast } = useToast();
  // const bgColor = useColorModeValue("white", "gray.800"); // Removed
  // const borderColor = useColorModeValue("gray.200", "gray.700"); // Removed

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
    <div className="min-h-screen bg-white p-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold">Stripe Integration</h1>
          <p className="text-gray-600 text-lg">
            Complete payment processing and financial management
          </p>
        </div>

        {/* Quick Stats */}
        {analytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Total Revenue</p>
                  <div className="text-2xl font-bold">{formatCurrency(analytics.totalRevenue)}</div>
                  <div className="flex items-center text-xs">
                    {analytics.revenueGrowth > 0 ? (
                      <ArrowRight className="mr-1 h-4 w-4 rotate-[-45deg] text-green-500" />
                    ) : (
                      <ArrowRight className="mr-1 h-4 w-4 rotate-[45deg] text-red-500" />
                    )}
                    <span className={analytics.revenueGrowth > 0 ? "text-green-500" : "text-red-500"}>
                      {Math.abs(analytics.revenueGrowth)}%
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Monthly Recurring</p>
                  <div className="text-2xl font-bold">{formatCurrency(analytics.monthlyRecurringRevenue)}</div>
                  <p className="text-xs text-muted-foreground">Active subscriptions</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Active Customers</p>
                  <div className="text-2xl font-bold">{analytics.activeCustomers}</div>
                  <div className="flex items-center text-xs">
                    {analytics.customerGrowth > 0 ? (
                      <ArrowRight className="mr-1 h-4 w-4 rotate-[-45deg] text-green-500" />
                    ) : (
                      <ArrowRight className="mr-1 h-4 w-4 rotate-[45deg] text-red-500" />
                    )}
                    <span className={analytics.customerGrowth > 0 ? "text-green-500" : "text-red-500"}>
                      {Math.abs(analytics.customerGrowth)}%
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Success Rate</p>
                  <div className="text-2xl font-bold">{analytics.paymentSuccessRate}%</div>
                  <p className="text-xs text-muted-foreground">
                    Of {analytics.totalPayments} payments
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Main Content Tabs */}
        <Tabs defaultValue="payments" className="w-full" onValueChange={(val) => setActiveTab(["payments", "customers", "subscriptions", "products", "analytics"].indexOf(val))}>
          <TabsList className="grid w-full grid-cols-5 mb-4">
            <TabsTrigger value="payments">Payments</TabsTrigger>
            <TabsTrigger value="customers">Customers</TabsTrigger>
            <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
            <TabsTrigger value="products">Products</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
          </TabsList>

          <Card>
            <CardContent className="p-6">
              {/* Payments Tab */}
              <TabsContent value="payments" className="mt-0">
                <div className="space-y-6">
                  <div className="flex justify-between items-center">
                    <h2 className="text-2xl font-semibold">Payment Management</h2>
                    <Button onClick={() => setIsCreatePaymentOpen(true)}>
                      <PlusSquare className="mr-2 h-4 w-4" />
                      Create Payment
                    </Button>
                  </div>

                  <div className="flex items-center space-x-4">
                    <Input
                      placeholder="Search payments..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="max-w-sm"
                    />
                    <Select
                      value={statusFilter}
                      onValueChange={(value) => setStatusFilter(value)}
                    >
                      <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="All Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="succeeded">Succeeded</SelectItem>
                        <SelectItem value="failed">Failed</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="rounded-md border">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-muted/50 text-muted-foreground">
                        <tr>
                          <th className="h-12 px-4 font-medium">ID</th>
                          <th className="h-12 px-4 font-medium">Amount</th>
                          <th className="h-12 px-4 font-medium">Customer</th>
                          <th className="h-12 px-4 font-medium">Description</th>
                          <th className="h-12 px-4 font-medium">Status</th>
                          <th className="h-12 px-4 font-medium">Date</th>
                          <th className="h-12 px-4 font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPayments.map((payment) => (
                          <tr key={payment.id} className="border-t hover:bg-muted/50">
                            <td className="p-4 font-mono text-xs">
                              {payment.id.substring(0, 12)}...
                            </td>
                            <td className="p-4">{formatCurrency(payment.amount)}</td>
                            <td className="p-4">
                              {payment.customer ? (
                                <div className="flex items-center gap-2">
                                  <Avatar className="h-6 w-6">
                                    <AvatarImage src={payment.customer.avatar_url} />
                                    <AvatarFallback>{payment.customer.name[0]}</AvatarFallback>
                                  </Avatar>
                                  <span className="text-sm">{payment.customer.name}</span>
                                </div>
                              ) : (
                                <span className="text-muted-foreground">Anonymous</span>
                              )}
                            </td>
                            <td className="p-4">
                              <span className="line-clamp-2 text-sm">
                                {payment.description}
                              </span>
                            </td>
                            <td className="p-4">
                              <Badge
                                variant={
                                  payment.status === "succeeded"
                                    ? "default"
                                    : payment.status === "failed"
                                      ? "destructive"
                                      : "secondary"
                                }
                                className={
                                  payment.status === "succeeded"
                                    ? "bg-green-100 text-green-800 hover:bg-green-100"
                                    : payment.status === "pending"
                                      ? "bg-yellow-100 text-yellow-800 hover:bg-yellow-100"
                                      : ""
                                }
                              >
                                {payment.status}
                              </Badge>
                            </td>
                            <td className="p-4">{formatDate(payment.created)}</td>
                            <td className="p-4">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  window.open(payment.receipt_url, "_blank")
                                }
                              >
                                Receipt
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              {/* Customers Tab */}
              <TabsContent value="customers" className="mt-0">
                <div className="space-y-6">
                  <div className="flex justify-between items-center">
                    <h2 className="text-2xl font-semibold">Customer Management</h2>
                    <Button onClick={() => setIsCreateCustomerOpen(true)}>
                      <PlusSquare className="mr-2 h-4 w-4" />
                      Add Customer
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {customers.map((customer) => (
                      <Card key={customer.id}>
                        <CardContent className="p-6">
                          <div className="space-y-4">
                            <div className="flex items-center gap-3">
                              <Avatar className="h-10 w-10">
                                <AvatarImage src={customer.avatar_url} />
                                <AvatarFallback>{customer.name[0]}</AvatarFallback>
                              </Avatar>
                              <div>
                                <h3 className="font-semibold">{customer.name}</h3>
                                <p className="text-sm text-muted-foreground">
                                  {customer.email}
                                </p>
                              </div>
                            </div>

                            <div className="space-y-2 w-full">
                              <div className="flex justify-between w-full">
                                <span className="font-medium">Balance:</span>
                                <span>{formatCurrency(customer.balance)}</span>
                              </div>
                              <div className="flex justify-between w-full">
                                <span className="font-medium">Subscriptions:</span>
                                <span>{customer.subscriptions_count}</span>
                              </div>
                              <div className="flex justify-between w-full">
                                <span className="font-medium">Created:</span>
                                <span className="text-sm">
                                  {formatDate(customer.created)}
                                </span>
                              </div>
                            </div>

                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full"
                              onClick={() => setSelectedCustomer(customer)}
                            >
                              View Details
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </TabsContent>

              {/* Subscriptions Tab */}
              <TabsContent value="subscriptions" className="mt-0">
                <div className="space-y-6">
                  <div className="flex justify-between items-center">
                    <h2 className="text-2xl font-semibold">Subscription Management</h2>
                    <Button onClick={() => setIsCreateSubscriptionOpen(true)}>
                      <PlusSquare className="mr-2 h-4 w-4" />
                      Create Subscription
                    </Button>
                  </div>

                  <div className="rounded-md border">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-muted/50 text-muted-foreground">
                        <tr>
                          <th className="h-12 px-4 font-medium">ID</th>
                          <th className="h-12 px-4 font-medium">Customer</th>
                          <th className="h-12 px-4 font-medium">Plan</th>
                          <th className="h-12 px-4 font-medium">Status</th>
                          <th className="h-12 px-4 font-medium">Amount</th>
                          <th className="h-12 px-4 font-medium">Next Payment</th>
                          <th className="h-12 px-4 font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subscriptions.map((sub) => (
                          <tr key={sub.id} className="border-t hover:bg-muted/50">
                            <td className="p-4 font-mono text-xs">
                              {sub.id.substring(0, 12)}...
                            </td>
                            <td className="p-4">
                              {sub.customer ? (
                                <div className="flex items-center gap-2">
                                  <Avatar className="h-6 w-6">
                                    <AvatarImage src={sub.customer.avatar_url} />
                                    <AvatarFallback>{sub.customer.name[0]}</AvatarFallback>
                                  </Avatar>
                                  <span className="text-sm">{sub.customer.name}</span>
                                </div>
                              ) : (
                                <span className="text-muted-foreground">Anonymous</span>
                              )}
                            </td>
                            <td className="p-4">
                              <div className="font-medium">{sub.plan_name}</div>
                              <div className="text-xs text-muted-foreground">
                                {sub.plan_description}
                              </div>
                            </td>
                            <td className="p-4">
                              <Badge
                                variant={
                                  sub.status === "active"
                                    ? "default"
                                    : sub.status === "canceled"
                                      ? "destructive"
                                      : "secondary"
                                }
                                className={
                                  sub.status === "active"
                                    ? "bg-green-100 text-green-800 hover:bg-green-100"
                                    : sub.status === "past_due"
                                      ? "bg-red-100 text-red-800 hover:bg-red-100"
                                      : ""
                                }
                              >
                                {sub.status}
                              </Badge>
                            </td>
                            <td className="p-4">
                              {formatCurrency(sub.amount)} / {sub.interval}
                            </td>
                            <td className="p-4">{formatDate(sub.next_payment_date)}</td>
                            <td className="p-4">
                              <Select
                                onValueChange={(value) =>
                                  handleSubscriptionAction(sub.id, value)
                                }
                              >
                                <SelectTrigger className="w-[130px]">
                                  <SelectValue placeholder="Actions" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="cancel">Cancel</SelectItem>
                                  <SelectItem value="pause">Pause</SelectItem>
                                  <SelectItem value="upgrade">Upgrade</SelectItem>
                                </SelectContent>
                              </Select>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </TabsContent>

              {/* Products Tab */}
              <TabsContent value="products" className="mt-0">
                <div className="space-y-6">
                  <div className="flex justify-between items-center">
                    <h2 className="text-2xl font-semibold">Product Management</h2>
                    <Button onClick={() => setIsCreateProductOpen(true)}>
                      <PlusSquare className="mr-2 h-4 w-4" />
                      Create Product
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {products.map((product) => (
                      <Card key={product.id}>
                        <CardContent className="p-6">
                          <div className="space-y-4">
                            <div className="aspect-video relative rounded-md bg-muted flex items-center justify-center overflow-hidden">
                              {product.images && product.images.length > 0 ? (
                                <img
                                  src={product.images[0]}
                                  alt={product.name}
                                  className="object-cover w-full h-full"
                                />
                              ) : (
                                <Star className="h-8 w-8 text-muted-foreground" />
                              )}
                            </div>
                            <div>
                              <h3 className="font-semibold text-lg">{product.name}</h3>
                              <p className="text-sm text-muted-foreground line-clamp-2">
                                {product.description}
                              </p>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-lg">
                                {formatCurrency(product.price)}
                              </span>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setSelectedProduct(product)}
                              >
                                Edit
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </TabsContent>

              {/* Analytics Tab - Placeholder */}
              <TabsContent value="analytics" className="mt-0">
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="rounded-full bg-muted p-4 mb-4">
                    <Star className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold">Analytics Dashboard</h3>
                  <p className="text-muted-foreground max-w-sm mt-2">
                    Detailed analytics and reporting features coming soon.
                  </p>
                </div>
              </TabsContent>
            </CardContent>
          </Card>
        </Tabs>

        {/* Create Payment Modal */}
        <Dialog open={isCreatePaymentOpen} onOpenChange={setIsCreatePaymentOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Payment</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Amount</label>
                <Input
                  type="number"
                  placeholder="0.00"
                  value={newPaymentAmount}
                  onChange={(e) => setNewPaymentAmount(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Currency</label>
                <Input
                  placeholder="USD"
                  value={newPaymentCurrency}
                  onChange={(e) => setNewPaymentCurrency(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Description</label>
                <Textarea
                  placeholder="Payment description"
                  value={newPaymentDescription}
                  onChange={(e) => setNewPaymentDescription(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsCreatePaymentOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={() =>
                  createPayment(
                    parseFloat(newPaymentAmount),
                    newPaymentCurrency,
                    newPaymentDescription,
                  )
                }
                disabled={!newPaymentAmount}
              >
                Create Payment
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Create Customer Modal */}
        <Dialog open={isCreateCustomerOpen} onOpenChange={setIsCreateCustomerOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Customer</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Name</label>
                <Input
                  placeholder="Customer name"
                  value={newCustomerName}
                  onChange={(e) => setNewCustomerName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Email</label>
                <Input
                  type="email"
                  placeholder="customer@example.com"
                  value={newCustomerEmail}
                  onChange={(e) => setNewCustomerEmail(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsCreateCustomerOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={() =>
                  createCustomer(newCustomerName, newCustomerEmail)
                }
                disabled={!newCustomerName || !newCustomerEmail}
              >
                Add Customer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Create Product Modal */}
        <Dialog open={isCreateProductOpen} onOpenChange={setIsCreateProductOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Product</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Product Name</label>
                <Input
                  placeholder="Product name"
                  value={newProductName}
                  onChange={(e) => setNewProductName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Description</label>
                <Textarea
                  placeholder="Product description"
                  value={newProductDescription}
                  onChange={(e) => setNewProductDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Price</label>
                <Input
                  type="number"
                  placeholder="0.00"
                  value={newProductPrice}
                  onChange={(e) => setNewProductPrice(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsCreateProductOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={() =>
                  createProduct(
                    newProductName,
                    newProductDescription,
                    parseFloat(newProductPrice),
                  )
                }
                disabled={!newProductName || !newProductPrice}
              >
                Add Product
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default StripeIntegration;
