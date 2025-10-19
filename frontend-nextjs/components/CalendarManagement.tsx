import React from "react";
import SharedCalendarManagement from "./shared/CalendarManagement";

const CalendarManagement: React.FC = () => {
  return (
    <SharedCalendarManagement
      showNavigation={true}
      compactView={false}
      onEventCreate={(event) => {
        console.log("Event created:", event);
        // TODO: Implement API call to backend
      }}
      onEventUpdate={(eventId, updates) => {
        console.log("Event updated:", eventId, updates);
        // TODO: Implement API call to backend
      }}
      onEventDelete={(eventId) => {
        console.log("Event deleted:", eventId);
        // TODO: Implement API call to backend
      }}
    />
  );
};

export default CalendarManagement;
