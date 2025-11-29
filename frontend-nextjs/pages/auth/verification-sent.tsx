import React from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Mail, ArrowRight } from 'lucide-react';

export default function VerificationSentPage() {
    const router = useRouter();
    const { email } = router.query;

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <div className="flex justify-center mb-4">
                        <div className="rounded-full bg-blue-100 p-4">
                            <Mail className="h-12 w-12 text-blue-600" />
                        </div>
                    </div>
                    <CardTitle className="text-2xl text-center">
                        Check Your Email
                    </CardTitle>
                    <CardDescription className="text-center">
                        We've sent a verification code to
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {email && (
                        <div className="text-center">
                            <p className="text-lg font-semibold text-gray-900">{email}</p>
                        </div>
                    )}

                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p className="text-sm text-gray-700">
                            <strong className="font-semibold">What to do next:</strong>
                        </p>
                        <ol className="mt-2 space-y-2 text-sm text-gray-600 list-decimal list-inside">
                            <li>Check your email inbox for a message from us</li>
                            <li>Copy the 6-digit verification code</li>
                            <li>Enter the code on the verification page</li>
                            <li>Start using your account!</li>
                        </ol>
                    </div>

                    <div className="space-y-3">
                        <Button
                            className="w-full"
                            onClick={() => router.push(`/auth/verify-email?email=${encodeURIComponent(email as string || '')}`)}
                        >
                            Enter Verification Code
                            <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>

                        <div className="text-center text-sm text-gray-600 space-y-1">
                            <p>Didn't receive the email?</p>
                            <ul className="space-y-1">
                                <li>• Check your spam or junk folder</li>
                                <li>• Make sure you entered the correct email address</li>
                                <li>
                                    • <Link
                                        href={`/auth/verify-email?email=${encodeURIComponent(email as string || '')}`}
                                        className="text-blue-600 hover:text-blue-700 font-medium"
                                    >
                                        Resend verification email
                                    </Link>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <div className="pt-4 border-t text-center">
                        <Link
                            href="/auth/signin"
                            className="text-sm text-gray-600 hover:text-gray-900"
                        >
                            ← Back to Sign In
                        </Link>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
