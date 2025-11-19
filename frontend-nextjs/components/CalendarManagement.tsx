import React, { useState, useEffect } from "react";
import SharedCalendarManagement, { CalendarEvent } from "./shared/CalendarManagement";
import { useToast } from "@chakra-ui/react";

const CalendarManagement: React.FC = () => {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const fetchEvents = async () => {
    try {
      const response = await fetch("/api/v1/calendar/events");
      if (response.ok) {
        const data = await response.json();
        // Convert date strings to Date objects
        const parsedEvents = data.events.map((e: any) => ({
          ...e,
          start: new Date(e.start),
          end: new Date(e.end),
        }));
        setEvents(parsedEvents);
      } else {
        console.error("Failed to fetch events");
        toast({
          title: "Error fetching events",
          status: "error",
          duration: 3000,
        });
      }
    } catch (error) {
      console.error("Error fetching events:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const handleCreateEvent = async (event: CalendarEvent) => {
    try {
      const response = await fetch("/api/v1/calendar/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
      });

      if (response.ok) {
        const data = await response.json();
        const newEvent = {
          ...data.event,
          start: new Date(data.event.start),
          end: new Date(data.event.end)
        };
        setEvents((prev) => [...prev, newEvent]);
        toast({ title: "Event created", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to create event");
      }
    } catch (error) {
      console.error("Error creating event:", error);
      toast({ title: "Failed to create event", status: "error", duration: 3000 });
    }
  };

  const handleUpdateEvent = async (eventId: string, updates: Partial<CalendarEvent>) => {
    try {
      const response = await fetch(`/api/v1/calendar/events/${eventId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (response.ok) {
        const data = await response.json();
        const updatedEvent = {
          ...data.event,
          start: new Date(data.event.start),
          end: new Date(data.event.end)
        };
        setEvents((prev) => prev.map(e => e.id === eventId ? updatedEvent : e));
        toast({ title: "Event updated", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to update event");
      }
    } catch (error) {
      console.error("Error updating event:", error);
      toast({ title: "Failed to update event", status: "error", duration: 3000 });
    }
  };

  const handleDeleteEvent = async (eventId: string) => {
    try {
      const response = await fetch(`/api/v1/calendar/events/${eventId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setEvents((prev) => prev.filter(e => e.id !== eventId));
        toast({ title: "Event deleted", status: "success", duration: 2000 });
      } else {
        throw new Error("Failed to delete event");
      }
    } catch (error) {
      console.error("Error deleting event:", error);
      toast({ title: "Failed to delete event", status: "error", duration: 3000 });
    }
  };

  return (
    <SharedCalendarManagement
      showNavigation={true}
      compactView={false}
      initialEvents={events}
      onEventCreate={handleCreateEvent}
      onEventUpdate={handleUpdateEvent}
      onEventDelete={handleDeleteEvent}
    />
  );
};

export default CalendarManagement;
