/**
 * My Templates Page
 * User's template management page with listing, filtering, and CRUD operations
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import {
  Plus,
  Search,
  Edit,
  Trash2,
  Star,
  Eye,
  EyeOff,
  Copy,
  TrendingUp,
} from 'lucide-react';
import { TemplateEditor } from './TemplateEditor';

// Types
export interface TemplateParameter {
  name: string;
  label?: string;
  description?: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required: boolean;
  default_value?: any;
  options?: string[];
  validation_rules?: Record<string, any>;
}

export interface TemplateStep {
  id: string;
  name: string;
  description?: string;
  step_type: string;
  service?: string;
  action?: string;
  parameters?: TemplateParameter[];
  condition?: string;
  depends_on?: string[];
  estimated_duration?: number;
  is_optional?: boolean;
}

export interface WorkflowTemplate {
  template_id?: string;
  id?: string;
  name: string;
  description: string;
  category: string;
  complexity: string;
  tags: string[];
  inputs: TemplateParameter[];
  steps: TemplateStep[];
  output_schema?: Record<string, any>;
  is_public?: boolean;
  is_featured?: boolean;
  usage_count?: number;
  rating?: number;
  rating_count?: number;
  created_at?: string;
  updated_at?: string;
}

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'automation', label: 'Automation' },
  { value: 'data_processing', label: 'Data Processing' },
  { value: 'ai_ml', label: 'AI/ML' },
  { value: 'business', label: 'Business' },
  { value: 'integration', label: 'Integration' },
  { value: 'monitoring', label: 'Monitoring' },
  { value: 'reporting', label: 'Reporting' },
  { value: 'security', label: 'Security' },
  { value: 'general', label: 'General' },
];

export const MyTemplatesPage: React.FC = () => {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<WorkflowTemplate | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<{ open: boolean; template: WorkflowTemplate | null }>({
    open: false,
    template: null,
  });

  // Fetch templates
  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      // In production, you'd get user_id from auth context
      const userId = 'current-user-id'; // Replace with actual auth
      const response = await fetch(`/api/user/templates?user_id=${userId}`);
      if (!response.ok) throw new Error('Failed to fetch templates');

      const data = await response.json();
      setTemplates(data);
    } catch (error) {
      console.error('Error fetching templates:', error);
      toast({
        title: 'Error',
        description: 'Failed to load templates',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  // Create new template
  const handleCreateTemplate = () => {
    setEditingTemplate(null);
    setShowEditor(true);
  };

  // Edit template
  const handleEditTemplate = (template: WorkflowTemplate) => {
    setEditingTemplate(template);
    setShowEditor(true);
  };

  // Save template
  const handleSaveTemplate = async (template: WorkflowTemplate) => {
    try {
      const userId = 'current-user-id'; // Replace with actual auth
      const isUpdate = !!template.template_id;

      const url = isUpdate
        ? `/api/user/templates/${template.template_id}?user_id=${userId}`
        : `/api/user/templates?user_id=${userId}`;

      const response = await fetch(url, {
        method: isUpdate ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...template,
          template_json: { nodes: [], edges: [] }, // Simplified for now
        }),
      });

      if (!response.ok) throw new Error('Failed to save template');

      toast({
        title: 'Success',
        description: isUpdate ? 'Template updated successfully' : 'Template created successfully',
      });

      setShowEditor(false);
      fetchTemplates();
    } catch (error) {
      console.error('Error saving template:', error);
      toast({
        title: 'Error',
        description: 'Failed to save template',
        variant: 'error',
      });
    }
  };

  // Delete template
  const handleDeleteTemplate = async () => {
    if (!deleteDialog.template) return;

    try {
      const userId = 'current-user-id'; // Replace with actual auth
      const response = await fetch(
        `/api/user/templates/${deleteDialog.template.template_id}?user_id=${userId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to delete template');

      toast({
        title: 'Success',
        description: 'Template deleted successfully',
      });

      setDeleteDialog({ open: false, template: null });
      fetchTemplates();
    } catch (error) {
      console.error('Error deleting template:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete template',
        variant: 'error',
      });
    }
  };

  // Toggle visibility
  const handleToggleVisibility = async (template: WorkflowTemplate) => {
    try {
      const userId = 'current-user-id'; // Replace with actual auth
      const response = await fetch(
        `/api/user/templates/${template.template_id}/publish?user_id=${userId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            visibility: template.is_public ? 'private' : 'public',
          }),
        }
      );

      if (!response.ok) throw new Error('Failed to update visibility');

      fetchTemplates();
    } catch (error) {
      console.error('Error updating visibility:', error);
      toast({
        title: 'Error',
        description: 'Failed to update visibility',
        variant: 'error',
      });
    }
  };

  // Duplicate template
  const handleDuplicateTemplate = async (template: WorkflowTemplate) => {
    try {
      const userId = 'current-user-id'; // Replace with actual auth
      const response = await fetch(
        `/api/user/templates/${template.template_id}/duplicate?user_id=${userId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: `${template.name} (Copy)`,
          }),
        }
      );

      if (!response.ok) throw new Error('Failed to duplicate template');

      toast({
        title: 'Success',
        description: 'Template duplicated successfully',
      });

      fetchTemplates();
    } catch (error) {
      console.error('Error duplicating template:', error);
      toast({
        title: 'Error',
        description: 'Failed to duplicate template',
        variant: 'error',
      });
    }
  };

  // Filter templates
  const filteredTemplates = templates.filter((template) => {
    const matchesSearch =
      !searchQuery ||
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory =
      categoryFilter === 'all' || template.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p>Loading templates...</p>
      </div>
    );
  }

  if (showEditor) {
    return (
      <div className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              {editingTemplate ? 'Edit Template' : 'Create New Template'}
            </h1>
            <p className="text-muted-foreground">
              {editingTemplate ? 'Update your workflow template' : 'Design a reusable workflow template'}
            </p>
          </div>
          <Button variant="outline" onClick={() => setShowEditor(false)}>
            Back to Templates
          </Button>
        </div>

        <TemplateEditor
          initialTemplate={editingTemplate || undefined}
          onSave={handleSaveTemplate}
          onCancel={() => setShowEditor(false)}
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">My Templates</h1>
          <p className="text-muted-foreground">
            Create and manage your workflow templates
          </p>
        </div>
        <Button onClick={handleCreateTemplate}>
          <Plus className="h-4 w-4 mr-2" />
          New Template
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Template Grid */}
      {filteredTemplates.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground mb-4">
              {searchQuery || categoryFilter !== 'all'
                ? 'No templates match your filters'
                : 'You haven\'t created any templates yet'}
            </p>
            {!searchQuery && categoryFilter === 'all' && (
              <Button onClick={handleCreateTemplate}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Template
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTemplates.map((template) => (
            <Card key={template.template_id || template.id} className="hover:shadow-md transition">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-lg">{template.name}</CardTitle>
                    <CardDescription className="line-clamp-2 mt-1">
                      {template.description}
                    </CardDescription>
                  </div>
                  {template.is_featured && (
                    <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Badges */}
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{template.category}</Badge>
                  <Badge variant="secondary">{template.complexity}</Badge>
                  {template.is_public ? (
                    <Badge variant="default">
                      <Eye className="h-3 w-3 mr-1" />
                      Public
                    </Badge>
                  ) : (
                    <Badge variant="outline">
                      <EyeOff className="h-3 w-3 mr-1" />
                      Private
                    </Badge>
                  )}
                </div>

                {/* Tags */}
                {template.tags && template.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {template.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                    {template.tags.length > 3 && (
                      <Badge variant="secondary" className="text-xs">
                        +{template.tags.length - 3}
                      </Badge>
                    )}
                  </div>
                )}

                {/* Stats */}
                {(template.usage_count || template.rating) && (
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {template.usage_count !== undefined && template.usage_count > 0 && (
                      <div className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {template.usage_count} uses
                      </div>
                    )}
                    {template.rating !== undefined && template.rating > 0 && (
                      <div className="flex items-center gap-1">
                        <Star className="h-3 w-3 fill-yellow-500 text-yellow-500" />
                        {template.rating.toFixed(1)}
                        {template.rating_count && `(${template.rating_count})`}
                      </div>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleEditTemplate(template)}
                  >
                    <Edit className="h-3 w-3 mr-1" />
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleToggleVisibility(template)}
                    title={template.is_public ? 'Make private' : 'Make public'}
                  >
                    {template.is_public ? (
                      <EyeOff className="h-3 w-3" />
                    ) : (
                      <Eye className="h-3 w-3" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDuplicateTemplate(template)}
                    title="Duplicate"
                  >
                    <Copy className="h-3 w-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDeleteDialog({ open: true, template })}
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialog.open} onOpenChange={(open) => setDeleteDialog({ open, template: null })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Template?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deleteDialog.template?.name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteTemplate} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default MyTemplatesPage;
