/**
 * Variable Modifier Component
 *
 * Allows modifying variable values during debugging.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Edit2, Check, X, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface Variable {
  variable_id: string;
  variable_name: string;
  variable_path: string;
  variable_type: string;
  value: any;
  value_preview: string;
  scope: string;
  is_mutable: boolean;
  is_changed: boolean;
  previous_value: any;
}

interface VariableModifierProps {
  sessionId: string | null;
  currentUserId: string;
  onVariableModified?: (variable: Variable) => void;
}

export const VariableModifier: React.FC<VariableModifierProps> = ({
  sessionId,
  currentUserId,
  onVariableModified,
}) => {
  const { toast } = useToast();

  const [selectedVariable, setSelectedVariable] = useState<Variable | null>(null);
  const [newValue, setNewValue] = useState<string>('');
  const [scope, setScope] = useState<string>('local');
  const [loading, setLoading] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);

  const handleModify = async () => {
    if (!selectedVariable || !sessionId) return;

    try {
      setLoading(true);

      // Parse new value based on type
      let parsedValue: any = newValue;
      if (selectedVariable.variable_type === 'number') {
        parsedValue = parseFloat(newValue);
      } else if (selectedVariable.variable_type === 'boolean') {
        parsedValue = newValue === 'true';
      } else if (selectedVariable.variable_type === 'object' || selectedVariable.variable_type === 'array') {
        parsedValue = JSON.parse(newValue);
      }

      const response = await fetch('/api/workflows/debug/variables/modify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          variable_name: selectedVariable.variable_name,
          new_value: parsedValue,
          scope: scope,
        }),
      });

      if (!response.ok) throw new Error('Failed to modify variable');

      const result = await response.json();

      toast({
        title: 'Variable Modified',
        description: `Changed ${selectedVariable.variable_name} to ${newValue}`,
      });

      onVariableModified?.(result.variable);
      setShowEditForm(false);
      setSelectedVariable(null);
      setNewValue('');
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to modify variable',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setShowEditForm(false);
    setSelectedVariable(null);
    setNewValue('');
  };

  if (!showEditForm) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowEditForm(true)}
        disabled={!sessionId}
      >
        <Edit2 className="h-4 w-4 mr-2" />
        Modify Variable
      </Button>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Edit2 className="h-5 w-5 text-orange-500" />
          Modify Variable
        </CardTitle>
        <CardDescription>Change variable values at runtime</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Variable Name */}
        <div>
          <Label htmlFor="variable-name">Variable Name</Label>
          <Input
            id="variable-name"
            placeholder="e.g., user_name, counter, config.max_retries"
            value={selectedVariable?.variable_name || newValue}
            onChange={(e) => setNewValue(e.target.value)}
          />
        </div>

        {/* Variable Type */}
        <div>
          <Label htmlFor="variable-type">Type</Label>
          <Select
            value={selectedVariable?.variable_type || 'string'}
            onValueChange={(value) => setSelectedVariable({
              variable_id: '',
              variable_name: newValue,
              variable_path: newValue,
              variable_type: value,
              value: null,
              value_preview: '',
              scope: scope,
              is_mutable: true,
              is_changed: false,
              previous_value: null,
            } as Variable)}
          >
            <SelectTrigger id="variable-type">
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="string">String</SelectItem>
              <SelectItem value="number">Number</SelectItem>
              <SelectItem value="boolean">Boolean</SelectItem>
              <SelectItem value="object">Object (JSON)</SelectItem>
              <SelectItem value="array">Array (JSON)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* New Value */}
        <div>
          <Label htmlFor="new-value">New Value</Label>
          {selectedVariable?.variable_type === 'object' || selectedVariable?.variable_type === 'array' ? (
            <textarea
              id="new-value"
              className="w-full p-2 border rounded-md font-mono text-sm"
              rows={5}
              placeholder='{"key": "value"}'
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
            />
          ) : (
            <Input
              id="new-value"
              placeholder="Enter new value"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
            />
          )}
        </div>

        {/* Scope */}
        <div>
          <Label htmlFor="scope">Scope</Label>
          <Select value={scope} onValueChange={setScope}>
            <SelectTrigger id="scope">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="local">Local</SelectItem>
              <SelectItem value="global">Global</SelectItem>
              <SelectItem value="workflow">Workflow</SelectItem>
              <SelectItem value="context">Context</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            onClick={handleModify}
            disabled={!newValue || loading}
            className="flex-1"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            Apply Change
          </Button>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={loading}
          >
            <X className="h-4 w-4 mr-2" />
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default VariableModifier;
