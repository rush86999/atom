'use client';

import React, { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Shield, ShieldCheck, ShieldAlert, Loader2, Copy, Check } from 'lucide-react';
import { toast } from 'react-hot-toast';

export default function TwoFactorSettings() {
    const [isEnabled, setIsEnabled] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isSettingUp, setIsSettingUp] = useState(false);
    const [setupData, setSetupData] = useState<{ secret: string; otpauth_url: string } | null>(null);
    const [verificationCode, setVerificationCode] = useState('');
    const [isVerifying, setIsVerifying] = useState(false);
    const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        fetchStatus();
    }, []);

    const fetchStatus = async () => {
        try {
            const res = await fetch('/api/auth/2fa/status');
            const data = await res.json();
            setIsEnabled(data.enabled);
        } catch (error) {
            console.error('Failed to fetch 2FA status:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleStartSetup = async () => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/2fa/setup', { method: 'POST' });
            if (!res.ok) throw new Error('Failed to initiate setup');
            const data = await res.json();
            setSetupData(data);
            setIsSettingUp(true);
        } catch (error) {
            toast.error('Could not start 2FA setup. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleEnable = async () => {
        if (!verificationCode) return;
        setIsVerifying(true);
        try {
            const res = await fetch('/api/auth/2fa/enable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: verificationCode })
            });
            const data = await res.json();
            if (res.ok) {
                setIsEnabled(true);
                setIsSettingUp(false);
                setBackupCodes(data.backup_codes);
                toast.success('Two-factor authentication enabled!');
            } else {
                toast.error(data.detail || 'Invalid verification code');
            }
        } catch (error) {
            toast.error('Verification failed. Please try again.');
        } finally {
            setIsVerifying(false);
        }
    };

    const handleDisable = async () => {
        const code = prompt('Please enter your 2FA code to disable it:');
        if (!code) return;

        setIsLoading(true);
        try {
            const res = await fetch('/api/auth/2fa/disable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            if (res.ok) {
                setIsEnabled(false);
                toast.success('Two-factor authentication disabled.');
            } else {
                const data = await res.json();
                toast.error(data.detail || 'Failed to disable 2FA');
            }
        } catch (error) {
            toast.error('An error occurred. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const copyBackupCodes = () => {
        if (!backupCodes) return;
        navigator.clipboard.writeText(backupCodes.join('\n'));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast.success('Backup codes copied to clipboard');
    };

    if (isLoading && !isSettingUp) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            </div>
        );
    }

    if (backupCodes) {
        return (
            <div className="space-y-4 p-6 bg-green-50 rounded-xl border border-green-200">
                <div className="flex items-center gap-2 text-green-700 font-semibold">
                    <ShieldCheck className="w-5 h-5" />
                    <span>2FA Enabled Successfully</span>
                </div>
                <p className="text-gray-600 text-sm">
                    Please save these recovery codes in a safe place.
                </p>
                <div className="bg-white p-4 rounded-lg font-mono text-sm text-green-800 border border-green-100">
                    {backupCodes.map((code, i) => (
                        <div key={i}>{code}</div>
                    ))}
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={copyBackupCodes}
                        className="text-xs bg-white border border-gray-300 px-3 py-1.5 rounded-md hover:bg-gray-50 flex items-center gap-2"
                    >
                        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                        Copy Codes
                    </button>
                    <button
                        onClick={() => setBackupCodes(null)}
                        className="text-xs text-gray-600 hover:text-gray-800 px-3 py-1.5"
                    >
                        Done
                    </button>
                </div>
            </div>
        );
    }

    if (isSettingUp && setupData) {
        return (
            <div className="space-y-6 p-6 bg-gray-50 border border-gray-200 rounded-xl">
                <div className="flex items-center gap-2 text-blue-600 font-semibold">
                    <Shield className="w-5 h-5" />
                    <span>Setup Two-Factor Authentication</span>
                </div>

                <div className="flex flex-col md:flex-row gap-8 items-center md:items-start">
                    <div className="bg-white p-4 rounded-xl border border-gray-200">
                        <QRCodeSVG value={setupData.otpauth_url} size={160} />
                    </div>

                    <div className="flex-1 space-y-4">
                        <div className="text-sm text-gray-600 space-y-2">
                            <p>1. Scan this QR code with your authenticator app.</p>
                            <p>2. Or enter this secret manually: <code className="bg-white border px-1 rounded text-orange-600">{setupData.secret}</code></p>
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="vcode" className="block text-sm font-medium text-gray-700">Verification Code</label>
                            <input
                                id="vcode"
                                value={verificationCode}
                                onChange={(e) => setVerificationCode(e.target.value)}
                                placeholder="123456"
                                className="w-full max-w-[200px] px-3 py-2 border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                            />
                        </div>

                        <div className="flex gap-2 pt-2">
                            <button
                                onClick={handleEnable}
                                disabled={isVerifying || verificationCode.length !== 6}
                                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                            >
                                {isVerifying && <Loader2 className="w-4 h-4 animate-spin" />}
                                Enable 2FA
                            </button>
                            <button
                                onClick={() => setIsSettingUp(false)}
                                className="text-gray-600 hover:text-gray-800 px-4 py-2"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="py-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${isEnabled ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                        {isEnabled ? <ShieldCheck className="w-6 h-6" /> : <ShieldAlert className="w-6 h-6" />}
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-gray-900">Two-Factor Authentication (2FA)</h3>
                        <p className="text-xs text-gray-500">
                            {isEnabled
                                ? 'Your account is secured with two-factor authentication.'
                                : 'Add an extra layer of security to your account.'}
                        </p>
                    </div>
                </div>

                {isEnabled ? (
                    <button
                        onClick={handleDisable}
                        className="text-sm text-red-600 hover:text-red-700 font-medium px-4 py-2 border border-red-200 rounded-md hover:bg-red-50"
                    >
                        Disable
                    </button>
                ) : (
                    <button
                        onClick={handleStartSetup}
                        className="text-sm bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 font-medium"
                    >
                        Enable 2FA
                    </button>
                )}
            </div>
        </div>
    );
}
