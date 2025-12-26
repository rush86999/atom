import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useSession } from 'next-auth/react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import { useToast } from '@components/ui/use-toast';

// Placeholders for imports that might be missing in some environments
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

interface ActivityLogItem {
    type: 'success' | 'error' | 'info';
    message: string;
    timestamp: string;
    workflowId?: string;
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

    const [activityLog, setActivityLog] = useState<ActivityLogItem[]>([]);

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
                // You could load more data here if needed
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
                toast({ title: 'GitLab disconnected', variant: 'default' });
            } else {
                throw new Error('Failed to disconnect');
            }
        } catch (error: any) {
            setGitlabStatus(prev => ({ ...prev, loading: false, error: error.message }));
            toast({ title: 'Error disconnecting GitLab', variant: 'destructive' });
        }
    };

    return (
        <Box marginTop="m" padding="m" borderWidth={1} borderColor="hairline" borderRadius="m">
            <Box flexDirection="row" justifyContent="space-between" alignItems="center" marginBottom="m">
                <Text variant="subHeader">🦊 GitLab Integration</Text>
                <Box
                    paddingHorizontal="s"
                    paddingVertical="xs"
                    borderRadius="s"
                    backgroundColor={gitlabStatus.connected ? 'green.100' : 'gray.200'}
                >
                    <Text variant="small" color={gitlabStatus.connected ? 'green.800' : 'gray.600'}>
                        {gitlabStatus.connected ? 'Connected' : 'Disconnected'}
                    </Text>
                </Box>
            </Box>

            {!gitlabStatus.connected ? (
                <Box alignItems="center" paddingVertical="l">
                    <Text marginBottom="m">Connect your GitLab account to manage repositories, issues, and merge requests</Text>
                    <Button
                        onPress={connectGitLab}
                        disabled={gitlabStatus.loading}
                        title={gitlabStatus.loading ? 'Connecting...' : 'Connect GitLab'}
                    />
                </Box>
            ) : (
                <Box>
                    {gitlabStatus.user && (
                        <Box flexDirection="row" alignItems="center" marginBottom="m" padding="s" backgroundColor="gray.50" borderRadius="s">
                            <img
                                src={gitlabStatus.user.avatar_url}
                                alt="GitLab Avatar"
                                style={{ width: 40, height: 40, borderRadius: '50%', marginRight: 12 }}
                            />
                            <Box>
                                <Text fontWeight="bold">{gitlabStatus.user.name}</Text>
                                <Text variant="small" color="secondaryText">@{gitlabStatus.user.username}</Text>
                            </Box>
                        </Box>
                    )}

                    <Box flexDirection="row" gap="s" marginBottom="m">
                        <Box flex={1} padding="m" borderWidth={1} borderColor="hairline" borderRadius="s" alignItems="center">
                            <Text variant="subHeader">{gitlabStatus.repositories.length}</Text>
                            <Text variant="small">Repositories</Text>
                        </Box>
                        <Box flex={1} padding="m" borderWidth={1} borderColor="hairline" borderRadius="s" alignItems="center">
                            <Text variant="subHeader">{gitlabStatus.issues.length}</Text>
                            <Text variant="small">Issues</Text>
                        </Box>
                        <Box flex={1} padding="m" borderWidth={1} borderColor="hairline" borderRadius="s" alignItems="center">
                            <Text variant="subHeader">{gitlabStatus.mergeRequests.length}</Text>
                            <Text variant="small">MRs</Text>
                        </Box>
                    </Box>

                    <Box>
                        <Button
                            onPress={disconnectGitLab}
                            disabled={gitlabStatus.loading}
                            title="Disconnect GitLab"
                            variant="danger"
                        />
                    </Box>
                </Box>
            )}

            {gitlabStatus.error && (
                <Box marginTop="m" padding="s" backgroundColor="red.50" borderRadius="s">
                    <Text color="red.700" variant="small">{gitlabStatus.error}</Text>
                </Box>
            )}
        </Box>
    );
};

export const GitLabChatIntegration = {
    handleCommand: async (command: string, userId: string) => {
        return { success: true, message: 'GitLab command processed' };
    },
    searchInGitLab: async (query: string, userId: string) => {
        return [];
    },
    getGitLabStatus: async (userId: string) => {
        return { connected: false };
    }
};

export default GitLabManager;
