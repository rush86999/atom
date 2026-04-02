'use client';

import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Layout, FileText, BarChart3 } from 'lucide-react';

export interface CanvasPresentation {
    id: string;
    name: string;
    canvas_type: string;
    description?: string;
    content?: any;
    created_at: string;
    updated_at: string;
}

interface CanvasCardProps {
    canvas: CanvasPresentation;
    onClick: () => void;
}

export function CanvasCard({ canvas, onClick }: CanvasCardProps) {
    const getIcon = () => {
        switch (canvas.content?.presentation_type) {
            case 'bar':
            case 'line':
            case 'pie':
                return BarChart3;
            case 'form':
            case 'markdown':
            default:
                return Layout;
        }
    };

    const Icon = getIcon();

    return (
        <Card
            className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-all group cursor-pointer"
            onClick={onClick}
        >
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-blue-400/10 rounded-xl group-hover:scale-110 transition-transform">
                        <Icon className="w-6 h-6 text-blue-400" />
                    </div>
                    <Badge variant="outline" className="text-[10px] bg-gray-800 text-gray-400 border-gray-700 capitalize">
                        {canvas.content?.presentation_type || canvas.canvas_type}
                    </Badge>
                </div>
                <CardTitle className="text-white">{canvas.name}</CardTitle>
                {canvas.description && (
                    <CardDescription className="text-gray-400 mt-2">
                        {canvas.description}
                    </CardDescription>
                )}
            </CardHeader>
            <CardFooter className="pt-4 border-t border-gray-800/50">
                <div className="flex items-center justify-between w-full text-sm text-gray-500">
                    <span>{new Date(canvas.created_at).toLocaleDateString()}</span>
                    <span className="group-hover:text-blue-400 transition-colors">View →</span>
                </div>
            </CardFooter>
        </Card>
    );
}
