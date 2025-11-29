import React, { useState, useEffect, useRef } from "react";
import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import {
    Settings,
    Mic,
    MicOff,
    Upload,
    Download,
    Activity,
    Loader2,
} from "lucide-react";

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
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
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
                variant: "destructive",
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
            description: "Audio processing has ended.",
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
                variant: "destructive",
            });
            return;
        }

        onModelUpload?.(file);

        toast({
            title: "Model uploaded",
            description: "Processing wake word model...",
        });
    };

    const handleModelDownload = (model: WakeWordModel) => {
        onModelDownload?.(model);

        toast({
            title: "Model download started",
            description: `Downloading "${model.name}"`,
        });
    };

    const handleSensitivityChange = (value: number) => {
        const newSensitivity = value;
        setSensitivity(newSensitivity);
        if (selectedModel) {
            const updatedModel = { ...selectedModel, sensitivity: newSensitivity };
            setSelectedModel(updatedModel);
            onModelChange?.(updatedModel);
        }
    };

    const getStatusColor = () => {
        if (!isListening) return "bg-gray-500";
        if (audioLevel > 0.7) return "bg-red-500";
        if (audioLevel > 0.4) return "bg-yellow-500";
        return "bg-green-500";
    };

    const getStatusText = () => {
        if (!isListening) return "Inactive";
        if (audioLevel > 0.7) return "Loud";
        if (audioLevel > 0.4) return "Active";
        return "Listening";
    };

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                <p className="mt-4 text-gray-500">Initializing audio...</p>
            </div>
        );
    }

    return (
        <div className={cn("space-y-6", compactView ? "p-2" : "p-6")}>
            {/* Header */}
            {showNavigation && (
                <div className="flex justify-between items-center">
                    <h2 className={cn("font-bold", compactView ? "text-xl" : "text-2xl")}>
                        Wake Word Detector
                    </h2>
                    <div className="flex space-x-2">
                        <Button
                            variant="outline"
                            size={compactView ? "sm" : "default"}
                            onClick={() => setIsSettingsOpen(true)}
                        >
                            <Settings className="w-4 h-4" />
                        </Button>

                        <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Wake Word Settings</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <Label>Sensitivity</Label>
                                        <div className="flex items-center space-x-4">
                                            <Slider
                                                value={sensitivity}
                                                min={0.1}
                                                max={1.0}
                                                step={0.1}
                                                onValueChange={handleSensitivityChange}
                                                className="flex-1"
                                            />
                                            <span className="text-sm text-gray-500 w-12">
                                                {Math.round(sensitivity * 100)}%
                                            </span>
                                        </div>
                                        <p className="text-sm text-gray-500">
                                            Adjust detection sensitivity
                                        </p>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsSettingsOpen(false)}>
                                        Close
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {isListening ? (
                            <Button
                                variant="destructive"
                                size={compactView ? "sm" : "default"}
                                onClick={stopListening}
                                className="gap-2"
                            >
                                <MicOff className="w-4 h-4" />
                                Stop Listening
                            </Button>
                        ) : (
                            <Button
                                variant="default"
                                size={compactView ? "sm" : "default"}
                                onClick={startListening}
                                className="gap-2 bg-green-600 hover:bg-green-700"
                            >
                                <Mic className="w-4 h-4" />
                                Start Listening
                            </Button>
                        )}
                    </div>
                </div>
            )}

            {/* Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className={cn(compactView ? "text-lg" : "text-xl")}>
                        Detection Status
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className={cn("grid gap-4", compactView ? "grid-cols-1" : "grid-cols-3")}>
                        <div className="flex flex-col items-center space-y-2">
                            <Badge
                                variant={isListening ? "default" : "secondary"}
                                className={cn("px-3 py-1", isListening ? getStatusColor() : "")}
                            >
                                {getStatusText()}
                            </Badge>
                            <span className="text-sm text-gray-500">Status</span>
                        </div>

                        <div className="flex flex-col items-center space-y-2 w-full">
                            <Progress value={audioLevel * 100} className="w-full" />
                            <span className="text-sm text-gray-500">
                                Audio Level: {Math.round(audioLevel * 100)}%
                            </span>
                        </div>

                        <div className="flex flex-col items-center space-y-2">
                            <span className={cn("font-bold", compactView ? "text-xl" : "text-2xl")}>
                                {selectedModel?.wakeWord || "No Model"}
                            </span>
                            <span className="text-sm text-gray-500">Wake Word</span>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Model Selection */}
            <Card>
                <CardHeader>
                    <CardTitle className={cn(compactView ? "text-lg" : "text-xl")}>
                        Wake Word Models
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <Select
                            value={selectedModel?.id || ""}
                            onValueChange={(value) => {
                                const model = models.find((m) => m.id === value);
                                if (model) handleModelChange(model);
                            }}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select a model" />
                            </SelectTrigger>
                            <SelectContent>
                                {models.map((model) => (
                                    <SelectItem key={model.id} value={model.id}>
                                        {model.name} - {model.wakeWord} ({model.version})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {selectedModel && (
                            <div className={cn("grid gap-4", compactView ? "grid-cols-1" : "grid-cols-2")}>
                                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                    <p className="text-sm font-medium text-gray-500">Accuracy</p>
                                    <p className="text-2xl font-bold">{selectedModel.performance.accuracy}%</p>
                                    <p className="text-xs text-gray-500">Detection accuracy</p>
                                </div>
                                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                    <p className="text-sm font-medium text-gray-500">False Positives</p>
                                    <p className="text-2xl font-bold">{selectedModel.performance.falsePositives}</p>
                                    <p className="text-xs text-gray-500">Per 1000 hours</p>
                                </div>
                            </div>
                        )}

                        <div className="flex space-x-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => document.getElementById("model-upload")?.click()}
                                className="gap-2"
                            >
                                <Upload className="w-4 h-4" />
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
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleModelDownload(selectedModel)}
                                    className="gap-2"
                                >
                                    <Download className="w-4 h-4" />
                                    Download Model
                                </Button>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Recent Detections */}
            <Card>
                <CardHeader>
                    <CardTitle className={cn(compactView ? "text-lg" : "text-xl")}>
                        Recent Detections ({detections.length})
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-2">
                        {detections.map((detection) => (
                            <Card key={detection.id} className="p-4">
                                <div className="flex justify-between items-center">
                                    <div>
                                        <p className="font-medium">
                                            {detection.timestamp.toLocaleTimeString()}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            Duration: {Math.round(detection.duration)}ms
                                        </p>
                                    </div>
                                    <Badge
                                        variant={
                                            detection.confidence > 0.8
                                                ? "default"
                                                : detection.confidence > 0.6
                                                    ? "secondary"
                                                    : "outline"
                                        }
                                        className={
                                            detection.confidence > 0.8 ? "bg-green-500 hover:bg-green-600" :
                                                detection.confidence > 0.6 ? "bg-yellow-500 hover:bg-yellow-600" : ""
                                        }
                                    >
                                        {Math.round(detection.confidence * 100)}% confidence
                                    </Badge>
                                </div>
                            </Card>
                        ))}
                        {detections.length === 0 && (
                            <p className="text-center text-gray-500 py-4">
                                No detections yet. Start listening to detect wake words.
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default WakeWordDetector;
