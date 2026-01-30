import React from "react";
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface PieChartProps {
    data: {
        name: string;
        value: number;
    }[];
    title?: string;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

export function PieChartCanvas({ data, title }: PieChartProps) {
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
