import React, { useState, useEffect } from 'react';
import {
  RefreshCw,
  ExternalLink,
  FileText,
  Users,
  Landmark,
  PieChart
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { xeroSkills } from './skills/xeroSkills';
import { XeroConfig, XeroInvoice, XeroContact, XeroTransaction, XeroBankAccount, XeroFinancialReport } from './types';
import { XeroDashboard } from './components/XeroDashboard';
import { XeroInvoices } from './components/XeroInvoices';
import { XeroContacts } from './components/XeroContacts';
import { XeroBanking } from './components/XeroBanking';
import { XeroReports } from './components/XeroReports';

const XeroIntegration: React.FC = () => {
  const [config, setConfig] = useState<XeroConfig>({ environment: 'production' });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const { toast } = useToast();

  // Data states
  const [invoices, setInvoices] = useState<XeroInvoice[]>([]);
  const [contacts, setContacts] = useState<XeroContact[]>([]);
  const [bankAccounts, setBankAccounts] = useState<XeroBankAccount[]>([]);
  const [transactions, setTransactions] = useState<XeroTransaction[]>([]);
  const [financialReports, setFinancialReports] = useState<XeroFinancialReport[]>([]);

  useEffect(() => {
    checkAuthentication();
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const checkAuthentication = async () => {
    try {
      const tokens = await xeroSkills.getStoredTokens();
      if (tokens && tokens.accessToken) {
        setIsAuthenticated(true);
        setConfig({
          accessToken: tokens.accessToken,
          tenantId: tokens.tenantId,
          environment: tokens.environment || 'production'
        });
      }
    } catch (error) {
      console.error('Authentication check failed:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [invoicesData, contactsData, bankAccountsData, transactionsData] = await Promise.all([
        xeroSkills.getInvoices({ page: 1, per_page: 100 }),
        xeroSkills.getContacts({ page: 1, per_page: 100 }),
        xeroSkills.getBankAccounts(),
        xeroSkills.getBankTransactions({ page: 1, per_page: 100 })
      ]);

      setInvoices(invoicesData.invoices || []);
      setContacts(contactsData.contacts || []);
      setBankAccounts(bankAccountsData.bankAccounts || []);
      setTransactions(transactionsData.transactions || []);
    } catch (error: any) {
      toast({
        title: 'Error loading data',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAuthentication = () => {
    window.location.href = '/api/integrations/xero/auth/start';
  };

  const handleCreateInvoice = async (invoiceData: any) => {
    try {
      setLoading(true);
      const newInvoice = await xeroSkills.createInvoice(invoiceData);
      setInvoices([newInvoice, ...invoices]);
      toast({
        title: 'Invoice created',
        description: 'Invoice has been created successfully',
      });
    } catch (error: any) {
      toast({
        title: 'Error creating invoice',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContact = async (contactData: any) => {
    try {
      setLoading(true);
      const newContact = await xeroSkills.createContact(contactData);
      setContacts([newContact, ...contacts]);
      toast({
        title: 'Contact created',
        description: 'Contact has been created successfully',
      });
    } catch (error: any) {
      toast({
        title: 'Error creating contact',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTransaction = async (transactionData: any) => {
    try {
      setLoading(true);
      const newTransaction = await xeroSkills.createBankTransaction(transactionData);
      setTransactions([newTransaction, ...transactions]);
      toast({
        title: 'Transaction created',
        description: 'Transaction has been created successfully',
      });
    } catch (error: any) {
      toast({
        title: 'Error creating transaction',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="mx-auto max-w-3xl space-y-8">
          <div className="text-center space-y-4">
            <h1 className="text-4xl font-bold text-blue-500">Xero Integration</h1>
            <p className="text-xl text-muted-foreground">
              Complete small business accounting and financial management
            </p>
            <p className="text-muted-foreground">
              Manage invoices, contacts, bank transactions, and financial reporting
            </p>
          </div>

          <Card className="border-blue-500 border-2 bg-blue-50/50 dark:bg-blue-950/20">
            <CardContent className="pt-6 text-center space-y-6">
              <div className="space-y-2">
                <h2 className="text-2xl font-semibold text-blue-600 dark:text-blue-400">Connect to Xero</h2>
                <p className="text-muted-foreground">
                  Authenticate with Xero to access your accounting data
                </p>
              </div>
              <Button
                size="lg"
                className="bg-blue-500 hover:bg-blue-600 text-white"
                onClick={handleAuthentication}
                disabled={loading}
              >
                {loading ? 'Connecting...' : 'Connect Xero Account'}
                <ExternalLink className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Invoice Management</CardTitle>
                <CardDescription>Create, send, and track invoices</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Contact Management</CardTitle>
                <CardDescription>Manage customers and suppliers</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Bank Reconciliation</CardTitle>
                <CardDescription>Automatic bank feed and reconciliation</CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-[1400px] space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card p-6 rounded-lg border shadow-sm">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold text-blue-500">Xero Integration</h1>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Badge variant="outline">
                {config.environment === 'sandbox' ? 'Sandbox' : 'Production'}
              </Badge>
              <span>•</span>
              <span className="text-sm">Tenant: {config.tenantId}</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={loadData}
              disabled={loading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh Data
            </Button>
            <Button
              className="bg-blue-500 hover:bg-blue-600 text-white"
              onClick={() => window.open('https://go.xero.com/', '_blank')}
            >
              Open Xero
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 lg:w-[600px] lg:grid-cols-5">
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="invoices">
              <FileText className="mr-2 h-4 w-4" />
              Invoices
            </TabsTrigger>
            <TabsTrigger value="contacts">
              <Users className="mr-2 h-4 w-4" />
              Contacts
            </TabsTrigger>
            <TabsTrigger value="banking">
              <Landmark className="mr-2 h-4 w-4" />
              Banking
            </TabsTrigger>
            <TabsTrigger value="reports">
              <PieChart className="mr-2 h-4 w-4" />
              Reports
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-6">
            <XeroDashboard
              invoices={invoices}
              contacts={contacts}
              transactions={transactions}
              bankAccounts={bankAccounts}
            />
          </TabsContent>

          <TabsContent value="invoices">
            <Card>
              <CardContent className="p-6">
                <XeroInvoices
                  invoices={invoices}
                  contacts={contacts}
                  onCreateInvoice={handleCreateInvoice}
                  loading={loading}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="contacts">
            <Card>
              <CardContent className="p-6">
                <XeroContacts
                  contacts={contacts}
                  onCreateContact={handleCreateContact}
                  loading={loading}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="banking">
            <Card>
              <CardContent className="p-6">
                <XeroBanking
                  bankAccounts={bankAccounts}
                  transactions={transactions}
                  contacts={contacts}
                  onCreateTransaction={handleCreateTransaction}
                  loading={loading}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="reports">
            <Card>
              <CardContent className="p-6">
                <XeroReports />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default XeroIntegration;