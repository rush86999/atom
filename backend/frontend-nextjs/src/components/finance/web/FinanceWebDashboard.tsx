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
