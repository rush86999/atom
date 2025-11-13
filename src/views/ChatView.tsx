import React, { useEffect, useState, useRef } from 'react';
import { GoogleGenAI, Chat } from "@google/genai";
import { ChatMessage } from '../types';

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

  return (
    <div className="chat-container">
      <header className="chat-header"><h1>Atom AI Assistant</h1><p>Your life, managed.</p></header>
      <div className="message-list">{messages.map((msg) => (<Message key={msg.id} message={msg} />))}<div ref={messagesEndRef} /></div>
      <footer className="chat-footer">
        <form onSubmit={handleSubmit} className="input-form">
          <textarea ref={textareaRef} value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }} placeholder={chat ? "Ask Atom anything..." : "AI disabled. Set VITE_GOOGLE_API_KEY to enable."} rows={1} disabled={isStreaming || !chat} aria-label="Chat input" />
          <button type="submit" disabled={isStreaming || !inputValue.trim() || !chat} aria-label="Send message"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" /></svg></button>
        </form>
      </footer>
    </div>
  );
};