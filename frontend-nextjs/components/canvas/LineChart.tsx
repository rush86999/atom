import React, { useEffect } from "react";
import { LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { ChartCanvasState, CanvasStateAPI } from './types';

interface LineChartProps {
    data: {
        timestamp: string;
        value: number;
        label?: string;
    }[];
    title?: string;
    color?: string;
}

export function LineChartCanvas({ data, title, color = "#8884d8" }: LineChartProps) {
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
            const canvasId = `chart-line-${Date.now()}`;

            // Create state object
            const state: ChartCanvasState = {
                canvas_type: 'generic',
                canvas_id: canvasId,
                timestamp: new Date().toISOString(),
                component: 'line_chart',
                chart_type: 'line',
                data_points: data.map((d, i) => ({
                    x: d.timestamp || i,
                    y: typeof d.value === 'number' ? d.value : 0,
                    label: d.label
                })),
                axes_labels: {
                    x: 'Time',
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
                <RechartsLineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                        dataKey="timestamp"
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
                    <Line
                        type="monotone"
                        dataKey="value"
                        stroke={color}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                    />
                </RechartsLineChart>
            </ResponsiveContainer>
        </div>
    );
}
