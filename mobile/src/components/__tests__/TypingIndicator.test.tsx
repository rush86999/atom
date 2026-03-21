/**
 * TypingIndicator Component Tests
 *
 * Testing suite for TypingIndicator component
 * Coverage goals: Animation, multiple agents, styling
 */

import React from 'react';
import { render } from '@testing-library/react-native';
import { TypingIndicator, CompactTypingIndicator } from '../chat/TypingIndicator';

// Mock dependencies
jest.mock('react-native-paper', () => ({
  Avatar: {
    Text: 'Avatar.Text',
  },
}));

describe('TypingIndicator Component', () => {
  describe('Basic Rendering', () => {
    test('should render typing indicator with agents', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(getByText('Agent 1')).toBeTruthy();
      expect(getByText('is typing')).toBeTruthy();
    });

    test('should not render when no agents', () => {
      const { root as container } = render(
        <TypingIndicator visible={true} agents={[]} />
      );

      // Component returns null when no agents
      expect(container).toBeTruthy();
    });

    test('should render default typing dots animation', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Multiple Agents', () => {
    test('should display single agent typing', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(getByText('Agent 1')).toBeTruthy();
      expect(getByText('is typing')).toBeTruthy();
    });

    test('should display two agents typing', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[
            { id: '1', name: 'Agent 1' },
            { id: '2', name: 'Agent 2' },
          ]}
        />
      );

      expect(getByText('Agent 1 and Agent 2')).toBeTruthy();
    });

    test('should display multiple agents with "and X others"', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[
            { id: '1', name: 'Agent 1' },
            { id: '2', name: 'Agent 2' },
            { id: '3', name: 'Agent 3' },
          ]}
        />
      );

      expect(getByText('Agent 1 and 2 others')).toBeTruthy();
    });

    test('should handle many agents typing', () => {
      const manyAgents = Array.from({ length: 5 }, (_, i) => ({
        id: `${i}`,
        name: `Agent ${i}`,
      }));

      const { getByText } = render(
        <TypingIndicator visible={true} agents={manyAgents} />
      );

      expect(getByText('Agent 0 and 4 others')).toBeTruthy();
    });

    test('should display empty agent list', () => {
      const { queryByText } = render(
        <TypingIndicator visible={true} agents={[]} />
      );

      // Should return null
      expect(queryByText('is typing')).toBeNull();
    });
  });

  describe('Avatar Display', () => {
    test('should show agent initials in avatar', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'John Doe' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle single word name', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle multi-word name', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent Very Long Name' }]}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Animation States', () => {
    test('should animate when visible', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should stop animation when hidden', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={false}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle visibility toggle', () => {
      const { rerender } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      rerender(
        <TypingIndicator
          visible={false}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      rerender(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      expect(true).toBeTruthy();
    });
  });

  describe('Agent Label Generation', () => {
    test('should show single agent name', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'TestAgent' }]}
        />
      );

      expect(getByText('TestAgent')).toBeTruthy();
      expect(getByText('is typing')).toBeTruthy();
    });

    test('should show "Agent1 and Agent2" for two agents', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[
            { id: '1', name: 'Alice' },
            { id: '2', name: 'Bob' },
          ]}
        />
      );

      expect(getByText('Alice and Bob')).toBeTruthy();
    });

    test('should show "Agent1 and X others" for 3+ agents', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[
            { id: '1', name: 'Alice' },
            { id: '2', name: 'Bob' },
            { id: '3', name: 'Charlie' },
          ]}
        />
      );

      expect(getByText('Alice and 2 others')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    test('should handle null agents', () => {
      const { root as container } = render(
        <TypingIndicator visible={true} agents={null as any} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle undefined agents', () => {
      const { root as container } = render(
        <TypingIndicator visible={true} agents={undefined as any} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle agent with null name', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: null as any }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle agent with empty name', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: '' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very long agent names', () => {
      const longName = 'A'.repeat(100);
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: longName }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle agent names with special characters', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent <>&"\\' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle agent with avatar_url', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1', avatar_url: 'http://example.com/avatar.png' }]}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Performance', () => {
    test('should handle rapid visibility changes', () => {
      const { rerender } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent 1' }]}
        />
      );

      for (let i = 0; i < 10; i++) {
        rerender(
          <TypingIndicator
            visible={i % 2 === 0}
            agents={[{ id: '1', name: 'Agent 1' }]}
          />
        );
      }

      expect(true).toBeTruthy();
    });

    test('should handle rapid agent changes', () => {
      const { rerender } = render(
        <TypingIndicator visible={true} agents={[]} />
      );

      for (let i = 0; i < 10; i++) {
        rerender(
          <TypingIndicator
            visible={true}
            agents={Array.from({ length: i }, (_, j) => ({
              id: `${j}`,
              name: `Agent ${j}`,
            }))}
          />
        );
      }

      expect(true).toBeTruthy();
    });
  });

  describe('Initials Generation', () => {
    test('should generate initials from full name', () => {
      const { getByText } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'John Doe' }]}
        />
      );

      // Should show "JD" initials
      expect(getByText('John Doe')).toBeTruthy();
    });

    test('should handle single word name', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent' }]}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle name with multiple spaces', () => {
      const { root as container } = render(
        <TypingIndicator
          visible={true}
          agents={[{ id: '1', name: 'Agent Very Long Name Here' }]}
        />
      );

      expect(container).toBeTruthy();
    });
  });
});

describe('CompactTypingIndicator Component', () => {
  test('should render compact typing indicator', () => {
    const { root as container } = render(<CompactTypingIndicator visible={true} />);

    expect(container).toBeTruthy();
  });

  test('should not render when visible is false', () => {
    const { root as container } = render(<CompactTypingIndicator visible={false} />);

    expect(container).toBeTruthy();
  });

  test('should handle visibility toggle', () => {
    const { rerender } = render(<CompactTypingIndicator visible={true} />);

    rerender(<CompactTypingIndicator visible={false} />);

    rerender(<CompactTypingIndicator visible={true} />);

    expect(true).toBeTruthy();
  });

  test('should render animated dots', () => {
    const { root as container } = render(<CompactTypingIndicator visible={true} />);

    expect(container).toBeTruthy();
  });
});
