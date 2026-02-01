/**
 * Session Persistence Component
 *
 * Handles export/import of debug sessions for sharing and analysis.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Upload, Loader2, FileText, Check } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface SessionPersistenceProps {
  sessionId: string | null;
  workflowId: string | null;
  currentUserId: string;
  onSessionImported?: (newSessionId: string) => void;
}

export const SessionPersistence: React.FC<SessionPersistenceProps> = ({
  sessionId,
  workflowId,
  currentUserId,
  onSessionImported,
}) => {
  const { toast } = useToast();

  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [restoreBreakpoints, setRestoreBreakpoints] = useState(true);
  const [restoreVariables, setRestoreVariables] = useState(true);

  const handleExport = async () => {
    if (!sessionId) return;

    try {
      setExportLoading(true);

      const response = await fetch(`/api/workflows/debug/sessions/${sessionId}/export`);

      if (!response.ok) throw new Error('Failed to export session');

      const data = await response.json();

      // Create and download JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `debug_session_${sessionId}_${new Date().toISOString()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast({
        title: 'Session Exported',
        description: 'Debug session has been exported successfully',
      });
    } catch (err) {
      toast({
        title: 'Export Failed',
        description: 'Failed to export debug session',
        variant: 'error',
      });
    } finally {
      setExportLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importFile) return;

    try {
      setImportLoading(true);

      const text = await importFile.text();
      const exportData = JSON.parse(text);

      const response = await fetch('/api/workflows/debug/sessions/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          export_data: exportData,
          restore_breakpoints: restoreBreakpoints,
          restore_variables: restoreVariables,
        }),
      });

      if (!response.ok) throw new Error('Failed to import session');

      const result = await response.json();

      toast({
        title: 'Session Imported',
        description: `Debug session imported as ${result.session_id}`,
      });

      onSessionImported?.(result.session_id);
      setImportFile(null);
    } catch (err) {
      toast({
        title: 'Import Failed',
        description: 'Failed to import debug session. Please check the file format.',
        variant: 'error',
      });
    } finally {
      setImportLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-blue-500" />
          Session Persistence
        </CardTitle>
        <CardDescription>Export and import debug sessions</CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Export Section */}
        <div>
          <h4 className="text-sm font-medium mb-3">Export Session</h4>
          <Button
            onClick={handleExport}
            disabled={!sessionId || exportLoading}
            variant="outline"
            className="w-full"
          >
            {exportLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Export Debug Session
          </Button>
          <p className="text-xs text-muted-foreground mt-2">
            Download current session as JSON for sharing or later analysis
          </p>
        </div>

        {/* Import Section */}
        <div className="border-t pt-4">
          <h4 className="text-sm font-medium mb-3">Import Session</h4>

          {/* File Input */}
          <div>
            <Label htmlFor="import-file">Session File</Label>
            <Input
              id="import-file"
              type="file"
              accept=".json"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              className="mt-1"
            />
            {importFile && (
              <p className="text-xs text-muted-foreground mt-1">
                Selected: {importFile.name}
              </p>
            )}
          </div>

          {/* Options */}
          <div className="mt-4 space-y-2">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="restore-breakpoints"
                checked={restoreBreakpoints}
                onCheckedChange={(checked) => setRestoreBreakpoints(checked as boolean)}
              />
              <Label htmlFor="restore-breakpoints" className="text-sm">
                Restore breakpoints
              </Label>
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="restore-variables"
                checked={restoreVariables}
                onCheckedChange={(checked) => setRestoreVariables(checked as boolean)}
              />
              <Label htmlFor="restore-variables" className="text-sm">
                Restore variable state
              </Label>
            </div>
          </div>

          {/* Import Button */}
          <Button
            onClick={handleImport}
            disabled={!importFile || importLoading}
            className="w-full mt-4"
          >
            {importLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            Import Debug Session
          </Button>
        </div>

        {/* Info */}
        <div className="bg-muted p-3 rounded-lg text-xs text-muted-foreground">
          <p><strong>Tip:</strong> Exported sessions include breakpoints, traces, and variables.
          Share them with team members for collaborative debugging.</p>
        </div>
      </CardContent>
    </Card>
  );
};

export default SessionPersistence;
