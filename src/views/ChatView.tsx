import React, { useEffect, useState, useRef } from 'react';
import { GoogleGenAI, Chat } from "@google/genai";
import { ChatMessage } from '../types';
import { useWebSocket } from '../hooks/useWebSocket';

const Message: React.FC<{ message: ChatMessage }> = ({ message }) => (
    <div className={`message ${message.role === "user" ? "user-message" : "atom-message"}`}>
      <div className="message-bubble">
          {message.content}
          {message.isStreaming && <span className="blinking-cursor"></span>}
      </div>
    </div>
);

export const ChatView = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [remoteTypingUsers, setRemoteTypingUsers] = useState<string[]>([]);
  const [chat, setChat] = useState<Chat | null>(null);
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
      setMessages([{ id: `atom-initial-${Date.now()}`, role: "assistant", content: "Hello! I'm Atom. How can I help you manage your day?" }]);
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isStreaming || !chat) return;

    const userMessage: ChatMessage = { id: `user-${Date.now()}`, role: "user", content: inputValue };
    setMessages((prev) => [...prev, userMessage]);
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

      setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg));

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

  return (
    <div className="chat-container">
      <header className="chat-header"><h1>Atom AI Assistant</h1><p>Your life, managed.</p></header>
      <div className="message-list">{messages.map((msg) => (<Message key={msg.id} message={msg} />))}<div ref={messagesEndRef} /></div>
      <div className="typing-indicator">{remoteTypingUsers.length > 0 && <small>{remoteTypingUsers.join(', ')} typing...</small>}</div>
      <footer className="chat-footer">
        <form onSubmit={handleSubmit} className="input-form">
          <textarea ref={textareaRef} value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }} placeholder={chat ? "Ask Atom anything..." : "AI disabled. Set VITE_GOOGLE_API_KEY to enable."} rows={1} disabled={isStreaming || !chat} aria-label="Chat input" />
          <button type="submit" disabled={isStreaming || !inputValue.trim() || !chat} aria-label="Send message"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" /></svg></button>
        </form>
      </footer>
    </div>
  );
};