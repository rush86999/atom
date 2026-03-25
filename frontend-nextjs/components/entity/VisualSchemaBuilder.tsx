import React, { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Plus, 
  Trash2, 
  Settings2, 
  GripVertical, 
  Type, 
  Hash, 
  CheckSquare, 
  Layers, 
  ChevronRight,
  Eye,
  ChevronDown
} from 'lucide-react';
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { FieldConfig, fieldsToSchema, schemaToFields } from '@/src/lib/schema/jsonSchemaToForm';
import { cn } from '@/lib/utils';
import { motion, Reorder, AnimatePresence } from 'framer-motion';

interface VisualSchemaBuilderProps {
  schema: any;
  onChange: (schema: any) => void;
}

const FIELD_TYPES = [
  { type: 'string', label: 'Text', icon: <Type className="w-3.5 h-3.5" />, color: 'text-blue-400' },
  { type: 'number', label: 'Number', icon: <Hash className="w-3.5 h-3.5" />, color: 'text-emerald-400' },
  { type: 'boolean', label: 'Boolean', icon: <CheckSquare className="w-3.5 h-3.5" />, color: 'text-amber-400' },
  { type: 'array', label: 'List', icon: <Layers className="w-3.5 h-3.5" />, color: 'text-purple-400' },
  { type: 'object', label: 'Object', icon: <ChevronRight className="w-3.5 h-3.5" />, color: 'text-pink-400' },
];

const FieldEditor: React.FC<{
  field: FieldConfig;
  onUpdate: (updates: Partial<FieldConfig>) => void;
  onRemove: () => void;
  isEditing: boolean;
  onToggleEdit: () => void;
  depth?: number;
}> = ({ field, onUpdate, onRemove, isEditing, onToggleEdit, depth = 0 }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const handleAddNestedField = (type: string) => {
    const newField: FieldConfig = {
      name: `field_${(field.properties?.length || 0) + 1}`,
      type,
      required: false,
      title: `Field ${(field.properties?.length || 0) + 1}`,
    };
    if (type === 'object') newField.properties = [];
    if (type === 'array') newField.items = { type: 'string' };
    
    onUpdate({
      properties: [...(field.properties || []), newField]
    });
  };

  return (
    <div className={cn(
      "p-3 bg-white/5 border rounded-lg transition-all group",
      isEditing ? "border-primary/50 shadow-[0_0_15px_rgba(var(--primary-rgb),0.1)]" : "border-white/10"
    )}>
      <div className="flex items-center gap-3">
        {depth === 0 && <GripVertical className="w-4 h-4 text-white/20 cursor-grab active:cursor-grabbing" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white truncate">{field.title || field.name}</span>
            <Badge variant="outline" className="text-[9px] bg-white/5 text-muted-foreground h-4 capitalize">
              {field.type}
            </Badge>
            {field.required && (
              <Badge className="text-[8px] bg-red-500/10 text-red-400 border-red-500/20 h-4 px-1 font-black">REQ</Badge>
            )}
          </div>
          <code className="text-[10px] text-white/40 font-mono italic">{field.name}</code>
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-white/40 hover:text-white"
            onClick={onToggleEdit}
          >
            <Settings2 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-white/40 hover:text-red-400"
            onClick={onRemove}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      <AnimatePresence>
        {isEditing && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-3 pt-3 border-t border-white/5 space-y-4"
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">Internal Name (Slug)</Label>
                <Input 
                  value={field.name}
                  onChange={e => onUpdate({ name: e.target.value })}
                  className="h-7 text-xs bg-black/40 border-white/10"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">Display Label</Label>
                <Input 
                  value={field.title}
                  onChange={e => onUpdate({ title: e.target.value })}
                  className="h-7 text-xs bg-black/40 border-white/10"
                />
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <input 
                  type="checkbox" 
                  checked={field.required}
                  onChange={e => onUpdate({ required: e.target.checked })}
                  className="w-3.5 h-3.5 rounded border-white/20 bg-black/40"
                />
                <Label className="text-xs text-white/80">Required</Label>
              </div>

              {field.type === 'array' && (
                <div className="flex items-center gap-2 ml-auto">
                  <Label className="text-[10px] text-muted-foreground">Item Type:</Label>
                  <Select 
                    value={field.items?.type || 'string'} 
                    onValueChange={val => onUpdate({ items: { ...field.items, type: val } })}
                  >
                    <SelectTrigger className="h-6 w-24 text-[10px] bg-black/40 border-white/10 uppercase font-bold">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-white/10 text-white">
                      {['string', 'number', 'boolean', 'object'].map(t => (
                        <SelectItem key={t} value={t} className="text-[10px] uppercase font-bold">{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            {field.type === 'object' && (
              <div className="pt-2 border-t border-white/5">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 cursor-pointer" onClick={() => setIsExpanded(!isExpanded)}>
                    <ChevronDown className={cn("w-3 h-3 text-white/40 transition-transform", !isExpanded && "-rotate-90")} />
                    <span className="text-[10px] font-black text-white/40 uppercase tracking-widest">Nested Properties</span>
                  </div>
                  <div className="flex gap-1">
                    {FIELD_TYPES.filter(t => t.type !== 'object').map(ft => (
                      <Button
                        key={ft.type}
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5 text-[9px] hover:text-white"
                        onClick={() => handleAddNestedField(ft.type)}
                        title={`Add ${ft.label}`}
                      >
                        {ft.icon}
                      </Button>
                    ))}
                  </div>
                </div>
                
                {isExpanded && (
                  <div className="space-y-2 pl-4 border-l border-white/10">
                    {field.properties?.map((nestedField: FieldConfig, nIdx: number) => (
                      <FieldEditor 
                        key={nIdx}
                        field={nestedField}
                        depth={depth + 1}
                        isEditing={false} // Simplified nesting for now
                        onToggleEdit={() => {}}
                        onRemove={() => {
                          const props = [...(field.properties || [])];
                          props.splice(nIdx, 1);
                          onUpdate({ properties: props });
                        }}
                        onUpdate={(updates: Partial<FieldConfig>) => {
                          const props = [...(field.properties || [])];
                          props[nIdx] = { ...props[nIdx], ...updates };
                          onUpdate({ properties: props });
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const VisualSchemaBuilder: React.FC<VisualSchemaBuilderProps> = ({
  schema,
  onChange
}) => {
  const [fields, setFields] = useState<FieldConfig[]>([]);
  const [editingFieldIdx, setEditingFieldIdx] = useState<number | null>(null);

  useEffect(() => {
    try {
      if (schema && typeof schema === 'object') {
        const extractedFields = schemaToFields(schema);
        setFields(extractedFields);
      }
    } catch (e) {
      console.error('Failed to parse schema for visual builder:', e);
    }
  }, [schema]);

  const currentSchema = useMemo(() => fieldsToSchema(fields), [fields]);

  const handleAddField = (type: string) => {
    const newField: FieldConfig = {
      name: `field_${fields.length + 1}`,
      type,
      required: false,
      title: `Field ${fields.length + 1}`,
    };

    if (type === 'array') newField.items = { type: 'string' };
    if (type === 'object') newField.properties = [];

    const newFields = [...fields, newField];
    setFields(newFields);
    onChange(fieldsToSchema(newFields));
  };

  return (
    <div className="grid grid-cols-12 gap-4 h-[600px] bg-zinc-950/20 rounded-xl border border-white/5 p-2 overflow-hidden">
      {/* Palette Column */}
      <div className="col-span-2 flex flex-col gap-2 p-2 border-r border-white/5">
        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 text-center">Constructors</span>
        {FIELD_TYPES.map(ft => (
          <Button
            key={ft.type}
            variant="ghost"
            className="justify-start gap-2 bg-white/5 hover:bg-white/10 text-xs px-2 py-1.5 h-auto border border-transparent hover:border-white/10"
            onClick={() => handleAddField(ft.type)}
          >
            <span className={ft.color}>{ft.icon}</span>
            {ft.label}
          </Button>
        ))}
      </div>

      {/* Canvas Column */}
      <div className="col-span-10 lg:col-span-5 flex flex-col gap-2 p-2 border-r border-white/5 overflow-y-auto custom-scrollbar">
        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Editor Canvas</span>
        {fields.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 border-2 border-dashed border-white/5 rounded-xl opacity-40">
            <Plus className="w-8 h-8 mb-2" />
            <p className="text-[10px]">Add field to start building</p>
          </div>
        ) : (
          <Reorder.Group axis="y" values={fields} onReorder={(newFields) => {
            setFields(newFields);
            onChange(fieldsToSchema(newFields));
          }} className="space-y-2">
            {fields.map((field, idx) => (
              <Reorder.Item key={field.name + idx} value={field}>
                <FieldEditor 
                  field={field}
                  isEditing={editingFieldIdx === idx}
                  onToggleEdit={() => setEditingFieldIdx(editingFieldIdx === idx ? null : idx)}
                  onRemove={() => {
                    const newFields = fields.filter((_, i) => i !== idx);
                    setFields(newFields);
                    onChange(fieldsToSchema(newFields));
                    if (editingFieldIdx === idx) setEditingFieldIdx(null);
                  }}
                  onUpdate={(updates) => {
                    const newFields = [...fields];
                    newFields[idx] = { ...newFields[idx], ...updates };
                    setFields(newFields);
                    onChange(fieldsToSchema(newFields));
                  }}
                />
              </Reorder.Item>
            ))}
          </Reorder.Group>
        )}
      </div>

      {/* Preview Column */}
      <div className="hidden lg:col-span-5 lg:flex flex-col gap-2 p-2 bg-black/20 overflow-y-auto custom-scrollbar rounded-r-xl">
        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
          <Eye className="w-3 h-3" /> Preview
        </span>
        
        <div className="rjsf-preview text-white px-2">
          <Form
            schema={currentSchema as any}
            validator={validator}
            children={true}
            uiSchema={{
              "ui:submitButtonOptions": { "norender": true },
              "ui:rootFieldId": "preview",
              "*": { "ui:classNames": "rjsf-custom-field" }
            }}
          />
        </div>

        <style jsx global>{`
          .rjsf-preview .form-group { margin-bottom: 0.75rem; }
          .rjsf-preview .control-label { font-size: 0.7rem; font-weight: 600; color: rgba(255,255,255,0.6); margin-bottom: 0.25rem; display: block; }
          .rjsf-preview input, .rjsf-preview textarea, .rjsf-preview select { 
            width: 100%; 
            background: rgba(255,255,255,0.03); 
            border: 1px solid rgba(255,255,255,0.1); 
            border-radius: 0.375rem; 
            padding: 0.375rem; 
            font-size: 0.75rem; 
            color: white;
            outline: none;
          }
          .rjsf-preview fieldset { border: none; padding: 0; margin: 0; }
          .rjsf-preview .help-block { font-size: 0.6rem; color: rgba(255,255,255,0.4); margin-top: 0.125rem; }
        `}</style>
      </div>
    </div>
  );
};

export default VisualSchemaBuilder;
