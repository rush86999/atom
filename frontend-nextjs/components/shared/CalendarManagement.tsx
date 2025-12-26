import React, { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Plus,
  Clock,
  Edit,
  Trash,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";

export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  start: Date;
  end: Date;
  location?: string;
  attendees?: string[];
  status: "confirmed" | "tentative" | "cancelled";
  recurring?: {
    frequency: "daily" | "weekly" | "monthly" | "yearly";
    interval: number;
    endDate?: Date;
  };
  platform: "google" | "outlook" | "local";
  color?: string;
}

export interface CalendarView {
  type: "day" | "week" | "month";
  currentDate: Date;
}

export interface Conflict {
  event1: CalendarEvent;
  event2: CalendarEvent;
  overlapMinutes: number;
}

export interface CalendarManagementProps {
  onEventCreate?: (event: CalendarEvent) => void;
  onEventUpdate?: (eventId: string, updates: Partial<CalendarEvent>) => void;
  onEventDelete?: (eventId: string) => void;
  initialEvents?: CalendarEvent[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const CalendarManagement: React.FC<CalendarManagementProps> = ({
  onEventCreate,
  onEventUpdate,
  onEventDelete,
  initialEvents = [],
  showNavigation = true,
  compactView = false,
}) => {
  const [events, setEvents] = useState<CalendarEvent[]>(initialEvents);
  const [view, setView] = useState<CalendarView>({
    type: "week",
    currentDate: new Date(),
  });
  const [loading, setLoading] = useState(false);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(
    null,
  );
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const { toast } = useToast();

  // Sync with initialEvents
  useEffect(() => {
    setEvents(initialEvents);
  }, [initialEvents]);

  const detectConflicts = (events: CalendarEvent[]): Conflict[] => {
    const conflicts: Conflict[] = [];
    for (let i = 0; i < events.length; i++) {
      for (let j = i + 1; j < events.length; j++) {
        const event1 = events[i];
        const event2 = events[j];
        if (event1.start < event2.end && event1.end > event2.start) {
          const overlapStart = new Date(
            Math.max(event1.start.getTime(), event2.start.getTime()),
          );
          const overlapEnd = new Date(
            Math.min(event1.end.getTime(), event2.end.getTime()),
          );
          const overlapMinutes =
            (overlapEnd.getTime() - overlapStart.getTime()) / (1000 * 60);
          conflicts.push({ event1, event2, overlapMinutes });
        }
      }
    }
    return conflicts;
  };

  useEffect(() => {
    setConflicts(detectConflicts(events));
  }, [events]);

  const handleCreateEvent = (eventData: Omit<CalendarEvent, "id">) => {
    const newEvent: CalendarEvent = {
      ...eventData,
      id: Date.now().toString(),
    };
    setEvents((prev) => [...prev, newEvent]);
    onEventCreate?.(newEvent);
    toast({
      title: "Event created",
      description: "Your event has been successfully created.",
      duration: 2000,
    });
  };

  const handleUpdateEvent = (
    eventId: string,
    updates: Partial<CalendarEvent>,
  ) => {
    setEvents((prev) =>
      prev.map((event) =>
        event.id === eventId ? { ...event, ...updates } : event,
      ),
    );
    onEventUpdate?.(eventId, updates);
    toast({
      title: "Event updated",
      description: "Your event has been successfully updated.",
      duration: 2000,
    });
  };

  const handleDeleteEvent = (eventId: string) => {
    setEvents((prev) => prev.filter((event) => event.id !== eventId));
    onEventDelete?.(eventId);
    toast({
      title: "Event deleted",
      description: "Your event has been successfully deleted.",
      duration: 2000,
    });
  };

  const navigateDate = (direction: "prev" | "next") => {
    const newDate = new Date(view.currentDate);
    if (view.type === "day") {
      newDate.setDate(newDate.getDate() + (direction === "next" ? 1 : -1));
    } else if (view.type === "week") {
      newDate.setDate(newDate.getDate() + (direction === "next" ? 7 : -7));
    } else {
      newDate.setMonth(newDate.getMonth() + (direction === "next" ? 1 : -1));
    }
    setView((prev) => ({ ...prev, currentDate: newDate }));
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  };

  const getEventsForDate = (date: Date) => {
    return events.filter((event) => {
      const eventDate = new Date(event.start);
      return eventDate.toDateString() === date.toDateString();
    });
  };

  const EventForm: React.FC<{
    event?: CalendarEvent;
    onSubmit: (data: Omit<CalendarEvent, "id">) => void;
    onCancel: () => void;
  }> = ({ event, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      title: event?.title || "",
      description: event?.description || "",
      start: event?.start.toISOString().slice(0, 16) || "",
      end: event?.end.toISOString().slice(0, 16) || "",
      location: event?.location || "",
      status: event?.status || "confirmed",
      platform: event?.platform || "google",
      color: event?.color || "#3182CE",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        title: formData.title,
        description: formData.description,
        start: new Date(formData.start),
        end: new Date(formData.end),
        location: formData.location,
        status: formData.status as "confirmed" | "tentative" | "cancelled",
        platform: formData.platform as "google" | "outlook" | "local",
        color: formData.color,
      });
      onCancel();
    };

    return (
      <form onSubmit={handleSubmit} data-testid="event-form" className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Title</label>
          <Input
            value={formData.title}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, title: e.target.value }))
            }
            placeholder="Event title"
            data-testid="event-title"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Description</label>
          <Textarea
            value={formData.description}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                description: e.target.value,
              }))
            }
            placeholder="Event description"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Start Time</label>
            <Input
              type="datetime-local"
              value={formData.start}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, start: e.target.value }))
              }
              data-testid="event-start"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">End Time</label>
            <Input
              type="datetime-local"
              value={formData.end}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, end: e.target.value }))
              }
              data-testid="event-end"
              required
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Location</label>
          <Input
            value={formData.location}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, location: e.target.value }))
            }
            placeholder="Event location"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Status</label>
            <Select
              value={formData.status}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, status: value as "confirmed" | "tentative" | "cancelled" }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="confirmed">Confirmed</SelectItem>
                <SelectItem value="tentative">Tentative</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Platform</label>
            <Select
              value={formData.platform}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, platform: value as "local" | "outlook" | "google" }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select platform" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="google">Google Calendar</SelectItem>
                <SelectItem value="outlook">Outlook Calendar</SelectItem>
                <SelectItem value="local">Local</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Color</label>
          <Input
            type="color"
            value={formData.color}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, color: e.target.value }))
            }
            className="h-10 w-full"
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit" data-testid="event-submit">
            {event ? "Update Event" : "Create Event"}
          </Button>
        </div>
      </form>
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <Spinner className="h-8 w-8" />
        <p className="mt-4 text-sm text-muted-foreground">Loading calendar...</p>
      </div>
    );
  }

  return (
    <div className={compactView ? "p-2" : "p-6"}>
      <div className={`flex flex-col gap-${compactView ? "3" : "6"}`}>
        {/* Header */}
        {showNavigation && (
          <div className="flex justify-between items-center">
            <h2 className={`font-bold ${compactView ? "text-xl" : "text-2xl"}`}>
              Calendar Management
            </h2>
            <Button
              size={compactView ? "sm" : "default"}
              onClick={() => {
                setSelectedEvent(null);
                setIsDialogOpen(true);
              }}
              data-testid="new-event-btn"
            >
              <Plus className="mr-2 h-4 w-4" />
              New Event
            </Button>
          </div>
        )}

        {/* View Controls */}
        {showNavigation && (
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div className="flex space-x-2">
                  <Button
                    size="sm"
                    variant={view.type === "day" ? "default" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "day" }))
                    }
                  >
                    Day
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "week" ? "default" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "week" }))
                    }
                  >
                    Week
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "month" ? "default" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "month" }))
                    }
                  >
                    Month
                  </Button>
                </div>

                <div className="flex items-center space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigateDate("prev")}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="font-bold min-w-[150px] text-center text-sm">
                    {view.currentDate.toLocaleDateString([], {
                      month: "long",
                      year: "numeric",
                      ...(view.type === "week" && { day: "numeric" }),
                    })}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigateDate("next")}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Conflict Alerts */}
        {conflicts.length > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Scheduling Conflicts</AlertTitle>
            <AlertDescription>
              Found {conflicts.length} scheduling conflict
              {conflicts.length > 1 ? "s" : ""}
            </AlertDescription>
          </Alert>
        )}

        {/* Calendar View */}
        <Card data-testid="calendar-view">
          <CardHeader className="pb-2">
            <CardTitle className={compactView ? "text-lg" : "text-xl"}>Schedule</CardTitle>
          </CardHeader>
          <CardContent>
            {view.type === "week" && (
              <div className="grid grid-cols-7 gap-2">
                {Array.from({ length: 7 }).map((_, index) => {
                  const date = new Date(view.currentDate);
                  date.setDate(date.getDate() - date.getDay() + index);
                  const dayEvents = getEventsForDate(date);

                  return (
                    <div key={index} className="border rounded-md p-2 min-h-[150px]">
                      <div className="font-bold mb-2 text-sm">
                        {formatDate(date)}
                      </div>
                      <div className="flex flex-col gap-1">
                        {dayEvents.map((event) => (
                          <div
                            key={event.id}
                            className="p-1 rounded text-white cursor-pointer text-xs"
                            style={{ backgroundColor: event.color || "#3182CE" }}
                            onClick={() => {
                              setSelectedEvent(event);
                              setIsDialogOpen(true);
                            }}
                          >
                            <div className="font-bold truncate">
                              {event.title}
                            </div>
                            <div className="text-[10px] opacity-90">
                              {formatTime(event.start)} -{" "}
                              {formatTime(event.end)}
                            </div>
                            <Badge
                              variant="secondary"
                              className="mt-1 text-[10px] h-4 px-1"
                            >
                              {event.platform}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upcoming Events */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className={compactView ? "text-lg" : "text-xl"}>Upcoming Events</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {events
                .filter((event) => event.start > new Date())
                .sort((a, b) => a.start.getTime() - b.start.getTime())
                .slice(0, compactView ? 3 : 5)
                .map((event) => (
                  <div
                    key={event.id}
                    className="flex justify-between items-center p-2 border rounded-md hover:bg-accent cursor-pointer transition-colors"
                    onClick={() => {
                      setSelectedEvent(event);
                      setIsDialogOpen(true);
                    }}
                  >
                    <div>
                      <div className={`font-bold ${compactView ? "text-sm" : "text-base"}`}>
                        {event.title}
                      </div>
                      <div className={`text-muted-foreground ${compactView ? "text-xs" : "text-sm"}`}>
                        {formatDate(event.start)} • {formatTime(event.start)} -{" "}
                        {formatTime(event.end)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={event.status === "confirmed" ? "default" : "secondary"}
                      >
                        {event.status}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEvent(event);
                          setIsDialogOpen(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteEvent(event.id);
                        }}
                      >
                        <Trash className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Event Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {selectedEvent ? "Edit Event" : "Create New Event"}
            </DialogTitle>
          </DialogHeader>
          <EventForm
            event={selectedEvent || undefined}
            onSubmit={(data) => {
              if (selectedEvent) {
                handleUpdateEvent(selectedEvent.id, data);
              } else {
                handleCreateEvent(data);
              }
              setIsDialogOpen(false);
            }}
            onCancel={() => setIsDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CalendarManagement;
