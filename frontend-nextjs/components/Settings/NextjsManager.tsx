/**
 * Next.js Integration Settings Component
 * Settings UI for Next.js/Vercel integration
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useToast } from '@/components/ui/use-toast';
import { Code, CheckCircle, AlertTriangle, ArrowRight, Settings, RefreshCw, Loader2 } from 'lucide-react';

interface NextjsSettingsProps {
  atomIngestionPipeline?: any;
  onConfigurationChange?: (config: any) => void;
  onIngestionComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

export const NextjsSettings: React.FC<NextjsSettingsProps> = ({
  atomIngestionPipeline,
  onConfigurationChange,
  onIngestionComplete,
  onError,
}) => {
  const [health, setHealth] = useState<{ connected: boolean; errors: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [showIntegration, setShowIntegration] = useState(false);
  const { toast } = useToast();

  // Check Next.js integration health
  const checkHealth = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/nextjs/health');
      const data = await response.json();

      if (data.services?.nextjs) {
        setHealth({
          connected: data.services.nextjs.status === 'healthy',
          errors: data.services.nextjs.error ? [data.services.nextjs.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        errors: ['Failed to check Next.js service health']
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Code className="w-6 h-6 text-blue-500" />
            <CardTitle>Next.js Integration</CardTitle>
            <Badge variant="secondary">Vercel</Badge>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={health?.connected ? 'default' : 'destructive'} className="flex items-center gap-1">
              {health?.connected ? (
                <CheckCircle className="w-3 h-3" />
              ) : (
                <AlertTriangle className="w-3 h-3" />
              )}
              {health?.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={checkHealth}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-1" />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Integration Overview */}
        <div className="space-y-3">
          <p className="text-muted-foreground">
            Connect your Vercel account to manage Next.js projects, deployments, and analytics directly from ATOM.
            This integration provides real-time monitoring of your applications and automated data ingestion.
          </p>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => window.open('https://vercel.com', '_blank')}
            >
              <ArrowRight className="w-4 h-4 mr-2" />
              Visit Vercel
            </Button>
            <Button
              onClick={() => setShowIntegration(!showIntegration)}
            >
              <Settings className="w-4 h-4 mr-2" />
              {showIntegration ? 'Hide Integration' : 'Configure Integration'}
            </Button>
          </div>
        </div>

        <hr />

        {/* Health Status */}
        {health && (
          <Alert variant={health.connected ? 'default' : 'destructive'}>
            {health.connected ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <AlertTriangle className="h-4 w-4" />
            )}
            <AlertTitle>
              Next.js service {health.connected ? 'healthy' : 'unhealthy'}
            </AlertTitle>
            {health.errors.length > 0 && (
              <AlertDescription className="text-red-500">
                {health.errors.join(', ')}
              </AlertDescription>
            )}
          </Alert>
        )}

        {/* Features Overview */}
        <div className="space-y-3">
          <p className="font-bold">Features Available:</p>
          <ul className="space-y-2 pl-4 text-sm text-muted-foreground">
            <li>📊 Real-time project analytics and monitoring</li>
            <li>🚀 Deployment tracking and status updates</li>
            <li>🔧 Build history and log access</li>
            <li>🌐 Environment variable management</li>
            <li>📈 Performance metrics and insights</li>
            <li>🔔 Automated alerts and notifications</li>
          </ul>
        </div>

        {/* Integration Component */}
        {showIntegration && (
          <>
            <hr />
            <div className="p-4 bg-muted rounded-lg">
              <p className="text-center text-muted-foreground">
                Next.js integration configuration panel will be loaded here.
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default NextjsSettings;