import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format, subDays, startOfDay } from 'date-fns';
import { useAppStore } from '../../store';

interface AnalyticsChartProps {
  type: 'line' | 'area' | 'bar' | 'pie';
  data: any[];
  dataKey: string;
  xAxisKey?: string;
  title?: string;
  height?: number;
  colors?: string[];
  showGrid?: boolean;
  showLegend?: boolean;
  className?: string;
}

const defaultColors = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#10b981', // green
  '#f59e0b', // yellow
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#f97316', // orange
  '#84cc16', // lime
];

export const AnalyticsChart: React.FC<AnalyticsChartProps> = ({
  type,
  data,
  dataKey,
  xAxisKey = 'date',
  title,
  height = 300,
  colors = defaultColors,
  showGrid = true,
  showLegend = false,
  className = '',
}) => {
  const { resolvedTheme } = useAppStore();

  const chartColors = useMemo(() => {
    return resolvedTheme === 'dark'
      ? colors.map(color => lightenColor(color, 0.2))
      : colors;
  }, [colors, resolvedTheme]);

  const renderChart = () => {
    const commonProps = {
      data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 },
    };

    switch (type) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => format(new Date(value), 'MMM dd')}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(value) => format(new Date(value), 'PPP')}
              contentStyle={{
                backgroundColor: resolvedTheme === 'dark' ? '#1f2937' : '#ffffff',
                border: `1px solid ${resolvedTheme === 'dark' ? '#374151' : '#e5e7eb'}`,
                borderRadius: '6px',
              }}
            />
            {showLegend && <Legend />}
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={chartColors[0]}
              strokeWidth={2}
              dot={{ fill: chartColors[0], strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, stroke: chartColors[0], strokeWidth: 2 }}
            />
          </LineChart>
        );

      case 'area':
        return (
          <AreaChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => format(new Date(value), 'MMM dd')}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(value) => format(new Date(value), 'PPP')}
              contentStyle={{
                backgroundColor: resolvedTheme === 'dark' ? '#1f2937' : '#ffffff',
                border: `1px solid ${resolvedTheme === 'dark' ? '#374151' : '#e5e7eb'}`,
                borderRadius: '6px',
              }}
            />
            {showLegend && <Legend />}
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={chartColors[0]}
              fill={chartColors[0]}
              fillOpacity={0.3}
            />
          </AreaChart>
        );

      case 'bar':
        return (
          <BarChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => format(new Date(value), 'MMM dd')}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(value) => format(new Date(value), 'PPP')}
              contentStyle={{
                backgroundColor: resolvedTheme === 'dark' ? '#1f2937' : '#ffffff',
                border: `1px solid ${resolvedTheme === 'dark' ? '#374151' : '#e5e7eb'}`,
                borderRadius: '6px',
              }}
            />
            {showLegend && <Legend />}
            <Bar dataKey={dataKey} fill={chartColors[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey={dataKey}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: resolvedTheme === 'dark' ? '#1f2937' : '#ffffff',
                border: `1px solid ${resolvedTheme === 'dark' ? '#374151' : '#e5e7eb'}`,
                borderRadius: '6px',
              }}
            />
            {showLegend && <Legend />}
          </PieChart>
        );

      default:
        return null;
    }
  };

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 ${className}`}>
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {title}
        </h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
};

// Utility function to lighten colors for dark mode
function lightenColor(color: string, percent: number): string {
  // Convert hex to RGB
  const num = parseInt(color.replace("#", ""), 16);
  const amt = Math.round(2.55 * percent * 100);
  const R = (num >> 16) + amt;
  const G = (num >> 8 & 0x00FF) + amt;
  const B = (num & 0x0000FF) + amt;
  return "#" + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
    (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
    (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
}

// Specialized chart components
export const TaskCompletionChart: React.FC<{ className?: string }> = ({ className }) => {
  const tasks = useAppStore((state) => state.tasks);

  const data = useMemo(() => {
    const last7Days = Array.from({ length: 7 }, (_, i) => {
      const date = startOfDay(subDays(new Date(), 6 - i));
      return {
        date: date.toISOString(),
        completed: tasks.filter(task =>
          task.status === 'completed' &&
          startOfDay(new Date(task.updatedAt || task.dueDate)).getTime() === date.getTime()
        ).length,
        created: tasks.filter(task =>
          startOfDay(new Date(task.createdAt || task.dueDate)).getTime() === date.getTime()
        ).length,
      };
    });

    return last7Days;
  }, [tasks]);

  return (
    <AnalyticsChart
      type="area"
      data={data}
      dataKey="completed"
      xAxisKey="date"
      title="Task Completion Trend"
      height={250}
      className={className}
    />
  );
};

export const AgentPerformanceChart: React.FC<{ className?: string }> = ({ className }) => {
  const agents = useAppStore((state) => state.agents);

  const data = useMemo(() => {
    return agents.map(agent => ({
      name: agent.name,
      tasksCompleted: agent.performance.tasksCompleted,
      successRate: agent.performance.successRate,
      avgResponseTime: agent.performance.avgResponseTime,
    }));
  }, [agents]);

  return (
    <AnalyticsChart
      type="bar"
      data={data}
      dataKey="tasksCompleted"
      xAxisKey="name"
      title="Agent Performance"
      height={250}
      className={className}
    />
  );
};

export const CommunicationVolumeChart: React.FC<{ className?: string }> = ({ className }) => {
  const messages = useAppStore((state) => state.messages);

  const data = useMemo(() => {
    const platforms = ['gmail', 'slack', 'teams', 'outlook'];
    return platforms.map(platform => ({
      name: platform.charAt(0).toUpperCase() + platform.slice(1),
      value: messages.filter(msg => msg.platform === platform).length,
    })).filter(item => item.value > 0);
  }, [messages]);

  if (data.length === 0) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 ${className}`}>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Communication Volume
        </h3>
        <div className="flex items-center justify-center h-48 text-gray-500 dark:text-gray-400">
          No communication data available
        </div>
      </div>
    );
  }

  return (
    <AnalyticsChart
      type="pie"
      data={data}
      dataKey="value"
      title="Communication Volume by Platform"
      height={250}
      className={className}
    />
  );
};

export const FinancialOverviewChart: React.FC<{ className?: string }> = ({ className }) => {
  const transactions = useAppStore((state) => state.transactions);

  const data = useMemo(() => {
    const last30Days = Array.from({ length: 30 }, (_, i) => {
      const date = startOfDay(subDays(new Date(), 29 - i));
      const dayTransactions = transactions.filter(t =>
        startOfDay(new Date(t.date)).getTime() === date.getTime()
      );

      return {
        date: date.toISOString(),
        income: dayTransactions
          .filter(t => t.type === 'credit')
          .reduce((sum, t) => sum + t.amount, 0),
        expenses: dayTransactions
          .filter(t => t.type === 'debit')
          .reduce((sum, t) => sum + t.amount, 0),
      };
    });

    return last30Days;
  }, [transactions]);

  return (
    <AnalyticsChart
      type="line"
      data={data}
      dataKey="income"
      xAxisKey="date"
      title="Financial Overview (Last 30 Days)"
      height={250}
      className={className}
      showLegend={true}
    />
  );
};
