import React, { useEffect, useState, useRef, useCallback, useMemo, FC } from 'react';
import { GoogleGenAI, Chat } from "@google/genai";
import { ChatMessage } from '../types';
import { useWebSocket } from '../hooks/useWebSocket';

interface ConversationContext {
    topic: string;
    relatedMessages: number;
    sentiment: 'positive' | 'neutral' | 'negative';
}

const Message: React.FC<{ message: ChatMessage; onReaction?: (reaction: string) => void }> = ({ message, onReaction }) => (
    <div className={`message ${message.role === "user" ? "user-message" : "atom-message"}`}>
      <div className="message-bubble">
          {message.content}
          {message.isStreaming && <span className="blinking-cursor"></span>}
      </div>
      <div className="message-actions">
          {message.role === "assistant" && (
              <>
                  <button onClick={() => onReaction?.('👍')} title="Helpful" className="reaction-btn">👍</button>
                  <button onClick={() => onReaction?.('👎')} title="Not helpful" className="reaction-btn">👎</button>
                  <button onClick={() => console.log('Copy:', message.content)} title="Copy" className="action-btn">📋</button>
              </>
          )}
      </div>
    </div>
);

// Advanced Message Context Widget
const MessageContextWidget: FC<{ context: ConversationContext | null }> = ({ context }) => {
    if (!context) return null;
    return (
        <div className="context-widget">
            <span>Topic: {context.topic}</span>
            <span>Sentiment: {context.sentiment}</span>
            <span>Context: {context.relatedMessages} related messages</span>
        </div>
    );
};

export const ChatView = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [remoteTypingUsers, setRemoteTypingUsers] = useState<string[]>([]);
  const [chat, setChat] = useState<Chat | null>(null);
  const [conversationHistory, setConversationHistory] = useState<ChatMessage[]>([]);
  const [context, setContext] = useState<ConversationContext | null>(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([
    "Help me prioritize my tasks",
    "Create a summary of my day",
    "What should I focus on next?",
    "Analyze my productivity"
  ]);
  const [messageReactions, setMessageReactions] = useState<Record<string, string>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isStreaming = messages.some(msg => msg.isStreaming);

  useEffect(() => {
    try {
      const apiKey = (import.meta as any)?.env?.VITE_GOOGLE_API_KEY;
      if (!apiKey) {
        setChat(null);
        setMessages([{ id: `atom-initial-${Date.now()}`, role: "assistant", content: "AI chat is disabled. Provide VITE_GOOGLE_API_KEY in your environment to enable chat." }]);
        return;
      }
      const ai = new GoogleGenAI({ apiKey });
      const chatSession = ai.chats.create({ model: "gemini-2.5-flash" });
      setChat(chatSession);
      const initialMessage = { id: `atom-initial-${Date.now()}`, role: "assistant" as const, content: "Hello! I'm Atom. How can I help you manage your day?" };
      setMessages([initialMessage]);
      setConversationHistory([initialMessage]);
    } catch (error) {
      console.error("Failed to initialize Gemini:", error);
      setChat(null);
      setMessages([{ id: `atom-error-${Date.now()}`, role: "assistant", content: "Error: Could not connect to the AI service." }]);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // WebSocket: subscribe to incoming chat messages and typing indicators
  useEffect(() => {
    const { subscribe, unsubscribe, emit } = useWebSocket({ enabled: true });

    const onMessageNew = (payload: any) => {
      if (!payload) return;
      const msg: ChatMessage = {
        id: payload.id || `remote-${Date.now()}`,
        role: payload.role || 'assistant',
        content: payload.content || payload.text || '',
      };
      setMessages(prev => [...prev, msg]);
      setConversationHistory(prev => [...prev, msg]);
    };

    const onTypingStart = (data: any) => {
      if (!data?.username) return;
      setRemoteTypingUsers(prev => Array.from(new Set([...prev, data.username])));
    };

    const onTypingStop = (data: any) => {
      if (!data?.username) return;
      setRemoteTypingUsers(prev => prev.filter(u => u !== data.username));
    };

    subscribe('message:new', onMessageNew);
    subscribe('typing:start', onTypingStart);
    subscribe('typing:stop', onTypingStop);

    return () => {
      unsubscribe('message:new', onMessageNew);
      unsubscribe('typing:start', onTypingStart);
      unsubscribe('typing:stop', onTypingStop);
    };
  }, []);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputValue]);

  // Analyze conversation context
  useEffect(() => {
    if (conversationHistory.length > 0) {
      const lastMessage = conversationHistory[conversationHistory.length - 1];
      const topic = lastMessage.content.split(' ')[0];
      setContext({
        topic,
        relatedMessages: conversationHistory.filter(m => m.content.includes(topic)).length,
        sentiment: lastMessage.content.includes('!') ? 'positive' : 'neutral'
      });
    }
  }, [conversationHistory]);

  const handleReaction = useCallback((messageId: string, reaction: string) => {
    setMessageReactions(prev => ({
      ...prev,
      [messageId]: reaction
    }));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isStreaming || !chat) return;

    const userMessage: ChatMessage = { id: `user-${Date.now()}`, role: "user", content: inputValue };
    setMessages((prev) => [...prev, userMessage]);
    setConversationHistory(prev => [...prev, userMessage]);
    setInputValue("");

    const assistantMessageId = `assistant-${Date.now()}`;
    try {
      setMessages((prev) => [...prev, { id: assistantMessageId, role: "assistant", content: "", isStreaming: true }]);
      
      const stream = await chat.sendMessageStream({ text: inputValue });

      for await (const chunk of stream) {
        setMessages((prev) => prev.map((msg) => 
            msg.id === assistantMessageId 
            ? { ...msg, content: msg.content + chunk.text }
            : msg
        ));
      }

      const finalMessage = messages.find(m => m.id === assistantMessageId);
      setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg));
      
      if (finalMessage) {
        setConversationHistory(prev => [...prev, { ...finalMessage, isStreaming: false }]);
      }

      // Emit the user message to server so other clients receive it
      try {
        const { emit } = useWebSocket({ enabled: true });
        emit && emit('message:new', { id: userMessage.id, role: 'user', content: userMessage.content, from: { name: 'You' } });
      } catch (e) {
        // ignore
      }

    } catch (error) {
      console.error("Error sending message:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: "Sorry, I encountered an error.", isStreaming: false }
            : msg
        )
      );
    }
  };

  // Emit typing indicators while user types
  useEffect(() => {
    const { emit } = useWebSocket({ enabled: true });
    if (!emit) return;
    if (inputValue && inputValue.length > 0) {
      emit('typing:start', { channelId: 'chat-global', username: 'You' });
      const t = setTimeout(() => emit('typing:stop', { channelId: 'chat-global', username: 'You' }), 2000);
      return () => clearTimeout(t);
    } else {
      emit('typing:stop', { channelId: 'chat-global', username: 'You' });
    }
  }, [inputValue]);

  const handleSuggestedQuestion = (question: string) => {
    setInputValue(question);
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>Atom AI Assistant</h1>
        <p>Your life, managed.</p>
        <MessageContextWidget context={context} />
      </header>
      <div className="message-list">
        {messages.map((msg) => (
            <Message 
              key={msg.id} 
              message={msg}
              onReaction={(reaction) => handleReaction(msg.id, reaction)}
            />
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="typing-indicator">
        {remoteTypingUsers.length > 0 && <small>{remoteTypingUsers.join(', ')} typing...</small>}
      </div>
      <div className="suggested-questions">
        {suggestedQuestions.map((q, i) => (
            <button key={i} onClick={() => handleSuggestedQuestion(q)} className="suggestion-btn">
              {q}
            </button>
        ))}
      </div>
      <footer className="chat-footer">
        <form onSubmit={handleSubmit} className="input-form">
          <textarea ref={textareaRef} value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }} placeholder={chat ? "Ask Atom anything..." : "AI disabled. Set VITE_GOOGLE_API_KEY to enable."} rows={1} disabled={isStreaming || !chat} aria-label="Chat input" />
          <button type="submit" disabled={isStreaming || !inputValue.trim() || !chat} aria-label="Send message"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" /></svg></button>
        </form>
      </footer>
    </div>
  );
};