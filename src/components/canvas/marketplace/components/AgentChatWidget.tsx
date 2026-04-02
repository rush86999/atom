/**
 * Agent Chat Widget Component
 *
 * Conversational interface component that connects to agent skills
 * for intelligent responses and multi-turn conversations.
 *
 * Features:
 * - Multi-turn conversations with context awareness
 * - Agent-powered responses using skills
 * - Message history and threading
 * - Typing indicators
 * - Rich message support (text, images, files, code)
 * - Voice input/output integration
 * - Agent presence and status
 * - Conversation templates
 * - Export chat history
 *
 * Perfect for creating AI assistants that use skills!
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Send,
  Mic,
  MicOff,
  Paperclip,
  MoreVertical,
  Trash2,
  Download,
  Bot,
  User,
  Clock,
  Check,
  CheckCheck
} from 'lucide-react';

export interface Message {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'delivered' | 'read';
  attachments?: Array<{
    type: 'image' | 'file' | 'code';
    url: string;
    name: string;
  }>;
  skill_used?: string;  // Which skill generated this response
}

export interface AgentChatWidgetProps {
  tenantId: string;
  agentId?: string;  // Agent to chat with
  skillId?: string;  // Or specific skill to use
  title?: string;
  description?: string;
  placeholder?: string;
  height?: number;
  enableVoice?: boolean;
  showTimestamp?: boolean;
  maxMessages?: number;
  onMessageSent?: (message: Message) => void;
  onMessageReceived?: (message: Message) => void;
}

export const AgentChatWidget: React.FC<AgentChatWidgetProps> = ({
  tenantId,
  agentId,
  skillId,
  title = 'Agent Chat',
  description = 'Chat with AI agent',
  placeholder = 'Type your message...',
  height = 500,
  enableVoice = false,
  showTimestamp = true,
  maxMessages = 100,
  onMessageSent,
  onMessageReceived
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(true);
  const [agentStatus, setAgentStatus] = useState<'online' | 'offline' | 'busy'>('online');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Send message to agent/skill
  const sendMessage = async (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      status: 'sending'
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const endpoint = skillId
        ? `/api/skills/${skillId}/execute`
        : `/api/v1/agents/${agentId}/chat`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': tenantId
        },
        body: JSON.stringify({
          message: content,
          history: messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content
          }))
        })
      });

      if (response.ok) {
        const result = await response.json();

        // Update user message status
        setMessages(prev => prev.map(m =>
          m.id === userMessage.id ? { ...m, status: 'delivered' } : m
        ));

        // Add agent response
        const agentMessage: Message = {
          id: `msg-${Date.now() + 1}`,
          role: 'agent',
          content: result.response || result.message || result.text || 'Response received',
          timestamp: new Date(),
          status: 'delivered',
          skill_used: result.skill_used
        };

        setMessages(prev => {
          const updated = [...prev, agentMessage];
          // Trim if exceeding max
          return updated.length > maxMessages ? updated.slice(-maxMessages) : updated;
        });

        onMessageSent?.(userMessage);
        onMessageReceived?.(agentMessage);
      }
    } catch (error) {
      console.error('Error sending message:', error);

      // Add error message
      const errorMessage: Message = {
        id: `msg-${Date.now() + 1}`,
        role: 'system',
        content: 'Failed to send message. Please try again.',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  // Handle voice input with Web Speech API
  const handleVoiceInput = () => {
    if (!enableVoice) return;

    // Check for browser support
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Voice input is not supported in this browser. Please use Chrome, Safari, or Edge.');
      return;
    }

    if (!isRecording) {
      // Start recording
      setIsRecording(true);
      const recognition = new SpeechRecognition();

      // Configure recognition
      recognition.continuous = false; // Stop after one sentence
      recognition.interimResults = true; // Show interim results
      recognition.lang = 'en-US'; // Default to English

      let finalTranscript = '';

      // Handle results
      recognition.onresult = (event: any) => {
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' ';
          } else {
            interimTranscript += transcript;
          }
        }

        // Update input with interim results
        setInput(finalTranscript + interimTranscript);
      };

      // Handle errors
      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);

        const errorMessages: Record<string, string> = {
          'no-speech': 'No speech detected. Please try again.',
          'audio-capture': 'No microphone found. Please ensure your microphone is connected.',
          'not-allowed': 'Microphone access denied. Please allow microphone access in your browser settings.',
          'network': 'Network error. Please check your connection.',
          'aborted': 'Voice input was aborted.'
        };

        const message = errorMessages[event.error] || `Error: ${event.error}`;
        alert(message);
      };

      // Handle completion
      recognition.onend = () => {
        setIsRecording(false);
        if (finalTranscript) {
          setInput(finalTranscript.trim());
        }
      };

      // Start recognition
      try {
        recognition.start();
      } catch (error) {
        console.error('Failed to start speech recognition:', error);
        setIsRecording(false);
      }
    } else {
      // Stop recording (will trigger onend)
      setIsRecording(false);
    }
  };

  // Handle file attachment
  const handleFileUpload = async (file: File) => {
    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB in bytes
    if (file.size > maxSize) {
      alert(`File too large. Maximum size: 10MB`);
      return;
    }

    // Validate file type
    const allowedTypes = [
      'image/jpeg', 'image/png', 'image/gif', 'image/webp',
      'application/pdf',
      'text/plain', 'text/markdown',
      'application/json',
      'text/csv'
    ];

    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(py|js|ts|jsx|tsx|html|css|doc|docx|xlsx)$/i)) {
      alert('Invalid file type. Allowed: images, PDF, documents, code files');
      return;
    }

    try {
      // Create FormData for upload
      const formData = new FormData();
      formData.append('file', file);

      // Upload to backend
      const response = await fetch('/api/chat/attachments/upload', {
        method: 'POST',
        body: formData,
        // Note: Don't set Content-Type header, let browser set it with boundary
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const data = await response.json();

      // Add attachment message
      setMessages(prev => [...prev, {
        id: uuidv4(),
        role: 'user',
        content: `[File: ${data.filename}](${data.url})`,
        timestamp: new Date(),
        attachment: {
          file_id: data.file_id,
          filename: data.filename,
          content_type: data.content_type,
          size: data.size,
          url: data.url
        }
      }]);

    } catch (error) {
      console.error('File upload error:', error);
      alert(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Clear chat history
  const clearHistory = () => {
    setMessages([]);
  };

  // Export chat history
  const exportChat = () => {
    const text = messages
      .map(m => `[${m.timestamp.toLocaleString()}] ${m.role}: ${m.content}`)
      .join('\n\n');

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  // Render message
  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';

    return (
      <div
        key={message.id}
        className={`flex items-start gap-3 mb-4 ${isUser ? 'flex-row-reverse' : ''}`}
      >
        <Avatar className="w-8 h-8">
          {isUser ? (
            <>
              <AvatarImage src="/avatar.png" />
              <AvatarFallback>
                <User className="w-4 h-4" />
              </AvatarFallback>
            </>
          ) : isSystem ? (
            <AvatarFallback className="bg-yellow-100 dark:bg-yellow-900">
              <Bot className="w-4 h-4 text-yellow-600" />
            </AvatarFallback>
          ) : (
            <>
              <AvatarImage src="/agent-avatar.png" />
              <AvatarFallback className="bg-purple-100 dark:bg-purple-900">
                <Bot className="w-4 h-4 text-purple-600" />
              </AvatarFallback>
            </>
          )}
        </Avatar>

        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[70%]`}>
          <div
            className={`rounded-lg px-4 py-2 ${isUser
                ? 'bg-primary text-primary-foreground'
                : isSystem
                  ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200'
                  : 'bg-muted'
              }`}
          >
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>

            {message.attachments && message.attachments.length > 0 && (
              <div className="mt-2 space-y-1">
                {message.attachments.map((attachment, index) => (
                  <div key={index} className="text-xs">
                    {attachment.type === 'image' ? (
                      <img src={attachment.url} alt={attachment.name} className="rounded max-w-full" />
                    ) : (
                      <a href={attachment.url} className="underline">
                        {attachment.name}
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 mt-1">
            {showTimestamp && (
              <span className="text-xs text-muted-foreground">
                {message.timestamp.toLocaleTimeString()}
              </span>
            )}

            {isUser && message.status && (
              <>
                {message.status === 'sending' && (
                  <Clock className="w-3 h-3 text-muted-foreground" />
                )}
                {message.status === 'sent' && (
                  <Check className="w-3 h-3 text-muted-foreground" />
                )}
                {message.status === 'delivered' && (
                  <CheckCheck className="w-3 h-3 text-muted-foreground" />
                )}
                {message.status === 'read' && (
                  <CheckCheck className="w-3 h-3 text-blue-500" />
                )}
              </>
            )}

            {message.skill_used && (
              <Badge variant="outline" className="text-xs">
                {message.skill_used}
              </Badge>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-purple-500" />
              {title}
            </CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Badge
              variant={agentStatus === 'online' ? 'default' : agentStatus === 'busy' ? 'secondary' : 'outline'}
              className="flex items-center gap-1"
            >
              <div className={`w-2 h-2 rounded-full ${agentStatus === 'online' ? 'bg-green-500' :
                  agentStatus === 'busy' ? 'bg-yellow-500' :
                    'bg-gray-400'
                }`} />
              {agentStatus}
            </Badge>

            <Button variant="ghost" size="sm" onClick={clearHistory}>
              <Trash2 className="w-4 h-4" />
            </Button>

            <Button variant="ghost" size="sm" onClick={exportChat}>
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <ScrollArea className={`h-[${height}px] pr-4`}>
          <div className="space-y-4">
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-center">
                <div className="space-y-2">
                  <Bot className="w-12 h-12 text-muted-foreground mx-auto" />
                  <p className="text-sm text-muted-foreground">
                    Start a conversation with the agent
                  </p>
                </div>
              </div>
            ) : (
              messages.map(renderMessage)
            )}

            {isTyping && (
              <div className="flex items-center gap-3">
                <Avatar className="w-8 h-8">
                  <AvatarFallback className="bg-purple-100 dark:bg-purple-900">
                    <Bot className="w-4 h-4 text-purple-600" />
                  </AvatarFallback>
                </Avatar>
                <div className="bg-muted rounded-lg px-4 py-2">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="mt-4 flex items-end gap-2">
          <div className="flex-1">
            <Textarea
              ref={inputRef}
              placeholder={placeholder}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="min-h-[60px] resize-none"
              disabled={!isConnected}
            />
          </div>

          <div className="flex flex-col gap-2">
            {enableVoice && (
              <Button
                variant={isRecording ? 'destructive' : 'outline'}
                size="icon"
                onClick={handleVoiceInput}
              >
                {isRecording ? (
                  <MicOff className="w-4 h-4" />
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </Button>
            )}

            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
            />
            <Button
              variant="outline"
              size="icon"
              onClick={() => document.getElementById('file-upload')?.click()}
            >
              <Paperclip className="w-4 h-4" />
            </Button>

            <Button
              size="icon"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || !isConnected}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="mt-2 text-xs text-muted-foreground text-center">
          Press Enter to send, Shift + Enter for new line
        </div>
      </CardContent>
    </Card>
  );
};
