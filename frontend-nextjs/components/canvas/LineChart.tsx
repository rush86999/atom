import React from "react";
import { LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

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
