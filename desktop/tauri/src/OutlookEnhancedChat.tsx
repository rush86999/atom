import React, { useState } from "react";

/**
 * Placeholder component for Outlook Enhanced Chat
 * This will be implemented when Outlook integration is ready
 */
const OutlookEnhancedChat: React.FC = () => {
  const [message, setMessage] = useState("");

  const handleSend = () => {
    alert("Outlook Enhanced Chat is not yet implemented. This feature will be available in a future update.");
    setMessage("");
  };

  return (
    <div className="outlook-chat-container">
      <div className="chat-header">
        <h2>Outlook Enhanced Chat</h2>
        <div className="connection-status">
          <span className="status-indicator disconnected"></span>
          <span className="status-text">Outlook Integration Coming Soon</span>
        </div>
      </div>

      <div className="chat-content">
        <div className="placeholder-message">
          <h3>📧 Outlook Integration</h3>
          <p>
            The Outlook Enhanced Chat feature is currently under development.
            This will allow you to manage your emails, calendar, and contacts
            directly through ATOM.
          </p>
          <div className="feature-list">
            <h4>Planned Features:</h4>
            <ul>
              <li>📨 Smart email management and responses</li>
              <li>📅 Calendar scheduling and meeting coordination</li>
              <li>👥 Contact management and organization</li>
              <li>🔍 Email search and filtering</li>
              <li>🤖 Automated email processing</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Outlook integration coming soon..."
          disabled
        />
        <button onClick={handleSend} disabled>
          Send
        </button>
      </div>

      <style>{`
        .outlook-chat-container {
          display: flex;
          flex-direction: column;
          height: 100%;
          padding: 20px;
          background: #f8f9fa;
        }

        .chat-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 15px;
          border-bottom: 2px solid #e9ecef;
        }

        .chat-header h2 {
          color: #0078d4;
          margin: 0;
          font-size: 1.5rem;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }

        .status-indicator.disconnected {
          background-color: #dc3545;
        }

        .status-text {
          color: #6c757d;
          font-size: 0.9rem;
        }

        .chat-content {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .placeholder-message {
          background: white;
          padding: 30px;
          border-radius: 12px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          max-width: 500px;
          text-align: center;
        }

        .placeholder-message h3 {
          color: #0078d4;
          margin-bottom: 15px;
        }

        .placeholder-message p {
          color: #495057;
          line-height: 1.6;
          margin-bottom: 20px;
        }

        .feature-list {
          text-align: left;
        }

        .feature-list h4 {
          color: #495057;
          margin-bottom: 10px;
        }

        .feature-list ul {
          color: #6c757d;
          line-height: 1.8;
        }

        .chat-input {
          display: flex;
          gap: 10px;
          margin-top: 20px;
        }

        .chat-input input {
          flex: 1;
          padding: 12px;
          border: 1px solid #ced4da;
          border-radius: 6px;
          font-size: 14px;
          background-color: #e9ecef;
        }

        .chat-input button {
          padding: 12px 24px;
          background-color: #6c757d;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: not-allowed;
          font-size: 14px;
        }
      `}</style>
    </div>
  );
};

export default OutlookEnhancedChat;
