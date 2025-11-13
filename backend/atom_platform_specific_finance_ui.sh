#!/bin/bash
# ATOM Finance Apps - Platform-Specific UI Components for Web and Desktop

echo "💰 ATOM FINANCE APPS - PLATFORM-SPECIFIC UI COMPONENTS"
echo "========================================================"

# Create directory structure for platform-specific components
mkdir -p frontend-nextjs/src/components/finance/desktop
mkdir -p frontend-nextjs/src/components/finance/web
mkdir -p desktop/tauri/src/components/finance
mkdir -p shared/src/services/finance
mkdir -p shared/src/types/finance

# Step 1: Create Web App Finance Components
echo ""
echo "🌐 Step 1: Create Web App Finance Components"
echo "-----------------------------------------------"

cat > frontend-nextjs/src/components/finance/web/FinanceWebDashboard.tsx << 'EOF'
import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Grid,
  Card,
  CardHeader,
  CardContent,
  Typography,
  Chip,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  LinearProgress,
  IconButton,
  Menu,
  Tooltip,
  Avatar,
  useTheme,
  alpha
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AccountBalance,
  Payment,
  Assessment,
  Receipt,
  AttachMoney,
  MoreVert,
  Download,
  Refresh,
  Notifications,
  Search,
  FilterList,
  Settings,
  OpenInNew,
  Schedule,
  Warning,
  CheckCircle
} from '@mui/icons-material';
import { ApexOptions } from 'apexcharts';
import dynamic from 'next/dynamic';
import { FinanceDashboardData } from '@shared/types/finance';
import { FinanceService } from '@shared/services/finance/FinanceService';

// Dynamic imports for performance optimization
const ReactApexChart = dynamic(() => import('react-apexcharts'), { ssr: false });

interface FinanceWebDashboardProps {
  initialData?: FinanceDashboardData;
  className?: string;
}

const FinanceWebDashboard: React.FC<FinanceWebDashboardProps> = ({
  initialData,
  className
}) => {
  const theme = useTheme();
  const [data, setData] = useState<FinanceDashboardData | null>(initialData || null);
  const [loading, setLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState('30d');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTransaction, setSelectedTransaction] = useState<string | null>(null);

  // Responsive breakpoints
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('md', 'lg'));

  // Memoized chart options for web optimization
  const revenueChartOptions = useMemo<ApexOptions>(() => ({
    chart: {
      type: 'area',
      background: 'transparent',
      toolbar: {
        show: true,
        tools: {
          download: true,
          selection: true,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true
        }
      },
      animations: {
        enabled: true,
        easing: 'easeinout',
        speed: 800,
        animateGradually: {
          enabled: true,
          delay: 150
        }
      }
    },
    dataLabels: {
      enabled: false
    },
    stroke: {
      curve: 'smooth',
      width: 3
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.7,
        opacityTo: 0.3,
        stops: [0, 90, 100]
      }
    },
    xaxis: {
      type: 'datetime',
      labels: {
        datetimeUTC: false
      }
    },
    yaxis: {
      labels: {
        formatter: (value: number) => formatCurrency(value)
      }
    },
    tooltip: {
      x: {
        format: 'MMM dd, yyyy HH:mm'
      },
      y: {
        formatter: (value: number) => formatCurrency(value)
      }
    },
    colors: [theme.palette.primary.main],
    theme: {
      mode: theme.palette.mode
    }
  }), [theme]);

  // Load data on component mount and when filters change
  useEffect(() => {
    loadDashboardData();
  }, [selectedPeriod, selectedCategory]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const response = await FinanceService.getDashboardData({
        period: selectedPeriod,
        category: selectedCategory === 'all' ? undefined : selectedCategory
      });
      setData(response.data);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Web-specific keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        loadDashboardData();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
        e.preventDefault();
        exportData();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const handleTransactionClick = (transactionId: string, event: React.MouseEvent<HTMLElement>) => {
    setSelectedTransaction(transactionId);
    setAnchorEl(event.currentTarget);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
    setSelectedTransaction(null);
  };

  const exportData = async () => {
    try {
      const response = await FinanceService.exportData({
        format: 'excel',
        period: selectedPeriod,
        category: selectedCategory === 'all' ? undefined : selectedCategory
      });
      
      // Create download link for web
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `finance_data_${selectedPeriod}.xlsx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Error exporting data:', error);
    }
  };

  // Responsive layout for web
  const getGridColumns = () => {
    if (isMobile) return 12;
    if (isTablet) return 6;
    return 3;
  };

  const MetricCard: React.FC<{
    title: string;
    value: number;
    change: number;
    icon: React.ReactNode;
    color: string;
  }> = ({ title, value, change, icon, color }) => (
    <Card
      sx={{
        height: '100%',
        background: alpha(color, 0.05),
        border: `1px solid ${alpha(color, 0.2)}`,
        transition: 'all 0.3s ease',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: theme.shadows[8]
        }
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Box display="flex" alignItems="center" mb={2}>
          <Avatar
            sx={{
              bgcolor: alpha(color, 0.1),
              color: color,
              mr: 2
            }}
          >
            {icon}
          </Avatar>
          <Box flex={1}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" component="div" fontWeight="bold">
              {formatCurrency(value)}
            </Typography>
          </Box>
        </Box>
        <Box display="flex" alignItems="center">
          {change > 0 ? (
            <TrendingUp sx={{ color: 'success.main', mr: 1 }} />
          ) : (
            <TrendingDown sx={{ color: 'error.main', mr: 1 }} />
          )}
          <Typography
            variant="body2"
            color={change > 0 ? 'success.main' : 'error.main'}
            fontWeight="medium"
          >
            {change > 0 ? '+' : ''}{change}%
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
            vs last period
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );

  if (loading && !data) {
    return (
      <Box sx={{ width: '100%', mt: 4 }}>
        <LinearProgress />
        <Typography variant="h6" sx={{ textAlign: 'center', mt: 2 }}>
          Loading Finance Dashboard...
        </Typography>
      </Box>
    );
  }

  return (
    <Box className={className} sx={{ width: '100%' }}>
      {/* Web Header with Toolbar */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 2
        }}
      >
        <Typography variant="h4" component="h1" fontWeight="bold">
          Finance Intelligence
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Period</InputLabel>
            <Select
              value={selectedPeriod}
              label="Period"
              onChange={(e) => setSelectedPeriod(e.target.value)}
            >
              <MenuItem value="7d">Last 7 Days</MenuItem>
              <MenuItem value="30d">Last 30 Days</MenuItem>
              <MenuItem value="90d">Last Quarter</MenuItem>
              <MenuItem value="365d">Last Year</MenuItem>
            </Select>
          </FormControl>
          
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Category</InputLabel>
            <Select
              value={selectedCategory}
              label="Category"
              onChange={(e) => setSelectedCategory(e.target.value)}
            >
              <MenuItem value="all">All Categories</MenuItem>
              <MenuItem value="revenue">Revenue</MenuItem>
              <MenuItem value="expenses">Expenses</MenuItem>
              <MenuItem value="investments">Investments</MenuItem>
            </Select>
          </FormControl>
          
          <Tooltip title="Refresh (Ctrl+R)">
            <IconButton onClick={loadDashboardData} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Export Data (Ctrl+E)">
            <IconButton onClick={exportData}>
              <Download />
            </IconButton>
          </Tooltip>
          
          <IconButton>
            <Notifications />
          </IconButton>
          
          <IconButton>
            <Settings />
          </IconButton>
        </Box>
      </Box>

      {/* Key Metrics Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Revenue"
            value={data?.totalRevenue || 0}
            change={data?.revenueChange || 0}
            icon={<TrendingUp />}
            color={theme.palette.success.main}
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Expenses"
            value={data?.totalExpenses || 0}
            change={data?.expensesChange || 0}
            icon={<TrendingDown />}
            color={theme.palette.error.main}
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Net Profit"
            value={data?.netProfit || 0}
            change={data?.profitChange || 0}
            icon={<AttachMoney />}
            color={theme.palette.primary.main}
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Cash Flow"
            value={data?.cashFlow || 0}
            change={data?.cashFlowChange || 0}
            icon={<AccountBalance />}
            color={theme.palette.warning.main}
          />
        </Grid>
      </Grid>

      {/* Charts Section - Web Optimized */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Revenue Trend Chart */}
        <Grid item xs={12} md={8}>
          <Card sx={{ height: 400 }}>
            <CardHeader
              title="Revenue Trend"
              subheader="Revenue over time with trend analysis"
              action={
                <Button
                  size="small"
                  startIcon={<OpenInNew />}
                  onClick={() => window.open('/analytics/revenue', '_blank')}
                >
                  View Details
                </Button>
              }
            />
            <CardContent sx={{ height: 300, pt: 0 }}>
              <ReactApexChart
                options={revenueChartOptions}
                series={[
                  {
                    name: 'Revenue',
                    data: data?.revenueTrend || []
                  }
                ]}
                type="area"
                height="100%"
              />
            </CardContent>
          </Card>
        </Grid>
        
        {/* Category Breakdown */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: 400 }}>
            <CardHeader
              title="Category Breakdown"
              subheader="Spending by category"
            />
            <CardContent sx={{ height: 300, pt: 0 }}>
              <ReactApexChart
                options={{
                  chart: {
                    type: 'donut',
                    background: 'transparent'
                  },
                  labels: ['Revenue', 'Expenses', 'Investments', 'Other'],
                  colors: [
                    theme.palette.success.main,
                    theme.palette.error.main,
                    theme.palette.primary.main,
                    theme.palette.warning.main
                  ],
                  legend: {
                    position: 'bottom'
                  },
                  plotOptions: {
                    pie: {
                      donut: {
                        size: '70%'
                      }
                    }
                  }
                }}
                series={[
                  data?.categoryBreakdown?.revenue || 0,
                  data?.categoryBreakdown?.expenses || 0,
                  data?.categoryBreakdown?.investments || 0,
                  data?.categoryBreakdown?.other || 0
                ]}
                type="donut"
                height="100%"
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Transactions Table - Web Optimized */}
      <Card>
        <CardHeader
          title="Recent Transactions"
          subheader="Latest financial transactions"
          action={
            <Button
              variant="outlined"
              startIcon={<OpenInNew />}
              onClick={() => window.open('/finance/transactions', '_blank')}
            >
              View All
            </Button>
          }
        />
        <CardContent sx={{ p: 0 }}>
          <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  <TableCell align="right">Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data?.recentTransactions?.map((transaction) => (
                  <TableRow
                    key={transaction.id}
                    hover
                    sx={{
                      '&:hover': {
                        backgroundColor: alpha(theme.palette.primary.main, 0.04)
                      }
                    }}
                  >
                    <TableCell>
                      {new Date(transaction.date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>{transaction.description}</TableCell>
                    <TableCell>
                      <Chip
                        label={transaction.category}
                        size="small"
                        color={getCategoryColor(transaction.category)}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        fontWeight="medium"
                        color={transaction.amount > 0 ? 'success.main' : 'error.main'}
                      >
                        {formatCurrency(transaction.amount)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Chip
                        label={transaction.status}
                        size="small"
                        color={getStatusColor(transaction.status)}
                        icon={getStatusIcon(transaction.status)}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => handleTransactionClick(transaction.id, e)}
                      >
                        <MoreVert />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Transaction Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
      >
        <MenuItem onClick={handleCloseMenu}>
          <OpenInNew sx={{ mr: 1 }} />
          Open in New Tab
        </MenuItem>
        <MenuItem onClick={handleCloseMenu}>
          <Receipt sx={{ mr: 1 }} />
          View Receipt
        </MenuItem>
        <MenuItem onClick={handleCloseMenu}>
          <Download sx={{ mr: 1 }} />
          Download
        </MenuItem>
      </Menu>
    </Box>
  );
};

// Helper functions
const getCategoryColor = (category: string): 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info' | undefined => {
  const colorMap: Record<string, 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info'> = {
    'revenue': 'success',
    'expenses': 'error',
    'investments': 'primary',
    'salary': 'info',
    'software': 'warning'
  };
  return colorMap[category] || 'default';
};

const getStatusColor = (status: string): 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info' | undefined => {
  const colorMap: Record<string, 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info'> = {
    'completed': 'success',
    'pending': 'warning',
    'failed': 'error',
    'cancelled': 'default'
  };
  return colorMap[status] || 'default';
};

const getStatusIcon = (status: string): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    'completed': <CheckCircle />,
    'pending': <Schedule />,
    'failed': <Warning />,
    'cancelled': <Warning />
  };
  return iconMap[status] || <CheckCircle />;
};

export default FinanceWebDashboard;
EOF

echo "✅ Web Finance Dashboard component created"

# Step 2: Create Desktop App Finance Components
echo ""
echo "🖥️ Step 2: Create Desktop App Finance Components"
echo "---------------------------------------------------"

cat > desktop/tauri/src/components/finance/FinanceDesktopDashboard.tsx << 'EOF'
import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  IconButton,
  Tooltip,
  LinearProgress,
  Menu,
  MenuItem,
  Divider,
  Badge,
  Avatar,
  Fab,
  AppBar,
  Toolbar,
  Button,
  Select,
  MenuItem as MenuItemComponent,
  FormControl,
  InputLabel,
  Chip
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AccountBalance,
  Payment,
  Assessment,
  Receipt,
  AttachMoney,
  MoreVert,
  Download,
  Refresh,
  Notifications,
  Settings,
  OpenInNew,
  Add,
  Save,
  Print,
  FileCopy,
  Sync,
  Warning,
  CheckCircle,
  Schedule,
  Fullscreen,
  FullscreenExit,
  Minimize,
  Close,
  DesktopWindows,
  KeyboardArrowLeft,
  KeyboardArrowRight,
  Home,
  Analytics,
  Payment as PaymentIcon,
  AccountBalanceWallet
} from '@mui/icons-material';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { writeTextFile } from '@tauri-apps/api/fs';
import { open } from '@tauri-apps/api/shell';
import { window as TauriWindow } from '@tauri-apps/api/window';
import { platform } from '@tauri-apps/api/os';
import { FinanceDashboardData } from '@shared/types/finance';
import { DesktopFinanceService } from '../../services/finance/DesktopFinanceService';

interface FinanceDesktopDashboardProps {
  initialData?: FinanceDashboardData;
  className?: string;
}

const FinanceDesktopDashboard: React.FC<FinanceDesktopDashboardProps> = ({
  initialData,
  className
}) => {
  const [data, setData] = useState<FinanceDashboardData | null>(initialData || null);
  const [loading, setLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState('30d');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedTransaction, setSelectedTransaction] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);
  const [syncStatus, setSyncStatus] = useState<'syncing' | 'synced' | 'offline'>('synced');
  const [currentPlatform, setCurrentPlatform] = useState<string>('');
  const [activeSection, setActiveSection] = useState<'dashboard' | 'transactions' | 'analytics' | 'settings'>('dashboard');

  // Initialize desktop-specific features
  useEffect(() => {
    initializeDesktopFeatures();
  }, []);

  const initializeDesktopFeatures = async () => {
    try {
      // Get platform information
      const platformInfo = await platform();
      setCurrentPlatform(platformInfo);

      // Set up Tauri event listeners for real-time updates
      const unlistenFinance = await listen('finance-data-updated', (event) => {
        setData(event.payload as FinanceDashboardData);
      });

      const unlistenNotifications = await listen('new-notification', () => {
        setNotificationCount(prev => prev + 1);
      });

      const unlistenSync = await listen('sync-status-changed', (event) => {
        setSyncStatus(event.payload as 'syncing' | 'synced' | 'offline');
      });

      // Cleanup listeners
      return () => {
        unlistenFinance();
        unlistenNotifications();
        unlistenSync();
      };
    } catch (error) {
      console.error('Error initializing desktop features:', error);
    }
  };

  // Load data on component mount and when filters change
  useEffect(() => {
    loadDashboardData();
  }, [selectedPeriod, selectedCategory]);

  const loadDashboardData = async () => {
    setLoading(true);
    setSyncStatus('syncing');
    
    try {
      // Use Tauri backend for desktop
      const response = await invoke('get_finance_dashboard_data', {
        period: selectedPeriod,
        category: selectedCategory === 'all' ? null : selectedCategory
      });
      
      setData(response as FinanceDashboardData);
      setSyncStatus('synced');
    } catch (error) {
      console.error('Error loading dashboard data:', error);
      setSyncStatus('offline');
    } finally {
      setLoading(false);
    }
  };

  // Desktop-specific file operations
  const saveToLocal = async () => {
    try {
      const fileName = `finance_data_${selectedPeriod}_${Date.now()}.json`;
      await writeTextFile(fileName, JSON.stringify(data, null, 2));
      
      // Show success notification
      await invoke('show_notification', {
        title: 'Data Saved',
        body: `Finance data saved to ${fileName}`,
        icon: 'success'
      });
    } catch (error) {
      console.error('Error saving data:', error);
    }
  };

  const printReport = async () => {
    try {
      await invoke('print_finance_report', {
        data: data,
        period: selectedPeriod,
        category: selectedCategory
      });
    } catch (error) {
      console.error('Error printing report:', error);
    }
  };

  const exportToExcel = async () => {
    try {
      const filePath = await invoke('export_finance_to_excel', {
        data: data,
        period: selectedPeriod,
        category: selectedCategory
      });
      
      // Open file in default application
      await open(filePath);
    } catch (error) {
      console.error('Error exporting to Excel:', error);
    }
  };

  // Desktop window controls
  const toggleFullscreen = async () => {
    try {
      const currentFullscreen = await TauriWindow.isFullscreen();
      await TauriWindow.setFullscreen(!currentFullscreen);
      setIsFullscreen(!currentFullscreen);
    } catch (error) {
      console.error('Error toggling fullscreen:', error);
    }
  };

  const minimizeWindow = async () => {
    try {
      await TauriWindow.minimize();
    } catch (error) {
      console.error('Error minimizing window:', error);
    }
  };

  const closeWindow = async () => {
    try {
      await TauriWindow.close();
    } catch (error) {
      console.error('Error closing window:', error);
    }
  };

  // Desktop keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 's':
            e.preventDefault();
            saveToLocal();
            break;
          case 'p':
            e.preventDefault();
            printReport();
            break;
          case 'e':
            e.preventDefault();
            exportToExcel();
            break;
          case 'f':
            e.preventDefault();
            toggleFullscreen();
            break;
          case 'n':
            e.preventDefault();
            setActiveSection('dashboard');
            break;
        }
      }
      
      // Alt+Tab for desktop sections
      if (e.altKey) {
        switch (e.key) {
          case '1':
            e.preventDefault();
            setActiveSection('dashboard');
            break;
          case '2':
            e.preventDefault();
            setActiveSection('transactions');
            break;
          case '3':
            e.preventDefault();
            setActiveSection('analytics');
            break;
          case '4':
            e.preventDefault();
            setActiveSection('settings');
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const handleTransactionClick = (transactionId: string, event: React.MouseEvent<HTMLElement>) => {
    setSelectedTransaction(transactionId);
    setAnchorEl(event.currentTarget);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
    setSelectedTransaction(null);
  };

  // Desktop-specific Metric Card
  const MetricCard: React.FC<{
    title: string;
    value: number;
    change: number;
    icon: React.ReactNode;
    color: string;
  }> = ({ title, value, change, icon, color }) => (
    <Card
      sx={{
        height: '100%',
        background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)`,
        border: `1px solid ${color}44`,
        position: 'relative',
        overflow: 'hidden',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 6,
          '& .metric-icon': {
            transform: 'scale(1.1)'
          }
        },
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '4px',
          background: color
        }
      }}
    >
      <CardContent sx={{ p: 3, position: 'relative', zIndex: 1 }}>
        <Box display="flex" alignItems="center" mb={2}>
          <Avatar
            className="metric-icon"
            sx={{
              bgcolor: `${color}22`,
              color: color,
              mr: 2,
              transition: 'transform 0.3s ease'
            }}
          >
            {icon}
          </Avatar>
          <Box flex={1}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" component="div" fontWeight="bold">
              {formatCurrency(value)}
            </Typography>
          </Box>
        </Box>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center">
            {change > 0 ? (
              <TrendingUp sx={{ color: 'success.main', mr: 1 }} />
            ) : (
              <TrendingDown sx={{ color: 'error.main', mr: 1 }} />
            )}
            <Typography
              variant="body2"
              color={change > 0 ? 'success.main' : 'error.main'}
              fontWeight="medium"
            >
              {change > 0 ? '+' : ''}{change}%
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            vs last period
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );

  // Desktop Navigation
  const renderNavigation = () => (
    <AppBar position="static" sx={{ background: 'linear-gradient(90deg, #1976d2 0%, #2196f3 100%)' }}>
      <Toolbar>
        <IconButton color="inherit" onClick={() => setActiveSection('dashboard')}>
          <Home />
        </IconButton>
        
        <Divider orientation="vertical" flexItem sx={{ mx: 1, bgcolor: 'white' }} />
        
        <Button
          color={activeSection === 'dashboard' ? 'secondary' : 'inherit'}
          onClick={() => setActiveSection('dashboard')}
          startIcon={<Dashboard />}
        >
          Dashboard
        </Button>
        
        <Button
          color={activeSection === 'transactions' ? 'secondary' : 'inherit'}
          onClick={() => setActiveSection('transactions')}
          startIcon={<Payment />}
        >
          Transactions
        </Button>
        
        <Button
          color={activeSection === 'analytics' ? 'secondary' : 'inherit'}
          onClick={() => setActiveSection('analytics')}
          startIcon={<Analytics />}
        >
          Analytics
        </Button>
        
        <Button
          color={activeSection === 'settings' ? 'secondary' : 'inherit'}
          onClick={() => setActiveSection('settings')}
          startIcon={<Settings />}
        >
          Settings
        </Button>

        <Box sx={{ flexGrow: 1 }} />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton color="inherit" onClick={loadDashboardData} disabled={loading}>
            <Sync />
          </IconButton>
          
          <Badge badgeContent={notificationCount} color="error">
            <IconButton color="inherit">
              <Notifications />
            </IconButton>
          </Badge>
          
          <Tooltip title={`Platform: ${currentPlatform}`}>
            <IconButton color="inherit">
              <DesktopWindows />
            </IconButton>
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );

  // Desktop Window Controls
  const renderWindowControls = () => (
    <Box sx={{ 
      position: 'absolute', 
      top: 0, 
      right: 0, 
      display: 'flex', 
      zIndex: 1000 
    }}>
      <IconButton size="small" onClick={minimizeWindow}>
        <Minimize />
      </IconButton>
      <IconButton size="small" onClick={toggleFullscreen}>
        {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
      </IconButton>
      <IconButton size="small" onClick={closeWindow}>
        <Close />
      </IconButton>
    </Box>
  );

  return (
    <Box className={className} sx={{ width: '100%', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {renderNavigation()}
      {renderWindowControls()}
      
      {/* Desktop Status Bar */}
      <Box sx={{ 
        px: 2, 
        py: 1, 
        background: 'grey.100', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        borderBottom: '1px solid',
        borderColor: 'divider'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="caption">
            Platform: {currentPlatform}
          </Typography>
          <Divider orientation="vertical" flexItem />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {syncStatus === 'syncing' && <LinearProgress size={16} />}
            <Typography variant="caption" color={syncStatus === 'synced' ? 'success.main' : syncStatus === 'syncing' ? 'warning.main' : 'error.main'}>
              {syncStatus.toUpperCase()}
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Tooltip title="Save Data (Ctrl+S)">
            <IconButton size="small" onClick={saveToLocal}>
              <Save />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Print Report (Ctrl+P)">
            <IconButton size="small" onClick={printReport}>
              <Print />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Export to Excel (Ctrl+E)">
            <IconButton size="small" onClick={exportToExcel}>
              <Download />
            </IconButton>
          </Tooltip>
          
          <Divider orientation="vertical" flexItem />
          
          <FormControl size="small" variant="standard">
            <Select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              sx={{ minWidth: 100 }}
            >
              <MenuItemComponent value="7d">7 Days</MenuItemComponent>
              <MenuItemComponent value="30d">30 Days</MenuItemComponent>
              <MenuItemComponent value="90d">Quarter</MenuItemComponent>
              <MenuItemComponent value="365d">Year</MenuItemComponent>
            </Select>
          </FormControl>
        </Box>
      </Box>

      {/* Main Content Area */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto' }}>
        {loading && !data && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '50%' }}>
            <LinearProgress sx={{ width: 300, mb: 2 }} />
            <Typography variant="h6">
              Loading Finance Dashboard...
            </Typography>
          </Box>
        )}

        {data && (
          <>
            {/* Desktop-optimized Key Metrics Grid */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
              <Grid item xs={12} sm={6} md={3}>
                <MetricCard
                  title="Total Revenue"
                  value={data.totalRevenue || 0}
                  change={data.revenueChange || 0}
                  icon={<TrendingUp />}
                  color="#4caf50"
                />
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <MetricCard
                  title="Total Expenses"
                  value={data.totalExpenses || 0}
                  change={data.expensesChange || 0}
                  icon={<TrendingDown />}
                  color="#f44336"
                />
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <MetricCard
                  title="Net Profit"
                  value={data.netProfit || 0}
                  change={data.profitChange || 0}
                  icon={<AccountBalanceWallet />}
                  color="#2196f3"
                />
              </Grid>
              
              <Grid item xs={12} sm={6} md={3}>
                <MetricCard
                  title="Cash Flow"
                  value={data.cashFlow || 0}
                  change={data.cashFlowChange || 0}
                  icon={<AccountBalance />}
                  color="#ff9800"
                />
              </Grid>
            </Grid>

            {/* Desktop-specific quick actions */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Quick Actions
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      <Button variant="contained" startIcon={<Add />} onClick={() => setActiveSection('transactions')}>
                        Add Transaction
                      </Button>
                      <Button variant="outlined" startIcon={<Receipt />} onClick={printReport}>
                        Generate Report
                      </Button>
                      <Button variant="outlined" startIcon={<Sync />} onClick={loadDashboardData}>
                        Sync Data
                      </Button>
                      <Button variant="outlined" startIcon={<Download />} onClick={exportToExcel}>
                        Export Data
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </>
        )}
      </Box>

      {/* Desktop Floating Action Button */}
      <Fab
        color="primary"
        sx={{
          position: 'absolute',
          bottom: 24,
          right: 24,
        }}
        onClick={() => setActiveSection('transactions')}
      >
        <Add />
      </Fab>

      {/* Transaction Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
        PaperProps={{
          sx: {
            boxShadow: 6,
            minWidth: 200
          }
        }}
      >
        <MenuItem onClick={handleCloseMenu}>
          <OpenInNew sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem onClick={handleCloseMenu}>
          <Receipt sx={{ mr: 1 }} />
          View Receipt
        </MenuItem>
        <MenuItem onClick={handleCloseMenu}>
          <FileCopy sx={{ mr: 1 }} />
          Copy Transaction ID
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleCloseMenu}>
          <Download sx={{ mr: 1 }} />
          Download
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default FinanceDesktopDashboard;
EOF

echo "✅ Desktop Finance Dashboard component created"

# Step 3: Create Shared Finance Service Types
echo ""
echo "📝 Step 3: Create Shared Finance Service Types"
echo "------------------------------------------------"

cat > shared/src/types/finance/index.ts << 'EOF'
export interface FinanceTransaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: string;
  status: 'completed' | 'pending' | 'failed' | 'cancelled';
  account: string;
  metadata?: Record<string, any>;
  receipt?: string;
  vendor?: string;
  tags?: string[];
  notes?: string;
  attachments?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface FinanceInvoice {
  id: string;
  number: string;
  customer: {
    id: string;
    name: string;
    email: string;
    phone?: string;
    address?: string;
  };
  items: InvoiceItem[];
  subtotal: number;
  tax: number;
  total: number;
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
  dueDate: string;
  sentDate?: string;
  paidDate?: string;
  notes?: string;
  attachments?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface InvoiceItem {
  id: string;
  description: string;
  quantity: number;
  unitPrice: number;
  total: number;
  tax?: number;
  category?: string;
}

export interface FinanceExpense {
  id: string;
  date: string;
  description: string;
  amount: number;
  category: string;
  vendor: {
    id: string;
    name: string;
    email?: string;
    phone?: string;
  };
  status: 'draft' | 'submitted' | 'approved' | 'rejected' | 'reimbursed';
  receipt?: string;
  tags?: string[];
  notes?: string;
  attachments?: string[];
  submittedBy?: string;
  approvedBy?: string;
  approvedAt?: string;
  reimbursedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceAccount {
  id: string;
  name: string;
  type: 'checking' | 'savings' | 'credit_card' | 'investment' | 'loan';
  balance: number;
  currency: string;
  bankName?: string;
  accountNumber?: string;
  routingNumber?: string;
  status: 'active' | 'inactive' | 'closed';
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceBudget {
  id: string;
  name: string;
  category: string;
  budgeted: number;
  spent: number;
  remaining: number;
  percentage: number;
  period: string;
  startDate: string;
  endDate: string;
  status: 'active' | 'completed' | 'cancelled';
  alertThreshold?: number;
  alertsEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceReport {
  id: string;
  title: string;
  type: 'profit_loss' | 'cash_flow' | 'balance_sheet' | 'expenses' | 'revenue' | 'budget';
  period: string;
  startDate: string;
  endDate: string;
  data: Record<string, any>;
  format: 'pdf' | 'excel' | 'csv';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  generatedAt?: string;
  downloadUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceDashboardData {
  totalRevenue: number;
  totalExpenses: number;
  netProfit: number;
  cashFlow: number;
  revenueChange: number;
  expensesChange: number;
  profitChange: number;
  cashFlowChange: number;
  revenueTrend: Array<{ x: number; y: number }>;
  categoryBreakdown: {
    revenue: number;
    expenses: number;
    investments: number;
    other: number;
  };
  recentTransactions: FinanceTransaction[];
  alerts: FinanceAlert[];
  summary: {
    period: string;
    startDate: string;
    endDate: string;
    generatedAt: string;
  };
}

export interface FinanceAlert {
  id: string;
  type: 'info' | 'warning' | 'error' | 'success';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  category?: string;
  transactionId?: string;
  read: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FinanceAnalytics {
  revenueAnalytics: {
    current: number;
    previous: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
    forecast: Array<{ period: string; value: number }>;
  };
  expenseAnalytics: {
    current: number;
    previous: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
    byCategory: Record<string, number>;
  };
  profitabilityAnalytics: {
    grossMargin: number;
    netMargin: number;
    operatingMargin: number;
    trend: 'up' | 'down' | 'stable';
  };
  cashFlowAnalytics: {
    operatingCashFlow: number;
    investingCashFlow: number;
    financingCashFlow: number;
    netCashFlow: number;
    trend: 'up' | 'down' | 'stable';
  };
  budgetAnalytics: {
    totalBudgeted: number;
    totalSpent: number;
    variance: number;
    byCategory: Array<{
      category: string;
      budgeted: number;
      spent: number;
      variance: number;
    }>;
  };
  riskAnalytics: {
    overallRisk: 'low' | 'medium' | 'high';
    riskFactors: Array<{
      type: string;
      level: 'low' | 'medium' | 'high';
      description: string;
    }>;
    recommendations: string[];
  };
}

export interface FinanceApp {
  id: string;
  name: string;
  category: FinanceAppCategory;
  description: string;
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: string;
  features: string[];
  supportedEntities: string[];
  config: FinanceAppConfig;
  createdAt: string;
  updatedAt: string;
}

export type FinanceAppCategory = 
  | 'accounting'
  | 'payment_processing'
  | 'expense_management'
  | 'banking_integration'
  | 'payroll_hrm'
  | 'procurement_sourcing'
  | 'investments'
  | 'tax_management'
  | 'reporting';

export interface FinanceAppConfig {
  apiVersion: string;
  realTimeSync: boolean;
  webhooks: boolean;
  batchSize: number;
  dataRetentionDays: number;
  enhancementLevel: 'standard' | 'advanced' | 'premium';
  complianceStandards: string[];
  features: string[];
  supportedEntities: string[];
}

export interface FinanceSearchFilters {
  period?: string;
  category?: string;
  account?: string;
  status?: string;
  dateRange?: {
    start: string;
    end: string;
  };
  amountRange?: {
    min: number;
    max: number;
  };
  search?: string;
  tags?: string[];
}

export interface FinanceApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface FinanceSyncResult {
  syncId: string;
  status: 'started' | 'in_progress' | 'completed' | 'failed';
  startedAt: string;
  completedAt?: string;
  recordsProcessed: number;
  recordsTotal: number;
  errors?: string[];
  estimatedCompletion?: string;
}

// Web-specific types
export interface WebFinanceChartOptions {
  responsive: boolean;
  animations: boolean;
  tooltip: boolean;
  legend: boolean;
  theme: 'light' | 'dark' | 'auto';
}

export interface WebFinanceTableState {
  pagination: {
    page: number;
    rowsPerPage: number;
    total: number;
  };
  sorting: {
    field: string;
    direction: 'asc' | 'desc';
  };
  filters: FinanceSearchFilters;
  selectedRows: string[];
}

// Desktop-specific types
export interface DesktopFinanceWindowConfig {
  width: number;
  height: number;
  x: number;
  y: number;
  fullscreen: boolean;
  alwaysOnTop: boolean;
  decorations: boolean;
}

export interface DesktopFinanceEvent {
  type: string;
  payload: any;
  timestamp: string;
}

export interface DesktopFinanceNotification {
  title: string;
  body: string;
  icon?: string;
  badge?: number;
  sound?: string;
  actions?: Array<{
    id: string;
    title: string;
    icon?: string;
  }>;
}

export interface DesktopFinanceShortcut {
  key: string;
  modifiers: Array<'ctrl' | 'alt' | 'shift' | 'meta'>;
  action: string;
  description: string;
}
EOF

echo "✅ Shared finance types created"

# Step 4: Create Shared Finance Services
echo ""
echo "🔧 Step 4: Create Shared Finance Services"
echo "-----------------------------------------"

cat > shared/src/services/finance/FinanceService.ts << 'EOF'
import { 
  FinanceDashboardData, 
  FinanceTransaction, 
  FinanceApiResponse,
  FinanceSearchFilters,
  FinanceSyncResult,
  FinanceAnalytics,
  FinanceReport
} from '@shared/types/finance';

export class FinanceService {
  private static instance: FinanceService;
  private baseUrl: string;
  private apiKey: string;

  private constructor() {
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY || '';
  }

  public static getInstance(): FinanceService {
    if (!FinanceService.instance) {
      FinanceService.instance = new FinanceService();
    }
    return FinanceService.instance;
  }

  // Dashboard Methods
  public async getDashboardData(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceDashboardData>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/dashboard?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Transaction Methods
  public async getTransactions(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceTransaction[]>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);
    if (filters.status) params.append('status', filters.status);
    if (filters.search) params.append('search', filters.search);
    if (filters.dateRange) {
      params.append('start_date', filters.dateRange.start);
      params.append('end_date', filters.dateRange.end);
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data: data.transactions,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async createTransaction(transaction: Partial<FinanceTransaction>): Promise<FinanceApiResponse<FinanceTransaction>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(transaction)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async updateTransaction(id: string, transaction: Partial<FinanceTransaction>): Promise<FinanceApiResponse<FinanceTransaction>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(transaction)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async deleteTransaction(id: string): Promise<FinanceApiResponse<void>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/transactions/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return {
        success: true,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Analytics Methods
  public async getAnalytics(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceAnalytics>> {
    const params = new URLSearchParams();
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/analytics?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Report Methods
  public async generateReport(type: string, filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceReport>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/reports`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          type,
          ...filters
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Export Methods
  public async exportData(format: 'excel' | 'csv' | 'pdf' = 'excel', filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<Blob>> {
    const params = new URLSearchParams();
    params.append('format', format);
    if (filters.period) params.append('period', filters.period);
    if (filters.category) params.append('category', filters.category);

    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/export?${params}`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const blob = await response.blob();
      return {
        success: true,
        data: blob,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Sync Methods
  public async syncFinanceApp(appId: string, syncConfig: any = {}): Promise<FinanceApiResponse<FinanceSyncResult>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/apps/${appId}/sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(syncConfig)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Health Check
  public async healthCheck(): Promise<FinanceApiResponse<{ status: string; timestamp: string }>> {
    try {
      const response = await fetch(`${this.baseUrl}/api/atom/finance/health`, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }
}
EOF

echo "✅ Shared finance service created"

# Step 5: Create Desktop-specific Finance Service
echo ""
echo "🖥️ Step 5: Create Desktop-specific Finance Service"
echo "----------------------------------------------------"

cat > desktop/tauri/src/services/finance/DesktopFinanceService.ts << 'EOF'
import { 
  FinanceDashboardData, 
  FinanceTransaction, 
  FinanceApiResponse,
  FinanceSearchFilters,
  FinanceSyncResult,
  DesktopFinanceNotification,
  DesktopFinanceShortcut
} from '@shared/types/finance';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { writeTextFile, exists, readTextFile } from '@tauri-apps/api/fs';
import { open } from '@tauri-apps/api/shell';
import { platform } from '@tauri-apps/api/os';
import { window as TauriWindow } from '@tauri-apps/api/window';

export class DesktopFinanceService {
  private static instance: DesktopFinanceService;
  private eventListeners: Map<string, () => void> = new Map();
  private shortcuts: Map<string, DesktopFinanceShortcut> = new Map();
  private platform: string = '';

  private constructor() {
    this.initializeDesktopFeatures();
  }

  public static getInstance(): DesktopFinanceService {
    if (!DesktopFinanceService.instance) {
      DesktopFinanceService.instance = new DesktopFinanceService();
    }
    return DesktopFinanceService.instance;
  }

  private async initializeDesktopFeatures() {
    try {
      // Get platform information
      this.platform = await platform();
      
      // Set up event listeners
      await this.setupEventListeners();
      
      // Set up keyboard shortcuts
      await this.setupKeyboardShortcuts();
      
      // Initialize local data cache
      await this.initializeLocalCache();
      
      console.log(`Desktop Finance Service initialized for ${this.platform}`);
    } catch (error) {
      console.error('Error initializing desktop features:', error);
    }
  }

  private async setupEventListeners() {
    // Listen for finance data updates from backend
    const unlistenFinance = await listen('finance-data-updated', (event) => {
      console.log('Finance data updated:', event.payload);
      this.handleDataUpdate(event.payload);
    });

    // Listen for sync status updates
    const unlistenSync = await listen('sync-status-changed', (event) => {
      console.log('Sync status changed:', event.payload);
      this.handleSyncStatusChange(event.payload);
    });

    // Listen for notifications
    const unlistenNotifications = await listen('desktop-notification', async (event) => {
      const notification = event.payload as DesktopFinanceNotification;
      await this.showDesktopNotification(notification);
    });

    this.eventListeners.set('finance-data-updated', unlistenFinance);
    this.eventListeners.set('sync-status-changed', unlistenSync);
    this.eventListeners.set('desktop-notification', unlistenNotifications);
  }

  private async setupKeyboardShortcuts() {
    // Define desktop-specific keyboard shortcuts
    const shortcuts: DesktopFinanceShortcut[] = [
      {
        key: 's',
        modifiers: ['ctrl'],
        action: 'save_data',
        description: 'Save finance data locally'
      },
      {
        key: 'r',
        modifiers: ['ctrl'],
        action: 'refresh_data',
        description: 'Refresh finance data'
      },
      {
        key: 'e',
        modifiers: ['ctrl'],
        action: 'export_excel',
        description: 'Export to Excel'
      },
      {
        key: 'p',
        modifiers: ['ctrl'],
        action: 'print_report',
        description: 'Print finance report'
      },
      {
        key: 'f',
        modifiers: ['ctrl'],
        action: 'search_transactions',
        description: 'Search transactions'
      },
      {
        key: 'n',
        modifiers: ['ctrl'],
        action: 'new_transaction',
        description: 'Create new transaction'
      },
      {
        key: '1',
        modifiers: ['alt'],
        action: 'show_dashboard',
        description: 'Show dashboard'
      },
      {
        key: '2',
        modifiers: ['alt'],
        action: 'show_transactions',
        description: 'Show transactions'
      },
      {
        key: '3',
        modifiers: ['alt'],
        action: 'show_analytics',
        description: 'Show analytics'
      }
    ];

    for (const shortcut of shortcuts) {
      this.shortcuts.set(shortcut.action, shortcut);
    }

    // Set up keyboard event listener
    const handleKeyPress = (e: KeyboardEvent) => {
      const modifiers: string[] = [];
      if (e.ctrlKey) modifiers.push('ctrl');
      if (e.altKey) modifiers.push('alt');
      if (e.shiftKey) modifiers.push('shift');
      if (e.metaKey) modifiers.push('meta');

      for (const [action, shortcut] of this.shortcuts) {
        if (
          e.key.toLowerCase() === shortcut.key.toLowerCase() &&
          this.arraysEqual(modifiers.sort(), shortcut.modifiers.sort())
        ) {
          this.handleShortcut(action);
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
  }

  private async initializeLocalCache() {
    try {
      const cachePath = 'finance_cache.json';
      const cacheExists = await exists(cachePath);
      
      if (cacheExists) {
        const cacheContent = await readTextFile(cachePath);
        console.log('Finance cache loaded from local file');
      }
    } catch (error) {
      console.error('Error initializing local cache:', error);
    }
  }

  // Dashboard Methods - Desktop-specific with Tauri backend
  public async getDashboardData(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceDashboardData>> {
    try {
      const data = await invoke('get_finance_dashboard_data', {
        period: filters.period || '30d',
        category: filters.category,
        startDate: filters.dateRange?.start,
        endDate: filters.dateRange?.end
      }) as FinanceDashboardData;

      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Transaction Methods - Desktop-specific
  public async getTransactions(filters: FinanceSearchFilters = {}): Promise<FinanceApiResponse<FinanceTransaction[]>> {
    try {
      const data = await invoke('get_finance_transactions', {
        period: filters.period,
        category: filters.category,
        status: filters.status,
        search: filters.search,
        startDate: filters.dateRange?.start,
        endDate: filters.dateRange?.end
      }) as FinanceTransaction[];

      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  public async createTransaction(transaction: Partial<FinanceTransaction>): Promise<FinanceApiResponse<FinanceTransaction>> {
    try {
      const data = await invoke('create_finance_transaction', {
        transaction
      }) as FinanceTransaction;

      // Show success notification
      await this.showDesktopNotification({
        title: 'Transaction Created',
        body: `Transaction of ${transaction.amount} created successfully`,
        icon: 'success'
      });

      return {
        success: true,
        data,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      // Show error notification
      await this.showDesktopNotification({
        title: 'Error',
        body: `Failed to create transaction: ${error instanceof Error ? error.message : 'Unknown error'}`,
        icon: 'error'
      });

      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // Desktop-specific file operations
  public async saveDataLocally(data: any): Promise<boolean> {
    try {
      const fileName = `finance_backup_${new Date().toISOString().split('T')[0]}.json`;
      await writeTextFile(fileName, JSON.stringify(data, null, 2));
      
      await this.showDesktopNotification({
        title: 'Data Saved',
        body: `Finance data saved to ${fileName}`,
        icon: 'success'
      });

      return true;
    } catch (error) {
      console.error('Error saving data locally:', error);
      return false;
    }
  }

  public async exportToExcel(filters: FinanceSearchFilters = {}): Promise<boolean> {
    try {
      const filePath = await invoke('export_finance_to_excel', {
        period: filters.period || '30d',
        category: filters.category,
        startDate: filters.dateRange?.start,
        endDate: filters.dateRange?.end
      }) as string;

      // Open file in default application
      await open(filePath);

      await this.showDesktopNotification({
        title: 'Export Complete',
        body: 'Finance data exported to Excel successfully',
        icon: 'success'
      });

      return true;
    } catch (error) {
      console.error('Error exporting to Excel:', error);
      return false;
    }
  }

  public async printReport(filters: FinanceSearchFilters = {}): Promise<boolean> {
    try {
      await invoke('print_finance_report', {
        period: filters.period || '30d',
        category: filters.category,
        startDate: filters.dateRange?.start,
        endDate: filters.dateRange?.end
      });

      await this.showDesktopNotification({
        title: 'Print Started',
        body: 'Finance report is being printed',
        icon: 'info'
      });

      return true;
    } catch (error) {
      console.error('Error printing report:', error);
      return false;
    }
  }

  // Desktop window management
  public async toggleFullscreen(): Promise<void> {
    try {
      const currentFullscreen = await TauriWindow.isFullscreen();
      await TauriWindow.setFullscreen(!currentFullscreen);
    } catch (error) {
      console.error('Error toggling fullscreen:', error);
    }
  }

  public async minimizeWindow(): Promise<void> {
    try {
      await TauriWindow.minimize();
    } catch (error) {
      console.error('Error minimizing window:', error);
    }
  }

  public async maximizeWindow(): Promise<void> {
    try {
      const currentMaximized = await TauriWindow.isMaximized();
      if (currentMaximized) {
        await TauriWindow.unmaximize();
      } else {
        await TauriWindow.maximize();
      }
    } catch (error) {
      console.error('Error maximizing window:', error);
    }
  }

  public async closeWindow(): Promise<void> {
    try {
      await TauriWindow.close();
    } catch (error) {
      console.error('Error closing window:', error);
    }
  }

  // Desktop notifications
  private async showDesktopNotification(notification: DesktopFinanceNotification): Promise<void> {
    try {
      await invoke('show_desktop_notification', {
        title: notification.title,
        body: notification.body,
        icon: notification.icon || 'info',
        badge: notification.badge,
        sound: notification.sound || 'default'
      });
    } catch (error) {
      console.error('Error showing desktop notification:', error);
    }
  }

  // Event handlers
  private handleDataUpdate(data: any): void {
    // Emit custom event for React components
    window.dispatchEvent(new CustomEvent('finance-data-updated', { detail: data }));
  }

  private handleSyncStatusChange(status: string): void {
    // Emit custom event for React components
    window.dispatchEvent(new CustomEvent('sync-status-changed', { detail: status }));
  }

  private handleShortcut(action: string): void {
    switch (action) {
      case 'save_data':
        this.saveDataLocally({});
        break;
      case 'refresh_data':
        this.getDashboardData({});
        break;
      case 'export_excel':
        this.exportToExcel({});
        break;
      case 'print_report':
        this.printReport({});
        break;
      case 'toggle_fullscreen':
        this.toggleFullscreen();
        break;
      default:
        // Emit custom shortcut event for React components
        window.dispatchEvent(new CustomEvent('finance-shortcut', { detail: action }));
        break;
    }
  }

  // Utility methods
  private arraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  // Platform-specific methods
  public getPlatform(): string {
    return this.platform;
  }

  public isWindows(): boolean {
    return this.platform === 'windows';
  }

  public isMac(): boolean {
    return this.platform === 'darwin';
  }

  public isLinux(): boolean {
    return this.platform === 'linux';
  }

  public getPlatformShortcuts(): Map<string, DesktopFinanceShortcut> {
    const platformShortcuts = new Map(this.shortcuts);
    
    // Add platform-specific shortcuts
    if (this.isMac()) {
      platformShortcuts.set('new_transaction', {
        key: 'n',
        modifiers: ['meta'],
        action: 'new_transaction',
        description: 'Create new transaction (Mac)'
      });
    }

    return platformShortcuts;
  }

  // Cleanup
  public cleanup(): void {
    // Remove event listeners
    for (const [event, unlisten] of this.eventListeners) {
      unlisten();
    }
    this.eventListeners.clear();
    this.shortcuts.clear();
  }
}
EOF

echo "✅ Desktop-specific finance service created"

echo ""
echo "✅ Platform-specific UI components created"
"