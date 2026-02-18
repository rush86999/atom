import React, { useEffect } from "react";
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { ChartCanvasState, CanvasStateAPI } from './types';

interface PieChartProps {
    data: {
        name: string;
        value: number;
    }[];
    title?: string;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

export function PieChartCanvas({ data, title }: PieChartProps) {
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
            const canvasId = `chart-pie-${Date.now()}`;

            // Create state object
            const state: ChartCanvasState = {
                canvas_type: 'generic',
                canvas_id: canvasId,
                timestamp: new Date().toISOString(),
                component: 'pie_chart',
                chart_type: 'pie',
                data_points: data.map((d, i) => ({
                    x: d.name || i,
                    y: typeof d.value === 'number' ? d.value : 0,
                    label: d.name
                })),
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
    }, [data, title]);

    return (
        <div className="w-full">
            {title && <h4 className="text-sm font-semibold mb-2">{title}</h4>}
            <ResponsiveContainer width="100%" height={200}>
                <RechartsPieChart margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <Pie
                        data={data}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={(entry) => `${entry.name}: ${entry.value}`}
                        labelLine={false}
                        fontSize={10}
                    >
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'hsl(var(--background))',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: '6px',
                            fontSize: '12px'
                        }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                </RechartsPieChart>
            </ResponsiveContainer>
        </div>
    );
}
