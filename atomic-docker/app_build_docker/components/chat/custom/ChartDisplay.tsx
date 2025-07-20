import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

type Props = {
    data: any[];
    chartType: 'bar'; // Extend this as needed for other chart types
};

const ChartDisplay = ({ data, chartType }: Props) => {
    return (
        <div className="my-2" style={{ width: '100%', height: 300 }}>
            <ResponsiveContainer>
                {chartType === 'bar' && (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="value" fill="#8884d8" />
                    </BarChart>
                )}
            </ResponsiveContainer>
        </div>
    );
};

export default ChartDisplay;
