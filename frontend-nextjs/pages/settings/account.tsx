import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Mail, CheckCircle2, XCircle, Trash2, Key, Eye, EyeOff, AlertCircle, Shield } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import TwoFactorSettings from '@/components/Settings/TwoFactorSettings';

interface UserAccount {
    id: string;
    provider: string;
    provider_account_id: string;
    created_at: string;
    expires_at: string | null;
}

interface AccountData {
    user: {
        email: string;
        name: string;
        email_verified: string | null;
        image: string | null;
        created_at: string;
    };
    accounts: UserAccount[];
}

export default function AccountSettings() {
    const { data: session, status } = useSession();
    const router = useRouter();
    const [accountData, setAccountData] = useState<AccountData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [removing, setRemoving] = useState<string | null>(null);
    const { toast } = useToast();
    const [changingPassword, setChangingPassword] = useState(false);
    const [showCurrentPassword, setShowCurrentPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [passwordData, setPasswordData] = useState({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
    });

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();

        if (passwordData.newPassword !== passwordData.confirmPassword) {
            toast({
                title: 'Error',
                description: 'New passwords do not match',
                variant: 'error'
            });
            return;
        }

        if (passwordData.newPassword.length < 8) {
            toast({
                title: 'Error',
                description: 'Password must be at least 8 characters',
                variant: 'error'
            });
            return;
        }

        setChangingPassword(true);
        try {
            // @ts-ignore
            const token = (session as any)?.backendToken || (session as any)?.user?.token;

            const res = await fetch('/api/auth/change-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    current_password: passwordData.currentPassword,
                    new_password: passwordData.newPassword
                })
            });

            if (res.ok) {
                toast({
                    title: 'Success',
                    description: 'Password updated successfully',
                    variant: 'success'
                });
                setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
            } else {
                const data = await res.json();
                toast({
                    title: 'Error',
                    description: data.detail || data.error || 'Failed to update password',
                    variant: 'error'
                });
            }
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to update password',
                variant: 'error'
            });
        } finally {
            setChangingPassword(false);
        }
    };

    useEffect(() => {
        if (status === 'unauthenticated') {
            router.push('/auth/signin');
        } else if (status === 'authenticated') {
            fetchAccounts();
        }
    }, [status]);

    const fetchAccounts = async () => {
        try {
            // @ts-ignore - backendToken is added in [...nextauth].ts
            const token = (session as any)?.backendToken || (session as any)?.user?.token;

            const response = await fetch('/api/auth/accounts', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (!response.ok) {
                // Try to parse error response
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) errorMsg += ` - ${errorData.detail}`;
                } catch (e) {
                    // Ignore json parse error
                    const text = await response.text();
                    if (text) errorMsg += ` - ${text.substring(0, 100)}`;
                }
                throw new Error(errorMsg);
            }
            const data = await response.json();
            setAccountData(data);
        } catch (err: any) {
            console.error("Fetch accounts error:", err);
            setError(err.message || 'Failed to load account information');
        } finally {
            setLoading(false);
        }
    };

    const handleRemoveAccount = async (accountId: string, provider: string) => {
        if (!confirm(`Are you sure you want to unlink your ${provider} account? You will no longer be able to sign in with ${provider}.`)) {
            return;
        }

        setRemoving(accountId);
        setError('');

        try {
            // @ts-ignore
            const token = (session as any)?.backendToken || (session as any)?.user?.token;

            const response = await fetch('/api/auth/accounts', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ accountId }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to remove account');
            }

            // Refresh account list
            await fetchAccounts();
        } catch (err: any) {
            setError(err.message || 'Failed to remove account');
        } finally {
            setRemoving(null);
        }
    };

    const getProviderIcon = (provider: string) => {
        switch (provider) {
            case 'google':
                return '🔐'; // Google icon
            case 'github':
                return '🐙'; // GitHub icon
            case 'credentials':
                return '🔑'; // Email/Password icon
            default:
                return '🔗';
        }
    };

    const getProviderLabel = (provider: string) => {
        switch (provider) {
            case 'google':
                return 'Google';
            case 'github':
                return 'GitHub';
            case 'credentials':
                return 'Email/Password';
            default:
                return provider;
        }
    };

    if (loading || status === 'loading') {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    if (!accountData) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <Alert variant="destructive" className="max-w-md">
                    <AlertDescription className="space-y-4">
                        <p className="font-semibold">{error || 'Failed to load account information'}</p>
                        <Button variant="outline" size="sm" onClick={fetchAccounts} className="w-full">
                            <span className="mr-2">↻</span> Retry
                        </Button>
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Account Settings</h1>
                    <p className="mt-2 text-gray-600">Manage your account and linked authentication methods</p>
                </div>

                {error && (
                    <Alert variant="destructive">
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                {/* User Profile Card */}
                <Card>
                    <CardHeader>
                        <CardTitle>Profile Information</CardTitle>
                        <CardDescription>Your account details</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center gap-4">
                            {accountData.user.image && (
                                <img
                                    src={accountData.user.image}
                                    alt={accountData.user.name || 'Avatar'}
                                    className="h-16 w-16 rounded-full"
                                />
                            )}
                            <div>
                                <p className="text-lg font-semibold">{accountData.user.name || 'User'}</p>
                                <p className="text-gray-600">{accountData.user.email}</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            {accountData.user.email_verified ? (
                                <>
                                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                                    <span className="text-sm text-green-700">Email Verified</span>
                                </>
                            ) : (
                                <>
                                    <XCircle className="h-4 w-4 text-amber-500" />
                                    <span className="text-sm text-amber-700">Email Not Verified</span>
                                </>
                            )}
                        </div>

                        <p className="text-sm text-gray-500">
                            Member since {new Date(accountData.user.created_at).toLocaleDateString()}
                        </p>
                    </CardContent>
                </Card>

                {/* Password Change Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Key className="h-5 w-5 text-blue-500" />
                            Change Password
                        </CardTitle>
                        <CardDescription>Update your account password</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleChangePassword} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="currentPassword">Current Password</Label>
                                <div className="relative">
                                    <Input
                                        id="currentPassword"
                                        type={showCurrentPassword ? "text" : "password"}
                                        value={passwordData.currentPassword}
                                        onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                                        placeholder="Enter current password"
                                        required
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                                    >
                                        {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="newPassword">New Password</Label>
                                    <div className="relative">
                                        <Input
                                            id="newPassword"
                                            type={showNewPassword ? "text" : "password"}
                                            value={passwordData.newPassword}
                                            onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                                            placeholder="Min 8 characters"
                                            required
                                            minLength={8}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowNewPassword(!showNewPassword)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                                        >
                                            {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                        </button>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="confirmPassword">Confirm New Password</Label>
                                    <Input
                                        id="confirmPassword"
                                        type="password"
                                        value={passwordData.confirmPassword}
                                        onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                                        placeholder="Repeat new password"
                                        required
                                        minLength={8}
                                    />
                                </div>
                            </div>

                            {passwordData.newPassword && passwordData.confirmPassword && (
                                <div className={`flex items-center gap-2 text-sm ${passwordData.newPassword === passwordData.confirmPassword ? 'text-green-600' : 'text-red-600'}`}>
                                    {passwordData.newPassword === passwordData.confirmPassword ? (
                                        <>
                                            <CheckCircle2 className="h-4 w-4" />
                                            <span>Passwords match</span>
                                        </>
                                    ) : (
                                        <>
                                            <AlertCircle className="h-4 w-4" />
                                            <span>Passwords do not match</span>
                                        </>
                                    )}
                                </div>
                            )}

                            <Button
                                type="submit"
                                disabled={changingPassword || !passwordData.currentPassword || !passwordData.newPassword || passwordData.newPassword !== passwordData.confirmPassword}
                                className="w-full"
                            >
                                {changingPassword ? (
                                    <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Updating...</>
                                ) : (
                                    'Update Password'
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* Two-Factor Authentication Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Shield className="h-5 w-5 text-green-500" />
                            Two-Factor Authentication
                        </CardTitle>
                        <CardDescription>Add an extra layer of security to your account</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <TwoFactorSettings />
                    </CardContent>
                </Card>

                {/* Linked Accounts Card */}
                <Card>
                    <CardHeader>
                        <CardTitle>Linked Accounts</CardTitle>
                        <CardDescription>
                            Connect multiple authentication methods to sign in easily
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {accountData.accounts.length === 0 ? (
                                <p className="text-gray-500 text-center py-8">
                                    No linked accounts found. Link an account to get started.
                                </p>
                            ) : (
                                accountData.accounts.map((account) => (
                                    <div
                                        key={account.id}
                                        className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                                    >
                                        <div className="flex items-center gap-4">
                                            <span className="text-3xl">{getProviderIcon(account.provider)}</span>
                                            <div>
                                                <p className="font-medium">{getProviderLabel(account.provider)}</p>
                                                <p className="text-sm text-gray-500">
                                                    Connected on {new Date(account.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            <Badge variant="secondary">
                                                {accountData.accounts.length === 1 ? 'Primary' : 'Linked'}
                                            </Badge>

                                            {accountData.accounts.length > 1 && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleRemoveAccount(account.id, account.provider)}
                                                    disabled={removing === account.id}
                                                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                                >
                                                    {removing === account.id ? (
                                                        <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Removing...</>
                                                    ) : (
                                                        <><Trash2 className="h-4 w-4 mr-2" /> Unlink</>
                                                    )}
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>

                        {/* Help text */}
                        {accountData.accounts.length === 1 && (
                            <p className="mt-4 text-sm text-amber-600 bg-amber-50 p-3 rounded border border-amber-200">
                                ⚠️ This is your only authentication method. Add anothermethod before unlinking this one.
                            </p>
                        )}
                    </CardContent>
                </Card>

                {/* Actions */}
                <div className="flex justify-between">
                    <Button variant="outline" onClick={() => router.push('/')}>
                        Back to Dashboard
                    </Button>
                </div>
            </div>
        </div>
    );
}
