// Add data-testid attributes to key elements
const ChatInterface = () => {
  return (
    <div>
      <input
        data-testid="agent-chat-input"
        type="text"
        placeholder="Message Atom agent..."
      />
      <button data-testid="send-button">Send</button>
      
      <div data-testid="atom-agent-response">
        {/* Agent responses will appear here */}
      </div>

      <input
        data-testid="upload-button"
        type="file"
        style={{ display: 'none' }}
      />
    </div>
  );
};