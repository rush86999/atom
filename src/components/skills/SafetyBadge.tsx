/**
 * SafetyBadge Component
 *
 * Displays skill safety level with color coding.
 * Six levels: UNKNOWN (gray), SAFE (green), LOW_RISK (blue),
 * MEDIUM_RISK (yellow), HIGH_RISK (orange), BLOCKED (red).
 */

import React from 'react';
import { getSafetyColorClass, getSafetyLabel, getSafetyIcon, SafetyLevel } from '@/lib/openclaw/openclaw-scans';

interface SafetyBadgeProps {
  level: SafetyLevel;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function SafetyBadge({ level, showIcon = true, size = 'md' }: SafetyBadgeProps) {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-full font-medium
        ${getSafetyColorClass(level)}
        ${sizeClasses[size]}
      `}
      title={`Safety Level: ${getSafetyLabel(level)}`}
    >
      {showIcon && <span>{getSafetyIcon(level)}</span>}
      <span>{getSafetyLabel(level)}</span>
    </span>
  );
}

export default SafetyBadge;
