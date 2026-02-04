/**
 * Variable Inspector Component
 *
 * Inspects and displays variable values at different execution points.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, Eye, EyeOff, RefreshCw, Plus } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface DebugVariable {
  variable_id: string;
  variable_name: string;
  variable_path: string;
  variable_type: string;
  value: any;
  value_preview: string;
  is_mutable: boolean;
  scope: string;
  is_changed: boolean;
  previous_value: any;
  is_watch: boolean;
}

interface VariableInspectorProps {
  sessionId: string | null;
  traceId?: string | null;
  workflowId: string;
  currentUserId: string;
}

export const VariableInspector: React.FC<VariableInspectorProps> = ({
  sessionId,
  traceId,
  workflowId,
  currentUserId,
}) => {
  const { toast } = useToast();

  const [variables, setVariables] = useState<DebugVariable[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showChangedOnly, setShowChangedOnly] = useState(false);

  useEffect(() => {
    if (sessionId) {
      fetchVariables();
    }
  }, [sessionId, traceId]);

  const fetchVariables = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      const endpoint = traceId
        ? `/api/workflows/debug/traces/${traceId}/variables`
        : `/api/workflows/debug/sessions/${sessionId}/variables`;

      const response = await fetch(endpoint);

      if (response.ok) {
        const data = await response.json();
        setVariables(data);
      }
    } catch (err) {
      console.error('Error fetching variables:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredVariables = variables.filter((v) => {
    const matchesSearch =
      !searchTerm ||
      v.variable_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      v.variable_path.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesChanged = !showChangedOnly || v.is_changed;

    return matchesSearch && matchesChanged;
  });

  const formatValue = (variable: DebugVariable) => {
    if (variable.value === null) return 'null';
    if (variable.value === undefined) return 'undefined';
    if (variable.value_preview) return variable.value_preview;

    const type = variable.variable_type;
    if (type === 'string' && typeof variable.value === 'string') {
      return `"${variable.value}"`;
    }
    if (type === 'boolean') {
      return variable.value ? 'true' : 'false';
    }

    return JSON.stringify(variable.value, null, 2);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-purple-500" />
              Variables
            </CardTitle>
            <CardDescription>
              {variables.length} variable{variables.length !== 1 ? 's' : ''}
            </CardDescription>
          </div>

          <Button variant="outline" size="sm" onClick={fetchVariables} disabled={!sessionId || loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Search and Filter */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search variables..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8"
            />
          </div>

          <Button
            variant={showChangedOnly ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowChangedOnly(!showChangedOnly)}
          >
            {showChangedOnly ? <Eye className="h-4 w-4 mr-2" /> : <EyeOff className="h-4 w-4 mr-2" />}
            Changed Only
          </Button>
        </div>

        {/* Variables List */}
        {loading ? (
          <div className="text-center py-4 text-muted-foreground">Loading variables...</div>
        ) : !sessionId ? (
          <div className="text-center py-8 text-muted-foreground">
            <Eye className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Start a debug session to inspect variables</p>
          </div>
        ) : filteredVariables.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No variables found</p>
          </div>
        ) : (
          <ScrollArea className="h-[400px]">
            <div className="space-y-2">
              {filteredVariables.map((v) => (
                <div
                  key={v.variable_id}
                  className={`p-3 border rounded-lg ${
                    v.is_changed ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-sm">{v.variable_name}</p>
                      <p className="text-xs text-muted-foreground">{v.variable_path}</p>
                    </div>

                    <div className="flex items-center gap-1">
                      <Badge variant="secondary" className="text-xs">
                        {v.scope}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {v.variable_type}
                      </Badge>
                      {v.is_watch && (
                        <Badge variant="default" className="text-xs">
                          <Plus className="h-3 w-3 mr-1" />
                          Watch
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="bg-muted p-2 rounded font-mono text-xs">
                    {formatValue(v)}
                  </div>

                  {v.is_changed && v.previous_value !== undefined && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      Previous: {JSON.stringify(v.previous_value)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
};

export default VariableInspector;
