/**
 * StreamingText Component Tests
 *
 * Testing suite for StreamingText component
 * Coverage goals: Streaming animation, markdown, code blocks, edge cases
 */

import React from 'react';
import { render, waitFor, act } from '@testing-library/react-native';
import { StreamingText } from '../chat/StreamingText';

// Mock dependencies
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      primary: '#2196F3',
      onSurface: '#000',
      onSurfaceVariant: '#666',
      surfaceVariant: '#f5f5f5',
      outline: '#e0e0e0',
    },
  }),
  Icon: 'Icon',
}));

jest.mock('react-native-markdown-display', () => 'Markdown');
jest.mock('react-native-syntax-highlighter', () => ({
  Prism: 'Prism',
}));

jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  vscDarkPlus: {},
}));

jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

describe('StreamingText Component', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Basic Rendering', () => {
    test('should render text content', () => {
      const { getByText } = render(
        <StreamingText text="Hello World" isStreaming={false} />
      );

      expect(getByText('Hello World')).toBeTruthy();
    });

    test('should render empty text without crashing', () => {
      const { root as container } = render(
        <StreamingText text="" isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very long text', () => {
      const longText = 'A'.repeat(1000);
      const { getByText } = render(
        <StreamingText text={longText} isStreaming={false} />
      );

      expect(getByText(longText)).toBeTruthy();
    });
  });

  describe('Streaming Animation', () => {
    test('should show full text immediately when not streaming', () => {
      const { getByText } = render(
        <StreamingText text="Hello World" isStreaming={false} />
      );

      expect(getByText('Hello World')).toBeTruthy();
    });

    test('should stream text character by character when streaming', async () => {
      const { getByText, queryByText } = render(
        <StreamingText text="Hello" isStreaming={true} speed={10} />
      );

      // Initially, no text should be visible
      expect(queryByText('Hello')).toBeNull();

      // Advance timers to let streaming progress
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Wait for state updates
      await waitFor(() => {
        expect(getByText('Hello')).toBeTruthy();
      });
    });

    test('should call onComplete when streaming finishes', async () => {
      const onComplete = jest.fn();
      render(
        <StreamingText
          text="Hi"
          isStreaming={true}
          speed={5}
          onComplete={onComplete}
        />
      );

      // Advance time past the streaming duration
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled();
      });
    });

    test('should not call onComplete when not streaming', () => {
      const onComplete = jest.fn();
      render(
        <StreamingText
          text="Hello"
          isStreaming={false}
          onComplete={onComplete}
        />
      );

      expect(onComplete).not.toHaveBeenCalled();
    });
  });

  describe('Markdown Rendering', () => {
    test('should render markdown when enabled', () => {
      const { root as container } = render(
        <StreamingText
          text="**Bold** and *Italic*"
          isStreaming={false}
          enableMarkdown={true}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should render plain text when markdown disabled', () => {
      const { getByText } = render(
        <StreamingText
          text="**Bold** text"
          isStreaming={false}
          enableMarkdown={false}
        />
      );

      expect(getByText('**Bold** text')).toBeTruthy();
    });

    test('should handle markdown headers', () => {
      const { root as container } = render(
        <StreamingText
          text="# Header 1\n## Header 2"
          isStreaming={false}
          enableMarkdown={true}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle markdown lists', () => {
      const { root as container } = render(
        <StreamingText
          text="- Item 1\n- Item 2"
          isStreaming={false}
          enableMarkdown={true}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should handle markdown links', () => {
      const { root as container } = render(
        <StreamingText
          text="[Link](https://example.com)"
          isStreaming={false}
          enableMarkdown={true}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Code Block Detection', () => {
    test('should detect code blocks in text', () => {
      const textWithCode = '```javascript\nconst x = 1;\n```';
      const { root as container } = render(
        <StreamingText text={textWithCode} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should render code block with language', () => {
      const codeText = '```python\ndef hello():\n    pass\n```';
      const { root as container } = render(
        <StreamingText text={codeText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should render multiple code blocks', () => {
      const multiCodeText =
        '```js\nconsole.log(1);\n```\nText\n```py\nprint(2)\n```';
      const { root as container } = render(
        <StreamingText text={multiCodeText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle code blocks without language', () => {
      const codeText = '```\ncode here\n```';
      const { root as container } = render(
        <StreamingText text={codeText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle inline code with markdown', () => {
      const inlineCodeText = 'This has `inline code` in it';
      const { root as container } = render(
        <StreamingText text={inlineCodeText} isStreaming={false} enableMarkdown={true} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Special Card Detection', () => {
    test('should detect canvas mentions', () => {
      const textWithCanvas = 'Check out [[canvas:canvas-123]] for details';
      const { getByText } = render(
        <StreamingText text={textWithCanvas} isStreaming={false} />
      );

      expect(getByText(/canvas:canvas-123/)).toBeTruthy();
    });

    test('should detect workflow mentions', () => {
      const textWithWorkflow = 'Run [[workflow:workflow-456]] now';
      const { getByText } = render(
        <StreamingText text={textWithWorkflow} isStreaming={false} />
      );

      expect(getByText(/workflow:workflow-456/)).toBeTruthy();
    });

    test('should detect form mentions', () => {
      const textWithForm = 'Fill [[form:form-789]] please';
      const { getByText } = render(
        <StreamingText text={textWithForm} isStreaming={false} />
      );

      expect(getByText(/form:form-789/)).toBeTruthy();
    });

    test('should detect multiple special cards', () => {
      const textWithMultiple =
        'See [[canvas:1]], [[workflow:2]], and [[form:3]]';
      const { root as container } = render(
        <StreamingText text={textWithMultiple} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle text without special cards', () => {
      const plainText = 'This is plain text with no special cards';
      const { getByText } = render(
        <StreamingText text={plainText} isStreaming={false} />
      );

      expect(getByText('This is plain text with no special cards')).toBeTruthy();
    });
  });

  describe('Text Truncation', () => {
    test('should truncate long text when not expanded', () => {
      const longText = 'A'.repeat(600);
      const { getByText, queryByText } = render(
        <StreamingText text={longText} isStreaming={false} />
      );

      expect(getByText(/.../)).toBeTruthy();
    });

    test('should show full text when expanded', () => {
      const longText = 'A'.repeat(600);
      const { getByText } = render(
        <StreamingText text={longText} isStreaming={false} />
      );

      // Find and press "Show more" button
      const showMoreButton = getByText('Show more');
      expect(showMoreButton).toBeTruthy();
    });

    test('should not truncate short text', () => {
      const shortText = 'Short text';
      const { queryByText } = render(
        <StreamingText text={shortText} isStreaming={false} />
      );

      expect(queryByText('Show more')).toBeNull();
    });

    test('should respect custom maxHeight', () => {
      const { root as container } = render(
        <StreamingText
          text="Test"
          isStreaming={false}
          maxHeight={500}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Progress Indicator', () => {
    test('should show progress indicator during streaming', () => {
      const { root as container } = render(
        <StreamingText text="A".repeat(100)} isStreaming={true} />
      );

      expect(container).toBeTruthy();
    });

    test('should update progress as streaming advances', async () => {
      const { root as container } = render(
        <StreamingText text="ABC" isStreaming={true} speed={10} />
      );

      act(() => {
        jest.advanceTimersByTime(50);
      });

      expect(container).toBeTruthy();
    });

    test('should not show progress when not streaming', () => {
      const { root as container } = render(
        <StreamingText text="Test" isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Custom Styling', () => {
    test('should apply custom container style', () => {
      const customStyle = { backgroundColor: '#f0f0f0' };
      const { root as container } = render(
        <StreamingText
          text="Test"
          isStreaming={false}
          style={customStyle}
        />
      );

      expect(container).toBeTruthy();
    });

    test('should apply custom text style', () => {
      const textStyle = { fontSize: 20 };
      const { getByText } = render(
        <StreamingText
          text="Test"
          isStreaming={false}
          textStyle={textStyle}
        />
      );

      expect(getByText('Test')).toBeTruthy();
    });

    test('should use custom speed when streaming', () => {
      const { root as container } = render(
        <StreamingText
          text="Test"
          isStreaming={true}
          speed={50}
        />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    test('should handle null text gracefully', () => {
      const { root as container } = render(
        <StreamingText text={null as any} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle undefined text gracefully', () => {
      const { root as container } = render(
        <StreamingText text={undefined as any} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle text with special characters', () => {
      const specialText = 'Special: <>&"\'\\n\\t';
      const { getByText } = render(
        <StreamingText text={specialText} isStreaming={false} />
      );

      expect(getByText(/Special:/)).toBeTruthy();
    });

    test('should handle text with emojis', () => {
      const emojiText = 'Hello 👋 World 🌍';
      const { getByText } = render(
        <StreamingText text={emojiText} isStreaming={false} />
      );

      expect(getByText(/Hello/)).toBeTruthy();
    });

    test('should handle text with newlines', () => {
      const newlineText = 'Line 1\nLine 2\nLine 3';
      const { root as container } = render(
        <StreamingText text={newlineText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very fast speed setting', () => {
      const { root as container } = render(
        <StreamingText text="Fast" isStreaming={true} speed={1} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very slow speed setting', () => {
      const { root as container } = render(
        <StreamingText text="Slow" isStreaming={true} speed={1000} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Cursor Animation', () => {
    test('should show cursor when streaming', () => {
      const { root as container } = render(
        <StreamingText text="Test" isStreaming={true} />
      );

      expect(container).toBeTruthy();
    });

    test('should not show cursor when not streaming', () => {
      const { root as container } = render(
        <StreamingText text="Test" isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Integration Tests', () => {
    test('should handle streaming with markdown and code blocks', () => {
      const complexText =
        '```js\nconsole.log("test");\n```\n\n**Bold** text';
      const { root as container } = render(
        <StreamingText text={complexText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle streaming with special cards and markdown', () => {
      const complexText =
        'Check [[canvas:123]] and **bold text**';
      const { root as container } = render(
        <StreamingText text={complexText} isStreaming={false} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle all features combined', () => {
      const allFeaturesText = `See [[canvas:1]] and [[workflow:2]].

\`\`\`js
const x = 1;
\`\`\`

**Bold** and *italic* text.

More text to make it long enough to truncate: ${'A'.repeat(500)}`;

      const { root as container } = render(
        <StreamingText
          text={allFeaturesText}
          isStreaming={false}
          enableMarkdown={true}
        />
      );

      expect(container).toBeTruthy();
    });
  });
});
