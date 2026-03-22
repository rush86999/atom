/**
 * MessageInput Component Tests
 *
 * Comprehensive test suite for MessageInput component covering:
 * - Text input with auto-grow
 * - Character counter
 * - Attachment handling (camera, gallery, documents)
 * - Voice recording
 * - @mentions for agents
 * - Send button behavior
 * - Disabled state
 * - Keyboard avoidance
 * - Attachment menu
 * - Emoji picker (mocked)
 *
 * Coverage Target: 80%+
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert } from 'react-native';
import { ThemeProvider } from 'react-native-paper';
import { MessageInput } from '../chat/MessageInput';

// Mock dependencies
jest.mock('expo-image-picker', () => ({
  requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
  launchCameraAsync: jest.fn(),
  launchImageLibraryAsync: jest.fn(),
  MediaTypeOptions: {
    Images: 'images',
  },
}));

jest.mock('expo-document-picker', () => ({
  getDocumentAsync: jest.fn(),
}));

jest.mock('expo-av', () => ({
  Audio: {
    requestPermissionsAsync: jest.fn(() => Promise.resolve({ granted: true })),
    setAudioModeAsync: jest.fn(),
    RECORDING_OPTIONS_PRESET_HIGH_QUALITY: 'high',
  },
}));

jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: jest.fn(() => ({ bottom: 0, top: 0, left: 0, right: 0 })),
}));

jest.spyOn(Alert, 'alert');

describe('MessageInput Component', () => {
  const mockOnSend = jest.fn();
  const mockAgents = [
    { id: 'agent1', name: 'Test Agent 1', avatar_url: 'https://example.com/avatar1.png' },
    { id: 'agent2', name: 'Test Agent 2', avatar_url: 'https://example.com/avatar2.png' },
  ];

  const renderWithTheme = (component: React.ReactElement) => {
    return render(
      <ThemeProvider theme={{ colors: { primary: '#2196F3', onSurface: '#000', surfaceVariant: '#f5f5f5', onSurfaceVariant: '#666', onSurfaceDisabled: '#ccc', error: '#F44336', outline: '#ccc', surface: '#fff', primaryContainer: '#e3f2fd' } }}>
        {component}
      </ThemeProvider>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    test('should render correctly with default props', () => {
      const { getByPlaceholderText, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
      expect(getByText('0 / 2000')).toBeTruthy();
    });

    test('should render with custom placeholder', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} placeholder="Custom placeholder" />
      );

      expect(getByPlaceholderText('Custom placeholder')).toBeTruthy();
    });

    test('should render with custom maxLength', () => {
      const { getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} maxLength={500} />
      );

      expect(getByText('0 / 500')).toBeTruthy();
    });

    test('should render attachment button', () => {
      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      // Attachment button is the first icon button
      const attachmentButton = getByTestId('icon-button');
      expect(attachmentButton).toBeTruthy();
    });

    test('should render voice input button when text is empty', () => {
      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      // Voice button should be visible
      const voiceButton = getByTestId('voice-button');
      expect(voiceButton).toBeTruthy();
    });
  });

  describe('Text Input', () => {
    test('should update text input on change', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello world');

      expect(textInput.props.value).toBe('Hello world');
    });

    test('should update character counter', () => {
      const { getByPlaceholderText, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello');

      expect(getByText('5 / 2000')).toBeTruthy();
    });

    test('should enforce maxLength', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} maxLength={10} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'This is a very long message that exceeds limit');

      // Should truncate to maxLength
      expect(textInput.props.value.length).toBeLessThanOrEqual(10);
    });

    test('should show send button when text is not empty', () => {
      const { getByPlaceholderText, getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');

      // Initially, send button should not be visible
      expect(() => getByTestId('send-button')).toThrow();

      // Type text
      fireEvent.changeText(textInput, 'Hello');

      // Send button should now be visible
      const sendButton = getByTestId('send-button');
      expect(sendButton).toBeTruthy();
    });

    test('should auto-grow input height with multiple lines', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      const initialHeight = 40;

      // Single line
      fireEvent.changeText(textInput, 'Line 1');
      expect(textInput.props.style.height).toBe(initialHeight);

      // Multiple lines
      fireEvent.changeText(textInput, 'Line 1\nLine 2\nLine 3');
      expect(textInput.props.style.height).toBeGreaterThan(initialHeight);

      // Max height (5 lines)
      const longText = Array(10).fill('Line').join('\n');
      fireEvent.changeText(textInput, longText);
      expect(textInput.props.style.height).toBeLessThanOrEqual(100); // max 5 lines * 20px
    });
  });

  describe('Send Functionality', () => {
    test('should call onSend when send button is pressed', () => {
      const { getByPlaceholderText, getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello world');

      const sendButton = getByTestId('send-button');
      fireEvent.press(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Hello world', []);
    });

    test('should clear text and attachments after send', () => {
      const { getByPlaceholderText, getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello world');

      const sendButton = getByTestId('send-button');
      fireEvent.press(sendButton);

      expect(textInput.props.value).toBe('');
      expect(getByText('0 / 2000')).toBeTruthy();
    });

    test('should not send empty message', () => {
      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const sendButton = getByTestId('send-button');
      fireEvent.press(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });

    test('should send with attachments', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.launchCameraAsync.mockResolvedValue({
        canceled: false,
        assets: [{ uri: 'file://photo.jpg', fileName: 'photo.jpg', fileSize: 1024 }],
      });

      const { getByPlaceholderText, getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      // Open attachment menu
      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      // Select camera
      await waitFor(() => {
        const cameraOption = getByText('Camera');
        fireEvent.press(cameraOption);
      });

      await waitFor(() => {
        expect(getByText('photo.jpg')).toBeTruthy();
      });

      // Type message and send
      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Check this photo');

      const sendButton = getByTestId('send-button');
      fireEvent.press(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Check this photo', expect.arrayContaining([
        expect.objectContaining({ type: 'image', uri: 'file://photo.jpg' }),
      ]));
    });
  });

  describe('@Mentions', () => {
    test('should show mention suggestions when @ is typed', () => {
      const { getByPlaceholderText, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@');

      // Should show filtered agents
      expect(getByText('Test Agent 1')).toBeTruthy();
      expect(getByText('Test Agent 2')).toBeTruthy();
    });

    test('should filter agents by mention query', () => {
      const { getByPlaceholderText, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@agent1');

      // Should only show matching agent
      expect(getByText('Test Agent 1')).toBeTruthy();
      expect(queryByText('Test Agent 2')).toBeNull();
    });

    test('should select agent mention', () => {
      const { getByPlaceholderText, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@');

      // Tap on agent suggestion
      const agentSuggestion = getByText('Test Agent 1');
      fireEvent.press(agentSuggestion);

      // Should replace @ with agent ID
      expect(textInput.props.value).toContain('@agent1');
      expect(queryByText('Test Agent 1')).toBeNull();
    });

    test('should hide suggestions when space is typed after query', () => {
      const { getByPlaceholderText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@agent ');

      // Should hide suggestions
      expect(queryByText('Test Agent 1')).toBeNull();
      expect(queryByText('Test Agent 2')).toBeNull();
    });

    test('should hide suggestions when no @ is present', () => {
      const { getByPlaceholderText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello world');

      expect(queryByText('Test Agent 1')).toBeNull();
    });
  });

  describe('Attachments - Camera', () => {
    test('should open attachment menu when attachment button is pressed', () => {
      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      expect(getByText('Camera')).toBeTruthy();
      expect(getByText('Gallery')).toBeTruthy();
      expect(getByText('Document')).toBeTruthy();
    });

    test('should request camera permissions and capture photo', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.requestCameraPermissionsAsync.mockResolvedValue({ granted: true });
      ImagePicker.launchCameraAsync.mockResolvedValue({
        canceled: false,
        assets: [{ uri: 'file://photo.jpg', fileName: 'photo.jpg', fileSize: 1024 }],
      });

      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const cameraOption = getByText('Camera');
        fireEvent.press(cameraOption);
      });

      expect(ImagePicker.requestCameraPermissionsAsync).toHaveBeenCalled();
      expect(ImagePicker.launchCameraAsync).toHaveBeenCalledWith({
        mediaTypes: 'images',
        quality: 0.8,
      });
    });

    test('should show permission alert if camera permission denied', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.requestCameraPermissionsAsync.mockResolvedValue({ granted: false });

      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const cameraOption = getByText('Camera');
        fireEvent.press(cameraOption);
      });

      expect(Alert.alert).toHaveBeenCalledWith(
        'Permission required',
        'Camera permission is required'
      );
    });

    test('should handle camera cancel', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.requestCameraPermissionsAsync.mockResolvedValue({ granted: true });
      ImagePicker.launchCameraAsync.mockResolvedValue({
        canceled: true,
      });

      const { getByTestId, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const cameraOption = getByText('Camera');
        fireEvent.press(cameraOption);
      });

      // Should not show attachment preview
      await waitFor(() => {
        expect(queryByText('photo.jpg')).toBeNull();
      });
    });
  });

  describe('Attachments - Gallery', () => {
    test('should pick multiple images from gallery', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.launchImageLibraryAsync.mockResolvedValue({
        canceled: false,
        assets: [
          { uri: 'file://photo1.jpg', fileName: 'photo1.jpg', fileSize: 1024 },
          { uri: 'file://photo2.jpg', fileName: 'photo2.jpg', fileSize: 2048 },
        ],
      });

      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const galleryOption = getByText('Gallery');
        fireEvent.press(galleryOption);
      });

      expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith({
        mediaTypes: 'images',
        quality: 0.8,
        allowsMultipleSelection: true,
      });
    });

    test('should handle gallery cancel', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.launchImageLibraryAsync.mockResolvedValue({
        canceled: true,
      });

      const { getByTestId, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const galleryOption = getByText('Gallery');
        fireEvent.press(galleryOption);
      });

      expect(queryByText('photo1.jpg')).toBeNull();
    });
  });

  describe('Attachments - Documents', () => {
    test('should pick documents', async () => {
      const DocumentPicker = require('expo-document-picker');
      DocumentPicker.getDocumentAsync.mockResolvedValue({
        canceled: false,
        assets: [
          { uri: 'file://doc.pdf', name: 'doc.pdf', size: 1024 },
        ],
      });

      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const documentOption = getByText('Document');
        fireEvent.press(documentOption);
      });

      expect(DocumentPicker.getDocumentAsync).toHaveBeenCalledWith({
        type: '*/*',
        multiple: true,
      });
    });

    test('should handle document picker cancel', async () => {
      const DocumentPicker = require('expo-document-picker');
      DocumentPicker.getDocumentAsync.mockResolvedValue({
        canceled: true,
      });

      const { getByTestId, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const documentOption = getByText('Document');
        fireEvent.press(documentOption);
      });

      expect(queryByText('doc.pdf')).toBeNull();
    });
  });

  describe('Attachment Removal', () => {
    test('should remove attachment when close button is pressed', async () => {
      const ImagePicker = require('expo-image-picker');
      ImagePicker.launchCameraAsync.mockResolvedValue({
        canceled: false,
        assets: [{ uri: 'file://photo.jpg', fileName: 'photo.jpg', fileSize: 1024 }],
      });

      const { getByTestId, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      // Add attachment
      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      await waitFor(() => {
        const cameraOption = getByText('Camera');
        fireEvent.press(cameraOption);
      });

      await waitFor(() => {
        expect(getByText('photo.jpg')).toBeTruthy();
      });

      // Remove attachment
      const removeButton = getByTestId('remove-attachment');
      fireEvent.press(removeButton);

      await waitFor(() => {
        expect(queryByText('photo.jpg')).toBeNull();
      });
    });
  });

  describe('Voice Recording', () => {
    test('should start recording on long press', async () => {
      const Audio = require('expo-av').Audio;
      const mockRecording = {
        prepareToRecordAsync: jest.fn(),
        startAsync: jest.fn(),
        stopAndUnloadAsync: jest.fn(),
        getURI: jest.fn(() => 'file://recording.aac'),
      };
      Audio.Recording = jest.fn(() => mockRecording);

      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const voiceButton = getByTestId('voice-button');
      fireEvent(voiceButton, 'onLongPress');

      await waitFor(() => {
        expect(Audio.requestPermissionsAsync).toHaveBeenCalled();
        expect(Audio.setAudioModeAsync).toHaveBeenCalled();
      });
    });

    test('should show recording indicator while recording', async () => {
      const { getByTestId, getByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      // Simulate recording state
      const voiceButton = getByTestId('voice-button');
      fireEvent(voiceButton, 'onLongPress');

      // After recording starts, stop button should appear
      await waitFor(() => {
        expect(getByText('0:00')).toBeTruthy();
      });
    });

    test('should stop recording and add attachment', async () => {
      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const voiceButton = getByTestId('voice-button');
      fireEvent(voiceButton, 'onLongPress');

      // Stop recording
      const stopButton = getByTestId('stop-button');
      fireEvent.press(stopButton);

      // Should add audio attachment
      await waitFor(() => {
        expect(getByTestId('audio-attachment')).toBeTruthy();
      });
    });

    test('should handle recording permission denied', async () => {
      const Audio = require('expo-av').Audio;
      Audio.requestPermissionsAsync.mockResolvedValue({ granted: false });

      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const voiceButton = getByTestId('voice-button');
      fireEvent(voiceButton, 'onLongPress');

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Permission required',
          'Microphone permission is required'
        );
      });
    });
  });

  describe('Disabled State', () => {
    test('should disable input when disabled prop is true', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} disabled={true} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      expect(textInput.props.editable).toBe(false);
    });

    test('should disable send button when disabled', () => {
      const { getByPlaceholderText, getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} disabled={true} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello');

      const sendButton = getByTestId('send-button');
      expect(sendButton.props.disabled).toBe(true);
    });

    test('should disable attachment button when disabled', () => {
      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} disabled={true} />
      );

      const attachmentButton = getByTestId('attachment-button');
      expect(attachmentButton.props.disabled).toBe(true);
    });
  });

  describe('Attachment Menu', () => {
    test('should close attachment menu when overlay is pressed', () => {
      const { getByTestId, getByText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('attachment-button');
      fireEvent.press(attachmentButton);

      expect(getByText('Camera')).toBeTruthy();

      // Press overlay to close
      const overlay = getByTestId('modal-overlay');
      fireEvent.press(overlay);

      expect(queryByText('Camera')).toBeNull();
    });
  });

  describe('Keyboard Avoidance', () => {
    test('should use padding behavior on iOS', () => {
      const Platform = require('react-native').Platform;
      const originalOS = Platform.OS;

      Platform.OS = 'ios';

      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const keyboardAvoidingView = getByTestId('keyboard-avoiding-view');
      expect(keyboardAvoidingView.props.behavior).toBe('padding');

      Platform.OS = originalOS;
    });

    test('should not use behavior on Android', () => {
      const Platform = require('react-native').Platform;
      const originalOS = Platform.OS;

      Platform.OS = 'android';

      const { getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const keyboardAvoidingView = getByTestId('keyboard-avoiding-view');
      expect(keyboardAvoidingView.props.behavior).toBeUndefined();

      Platform.OS = originalOS;
    });
  });

  describe('Edge Cases', () => {
    test('should handle empty agents array', () => {
      const { getByPlaceholderText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} agents={[]} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@');

      expect(queryByText('Test Agent 1')).toBeNull();
    });

    test('should handle no agents prop', () => {
      const { getByPlaceholderText, queryByText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, '@');

      expect(queryByText('Test Agent 1')).toBeNull();
    });

    test('should handle very long text', () => {
      const { getByPlaceholderText } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      const longText = 'A'.repeat(3000);

      fireEvent.changeText(textInput, longText);

      // Should truncate to maxLength
      expect(textInput.props.value.length).toBe(2000);
    });

    test('should handle special characters in text', () => {
      const { getByPlaceholderText, getByTestId } = renderWithTheme(
        <MessageInput onSend={mockOnSend} />
      );

      const textInput = getByPlaceholderText('Type a message...');
      fireEvent.changeText(textInput, 'Hello @#$%^&*() World');

      const sendButton = getByTestId('send-button');
      fireEvent.press(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Hello @#$%^&*() World', []);
    });
  });
});
