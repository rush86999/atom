import React, { useState, useEffect } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2 } from "lucide-react";

const locales = {
    'en-US': enUS,
};

const localizer = dateFnsLocalizer({
    format,
    parse,
    startOfWeek,
    getDay,
    locales,
});

interface CalendarEvent {
    id: string;
    title: string;
    start: Date;
    end: Date;
    description?: string;
    location?: string;
    status?: string;
    platform?: string;
    color?: string;
}

const CalendarView = () => {
    const [events, setEvents] = useState<CalendarEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const { toast } = useToast();

    // New Event Form State
    const [newEvent, setNewEvent] = useState({
        title: '',
        start: '',
        end: '',
        description: '',
        location: '',
        color: '#3182CE'
    });

    const fetchEvents = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/v1/calendar/events');
            const data = await response.json();
            if (data.success) {
                // Convert string dates to Date objects
                const parsedEvents = data.events.map((event: any) => ({
                    ...event,
                    start: new Date(event.start),
                    end: new Date(event.end),
                }));
                setEvents(parsedEvents);
            }
        } catch (error) {
            console.error("Failed to fetch events:", error);
            toast({
                title: "Error fetching events",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchEvents();
    }, []);

    const handleCreateEvent = async () => {
        try {
            const response = await fetch('/api/v1/calendar/events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...newEvent,
                    start: new Date(newEvent.start).toISOString(),
                    end: new Date(newEvent.end).toISOString(),
                }),
            });

            const data = await response.json();
            if (data.success) {
                toast({
                    title: "Event created",
                    description: "Your event has been successfully scheduled.",
                });
                setIsModalOpen(false);
                fetchEvents(); // Refresh events
                // Reset form
                setNewEvent({
                    title: '',
                    start: '',
                    end: '',
                    description: '',
                    location: '',
                    color: '#3182CE'
                });
            }
        } catch (error) {
            toast({
                title: "Error creating event",
                variant: "destructive",
            });
        }
    };

    if (loading) {
        return (
            <div className="h-[500px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="h-[80vh] p-4 bg-white dark:bg-gray-900 rounded-lg border shadow-sm flex flex-col">
            <div className="mb-4 flex justify-between items-center">
                <h2 className="text-2xl font-bold">Calendar</h2>
                <Button onClick={() => setIsModalOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    New Event
                </Button>
            </div>

            <div className="flex-1 calendar-container">
                <Calendar
                    localizer={localizer}
                    events={events}
                    startAccessor="start"
                    endAccessor="end"
                    style={{ height: '100%' }}
                    eventPropGetter={(event) => ({
                        style: {
                            backgroundColor: event.color || '#3182CE',
                        },
                    })}
                />
            </div>

            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Event</DialogTitle>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Title</Label>
                            <Input
                                placeholder="Meeting with Team"
                                value={newEvent.title}
                                onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Start Time</Label>
                            <Input
                                type="datetime-local"
                                value={newEvent.start}
                                onChange={(e) => setNewEvent({ ...newEvent, start: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>End Time</Label>
                            <Input
                                type="datetime-local"
                                value={newEvent.end}
                                onChange={(e) => setNewEvent({ ...newEvent, end: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Description</Label>
                            <Input
                                placeholder="Details about the event"
                                value={newEvent.description}
                                onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Color</Label>
                            <Select
                                value={newEvent.color}
                                onValueChange={(value) => setNewEvent({ ...newEvent, color: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select color" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="#3182CE">Blue</SelectItem>
                                    <SelectItem value="#38A169">Green</SelectItem>
                                    <SelectItem value="#E53E3E">Red</SelectItem>
                                    <SelectItem value="#D69E2E">Yellow</SelectItem>
                                    <SelectItem value="#805AD5">Purple</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreateEvent}>Save</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default CalendarView;
