/**
 * Azure Integration Component
 * Complete Microsoft Azure cloud platform integration
 */

import React, { useState, useEffect } from "react";
import {
    Sun,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    RefreshCw,
    Server,
    Database,
    Settings,
    Eye,
    ExternalLink,
    Loader2,
    Cpu,
    Globe,
    HardDrive,
    Layers,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

interface AzureResourceGroup {
    id: string;
    name: string;
    location: string;
    tags: Record<string, string>;
    created_at: string;
}

interface AzureVirtualMachine {
    id: string;
    name: string;
    location: string;
    size: string;
    status: string;
    os_type: string;
    admin_username: string;
    public_ip: string;
    created_at: string;
    resource_group: string;
}

interface AzureStorageAccount {
    id: string;
    name: string;
    location: string;
    type: string;
    tier: string;
    replication: string;
    access_tier: string;
    blob_endpoint: string;
    file_endpoint: string;
    created_at: string;
    resource_group: string;
}

interface AzureAppService {
    id: string;
    name: string;
    location: string;
    state: string;
    host_names: string[];
    app_service_plan: string;
    runtime: string;
    https_only: boolean;
    created_at: string;
    resource_group: string;
}

interface AzureSubscription {
    id: string;
    subscriptionId: string;
    displayName: string;
    state: string;
    tenantId: string;
    policies?: any[];
}

const AzureIntegration: React.FC = () => {
    const [resourceGroups, setResourceGroups] = useState<AzureResourceGroup[]>(
        [],
    );
    const [virtualMachines, setVirtualMachines] = useState<AzureVirtualMachine[]>(
        [],
    );
    const [storageAccounts, setStorageAccounts] = useState<AzureStorageAccount[]>(
        [],
    );
    const [appServices, setAppServices] = useState<AzureAppService[]>([]);
    const [subscriptions, setSubscriptions] = useState<AzureSubscription[]>([]);
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedResourceGroup, setSelectedResourceGroup] = useState("");
    const [selectedSubscription, setSelectedSubscription] = useState("");

    // Form states
    const [vmForm, setVmForm] = useState({
        resource_group: "",
        vm_name: "",
        location: "East US",
        size: "Standard_B2s",
        image_publisher: "MicrosoftWindowsServer",
        image_offer: "WindowsServer",
        image_sku: "2019-Datacenter",
        admin_username: "",
        admin_password: "",
        network_interface_id: "",
    });

    const [appForm, setAppForm] = useState({
        resource_group: "",
        app_name: "",
        location: "East US",
        plan_tier: "Basic",
        plan_size: "B1",
        runtime: "NODE",
        https_only: true,
    });

    const [storageForm, setStorageForm] = useState({
        resource_group: "",
        storage_name: "",
        location: "East US",
        account_type: "Standard_LRS",
        tier: "Standard",
    });

    const [isVMOOpen, setIsVMOOpen] = useState(false);
    const [isAppOpen, setIsAppOpen] = useState(false);
    const [isStorageOpen, setIsStorageOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/azure/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadSubscriptions();
            } else {
                setConnected(false);
                setHealthStatus("error");
            }
        } catch (error) {
            console.error("Health check failed:", error);
            setConnected(false);
            setHealthStatus("error");
        }
    };

    // Load Azure resources
    const loadSubscriptions = async () => {
        try {
            const response = await fetch("/api/integrations/azure/subscriptions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setSubscriptions(data.data?.subscriptions || []);
                if (data.data?.subscriptions?.length > 0) {
                    setSelectedSubscription(data.data.subscriptions[0].subscriptionId);
                }
            }
        } catch (error) {
            console.error("Failed to load subscriptions:", error);
        }
    };

    const loadResourceGroups = async () => {
        try {
            const response = await fetch("/api/integrations/azure/resource-groups", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    subscription_id: selectedSubscription,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setResourceGroups(data.data?.resourceGroups || []);
            }
        } catch (error) {
            console.error("Failed to load resource groups:", error);
        }
    };

    const loadVirtualMachines = async () => {
        try {
            const response = await fetch("/api/integrations/azure/virtual-machines", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    subscription_id: selectedSubscription,
                    resource_group: selectedResourceGroup,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setVirtualMachines(data.data?.virtualMachines || []);
            }
        } catch (error) {
            console.error("Failed to load virtual machines:", error);
        }
    };

    const loadStorageAccounts = async () => {
        try {
            const response = await fetch("/api/integrations/azure/storage-accounts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    subscription_id: selectedSubscription,
                    resource_group: selectedResourceGroup,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setStorageAccounts(data.data?.storageAccounts || []);
            }
        } catch (error) {
            console.error("Failed to load storage accounts:", error);
        }
    };

    const loadAppServices = async () => {
        try {
            const response = await fetch("/api/integrations/azure/app-services", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    subscription_id: selectedSubscription,
                    resource_group: selectedResourceGroup,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setAppServices(data.data?.appServices || []);
            }
        } catch (error) {
            console.error("Failed to load app services:", error);
        }
    };

    // Create resources
    const createVirtualMachine = async () => {
        try {
            const response = await fetch(
                "/api/integrations/azure/virtual-machines/create",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        ...vmForm,
                        user_id: "current",
                        subscription_id: selectedSubscription,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Virtual machine creation initiated",
                });
                setIsVMOOpen(false);
                setVmForm({
                    resource_group: "",
                    vm_name: "",
                    location: "East US",
                    size: "Standard_B2s",
                    image_publisher: "MicrosoftWindowsServer",
                    image_offer: "WindowsServer",
                    image_sku: "2019-Datacenter",
                    admin_username: "",
                    admin_password: "",
                    network_interface_id: "",
                });
                loadVirtualMachines();
            }
        } catch (error) {
            console.error("Failed to create virtual machine:", error);
            toast({
                title: "Error",
                description: "Failed to create virtual machine",
                variant: "destructive",
            });
        }
    };

    const deployAppService = async () => {
        try {
            const response = await fetch(
                "/api/integrations/azure/app-services/deploy",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        ...appForm,
                        user_id: "current",
                        subscription_id: selectedSubscription,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "App service deployment initiated",
                });
                setIsAppOpen(false);
                setAppForm({
                    resource_group: "",
                    app_name: "",
                    location: "East US",
                    plan_tier: "Basic",
                    plan_size: "B1",
                    runtime: "NODE",
                    https_only: true,
                });
                loadAppServices();
            }
        } catch (error) {
            console.error("Failed to deploy app service:", error);
            toast({
                title: "Error",
                description: "Failed to deploy app service",
                variant: "destructive",
            });
        }
    };

    const createStorageAccount = async () => {
        try {
            const response = await fetch(
                "/api/integrations/azure/storage-accounts/create",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        ...storageForm,
                        user_id: "current",
                        subscription_id: selectedSubscription,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Storage account creation initiated",
                });
                setIsStorageOpen(false);
                setStorageForm({
                    resource_group: "",
                    storage_name: "",
                    location: "East US",
                    account_type: "Standard_LRS",
                    tier: "Standard",
                });
                loadStorageAccounts();
            }
        } catch (error) {
            console.error("Failed to create storage account:", error);
            toast({
                title: "Error",
                description: "Failed to create storage account",
                variant: "destructive",
            });
        }
    };

    // Filter data based on search
    const filteredVMs = virtualMachines.filter(
        (vm) =>
            vm.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            vm.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
            vm.status.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredStorage = storageAccounts.filter(
        (storage) =>
            storage.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            storage.resource_group
                .toLowerCase()
                .includes(searchQuery.toLowerCase()) ||
            storage.tier.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredApps = appServices.filter(
        (app) =>
            app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            app.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
            app.state.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalRG = resourceGroups.length;
    const totalVMs = virtualMachines.length;
    const runningVMs = virtualMachines.filter(
        (vm) => vm.status.toLowerCase() === "running",
    ).length;
    const totalStorage = storageAccounts.length;
    const totalApps = appServices.length;
    const runningApps = appServices.filter(
        (app) => app.state.toLowerCase() === "running",
    ).length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected && selectedSubscription) {
            loadResourceGroups();
            loadVirtualMachines();
            loadStorageAccounts();
            loadAppServices();
        }
    }, [
        connected,
        selectedSubscription,
        selectedResourceGroup,
    ]);

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status?.toLowerCase()) {
            case "running":
                return "default"; // green-ish
            case "stopped":
                return "destructive";
            case "starting":
                return "secondary"; // yellow-ish
            case "stopping":
                return "secondary"; // orange-ish
            case "creating":
                return "outline"; // blue-ish
            case "deleting":
                return "destructive";
            default:
                return "outline";
        }
    };

    const getTierVariant = (tier: string): "default" | "secondary" | "outline" => {
        switch (tier?.toLowerCase()) {
            case "premium":
                return "default"; // purple-ish
            case "standard":
                return "outline"; // blue-ish
            case "basic":
                return "secondary"; // green-ish
            default:
                return "outline";
        }
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Sun className="w-8 h-8 text-blue-500" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Microsoft Azure Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Cloud computing platform for infrastructure and services
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Badge
                            variant={healthStatus === "healthy" ? "default" : "destructive"}
                            className="flex items-center space-x-1"
                        >
                            {healthStatus === "healthy" ? (
                                <CheckCircle className="w-3 h-3 mr-1" />
                            ) : (
                                <AlertTriangle className="w-3 h-3 mr-1" />
                            )}
                            {connected ? "Connected" : "Disconnected"}
                        </Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkConnection}
                        >
                            <RefreshCw className="mr-2 w-3 h-3" />
                            Refresh Status
                        </Button>
                    </div>

                    {subscriptions.length > 0 && (
                        <div className="flex items-center space-x-4">
                            <Select
                                value={selectedSubscription}
                                onValueChange={setSelectedSubscription}
                            >
                                <SelectTrigger className="w-[300px]">
                                    <SelectValue placeholder="Select Subscription" />
                                </SelectTrigger>
                                <SelectContent>
                                    {subscriptions.map((sub) => (
                                        <SelectItem key={sub.subscriptionId} value={sub.subscriptionId}>
                                            {sub.displayName} ({sub.state})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center justify-center space-y-6 py-8">
                                <Sun className="w-16 h-16 text-gray-400" />
                                <div className="space-y-2 text-center">
                                    <h2 className="text-2xl font-bold">Connect Azure</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Azure account to start managing cloud resources
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-blue-600 hover:bg-blue-700"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/azure/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Azure Account
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    // Connected State
                    <>
                        {/* Services Overview */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Virtual Machines</p>
                                        <div className="text-2xl font-bold">{totalVMs}</div>
                                        <p className="text-xs text-muted-foreground">{runningVMs} running</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Storage Accounts</p>
                                        <div className="text-2xl font-bold">{totalStorage}</div>
                                        <p className="text-xs text-muted-foreground">Blob and file storage</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">App Services</p>
                                        <div className="text-2xl font-bold">{totalApps}</div>
                                        <p className="text-xs text-muted-foreground">{runningApps} running</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Resource Groups</p>
                                        <div className="text-2xl font-bold">{totalRG}</div>
                                        <p className="text-xs text-muted-foreground">Resource organization</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="virtual-machines">
                            <TabsList>
                                <TabsTrigger value="virtual-machines">Virtual Machines</TabsTrigger>
                                <TabsTrigger value="app-services">App Services</TabsTrigger>
                                <TabsTrigger value="storage">Storage</TabsTrigger>
                                <TabsTrigger value="resource-groups">Resource Groups</TabsTrigger>
                            </TabsList>

                            {/* Virtual Machines Tab */}
                            <TabsContent value="virtual-machines" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedResourceGroup}
                                        onValueChange={setSelectedResourceGroup}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Resource Group" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Resource Groups</SelectItem>
                                            {resourceGroups.map((rg) => (
                                                <SelectItem key={rg.id} value={rg.name}>
                                                    {rg.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search VMs..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsVMOOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create VM
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                                    <tr>
                                                        <th className="px-6 py-3">Name</th>
                                                        <th className="px-6 py-3">Size</th>
                                                        <th className="px-6 py-3">OS</th>
                                                        <th className="px-6 py-3">Status</th>
                                                        <th className="px-6 py-3">Resource Group</th>
                                                        <th className="px-6 py-3">IP Address</th>
                                                        <th className="px-6 py-3">Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {filteredVMs.map((vm) => (
                                                        <tr key={vm.id} className="bg-white border-b hover:bg-gray-50">
                                                            <td className="px-6 py-4 font-medium text-gray-900">
                                                                <div className="flex items-center space-x-2">
                                                                    <Server className="w-4 h-4 text-blue-500" />
                                                                    <span>{vm.name}</span>
                                                                </div>
                                                            </td>
                                                            <td className="px-6 py-4">{vm.size}</td>
                                                            <td className="px-6 py-4">
                                                                <Badge variant="outline">{vm.os_type}</Badge>
                                                            </td>
                                                            <td className="px-6 py-4">
                                                                <Badge variant={getStatusVariant(vm.status)}>
                                                                    {vm.status}
                                                                </Badge>
                                                            </td>
                                                            <td className="px-6 py-4">{vm.resource_group}</td>
                                                            <td className="px-6 py-4">{vm.public_ip || "N/A"}</td>
                                                            <td className="px-6 py-4">
                                                                <Button variant="outline" size="sm">
                                                                    <Eye className="w-4 h-4 mr-2" />
                                                                    Details
                                                                </Button>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* App Services Tab */}
                            <TabsContent value="app-services" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedResourceGroup}
                                        onValueChange={setSelectedResourceGroup}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Resource Group" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Resource Groups</SelectItem>
                                            {resourceGroups.map((rg) => (
                                                <SelectItem key={rg.id} value={rg.name}>
                                                    {rg.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search apps..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsAppOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Deploy App
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                                    <tr>
                                                        <th className="px-6 py-3">Name</th>
                                                        <th className="px-6 py-3">Runtime</th>
                                                        <th className="px-6 py-3">State</th>
                                                        <th className="px-6 py-3">Host Names</th>
                                                        <th className="px-6 py-3">Resource Group</th>
                                                        <th className="px-6 py-3">HTTPS Only</th>
                                                        <th className="px-6 py-3">Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {filteredApps.map((app) => (
                                                        <tr key={app.id} className="bg-white border-b hover:bg-gray-50">
                                                            <td className="px-6 py-4 font-medium text-gray-900">
                                                                <div className="flex items-center space-x-2">
                                                                    <Globe className="w-4 h-4 text-blue-500" />
                                                                    <span>{app.name}</span>
                                                                </div>
                                                            </td>
                                                            <td className="px-6 py-4">{app.runtime}</td>
                                                            <td className="px-6 py-4">
                                                                <Badge variant={getStatusVariant(app.state)}>
                                                                    {app.state}
                                                                </Badge>
                                                            </td>
                                                            <td className="px-6 py-4">{app.host_names[0]}</td>
                                                            <td className="px-6 py-4">{app.resource_group}</td>
                                                            <td className="px-6 py-4">
                                                                <Badge variant={app.https_only ? "default" : "destructive"}>
                                                                    {app.https_only ? "Enabled" : "Disabled"}
                                                                </Badge>
                                                            </td>
                                                            <td className="px-6 py-4">
                                                                <div className="flex space-x-2">
                                                                    <Button variant="outline" size="sm">
                                                                        <Eye className="w-4 h-4 mr-2" />
                                                                        Details
                                                                    </Button>
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() =>
                                                                            window.open(`https://${app.host_names[0]}`, "_blank")
                                                                        }
                                                                    >
                                                                        <ExternalLink className="w-4 h-4 mr-2" />
                                                                        Open
                                                                    </Button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Storage Tab */}
                            <TabsContent value="storage" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedResourceGroup}
                                        onValueChange={setSelectedResourceGroup}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Resource Group" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Resource Groups</SelectItem>
                                            {resourceGroups.map((rg) => (
                                                <SelectItem key={rg.id} value={rg.name}>
                                                    {rg.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search storage..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsStorageOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Storage
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                                    <tr>
                                                        <th className="px-6 py-3">Name</th>
                                                        <th className="px-6 py-3">Type</th>
                                                        <th className="px-6 py-3">Tier</th>
                                                        <th className="px-6 py-3">Replication</th>
                                                        <th className="px-6 py-3">Resource Group</th>
                                                        <th className="px-6 py-3">Location</th>
                                                        <th className="px-6 py-3">Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {filteredStorage.map((storage) => (
                                                        <tr key={storage.id} className="bg-white border-b hover:bg-gray-50">
                                                            <td className="px-6 py-4 font-medium text-gray-900">
                                                                <div className="flex items-center space-x-2">
                                                                    <Database className="w-4 h-4 text-blue-500" />
                                                                    <span>{storage.name}</span>
                                                                </div>
                                                            </td>
                                                            <td className="px-6 py-4">{storage.type}</td>
                                                            <td className="px-6 py-4">
                                                                <Badge variant={getTierVariant(storage.tier)}>
                                                                    {storage.tier}
                                                                </Badge>
                                                            </td>
                                                            <td className="px-6 py-4">{storage.replication}</td>
                                                            <td className="px-6 py-4">{storage.resource_group}</td>
                                                            <td className="px-6 py-4">{storage.location}</td>
                                                            <td className="px-6 py-4">
                                                                <Button variant="outline" size="sm">
                                                                    <Eye className="w-4 h-4 mr-2" />
                                                                    Details
                                                                </Button>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Resource Groups Tab */}
                            <TabsContent value="resource-groups" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search resource groups..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                                    <tr>
                                                        <th className="px-6 py-3">Name</th>
                                                        <th className="px-6 py-3">Location</th>
                                                        <th className="px-6 py-3">Created</th>
                                                        <th className="px-6 py-3">Tags</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {resourceGroups
                                                        .filter(
                                                            (rg) =>
                                                                rg.name
                                                                    .toLowerCase()
                                                                    .includes(searchQuery.toLowerCase()) ||
                                                                rg.location
                                                                    .toLowerCase()
                                                                    .includes(searchQuery.toLowerCase()),
                                                        )
                                                        .map((rg) => (
                                                            <tr key={rg.id} className="bg-white border-b hover:bg-gray-50">
                                                                <td className="px-6 py-4 font-medium text-gray-900">
                                                                    <div className="flex items-center space-x-2">
                                                                        <Layers className="w-4 h-4 text-blue-500" />
                                                                        <span>{rg.name}</span>
                                                                    </div>
                                                                </td>
                                                                <td className="px-6 py-4">{rg.location}</td>
                                                                <td className="px-6 py-4">
                                                                    {formatDate(rg.created_at)}
                                                                </td>
                                                                <td className="px-6 py-4">
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {Object.entries(rg.tags).map(
                                                                            ([key, value]) => (
                                                                                <Badge key={key} variant="outline">
                                                                                    {key}: {value}
                                                                                </Badge>
                                                                            ),
                                                                        )}
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>

                        {/* Create VM Modal */}
                        <Dialog open={isVMOOpen} onOpenChange={setIsVMOOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Virtual Machine</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Resource Group</label>
                                        <Select
                                            value={vmForm.resource_group}
                                            onValueChange={(value) =>
                                                setVmForm({
                                                    ...vmForm,
                                                    resource_group: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Resource Group" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {resourceGroups.map((rg) => (
                                                    <SelectItem key={rg.id} value={rg.name}>
                                                        {rg.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">VM Name</label>
                                        <Input
                                            placeholder="my-vm"
                                            value={vmForm.vm_name}
                                            onChange={(e) =>
                                                setVmForm({ ...vmForm, vm_name: e.target.value })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Location</label>
                                        <Select
                                            value={vmForm.location}
                                            onValueChange={(value) =>
                                                setVmForm({ ...vmForm, location: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Location" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="East US">East US</SelectItem>
                                                <SelectItem value="West US">West US</SelectItem>
                                                <SelectItem value="West Europe">West Europe</SelectItem>
                                                <SelectItem value="Southeast Asia">Southeast Asia</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">VM Size</label>
                                        <Select
                                            value={vmForm.size}
                                            onValueChange={(value) =>
                                                setVmForm({ ...vmForm, size: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select VM Size" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Standard_B1s">
                                                    Standard_B1s (1 vCPU, 1 GB RAM)
                                                </SelectItem>
                                                <SelectItem value="Standard_B2s">
                                                    Standard_B2s (1 vCPU, 2 GB RAM)
                                                </SelectItem>
                                                <SelectItem value="Standard_B2ms">
                                                    Standard_B2ms (2 vCPU, 8 GB RAM)
                                                </SelectItem>
                                                <SelectItem value="Standard_D2s_v3">
                                                    Standard_D2s_v3 (2 vCPU, 8 GB RAM)
                                                </SelectItem>
                                                <SelectItem value="Standard_D4s_v3">
                                                    Standard_D4s_v3 (4 vCPU, 16 GB RAM)
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Admin Username</label>
                                        <Input
                                            placeholder="azureuser"
                                            value={vmForm.admin_username}
                                            onChange={(e) =>
                                                setVmForm({
                                                    ...vmForm,
                                                    admin_username: e.target.value,
                                                })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Admin Password</label>
                                        <Input
                                            type="password"
                                            placeholder="SecurePassword123!"
                                            value={vmForm.admin_password}
                                            onChange={(e) =>
                                                setVmForm({
                                                    ...vmForm,
                                                    admin_password: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsVMOOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={createVirtualMachine}
                                        disabled={
                                            !vmForm.resource_group ||
                                            !vmForm.vm_name ||
                                            !vmForm.admin_username ||
                                            !vmForm.admin_password
                                        }
                                    >
                                        Create VM
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Deploy App Service Modal */}
                        <Dialog open={isAppOpen} onOpenChange={setIsAppOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Deploy App Service</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Resource Group</label>
                                        <Select
                                            value={appForm.resource_group}
                                            onValueChange={(value) =>
                                                setAppForm({
                                                    ...appForm,
                                                    resource_group: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Resource Group" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {resourceGroups.map((rg) => (
                                                    <SelectItem key={rg.id} value={rg.name}>
                                                        {rg.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">App Name</label>
                                        <Input
                                            placeholder="my-app"
                                            value={appForm.app_name}
                                            onChange={(e) =>
                                                setAppForm({ ...appForm, app_name: e.target.value })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Location</label>
                                        <Select
                                            value={appForm.location}
                                            onValueChange={(value) =>
                                                setAppForm({ ...appForm, location: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Location" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="East US">East US</SelectItem>
                                                <SelectItem value="West US">West US</SelectItem>
                                                <SelectItem value="West Europe">West Europe</SelectItem>
                                                <SelectItem value="Southeast Asia">Southeast Asia</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Runtime</label>
                                        <Select
                                            value={appForm.runtime}
                                            onValueChange={(value) =>
                                                setAppForm({ ...appForm, runtime: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Runtime" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="NODE">Node.js</SelectItem>
                                                <SelectItem value="PYTHON">Python</SelectItem>
                                                <SelectItem value="JAVA">Java</SelectItem>
                                                <SelectItem value="DOTNETCORE">.NET Core</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="flex items-center space-x-2">
                                        <Input
                                            type="checkbox"
                                            id="https_only"
                                            className="w-4 h-4"
                                            checked={appForm.https_only}
                                            onChange={(e) =>
                                                setAppForm({
                                                    ...appForm,
                                                    https_only: e.target.checked,
                                                })
                                            }
                                        />
                                        <label htmlFor="https_only" className="text-sm font-medium leading-none">
                                            HTTPS Only
                                        </label>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsAppOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={deployAppService}
                                        disabled={
                                            !appForm.resource_group ||
                                            !appForm.app_name ||
                                            !appForm.location
                                        }
                                    >
                                        Deploy App
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Storage Account Modal */}
                        <Dialog open={isStorageOpen} onOpenChange={setIsStorageOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Storage Account</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Resource Group</label>
                                        <Select
                                            value={storageForm.resource_group}
                                            onValueChange={(value) =>
                                                setStorageForm({
                                                    ...storageForm,
                                                    resource_group: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Resource Group" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {resourceGroups.map((rg) => (
                                                    <SelectItem key={rg.id} value={rg.name}>
                                                        {rg.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Storage Account Name</label>
                                        <Input
                                            placeholder="mystorageaccount"
                                            value={storageForm.storage_name}
                                            onChange={(e) =>
                                                setStorageForm({
                                                    ...storageForm,
                                                    storage_name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Location</label>
                                        <Select
                                            value={storageForm.location}
                                            onValueChange={(value) =>
                                                setStorageForm({
                                                    ...storageForm,
                                                    location: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Location" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="East US">East US</SelectItem>
                                                <SelectItem value="West US">West US</SelectItem>
                                                <SelectItem value="West Europe">West Europe</SelectItem>
                                                <SelectItem value="Southeast Asia">Southeast Asia</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Account Type</label>
                                        <Select
                                            value={storageForm.account_type}
                                            onValueChange={(value) =>
                                                setStorageForm({
                                                    ...storageForm,
                                                    account_type: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Account Type" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Standard_LRS">Standard LRS</SelectItem>
                                                <SelectItem value="Standard_ZRS">Standard ZRS</SelectItem>
                                                <SelectItem value="Standard_GRS">Standard GRS</SelectItem>
                                                <SelectItem value="Premium_LRS">Premium LRS</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Tier</label>
                                        <Select
                                            value={storageForm.tier}
                                            onValueChange={(value) =>
                                                setStorageForm({
                                                    ...storageForm,
                                                    tier: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Tier" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Standard">Standard</SelectItem>
                                                <SelectItem value="Premium">Premium</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsStorageOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={createStorageAccount}
                                        disabled={
                                            !storageForm.resource_group ||
                                            !storageForm.storage_name ||
                                            !storageForm.location
                                        }
                                    >
                                        Create Storage
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </>
                )}
            </div>
        </div>
    );
};

export default AzureIntegration;
