import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, Mail, AlertCircle, Loader2 } from 'lucide-react';

export default function VerifyEmailPage() {
    const router = useRouter();
    const { email } = router.query;

    const [verificationCode, setVerificationCode] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);
    const [resending, setResending] = useState(false);

    const handleVerify = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/auth/verify-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email || '',
                    code: verificationCode,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Verification failed');
            }

            setSuccess(true);
            // Redirect to signin after 2 seconds
            setTimeout(() => {
                router.push('/auth/signin?verified=true');
            }, 2000);
        } catch (err: any) {
            setError(err.message || 'Verification failed. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleResend = async () => {
        if (!email) {
            setError('Email address is required');
            return;
        }

        setError('');
        setResending(true);

        try {
            const response = await fetch('/api/auth/send-verification-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to resend verification email');
            }

            setError('');
            alert('Verification email sent! Please check your inbox.');
        } catch (err: any) {
            setError(err.message || 'Failed to resend email');
        } finally {
            setResending(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
                <Card className="w-full max-w-md">
                    <CardContent className="pt-6">
                        <div className="text-center">
                            <CheckCircle2 className="mx-auto h-16 w-16 text-green-500 mb-4" />
                            <h2 className="text-2xl font-bold text-gray-900 mb-2">
                                Email Verified!
                            </h2>
                            <p className="text-gray-600 mb-4">
                                Your email has been successfully verified. Redirecting to sign in...
                            </p>
                            <Loader2 className="mx-auto h-6 w-6 animate-spin text-blue-500" />
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <div className="flex justify-center mb-4">
                        <Mail className="h-12 w-12 text-blue-500" />
                    </div>
                    <CardTitle className="text-2xl text-center">Verify Your Email</CardTitle>
                    <CardDescription className="text-center">
                        Enter the 6-digit code sent to {email ? <strong>{email}</strong> : 'your email'}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleVerify} className="space-y-4">
                        {error && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        <div className="space-y-2">
                            <Label htmlFor="code">Verification Code</Label>
                            <Input
                                id="code"
                                type="text"
                                placeholder="000000"
                                value={verificationCode}
                                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                maxLength={6}
                                className="text-center text-2xl font-mono tracking-widest"
                                required
                                autoFocus
                            />
                            <p className="text-sm text-gray-500 text-center">
                                Please enter the 6-digit code from your email
                            </p>
                        </div>

                        <Button
                            type="submit"
                            className="w-full"
                            disabled={isLoading || verificationCode.length !== 6}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Verifying...
                                </>
                            ) : (
                                'Verify Email'
                            )}
                        </Button>

                        <div className="text-center space-y-2">
                            <p className="text-sm text-gray-600">
                                Didn't receive the code?
                            </p>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleResend}
                                disabled={resending || !email}
                                className="w-full"
                            >
                                {resending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Sending...
                                    </>
                                ) : (
                                    'Resend Verification Email'
                                )}
                            </Button>
                        </div>

                        <div className="text-center">
                            <Link href="/auth/signin" className="text-sm text-blue-600 hover:text-blue-700">
                                Back to Sign In
                            </Link>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
