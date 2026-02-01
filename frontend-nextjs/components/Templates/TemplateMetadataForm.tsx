/**
 * Template Metadata Form Component
 * Form for editing template metadata (name, description, category, complexity, tags)
 */

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, Plus } from 'lucide-react';

export interface TemplateMetadata {
  name: string;
  description: string;
  category: string;
  complexity: string;
  tags: string[];
}

interface TemplateMetadataFormProps {
  metadata: TemplateMetadata;
  onChange: (metadata: TemplateMetadata) => void;
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

const SUGGESTED_TAGS = [
  'automation', 'integration', 'data', 'api', 'webhook',
  'notification', 'email', 'slack', 'crm', 'marketing',
  'analytics', 'reporting', 'monitoring', 'ai', 'ml'
];

export const TemplateMetadataForm: React.FC<TemplateMetadataFormProps> = ({
  metadata,
  onChange,
  readOnly = false,
}) => {
  const [tagInput, setTagInput] = useState('');

  const handleAddTag = useCallback(() => {
    if (tagInput && !metadata.tags.includes(tagInput)) {
      onChange({
        ...metadata,
        tags: [...metadata.tags, tagInput.toLowerCase()],
      });
      setTagInput('');
    }
  }, [tagInput, metadata, onChange]);

  const handleRemoveTag = useCallback((tag: string) => {
    onChange({
      ...metadata,
      tags: metadata.tags.filter(t => t !== tag),
    });
  }, [metadata, onChange]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  }, [handleAddTag]);

  return (
    <div className="space-y-6">
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="template-name">Template Name *</Label>
        <Input
          id="template-name"
          value={metadata.name}
          onChange={(e) => onChange({ ...metadata, name: e.target.value })}
          placeholder="e.g., Slack Notification on New Lead"
          disabled={readOnly}
          required
        />
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="template-description">Description *</Label>
        <Textarea
          id="template-description"
          value={metadata.description}
          onChange={(e) => onChange({ ...metadata, description: e.target.value })}
          placeholder="Describe what this template does and when to use it..."
          rows={4}
          disabled={readOnly}
          required
        />
      </div>

      {/* Category & Complexity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="template-category">Category *</Label>
          <Select
            value={metadata.category}
            onValueChange={(value) => onChange({ ...metadata, category: value })}
            disabled={readOnly}
          >
            <SelectTrigger id="template-category">
              <SelectValue placeholder="Select category" />
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

        <div className="space-y-2">
          <Label htmlFor="template-complexity">Complexity *</Label>
          <Select
            value={metadata.complexity}
            onValueChange={(value) => onChange({ ...metadata, complexity: value })}
            disabled={readOnly}
          >
            <SelectTrigger id="template-complexity">
              <SelectValue placeholder="Select complexity" />
            </SelectTrigger>
            <SelectContent>
              {COMPLEXITY_LEVELS.map((level) => (
                <SelectItem key={level.value} value={level.value}>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${level.color}`} />
                    {level.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Tags */}
      <div className="space-y-2">
        <Label htmlFor="template-tags">Tags</Label>
        {!readOnly && (
          <div className="flex gap-2">
            <Input
              id="template-tags"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Add a tag..."
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={handleAddTag}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Tag List */}
        {metadata.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {metadata.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                {tag}
                {!readOnly && (
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </Badge>
            ))}
          </div>
        )}

        {/* Suggested Tags */}
        {!readOnly && (
          <div className="mt-3">
            <p className="text-sm text-muted-foreground mb-2">Suggested tags:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_TAGS.filter(tag => !metadata.tags.includes(tag)).slice(0, 8).map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => onChange({
                    ...metadata,
                    tags: [...metadata.tags, tag],
                  })}
                  className="text-xs px-2 py-1 border rounded hover:bg-muted"
                >
                  + {tag}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Preview Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Preview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div>
            <span className="font-semibold">{metadata.name || 'Untitled Template'}</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">
              {CATEGORIES.find(c => c.value === metadata.category)?.label || metadata.category}
            </Badge>
            <Badge variant="outline" className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${
                COMPLEXITY_LEVELS.find(l => l.value === metadata.complexity)?.color
              }`} />
              {COMPLEXITY_LEVELS.find(l => l.value === metadata.complexity)?.label || metadata.complexity}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground line-clamp-2">
            {metadata.description || 'No description'}
          </p>
          {metadata.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {metadata.tags.slice(0, 5).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {metadata.tags.length > 5 && (
                <Badge variant="secondary" className="text-xs">
                  +{metadata.tags.length - 5}
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TemplateMetadataForm;
