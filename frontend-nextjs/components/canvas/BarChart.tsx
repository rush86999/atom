import React from "react";
import { BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface BarChartProps {
    data: {
        name: string;
        value: number;
    }[];
    title?: string;
    color?: string;
}

export function BarChartCanvas({ data, title, color = "#8884d8" }: BarChartProps) {
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
