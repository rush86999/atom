import { useState } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

interface Message {
  text: string;
  sender: "user" | "agent";
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (input.trim() === "") return;

    const newMessages: Message[] = [...messages, { text: input, sender: "user" }];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response: string = await invoke("send_message_to_agent", { message: input });
      setMessages([...newMessages, { text: response, sender: "agent" }]);
    } catch (err) {
      console.error("Error invoking send_message_to_agent:", err);
      setMessages([...newMessages, { text: "Error communicating with the agent.", sender: "agent" }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.sender}`}>
            {message.text}
          </div>
        ))}
        {isLoading && <div className="message agent">...</div>}
      </div>
      <div className="input-container">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type your message..."
        />
        <button onClick={handleSend} disabled={isLoading}>
          Send
        </button>
      </div>
    </div>
  );
}

export default Chat;
