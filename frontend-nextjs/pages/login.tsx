import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { Mail, Lock, Eye, EyeOff } from 'lucide-react';
import { loginWithBackend, persistBackendToken } from '../lib/backendAuth';
import { registerWithBackend } from '../lib/registration';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function LoginPage() {
    const router = useRouter();
    const [isLogin, setIsLogin] = useState(true);
    const [showPassword, setShowPassword] = useState(false);
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [ssoLoading, setSsoLoading] = useState(false);
    const [ssoError, setSsoError] = useState('');
    const [error, setError] = useState('');

    const [formData, setFormData] = useState({
        email: '',
        password: '',
        first_name: '',
        last_name: ''
    });

    // OIDC SSO: probe the backend login endpoint first so we can surface a
    // friendly message when SSO isn't configured (409/503) instead of
    // navigating the user to a raw error response. When configured, the
    // endpoint 302s to the IdP — hand off to a full-page navigation so the
    // browser follows the redirect (an opaque redirect under CORS hides the
    // Location header, so we re-navigate to the login URL itself).
    const handleSSO = async () => {
        setSsoError('');
        setSsoLoading(true);
        const ssoLoginUrl = `${API_BASE}/api/auth/sso/oidc/login`;
        try {
            const response = await fetch(ssoLoginUrl, {
                redirect: 'manual',
                headers: { Accept: 'application/json' },
            });
            if (response.status === 409 || response.status === 503) {
                setSsoError('SSO is not configured for this workspace');
                setSsoLoading(false);
                return;
            }
        } catch {
            // Probe failed (e.g. CORS on the redirect hop) — fall through and
            // let the navigation itself surface any real problem.
        }
        window.location.href = ssoLoginUrl;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        // Resolve the post-auth redirect target. The middleware sets
        // callbackUrl when bouncing a logged-out user from a deep link; honor
        // it so the user returns to the page they wanted instead of always
        // landing on /dashboard. Guard against open-redirect: only allow
        // relative paths (must start with "/").
        const callbackUrl = typeof router.query.callbackUrl === 'string'
            ? router.query.callbackUrl
            : '/dashboard';
        const safeDest = callbackUrl.startsWith('/') && !callbackUrl.startsWith('//')
            ? callbackUrl
            : '/dashboard';

        try {
            if (isLogin) {
                const data = await loginWithBackend(formData.email, formData.password);
                persistBackendToken(data.access_token);
                router.push(safeDest);
            } else {
                // Register — same rules and error mapping as /auth/signup.
                if (formData.password.length < 8) {
                    throw new Error('Password must be at least 8 characters long');
                }
                if (formData.password !== confirmPassword) {
                    throw new Error('Passwords do not match');
                }
                const data = await registerWithBackend({
                    email: formData.email,
                    password: formData.password,
                    first_name: formData.first_name,
                    last_name: formData.last_name,
                });
                // #7 fix: was logging the full JWT to console — capturable by
                // browser extensions, shared screens, forwarded logs.
                persistBackendToken(data.access_token);
                router.push(safeDest);
            }
        } catch (err: any) {
            setError(err.message || 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 flex items-center justify-center p-4">
            <div className="max-w-md w-full">
                <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8">
                    {/* Header */}
                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                            ATOM Platform
                        </h1>
                        <p className="text-gray-600 dark:text-gray-400 mt-2">
                            {isLogin ? 'Welcome back!' : 'Create your account'}
                        </p>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div data-testid="login-error-message" className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 border border-red-400 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                        {!isLogin && (
                            <>
                                <div>
                                    <label htmlFor="first_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        First Name
                                    </label>
                                <input
                                    id="first_name"
                                    type="text"
                                    required
                                    data-testid="login-first-name-input"
                                    value={formData.first_name}
                                        onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                                        placeholder="John"
                                    />
                                </div>
                                <div>
                                    <label htmlFor="last_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Last Name
                                    </label>
                                <input
                                    id="last_name"
                                    type="text"
                                    required
                                    data-testid="login-last-name-input"
                                    value={formData.last_name}
                                        onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                                        placeholder="Doe"
                                    />
                                </div>
                            </>
                        )}

                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Email
                            </label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    id="email"
                                    type="email"
                                    required
                                    data-testid="login-email-input"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                                    placeholder="you@example.com"
                                />
                            </div>
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Password
                            </label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    required
                                    data-testid="login-password-input"
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    className="w-full pl-10 pr-12 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                                    placeholder="••••••••"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    aria-label={showPassword ? "Hide password" : "Show password"}
                                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-400 dark:hover:text-gray-300"
                                >
                                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                </button>
                            </div>
                            {!isLogin && (
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    {formData.password.length === 0
                                        ? 'Must be at least 8 characters'
                                        : formData.password.length < 8
                                            ? 'Password must be at least 8 characters'
                                            : confirmPassword.length > 0 && confirmPassword !== formData.password
                                                ? 'Passwords do not match'
                                                : '✓ Password looks good'}
                                </p>
                            )}
                        </div>

                        {!isLogin && (
                            <div>
                                <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Confirm Password
                                </label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <input
                                        id="confirm_password"
                                        type={showPassword ? 'text' : 'password'}
                                        required
                                        data-testid="login-confirm-password-input"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                                        placeholder="••••••••"
                                    />
                                </div>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loading}
                            data-testid="login-submit-button"
                            className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-semibold rounded-lg transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? 'Processing...' : isLogin ? 'Sign In' : 'Create Account'}
                        </button>
                    </form>

                    {/* SSO (OIDC) — only meaningful for sign-in */}
                    {isLogin && (
                        <div className="mt-4">
                            <div className="relative my-4">
                                <div className="absolute inset-0 flex items-center">
                                    <span className="w-full border-t border-gray-200 dark:border-gray-700" />
                                </div>
                                <div className="relative flex justify-center text-sm">
                                    <span className="bg-white dark:bg-gray-800 px-2 text-gray-500 dark:text-gray-400">or</span>
                                </div>
                            </div>
                            {ssoError && (
                                <div data-testid="sso-error-message" className="mb-3 p-3 bg-yellow-100 dark:bg-yellow-900/20 border border-yellow-400 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-400 text-sm">
                                    {ssoError}
                                </div>
                            )}
                            <button
                                type="button"
                                onClick={handleSSO}
                                disabled={ssoLoading}
                                data-testid="login-sso-button"
                                className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-semibold rounded-lg transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {ssoLoading ? 'Redirecting...' : 'Sign in with SSO (OIDC)'}
                            </button>
                        </div>
                    )}

                    {/* Toggle Login/Register */}
                    <div className="mt-6 text-center">
                        <button
                            data-testid="login-toggle-mode"
                            onClick={() => {
                                setIsLogin(!isLogin);
                                setError('');
                                setConfirmPassword('');
                            }}
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                        >
                            {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}


