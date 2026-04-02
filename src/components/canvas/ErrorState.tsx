'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
    title: string;
    message: string;
    action?: () => void;
    actionLabel?: string;
}

export function ErrorState({ title, message, action, actionLabel = 'Retry' }: ErrorStateProps) {
    return (
        <Card className="bg-gray-900 border-gray-800">
            <CardContent className="flex flex-col items-center justify-center py-12">
                <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
                <p className="text-gray-400 text-center mb-6 max-w-md">{message}</p>
                {action && (
                    <Button onClick={action} variant="outline" className="border-gray-700">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        {actionLabel}
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
