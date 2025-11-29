import React from 'react';
import CalendarManagement from '../components/CalendarManagement';

const CalendarPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50" data-testid="calendar-view">
      <CalendarManagement />
    </div>
  );
};

export default CalendarPage;
