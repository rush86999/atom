import React, { useState, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  IconButton,
  Badge,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Checkbox,
  Switch,
  useDisclosure,
  SimpleGrid,
  Flex,
  Divider,
  Alert,
  AlertIcon,
} from "@chakra-ui/react";
import {
  AddIcon,
  TimeIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@chakra-ui/icons";

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
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

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
      status: "success",
      duration: 2000,
      isClosable: true,
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
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteEvent = (eventId: string) => {
    setEvents((prev) => prev.filter((event) => event.id !== eventId));
    onEventDelete?.(eventId);
    toast({
      title: "Event deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
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
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Title</FormLabel>
            <Input
              value={formData.title}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, title: e.target.value }))
              }
              placeholder="Event title"
            />
          </FormControl>

          <FormControl>
            <FormLabel>Description</FormLabel>
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
          </FormControl>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl isRequired>
              <FormLabel>Start Time</FormLabel>
              <Input
                type="datetime-local"
                value={formData.start}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, start: e.target.value }))
                }
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>End Time</FormLabel>
              <Input
                type="datetime-local"
                value={formData.end}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, end: e.target.value }))
                }
              />
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Location</FormLabel>
            <Input
              value={formData.location}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, location: e.target.value }))
              }
              placeholder="Event location"
            />
          </FormControl>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl>
              <FormLabel>Status</FormLabel>
              <Select
                value={formData.status}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, status: e.target.value }))
                }
              >
                <option value="confirmed">Confirmed</option>
                <option value="tentative">Tentative</option>
                <option value="cancelled">Cancelled</option>
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Platform</FormLabel>
              <Select
                value={formData.platform}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, platform: e.target.value }))
                }
              >
                <option value="google">Google Calendar</option>
                <option value="outlook">Outlook Calendar</option>
                <option value="local">Local</option>
              </Select>
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Color</FormLabel>
            <Input
              type="color"
              value={formData.color}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, color: e.target.value }))
              }
            />
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {event ? "Update Event" : "Create Event"}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading calendar...</Text>
      </Box>
    );
  }

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>
              Calendar Management
            </Heading>
            <Button
              leftIcon={<AddIcon />}
              colorScheme="blue"
              size={compactView ? "sm" : "md"}
              onClick={() => {
                setSelectedEvent(null);
                onOpen();
              }}
            >
              New Event
            </Button>
          </Flex>
        )}

        {/* View Controls */}
        {showNavigation && (
          <Card size={compactView ? "sm" : "md"}>
            <CardBody>
              <Flex justify="space-between" align="center">
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    variant={view.type === "day" ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "day" }))
                    }
                  >
                    Day
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "week" ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "week" }))
                    }
                  >
                    Week
                  </Button>
                  <Button
                    size="sm"
                    variant={view.type === "month" ? "solid" : "outline"}
                    onClick={() =>
                      setView((prev) => ({ ...prev, type: "month" }))
                    }
                  >
                    Month
                  </Button>
                </HStack>

                <HStack spacing={2}>
                  <IconButton
                    aria-label="Previous"
                    icon={<ChevronLeftIcon />}
                    size="sm"
                    onClick={() => navigateDate("prev")}
                  />
                  <Text
                    fontWeight="bold"
                    minWidth="150px"
                    textAlign="center"
                    fontSize="sm"
                  >
                    {view.currentDate.toLocaleDateString([], {
                      month: "long",
                      year: "numeric",
                      ...(view.type === "week" && { day: "numeric" }),
                    })}
                  </Text>
                  <IconButton
                    aria-label="Next"
                    icon={<ChevronRightIcon />}
                    size="sm"
                    onClick={() => navigateDate("next")}
                  />
                </HStack>
              </Flex>
            </CardBody>
          </Card>
        )}

        {/* Conflict Alerts */}
        {conflicts.length > 0 && (
          <Alert status="warning" size="sm">
            <AlertIcon />
            Found {conflicts.length} scheduling conflict
            {conflicts.length > 1 ? "s" : ""}
          </Alert>
        )}

        {/* Calendar View */}
        <Card size={compactView ? "sm" : "md"}>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Schedule</Heading>
          </CardHeader>
          <CardBody>
            {view.type === "week" && (
              <SimpleGrid columns={7} spacing={2}>
                {Array.from({ length: 7 }).map((_, index) => {
                  const date = new Date(view.currentDate);
                  date.setDate(date.getDate() - date.getDay() + index);
                  const dayEvents = getEventsForDate(date);

                  return (
                    <Box key={index} borderWidth="1px" borderRadius="md" p={2}>
                      <Text fontWeight="bold" mb={1} fontSize="sm">
                        {formatDate(date)}
                      </Text>
                      <VStack spacing={1} align="stretch">
                        {dayEvents.map((event) => (
                          <Box
                            key={event.id}
                            p={1}
                            bg={event.color}
                            color="white"
                            borderRadius="md"
                            cursor="pointer"
                            onClick={() => {
                              setSelectedEvent(event);
                              onOpen();
                            }}
                          >
                            <Text fontSize="xs" fontWeight="bold" noOfLines={1}>
                              {event.title}
                            </Text>
                            <Text fontSize="2xs">
                              {formatTime(event.start)} -{" "}
                              {formatTime(event.end)}
                            </Text>
                            <Badge
                              colorScheme={
                                event.platform === "google" ? "blue" : "green"
                              }
                              size="xs"
                            >
                              {event.platform}
                            </Badge>
                          </Box>
                        ))}
                      </VStack>
                    </Box>
                  );
                })}
              </SimpleGrid>
            )}
          </CardBody>
        </Card>

        {/* Upcoming Events */}
        <Card size={compactView ? "sm" : "md"}>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Upcoming Events</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={2} align="stretch">
              {events
                .filter((event) => event.start > new Date())
                .sort((a, b) => a.start.getTime() - b.start.getTime())
                .slice(0, compactView ? 3 : 5)
                .map((event) => (
                  <Flex
                    key={event.id}
                    justify="space-between"
                    align="center"
                    p={2}
                    borderWidth="1px"
                    borderRadius="md"
                    cursor="pointer"
                    onClick={() => {
                      setSelectedEvent(event);
                      onOpen();
                    }}
                  >
                    <Box>
                      <Text
                        fontWeight="bold"
                        fontSize={compactView ? "sm" : "md"}
                      >
                        {event.title}
                      </Text>
                      <Text
                        fontSize={compactView ? "xs" : "sm"}
                        color="gray.600"
                      >
                        {formatDate(event.start)} • {formatTime(event.start)} -{" "}
                        {formatTime(event.end)}
                      </Text>
                    </Box>
                    <HStack>
                      <Badge
                        colorScheme={
                          event.status === "confirmed" ? "green" : "yellow"
                        }
                        size={compactView ? "sm" : "md"}
                      >
                        {event.status}
                      </Badge>
                      <IconButton
                        aria-label="Edit event"
                        icon={<EditIcon />}
                        size="xs"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEvent(event);
                          onOpen();
                        }}
                      />
                      <IconButton
                        aria-label="Delete event"
                        icon={<DeleteIcon />}
                        size="xs"
                        variant="ghost"
                        colorScheme="red"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteEvent(event.id);
                        }}
                      />
                    </HStack>
                  </Flex>
                ))}
            </VStack>
          </CardBody>
        </Card>
      </VStack>

      {/* Event Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size={compactView ? "md" : "lg"}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedEvent ? "Edit Event" : "Create New Event"}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <EventForm
              event={selectedEvent || undefined}
              onSubmit={(data) => {
                if (selectedEvent) {
                  handleUpdateEvent(selectedEvent.id, data);
                } else {
                  handleCreateEvent(data);
                }
              }}
              onCancel={onClose}
            />
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default CalendarManagement;
