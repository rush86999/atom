import React, { useState, useEffect, useRef } from "react";
import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import {
    Mic,
    MicOff,
    Settings,
    Trash2,
    CheckCircle2,
    AlertTriangle,
    Info,
    X,
    ChevronDown,
    ChevronUp,
    Activity,
    Command,
} from "lucide-react";

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
    const [isCommandModalOpen, setIsCommandModalOpen] = useState(false);
    const [isResultsOpen, setIsResultsOpen] = useState(false);
    const { toast } = useToast();

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
                        description: "Listening for commands...",
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
                        variant: "error",
                    });
                    setIsListening(false);
                };

                setRecognition(recognitionInstance);
            } else {
                toast({
                    title: "Speech recognition not supported",
                    description: "Your browser does not support speech recognition.",
                    variant: "error",
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
            });
        } else {
            toast({
                title: "No matching command found",
                description: `"${transcript}" (${Math.round(confidence * 100)}% confidence)`,
                variant: "error", // Using destructive for warning-like visual
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
                    variant: "error",
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
            description: "New voice command has been added.",
        });
        setIsCommandModalOpen(false);
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
        if (isCommandModalOpen) {
            toast({
                title: "Command updated",
                description: "Voice command has been updated.",
            });
            setIsCommandModalOpen(false);
        }
    };

    const handleDeleteCommand = (commandId: string) => {
        setCommands((prev) => prev.filter((command) => command.id !== commandId));
        onCommandDelete?.(commandId);
        toast({
            title: "Command deleted",
            description: "Voice command has been removed.",
        });
    };

    const toggleCommandEnabled = (commandId: string) => {
        const command = commands.find((c) => c.id === commandId);
        if (command) {
            handleUpdateCommand(commandId, { enabled: !command.enabled });
        }
    };

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.8) return "bg-green-500";
        if (confidence >= 0.6) return "bg-yellow-500";
        return "bg-red-500";
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
                    variant: "error",
                });
            }
        };

        return (
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="phrase">Voice Phrase</Label>
                    <Input
                        id="phrase"
                        value={formData.phrase}
                        onChange={(e) =>
                            setFormData((prev) => ({ ...prev, phrase: e.target.value }))
                        }
                        placeholder="e.g., open calendar"
                        required
                    />
                </div>

                <div className="space-y-2">
                    <Label htmlFor="action">Action</Label>
                    <Select
                        value={formData.action}
                        onValueChange={(value) =>
                            setFormData((prev) => ({ ...prev, action: value }))
                        }
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Select action" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="navigate">Navigate</SelectItem>
                            <SelectItem value="create_task">Create Task</SelectItem>
                            <SelectItem value="send_email">Send Email</SelectItem>
                            <SelectItem value="get_weather">Get Weather</SelectItem>
                            <SelectItem value="play_music">Play Music</SelectItem>
                            <SelectItem value="search">Search</SelectItem>
                            <SelectItem value="custom">Custom Action</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Input
                        id="description"
                        value={formData.description}
                        onChange={(e) =>
                            setFormData((prev) => ({
                                ...prev,
                                description: e.target.value,
                            }))
                        }
                        placeholder="Describe what this command does"
                        required
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label htmlFor="confidence">Confidence Threshold</Label>
                        <Input
                            id="confidence"
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
                    </div>

                    <div className="flex items-center space-x-2 pt-8">
                        <Switch
                            id="enabled"
                            checked={formData.enabled}
                            onCheckedChange={(checked) =>
                                setFormData((prev) => ({
                                    ...prev,
                                    enabled: checked,
                                }))
                            }
                        />
                        <Label htmlFor="enabled">Enabled</Label>
                    </div>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="parameters">Parameters (JSON)</Label>
                    <Textarea
                        id="parameters"
                        value={formData.parameters}
                        onChange={(e) =>
                            setFormData((prev) => ({ ...prev, parameters: e.target.value }))
                        }
                        placeholder='{"key": "value"}'
                        rows={4}
                        className="font-mono"
                    />
                </div>

                <DialogFooter>
                    <Button variant="outline" type="button" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button type="submit">
                        {command ? "Update Command" : "Create Command"}
                    </Button>
                </DialogFooter>
            </form>
        );
    };

    return (
        <div className={cn("space-y-6", compactView ? "p-2" : "p-6")}>
            {/* Header */}
            {showNavigation && (
                <div className="flex justify-between items-center">
                    <h2 className={cn("font-bold", compactView ? "text-xl" : "text-2xl")}>
                        Voice Commands
                    </h2>
                    <div className="flex space-x-2">
                        <Button
                            variant="outline"
                            size={compactView ? "sm" : "default"}
                            onClick={() => setIsResultsOpen(true)}
                        >
                            View Results ({recognitionResults.length})
                        </Button>

                        <Dialog open={isResultsOpen} onOpenChange={setIsResultsOpen}>
                            <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                                <DialogHeader>
                                    <DialogTitle>Recognition Results</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-2">
                                    {recognitionResults.map((result) => (
                                        <Card key={result.id} className="p-4">
                                            <div className="flex justify-between items-start">
                                                <div>
                                                    <p className="font-medium">"{result.transcript}"</p>
                                                    <p className="text-sm text-gray-500">{result.timestamp.toLocaleTimeString()}</p>
                                                </div>
                                                <Badge variant={result.processed ? "default" : "secondary"}>
                                                    {Math.round(result.confidence * 100)}%
                                                </Badge>
                                            </div>
                                        </Card>
                                    ))}
                                    {recognitionResults.length === 0 && (
                                        <p className="text-center text-gray-500">No results yet.</p>
                                    )}
                                </div>
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
                                disabled={isProcessing}
                                className="gap-2 bg-green-600 hover:bg-green-700"
                            >
                                <Mic className="w-4 h-4" />
                                Start Listening
                            </Button>
                        )}

                        <Button
                            variant="outline"
                            size={compactView ? "sm" : "default"}
                            onClick={() => {
                                setSelectedCommand(null);
                                setIsCommandModalOpen(true);
                            }}
                            className="gap-2"
                        >
                            <Settings className="w-4 h-4" />
                            Manage Commands
                        </Button>

                        <Dialog open={isCommandModalOpen} onOpenChange={setIsCommandModalOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>
                                        {selectedCommand ? "Edit Command" : "Create Command"}
                                    </DialogTitle>
                                </DialogHeader>
                                <CommandForm
                                    command={selectedCommand || undefined}
                                    onSubmit={(data) => {
                                        if (selectedCommand) {
                                            handleUpdateCommand(selectedCommand.id, data);
                                        } else {
                                            handleCreateCommand(data);
                                        }
                                    }}
                                    onCancel={() => setIsCommandModalOpen(false)}
                                />
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
            )}

            {/* Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className={cn(compactView ? "text-lg" : "text-xl")}>
                        Voice Recognition Status
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className={cn("grid gap-4", compactView ? "grid-cols-1" : "grid-cols-3")}>
                        <div className="flex flex-col items-center space-y-2">
                            <Badge
                                variant={isListening ? "default" : "secondary"}
                                className={cn("px-3 py-1", isListening ? "bg-green-500 hover:bg-green-600" : "")}
                            >
                                {isListening ? "Listening" : "Inactive"}
                            </Badge>
                            <span className="text-sm text-gray-500">Status</span>
                        </div>

                        <div className="flex flex-col items-center space-y-2 w-full">
                            <Progress value={confidence * 100} className="w-full" />
                            <span className="text-sm text-gray-500">
                                Confidence: {Math.round(confidence * 100)}%
                            </span>
                        </div>

                        <div className="flex flex-col items-center space-y-2">
                            <span className={cn("font-bold", compactView ? "text-xl" : "text-2xl")}>
                                {commands.filter((c) => c.enabled).length}
                            </span>
                            <span className="text-sm text-gray-500">Active Commands</span>
                        </div>
                    </div>

                    {currentTranscript && (
                        <Alert className="mt-4 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
                            <Info className="h-4 w-4" />
                            <AlertTitle>Current Input</AlertTitle>
                            <AlertDescription>{currentTranscript}</AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {/* Available Commands */}
            <Card>
                <CardHeader>
                    <CardTitle className={cn(compactView ? "text-lg" : "text-xl")}>
                        Available Commands ({commands.filter((c) => c.enabled).length})
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className={cn("grid gap-4", compactView ? "grid-cols-1" : "grid-cols-2")}>
                        {commands
                            .filter((command) => command.enabled)
                            .map((command) => (
                                <Card key={command.id} className="p-4">
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1">
                                            <p className="font-medium">"{command.phrase}"</p>
                                            <p className="text-sm text-gray-500">{command.description}</p>
                                            <div className="flex items-center space-x-2">
                                                <Badge variant={command.enabled ? "default" : "secondary"} className={command.enabled ? "bg-green-500 hover:bg-green-600" : ""}>
                                                    {command.enabled ? "Enabled" : "Disabled"}
                                                </Badge>
                                                <span className="text-xs text-gray-500">
                                                    {command.usageCount} uses
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex space-x-1">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => toggleCommandEnabled(command.id)}
                                                className={command.enabled ? "text-green-600" : "text-yellow-600"}
                                            >
                                                {command.enabled ? (
                                                    <CheckCircle2 className="w-4 h-4" />
                                                ) : (
                                                    <AlertTriangle className="w-4 h-4" />
                                                )}
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => {
                                                    setSelectedCommand(command);
                                                    setIsCommandModalOpen(true);
                                                }}
                                            >
                                                <Settings className="w-4 h-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => handleDeleteCommand(command.id)}
                                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </div>
                                </Card>
                            ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default VoiceCommands;
