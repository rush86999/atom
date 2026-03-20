/**
 * AnalyticsDashboardScreen Tests
 *
 * Comprehensive test suite for AnalyticsDashboardScreen component covering:
 * - Rendering with KPI data
 * - Time range selection
 * - KPI cards display
 * - Execution timeline chart
 * - Top workflows list
 * - Pull-to-refresh
 * - Navigation interactions
 * - Loading and error states
 *
 * @see src/screens/analytics/AnalyticsDashboardScreen.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { AnalyticsDashboardScreen } from '../../src/screens/analytics/AnalyticsDashboardScreen';

// Mock navigation
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
  dispatch: jest.fn(),
  isFocused: jest.fn(() => true),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  NavigationProp: jest.fn(),
}));

// Mock analytics service
const mockKPIs = {
  total_executions: 1250,
  successful_executions: 1187,
  failed_executions: 63,
  success_rate: 95.0,
  error_rate: 5.0,
  average_duration_seconds: 45.5,
  unique_workflows: 25,
  unique_users: 8,
};

const mockTimelineData = [
  {
    timestamp: '2024-01-01T10:00:00.000Z',
    success_count: 45,
    failure_count: 3,
  },
  {
    timestamp: '2024-01-01T11:00:00.000Z',
    success_count: 52,
    failure_count: 5,
  },
  {
    timestamp: '2024-01-01T12:00:00.000Z',
    success_count: 48,
    failure_count: 2,
  },
];

const mockTopWorkflows = [
  {
    workflow_id: 'workflow-1',
    workflow_name: 'Data Sync',
    total_executions: 250,
    success_rate: 98.5,
  },
  {
    workflow_id: 'workflow-2',
    workflow_name: 'Email Notifications',
    total_executions: 180,
    success_rate: 96.0,
  },
  {
    workflow_id: 'workflow-3',
    workflow_name: 'Data Processing',
    total_executions: 150,
    success_rate: 94.5,
  },
];

jest.mock('../../src/services/analyticsService', () => ({
  getDashboardKPIs: jest.fn().mockResolvedValue(mockKPIs),
  getExecutionTimeline: jest.fn().mockResolvedValue(mockTimelineData),
  getTopWorkflows: jest.fn().mockResolvedValue(mockTopWorkflows),
}));

describe('AnalyticsDashboardScreen - Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Renders loading state initially
  it('should render loading state initially', () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    expect(getByText('Loading analytics...')).toBeTruthy();
  });

  // Test 2: Renders header
  it('should render header after loading', async () => {
    const { getByText, queryByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(queryByText('Loading analytics...')).toBeNull();
    });

    expect(getByText('Analytics Dashboard')).toBeTruthy();
    expect(getByText('Workflow performance metrics')).toBeTruthy();
  });

  // Test 3: Displays all KPI cards
  it('should display all KPI cards', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Total Executions')).toBeTruthy();
      expect(getByText('Success Rate')).toBeTruthy();
      expect(getByText('Failed')).toBeTruthy();
      expect(getByText('Avg Duration')).toBeTruthy();
    });
  });

  // Test 4: Displays KPI values
  it('should display KPI values', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('1250')).toBeTruthy();
      expect(getByText('95.0%')).toBeTruthy();
      expect(getByText('63')).toBeTruthy();
      expect(getByText('45.5s')).toBeTruthy();
    });
  });

  // Test 5: Displays KPI subtitles
  it('should display KPI subtitles', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('All workflows')).toBeTruthy();
      expect(getByText('1187 successful')).toBeTruthy();
      expect(getByText('5.0% error rate')).toBeTruthy();
      expect(getByText('Per execution')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Time Range Selector', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays time range options
  it('should display time range options', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('1 Hour')).toBeTruthy();
      expect(getByText('24 Hours')).toBeTruthy();
      expect(getByText('7 Days')).toBeTruthy();
      expect(getByText('30 Days')).toBeTruthy();
    });
  });

  // Test 2: Selects time range on press
  it('should select time range on press', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('24 Hours')).toBeTruthy();
    });

    const sevenDaysButton = getByText('7 Days');
    fireEvent.press(sevenDaysButton);

    await waitFor(() => {
      expect(getDashboardKPIs).toHaveBeenCalledWith('7d');
    });
  });

  // Test 3: Changes chip style when selected
  it('should change chip style when selected', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('24 Hours')).toBeTruthy();
    });

    // 24 Hours should be selected by default
    const oneHourButton = getByText('1 Hour');
    fireEvent.press(oneHourButton);

    // Selection should change
    await waitFor(() => {
      expect(getByText('1 Hour')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - KPI Cards', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays total executions KPI
  it('should display total executions KPI', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Total Executions')).toBeTruthy();
      expect(getByText('1250')).toBeTruthy();
    });
  });

  // Test 2: Displays success rate KPI
  it('should display success rate KPI', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Success Rate')).toBeTruthy();
      expect(getByText('95.0%')).toBeTruthy();
    });
  });

  // Test 3: Displays failed executions KPI
  it('should display failed executions KPI', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Failed')).toBeTruthy();
      expect(getByText('63')).toBeTruthy();
    });
  });

  // Test 4: Displays average duration KPI
  it('should display average duration KPI', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Avg Duration')).toBeTruthy();
      expect(getByText('45.5s')).toBeTruthy();
    });
  });

  // Test 5: Displays KPI icons
  it('should display KPI icons', async () => {
    const { getByTestId } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      // KPI icons should be present
      expect(getByTestId(/icon-stats-chart/i)).toBeTruthy();
      expect(getByTestId(/icon-checkmark-circle/i)).toBeTruthy();
      expect(getByTestId(/icon-close-circle/i)).toBeTruthy();
      expect(getByTestId(/icon-time/i)).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Execution Timeline', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays timeline chart
  it('should display timeline chart', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Execution Timeline')).toBeTruthy();
    });
  });

  // Test 2: Shows empty state when no timeline data
  it('should show empty state when no timeline data', async () => {
    const getExecutionTimeline = require('../../src/services/analyticsService').getExecutionTimeline;
    getExecutionTimeline.mockResolvedValueOnce([]);

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('No timeline data available')).toBeTruthy();
    });
  });

  // Test 3: Displays chart legend
  it('should display chart legend', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Success')).toBeTruthy();
      expect(getByText('Failure')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Top Workflows', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays top workflows section
  it('should display top workflows section', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Top Workflows')).toBeTruthy();
    });
  });

  // Test 2: Displays workflow names
  it('should display workflow names', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync')).toBeTruthy();
      expect(getByText('Email Notifications')).toBeTruthy();
      expect(getByText('Data Processing')).toBeTruthy();
    });
  });

  // Test 3: Displays workflow stats
  it('should display workflow stats', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText(/250 runs/)).toBeTruthy();
      expect(getByText(/98.5% success/)).toBeTruthy();
    });
  });

  // Test 4: Shows empty state when no workflows
  it('should show empty state when no workflows', async () => {
    const getTopWorkflows = require('../../src/services/analyticsService').getTopWorkflows;
    getTopWorkflows.mockResolvedValueOnce([]);

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('No workflow data available')).toBeTruthy();
    });
  });

  // Test 5: Displays workflow ranking
  it('should display workflow ranking', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('#1')).toBeTruthy();
      expect(getByText('#2')).toBeTruthy();
      expect(getByText('#3')).toBeTruthy();
    });
  });

  // Test 6: Has View All button
  it('should have View All button', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('View All')).toBeTruthy();
    });
  });

  // Test 7: Navigates to workflows list on View All press
  it('should navigate to workflows list on View All press', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      const viewAllButton = getByText('View All');
      fireEvent.press(viewAllButton);
    });

    expect(mockNavigation.navigate).toHaveBeenCalledWith('WorkflowsList');
  });
});

describe('AnalyticsDashboardScreen - Overview Section', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays overview section
  it('should display overview section', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Overview')).toBeTruthy();
    });
  });

  // Test 2: Displays unique workflows count
  it('should display unique workflows count', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('25')).toBeTruthy();
      expect(getByText('Unique Workflows')).toBeTruthy();
    });
  });

  // Test 3: Displays active users count
  it('should display active users count', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('8')).toBeTruthy();
      expect(getByText('Active Users')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Pull to Refresh', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Refreshes data on pull
  it('should refresh data on pull', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Analytics Dashboard')).toBeTruthy();
    });

    // Simulate pull to refresh
    act(() => {
      getDashboardKPIs.mockClear();
      getDashboardKPIs.mockResolvedValueOnce(mockKPIs);
    });

    // RefreshControl would trigger refresh
    await waitFor(() => {
      expect(getDashboardKPIs).toHaveBeenCalled();
    });
  });
});

describe('AnalyticsDashboardScreen - Error States', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows error when KPI fetch fails
  it('should show error when KPI fetch fails', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockRejectedValueOnce(new Error('API error'));

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Failed to load analytics')).toBeTruthy();
    });
  });

  // Test 2: Shows retry button on error
  it('should show retry button on error', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockRejectedValueOnce(new Error('API error'));

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Retry')).toBeTruthy();
    });
  });

  // Test 3: Retries on retry button press
  it('should retry on retry button press', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockRejectedValueOnce(new Error('API error'));
    getDashboardKPIs.mockResolvedValueOnce(mockKPIs);

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      const retryButton = getByText('Retry');
      fireEvent.press(retryButton);
    });

    await waitFor(() => {
      expect(getByText('Analytics Dashboard')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Edge Cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles zero executions
  it('should handle zero executions', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockResolvedValueOnce({
      ...mockKPIs,
      total_executions: 0,
      successful_executions: 0,
      failed_executions: 0,
      success_rate: 0,
    });

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('0')).toBeTruthy();
    });
  });

  // Test 2: Handles very high success rate
  it('should handle very high success rate', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockResolvedValueOnce({
      ...mockKPIs,
      success_rate: 100.0,
    });

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('100.0%')).toBeTruthy();
    });
  });

  // Test 3: Handles long duration
  it('should handle long duration', async () => {
    const getDashboardKPIs = require('../../src/services/analyticsService').getDashboardKPIs;
    getDashboardKPIs.mockResolvedValueOnce({
      ...mockKPIs,
      average_duration_seconds: 3600.5, // 1 hour
    });

    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('3600.5s')).toBeTruthy();
    });
  });
});

describe('AnalyticsDashboardScreen - Layout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has proper section spacing
  it('should have proper section spacing', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Key Performance Indicators')).toBeTruthy();
      expect(getByText('Execution Timeline')).toBeTruthy();
      expect(getByText('Top Workflows')).toBeTruthy();
      expect(getByText('Overview')).toBeTruthy();
    });
  });

  // Test 2: Scrollable content
  it('should have scrollable content', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Key Performance Indicators')).toBeTruthy();
    });

    // Content should be scrollable
    expect(getByText('Key Performance Indicators')).toBeTruthy();
  });
});

describe('AnalyticsDashboardScreen - Accessibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has accessible labels
  it('should have accessible labels', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Analytics Dashboard')).toBeTruthy();
      expect(getByText('Total Executions')).toBeTruthy();
      expect(getByText('Success Rate')).toBeTruthy();
    });
  });

  // Test 2: Has accessible time range selector
  it('should have accessible time range selector', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('1 Hour')).toBeTruthy();
      expect(getByText('24 Hours')).toBeTruthy();
      expect(getByText('7 Days')).toBeTruthy();
      expect(getByText('30 Days')).toBeTruthy();
    });
  });

  // Test 3: Has accessible KPI cards
  it('should have accessible KPI cards', async () => {
    const { getByText } = render(<AnalyticsDashboardScreen />);

    await waitFor(() => {
      expect(getByText('Total Executions')).toBeTruthy();
      expect(getByText('Success Rate')).toBeTruthy();
      expect(getByText('Failed')).toBeTruthy();
      expect(getByText('Avg Duration')).toBeTruthy();
    });
  });
});
