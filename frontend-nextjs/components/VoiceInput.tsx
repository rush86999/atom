import React, { useState, useRef, useCallback, useEffect } from 'react';

interface VoiceInputProps {
    onTranscript: (text: string) => void;
    onCommand?: (result: any) => void;
    className?: string;
}

const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscript, onCommand, className }) => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [error, setError] = useState<string | null>(null);
    const recognitionRef = useRef<any>(null);

    useEffect(() => {
        // Check browser support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            setError('Voice input is not supported in this browser');
            return;
        }

        // Initialize Web Speech API
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false;
        recognitionRef.current.interimResults = true;
        recognitionRef.current.lang = 'en-US';

        recognitionRef.current.onresult = (event: any) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    finalTranscript += result[0].transcript;
                } else {
                    interimTranscript += result[0].transcript;
                }
            }

            setTranscript(finalTranscript || interimTranscript);

            if (finalTranscript) {
                onTranscript(finalTranscript);
            }
        };

        recognitionRef.current.onerror = (event: any) => {
            setError(`Voice error: ${event.error}`);
            setIsListening(false);
        };

        recognitionRef.current.onend = () => {
            setIsListening(false);
        };

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        };
    }, [onTranscript]);

    const toggleListening = useCallback(() => {
        if (!recognitionRef.current) return;

        if (isListening) {
            recognitionRef.current.stop();
            setIsListening(false);
        } else {
            setTranscript('');
            setError(null);
            recognitionRef.current.start();
            setIsListening(true);
        }
    }, [isListening]);

    const submitCommand = async () => {
        if (!transcript.trim()) return;

        try {
            const response = await fetch('/api/v1/voice/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript, language: 'en' }),
            });

            const result = await response.json();
            if (onCommand) {
                onCommand(result);
            }
        } catch (err) {
            setError('Failed to process voice command');
        }
    };

    return (
        <div className={`voice-input ${className || ''}`}>
            <div className="voice-controls">
                <button
                    onClick={toggleListening}
                    className={`voice-button ${isListening ? 'listening' : ''}`}
                    title={isListening ? 'Stop listening' : 'Start voice input'}
                >
                    <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                    >
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                    {isListening && <span className="pulse-ring" />}
                </button>

                {transcript && (
                    <button onClick={submitCommand} className="submit-button">
                        Send to Atom
                    </button>
                )}
            </div>

            {isListening && (
                <div className="listening-indicator">
                    <span className="dot" />
                    <span className="dot" />
                    <span className="dot" />
                    Listening...
                </div>
            )}

            {transcript && (
                <div className="transcript-display">
                    <p>{transcript}</p>
                </div>
            )}

            {error && <div className="voice-error">{error}</div>}

            <style jsx>{`
        .voice-input {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .voice-controls {
          display: flex;
          gap: 12px;
          align-items: center;
        }

        .voice-button {
          position: relative;
          width: 56px;
          height: 56px;
          border-radius: 50%;
          border: none;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
        }

        .voice-button:hover {
          transform: scale(1.05);
          box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
        }

        .voice-button.listening {
          background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.1); }
        }

        .pulse-ring {
          position: absolute;
          width: 100%;
          height: 100%;
          border-radius: 50%;
          border: 2px solid currentColor;
          animation: pulse-ring 1.5s infinite;
        }

        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 1; }
          100% { transform: scale(1.5); opacity: 0; }
        }

        .submit-button {
          padding: 12px 24px;
          border-radius: 8px;
          border: none;
          background: #10b981;
          color: white;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .submit-button:hover {
          background: #059669;
        }

        .listening-indicator {
          display: flex;
          align-items: center;
          gap: 4px;
          color: #f5576c;
          font-size: 14px;
        }

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #f5576c;
          animation: bounce 0.6s infinite alternate;
        }

        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes bounce {
          0% { transform: translateY(0); }
          100% { transform: translateY(-8px); }
        }

        .transcript-display {
          padding: 16px;
          background: rgba(102, 126, 234, 0.1);
          border-radius: 12px;
          border-left: 4px solid #667eea;
        }

        .transcript-display p {
          margin: 0;
          font-size: 16px;
          color: #333;
        }

        .voice-error {
          padding: 12px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 8px;
          color: #dc2626;
          font-size: 14px;
        }
      `}</style>
        </div>
    );
};

export default VoiceInput;
