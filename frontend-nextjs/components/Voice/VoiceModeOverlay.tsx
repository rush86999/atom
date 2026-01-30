'use client'

import { useState, useEffect, useRef } from 'react'
import { VoiceVisualizer } from './VoiceVisualizer'
import { Button } from '@/components/ui/button'
import { X, Mic, MicOff } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

interface VoiceModeOverlayProps {
    isOpen: boolean
    onClose: () => void
    onSend: (text: string) => Promise<void>
    isProcessing: boolean
    lastAgentMessage: string | null
}

export function VoiceModeOverlay({ isOpen, onClose, onSend, isProcessing, lastAgentMessage }: VoiceModeOverlayProps) {
    const [mode, setMode] = useState<'idle' | 'listening' | 'processing' | 'speaking'>('idle')
    const [transcript, setTranscript] = useState('')
    const recognitionRef = useRef<any>(null)
    const synthesisRef = useRef<SpeechSynthesis | null>(null)
    const [lastSpokenMessage, setLastSpokenMessage] = useState<string | null>(null)

    // Initialize Speech Synthesis
    useEffect(() => {
        if (typeof window !== 'undefined') {
            synthesisRef.current = window.speechSynthesis
        }
    }, [])

    // Handle Agent Speech
    useEffect(() => {
        if (lastAgentMessage && lastAgentMessage !== lastSpokenMessage && !isProcessing) {
            setLastSpokenMessage(lastAgentMessage)
            speak(lastAgentMessage)
        }
    }, [lastAgentMessage, isProcessing])

    // Initialize Recognition on Open
    useEffect(() => {
        if (isOpen) {
            startListening()
        } else {
            stopListening()
            stopSpeaking()
        }
        return () => {
            stopListening()
            stopSpeaking()
        }
    }, [isOpen])

    const startListening = () => {
        if (!('webkitSpeechRecognition' in window)) {
            alert("Voice not supported in this browser. Try Chrome/Edge.")
            return
        }

        stopSpeaking() // Don't listen to self

        try {
            const SpeechRecognition = (window as any).webkitSpeechRecognition
            const recognition = new SpeechRecognition()
            recognition.continuous = false // Stop after one sentence for turn-taking
            recognition.interimResults = true
            recognition.lang = 'en-US'

            recognition.onstart = () => {
                setMode('listening')
                setTranscript('')
            }

            recognition.onresult = (event: any) => {
                let interimTranscript = ''
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    interimTranscript += event.results[i][0].transcript
                }
                setTranscript(interimTranscript)
            }

            recognition.onend = () => {
                // If we have a transcript, send it
                // We access the LATEST transcript from state/ref (react closure issue, be careful)
                // Actually safer to read final result from event above, but this is simple mocked logic
                // Wait for final event handling
            }

            // Override result slightly to detect 'isFinal'
            recognition.onresult = (event: any) => {
                let finalTx = ''
                let interimTx = ''
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTx += event.results[i][0].transcript
                    } else {
                        interimTx += event.results[i][0].transcript
                    }
                }

                setTranscript(finalTx || interimTx)

                if (finalTx) {
                    handleSend(finalTx)
                    recognition.stop()
                }
            }

            recognitionRef.current = recognition
            recognition.start()
        } catch (e) {
            console.error(e)
            setMode('idle')
        }
    }

    const stopListening = () => {
        if (recognitionRef.current) {
            try {
                recognitionRef.current.stop()
            } catch (e) { }
            recognitionRef.current = null
        }
        if (mode === 'listening') setMode('idle')
    }

    const stopSpeaking = () => {
        if (synthesisRef.current) {
            synthesisRef.current.cancel()
        }
    }

    const handleSend = async (text: string) => {
        setMode('processing')
        await onSend(text)
        // Set mode to speaking is handled by effect on lastAgentMessage
        // But if no response, go to idle
    }

    const speak = (text: string) => {
        if (!synthesisRef.current) return

        // Simple text cleanup
        const cleanText = text.replace(/[*#`]/g, '') // Remove markdown

        const utterance = new SpeechSynthesisUtterance(cleanText)

        // Pick a nice voice if available
        const voices = synthesisRef.current.getVoices()
        const preferredVoice = voices.find(v => v.name.includes("Google US English")) || voices[0]
        if (preferredVoice) utterance.voice = preferredVoice

        utterance.rate = 1.1

        utterance.onstart = () => setMode('speaking')
        utterance.onend = () => {
            setMode('idle')
            // Auto restart listening for continuous conversation?
            // For now, let user click to reply to avoid loops
        }

        synthesisRef.current.speak(utterance)
    }

    const handleClose = () => {
        stopListening()
        stopSpeaking()
        onClose()
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 bg-black/95 backdrop-blur-xl flex flex-col items-center justify-center p-6"
                >
                    <Button
                        variant="ghost"
                        size="icon"
                        className="absolute top-6 right-6 rounded-full h-12 w-12 hover:bg-white/10"
                        onClick={handleClose}
                    >
                        <X className="w-6 h-6 text-white" />
                    </Button>

                    <div className="flex-1 flex flex-col items-center justify-center w-full max-w-2xl space-y-12">

                        <div className="text-center space-y-4">
                            <h2 className="text-2xl font-medium text-zinc-400">
                                {mode === 'listening' ? "I'm listening..." :
                                    mode === 'processing' ? "Thinking..." :
                                        mode === 'speaking' ? "Atom Speaking..." :
                                            "Tap to speak"}
                            </h2>
                            <p className="text-4xl md:text-5xl font-bold text-white leading-tight min-h-[120px]">
                                "{transcript || (mode === 'speaking' ? lastAgentMessage?.slice(0, 100) + "..." : "...")}"
                            </p>
                        </div>

                        <VoiceVisualizer mode={mode} />

                        <div className="flex gap-6">
                            <Button
                                size="lg"
                                className={`h-20 w-20 rounded-full transition-all duration-300 ${mode === 'listening'
                                        ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/20 scale-110'
                                        : 'bg-white text-black hover:bg-zinc-200 shadow-lg shadow-white/20'
                                    }`}
                                onClick={mode === 'listening' ? stopListening : startListening}
                            >
                                {mode === 'listening' ? <MicOff className="h-8 w-8" /> : <Mic className="h-8 w-8" />}
                            </Button>
                        </div>
                    </div>

                    <div className="pb-8">
                        <p className="text-zinc-600 text-sm font-medium">ATOM VOICE v1.0 • WEB SPEECH API</p>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}
