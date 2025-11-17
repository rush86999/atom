import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { usePerformanceMonitor, PerformanceMetrics } from '../utils/performance';

const PerformanceTimeline: React.FC = () => {
  const [data, setData] = useState<PerformanceMetrics[]>([]);
  const monitor = usePerformanceMonitor();

  useEffect(() => {
    const unsubscribe = monitor.subscribeToRealTimeUpdates((metrics) => {
      setData((prevData) => [...prevData.slice(-20), metrics]);
    });

    return () => unsubscribe();
  }, [monitor]);

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="fcp" stroke="#8884d8" name="FCP (ms)" />
          <Line type="monotone" dataKey="lcp" stroke="#82ca9d" name="LCP (ms)" />
          <Line type="monotone" dataKey="cls" stroke="#ffc658" name="CLS" />
          <Line type="monotone" dataKey="ttfb" stroke="#ff8042" name="TTFB (ms)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PerformanceTimeline;
