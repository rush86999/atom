'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Calendar, Hash, Type, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface EntityTypeCardProps {
  entityType: {
    id: string;
    slug: string;
    display_name: string;
    description?: string;
    json_schema: Record<string, any>;
    is_system: boolean;
    version: number;
    created_at: string;
    updated_at: string;
    available_skills?: string[];
  };
  onEdit?: () => void;
}

/**
 * Format date string to readable format
 */
const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch (e) {
    return 'Unknown Date';
  }
};

/**
 * Get first few properties from JSON schema for preview
 */
const getSchemaPreview = (schema: Record<string, any>): Array<{ name: string; type: string }> => {
  if (!schema || !schema.properties) return [];

  const properties = Object.entries(schema.properties).slice(0, 3);
  return properties.map(([name, def]: [string, any]) => ({
    name,
    type: Array.isArray(def.type) ? def.type.join(' | ') : def.type || 'any',
  }));
};

/**
 * EntityTypeCard Component
 */
export const EntityTypeCard: React.FC<EntityTypeCardProps> = ({
  entityType,
  onEdit,
}) => {
  const {
    id,
    slug,
    display_name,
    description,
    json_schema,
    is_system,
    version,
    created_at,
    updated_at,
    available_skills = [],
  } = entityType;

  const schemaPreview = getSchemaPreview(json_schema);

  return (
    <Card className="bg-white/5 border-white/10 backdrop-blur-xl hover:border-white/20 transition-all">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-sm font-bold text-white truncate flex items-center gap-2">
              <Type className="w-4 h-4 text-primary flex-shrink-0" />
              {display_name}
            </CardTitle>
            <div className="flex items-center gap-2 mt-1">
              <code className="text-[10px] text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded font-mono">
                {slug}
              </code>
              <Badge
                variant="outline"
                className={cn(
                  "text-[9px] uppercase font-bold",
                  is_system
                    ? "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    : "bg-green-500/10 text-green-400 border-green-500/20"
                )}
              >
                {is_system ? 'System' : 'Custom'}
              </Badge>
              <Badge variant="outline" className="text-[9px] bg-white/5 text-muted-foreground border-white/10">
                v{version}
              </Badge>
            </div>
          </div>
          {!is_system && onEdit && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-white hover:bg-white/5"
              onClick={onEdit}
            >
              <Edit2 className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{description}</p>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Schema Preview */}
        {schemaPreview.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
              <Hash className="w-3 h-3" />
              Schema Preview
            </div>
            <div className="space-y-1">
              {schemaPreview.map((prop) => (
                <div key={prop.name} className="flex items-center gap-2 text-xs">
                  <span className="text-white font-medium">{prop.name}</span>
                  <span className="text-muted-foreground text-[10px] font-mono">: {prop.type}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Available Skills */}
        {available_skills.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
              Available Skills
            </div>
            <div className="flex flex-wrap gap-1.5">
              {available_skills.slice(0, 3).map((skillId) => (
                <Badge
                  key={skillId}
                  variant="outline"
                  className="text-[9px] bg-primary/10 text-primary border-primary/20"
                >
                  {skillId}
                </Badge>
              ))}
              {available_skills.length > 3 && (
                <Badge variant="outline" className="text-[9px] bg-white/5 text-muted-foreground border-white/10">
                  +{available_skills.length - 3} more
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="pt-2 border-t border-white/5 flex items-center gap-1 text-[10px] text-muted-foreground">
          <Calendar className="w-3 h-3" />
          <span>
            Created {formatDate(created_at)}
            {updated_at !== created_at && ` • Updated ${formatDate(updated_at)}`}
          </span>
        </div>
      </CardContent>
    </Card>
  );
};
