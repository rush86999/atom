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
