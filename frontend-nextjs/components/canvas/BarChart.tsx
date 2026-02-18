import React, { useEffect } from "react";
import { BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { ChartCanvasState, CanvasStateAPI } from './types';

interface BarChartProps {
    data: {
        name: string;
        value: number;
    }[];
    title?: string;
    color?: string;
}

export function BarChartCanvas({ data, title, color = "#8884d8" }: BarChartProps) {
    // Register canvas state with global API for AI agent access
    useEffect(() => {
        // Initialize global atom.canvas API
        if (typeof window !== 'undefined') {
            if (!(window as any).atom) {
                (window as any).atom = {};
            }
            if (!(window as any).atom.canvas) {
                (window as any).atom.canvas = {
                    getState: (canvasId: string) => null,
                    getAllStates: () => [],
                    subscribe: () => () => {},
                    subscribeAll: () => () => {}
                };
            }

            // Generate canvas ID
            const canvasId = `chart-bar-${Date.now()}`;

            // Create state object
            const state: ChartCanvasState = {
                canvas_type: 'generic',
                canvas_id: canvasId,
                timestamp: new Date().toISOString(),
                component: 'bar_chart',
                chart_type: 'bar',
                data_points: data.map((d, i) => ({
                    x: d.name || i,
                    y: typeof d.value === 'number' ? d.value : 0,
                    label: d.name
                })),
                axes_labels: {
                    x: 'Category',
                    y: 'Value'
                },
                title: title,
                legend: true
            };

            // Register getState function
            const api = (window as any).atom.canvas as CanvasStateAPI;
            const originalGetState = api.getState;
            api.getState = (canvasId: string) => {
                const originalResult = originalGetState(canvasId);
                if (originalResult) return originalResult;
                return canvasId === state.canvas_id ? state : null;
            };

            const originalGetAllStates = api.getAllStates;
            api.getAllStates = () => {
                const states = originalGetAllStates() || [];
                return [...states, { canvas_id: state.canvas_id, state }];
            };

            // Cleanup on unmount
            return () => {
                api.getState = originalGetState;
                api.getAllStates = originalGetAllStates;
            };
        }
    }, [data, title, color]);

    return (
        <div className="w-full">
            {title && <h4 className="text-sm font-semibold mb-2">{title}</h4>}
            <ResponsiveContainer width="100%" height={200}>
                <RechartsBarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                        dataKey="name"
                        tick={{ fontSize: 10 }}
                        className="text-muted-foreground"
                    />
                    <YAxis
                        tick={{ fontSize: 10 }}
                        className="text-muted-foreground"
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'hsl(var(--background))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: '6px',
                            fontSize: '12px'
                        }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
                </RechartsBarChart>
            </ResponsiveContainer>
        </div>
    );
}
