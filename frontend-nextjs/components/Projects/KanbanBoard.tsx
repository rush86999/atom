import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from 'react-beautiful-dnd';
import { Box, Text, VStack, HStack, Badge, useColorModeValue, Spinner, Center, Button, useToast, Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton, FormControl, FormLabel, Input, Select, useDisclosure, Textarea } from '@chakra-ui/react';
import { AddIcon } from '@chakra-ui/icons';

interface Task {
    id: string;
    title: string;
    description?: string;
    status: string;
    priority: string;
    dueDate?: string;
    assignee?: string;
    tags?: string[];
}

interface Columns {
    [key: string]: {
        name: string;
        items: Task[];
    };
}

const KanbanBoard = () => {
    const [columns, setColumns] = useState<Columns>({
        todo: { name: 'To Do', items: [] },
        'in-progress': { name: 'In Progress', items: [] },
        completed: { name: 'Completed', items: [] },
    });
    const [loading, setLoading] = useState(true);
    const { isOpen, onOpen, onClose } = useDisclosure();
    const toast = useToast();

    // New Task Form State
    const [newTask, setNewTask] = useState({
        title: '',
        description: '',
        priority: 'medium',
        dueDate: '',
        status: 'todo'
    });

    const bgColor = useColorModeValue('gray.50', 'gray.900');
    const cardBg = useColorModeValue('white', 'gray.800');
    const borderColor = useColorModeValue('gray.200', 'gray.700');

    const fetchTasks = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/v1/tasks?platform=all');
            const data = await response.json();

            if (data.success) {
                const tasks: Task[] = data.tasks;
                const newColumns = {
                    todo: { name: 'To Do', items: [] as Task[] },
                    'in-progress': { name: 'In Progress', items: [] as Task[] },
                    completed: { name: 'Completed', items: [] as Task[] },
                };

                tasks.forEach(task => {
                    const status = task.status.toLowerCase();
                    if (newColumns[status]) {
                        newColumns[status].items.push(task);
                    } else {
                        // Fallback for unknown statuses
                        newColumns['todo'].items.push(task);
                    }
                });

                setColumns(newColumns);
            }
        } catch (error) {
            console.error("Failed to fetch tasks:", error);
            toast({
                title: "Error fetching tasks",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    const onDragEnd = async (result: DropResult) => {
        if (!result.destination) return;
        const { source, destination } = result;

        if (source.droppableId !== destination.droppableId) {
            const sourceColumn = columns[source.droppableId];
            const destColumn = columns[destination.droppableId];
            const sourceItems = [...sourceColumn.items];
            const destItems = [...destColumn.items];
            const [removed] = sourceItems.splice(source.index, 1);

            // Update local state immediately for UI responsiveness
            const newStatus = destination.droppableId;
            const updatedTask = { ...removed, status: newStatus };
            destItems.splice(destination.index, 0, updatedTask);

            setColumns({
                ...columns,
                [source.droppableId]: {
                    ...sourceColumn,
                    items: sourceItems,
                },
                [destination.droppableId]: {
                    ...destColumn,
                    items: destItems,
                },
            });

            // API Call to update status
            try {
                await fetch(`/api/v1/tasks/${removed.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: newStatus })
                });
            } catch (error) {
                toast({
                    title: "Failed to update task status",
                    status: "error",
                    duration: 3000,
                    isClosable: true,
                });
                // Revert state if needed (omitted for brevity)
            }
        } else {
            const column = columns[source.droppableId];
            const copiedItems = [...column.items];
            const [removed] = copiedItems.splice(source.index, 1);
            copiedItems.splice(destination.index, 0, removed);

            setColumns({
                ...columns,
                [source.droppableId]: {
                    ...column,
                    items: copiedItems,
                },
            });
        }
    };

    const handleCreateTask = async () => {
        try {
            const response = await fetch('/api/v1/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...newTask,
                    dueDate: newTask.dueDate ? new Date(newTask.dueDate).toISOString() : new Date().toISOString(),
                }),
            });

            const data = await response.json();
            if (data.success) {
                toast({
                    title: "Task created",
                    status: "success",
                    duration: 3000,
                    isClosable: true,
                });
                onClose();
                fetchTasks(); // Refresh tasks
                setNewTask({
                    title: '',
                    description: '',
                    priority: 'medium',
                    dueDate: '',
                    status: 'todo'
                });
            }
        } catch (error) {
            toast({
                title: "Error creating task",
                status: "error",
                duration: 3000,
                isClosable: true,
            });
        }
    };

    const getPriorityColor = (priority: string) => {
        switch (priority.toLowerCase()) {
            case 'high': return 'red';
            case 'medium': return 'yellow';
            case 'low': return 'green';
            default: return 'gray';
        }
    };

    // Strict Mode Droppable Fix
    const [enabled, setEnabled] = useState(false);
    useEffect(() => {
        const animation = requestAnimationFrame(() => setEnabled(true));
        return () => {
            cancelAnimationFrame(animation);
            setEnabled(false);
        };
    }, []);

    if (!enabled) {
        return null;
    }

    if (loading) {
        return (
            <Center h="500px">
                <Spinner size="xl" />
            </Center>
        );
    }

    return (
        <Box h="80vh" p={4}>
            <Box mb={6} display="flex" justifyContent="space-between" alignItems="center">
                <Text fontSize="2xl" fontWeight="bold">Project Board</Text>
                <Button leftIcon={<AddIcon />} colorScheme="teal" onClick={onOpen}>
                    New Task
                </Button>
            </Box>

            <DragDropContext onDragEnd={onDragEnd}>
                <HStack spacing={8} alignItems="flex-start" h="full" overflowX="auto">
                    {Object.entries(columns).map(([columnId, column]) => (
                        <Box
                            key={columnId}
                            bg={bgColor}
                            w="350px"
                            minW="300px"
                            p={4}
                            borderRadius="lg"
                            border="1px"
                            borderColor={borderColor}
                            h="full"
                            display="flex"
                            flexDirection="column"
                        >
                            <Text fontWeight="bold" mb={4} fontSize="lg">{column.name} <Badge ml={2}>{column.items.length}</Badge></Text>
                            <Droppable droppableId={columnId}>
                                {(provided, snapshot) => (
                                    <VStack
                                        {...provided.droppableProps}
                                        ref={provided.innerRef}
                                        spacing={4}
                                        align="stretch"
                                        flex="1"
                                        overflowY="auto"
                                        bg={snapshot.isDraggingOver ? useColorModeValue('gray.100', 'gray.700') : 'transparent'}
                                        p={2}
                                        borderRadius="md"
                                        transition="background-color 0.2s ease"
                                    >
                                        {column.items.map((task, index) => (
                                            <Draggable key={task.id} draggableId={task.id} index={index}>
                                                {(provided, snapshot) => (
                                                    <Box
                                                        ref={provided.innerRef}
                                                        {...provided.draggableProps}
                                                        {...provided.dragHandleProps}
                                                        bg={cardBg}
                                                        p={4}
                                                        borderRadius="md"
                                                        boxShadow={snapshot.isDragging ? "lg" : "sm"}
                                                        border="1px"
                                                        borderColor={borderColor}
                                                        _hover={{ boxShadow: "md" }}
                                                    >
                                                        <HStack justify="space-between" mb={2}>
                                                            <Badge colorScheme={getPriorityColor(task.priority)}>{task.priority}</Badge>
                                                            {task.assignee && <Badge variant="outline">{task.assignee}</Badge>}
                                                        </HStack>
                                                        <Text fontWeight="semibold" mb={1}>{task.title}</Text>
                                                        <Text fontSize="sm" color="gray.500" noOfLines={2}>{task.description}</Text>
                                                        {task.dueDate && (
                                                            <Text fontSize="xs" color="gray.400" mt={2}>Due: {new Date(task.dueDate).toLocaleDateString()}</Text>
                                                        )}
                                                    </Box>
                                                )}
                                            </Draggable>
                                        ))}
                                        {provided.placeholder}
                                    </VStack>
                                )}
                            </Droppable>
                        </Box>
                    ))}
                </HStack>
            </DragDropContext>

            <Modal isOpen={isOpen} onClose={onClose}>
                <ModalOverlay />
                <ModalContent>
                    <ModalHeader>Create New Task</ModalHeader>
                    <ModalCloseButton />
                    <ModalBody pb={6}>
                        <FormControl>
                            <FormLabel>Title</FormLabel>
                            <Input
                                placeholder="Task title"
                                value={newTask.title}
                                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Description</FormLabel>
                            <Textarea
                                placeholder="Task details"
                                value={newTask.description}
                                onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Priority</FormLabel>
                            <Select
                                value={newTask.priority}
                                onChange={(e) => setNewTask({ ...newTask, priority: e.target.value })}
                            >
                                <option value="high">High</option>
                                <option value="medium">Medium</option>
                                <option value="low">Low</option>
                            </Select>
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Due Date</FormLabel>
                            <Input
                                type="date"
                                value={newTask.dueDate}
                                onChange={(e) => setNewTask({ ...newTask, dueDate: e.target.value })}
                            />
                        </FormControl>

                        <FormControl mt={4}>
                            <FormLabel>Status</FormLabel>
                            <Select
                                value={newTask.status}
                                onChange={(e) => setNewTask({ ...newTask, status: e.target.value })}
                            >
                                <option value="todo">To Do</option>
                                <option value="in-progress">In Progress</option>
                                <option value="completed">Completed</option>
                            </Select>
                        </FormControl>
                    </ModalBody>

                    <ModalFooter>
                        <Button colorScheme="teal" mr={3} onClick={handleCreateTask}>
                            Create
                        </Button>
                        <Button onClick={onClose}>Cancel</Button>
                    </ModalFooter>
                </ModalContent>
            </Modal>
        </Box>
    );
};

export default KanbanBoard;
