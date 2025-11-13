import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Badge,
  Button,
  IconButton,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Alert,
  AlertIcon,
  SimpleGrid,
  Flex,
  Spinner,
  useToast,
  Progress,
  Code,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  List,
  ListItem,
  ListIcon,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  InfoIcon,
} from "@chakra-ui/icons";
import { TriangleDownIcon, TriangleUpIcon, CloseIcon, DeleteIcon } from "@chakra-ui/icons";

interface VoiceCommand {
  id: string;
  phrase: string;
  action: string;
  description: string;
  enabled: boolean;
  confidenceThreshold: number;
  parameters?: Record<string, any>;
  lastUsed?: Date;
  usageCount: number;
}

interface VoiceRecognitionResult {
  id: string;
  timestamp: Date;
  transcript: string;
  confidence: number;
  command?: VoiceCommand;
  processed: boolean;
  error?: string;
}

interface VoiceCommandsProps {
  onCommandRecognized?: (result: VoiceRecognitionResult) => void;
  onCommandExecute?: (
    command: VoiceCommand,
    parameters?: Record<string, any>,
  ) => void;
  onCommandCreate?: (command: VoiceCommand) => void;
  onCommandUpdate?: (commandId: string, updates: Partial<VoiceCommand>) => void;
  onCommandDelete?: (commandId: string) => void;
  initialCommands?: VoiceCommand[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const VoiceCommands: React.FC<VoiceCommandsProps> = ({
  onCommandRecognized,
  onCommandExecute,
  onCommandCreate,
  onCommandUpdate,
  onCommandDelete,
  initialCommands = [],
  showNavigation = true,
  compactView = false,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recognitionResults, setRecognitionResults] = useState<
    VoiceRecognitionResult[]
  >([]);
  const [commands, setCommands] = useState<VoiceCommand[]>(initialCommands);
  const [selectedCommand, setSelectedCommand] = useState<VoiceCommand | null>(
    null,
  );
  const [currentTranscript, setCurrentTranscript] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [recognition, setRecognition] = useState<any>(null);
  const {
    isOpen: isCommandModalOpen,
    onOpen: onCommandModalOpen,
    onClose: onCommandModalClose,
  } = useDisclosure();
  const {
    isOpen: isResultsOpen,
    onOpen: onResultsOpen,
    onClose: onResultsClose,
  } = useDisclosure();
  const toast = useToast();

  // Default commands
  const defaultCommands: VoiceCommand[] = [
    {
      id: "open_calendar",
      phrase: "open calendar",
      action: "navigate",
      description: "Open the calendar view",
      enabled: true,
      confidenceThreshold: 0.7,
      parameters: { route: "/calendar" },
      usageCount: 0,
    },
    {
      id: "create_task",
      phrase: "create task",
      action: "create_task",
      description: "Create a new task",
      enabled: true,
      confidenceThreshold: 0.8,
      usageCount: 0,
    },
    {
      id: "check_weather",
      phrase: "what's the weather",
      action: "get_weather",
      description: "Get current weather information",
      enabled: true,
      confidenceThreshold: 0.6,
      usageCount: 0,
    },
    {
      id: "send_email",
      phrase: "send email",
      action: "send_email",
      description: "Compose and send an email",
      enabled: false,
      confidenceThreshold: 0.8,
      usageCount: 0,
    },
  ];

  useEffect(() => {
    if (initialCommands.length === 0) {
      setCommands(defaultCommands);
    } else {
      setCommands(initialCommands);
    }

    // Initialize speech recognition
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognitionInstance = new SpeechRecognition();
        recognitionInstance.continuous = true;
        recognitionInstance.interimResults = true;
        recognitionInstance.lang = "en-US";

        recognitionInstance.onstart = () => {
          setIsListening(true);
          toast({
            title: "Voice recognition started",
            status: "info",
            duration: 2000,
            isClosable: true,
          });
        };

        recognitionInstance.onend = () => {
          setIsListening(false);
        };

        recognitionInstance.onresult = (event: any) => {
          let finalTranscript = "";
          let interimTranscript = "";
          let currentConfidence = 0;

          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            const confidence = event.results[i][0].confidence;

            if (event.results[i].isFinal) {
              finalTranscript += transcript;
              currentConfidence = confidence;
            } else {
              interimTranscript += transcript;
            }
          }

          if (finalTranscript) {
            processVoiceCommand(finalTranscript, currentConfidence);
          } else if (interimTranscript) {
            setCurrentTranscript(interimTranscript);
            setConfidence(currentConfidence);
          }
        };

        recognitionInstance.onerror = (event: any) => {
          console.error("Speech recognition error:", event.error);
          toast({
            title: "Speech recognition error",
            description: event.error,
            status: "error",
            duration: 3000,
            isClosable: true,
          });
          setIsListening(false);
        };

        setRecognition(recognitionInstance);
      } else {
        toast({
          title: "Speech recognition not supported",
          description: "Your browser does not support speech recognition.",
          status: "warning",
          duration: 5000,
          isClosable: true,
        });
      }
    }

    return () => {
      if (recognition) {
        recognition.stop();
      }
    };
  }, []);

  const processVoiceCommand = (transcript: string, confidence: number) => {
    setIsProcessing(true);
    setCurrentTranscript(transcript);
    setConfidence(confidence);

    // Find matching command
    const matchedCommand = commands.find(
      (command) =>
        command.enabled &&
        transcript.toLowerCase().includes(command.phrase.toLowerCase()) &&
        confidence >= command.confidenceThreshold,
    );

    const result: VoiceRecognitionResult = {
      id: Date.now().toString(),
      timestamp: new Date(),
      transcript,
      confidence,
      command: matchedCommand,
      processed: !!matchedCommand,
    };

    setRecognitionResults((prev) => [result, ...prev.slice(0, 9)]); // Keep last 10 results
    onCommandRecognized?.(result);

    if (matchedCommand) {
      // Update command usage
      const updatedCommand = {
        ...matchedCommand,
        lastUsed: new Date(),
        usageCount: matchedCommand.usageCount + 1,
      };
      handleUpdateCommand(matchedCommand.id, updatedCommand);

      // Execute command
      onCommandExecute?.(matchedCommand, matchedCommand.parameters);

      toast({
        title: "Command executed",
        description: `"${matchedCommand.phrase}" - ${matchedCommand.description}`,
        status: "success",
        duration: 3000,
        isClosable: true,
      });
    } else {
      toast({
        title: "No matching command found",
        description: `"${transcript}" (${Math.round(confidence * 100)}% confidence)`,
        status: "warning",
        duration: 3000,
        isClosable: true,
      });
    }

    setIsProcessing(false);
    setCurrentTranscript("");
  };

  const startListening = () => {
    if (recognition && !isListening) {
      try {
        recognition.start();
      } catch (error) {
        console.error("Error starting speech recognition:", error);
        toast({
          title: "Error starting voice recognition",
          status: "error",
          duration: 3000,
          isClosable: true,
        });
      }
    }
  };

  const stopListening = () => {
    if (recognition && isListening) {
      recognition.stop();
    }
  };

  const handleCreateCommand = (
    commandData: Omit<VoiceCommand, "id" | "usageCount">,
  ) => {
    const newCommand: VoiceCommand = {
      ...commandData,
      id: Date.now().toString(),
      usageCount: 0,
    };
    setCommands((prev) => [...prev, newCommand]);
    onCommandCreate?.(newCommand);
    toast({
      title: "Command created",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleUpdateCommand = (
    commandId: string,
    updates: Partial<VoiceCommand>,
  ) => {
    setCommands((prev) =>
      prev.map((command) =>
        command.id === commandId ? { ...command, ...updates } : command,
      ),
    );
    onCommandUpdate?.(commandId, updates);
  };

  const handleDeleteCommand = (commandId: string) => {
    setCommands((prev) => prev.filter((command) => command.id !== commandId));
    onCommandDelete?.(commandId);
    toast({
      title: "Command deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const toggleCommandEnabled = (commandId: string) => {
    const command = commands.find((c) => c.id === commandId);
    if (command) {
      handleUpdateCommand(commandId, { enabled: !command.enabled });
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return "green";
    if (confidence >= 0.6) return "yellow";
    return "red";
  };

  const CommandForm: React.FC<{
    command?: VoiceCommand;
    onSubmit: (data: Omit<VoiceCommand, "id" | "usageCount">) => void;
    onCancel: () => void;
  }> = ({ command, onSubmit, onCancel }) => {
    const [formData, setFormData] = useState({
      phrase: command?.phrase || "",
      action: command?.action || "",
      description: command?.description || "",
      enabled: command?.enabled ?? true,
      confidenceThreshold: command?.confidenceThreshold || 0.7,
      parameters: command?.parameters
        ? JSON.stringify(command.parameters, null, 2)
        : "",
    });

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      try {
        const parameters = formData.parameters
          ? JSON.parse(formData.parameters)
          : undefined;

        onSubmit({
          phrase: formData.phrase,
          action: formData.action,
          description: formData.description,
          enabled: formData.enabled,
          confidenceThreshold: formData.confidenceThreshold,
          parameters,
        });
      } catch (error) {
        toast({
          title: "Invalid parameters",
          description: "Please check the parameters JSON format",
          status: "error",
          duration: 3000,
          isClosable: true,
        });
      }
    };

    return (
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired>
            <FormLabel>Voice Phrase</FormLabel>
            <Input
              value={formData.phrase}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, phrase: e.target.value }))
              }
              placeholder="e.g., open calendar"
            />
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Action</FormLabel>
            <Select
              value={formData.action}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, action: e.target.value }))
              }
            >
              <option value="navigate">Navigate</option>
              <option value="create_task">Create Task</option>
              <option value="send_email">Send Email</option>
              <option value="get_weather">Get Weather</option>
              <option value="play_music">Play Music</option>
              <option value="search">Search</option>
              <option value="custom">Custom Action</option>
            </Select>
          </FormControl>

          <FormControl isRequired>
            <FormLabel>Description</FormLabel>
            <Input
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  description: e.target.value,
                }))
              }
              placeholder="Describe what this command does"
            />
          </FormControl>

          <SimpleGrid columns={2} spacing={4}>
            <FormControl>
              <FormLabel>Confidence Threshold</FormLabel>
              <Input
                type="number"
                step="0.1"
                min="0.1"
                max="1.0"
                value={formData.confidenceThreshold}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    confidenceThreshold: parseFloat(e.target.value),
                  }))
                }
              />
            </FormControl>

            <FormControl display="flex" alignItems="center">
              <FormLabel mb="0" flex="1">
                Enabled
              </FormLabel>
              <Switch
                isChecked={formData.enabled}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    enabled: e.target.checked,
                  }))
                }
              />
            </FormControl>
          </SimpleGrid>

          <FormControl>
            <FormLabel>Parameters (JSON)</FormLabel>
            <Textarea
              value={formData.parameters}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, parameters: e.target.value }))
              }
              placeholder='{"key": "value"}'
              rows={4}
              fontFamily="mono"
            />
          </FormControl>

          <HStack width="100%" justifyContent="flex-end" spacing={3}>
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" colorScheme="blue">
              {command ? "Update Command" : "Create Command"}
            </Button>
          </HStack>
        </VStack>
      </form>
    );
  };

  return (
    <Box p={compactView ? 2 : 6}>
      <VStack spacing={compactView ? 3 : 6} align="stretch">
        {/* Header */}
        {showNavigation && (
          <Flex justify="space-between" align="center">
            <Heading size={compactView ? "md" : "lg"}>Voice Commands</Heading>
            <HStack spacing={2}>
              <Button
                variant="outline"
                size={compactView ? "sm" : "md"}
                onClick={onResultsOpen}
              >
                View Results ({recognitionResults.length})
              </Button>
              {isListening ? (
                <Button
                  leftIcon={<CloseIcon />}
                  colorScheme="red"
                  size={compactView ? "sm" : "md"}
                  onClick={stopListening}
                >
                  Stop Listening
                </Button>
              ) : (
                <Button
                  leftIcon={<TriangleUpIcon />}
                  colorScheme="green"
                  size={compactView ? "sm" : "md"}
                  onClick={startListening}
                  isLoading={isProcessing}
                >
                  Start Listening
                </Button>
              )}
              <Button
                leftIcon={<SettingsIcon />}
                colorScheme="blue"
                size={compactView ? "sm" : "md"}
                onClick={() => {
                  setSelectedCommand(null);
                  onCommandModalOpen();
                }}
              >
                Manage Commands
              </Button>
            </HStack>
          </Flex>
        )}

        {/* Status Card */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>
              Voice Recognition Status
            </Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={compactView ? 1 : 3} spacing={4}>
              <VStack spacing={2} align="center">
                <Badge
                  colorScheme={isListening ? "green" : "gray"}
                  fontSize={compactView ? "sm" : "md"}
                  px={3}
                  py={1}
                >
                  {isListening ? "Listening" : "Inactive"}
                </Badge>
                <Text fontSize="sm" color="gray.600">
                  Status
                </Text>
              </VStack>

              <VStack spacing={2} align="center">
                <Progress
                  value={confidence * 100}
                  size="lg"
                  width="100%"
                  colorScheme={getConfidenceColor(confidence)}
                />
                <Text fontSize="sm" color="gray.600">
                  Confidence: {Math.round(confidence * 100)}%
                </Text>
              </VStack>

              <VStack spacing={2} align="center">
                <Text fontSize={compactView ? "lg" : "xl"} fontWeight="bold">
                  {commands.filter((c) => c.enabled).length}
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Active Commands
                </Text>
              </VStack>
            </SimpleGrid>

            {currentTranscript && (
              <Alert status="info" mt={4}>
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontWeight="medium">Current Input:</Text>
                  <Text>{currentTranscript}</Text>
                </VStack>
              </Alert>
            )}
          </CardBody>
        </Card>

        {/* Available Commands */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>
              Available Commands ({commands.filter((c) => c.enabled).length})
            </Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={compactView ? 1 : 2} spacing={4}>
              {commands
                .filter((command) => command.enabled)
                .map((command) => (
                  <Card key={command.id} size="sm">
                    <CardBody>
                      <Flex justify="space-between" align="center">
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="medium">&quot;{command.phrase}&quot;</Text>
                          <Text fontSize="sm" color="gray.600">
                            {command.description}
                          </Text>
                          <HStack spacing={2}>
                            <Badge
                              colorScheme={command.enabled ? "green" : "gray"}
                              size="sm"
                            >
                              {command.enabled ? "Enabled" : "Disabled"}
                            </Badge>
                            <Text fontSize="xs" color="gray.500">
                              {command.usageCount} uses
                            </Text>
                          </HStack>
                        </VStack>
                        <HStack spacing={1}>
                          <IconButton
                            aria-label="Toggle command"
                            icon={
                              command.enabled ? (
                                <CheckCircleIcon />
                              ) : (
                                <WarningTwoIcon />
                              )
                            }
                            size="sm"
                            variant="ghost"
                            colorScheme={command.enabled ? "green" : "yellow"}
                            onClick={() => toggleCommandEnabled(command.id)}
                          />
                          <IconButton
                            aria-label="Edit command"
                            icon={<SettingsIcon />}
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setSelectedCommand(command);
                              onCommandModalOpen();
                            }}
                          />
                          <IconButton
                            aria-label="Delete command"
                            icon={<DeleteIcon />}
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                            onClick={() => handleDeleteCommand(command.id)}
                          />
                        </HStack>
                      </Flex>
                    </CardBody>
                  </Card>
                ))}
            </SimpleGrid>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default VoiceCommands;
