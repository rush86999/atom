import { ReactElement } from 'react';

// Mock all Recharts components for testing
// This allows tests to verify component rendering without actual SVG rendering

export const ResponsiveContainer = ({ children, width, height }: any) => (
  <div data-testid="recharts-responsive-container" className="recharts-responsive-container" style={{ width, height }}>
    {children}
  </div>
);

export const LineChart = ({ children, data }: any) => (
  <div data-testid="recharts-line-chart" data-data={JSON.stringify(data)}>
    {children}
  </div>
);

export const PieChart = ({ children, data }: any) => (
  <div data-testid="recharts-pie-chart" data-data={JSON.stringify(data)}>
    {children}
  </div>
);

export const BarChart = ({ children, data }: any) => (
  <div data-testid="recharts-bar-chart">{children}</div>
);

export const AreaChart = ({ children, data }: any) => (
  <div data-testid="recharts-area-chart">{children}</div>
);

export const XAxis = () => <div data-testid="recharts-x-axis" />;
export const YAxis = () => <div data-testid="recharts-y-axis" />;
export const CartesianGrid = () => <div data-testid="recharts-cartesian-grid" />;
export const Tooltip = () => <div data-testid="recharts-tooltip" />;
export const Legend = () => <div data-testid="recharts-legend" />;

export const Line = ({ name, dataKey, stroke }: any) => (
  <div data-testid="recharts-line" data-name={name} data-stroke={stroke} />
);

export const Bar = ({ name, dataKey, fill }: any) => (
  <div data-testid="recharts-bar" data-name={name} data-fill={fill} />
);

export const Area = ({ name, dataKey, fill }: any) => (
  <div data-testid="recharts-area" data-name={name} data-fill={fill} />
);

export const Pie = ({ name, dataKey, fill, label, children }: any) => (
  <div data-testid="recharts-pie" data-name={name} data-fill={fill}>
    {children}
  </div>
);

export const Cell = ({ fill }: any) => (
  <div data-testid="recharts-cell" data-fill={fill} />
);
