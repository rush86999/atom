'use client';

import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import axios from 'axios';
import { toast } from 'sonner';
import { EntityTypeCard } from './EntityTypeCard';
import { Loader2, Search, AlertCircle, Type, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EntityType {
  id: string;
  tenant_id: string;
  slug: string;
  display_name: string;
  description?: string;
  json_schema: Record<string, any>;
  available_skills: string[];
  is_active: boolean;
  is_system: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

interface EntityTypeListProps {
  refreshTrigger?: number;
  onSkillToggle?: (entityTypeId: string, skillId: string, enabled: boolean) => void;
}

/**
 * EntityTypeList Component
 */
export const EntityTypeList: React.FC<EntityTypeListProps> = ({
  refreshTrigger,
  onSkillToggle,
}) => {
  const { data: session } = useSession();
  const [entityTypes, setEntityTypes] = useState<EntityType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filterSystem, setFilterSystem] = useState(false);

  const workspaceId = (session as any)?.user?.workspace_id || 'default';

  const fetchEntityTypes = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get('/api/entity-types', {
        params: {
          workspace_id: workspaceId,
          include_system: filterSystem,
        },
      });

      // Handle both success structure and direct array
      const data = response.data.success ? response.data.data : response.data;
      setEntityTypes(Array.isArray(data) ? data : (data.entity_types || []));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch entity types';
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntityTypes();
  }, [refreshTrigger, filterSystem, workspaceId]);

  const filteredEntityTypes = React.useMemo(() => {
    if (!search) return entityTypes;

    const searchLower = search.toLowerCase();
    return entityTypes.filter((et) => {
      return (
        et.display_name.toLowerCase().includes(searchLower) ||
        et.slug.toLowerCase().includes(searchLower) ||
        et.description?.toLowerCase().includes(searchLower)
      );
    });
  }, [entityTypes, search]);

  const handleClearFilters = () => {
    setSearch('');
    setFilterSystem(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 items-center bg-white/5 p-4 rounded-xl border border-white/5">
        <div className="flex-1 relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search entity types by name or slug..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm text-white placeholder:text-muted-foreground"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-white cursor-pointer">
          <input
            type="checkbox"
            checked={filterSystem}
            onChange={(e) => setFilterSystem(e.target.checked)}
            className="w-4 h-4 rounded border-white/20 bg-white/5 text-primary focus:ring-primary focus:ring-offset-0"
          />
          <span>Include System Types</span>
        </label>

        {(search || filterSystem) && (
          <button
            onClick={handleClearFilters}
            className="px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-muted-foreground hover:text-white hover:bg-white/10 transition-colors"
          >
            Clear Filters
          </button>
        )}

        <button
          onClick={fetchEntityTypes}
          disabled={loading}
          className="p-2 bg-white/5 border border-white/10 rounded-lg text-muted-foreground hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
          title="Refresh entity types"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredEntityTypes.length} of {entityTypes.length} entity type
        {entityTypes.length !== 1 ? 's' : ''}
      </div>

      {loading && entityTypes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground">Loading entity types...</p>
        </div>
      )}

      {error && !loading && (
        <div className="flex items-start gap-2 p-4 bg-red-500/10 border border-red-500/20 rounded-md">
          <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-red-400 font-medium">Error Loading Entity Types</p>
            <p className="text-sm text-red-400 mt-1">{error}</p>
          </div>
          <button
            onClick={fetchEntityTypes}
            className="px-3 py-1 text-sm bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && entityTypes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Type className="w-12 h-12 text-muted-foreground mb-3" />
          <p className="text-lg font-medium text-white mb-2">No Entity Types Found</p>
          <p className="text-sm text-muted-foreground max-w-md">
            No custom entity types found. Create your first entity type to get started.
          </p>
        </div>
      )}

      {!loading && !error && filteredEntityTypes.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredEntityTypes.map((entityType) => (
            <EntityTypeCard
              key={entityType.id}
              id={entityType.id}
              slug={entityType.slug}
              display_name={entityType.display_name}
              description={entityType.description}
              json_schema={entityType.json_schema}
              is_system={entityType.is_system}
              version={entityType.version}
              created_at={entityType.created_at}
              updated_at={entityType.updated_at}
              available_skills={entityType.available_skills}
            />
          ))}
        </div>
      )}
    </div>
  );
};
