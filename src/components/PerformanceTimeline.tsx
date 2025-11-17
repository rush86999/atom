import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { usePerformanceMonitor, PerformanceMetrics } from '../utils/performance';
import { useWebSocket } from '../hooks/useWebSocket';

const PerformanceTimeline: React.FC = () => {
  const [data, setData] = useState<any[]>([]);
  const monitor = usePerformanceMonitor();
  const { subscribe, unsubscribe } = useWebSocket({ enabled: true });

  useEffect(() => {
    // Subscribe to local performance monitor updates (browser metrics)
    const unsubscribeMonitor = monitor.subscribeToRealTimeUpdates((metrics: PerformanceMetrics) => {
      setData((prevData) => [...prevData.slice(-19), { ...metrics, source: 'client' }]);
    });

    return () => unsubscribeMonitor();
  }, [monitor]);

  useEffect(() => {
    // Listen for server metrics updates
    const onMetrics = (m: any) => {
      const point = {
        timestamp: m.timestamp || new Date().toISOString(),
        currentConnections: m.currentConnections,
        messagesReceived: m.messagesReceived,
        messagesSent: m.messagesSent,
        source: 'server',
      };
      setData((prev) => [...prev.slice(-19), point]);
    };

    subscribe('metrics:update', onMetrics);

    return () => {
      unsubscribe('metrics:update', onMetrics);
    };
  }, [subscribe, unsubscribe]);

  // Normalize data to a shape that the chart can use; chart will show messagesReceived and currentConnections
  const chartData = data.map((d) => ({
    timestamp: new Date(d.timestamp).toLocaleTimeString(),
    messagesReceived: d.messagesReceived || 0,
    messagesSent: d.messagesSent || 0,
    currentConnections: d.currentConnections || 0,
    fcp: typeof d.fcp === 'number' ? d.fcp : undefined,
    lcp: typeof d.lcp === 'number' ? d.lcp : undefined,
    cls: typeof d.cls === 'number' ? d.cls : undefined,
    ttfb: typeof d.ttfb === 'number' ? d.ttfb : undefined,
  }));

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="messagesReceived" stroke="#8884d8" name="Messages Received" />
          <Line type="monotone" dataKey="messagesSent" stroke="#82ca9d" name="Messages Sent" />
          <Line type="monotone" dataKey="currentConnections" stroke="#ff8042" name="Connections" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PerformanceTimeline;
