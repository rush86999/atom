import React, { useState, useEffect } from "react";

interface ShopifyProduct {
  id: string;
  title: string;
  description?: string;
  price: string;
  compare_at_price?: string;
  inventory_quantity: number;
  vendor: string;
  product_type: string;
  status: "active" | "draft" | "archived";
  featured_image?: string;
  created_at: string;
  updated_at: string;
  variants_count: number;
  tags: string[];
}

interface ShopifyOrder {
  id: string;
  order_number: number;
  email: string;
  customer_name: string;
  total_price: string;
  financial_status: "paid" | "pending" | "refunded" | "voided";
  fulfillment_status: "fulfilled" | "partial" | "unfulfilled";
  created_at: string;
  line_items: Array<{
    title: string;
    quantity: number;
    price: string;
  }>;
}

interface ShopifyCustomer {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  orders_count: number;
  total_spent: string;
  created_at: string;
  tags: string[];
  default_address?: {
    address1: string;
    city: string;
    province: string;
    country: string;
    zip: string;
  };
}

interface ShopifyAnalytics {
  total_sales: string;
  total_orders: number;
  total_customers: number;
  average_order_value: string;
  conversion_rate: number;
  top_selling_products: Array<{
    title: string;
    quantity_sold: number;
    revenue: string;
  }>;
}

interface ShopifyIntegrationProps {
  userId: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  isConnected?: boolean;
}

export const ShopifyIntegration: React.FC<ShopifyIntegrationProps> = ({
  userId,
  onConnect,
  onDisconnect,
  isConnected = false,
}) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [orders, setOrders] = useState<ShopifyOrder[]>([]);
  const [customers, setCustomers] = useState<ShopifyCustomer[]>([]);
  const [analytics, setAnalytics] = useState<ShopifyAnalytics | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connected" | "disconnected" | "connecting"
  >(isConnected ? "connected" : "disconnected");

  // Mock data for demonstration
  const mockProducts: ShopifyProduct[] = [
    {
      id: "prod-1",
      title: "Premium Wireless Headphones",
      description: "High-quality wireless headphones with noise cancellation",
      price: "$199.99",
      compare_at_price: "$249.99",
      inventory_quantity: 45,
      vendor: "AudioTech",
      product_type: "Electronics",
      status: "active",
      featured_image: "https://via.placeholder.com/200x200",
      created_at: "2024-01-15T10:30:00Z",
      updated_at: "2024-01-20T14:20:00Z",
      variants_count: 3,
      tags: ["wireless", "audio", "premium"],
    },
    {
      id: "prod-2",
      title: "Organic Cotton T-Shirt",
      description: "Comfortable organic cotton t-shirt in various colors",
      price: "$29.99",
      inventory_quantity: 120,
      vendor: "EcoWear",
      product_type: "Apparel",
      status: "active",
      featured_image: "https://via.placeholder.com/200x200",
      created_at: "2024-01-10T09:15:00Z",
      updated_at: "2024-01-18T11:45:00Z",
      variants_count: 5,
      tags: ["organic", "clothing", "sustainable"],
    },
    {
      id: "prod-3",
      title: "Stainless Steel Water Bottle",
      description:
        "Durable stainless steel water bottle, keeps drinks cold for 24 hours",
      price: "$34.99",
      compare_at_price: "$39.99",
      inventory_quantity: 78,
      vendor: "HydroLife",
      product_type: "Accessories",
      status: "active",
      featured_image: "https://via.placeholder.com/200x200",
      created_at: "2024-01-12T13:20:00Z",
      updated_at: "2024-01-19T16:30:00Z",
      variants_count: 2,
      tags: ["eco-friendly", "hydration", "outdoor"],
    },
  ];

  const mockOrders: ShopifyOrder[] = [
    {
      id: "order-1",
      order_number: 1001,
      email: "customer1@example.com",
      customer_name: "John Smith",
      total_price: "$229.98",
      financial_status: "paid",
      fulfillment_status: "fulfilled",
      created_at: "2024-01-20T09:30:00Z",
      line_items: [
        { title: "Premium Wireless Headphones", quantity: 1, price: "$199.99" },
        { title: "Organic Cotton T-Shirt", quantity: 1, price: "$29.99" },
      ],
    },
    {
      id: "order-2",
      order_number: 1002,
      email: "customer2@example.com",
      customer_name: "Sarah Johnson",
      total_price: "$34.99",
      financial_status: "paid",
      fulfillment_status: "unfulfilled",
      created_at: "2024-01-19T14:45:00Z",
      line_items: [
        { title: "Stainless Steel Water Bottle", quantity: 1, price: "$34.99" },
      ],
    },
    {
      id: "order-3",
      order_number: 1003,
      email: "customer3@example.com",
      customer_name: "Mike Wilson",
      total_price: "$64.98",
      financial_status: "pending",
      fulfillment_status: "unfulfilled",
      created_at: "2024-01-18T16:20:00Z",
      line_items: [
        { title: "Organic Cotton T-Shirt", quantity: 2, price: "$59.98" },
      ],
    },
  ];

  const mockCustomers: ShopifyCustomer[] = [
    {
      id: "cust-1",
      first_name: "John",
      last_name: "Smith",
      email: "customer1@example.com",
      phone: "+1-555-0101",
      orders_count: 3,
      total_spent: "$450.00",
      created_at: "2024-01-01T10:00:00Z",
      tags: ["repeat-customer", "premium"],
      default_address: {
        address1: "123 Main St",
        city: "New York",
        province: "NY",
        country: "United States",
        zip: "10001",
      },
    },
    {
      id: "cust-2",
      first_name: "Sarah",
      last_name: "Johnson",
      email: "customer2@example.com",
      orders_count: 1,
      total_spent: "$34.99",
      created_at: "2024-01-15T14:30:00Z",
      tags: ["new-customer"],
      default_address: {
        address1: "456 Oak Ave",
        city: "Los Angeles",
        province: "CA",
        country: "United States",
        zip: "90210",
      },
    },
    {
      id: "cust-3",
      first_name: "Mike",
      last_name: "Wilson",
      email: "customer3@example.com",
      phone: "+1-555-0202",
      orders_count: 2,
      total_spent: "$120.00",
      created_at: "2023-12-20T09:15:00Z",
      tags: ["loyal-customer"],
      default_address: {
        address1: "789 Pine St",
        city: "Chicago",
        province: "IL",
        country: "United States",
        zip: "60601",
      },
    },
  ];

  const mockAnalytics: ShopifyAnalytics = {
    total_sales: "$624.95",
    total_orders: 3,
    total_customers: 3,
    average_order_value: "$208.32",
    conversion_rate: 2.8,
    top_selling_products: [
      {
        title: "Premium Wireless Headphones",
        quantity_sold: 1,
        revenue: "$199.99",
      },
      { title: "Organic Cotton T-Shirt", quantity_sold: 3, revenue: "$89.97" },
      {
        title: "Stainless Steel Water Bottle",
        quantity_sold: 1,
        revenue: "$34.99",
      },
    ],
  };

  useEffect(() => {
    if (connectionStatus === "connected") {
      loadInitialData();
    }
  }, [connectionStatus]);

  const loadInitialData = async () => {
    setIsLoading(true);
    try {
      // Simulate API calls
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setProducts(mockProducts);
      setOrders(mockOrders);
      setCustomers(mockCustomers);
      setAnalytics(mockAnalytics);
    } catch (error) {
      console.error("Failed to load Shopify data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    setConnectionStatus("connecting");
    try {
      // Simulate OAuth connection
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setConnectionStatus("connected");
      onConnect?.();
    } catch (error) {
      setConnectionStatus("disconnected");
      console.error("Failed to connect to Shopify:", error);
    }
  };

  const handleDisconnect = async () => {
    try {
      setConnectionStatus("disconnected");
      setProducts([]);
      setOrders([]);
      setCustomers([]);
      setAnalytics(null);
      onDisconnect?.();
    } catch (error) {
      console.error("Failed to disconnect from Shopify:", error);
    }
  };

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      // Simulate search API call
      setIsLoading(true);
      await new Promise((resolve) => setTimeout(resolve, 500));
      const filteredProducts = mockProducts.filter(
        (product) =>
          product.title.toLowerCase().includes(query.toLowerCase()) ||
          product.description?.toLowerCase().includes(query.toLowerCase()) ||
          product.tags.some((tag) =>
            tag.toLowerCase().includes(query.toLowerCase()),
          ),
      );
      setProducts(filteredProducts);
      setIsLoading(false);
    } else {
      setProducts(mockProducts);
    }
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

  const formatCurrency = (amount: string) => {
    return amount;
  };

  if (connectionStatus === "disconnected") {
    return (
      <div className="w-full p-6 border rounded-lg">
        <div className="mb-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
              🛍️
            </div>
            Shopify Integration
          </h2>
          <p className="text-gray-600">
            Connect your Shopify store to manage products, orders, customers,
            and analytics directly from ATOM.
          </p>
        </div>
        <div className="bg-gray-100 p-4 rounded-lg mb-4">
          <h4 className="font-semibold mb-2">Features</h4>
          <ul className="space-y-1 text-sm text-gray-600">
            <li>• Product catalog management</li>
            <li>• Order processing and fulfillment</li>
            <li>• Customer relationship management</li>
            <li>• Sales analytics and reporting</li>
            <li>• Inventory tracking</li>
          </ul>
        </div>
        <button
          onClick={handleConnect}
          className="w-full bg-green-600 hover:bg-green-700 text-white py-3 px-4 rounded-lg font-medium"
        >
          🛍️ Connect Shopify Store
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-6 border rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
              🛍️
            </div>
            <div>
              <h2 className="text-xl font-bold">Shopify Store</h2>
              <p className="text-gray-600">
                E-commerce management and analytics
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                connectionStatus === "connected"
                  ? "bg-green-100 text-green-800"
                  : "bg-yellow-100 text-yellow-800"
              }`}
            >
              {connectionStatus === "connected"
                ? "✅ Connected"
                : "🔄 Connecting..."}
            </span>
            <button
              className="border border-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-50"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="p-6 border rounded-lg">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="Search products, orders, customers..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <button className="border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50">
            🔍 Filter
          </button>
          <button className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700">
            ➕ New Product
          </button>
        </div>
      </div>

      {/* Main Content Tabs */}
      <div className="space-y-4">
        <div className="grid grid-cols-5 gap-2 border-b">
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "dashboard"
                ? "border-green-500 text-green-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📊 Dashboard
          </button>
          <button
            onClick={() => setActiveTab("products")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "products"
                ? "border-green-500 text-green-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📦 Products
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {products.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("orders")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "orders"
                ? "border-green-500 text-green-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📋 Orders
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {orders.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("customers")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "customers"
                ? "border-green-500 text-green-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            👥 Customers
            <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
              {customers.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 ${
              activeTab === "analytics"
                ? "border-green-500 text-green-600"
                : "border-transparent text-gray-600 hover:text-gray-800"
            }`}
          >
            📈 Analytics
          </button>
        </div>

        {/* Dashboard Tab */}
        {activeTab === "dashboard" && (
          <div className="space-y-4">
            {analytics && (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">
                    {analytics.total_sales}
                  </div>
                  <div className="text-sm text-blue-600">Total Sales</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {analytics.total_orders}
                  </div>
                  <div className="text-sm text-green-600">Total Orders</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">
                    {analytics.total_customers}
                  </div>
                  <div className="text-sm text-purple-600">Total Customers</div>
                </div>
                <div className="bg-orange-50 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600">
                    {analytics.average_order_value}
                  </div>
                  <div className="text-sm text-orange-600">
                    Average Order Value
                  </div>
                </div>
              </div>
            )}

            {/* Recent Orders */}
            <div className="p-6 border rounded-lg">
              <h3 className="text-lg font-semibold mb-4">Recent Orders</h3>
              <div className="space-y-3">
                {orders.slice(0, 5).map((order) => (
                  <div
                    key={order.id}
                    className="flex items-center justify-between py-2 border-b"
                  >
                    <div>
                      <div className="font-medium">
                        Order #{order.order_number}
                      </div>
                      <div className="text-sm text-gray-600">
                        {order.customer_name}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">{order.total_price}</div>
                      <div
                        className={`text-xs px-2 py-1 rounded ${
                          order.financial_status === "paid"
                            ? "bg-green-100 text-green-800"
                            : order.financial_status === "pending"
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-red-100 text-red-800"
                        }`}
                      >
                        {order.financial_status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Products */}
            {analytics && (
              <div className="p-6 border rounded-lg">
                <h3 className="text-lg font-semibold mb-4">
                  Top Selling Products
                </h3>
                <div className="space-y-3">
                  {analytics.top_selling_products.map((product, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between py-2 border-b"
                    >
                      <div className="font-medium">{product.title}</div>
                      <div className="text-right">
                        <div className="text-sm">
                          {product.quantity_sold} sold
                        </div>
                        <div className="text-sm text-gray-600">
                          {product.revenue}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Products Tab */}
        {activeTab === "products" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Product Catalog</h3>
                <p className="text-gray-600">
                  Manage your product inventory and listings
                </p>
              </div>
              <div>
                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <span className="animate-spin mr-2">🔄</span>
                    Loading products...
                  </div>
                ) : products.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-4">📦</div>
                    <p>No products found</p>
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {products.map((product) => (
                      <div
                        key={product.id}
                        className="border rounded-lg overflow-hidden"
                      >
                        <div className="aspect-square bg-gray-100 relative">
                          {product.featured_image ? (
                            <img
                              src={product.featured_image}
                              alt={product.title}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <span className="text-2xl">📦</span>
                            </div>
                          )}
                        </div>
                        <div className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <h3 className="font-semibold text-sm line-clamp-2 flex-1">
                              {product.title}
                            </h3>
                            <span
                              className={`text-xs px-2 py-1 rounded ${
                                product.status === "active"
                                  ? "bg-green-100 text-green-800"
                                  : product.status === "draft"
                                    ? "bg-yellow-100 text-yellow-800"
                                    : "bg-gray-100 text-gray-800"
                              }`}
                            >
                              {product.status}
                            </span>
                          </div>
                          {product.description && (
                            <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                              {product.description}
                            </p>
                          )}
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-semibold text-green-600">
                              {product.price}
                            </span>
                            {product.compare_at_price && (
                              <span className="text-xs text-gray-500 line-through">
                                {product.compare_at_price}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>Stock: {product.inventory_quantity}</span>
                            <span>{product.vendor}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Orders Tab */}
        {activeTab === "orders" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Order Management</h3>
                <p className="text-gray-600">View and manage customer orders</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium">Order #</th>
                      <th className="text-left py-2 font-medium">Customer</th>
                      <th className="text-left py-2 font-medium">Amount</th>
                      <th className="text-left py-2 font-medium">Status</th>
                      <th className="text-left py-2 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.id} className="border-b">
                        <td className="py-3 font-medium">
                          #{order.order_number}
                        </td>
                        <td className="py-3">
                          <div>
                            <div className="font-medium">
                              {order.customer_name}
                            </div>
                            <div className="text-sm text-gray-600">
                              {order.email}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 font-medium">
                          {order.total_price}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-col gap-1">
                            <span
                              className={`text-xs px-2 py-1 rounded w-fit ${
                                order.financial_status === "paid"
                                  ? "bg-green-100 text-green-800"
                                  : order.financial_status === "pending"
                                    ? "bg-yellow-100 text-yellow-800"
                                    : "bg-red-100 text-red-800"
                              }`}
                            >
                              {order.financial_status}
                            </span>
                            <span
                              className={`text-xs px-2 py-1 rounded w-fit ${
                                order.fulfillment_status === "fulfilled"
                                  ? "bg-blue-100 text-blue-800"
                                  : order.fulfillment_status === "partial"
                                    ? "bg-yellow-100 text-yellow-800"
                                    : "bg-gray-100 text-gray-800"
                              }`}
                            >
                              {order.fulfillment_status}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 text-sm text-gray-600">
                          {formatDate(order.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Customers Tab */}
        {activeTab === "customers" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Customer Management</h3>
                <p className="text-gray-600">
                  View and manage customer information
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium">Customer</th>
                      <th className="text-left py-2 font-medium">Email</th>
                      <th className="text-left py-2 font-medium">Orders</th>
                      <th className="text-left py-2 font-medium">
                        Total Spent
                      </th>
                      <th className="text-left py-2 font-medium">
                        Member Since
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {customers.map((customer) => (
                      <tr key={customer.id} className="border-b">
                        <td className="py-3">
                          <div className="font-medium">
                            {customer.first_name} {customer.last_name}
                          </div>
                          {customer.phone && (
                            <div className="text-sm text-gray-600">
                              {customer.phone}
                            </div>
                          )}
                        </td>
                        <td className="py-3 text-sm text-gray-600">
                          {customer.email}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <span>📋</span>
                            {customer.orders_count} orders
                          </div>
                        </td>
                        <td className="py-3 font-medium">
                          {customer.total_spent}
                        </td>
                        <td className="py-3 text-sm text-gray-600">
                          {formatDate(customer.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === "analytics" && (
          <div className="space-y-4">
            <div className="p-6 border rounded-lg">
              <div className="mb-4">
                <h3 className="text-lg font-semibold">Sales Analytics</h3>
                <p className="text-gray-600">
                  Detailed analytics and performance metrics
                </p>
              </div>
              {analytics && (
                <div className="space-y-6">
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {analytics.total_sales}
                      </div>
                      <div className="text-sm text-blue-600">Total Sales</div>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {analytics.total_orders}
                      </div>
                      <div className="text-sm text-green-600">Total Orders</div>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {analytics.total_customers}
                      </div>
                      <div className="text-sm text-purple-600">
                        Total Customers
                      </div>
                    </div>
                    <div className="bg-orange-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-orange-600">
                        {analytics.average_order_value}
                      </div>
                      <div className="text-sm text-orange-600">
                        Average Order Value
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-6 md:grid-cols-2">
                    <div className="p-4 border rounded-lg">
                      <h4 className="font-semibold mb-3">Conversion Rate</h4>
                      <div className="text-3xl font-bold text-green-600">
                        {analytics.conversion_rate}%
                      </div>
                      <p className="text-sm text-gray-600 mt-2">
                        Percentage of visitors who make a purchase
                      </p>
                    </div>

                    <div className="p-4 border rounded-lg">
                      <h4 className="font-semibold mb-3">Top Products</h4>
                      <div className="space-y-2">
                        {analytics.top_selling_products.map(
                          (product, index) => (
                            <div
                              key={index}
                              className="flex items-center justify-between"
                            >
                              <span className="text-sm">{product.title}</span>
                              <div className="text-right">
                                <div className="font-medium">
                                  {product.revenue}
                                </div>
                                <div className="text-xs text-gray-600">
                                  {product.quantity_sold} sold
                                </div>
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
