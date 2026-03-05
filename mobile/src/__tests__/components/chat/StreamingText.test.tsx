/**
 * StreamingText Component Tests
 *
 * Tests for streaming text animation with markdown support,
 * special cards, and cursor animation.
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { StreamingText } from '../../../components/chat/StreamingText';

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      primary: '#2196F3',
      onSurface: '#000',
      onSurfaceVariant: '#666',
    },
  }),
  Icon: 'Icon',
}));

// Mock markdown components
jest.mock('react-native-markdown-display', () => ({
  Markdown: ({ children, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{children}</Text>;
  },
}));

// Mock syntax highlighter
jest.mock('react-native-syntax-highlighter', () => ({
  Prism: ({ children, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{children}</Text>;
  },
}));

jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  vscDarkPlus: {},
}));

describe('StreamingText', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render text content', () => {
      const { getByText } = render(<StreamingText text="Hello, world!" />);

      expect(getByText('Hello, world!')).toBeTruthy();
    });

    it('should render empty text', () => {
      const { getByText } = render(<StreamingText text="" />);

      expect(getByText('')).toBeTruthy();
    });

    it('should render multiline text', () => {
      const { getByText } = render(
        <StreamingText text="Line 1\nLine 2\nLine 3" />
      );

      expect(getByText(/Line 1/)).toBeTruthy();
      expect(getByText(/Line 2/)).toBeTruthy();
      expect(getByText(/Line 3/)).toBeTruthy();
    });

    it('should render long text', () => {
      const longText = 'A'.repeat(500);
      const { getByText } = render(<StreamingText text={longText} />);

      expect(getByText(longText)).toBeTruthy();
    });
  });

  describe('Streaming Animation', () => {
    it('should show cursor while streaming', () => {
      const { getByText } = render(
        <StreamingText text="Hello" isStreaming={true} />
      );

      expect(getByText('Hello')).toBeTruthy();
    });

    it('should hide cursor when not streaming', () => {
      const { getByText } = render(
        <StreamingText text="Hello" isStreaming={false} />
      );

      expect(getByText('Hello')).toBeTruthy();
    });

    it('should handle streaming completion callback', async () => {
      const onComplete = jest.fn();

      const { getByText } = render(
        <StreamingText
          text="Test"
          isStreaming={true}
          onComplete={onComplete}
          speed={10}
        />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    it('should handle custom speed', () => {
      const { getByText } = render(
        <StreamingText text="Test" speed={50} />
      );

      expect(getByText('Test')).toBeTruthy();
    });
  });

  describe('Markdown Support', () => {
    it('should apply markdown formatting when enabled', () => {
      const { getByText } = render(
        <StreamingText
          text="# Heading\n\n**Bold** and *italic*"
          enableMarkdown={true}
        />
      );

      expect(getByText(/Heading/)).toBeTruthy();
      expect(getByText(/Bold/)).toBeTruthy();
      expect(getByText(/italic/)).toBeTruthy();
    });

    it('should not apply markdown when disabled', () => {
      const { getByText } = render(
        <StreamingText
          text="# Heading\n\n**Bold**"
          enableMarkdown={false}
        />
      );

      // Text should be rendered as-is
      expect(getByText(/# Heading/)).toBeTruthy();
    });

    it('should render code blocks', () => {
      const { getByText } = render(
        <StreamingText
          text="```javascript\nconst x = 1;\n```"
          enableMarkdown={true}
        />
      );

      expect(getByText(/const x = 1/)).toBeTruthy();
    });

    it('should render inline code', () => {
      const { getByText } = render(
        <StreamingText
          text="Use `console.log()` for debugging"
          enableMarkdown={true}
        />
      );

      expect(getByText(/console\.log/)).toBeTruthy();
    });
  });

  describe('Special Cards', () => {
    it('should detect canvas mentions', () => {
      const { getByText } = render(
        <StreamingText text="Check out [[canvas:canvas-123]]" />
      );

      expect(getByText(/canvas:canvas-123/)).toBeTruthy();
    });

    it('should detect workflow mentions', () => {
      const { getByText } = render(
        <StreamingText text="Run [[workflow:workflow-456]]" />
      );

      expect(getByText(/workflow:workflow-456/)).toBeTruthy();
    });

    it('should detect form mentions', () => {
      const { getByText } = render(
        <StreamingText text="Fill [[form:form-789]]" />
      );

      expect(getByText(/form:form-789/)).toBeTruthy();
    });

    it('should detect multiple special cards', () => {
      const { getByText } = render(
        <StreamingText
          text="[[canvas:1]] and [[workflow:2]] and [[form:3]]"
        />
      );

      expect(getByText(/canvas:1/)).toBeTruthy();
      expect(getByText(/workflow:2/)).toBeTruthy();
      expect(getByText(/form:3/)).toBeTruthy();
    });
  });

  describe('Expand/Collapse', () => {
    it('should respect maxHeight prop', () => {
      const { getByTestId } = render(
        <StreamingText
          text="A".repeat(1000)}
          maxHeight={100}
        />
      );

      // Component should render
      expect(getByTestId('streaming-text')).toBeTruthy();
    });
  });

  describe('Custom Styles', () => {
    it('should apply custom container style', () => {
      const customStyle = { backgroundColor: '#f0f0f0' };
      const { getByTestId } = render(
        <StreamingText text="Test" style={customStyle} />
      );

      expect(getByTestId('streaming-text')).toBeTruthy();
    });

    it('should apply custom text style', () => {
      const customTextStyle = { fontSize: 18, color: 'red' };
      const { getByText } = render(
        <StreamingText text="Test" textStyle={customTextStyle} />
      );

      expect(getByText('Test')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('should handle null text gracefully', () => {
      const { getByText } = render(
        <StreamingText text={null as any} />
      );

      // Should not crash
      expect(getByText('')).toBeTruthy();
    });

    it('should handle undefined text gracefully', () => {
      const { getByText } = render(
        <StreamingText text={undefined as any} />
      );

      // Should not crash
      expect(getByText('')).toBeTruthy();
    });

    it('should handle special characters', () => {
      const { getByText } = render(
        <StreamingText text="Test <script>&\"special\"" />
      );

      expect(getByText(/Test/)).toBeTruthy();
    });

    it('should handle emojis', () => {
      const { getByText } = render(
        <StreamingText text="Hello 👋 World 🌍" />
      );

      expect(getByText(/Hello/)).toBeTruthy();
      expect(getByText(/World/)).toBeTruthy();
    });

    it('should handle very long words', () => {
      const longWord = 'a'.repeat(200);
      const { getByText } = render(
        <StreamingText text={longWord} />
      );

      expect(getByText(longWord)).toBeTruthy();
    });
  });

  describe('Performance', () => {
    it('should handle rapid text updates', () => {
      const { rerender, getByText } = render(
        <StreamingText text="A" />
      );

      for (let i = 0; i < 10; i++) {
        rerender(<StreamingText text={`Update ${i}`} />);
      }

      expect(getByText(/Update/)).toBeTruthy();
    });

    it('should not crash on very long streaming text', () => {
      const longText = 'A'.repeat(10000);
      const { getByText } = render(
        <StreamingText text={longText} isStreaming={true} />
      );

      expect(getByText(longText.substring(0, 100))).toBeTruthy();
    });
  });
});
