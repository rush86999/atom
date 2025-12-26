import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';

interface GitLabUser {
    id: string;
    name: string;
    username: string;
    avatar_url: string;
}

interface GitLabStatus {
    connected: boolean;
    loading: boolean;
    error: string | null;
    user: GitLabUser | null;
    repositories: any[];
    issues: any[];
    mergeRequests: any[];
}

const GitLabManager: React.FC = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();
    const router = useRouter();

    const [gitlabStatus, setGitlabStatus] = useState<GitLabStatus>({
        connected: false,
        loading: false,
        error: null,
        user: null,
        repositories: [],
        issues: [],
        mergeRequests: []
    });

    const fetchConnectionStatus = useCallback(async () => {
        if (!userId) return;
        setGitlabStatus(prev => ({ ...prev, loading: true, error: null }));

        try {
            const response = await fetch(`/api/v1/users/${userId}/services`);
            const data = await response.json();

            if (data.success && data.connected_services.includes('gitlab')) {
                const serviceInfo = data.service_info.gitlab;
                setGitlabStatus(prev => ({
                    ...prev,
                    connected: true,
                    user: serviceInfo.user,
                    loading: false
                }));
            } else {
                setGitlabStatus(prev => ({ ...prev, connected: false, loading: false }));
            }
        } catch (error) {
            console.error('GitLab connection check error:', error);
            setGitlabStatus(prev => ({
                ...prev,
                loading: false,
                error: 'Failed to check GitLab connection'
            }));
        }
    }, [userId]);

    useEffect(() => {
        if (userId) fetchConnectionStatus();
    }, [userId, fetchConnectionStatus]);

    const connectGitLab = async () => {
        if (!userId) return;
        window.location.href = `/api/auth/gitlab/authorize?user_id=${userId}`;
    };

    const disconnectGitLab = async () => {
        if (!userId) return;
        setGitlabStatus(prev => ({ ...prev, loading: true }));
        try {
            const response = await fetch(`/api/v1/users/${userId}/services/gitlab`, {
                method: 'DELETE'
            });
            if (response.ok) {
                setGitlabStatus({
                    connected: false,
                    loading: false,
                    error: null,
                    user: null,
                    repositories: [],
                    issues: [],
                    mergeRequests: []
                });
                toast({ title: 'GitLab disconnected', variant: 'success' });
            } else {
                throw new Error('Failed to disconnect');
            }
        } catch (error: any) {
            setGitlabStatus(prev => ({ ...prev, loading: false, error: error.message }));
            toast({ title: 'Error disconnecting GitLab', variant: 'error' });
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex justify-between items-center">
                    <CardTitle>🦊 GitLab Integration</CardTitle>
                    <Badge variant={gitlabStatus.connected ? 'default' : 'secondary'}>
                        {gitlabStatus.connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {!gitlabStatus.connected ? (
                    <div className="flex flex-col items-center py-6 text-center space-y-4">
                        <p className="text-muted-foreground italic">Connect your GitLab account to manage repositories, issues, and merge requests</p>
                        <Button
                            onClick={connectGitLab}
                            disabled={gitlabStatus.loading}
                        >
                            {gitlabStatus.loading ? 'Connecting...' : 'Connect GitLab'}
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {gitlabStatus.user && (
                            <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
                                <img
                                    src={gitlabStatus.user.avatar_url}
                                    alt="GitLab Avatar"
                                    className="w-12 h-12 rounded-full border-2 border-primary/20"
                                />
                                <div>
                                    <div className="font-bold text-lg">{gitlabStatus.user.name}</div>
                                    <div className="text-sm text-muted-foreground">@{gitlabStatus.user.username}</div>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-3 gap-4">
                            <div className="p-4 border rounded-lg text-center flex flex-col gap-1">
                                <div className="text-2xl font-bold">{gitlabStatus.repositories.length}</div>
                                <div className="text-xs text-muted-foreground uppercase tracking-widest">Repositories</div>
                            </div>
                            <div className="p-4 border rounded-lg text-center flex flex-col gap-1">
                                <div className="text-2xl font-bold">{gitlabStatus.issues.length}</div>
                                <div className="text-xs text-muted-foreground uppercase tracking-widest">Issues</div>
                            </div>
                            <div className="p-4 border rounded-lg text-center flex flex-col gap-1">
                                <div className="text-2xl font-bold">{gitlabStatus.mergeRequests.length}</div>
                                <div className="text-xs text-muted-foreground uppercase tracking-widest">MRs</div>
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <Button
                                onClick={disconnectGitLab}
                                disabled={gitlabStatus.loading}
                                variant="destructive"
                            >
                                Disconnect GitLab
                            </Button>
                        </div>
                    </div>
                )}

                {gitlabStatus.error && (
                    <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm font-medium">
                        {gitlabStatus.error}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default GitLabManager;
