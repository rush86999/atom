import React, { useState, useEffect } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import format from 'date-fns/format';
import parse from 'date-fns/parse';
import startOfWeek from 'date-fns/startOfWeek';
import getDay from 'date-fns/getDay';
import enUS from 'date-fns/locale/en-US';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { Box, useColorModeValue, Spinner, Center, Text, Button, Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton, FormControl, FormLabel, Input, Select, useDisclosure, useToast } from '@chakra-ui/react';
import { AddIcon } from '@chakra-ui/icons';

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
    const { isOpen, onOpen, onClose } = useDisclosure();
    const toast = useToast();

    // New Event Form State
    const [newEvent, setNewEvent] = useState({
        title: '',
        start: '',
        end: '',
        description: '',
        location: '',
        color: '#3182CE'
    });

    const bgColor = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

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
                status: "error",
                duration: 3000,
                isClosable: true,
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
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                onClose();
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
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        }
    };

    if (loading) {
        return (
            <Center h="500px">
                <Spinner size="xl" />
            </Center>
        );
    }

    return (
        <Box
            h="80vh"
            p={4}
            bg={bgColor}
            borderRadius="lg"
            border="1px"
            borderColor={borderColor}
            boxShadow="sm"
        >
            <Box mb={4} display="flex" justifyContent="space-between" alignItems="center">
                <Text fontSize="2xl" fontWeight="bold">Calendar</Text>
                <Button leftIcon={<AddIcon />} colorScheme="blue" onClick={onOpen}>
                    New Event
                </Button>
            </Box>

            <Calendar
                localizer={localizer}
                events={events}
                startAccessor="start"
                endAccessor="end"
                style={{ height: 'calc(100% - 60px)' }}
                eventPropGetter={(event) => ({
                    style: {
                        backgroundColor: event.color || '#3182CE',
                    },
                })}
            />

            <Modal isOpen={isOpen} onClose={onClose}>
                <ModalOverlay />
                <ModalContent>
                    <ModalHeader>Create New Event</ModalHeader>
                    <ModalCloseButton />
                    <ModalBody pb={6}>
                        <FormControl>
                            <FormLabel>Title</FormLabel>
                            <Input
                                placeholder="Meeting with Team"
                                value={newEvent.title}
                                onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Start Time</FormLabel>
                            <Input
                                type="datetime-local"
                                value={newEvent.start}
                                onChange={(e) => setNewEvent({ ...newEvent, start: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>End Time</FormLabel>
                            <Input
                                type="datetime-local"
                                value={newEvent.end}
                                onChange={(e) => setNewEvent({ ...newEvent, end: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Description</FormLabel>
                            <Input
                                placeholder="Details about the event"
                                value={newEvent.description}
                                onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Color</FormLabel>
                            <Select
                                value={newEvent.color}
                                onChange={(e) => setNewEvent({ ...newEvent, color: e.target.value })}
                            >
                                <option value="#3182CE">Blue</option>
                                <option value="#38A169">Green</option>
                                <option value="#E53E3E">Red</option>
                                <option value="#D69E2E">Yellow</option>
                                <option value="#805AD5">Purple</option>
                            </Select>
                        </FormControl>
                    </ModalBody>

                    <ModalFooter>
                        <Button colorScheme="blue" mr={3} onClick={handleCreateEvent}>
                            Save
                        </Button>
                        <Button onClick={onClose}>Cancel</Button>
                    </ModalFooter>
                </ModalContent>
            </Modal>
        </Box>
    );
};

export default CalendarView;
