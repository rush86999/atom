'use client';

import React from 'react';
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

export function CanvasListSkeleton() {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
                <Card key={i} className="bg-gray-900 border-gray-800">
                    <CardHeader className="pb-4">
                        <div className="flex items-center justify-between mb-4">
                            <Skeleton className="w-12 h-12 rounded-xl bg-gray-800" />
                            <Skeleton className="w-16 h-6 rounded-full bg-gray-800" />
                        </div>
                        <Skeleton className="w-3/4 h-6 bg-gray-800 mb-2" />
                        <Skeleton className="w-1/2 h-4 bg-gray-800" />
                    </CardHeader>
                    <CardFooter className="pt-4 border-t border-gray-800/50">
                        <Skeleton className="w-1/3 h-4 bg-gray-800" />
                    </CardFooter>
                </Card>
            ))}
        </div>
    );
}
