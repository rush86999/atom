import React from "react";
import CommunicationHub from "./shared/CommunicationHub";

const CommunicationHubWrapper: React.FC = () => {
  return (
    <CommunicationHub
      showNavigation={true}
      compactView={false}
      onMessageSend={(message) => {
        console.log("Message sent:", message);
        // TODO: Implement API call to backend
      }}
      onMessageUpdate={(messageId, updates) => {
        console.log("Message updated:", messageId, updates);
        // TODO: Implement API call to backend
      }}
      onMessageDelete={(messageId) => {
        console.log("Message deleted:", messageId);
        // TODO: Implement API call to backend
      }}
      onConversationCreate={(conversation) => {
        console.log("Conversation created:", conversation);
        // TODO: Implement API call to backend
      }}
    />
  );
};

export default CommunicationHubWrapper;
