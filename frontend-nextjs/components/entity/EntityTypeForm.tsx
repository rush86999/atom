import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import MonacoSchemaEditor from './MonacoSchemaEditor';
import VisualSchemaBuilder from './VisualSchemaBuilder';
import { validateSchema } from '@/src/lib/validators/jsonSchema';
import { LayoutGrid, Code2, Sparkles, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EntityTypeFormProps {
  entityType?: any;
  onSuccess: (entityType: any) => void;
  onCancel: () => void;
  workspaceId: string;
}

const DEFAULT_SCHEMA = JSON.stringify({
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" }
  },
  "required": ["name"]
}, null, 2);

const EntityTypeForm: React.FC<EntityTypeFormProps> = ({
  entityType,
  onSuccess,
  onCancel,
  workspaceId
}) => {
  const [formData, setFormData] = useState({
    slug: entityType?.slug || '',
    display_name: entityType?.display_name || '',
    description: entityType?.description || '',
    json_schema: entityType?.json_schema ? JSON.stringify(entityType.json_schema, null, 2) : DEFAULT_SCHEMA,
    available_skills: entityType?.available_skills || []
  });

  const [editorMode, setEditorMode] = useState<'monaco' | 'visual'>('visual');
  const [skills, setSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [fetchLoading, setFetchLoading] = useState(true);

  const isEdit = !!entityType;

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const response = await axios.get('/api/skills', {
          headers: { 'X-Workspace-ID': workspaceId }
        });
        setSkills(response.data || []);
      } catch (error) {
        console.error('Failed to fetch skills:', error);
      } finally {
        setFetchLoading(false);
      }
    };
    fetchSkills();
  }, [workspaceId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate schema before submission
    try {
      const parsedSchema = JSON.parse(formData.json_schema);
      const validation = validateSchema(parsedSchema);
      if (!validation.valid) {
        toast.error(`Invalid Schema: ${validation.errors[0]}`);
        return;
      }
    } catch (e: any) {
      toast.error(`JSON Parse error: ${e.message}`);
      return;
    }

    setLoading(true);
    try {
      const payload = {
        ...formData,
        json_schema: JSON.parse(formData.json_schema)
      };

      let response;
      if (isEdit) {
        response = await axios.put(`/api/entity-types/${entityType.id}`, payload, {
          headers: { 'X-Workspace-ID': workspaceId }
        });
        toast.success('Entity type updated successfully');
      } else {
        response = await axios.post('/api/entity-types', payload, {
          headers: { 'X-Workspace-ID': workspaceId }
        });
        toast.success('Entity type created successfully');
      }
      onSuccess(response.data);
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Failed to save entity type';
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleAiSuggest = async () => {
    if (!formData.display_name) {
      toast.error('Please enter a Display Name first');
      return;
    }

    setSuggesting(true);
    try {
      const response = await axios.post('/api/entity-types/suggest-schema', {
        display_name: formData.display_name,
        description: formData.description
      }, {
        headers: { 'X-Workspace-ID': workspaceId }
      });

      // Handle both success structure and direct object
      const schema = response.data.success ? response.data.data : response.data;
      
      setFormData(prev => ({
        ...prev,
        json_schema: JSON.stringify(schema, null, 2)
      }));
      toast.success('Schema suggested by AI!');
    } catch (error: any) {
      toast.error('Failed to get AI suggestion');
      console.error(error);
    } finally {
      setSuggesting(false);
    }
  };

  const toggleSkill = (skillId: string) => {
    setFormData(prev => ({
      ...prev,
      available_skills: prev.available_skills.includes(skillId)
        ? prev.available_skills.filter((id: string) => id !== skillId)
        : [...prev.available_skills, skillId]
    }));
  };

  return (
    <div className="space-y-6 max-h-[80vh] overflow-y-auto pr-2 custom-scrollbar">
      <form onSubmit={handleSubmit} className="space-y-6 pb-2">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="display_name" className="text-sm font-semibold text-white/90">Display Name</Label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleAiSuggest}
                disabled={suggesting || !formData.display_name}
                className="h-6 px-2 text-[10px] font-bold gap-1.5 text-primary hover:text-primary/80 hover:bg-primary/10"
              >
                {suggesting ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                AI SUGGEST
              </Button>
            </div>
            <Input
              id="display_name"
              placeholder="e.g. Financial Transaction"
              value={formData.display_name}
              onChange={e => setFormData({ ...formData, display_name: e.target.value })}
              required
              className="bg-white/5 border-white/10 text-white focus:ring-primary/50"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="slug" className="text-sm font-semibold text-white/90">Slug</Label>
            <Input
              id="slug"
              placeholder="e.g. financial-transaction"
              value={formData.slug}
              onChange={e => setFormData({ ...formData, slug: e.target.value })}
              required
              disabled={isEdit}
              className="bg-white/5 border-white/10 text-white disabled:opacity-50"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description" className="text-sm font-semibold text-white/90">Description</Label>
          <Textarea
            id="description"
            placeholder="Describe what this entity represents..."
            value={formData.description}
            onChange={e => setFormData({ ...formData, description: e.target.value })}
            className="bg-white/5 border-white/10 text-white min-h-[80px]"
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-semibold text-white/90">Schema Definition</Label>
            <div className="flex bg-white/5 p-0.5 rounded-lg border border-white/10">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setEditorMode('visual')}
                className={cn(
                  "h-7 px-3 text-[10px] font-bold gap-1.5 rounded-md transition-all",
                  editorMode === 'visual' 
                    ? "bg-primary/20 text-primary border border-primary/30" 
                    : "text-muted-foreground hover:text-white"
                )}
              >
                <LayoutGrid className="w-3 h-3" />
                VISUAL BUILDER
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setEditorMode('monaco')}
                className={cn(
                  "h-7 px-3 text-[10px] font-bold gap-1.5 rounded-md transition-all",
                  editorMode === 'monaco' 
                    ? "bg-primary/20 text-primary border border-primary/30" 
                    : "text-muted-foreground hover:text-white"
                )}
              >
                <Code2 className="w-3 h-3" />
                CODE EDITOR
              </Button>
            </div>
          </div>

          <div className="min-h-[400px]">
            {editorMode === 'visual' ? (
              <VisualSchemaBuilder
                schema={JSON.parse(formData.json_schema || '{}')}
                onChange={newSchema => setFormData({ ...formData, json_schema: JSON.stringify(newSchema, null, 2) })}
              />
            ) : (
              <MonacoSchemaEditor
                value={formData.json_schema}
                onChange={val => setFormData({ ...formData, json_schema: val })}
              />
            )}
          </div>
        </div>

        <div className="space-y-3">
          <Label className="text-sm font-semibold text-white/90">Available Skills</Label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {fetchLoading ? (
              <div className="col-span-full text-center py-4 text-white/30 text-xs italic">Loading skills...</div>
            ) : skills.length === 0 ? (
              <div className="col-span-full text-center py-4 text-white/30 text-xs italic">No skills available</div>
            ) : (
              skills.map(skill => (
                <div 
                  key={skill.id}
                  onClick={() => toggleSkill(skill.id)}
                  className={`
                    flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all
                    ${formData.available_skills.includes(skill.id) 
                      ? 'bg-primary/20 border-primary/50 text-white shadow-[0_0_10px_rgba(var(--primary-rgb),0.1)]' 
                      : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10 hover:border-white/20'
                    }
                  `}
                >
                  <div className={`w-2 h-2 rounded-full ${formData.available_skills.includes(skill.id) ? 'bg-primary animate-pulse' : 'bg-white/20'}`} />
                  <span className="text-[11px] font-medium truncate">{skill.name}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-4 sticky bottom-0 bg-zinc-900 pb-2 border-t border-white/10">
          <Button 
            type="button" 
            variant="ghost" 
            onClick={onCancel}
            className="text-white/60 hover:text-white hover:bg-white/5"
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            disabled={loading}
            className="bg-primary hover:bg-primary/90 text-white px-8"
          >
            {loading ? 'Saving...' : (isEdit ? 'Update Type' : 'Create Type')}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default EntityTypeForm;
