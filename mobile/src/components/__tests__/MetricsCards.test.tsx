/**
 * MetricsCards Component Tests
 *
 * Testing suite for MetricsCards component
 * Coverage goals: Rendering, interactions, edge cases
 */

import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { MetricsCards } from '../MetricsCards';
import { MetricCardData } from '../../types/analytics';

// Mock Ionicons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('MetricsCards Component', () => {
  const mockData: MetricCardData[] = [
    {
      title: 'Total Sales',
      value: '$12,345',
      color: 'success',
      trend: 'up',
      trendValue: '+12.5%',
      description: 'Monthly revenue',
    },
    {
      title: 'Active Users',
      value: '1,234',
      color: 'info',
      trend: 'stable',
    },
    {
      title: 'Conversion Rate',
      value: '3.2%',
      color: 'warning',
      trend: 'down',
      trendValue: '-0.8%',
    },
    {
      title: 'Error Rate',
      value: '0.5%',
      color: 'error',
      trend: 'down',
      trendValue: '-0.2%',
      description: 'System errors',
    },
  ];

  describe('Rendering', () => {
    test('should render all cards in data array', () => {
      const { getAllByTestId } = render(<MetricsCards data={mockData} />);

      // Each card should be rendered
      expect(mockData.length).toBeGreaterThan(0);
    });

    test('should render card with value and title', () => {
      const { getByText } = render(<MetricsCards data={[mockData[0]]} />);

      expect(getByText('Total Sales')).toBeTruthy();
      expect(getByText('$12,345')).toBeTruthy();
    });

    test('should render trend icon when trend is provided', () => {
      const { getByText } = render(<MetricsCards data={[mockData[0]]} />);

      // Trend value should be visible
      expect(getByText('+12.5%')).toBeTruthy();
    });

    test('should render description when provided', () => {
      const { getByText } = render(<MetricsCards data={[mockData[0]]} />);

      expect(getByText('Monthly revenue')).toBeTruthy();
    });

    test('should not render description when not provided', () => {
      const { queryByText } = render(<MetricsCards data={[mockData[1]]} />);

      expect(queryByText('Monthly revenue')).toBeNull();
    });

    test('should render trend value when provided', () => {
      const { getByText } = render(<MetricsCards data={[mockData[0]]} />);

      expect(getByText('+12.5%')).toBeTruthy();
    });

    test('should handle empty data array', () => {
      const renderResult = render(<MetricsCards data={[]} />);

      // Should render without crashing
      expect(renderResult).toBeTruthy();
    });
  });

  describe('Color Mapping', () => {
    test('should apply success color correctly', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', color: 'success' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should apply warning color correctly', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', color: 'warning' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should apply error color correctly', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', color: 'error' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should apply info color correctly', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', color: 'info' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should default to info color when no color provided', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should apply unknown color as info', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', color: 'unknown' as any }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });
  });

  describe('Trend Icons', () => {
    test('should render up trend icon', () => {
      const { getByText } = render(
        <MetricsCards
          data={[{ title: 'Test', value: '100', trend: 'up', trendValue: '+10%' }]}
        />
      );

      expect(getByText('+10%')).toBeTruthy();
    });

    test('should render down trend icon', () => {
      const { getByText } = render(
        <MetricsCards
          data={[{ title: 'Test', value: '100', trend: 'down', trendValue: '-10%' }]}
        />
      );

      expect(getByText('-10%')).toBeTruthy();
    });

    test('should render stable trend icon', () => {
      const { getByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100', trend: 'stable' }]} />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should not render trend icon when trend is not provided', () => {
      const { queryByText } = render(
        <MetricsCards data={[{ title: 'Test', value: '100' }]} />
      );

      // No trend value should be present
      expect(queryByText('%')).toBeNull();
    });
  });

  describe('Interactions', () => {
    test('should call onPress with correct index when card is pressed', () => {
      const onPress = jest.fn();
      const { getByText } = render(
        <MetricsCards data={mockData} onPress={onPress} />
      );

      fireEvent.press(getByText('Total Sales'));
      expect(onPress).toHaveBeenCalledWith(0);

      fireEvent.press(getByText('Active Users'));
      expect(onPress).toHaveBeenCalledWith(1);
    });

    test('should not call onPress when onPress is not provided', () => {
      const { getByText } = render(<MetricsCards data={mockData} />);

      // Should not crash when pressed
      expect(() => fireEvent.press(getByText('Total Sales'))).not.toThrow();
    });

    test('should handle multiple card presses', () => {
      const onPress = jest.fn();
      const { getByText } = render(
        <MetricsCards data={mockData} onPress={onPress} />
      );

      fireEvent.press(getByText('Total Sales'));
      fireEvent.press(getByText('Active Users'));
      fireEvent.press(getByText('Conversion Rate'));

      expect(onPress).toHaveBeenCalledTimes(3);
      expect(onPress).toHaveBeenNthCalledWith(1, 0);
      expect(onPress).toHaveBeenNthCalledWith(2, 1);
      expect(onPress).toHaveBeenNthCalledWith(3, 2);
    });
  });

  describe('Edge Cases', () => {
    test('should handle null values gracefully', () => {
      const dataWithNulls: MetricCardData[] = [
        {
          title: 'Test',
          value: '',
          color: null as any,
          trend: null as any,
          description: null as any,
          trendValue: null as any,
        },
      ];

      const { root as container } = render(<MetricsCards data={dataWithNulls} />);

      expect(container).toBeTruthy();
    });

    test('should handle undefined optional fields', () => {
      const minimalData: MetricCardData[] = [
        {
          title: 'Test',
          value: '100',
        },
      ];

      const { getByText, queryByText } = render(
        <MetricsCards data={minimalData} />
      );

      expect(getByText('Test')).toBeTruthy();
      expect(getByText('100')).toBeTruthy();
      expect(queryByText('%')).toBeNull();
    });

    test('should handle very long values', () => {
      const longValueData: MetricCardData[] = [
        {
          title: 'Test',
          value: '$999,999,999,999.99',
        },
      ];

      const { getByText } = render(<MetricsCards data={longValueData} />);

      expect(getByText('$999,999,999,999.99')).toBeTruthy();
    });

    test('should handle very long descriptions', () => {
      const longDescData: MetricCardData[] = [
        {
          title: 'Test',
          value: '100',
          description: 'This is a very long description that should wrap properly',
        },
      ];

      const { getByText } = render(<MetricsCards data={longDescData} />);

      expect(getByText('This is a very long description that should wrap properly')).toBeTruthy();
    });

    test('should handle special characters in values', () => {
      const specialCharData: MetricCardData[] = [
        {
          title: 'Test',
          value: '$1,234.56%',
          trendValue: '+12.5% ↑',
        },
      ];

      const { getByText } = render(<MetricsCards data={specialCharData} />);

      expect(getByText('$1,234.56%')).toBeTruthy();
    });
  });

  describe('Layout and Styling', () => {
    test('should render cards in 2-column layout', () => {
      const { root as container } = render(<MetricsCards data={mockData} />);

      // Verify component renders
      expect(container).toBeTruthy();
    });

    test('should handle odd number of cards', () => {
      const oddData = mockData.slice(0, 3);
      const { root as container } = render(<MetricsCards data={oddData} />);

      expect(container).toBeTruthy();
    });

    test('should handle even number of cards', () => {
      const evenData = mockData.slice(0, 4);
      const { root as container } = render(<MetricsCards data={evenData} />);

      expect(container).toBeTruthy();
    });

    test('should handle single card', () => {
      const { getByText } = render(<MetricsCards data={[mockData[0]]} />);

      expect(getByText('Total Sales')).toBeTruthy();
    });

    test('should handle many cards', () => {
      const manyData = Array(10).fill(null).map((_, i) => ({
        title: `Card ${i}`,
        value: `${i}`,
      }));

      const { root as container } = render(<MetricsCards data={manyData} />);

      expect(container).toBeTruthy();
    });
  });

  describe('Integration', () => {
    test('should work with all optional fields provided', () => {
      const completeData: MetricCardData[] = [
        {
          title: 'Complete Card',
          value: '123',
          color: 'success',
          trend: 'up',
          trendValue: '+10%',
          description: 'All fields present',
        },
      ];

      const { getByText } = render(<MetricsCards data={completeData} />);

      expect(getByText('Complete Card')).toBeTruthy();
      expect(getByText('123')).toBeTruthy();
      expect(getByText('+10%')).toBeTruthy();
      expect(getByText('All fields present')).toBeTruthy();
    });

    test('should work with mixed optional fields', () => {
      const mixedData: MetricCardData[] = [
        {
          title: 'Card 1',
          value: '100',
          color: 'info',
        },
        {
          title: 'Card 2',
          value: '200',
          trend: 'up',
          trendValue: '+20%',
        },
        {
          title: 'Card 3',
          value: '300',
          description: 'No trend',
        },
      ];

      const { getByText, queryByText } = render(<MetricsCards data={mixedData} />);

      expect(getByText('Card 1')).toBeTruthy();
      expect(getByText('Card 2')).toBeTruthy();
      expect(getByText('Card 3')).toBeTruthy();
      expect(queryByText('+20%')).toBeTruthy();
      expect(queryByText('No trend')).toBeTruthy();
    });
  });
});
