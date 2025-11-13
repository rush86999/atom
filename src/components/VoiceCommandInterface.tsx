import React, { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Volume2, VolumeX, Settings } from 'lucide-react';
import { useAppStore } from '../store';
import { useToast } from './NotificationSystem';

interface VoiceCommandInterfaceProps {
  isOpen: boolean;
  onClose: () => void;
  onCommand: (command: string, confidence: number) => void;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: ((this: SpeechRecognition, ev: Event) => any) | null;
  onend: ((this: SpeechRecognition, ev: Event) => any) | null;
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => any) | null;
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => any) | null;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
  isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

export const VoiceCommandInterface: React.FC<VoiceCommandInterfaceProps> = ({
  isOpen,
  onClose,
  onCommand,
}) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState(0);
  const [isSupported, setIsSupported] = useState(false);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number>();

  const { voiceCommands, updateVoiceCommand } = useAppStore();
  const toast = useToast();

  // Check if speech recognition is supported
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setIsSupported(!!SpeechRecognition);

    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      const recognition = recognitionRef.current;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
        toast.success('Voice recognition started');
      };

      recognition.onend = () => {
        setIsListening(false);
        setVolume(0);
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            finalTranscript += result[0].transcript;
          } else {
            interimTranscript += result[0].transcript;
          }
        }

        setTranscript(finalTranscript + interimTranscript);

        if (finalTranscript) {
          handleCommand(finalTranscript, event.results[event.results.length - 1][0].confidence);
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        setError(event.error);
        setIsListening(false);
        toast.error('Voice Recognition Error');
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [toast]);

  // Audio visualization
  useEffect(() => {
    if (!isListening) return;

    const initAudioVisualization = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContextRef.current = new AudioContext();
        analyserRef.current = audioContextRef.current.createAnalyser();
        const source = audioContextRef.current.createMediaStreamSource(stream);

        analyserRef.current.fftSize = 256;
        source.connect(analyserRef.current);

        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

        const updateVolume = () => {
          if (!analyserRef.current) return;

          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          setVolume(average / 255);

          animationFrameRef.current = requestAnimationFrame(updateVolume);
        };

        updateVolume();
      } catch (err) {
        console.error('Error initializing audio visualization:', err);
      }
    };

    initAudioVisualization();

    return () => {
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [isListening]);

  const handleCommand = useCallback(async (command: string, confidence: number) => {
    setIsProcessing(true);

    try {
      // Process the voice command
      const processedCommand = command.toLowerCase().trim();

      // Log the voice command
      console.log(`Voice command received: "${processedCommand}" with confidence ${confidence}`);

      // Update command usage statistics
      const existingCommand = voiceCommands.find(cmd =>
        cmd.phrase.toLowerCase().includes(processedCommand) ||
        processedCommand.includes(cmd.phrase.toLowerCase())
      );

      if (existingCommand) {
        updateVoiceCommand(existingCommand.id, {
          usageCount: (existingCommand.usageCount || 0) + 1,
          lastUsed: new Date().toISOString(),
          averageConfidence: existingCommand.averageConfidence
            ? (existingCommand.averageConfidence + confidence) / 2
            : confidence,
        });
      }

      // Call the command handler
      onCommand(processedCommand, confidence);

      // Clear transcript after processing
      setTimeout(() => {
        setTranscript('');
        setIsProcessing(false);
      }, 1000);

    } catch (err) {
      setError('Failed to process command');
      setIsProcessing(false);
      toast.error('Command Processing Failed');
    }
  }, [voiceCommands, updateVoiceCommand, onCommand, toast]);

  const startListening = () => {
    if (!recognitionRef.current || !isSupported) return;

    try {
      recognitionRef.current.start();
    } catch (err) {
      setError('Failed to start voice recognition');
      toast.error('Voice Recognition Failed');
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  };

  const toggleListening = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  if (!isSupported) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
        onClick={onClose}
      >
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md mx-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Voice Commands Not Supported
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Your browser doesn't support voice recognition. Please use a modern browser like Chrome or Edge.
          </p>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
          >
            Close
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Voice Commands
                </h3>
                <button
                  onClick={onClose}
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <Settings className="w-5 h-5" />
                </button>
              </div>

              {/* Voice visualization */}
              <div className="flex justify-center mb-6">
                <div className="relative">
                  <motion.div
                    className={`w-24 h-24 rounded-full border-4 flex items-center justify-center ${
                      isListening
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-300 bg-gray-50 dark:bg-gray-700'
                    }`}
                    animate={isListening ? {
                      scale: [1, 1.1, 1],
                      borderColor: ['rgb(59, 130, 246)', 'rgb(147, 197, 253)', 'rgb(59, 130, 246)']
                    } : {}}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    <motion.div
                      className="w-16 h-16 rounded-full bg-blue-500 flex items-center justify-center"
                      animate={isListening ? {
                        scale: [1, 1 + volume * 0.5, 1]
                      } : {}}
                    >
                      {isListening ? (
                        <Mic className="w-8 h-8 text-white" />
                      ) : (
                        <MicOff className="w-8 h-8 text-gray-400" />
                      )}
                    </motion.div>
                  </motion.div>

                  {/* Volume rings */}
                  {isListening && (
                    <>
                      <motion.div
                        className="absolute inset-0 rounded-full border-2 border-blue-300"
                        animate={{
                          scale: [1, 1.2, 1],
                          opacity: [0.5, 0, 0.5]
                        }}
                        transition={{ duration: 1, repeat: Infinity }}
                      />
                      <motion.div
                        className="absolute inset-0 rounded-full border border-blue-200"
                        animate={{
                          scale: [1, 1.4, 1],
                          opacity: [0.3, 0, 0.3]
                        }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      />
                    </>
                  )}
                </div>
              </div>

              {/* Transcript */}
              <div className="mb-6">
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 min-h-[60px]">
                  {transcript ? (
                    <p className="text-gray-900 dark:text-white">
                      {transcript}
                      {!isProcessing && <span className="animate-pulse">|</span>}
                    </p>
                  ) : (
                    <p className="text-gray-500 dark:text-gray-400 italic">
                      {isListening ? 'Listening...' : 'Click the microphone to start'}
                    </p>
                  )}
                </div>
              </div>

              {/* Error message */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                  <p className="text-red-800 dark:text-red-200 text-sm">{error}</p>
                </div>
              )}

              {/* Controls */}
              <div className="flex justify-center space-x-4">
                <button
                  onClick={toggleListening}
                  disabled={isProcessing}
                  className={`px-6 py-3 rounded-full font-medium transition-colors ${
                    isListening
                      ? 'bg-red-500 hover:bg-red-600 text-white'
                      : 'bg-blue-500 hover:bg-blue-600 text-white'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {isListening ? 'Stop Listening' : 'Start Listening'}
                </button>
              </div>

              {/* Voice command suggestions */}
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Try saying:
                </h4>
                <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  <p>• "Create a new task"</p>
                  <p>• "Show me today's events"</p>
                  <p>• "Check my messages"</p>
                  <p>• "Open dashboard"</p>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// Voice command processor hook
export const useVoiceCommands = () => {
  const { setCurrentView, addTask, setSearchQuery } = useAppStore();
  const toast = useToast();

  const processCommand = useCallback((command: string, confidence: number) => {
    const cmd = command.toLowerCase();

    // Navigation commands
    if (cmd.includes('dashboard') || cmd.includes('home')) {
      setCurrentView('dashboard');
      toast.success('Navigation', 'Switched to Dashboard');
    } else if (cmd.includes('tasks') || cmd.includes('todo')) {
      setCurrentView('tasks');
      toast.success('Navigation', 'Switched to Tasks');
    } else if (cmd.includes('agents')) {
      setCurrentView('agents');
      toast.success('Navigation', 'Switched to Agents');
    } else if (cmd.includes('calendar') || cmd.includes('events')) {
      setCurrentView('calendar');
      toast.success('Navigation', 'Switched to Calendar');
    } else if (cmd.includes('communications') || cmd.includes('messages')) {
      setCurrentView('communications');
      toast.success('Navigation', 'Switched to Communications');
    } else if (cmd.includes('settings')) {
      setCurrentView('settings');
      toast.success('Navigation', 'Switched to Settings');
    }

    // Task commands
    else if (cmd.includes('create task') || cmd.includes('new task')) {
      const title = cmd.replace(/(create|new) task/i, '').trim();
      if (title) {
        addTask({
          id: Date.now().toString(),
          title: title.charAt(0).toUpperCase() + title.slice(1),
          description: '',
          status: 'pending',
          priority: 'medium',
          assignee: '',
          dueDate: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        });
        toast.success('Task Created', `Created task: ${title}`);
      } else {
        toast.warning('Task Creation', 'Please specify a task title');
      }
    }

    // Search commands
    else if (cmd.includes('search') || cmd.includes('find')) {
      const query = cmd.replace(/(search for|find)/i, '').trim();
      if (query) {
        setSearchQuery(query);
        toast.success('Search', `Searching for: ${query}`);
      }
    }

    // General commands
    else if (cmd.includes('help') || cmd.includes('commands')) {
      toast.info('Voice Commands', 'Say "show commands" or "help" to see available commands');
    }

    else {
      toast.warning('Unknown Command', `I didn't understand: "${command}"`);
    }
  }, [setCurrentView, addTask, setSearchQuery, toast]);

  return { processCommand };
};
