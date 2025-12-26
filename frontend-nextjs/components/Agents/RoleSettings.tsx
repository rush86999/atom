import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import { Plus, Edit, Trash2, Copy } from 'lucide-react';

interface AgentRole {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  permissions: {
    canAccessFiles: boolean;
    canAccessWeb: boolean;
    canExecuteCode: boolean;
    canAccessDatabase: boolean;
    canSendEmails: boolean;
    canMakeAPICalls: boolean;
  };
  systemPrompt: string;
  modelConfig: {
    model: string;
    temperature: number;
    maxTokens: number;
    topP: number;
    frequencyPenalty: number;
    presencePenalty: number;
  };
  isDefault: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface RoleSettingsProps {
  onRoleCreate?: (role: AgentRole) => void;
  onRoleUpdate?: (roleId: string, updates: Partial<AgentRole>) => void;
  onRoleDelete?: (roleId: string) => void;
  onRoleDuplicate?: (role: AgentRole) => void;
  initialRoles?: AgentRole[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const RoleSettings: React.FC<RoleSettingsProps> = ({
  onRoleCreate,
  onRoleUpdate,
  onRoleDelete,
  onRoleDuplicate,
  initialRoles = [],
  showNavigation = true,
  compactView = false
}) => {
  const [roles, setRoles] = useState<AgentRole[]>(initialRoles);
  const [selectedRole, setSelectedRole] = useState<AgentRole | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  // Default roles
  const defaultRoles: AgentRole[] = [
    {
      id: 'personal_assistant',
      name: 'Personal Assistant',
      description: 'General purpose assistant for daily tasks and scheduling',
      capabilities: ['scheduling', 'email_management', 'note_taking', 'web_search'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: false,
        canAccessDatabase: false,
        canSendEmails: true,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are a helpful personal assistant. Help with scheduling, email management, and general tasks.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.7,
        maxTokens: 2000,
        topP: 1.0,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    },
    {
      id: 'research_agent',
      name: 'Research Agent',
      description: 'Specialized in research and information gathering',
      capabilities: ['web_search', 'data_analysis', 'summarization', 'citation'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: false,
        canAccessDatabase: false,
        canSendEmails: false,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are a research specialist. Provide thorough, well-researched information with proper citations.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.3,
        maxTokens: 4000,
        topP: 1.0,
        frequencyPenalty: 0.1,
        presencePenalty: 0.1
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    },
    {
      id: 'coding_agent',
      name: 'Coding Agent',
      description: 'Software development and code assistance',
      capabilities: ['code_generation', 'debugging', 'code_review', 'documentation'],
      permissions: {
        canAccessFiles: true,
        canAccessWeb: true,
        canExecuteCode: true,
        canAccessDatabase: true,
        canSendEmails: false,
        canMakeAPICalls: true
      },
      systemPrompt: 'You are an expert software developer. Write clean, efficient, and well-documented code.',
      modelConfig: {
        model: 'gpt-4',
        temperature: 0.2,
        maxTokens: 4000,
        topP: 1.0,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0
      },
      isDefault: true,
      createdAt: new Date(),
      updatedAt: new Date()
    }
  ];

  useEffect(() => {
    if (initialRoles.length === 0 && roles.length === 0) {
      setRoles(defaultRoles);
    } else if (initialRoles.length > 0) {
      setRoles(initialRoles);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRoles]);

  const handleCreateRole = (roleData: Omit<AgentRole, 'id' | 'createdAt' | 'updatedAt' | 'isDefault'>) => {
    const newRole: AgentRole = {
      ...roleData,
      id: Date.now().toString(),
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setRoles(prev => [...prev, newRole]);
    onRoleCreate?.(newRole);
    toast({
      title: 'Role created',
      variant: 'success',
    });
    setIsDialogOpen(false);
  };

  const handleUpdateRole = (roleData: Omit<AgentRole, 'id' | 'createdAt' | 'updatedAt' | 'isDefault'>) => {
    if (!selectedRole) return;

    const updates = roleData;
    setRoles(prev => prev.map(role =>
      role.id === selectedRole.id ? { ...role, ...updates, updatedAt: new Date() } : role
    ));
    onRoleUpdate?.(selectedRole.id, updates);
    toast({
      title: 'Role updated',
      variant: 'success',
    });
    setIsDialogOpen(false);
    setSelectedRole(null);
  };

  const handleDeleteRole = (roleId: string) => {
    const role = roles.find(r => r.id === roleId);
    if (role?.isDefault) {
      toast({
        title: 'Cannot delete default role',
        variant: 'error',
      });
      return;
    }
    setRoles(prev => prev.filter(role => role.id !== roleId));
    onRoleDelete?.(roleId);
    toast({
      title: 'Role deleted',
      variant: 'success',
    });
  };

  const handleDuplicateRole = (role: AgentRole) => {
    const duplicatedRole: AgentRole = {
      ...role,
      id: Date.now().toString(),
      name: `${role.name} (Copy)`,
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    setRoles(prev => [...prev, duplicatedRole]);
    onRoleDuplicate?.(duplicatedRole);
    toast({
      title: 'Role duplicated',
      variant: 'success',
    });
  };

  const openCreateDialog = () => {
    setSelectedRole(null);
    setIsDialogOpen(true);
  };

  const openEditDialog = (role: AgentRole) => {
    setSelectedRole(role);
    setIsDialogOpen(true);
  };

  // Form Component
  const RoleForm = ({ role, onSubmit, onCancel }: { role?: AgentRole | null, onSubmit: (data: any) => void, onCancel: () => void }) => {
    const [formData, setFormData] = useState({
      name: role?.name || '',
      description: role?.description || '',
      capabilities: role?.capabilities?.join(', ') || '',
      permissions: {
        canAccessFiles: role?.permissions?.canAccessFiles || false,
        canAccessWeb: role?.permissions?.canAccessWeb || false,
        canExecuteCode: role?.permissions?.canExecuteCode || false,
        canAccessDatabase: role?.permissions?.canAccessDatabase || false,
        canSendEmails: role?.permissions?.canSendEmails || false,
        canMakeAPICalls: role?.permissions?.canMakeAPICalls || false
      },
      systemPrompt: role?.systemPrompt || '',
      modelConfig: {
        model: role?.modelConfig?.model || 'gpt-4',
        temperature: role?.modelConfig?.temperature || 0.7,
        maxTokens: role?.modelConfig?.maxTokens || 2000,
        topP: role?.modelConfig?.topP || 1.0,
        frequencyPenalty: role?.modelConfig?.frequencyPenalty || 0.0,
        presencePenalty: role?.modelConfig?.presencePenalty || 0.0
      }
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        name: formData.name,
        description: formData.description,
        capabilities: formData.capabilities.split(',').map(cap => cap.trim()).filter(Boolean),
        permissions: formData.permissions,
        systemPrompt: formData.systemPrompt,
        modelConfig: formData.modelConfig
      });
    };

    return (
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Role Name</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Enter role name"
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">Description</Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
            placeholder="Describe the role's purpose"
            rows={2}
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="capabilities">Capabilities</Label>
          <Input
            id="capabilities"
            value={formData.capabilities}
            onChange={(e) => setFormData(prev => ({ ...prev, capabilities: e.target.value }))}
            placeholder="web_search, data_analysis, code_generation"
          />
          <p className="text-sm text-gray-500">Separate capabilities with commas</p>
        </div>

        <Accordion type="single" collapsible className="w-full">
          <AccordionItem value="permissions">
            <AccordionTrigger>Permissions</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                {Object.entries(formData.permissions).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <Label htmlFor={key} className="flex-1 capitalize">
                      {key.replace(/([A-Z])/g, ' $1').trim()}
                    </Label>
                    <Switch
                      id={key}
                      checked={value}
                      onCheckedChange={(checked) => setFormData(prev => ({
                        ...prev,
                        permissions: { ...prev.permissions, [key]: checked }
                      }))}
                    />
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="model-config">
            <AccordionTrigger>Model Configuration</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Select
                    value={formData.modelConfig.model}
                    onValueChange={(value) => setFormData(prev => ({
                      ...prev,
                      modelConfig: { ...prev.modelConfig, model: value }
                    }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select Model" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gpt-4">GPT-4</SelectItem>
                      <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                      <SelectItem value="claude-3">Claude 3</SelectItem>
                      <SelectItem value="llama-2">Llama 2</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="temperature">Temperature</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={formData.modelConfig.temperature}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        modelConfig: { ...prev.modelConfig, temperature: parseFloat(e.target.value) }
                      }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="maxTokens">Max Tokens</Label>
                    <Input
                      type="number"
                      value={formData.modelConfig.maxTokens}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        modelConfig: { ...prev.modelConfig, maxTokens: parseInt(e.target.value) }
                      }))}
                    />
                  </div>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        <div className="space-y-2">
          <Label htmlFor="systemPrompt">System Prompt</Label>
          <Textarea
            id="systemPrompt"
            value={formData.systemPrompt}
            onChange={(e) => setFormData(prev => ({ ...prev, systemPrompt: e.target.value }))}
            placeholder="Define the agent's behavior..."
            rows={6}
            required
          />
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">
            {role ? 'Update Role' : 'Create Role'}
          </Button>
        </DialogFooter>
      </form>
    );
  };

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <Spinner />
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Role Settings</CardTitle>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Create Role
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Capabilities</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.map((role) => (
              <TableRow key={role.id}>
                <TableCell className="font-medium">{role.name}</TableCell>
                <TableCell>{role.description}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {role.capabilities.map((cap) => (
                      <Badge key={cap} variant="secondary">
                        {cap}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEditDialog(role)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDuplicateRole(role)}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-500 hover:text-red-600"
                      onClick={() => handleDeleteRole(role.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selectedRole ? 'Edit Role' : 'Create Role'}</DialogTitle>
          </DialogHeader>
          <RoleForm
            role={selectedRole}
            onSubmit={selectedRole ? handleUpdateRole : handleCreateRole}
            onCancel={() => setIsDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default RoleSettings;
