/**
 * Template Editor Component
 * Visual workflow template editor for creating custom templates
 */

import React, { useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { Spinner } from '@/components/ui/spinner';
import {
  Save,
  Eye,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { TemplateMetadataForm } from './TemplateMetadataForm';
import { TemplatePreviewModal } from './TemplatePreviewModal';

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
  name: string;
  description: string;
  category: string;
  complexity: string;
  tags: string[];
  inputs: TemplateParameter[];
  steps: TemplateStep[];
  output_schema?: Record<string, any>;
}

interface TemplateEditorProps {
  initialTemplate?: Partial<WorkflowTemplate>;
  onSave?: (template: WorkflowTemplate) => Promise<void>;
  onCancel?: () => void;
  readOnly?: boolean;
}

const CATEGORIES = [
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

const COMPLEXITY_LEVELS = [
  { value: 'beginner', label: 'Beginner', color: 'bg-green-500' },
  { value: 'intermediate', label: 'Intermediate', color: 'bg-blue-500' },
  { value: 'advanced', label: 'Advanced', color: 'bg-orange-500' },
  { value: 'expert', label: 'Expert', color: 'bg-red-500' },
];

const STEP_TYPES = [
  'trigger',
  'action',
  'condition',
  'loop',
  'sub_workflow',
  'agent_execution',
  'human_input',
];

export const TemplateEditor: React.FC<TemplateEditorProps> = ({
  initialTemplate,
  onSave,
  onCancel,
  readOnly = false,
}) => {
  const { toast } = useToast();

  // Template state
  const [template, setTemplate] = useState<WorkflowTemplate>(
    initialTemplate || {
      name: '',
      description: '',
      category: 'automation',
      complexity: 'intermediate',
      tags: [],
      inputs: [],
      steps: [],
    }
  );

  const [activeTab, setActiveTab] = useState<'metadata' | 'inputs' | 'steps' | 'preview'>('metadata');
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  // Handlers
  const handleUpdateTemplate = useCallback((updates: Partial<WorkflowTemplate>) => {
    setTemplate(prev => ({ ...prev, ...updates }));
  }, []);

  const handleAddStep = useCallback(() => {
    const newStep: TemplateStep = {
      id: `step_${Date.now()}`,
      name: `Step ${template.steps.length + 1}`,
      description: '',
      step_type: 'action',
      parameters: [],
      estimated_duration: 60,
      is_optional: false,
    };

    setTemplate(prev => ({
      ...prev,
      steps: [...prev.steps, newStep],
    }));
    setSelectedStep(newStep.id);
  }, [template.steps.length]);

  const handleUpdateStep = useCallback((stepId: string, updates: Partial<TemplateStep>) => {
    setTemplate(prev => ({
      ...prev,
      steps: prev.steps.map(step =>
        step.id === stepId ? { ...step, ...updates } : step
      ),
    }));
  }, []);

  const handleDeleteStep = useCallback((stepId: string) => {
    setTemplate(prev => ({
      ...prev,
      steps: prev.steps.filter(step => step.id !== stepId),
    }));
    if (selectedStep === stepId) {
      setSelectedStep(null);
    }
  }, [selectedStep]);

  const handleMoveStep = useCallback((stepId: string, direction: 'up' | 'down') => {
    setTemplate(prev => {
      const steps = [...prev.steps];
      const index = steps.findIndex(s => s.id === stepId);

      if (direction === 'up' && index > 0) {
        [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]];
      } else if (direction === 'down' && index < steps.length - 1) {
        [steps[index], steps[index + 1]] = [steps[index + 1], steps[index]];
      }

      return { ...prev, steps };
    });
  }, []);

  const handleAddTag = useCallback((tag: string) => {
    if (tag && !template.tags.includes(tag)) {
      setTemplate(prev => ({
        ...prev,
        tags: [...prev.tags, tag],
      }));
    }
  }, [template.tags]);

  const handleRemoveTag = useCallback((tag: string) => {
    setTemplate(prev => ({
      ...prev,
      tags: prev.tags.filter(t => t !== tag),
    }));
  }, []);

  const handleSave = async () => {
    if (!template.name.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Template name is required',
        variant: 'error',
      });
      return;
    }

    if (!template.description.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Template description is required',
        variant: 'error',
      });
      return;
    }

    if (template.steps.length === 0) {
      toast({
        title: 'Validation Error',
        description: 'Template must have at least one step',
        variant: 'error',
      });
      return;
    }

    setSaving(true);
    try {
      if (onSave) {
        await onSave(template);
      }
      toast({
        title: 'Success',
        description: 'Template saved successfully',
        variant: 'default',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save template',
        variant: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = () => {
    setShowPreview(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Template Editor</h2>
          <p className="text-muted-foreground">
            Create a custom workflow template
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handlePreview}
            disabled={!template.name}
          >
            <Eye className="h-4 w-4 mr-2" />
            Preview
          </Button>
          {!readOnly && (
            <>
              <Button variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? (
                  <>
                    <Spinner className="h-4 w-4 mr-2" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save Template
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Card>
        <CardContent className="p-0">
          <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)}>
            <TabsList className="w-full justify-start rounded-b-none border-b p-0">
              <TabsTrigger value="metadata" className="data-[state=active]:bg-background">
                <Settings className="h-4 w-4 mr-2" />
                Metadata
              </TabsTrigger>
              <TabsTrigger value="inputs" className="data-[state=active]:bg-background">
                Input Parameters
              </TabsTrigger>
              <TabsTrigger value="steps" className="data-[state=active]:bg-background">
                Workflow Steps
              </TabsTrigger>
              <TabsTrigger value="preview" className="data-[state=active]:bg-background">
                <Eye className="h-4 w-4 mr-2" />
                Preview
              </TabsTrigger>
            </TabsList>

            {/* Metadata Tab */}
            <TabsContent value="metadata" className="p-6">
              <TemplateMetadataForm
                template={template}
                onUpdate={handleUpdateTemplate}
                onAddTag={handleAddTag}
                onRemoveTag={handleRemoveTag}
                readOnly={readOnly}
              />
            </TabsContent>

            {/* Inputs Tab */}
            <TabsContent value="inputs" className="p-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">Input Parameters</h3>
                    <p className="text-sm text-muted-foreground">
                      Define parameters that users will provide when using this template
                    </p>
                  </div>
                </div>

                {template.inputs.length === 0 ? (
                  <div className="text-center py-12 border-2 border-dashed rounded-lg">
                    <p className="text-muted-foreground">No input parameters defined yet</p>
                    <Button
                      variant="outline"
                      className="mt-4"
                      onClick={() => setTemplate(prev => ({ ...prev, inputs: [...prev.inputs, {
                        name: '',
                        type: 'string',
                        required: true,
                      }] }))}
                      disabled={readOnly}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Parameter
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {template.inputs.map((input, index) => (
                      <Card key={index}>
                        <CardContent className="p-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <Label>Parameter Name</Label>
                              <Input
                                value={input.name}
                                onChange={(e) => {
                                  const newInputs = [...template.inputs];
                                  newInputs[index] = { ...input, name: e.target.value };
                                  setTemplate(prev => ({ ...prev, inputs: newInputs }));
                                }}
                                disabled={readOnly}
                                placeholder="parameter_name"
                              />
                            </div>
                            <div>
                              <Label>Type</Label>
                              <Select
                                value={input.type}
                                onValueChange={(value: any) => {
                                  const newInputs = [...template.inputs];
                                  newInputs[index] = { ...input, type: value };
                                  setTemplate(prev => ({ ...prev, inputs: newInputs }));
                                }}
                                disabled={readOnly}
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="string">String</SelectItem>
                                  <SelectItem value="number">Number</SelectItem>
                                  <SelectItem value="boolean">Boolean</SelectItem>
                                  <SelectItem value="object">Object</SelectItem>
                                  <SelectItem value="array">Array</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label>Label</Label>
                              <Input
                                value={input.label || ''}
                                onChange={(e) => {
                                  const newInputs = [...template.inputs];
                                  newInputs[index] = { ...input, label: e.target.value };
                                  setTemplate(prev => ({ ...prev, inputs: newInputs }));
                                }}
                                disabled={readOnly}
                                placeholder="User-friendly label"
                              />
                            </div>
                            <div className="flex items-end">
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => {
                                  const newInputs = template.inputs.filter((_, i) => i !== index);
                                  setTemplate(prev => ({ ...prev, inputs: newInputs }));
                                }}
                                disabled={readOnly}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                          <div className="mt-3">
                            <Label>Description</Label>
                            <Textarea
                              value={input.description || ''}
                              onChange={(e) => {
                                const newInputs = [...template.inputs];
                                newInputs[index] = { ...input, description: e.target.value };
                                setTemplate(prev => ({ ...prev, inputs: newInputs }));
                              }}
                              disabled={readOnly}
                              placeholder="Describe this parameter..."
                              rows={2}
                            />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                    <Button
                      variant="outline"
                      onClick={() => setTemplate(prev => ({ ...prev, inputs: [...prev.inputs, {
                        name: '',
                        type: 'string',
                        required: true,
                    }] }))}
                      disabled={readOnly}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add Parameter
                    </Button>
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Steps Tab */}
            <TabsContent value="steps" className="p-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">Workflow Steps</h3>
                    <p className="text-sm text-muted-foreground">
                      Define the sequence of steps for this workflow
                    </p>
                  </div>
                  <Button onClick={handleAddStep} disabled={readOnly}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Step
                  </Button>
                </div>

                {template.steps.length === 0 ? (
                  <div className="text-center py-12 border-2 border-dashed rounded-lg">
                    <p className="text-muted-foreground">No workflow steps defined yet</p>
                    <Button
                      variant="outline"
                      className="mt-4"
                      onClick={handleAddStep}
                      disabled={readOnly}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Add First Step
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {template.steps.map((step, index) => (
                      <Card
                        key={step.id}
                        className={selectedStep === step.id ? 'ring-2 ring-primary' : ''}
                        onClick={() => setSelectedStep(step.id)}
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge variant="outline">{step.step_type}</Badge>
                                <span className="font-semibold">{step.name}</span>
                                {step.is_optional && (
                                  <Badge variant="secondary">Optional</Badge>
                                )}
                              </div>
                              {step.description && (
                                <p className="text-sm text-muted-foreground mb-2">
                                  {step.description}
                                </p>
                              )}
                              <div className="flex gap-2 text-xs text-muted-foreground">
                                {step.service && <span>Service: {step.service}</span>}
                                {step.action && <span>Action: {step.action}</span>}
                                {step.estimated_duration && (
                                  <span>Duration: {step.estimated_duration}s</span>
                                )}
                              </div>
                            </div>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleMoveStep(step.id, 'up');
                                }}
                                disabled={index === 0 || readOnly}
                              >
                                <ArrowUp className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleMoveStep(step.id, 'down');
                                }}
                                disabled={index === template.steps.length - 1 || readOnly}
                              >
                                <ArrowDown className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteStep(step.id);
                                }}
                                disabled={readOnly}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Preview Tab */}
            <TabsContent value="preview" className="p-6">
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold mb-4">Template Summary</h3>
                  <dl className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-sm text-muted-foreground">Name</dt>
                      <dd className="font-medium">{template.name || 'Not set'}</dd>
                    </div>
                    <div>
                      <dt className="text-sm text-muted-foreground">Category</dt>
                      <dd className="capitalize">{template.category}</dd>
                    </div>
                    <div>
                      <dt className="text-sm text-muted-foreground">Complexity</dt>
                      <dd className="capitalize">{template.complexity}</dd>
                    </div>
                    <div>
                      <dt className="text-sm text-muted-foreground">Input Parameters</dt>
                      <dd>{template.inputs.length} parameters</dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-sm text-muted-foreground">Description</dt>
                      <dd className="text-sm">{template.description || 'Not set'}</dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-sm text-muted-foreground">Tags</dt>
                      <dd className="flex gap-1 flex-wrap">
                        {template.tags.length > 0 ? (
                          template.tags.map(tag => (
                            <Badge key={tag} variant="secondary">{tag}</Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">No tags</span>
                        )}
                      </dd>
                    </div>
                  </dl>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">Workflow Steps</h4>
                  <div className="space-y-2">
                    {template.steps.map((step, index) => (
                      <div key={step.id} className="flex items-center gap-2 text-sm">
                        <Badge variant="outline">{index + 1}</Badge>
                        <span>{step.name}</span>
                        <span className="text-muted-foreground">({step.step_type})</span>
                      </div>
                    ))}
                    {template.steps.length === 0 && (
                      <p className="text-sm text-muted-foreground">No steps defined</p>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Preview Modal */}
      {showPreview && (
        <TemplatePreviewModal
          template={template}
          open={showPreview}
          onClose={() => setShowPreview(false)}
        />
      )}
    </div>
  );
};
