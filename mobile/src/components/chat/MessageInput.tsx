/**
 * MessageInput Component
 *
 * Enhanced message input with attachments, voice input, emoji picker,
 * and @mentions support for agents.
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  Modal,
} from 'react-native';
import { useTheme, Icon, Avatar, IconButton, Chip } from 'react-native-paper';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Audio } from 'expo-av';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// Types
interface Attachment {
  id: string;
  type: 'image' | 'document' | 'audio';
  uri: string;
  name: string;
  size?: number;
  duration?: number;
}

interface Agent {
  id: string;
  name: string;
  avatar_url?: string;
}

interface MessageInputProps {
  onSend: (message: string, attachments?: Attachment[]) => void;
  agents?: Agent[];
  disabled?: boolean;
  maxLength?: number;
  placeholder?: string;
}

/**
 * MessageInput Component
 *
 * Multi-line input with attachments, voice, and @mentions
 */
export const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  agents = [],
  disabled = false,
  maxLength = 2000,
  placeholder = 'Type a message...',
}) => {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>([]);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [inputHeight, setInputHeight] = useState(40);

  const textInputRef = useRef<TextInput>(null);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Filter agents when @ is typed
   */
  useEffect(() => {
    const lastAtIndex = text.lastIndexOf('@');
    if (lastAtIndex !== -1) {
      const query = text.substring(lastAtIndex + 1);
      const spaceAfterQuery = query.indexOf(' ');

      if (spaceAfterQuery === -1) {
        setMentionQuery(query);
        const filtered = agents.filter((agent) =>
          agent.name.toLowerCase().includes(query.toLowerCase())
        );
        setFilteredAgents(filtered);
        setMentionIndex(0);
      } else {
        setMentionQuery('');
        setFilteredAgents([]);
      }
    } else {
      setMentionQuery('');
      setFilteredAgents([]);
    }
  }, [text, agents]);

  /**
   * Update recording duration
   */
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      setRecordingDuration(0);
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);

  /**
   * Handle text change with auto-grow
   */
  const handleTextChange = (newText: string) => {
    setText(newText);

    // Auto-grow input (max 5 lines)
    const lineHeight = 20;
    const maxHeight = lineHeight * 5;
    const lines = Math.min(newText.split('\n').length, 5);
    setInputHeight(Math.max(40, lines * lineHeight));
  };

  /**
   * Handle send
   */
  const handleSend = () => {
    if (!text.trim() && attachments.length === 0) return;

    onSend(text.trim(), attachments);
    setText('');
    setAttachments([]);
    setInputHeight(40);
  };

  /**
   * Handle @mention selection
   */
  const handleSelectAgent = (agent: Agent) => {
    const lastAtIndex = text.lastIndexOf('@');
    const before = text.substring(0, lastAtIndex);
    const after = text.substring(lastAtIndex + 1 + mentionQuery.length);
    const newText = `${before}@${agent.id} ${after}`;

    setText(newText);
    setMentionQuery('');
    setFilteredAgents([]);

    textInputRef.current?.focus();
  };

  /**
   * Handle attachment pick (camera)
   */
  const handlePickCamera = async () => {
    setShowAttachmentMenu(false);

    const permissionResult = await ImagePicker.requestCameraPermissionsAsync();
    if (!permissionResult.granted) {
      Alert.alert('Permission required', 'Camera permission is required');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      const attachment: Attachment = {
        id: `attach_${Date.now()}`,
        type: 'image',
        uri: result.assets[0].uri,
        name: result.assets[0].fileName || 'image.jpg',
        size: result.assets[0].fileSize,
      };
      setAttachments((prev) => [...prev, attachment]);
    }
  };

  /**
   * Handle attachment pick (gallery)
   */
  const handlePickGallery = async () => {
    setShowAttachmentMenu(false);

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
      allowsMultipleSelection: true,
    });

    if (!result.canceled) {
      const newAttachments: Attachment[] = result.assets.map((asset) => ({
        id: `attach_${Date.now()}_${Math.random()}`,
        type: 'image',
        uri: asset.uri,
        name: asset.fileName || 'image.jpg',
        size: asset.fileSize,
      }));
      setAttachments((prev) => [...prev, ...newAttachments]);
    }
  };

  /**
   * Handle attachment pick (document)
   */
  const handlePickDocument = async () => {
    setShowAttachmentMenu(false);

    const result = await DocumentPicker.getDocumentAsync({
      type: '*/*',
      multiple: true,
    });

    if (result.canceled === false && result.assets) {
      const newAttachments: Attachment[] = result.assets.map((asset) => ({
        id: `attach_${Date.now()}_${Math.random()}`,
        type: 'document',
        uri: asset.uri,
        name: asset.name,
        size: asset.size,
      }));
      setAttachments((prev) => [...prev, ...newAttachments]);
    }
  };

  /**
   * Handle voice record start
   */
  const handleStartRecording = async () => {
    try {
      const permissionResult = await Audio.requestPermissionsAsync();
      if (!permissionResult.granted) {
        Alert.alert('Permission required', 'Microphone permission is required');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RECORDING_OPTIONS_PRESET_HIGH_QUALITY);
      await recording.startAsync();

      recordingRef.current = recording;
      setIsRecording(true);
    } catch (error) {
      console.error('Failed to start recording:', error);
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  /**
   * Handle voice record stop
   */
  const handleStopRecording = async () => {
    if (!recordingRef.current) return;

    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();

      if (uri) {
        const attachment: Attachment = {
          id: `attach_${Date.now()}`,
          type: 'audio',
          uri,
          name: 'voice_message.aac',
          duration: recordingDuration,
        };
        setAttachments((prev) => [...prev, attachment]);
      }

      recordingRef.current = null;
      setIsRecording(false);
    } catch (error) {
      console.error('Failed to stop recording:', error);
    }
  };

  /**
   * Handle attachment removal
   */
  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  /**
   * Format recording duration
   */
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  /**
   * Render attachment preview
   */
  const renderAttachment = (attachment: Attachment) => (
    <View
      key={attachment.id}
      style={[styles.attachmentPreview, { backgroundColor: theme.colors.surfaceVariant }]}
    >
      {attachment.type === 'image' ? (
        <Avatar.Image size={40} source={{ uri: attachment.uri }} />
      ) : attachment.type === 'audio' ? (
        <Icon source="microphone" size={24} color={theme.colors.primary} />
      ) : (
        <Icon source="file-document" size={24} color={theme.colors.primary} />
      )}
      <Text
        style={[styles.attachmentName, { color: theme.colors.onSurface }]}
        numberOfLines={1}
        ellipsizeMode="middle"
      >
        {attachment.name}
      </Text>
      <IconButton
        icon="close"
        size={16}
        onPress={() => handleRemoveAttachment(attachment.id)}
      />
    </View>
  );

  /**
   * Render mention suggestion
   */
  const renderMentionSuggestion = (agent: Agent, index: number) => (
    <TouchableOpacity
      key={agent.id}
      style={[
        styles.mentionSuggestion,
        index === mentionIndex && { backgroundColor: theme.colors.primaryContainer },
      ]}
      onPress={() => handleSelectAgent(agent)}
    >
      <Avatar.Text
        size={32}
        label={agent.name.substring(0, 2).toUpperCase()}
        style={{ backgroundColor: theme.colors.primary }}
      />
      <Text style={[styles.mentionName, { color: theme.colors.onSurface }]}>
        {agent.name}
      </Text>
    </TouchableOpacity>
  );

  return (
    <KeyboardAvoidingView
      style={[styles.container, { paddingBottom: insets.bottom }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Attachment previews */}
      {attachments.length > 0 && (
        <ScrollView horizontal style={styles.attachmentsContainer} showsHorizontalScrollIndicator={false}>
          {attachments.map(renderAttachment)}
        </ScrollView>
      )}

      {/* Mention suggestions */}
      {filteredAgents.length > 0 && (
        <View style={[styles.mentionSuggestions, { backgroundColor: theme.colors.surface }]}>
          <ScrollView keyboardShouldPersistTaps="handled">
            {filteredAgents.map((agent, index) => renderMentionSuggestion(agent, index))}
          </ScrollView>
        </View>
      )}

      {/* Input row */}
      <View style={[styles.inputRow, { borderTopColor: theme.colors.outline }]}>
        {/* Attachment button */}
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => setShowAttachmentMenu(true)}
          disabled={disabled}
        >
          <Icon
            source="paperclip"
            size={24}
            color={disabled ? theme.colors.onSurfaceDisabled : theme.colors.onSurfaceVariant}
          />
        </TouchableOpacity>

        {/* Text input */}
        <TextInput
          ref={textInputRef}
          style={[
            styles.input,
            {
              backgroundColor: theme.colors.surfaceVariant,
              color: theme.colors.onSurface,
              height: inputHeight,
            },
          ]}
          value={text}
          onChangeText={handleTextChange}
          placeholder={placeholder}
          placeholderTextColor={theme.colors.onSurfaceVariant}
          multiline
          maxLength={maxLength}
          editable={!disabled}
          onFocus={() => setShowAttachmentMenu(false)}
        />

        {/* Recording indicator */}
        {isRecording ? (
          <TouchableOpacity
            style={[styles.recordButton, { backgroundColor: theme.colors.error }]}
            onPress={handleStopRecording}
          >
            <Icon source="stop" size={24} color="#fff" />
            <Text style={styles.recordDuration}>{formatDuration(recordingDuration)}</Text>
          </TouchableOpacity>
        ) : (
          <>
            {/* Voice input button */}
            {!text.trim() && (
              <TouchableOpacity
                style={styles.iconButton}
                onLongPress={handleStartRecording}
                disabled={disabled}
              >
                <Icon
                  source="microphone"
                  size={24}
                  color={disabled ? theme.colors.onSurfaceDisabled : theme.colors.onSurfaceVariant}
                />
              </TouchableOpacity>
            )}

            {/* Send button */}
            {text.trim() && (
              <TouchableOpacity
                style={[styles.sendButton, { backgroundColor: theme.colors.primary }]}
                onPress={handleSend}
                disabled={disabled}
              >
                <Icon source="send" size={20} color="#fff" />
              </TouchableOpacity>
            )}
          </>
        )}
      </View>

      {/* Character counter */}
      <Text style={[styles.charCounter, { color: theme.colors.onSurfaceVariant }]}>
        {text.length} / {maxLength}
      </Text>

      {/* Attachment menu */}
      <Modal
        visible={showAttachmentMenu}
        transparent
        animationType="slide"
        onRequestClose={() => setShowAttachmentMenu(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowAttachmentMenu(false)}
        >
          <View style={[styles.attachmentMenu, { backgroundColor: theme.colors.surface }]}>
            <TouchableOpacity style={styles.attachmentOption} onPress={handlePickCamera}>
              <Icon source="camera" size={24} color={theme.colors.primary} />
              <Text style={[styles.attachmentOptionText, { color: theme.colors.onSurface }]}>
                Camera
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.attachmentOption} onPress={handlePickGallery}>
              <Icon source="image" size={24} color={theme.colors.primary} />
              <Text style={[styles.attachmentOptionText, { color: theme.colors.onSurface }]}>
                Gallery
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.attachmentOption} onPress={handlePickDocument}>
              <Icon source="file-document" size={24} color={theme.colors.primary} />
              <Text style={[styles.attachmentOptionText, { color: theme.colors.onSurface }]}>
                Document
              </Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
  },
  iconButton: {
    padding: 8,
    marginRight: 8,
  },
  input: {
    flex: 1,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 15,
    maxHeight: 100,
  },
  sendButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  recordButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 18,
    marginLeft: 8,
  },
  recordDuration: {
    color: '#fff',
    fontWeight: '600',
    marginLeft: 8,
  },
  charCounter: {
    fontSize: 11,
    textAlign: 'right',
    paddingHorizontal: 12,
    paddingBottom: 4,
  },
  attachmentsContainer: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    maxHeight: 80,
  },
  attachmentPreview: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 8,
    gap: 8,
  },
  attachmentName: {
    flex: 1,
    fontSize: 12,
    maxWidth: 150,
  },
  mentionSuggestions: {
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
    maxHeight: 150,
  },
  mentionSuggestion: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
  },
  mentionName: {
    fontSize: 15,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  attachmentMenu: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
  },
  attachmentOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    gap: 16,
  },
  attachmentOptionText: {
    fontSize: 16,
    fontWeight: '500',
  },
});

export default MessageInput;
