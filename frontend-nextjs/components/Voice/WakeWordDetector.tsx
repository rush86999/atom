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
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Code,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  DownloadIcon,
  TriangleDownIcon,
  TriangleUpIcon,
  AttachmentIcon,
} from "@chakra-ui/icons";

interface WakeWordDetection {
  id: string;
  timestamp: Date;
  confidence: number;
  audioData?: ArrayBuffer;
  duration: number;
}

interface WakeWordModel {
  id: string;
  name: string;
  description: string;
  version: string;
  wakeWord: string;
  sensitivity: number;
  isActive: boolean;
  performance: {
    accuracy: number;
    falsePositives: number;
    detections: number;
  };
  fileSize: number;
  lastUpdated: Date;
}

interface WakeWordDetectorProps {
  onDetection?: (detection: WakeWordDetection) => void;
  onModelChange?: (model: WakeWordModel) => void;
  onModelUpload?: (modelFile: File) => void;
  onModelDownload?: (model: WakeWordModel) => void;
  initialModels?: WakeWordModel[];
  showNavigation?: boolean;
  compactView?: boolean;
}

const WakeWordDetector: React.FC<WakeWordDetectorProps> = ({
  onDetection,
  onModelChange,
  onModelUpload,
  onModelDownload,
  initialModels = [],
  showNavigation = true,
  compactView = false,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [detections, setDetections] = useState<WakeWordDetection[]>([]);
  const [models, setModels] = useState<WakeWordModel[]>(initialModels);
  const [selectedModel, setSelectedModel] = useState<WakeWordModel | null>(
    null,
  );
  const [sensitivity, setSensitivity] = useState(0.7);
  const [audioLevel, setAudioLevel] = useState(0);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [audioContext, setAudioContext] = useState<AudioContext | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const animationRef = useRef<number>();
  const {
    isOpen: isSettingsOpen,
    onOpen: onSettingsOpen,
    onClose: onSettingsClose,
  } = useDisclosure();
  const toast = useToast();

  // Default models if none provided
  const defaultModels: WakeWordModel[] = [
    {
      id: "default_wakeword",
      name: "Default Wake Word",
      description: "Standard wake word detection model",
      version: "1.0.0",
      wakeWord: "Hey Atom",
      sensitivity: 0.7,
      isActive: true,
      performance: {
        accuracy: 92,
        falsePositives: 2,
        detections: 0,
      },
      fileSize: 2.4,
      lastUpdated: new Date(),
    },
    {
      id: "custom_wakeword",
      name: "Custom Wake Word",
      description: "Train your own wake word",
      version: "1.0.0",
      wakeWord: "Custom",
      sensitivity: 0.8,
      isActive: false,
      performance: {
        accuracy: 0,
        falsePositives: 0,
        detections: 0,
      },
      fileSize: 0,
      lastUpdated: new Date(),
    },
  ];

  useEffect(() => {
    if (initialModels.length === 0) {
      setModels(defaultModels);
      setSelectedModel(defaultModels[0]);
    } else {
      setModels(initialModels);
      const activeModel = initialModels.find((model) => model.isActive);
      setSelectedModel(activeModel || initialModels[0]);
    }
  }, [initialModels]);

  useEffect(() => {
    if (selectedModel) {
      setSensitivity(selectedModel.sensitivity);
    }
  }, [selectedModel]);

  const initializeAudio = async (): Promise<boolean> => {
    try {
      setIsLoading(true);

      // Request microphone permission
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Create audio context
      const ctx = new (window.AudioContext ||
        (window as any).webkitAudioContext)();
      const source = ctx.createMediaStreamSource(mediaStream);
      const analyserNode = ctx.createAnalyser();

      analyserNode.fftSize = 256;
      source.connect(analyserNode);

      setStream(mediaStream);
      setAudioContext(ctx);
      setAnalyser(analyserNode);

      // Start audio level visualization
      startAudioVisualization(analyserNode);

      setIsLoading(false);
      return true;
    } catch (error) {
      console.error("Error initializing audio:", error);
      toast({
        title: "Microphone access denied",
        description:
          "Please allow microphone access to use wake word detection.",
        status: "error",
        duration: 5000,
        isClosable: true,
      });
      setIsLoading(false);
      return false;
    }
  };

  const startAudioVisualization = (analyserNode: AnalyserNode) => {
    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);

    const updateAudioLevel = () => {
      analyserNode.getByteFrequencyData(dataArray);
      const average =
        dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
      setAudioLevel(average / 255);
      animationRef.current = requestAnimationFrame(updateAudioLevel);
    };

    animationRef.current = requestAnimationFrame(updateAudioLevel);
  };

  const startListening = async () => {
    if (isListening) return;

    const success = await initializeAudio();
    if (!success) return;

    setIsListening(true);

    // Simulate wake word detection (in a real implementation, this would use a proper wake word detection library)
    simulateWakeWordDetection();

    toast({
      title: "Wake word detection started",
      description: `Listening for "${selectedModel?.wakeWord}"`,
      status: "success",
      duration: 3000,
      isClosable: true,
    });
  };

  const stopListening = () => {
    if (!isListening) return;

    // Clean up audio resources
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }

    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }

    if (audioContext) {
      audioContext.close();
    }

    setStream(null);
    setAudioContext(null);
    setAnalyser(null);
    setAudioLevel(0);
    setIsListening(false);

    toast({
      title: "Wake word detection stopped",
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  };

  const simulateWakeWordDetection = () => {
    // In a real implementation, this would be replaced with actual wake word detection
    // For demonstration, we'll simulate random detections
    const detectionInterval = setInterval(() => {
      if (!isListening) {
        clearInterval(detectionInterval);
        return;
      }

      // Random chance of detection based on audio level and sensitivity
      const detectionProbability = audioLevel * sensitivity * 0.1;
      if (Math.random() < detectionProbability) {
        const detection: WakeWordDetection = {
          id: Date.now().toString(),
          timestamp: new Date(),
          confidence: Math.random() * 0.5 + 0.5, // 0.5 to 1.0
          duration: Math.random() * 1000 + 500, // 0.5 to 1.5 seconds
        };

        setDetections((prev) => [detection, ...prev.slice(0, 9)]); // Keep last 10 detections
        onDetection?.(detection);

        toast({
          title: "Wake word detected!",
          description: `"${selectedModel?.wakeWord}" detected with ${Math.round(detection.confidence * 100)}% confidence`,
          status: "success",
          duration: 2000,
          isClosable: true,
        });
      }
    }, 1000);

    return () => clearInterval(detectionInterval);
  };

  const handleModelChange = (model: WakeWordModel) => {
    setSelectedModel(model);
    onModelChange?.(model);

    toast({
      title: "Model changed",
      description: `Now using "${model.name}"`,
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleModelUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith(".model") && !file.name.endsWith(".bin")) {
      toast({
        title: "Invalid file type",
        description: "Please upload a valid model file (.model or .bin)",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    onModelUpload?.(file);

    toast({
      title: "Model uploaded",
      description: "Processing wake word model...",
      status: "info",
      duration: 3000,
      isClosable: true,
    });
  };

  const handleModelDownload = (model: WakeWordModel) => {
    onModelDownload?.(model);

    toast({
      title: "Model download started",
      description: `Downloading "${model.name}"`,
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleSensitivityChange = (value: number) => {
    setSensitivity(value);
    if (selectedModel) {
      const updatedModel = { ...selectedModel, sensitivity: value };
      setSelectedModel(updatedModel);
      onModelChange?.(updatedModel);
    }
  };

  const getStatusColor = () => {
    if (!isListening) return "gray";
    if (audioLevel > 0.7) return "red";
    if (audioLevel > 0.4) return "yellow";
    return "green";
  };

  const getStatusText = () => {
    if (!isListening) return "Inactive";
    if (audioLevel > 0.7) return "Loud";
    if (audioLevel > 0.4) return "Active";
    return "Listening";
  };

  if (isLoading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Initializing audio...</Text>
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
              Wake Word Detector
            </Heading>
            <HStack spacing={2}>
              <IconButton
                aria-label="Settings"
                icon={<SettingsIcon />}
                size={compactView ? "sm" : "md"}
                onClick={onSettingsOpen}
              />
              {isListening ? (
                <Button
                  leftIcon={<StopIcon />}
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
                >
                  Start Listening
                </Button>
              )}
            </HStack>
          </Flex>
        )}

        {/* Status Card */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Detection Status</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={compactView ? 1 : 3} spacing={4}>
              <VStack spacing={2} align="center">
                <Badge
                  colorScheme={getStatusColor()}
                  fontSize={compactView ? "sm" : "md"}
                  px={3}
                  py={1}
                >
                  {getStatusText()}
                </Badge>
                <Text fontSize="sm" color="gray.600">
                  Status
                </Text>
              </VStack>

              <VStack spacing={2} align="center">
                <Progress
                  value={audioLevel * 100}
                  size="lg"
                  width="100%"
                  colorScheme={getStatusColor()}
                />
                <Text fontSize="sm" color="gray.600">
                  Audio Level: {Math.round(audioLevel * 100)}%
                </Text>
              </VStack>

              <VStack spacing={2} align="center">
                <Text fontSize={compactView ? "lg" : "xl"} fontWeight="bold">
                  {selectedModel?.wakeWord || "No Model"}
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Wake Word
                </Text>
              </VStack>
            </SimpleGrid>
          </CardBody>
        </Card>

        {/* Model Selection */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>Wake Word Models</Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <Select
                value={selectedModel?.id || ""}
                onChange={(e) => {
                  const model = models.find((m) => m.id === e.target.value);
                  if (model) handleModelChange(model);
                }}
              >
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} - {model.wakeWord} ({model.version})
                  </option>
                ))}
              </Select>

              {selectedModel && (
                <SimpleGrid columns={compactView ? 1 : 2} spacing={4}>
                  <Stat>
                    <StatLabel>Accuracy</StatLabel>
                    <StatNumber>
                      {selectedModel.performance.accuracy}%
                    </StatNumber>
                    <StatHelpText>Detection accuracy</StatHelpText>
                  </Stat>
                  <Stat>
                    <StatLabel>False Positives</StatLabel>
                    <StatNumber>
                      {selectedModel.performance.falsePositives}
                    </StatNumber>
                    <StatHelpText>Per 1000 hours</StatHelpText>
                  </Stat>
                </SimpleGrid>
              )}

              <HStack spacing={2}>
                <Button
                  icon={<AttachmentIcon />}
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    document.getElementById("model-upload")?.click()
                  }
                >
                  Upload Model
                </Button>
                <input
                  id="model-upload"
                  type="file"
                  accept=".model,.bin"
                  style={{ display: "none" }}
                  onChange={handleModelUpload}
                />
                {selectedModel && selectedModel.fileSize > 0 && (
                  <Button
                    leftIcon={<DownloadIcon />}
                    variant="outline"
                    size="sm"
                    onClick={() => handleModelDownload(selectedModel)}
                  >
                    Download Model
                  </Button>
                )}
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Recent Detections */}
        <Card>
          <CardHeader>
            <Heading size={compactView ? "sm" : "md"}>
              Recent Detections ({detections.length})
            </Heading>
          </CardHeader>
          <CardBody>
            <VStack spacing={2} align="stretch">
              {detections.map((detection) => (
                <Card key={detection.id} size="sm">
                  <CardBody>
                    <Flex justify="space-between" align="center">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="medium">
                          {detection.timestamp.toLocaleTimeString()}
                        </Text>
                        <Text fontSize="sm" color="gray.600">
                          Duration: {detection.duration}ms
                        </Text>
                      </VStack>
                      <Badge
                        colorScheme={
                          detection.confidence > 0.8
                            ? "green"
                            : detection.confidence > 0.6
                              ? "yellow"
                              : "orange"
                        }
                      >
                        {Math.round(detection.confidence * 100)}% confidence
                      </Badge>
                    </Flex>
                  </CardBody>
                </Card>
              ))}
              {detections.length === 0 && (
                <Text textAlign="center" color="gray.500" py={4}>
                  No detections yet. Start listening to detect wake words.
                </Text>
              )}
            </VStack>
          </CardBody>
        </Card>
      </VStack>

      {/* Settings Modal */}
      <Modal isOpen={isSettingsOpen} onClose={onSettingsClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Wake Word Settings</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Sensitivity</FormLabel>
                <Slider
                  value={sensitivity}
                  min={0.1}
                  max={1.0}
                  step={0.1}
                  onChange={handleSensitivityChange}
                >
                  <SliderTrack>
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb />
                </Slider>
                <Text fontSize="sm" color="gray.600">
                  Sensitivity: {Math.round(sensitivity * 100)}%
                </Text>
              </FormControl>

              <HStack spacing={3} width="100%" justifyContent="flex-end">
                <Button variant="outline" onClick={onSettingsClose}>
                  Close
                </Button>
              </HStack>
            </VStack>
          </ModalBody>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default WakeWordDetector;
