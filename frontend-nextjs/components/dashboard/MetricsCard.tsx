/**
 * Metrics Card Component
 * Reusable card component for displaying dashboard metrics
 */

import React from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  LucideIcon,
} from 'lucide-react';

export interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  progress?: number;
  variant?: 'default' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md' | 'lg';
  footer?: React.ReactNode;
}

const MetricsCard: React.FC<MetricCardProps> = ({
  title,
  value,
  description,
  icon,
  trend,
  trendValue,
  progress,
  variant = 'default',
  size = 'md',
  footer,
}) => {
  const getVariantClasses = () => {
    switch (variant) {
      case 'success':
        return 'border-green-500 bg-green-50';
      case 'warning':
        return 'border-yellow-500 bg-yellow-50';
      case 'error':
        return 'border-red-500 bg-red-50';
      default:
        return '';
    }
  };

  const getTrendIcon = () => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'down':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <Minus className="h-4 w-4 text-gray-500" />;
    }
  };

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'text-lg font-bold';
      case 'lg':
        return 'text-4xl font-bold';
      default:
        return 'text-2xl font-bold';
    }
  };

  return (
    <Card className={getVariantClasses()}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className={`flex items-baseline justify-between ${getSizeClasses()}`}>
          <div>{value}</div>
          {trend && (
            <div className="flex items-center gap-1 text-sm">
              {getTrendIcon()}
              {trendValue && <span className="text-muted-foreground">{trendValue}</span>}
            </div>
          )}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
        {typeof progress === 'number' && (
          <div className="mt-3">
            <Progress value={progress} className="h-2" />
          </div>
        )}
        {footer && (
          <div className="mt-3 pt-3 border-t">
            {footer}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MetricsCard;
