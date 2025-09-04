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
} from "@chakra-ui/react";
import {
  AddIcon,
  CalendarIcon,
  ChatIcon,
  CheckIcon,
  TimeIcon,
  ViewIcon,
} from "@chakra-ui/icons";

interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  description?: string;
  location?: string;
  attendees?: string[];
  status: "confirmed" | "tentative" | "cancelled";
}

interface Task {
  id: string;
  title: string;
  description?: string;
  dueDate: Date;
  priority: "high" | "medium" | "low";
  status: "todo" | "in-progress" | "completed";
  project?: string;
  tags?: string[];
}

interface Message {
  id: string;
  platform: "email" | "slack" | "teams" | "discord";
  from: string;
  subject: string;
  preview: string;
  timestamp: Date;
  unread: boolean;
  priority: "high" | "normal" | "low";
}

interface DashboardData {
  calendar: CalendarEvent[];
  tasks: Task[];
  messages: Message[];
  stats: {
    upcomingEvents: number;
    overdueTasks: number;
    unreadMessages: number;
    completedTasks: number;
  };
}

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const toast = useToast();

  const fetchDashboardData = async () => {
    try {
      const response = await fetch("/api/dashboard-dev");
      if (!response.ok) {
        throw new Error("Failed to fetch dashboard data");
      }
      const result = await response.json();
      setData(result);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load dashboard data",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
      console.error("Error fetching dashboard data:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  const handleCompleteTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/tasks/${taskId}/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: "completed" }),
      });
      if (response.ok) {
        toast({
          title: "Task completed",
          status: "success",
          duration: 2000,
          isClosable: true,
        });
        fetchDashboardData(); // Refresh data
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to complete task",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleMarkAsRead = async (messageId: string) => {
    try {
      const response = await fetch(`/api/messages/${messageId}/read`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ read: true }),
      });
      if (response.ok) {
        fetchDashboardData(); // Refresh data
      }
    } catch (error) {
      console.error("Error marking message as read:", error);
    }
  };

  if (loading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading your dashboard...</Text>
        </VStack>
      </Box>
    );
  }

  if (!data) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Heading size="lg">Unable to load dashboard</Heading>
          <Text>Please try refreshing the page</Text>
          <Button onClick={handleRefresh} isLoading={refreshing}>
            Refresh
          </Button>
        </VStack>
      </Box>
    );
  }

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString();
  };

  const isToday = (date: Date) => {
    const today = new Date();
    return new Date(date).toDateString() === today.toDateString();
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "red";
      case "medium":
        return "orange";
      case "low":
        return "green";
      default:
        return "gray";
    }
  };

  const getPlatformIcon = (platform: string) => {
    switch (platform) {
      case "email":
        return "📧";
      case "slack":
        return "💬";
      case "teams":
        return "💼";
      case "discord":
        return "🎮";
      default:
        return "💬";
    }
  };

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8}>
        <VStack align="start" spacing={1}>
          <Heading size="xl">Your Dashboard</Heading>
          <Text color="gray.600">
            Welcome back! Here's your overview for today.
          </Text>
        </VStack>
        <Button
          leftIcon={<AddIcon />}
          colorScheme="blue"
          onClick={handleRefresh}
          isLoading={refreshing}
        >
          Refresh
        </Button>
      </HStack>

      {/* Stats Overview */}
      <Grid templateColumns="repeat(4, 1fr)" gap={6} mb={8}>
        <Card>
          <CardBody>
            <VStack align="center">
              <CalendarIcon boxSize={6} color="blue.500" />
              <Text fontSize="2xl" fontWeight="bold">
                {data.stats.upcomingEvents}
              </Text>
              <Text color="gray.600">Upcoming Events</Text>
            </VStack>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <VStack align="center">
              <TimeIcon boxSize={6} color="red.500" />
              <Text fontSize="2xl" fontWeight="bold">
                {data.stats.overdueTasks}
              </Text>
              <Text color="gray.600">Overdue Tasks</Text>
            </VStack>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <VStack align="center">
              <ChatIcon boxSize={6} color="green.500" />
              <Text fontSize="2xl" fontWeight="bold">
                {data.stats.unreadMessages}
              </Text>
              <Text color="gray.600">Unread Messages</Text>
            </VStack>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <VStack align="center">
              <CheckIcon boxSize={6} color="purple.500" />
              <Text fontSize="2xl" fontWeight="bold">
                {data.stats.completedTasks}
              </Text>
              <Text color="gray.600">Completed Today</Text>
            </VStack>
          </CardBody>
        </Card>
      </Grid>

      {/* Main Content Grid */}
      <Grid templateColumns="repeat(3, 1fr)" gap={8}>
        {/* Calendar Events */}
        <GridItem colSpan={1}>
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Today's Calendar</Heading>
                <Badge colorScheme="blue">{data.calendar.length} events</Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                {data.calendar.slice(0, 5).map((event) => (
                  <Box key={event.id} p={3} borderWidth="1px" borderRadius="md">
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="bold">{event.title}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {formatTime(event.start)} - {formatTime(event.end)}
                        </Text>
                        {event.location && (
                          <Text fontSize="sm" color="gray.500">
                            {event.location}
                          </Text>
                        )}
                      </VStack>
                      <Badge
                        colorScheme={
                          event.status === "confirmed" ? "green" : "yellow"
                        }
                      >
                        {event.status}
                      </Badge>
                    </HStack>
                  </Box>
                ))}
                {data.calendar.length === 0 && (
                  <Text color="gray.500" textAlign="center">
                    No events scheduled for today
                  </Text>
                )}
              </VStack>
            </CardBody>
            <CardFooter>
              <Button
                leftIcon={<CalendarIcon />}
                variant="outline"
                size="sm"
                w="full"
              >
                View Full Calendar
              </Button>
            </CardFooter>
          </Card>
        </GridItem>

        {/* Tasks */}
        <GridItem colSpan={1}>
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Tasks</Heading>
                <Badge colorScheme="orange">{data.tasks.length} tasks</Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={3} align="stretch">
                {data.tasks.slice(0, 6).map((task) => (
                  <Box
                    key={task.id}
                    p={3}
                    borderWidth="1px"
                    borderRadius="md"
                    borderColor={
                      task.priority === "high" ? "red.200" : "gray.200"
                    }
                    bg={task.status === "completed" ? "green.50" : "white"}
                  >
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1} flex={1}>
                        <HStack>
                          <Text
                            fontWeight="bold"
                            textDecoration={
                              task.status === "completed"
                                ? "line-through"
                                : "none"
                            }
                            color={
                              task.status === "completed"
                                ? "gray.600"
                                : "inherit"
                            }
                          >
                            {task.title}
                          </Text>
                          <Badge
                            colorScheme={getPriorityColor(task.priority)}
                            size="sm"
                          >
                            {task.priority}
                          </Badge>
                        </HStack>
                        {task.description && (
                          <Text fontSize="sm" color="gray.600" noOfLines={1}>
                            {task.description}
                          </Text>
                        )}
                        <Text fontSize="sm" color="gray.500">
                          Due:{" "}
                          {isToday(task.dueDate)
                            ? "Today"
                            : formatDate(task.dueDate)}
                        </Text>
                      </VStack>
                      {task.status !== "completed" && (
                        <IconButton
                          aria-label="Complete task"
                          icon={<CheckIcon />}
                          size="sm"
                          colorScheme="green"
                          onClick={() => handleCompleteTask(task.id)}
                        />
                      )}
                    </HStack>
                  </Box>
                ))}
                {data.tasks.length === 0 && (
                  <Text color="gray.500" textAlign="center">
                    No tasks assigned
                  </Text>
                )}
              </VStack>
            </CardBody>
            <CardFooter>
              <Button
                leftIcon={<AddIcon />}
                variant="outline"
                size="sm"
                w="full"
              >
                Add New Task
              </Button>
            </CardFooter>
          </Card>
        </GridItem>

        {/* Messages */}
        <GridItem colSpan={1}>
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Messages</Heading>
                <Badge colorScheme="green">
                  {data.messages.length} messages
                </Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={3} align="stretch">
                {data.messages.slice(0, 5).map((message) => (
                  <Box
                    key={message.id}
                    p={3}
                    borderWidth="1px"
                    borderRadius="md"
                    bg={message.unread ? "blue.50" : "white"}
                    borderColor={message.unread ? "blue.200" : "gray.200"}
                    cursor="pointer"
                    onClick={() => handleMarkAsRead(message.id)}
                  >
                    <HStack spacing={3} align="start">
                      <Text fontSize="lg">
                        {getPlatformIcon(message.platform)}
                      </Text>
                      <VStack align="start" spacing={1} flex={1}>
                        <HStack justify="space-between" w="full">
                          <Text fontWeight="bold" noOfLines={1}>
                            {message.from}
                          </Text>
                          <Text fontSize="sm" color="gray.500">
                            {formatTime(message.timestamp)}
                          </Text>
                        </HStack>
                        <Text fontWeight="medium" noOfLines={1}>
                          {message.subject}
                        </Text>
                        <Text fontSize="sm" color="gray.600" noOfLines={2}>
                          {message.preview}
                        </Text>
                      </VStack>
                      {message.unread && (
                        <Badge colorScheme="blue" ml={2}>
                          New
                        </Badge>
                      )}
                    </HStack>
                  </Box>
                ))}
                {data.messages.length === 0 && (
                  <Text color="gray.500" textAlign="center">
                    No messages
                  </Text>
                )}
              </VStack>
            </CardBody>
            <CardFooter>
              <Button
                leftIcon={<ViewIcon />}
                variant="outline"
                size="sm"
                w="full"
              >
                View All Messages
              </Button>
            </CardFooter>
          </Card>
        </GridItem>
      </Grid>
    </Box>
  );
};

export default Dashboard;
