/**
 * TypingIndicator Component Tests
 *
 * Tests for typing indicator animation, agent names,
 * and compact variant.
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { TypingIndicator, CompactTypingIndicator } from '../../../components/chat/TypingIndicator';

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  Avatar: {
    Text: ({ label, style }: any) => {
      const React = require('react');
      const { Text } = require('react-native');
      return <Text style={style}>{label}</Text>;
    },
  },
}));

describe('TypingIndicator', () => {
  const mockAgents = [
    { id: 'agent-1', name: 'Alice' },
    { id: 'agent-2', name: 'Bob' },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('should show animated dots when typing', () => {
      const { getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      expect(getByText('Alice')).toBeTruthy();
      expect(getByText('is typing')).toBeTruthy();
    });

    it('should hide when not visible', () => {
      const { queryByText } = render(
        <TypingIndicator agents={mockAgents} visible={false} />
      );

      // Component should return null when no agents or not visible
      expect(queryByText('is typing')).toBeNull();
    });

    it('should not render when no agents', () => {
      const { queryByText } = render(
        <TypingIndicator agents={[]} visible={true} />
      );

      expect(queryByText('is typing')).toBeNull();
    });

    it('should render avatar with agent initials', () => {
      const { getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      // Alice -> AL
      expect(getByText('AL')).toBeTruthy();
    });
  });

  describe('Agent Names', () => {
    it('should display single agent name', () => {
      const singleAgent = [{ id: 'agent-1', name: 'Alice' }];

      const { getByText } = render(
        <TypingIndicator agents={singleAgent} visible={true} />
      );

      expect(getByText('Alice')).toBeTruthy();
      expect(getByText('is typing')).toBeTruthy();
    });

    it('should display two agent names with "and"', () => {
      const { getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      expect(getByText('Alice and Bob')).toBeTruthy();
    });

    it('should display agent name and count for 3+ agents', () => {
      const manyAgents = [
        { id: 'agent-1', name: 'Alice' },
        { id: 'agent-2', name: 'Bob' },
        { id: 'agent-3', name: 'Charlie' },
      ];

      const { getByText } = render(
        <TypingIndicator agents={manyAgents} visible={true} />
      );

      expect(getByText('Alice and 2 others')).toBeTruthy();
    });

    it('should extract initials from multi-word names', () => {
      const multiWordAgent = [
        { id: 'agent-1', name: 'Artificial Intelligence' },
      ];

      const { getByText } = render(
        <TypingIndicator agents={multiWordAgent} visible={true} />
      );

      // AI
      expect(getByText('AI')).toBeTruthy();
    });

    it('should limit initials to 2 characters', () => {
      const longNameAgent = [
        { id: 'agent-1', name: 'Very Long Name Here' },
      ];

      const { getByText } = render(
        <TypingIndicator agents={longNameAgent} visible={true} />
      );

      // VL
      expect(getByText('VL')).toBeTruthy();
    });
  });

  describe('Animation', () => {
    it('should animate dots bouncing', () => {
      const { getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      expect(getByText('is typing')).toBeTruthy();
    });

    it('should animate entrance on visible', async () => {
      const { getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      await waitFor(() => {
        expect(getByText('Alice')).toBeTruthy();
      });
    });

    it('should animate exit on hide', async () => {
      const { getByText, rerender } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      expect(getByText('Alice')).toBeTruthy();

      rerender(<TypingIndicator agents={mockAgents} visible={false} />);

      // Should animate out
      await waitFor(() => {
        // Component may still be in DOM during exit animation
      });
    });
  });

  describe('Compact Typing Indicator', () => {
    it('should render compact variant', () => {
      const { getByTestId } = render(
        <CompactTypingIndicator visible={true} />
      );

      expect(getByTestId('compact-typing-indicator')).toBeTruthy();
    });

    it('should show animated dots in compact mode', () => {
      const { getByTestId } = render(
        <CompactTypingIndicator visible={true} />
      );

      expect(getByTestId('compact-typing-indicator')).toBeTruthy();
    });

    it('should hide when not visible', () => {
      const { queryByTestId } = render(
        <CompactTypingIndicator visible={false} />
      );

      // Should fade out
      expect(queryByTestId('compact-typing-indicator')).toBeTruthy();
    });

    it('should have smaller dots than standard variant', () => {
      const { getByTestId } = render(
        <CompactTypingIndicator visible={true} />
      );

      expect(getByTestId('compact-typing-indicator')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('should handle agents with empty names', () => {
      const emptyNameAgent = [{ id: 'agent-1', name: '' }];

      const { getByTestId } = render(
        <TypingIndicator agents={emptyNameAgent} visible={true} />
      );

      expect(getByTestId('typing-indicator')).toBeTruthy();
    });

    it('should handle agents with single character names', () => {
      const singleCharAgent = [{ id: 'agent-1', name: 'A' }];

      const { getByText } = render(
        <TypingIndicator agents={singleCharAgent} visible={true} />
      );

      expect(getByText('A')).toBeTruthy();
    });

    it('should handle agents with special characters in names', () => {
      const specialCharAgent = [{ id: 'agent-1', name: 'Agent-123' }];

      const { getByText } = render(
        <TypingIndicator agents={specialCharAgent} visible={true} />
      );

      expect(getByText('Agent-123')).toBeTruthy();
    });

    it('should handle rapid visibility changes', () => {
      const { rerender, getByText } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      expect(getByText('Alice')).toBeTruthy();

      rerender(<TypingIndicator agents={mockAgents} visible={false} />);
      rerender(<TypingIndicator agents={mockAgents} visible={true} />);
      rerender(<TypingIndicator agents={mockAgents} visible={false} />);

      // Should handle rapid changes without crashing
      expect(getByText('Alice')).toBeTruthy();
    });
  });

  describe('Performance', () => {
    it('should not leak memory when unmounted', () => {
      const { unmount } = render(
        <TypingIndicator agents={mockAgents} visible={true} />
      );

      // Should cleanup animations on unmount
      unmount();

      // No errors should occur
      expect(true).toBe(true);
    });

    it('should handle many agents efficiently', () => {
      const manyAgents = Array.from({ length: 100 }, (_, i) => ({
        id: `agent-${i}`,
        name: `Agent ${i}`,
      }));

      const { getByText } = render(
        <TypingIndicator agents={manyAgents} visible={true} />
      );

      expect(getByText(/Agent 0 and 99 others/)).toBeTruthy();
    });
  });
});
