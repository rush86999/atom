import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Badge } from '@/components/ui/badge';

const GitHubManager = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const [apiKey, setApiKey] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const { toast } = useToast();

    useEffect(() => {
        const checkConnection = async () => {
            try {
                const response = await fetch('/api/integrations/credentials?service=github');
                const data = await response.json();
                if (data.isConnected) {
                    setIsConnected(true);
                    setApiKey('********');
                }
            } catch (error) {
                console.error('Error checking GitHub connection:', error);
            } finally {
                setIsLoading(false);
            }
        };
        if (userId) checkConnection();
    }, [userId]);

    const handleSaveApiKey = async () => {
        if (!apiKey.trim()) return;
        try {
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: 'github', secret: apiKey }),
            });
            if (response.ok) {
                setIsConnected(true);
                setApiKey('********');
                toast({ title: 'GitHub API Key saved successfully.', variant: 'success' });
            } else {
                toast({ title: 'Failed to save GitHub API Key.', variant: 'error' });
            }
        } catch (error) {
            toast({ title: 'Error connecting to the server.', variant: 'error' });
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex justify-between items-center">
                    <CardTitle>GitHub Integration</CardTitle>
                    <Badge variant={isConnected ? 'default' : 'secondary'}>
                        {isConnected ? 'Connected' : 'Not Connected'}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid gap-2">
                    <Label htmlFor="githubApiKey">Personal Access Token</Label>
                    <Input
                        id="githubApiKey"
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="Enter GitHub Personal Access Token"
                    />
                    <p className="text-xs text-muted-foreground">
                        Your token is used to access repositories and manage issues on your behalf.
                    </p>
                </div>
                <Button onClick={handleSaveApiKey} disabled={isLoading}>
                    {isConnected ? 'Update Token' : 'Save Token'}
                </Button>
            </CardContent>
        </Card>
    );
};

export default GitHubManager;
