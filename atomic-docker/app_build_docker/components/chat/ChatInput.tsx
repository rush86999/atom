/* eslint-disable react/self-closing-comp */
import React, { useState, useRef, useEffect, useCallback } from "react";
import * as tf from '@tensorflow/tfjs';
import Meyda from 'meyda';
// import cls from 'classnames' // cn is preferred now
import {Textarea} from '@components/chat/ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@components/chat/ui/tooltip";
import { cn } from "@lib/Chat/utils";
import { buttonVariants, Button } from "@components/chat/ui/button";
import { IconPlus, IconArrowElbow, IconMic, IconMicOff } from '@components/chat/ui/icons';
import { useEnterSubmit } from '@lib/Chat/hooks/use-enter-submit'
import { useAudioMode } from '@lib/contexts/AudioModeContext';

type Props = {
    sendMessage: (text: string) => void,
    isNewSession: boolean,
    callNewSession: () => void
}

const WAKE_WORD_MODEL_URL = '/models/atom_wake_word/model.json';
const WAKE_WORD_THRESHOLD = 0.7;
const SILENCE_THRESHOLD_MS = 2000;
const MIN_RECORDING_DURATION_MS = 500;
const MEYDA_BUFFER_SIZE = 512;
const MEYDA_FEATURE_EXTRACTORS = ["mfcc"];
const MEYDA_MFCC_COEFFS = 13;
const WAKE_WORD_EXPECTED_FRAMES = 43;

const ChatInput = ({ sendMessage, isNewSession, callNewSession }: Props) => {
    const [text, setText] = useState<string>('');
    const { formRef, onKeyDown } = useEnterSubmit();
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // --- STT States ---
    const [isSttRecording, setIsSttRecording] = useState<boolean>(false);
    const sttMediaRecorderRef = useRef<MediaRecorder | null>(null);
    const sttAudioChunksRef = useRef<Blob[]>([]);
    const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
    const sttStreamRef = useRef<MediaStream | null>(null);

    // --- Audio Mode & Wake Word States ---
    const { isAudioModeEnabled, toggleAudioMode, replyRequestCount } = useAudioMode();
    const [wakeWordStatus, setWakeWordStatus] = useState<string>("Audio Mode Disabled");
    const [tfModel, setTfModel] = useState<tf.GraphModel | tf.LayersModel | null>(null);

    const wwAudioContextRef = useRef<AudioContext | null>(null); // Dedicated for Wake Word
    const wwMicStreamRef = useRef<MediaStream | null>(null);
    const wwMediaStreamSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const meydaRef = useRef<Meyda | null>(null);
    const featureBufferRef = useRef<number[][]>([]);

    const recordingStartTimeRef = useRef<number>(0);
    const lastSpeechTimeRef = useRef<number>(0);
    const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => { if (inputRef.current) inputRef.current.focus() }, []);

    useEffect(() => { // Cleanup STT resources
        return () => {
            sttStreamRef.current?.getTracks().forEach(track => track.stop());
            if (sttMediaRecorderRef.current?.state === "recording") sttMediaRecorderRef.current.stop();
        };
    }, []);

    const onChangeText = (e: { currentTarget: { value: React.SetStateAction<string>; }; }) => setText(e.currentTarget.value);

    const stopVoiceCapture = useCallback(() => {
        console.log("stopVoiceCapture called. STT MediaRecorder state:", sttMediaRecorderRef.current?.state);
        if (sttMediaRecorderRef.current && sttMediaRecorderRef.current.state === "recording") {
            sttMediaRecorderRef.current.stop();
        }
        if (silenceTimeoutRef.current) {
            clearTimeout(silenceTimeoutRef.current);
            silenceTimeoutRef.current = null;
        }
        if (sttMediaRecorderRef.current?.state !== "recording" && isSttRecording) {
             setIsSttRecording(false);
        }
    }, [isSttRecording]);

    const processFeaturesAndPredict = useCallback(async (features: any) => {
        if (!tfModel || !isAudioModeEnabled || isSttRecording || !meydaRef.current?.isRunning() || !features.mfcc || features.mfcc.length !== MEYDA_MFCC_COEFFS) {
            return;
        }
        featureBufferRef.current.push(features.mfcc);
        if (featureBufferRef.current.length > WAKE_WORD_EXPECTED_FRAMES) featureBufferRef.current.shift();

        if (featureBufferRef.current.length === WAKE_WORD_EXPECTED_FRAMES) {
            const inputTensor = tf.tensor3d([featureBufferRef.current], [1, WAKE_WORD_EXPECTED_FRAMES, MEYDA_MFCC_COEFFS]);
            try {
                const prediction = tfModel.predict(inputTensor) as tf.Tensor;
                const predictionData = await prediction.data() as Float32Array;
                if (predictionData[0] > WAKE_WORD_THRESHOLD) {
                    console.log("Atom detected with confidence:", predictionData[0]);
                    if(meydaRef.current?.isRunning()) meydaRef.current.stop();

                    wwMicStreamRef.current?.getTracks().forEach(track => track.stop());
                    wwMicStreamRef.current = null;
                    if (wwAudioContextRef.current && wwAudioContextRef.current.state !== 'closed') {
                       await wwAudioContextRef.current.close();
                    }
                    wwAudioContextRef.current = null;
                    wwMediaStreamSourceRef.current = null;

                    setWakeWordStatus("Atom detected! Listening for command...");
                    await startVoiceCapture(true);
                }
                tf.dispose([inputTensor, prediction]);
            } catch (error) {
                console.error("Error during wake word prediction:", error);
                setWakeWordStatus("Error: Wake word prediction failed.");
                tf.dispose(inputTensor);
            }
        }
    }, [tfModel, isAudioModeEnabled, isSttRecording, startVoiceCapture]);

    const stopWakeWordEngineInternal = useCallback(() => {
        console.log("stopWakeWordEngineInternal: Cleaning up wake word resources.");
        meydaRef.current?.stop();
        // micStreamRef is wwMicStreamRef in this context
        wwMicStreamRef.current?.getTracks().forEach(track => track.stop());
        wwMicStreamRef.current = null;
        if (wwAudioContextRef.current && wwAudioContextRef.current.state !== 'closed') {
            wwAudioContextRef.current.close().catch(e => console.error("Error closing WW AudioContext:", e));
        }
        wwAudioContextRef.current = null;
        tfModel?.dispose();
        setTfModel(null);
        meydaRef.current = null;
        wwMediaStreamSourceRef.current = null;
        featureBufferRef.current = [];
    }, [tfModel]);

    const initializeWakeWordEngine = useCallback(async () => {
        if (!isAudioModeEnabled) { console.log("Attempted to init WW engine, but Audio Mode is off."); return; }
        if (tfModel && meydaRef.current?.isRunning()) { console.log("WW engine already initialized and running."); return; }

        console.log("Initializing Wake Word Engine...");
        setWakeWordStatus("Audio Mode: Initializing engine...");
        let modelError = false, micError = false, audioProcessorError = false;

        try {
            if (!tfModel) {
                try {
                    const loadedModel = await tf.loadGraphModel(WAKE_WORD_MODEL_URL);
                    setTfModel(loadedModel); console.log("Wake word model loaded.");
                } catch (e) { modelError = true; throw e; }
            }
            let stream;
            try {
                if (!wwAudioContextRef.current || wwAudioContextRef.current.state === 'closed') {
                    wwAudioContextRef.current = new AudioContext(); console.log("New AudioContext for WW.");
                }
                 // Use wwMicStreamRef for wake word specific stream
                if (!wwMicStreamRef.current || !wwMicStreamRef.current.active) {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    wwMicStreamRef.current = stream; console.log("New media stream for WW.");
                } else { stream = wwMicStreamRef.current; }
            } catch (e) { micError = true; throw e; }

            const context = wwAudioContextRef.current;
            if (!context) throw new Error("AudioContext not available for WW.");

            if (!wwMediaStreamSourceRef.current || wwMediaStreamSourceRef.current.context.state === 'closed' || wwMediaStreamSourceRef.current.mediaStream !== stream ) {
                 wwMediaStreamSourceRef.current = context.createMediaStreamSource(stream); console.log("New MediaStreamAudioSourceNode for WW.");
            }
            const source = wwMediaStreamSourceRef.current;

            if (meydaRef.current) meydaRef.current.stop();
            try {
                meydaRef.current = new Meyda({
                    audioContext: context, source: source,
                    bufferSize: MEYDA_BUFFER_SIZE, featureExtractors: MEYDA_FEATURE_EXTRACTORS,
                    callback: processFeaturesAndPredict
                });
                meydaRef.current.start(); console.log("Meyda instance created and started for WW.");
            } catch (e) { audioProcessorError = true; throw e; }

            featureBufferRef.current = [];
            setWakeWordStatus("Audio Mode: Listening for 'Atom'...");
        } catch (e: any) {
            console.error("Wake Word Engine Initialization Error:", e.message);
            if (modelError) setWakeWordStatus("Error: Wake word model failed to load. Please try again.");
            else if (micError) setWakeWordStatus("Error: Microphone access denied for wake word. Please check permissions.");
            else if (audioProcessorError) setWakeWordStatus("Error: Audio feature setup failed. Please try again.");
            else setWakeWordStatus("Error: Engine init failed.");

            if (isAudioModeEnabled) toggleAudioMode();
            else stopWakeWordEngineInternal();
        }
    }, [isAudioModeEnabled, toggleAudioMode, tfModel, processFeaturesAndPredict, stopWakeWordEngineInternal]);

    const stopWakeWordEngine = useCallback(() => {
        console.log("stopWakeWordEngine called.");
        stopWakeWordEngineInternal();
        setWakeWordStatus("Audio Mode: Disabled.");
        if (isSttRecording && sttMediaRecorderRef.current) {
            console.log("Audio mode disabled/stopped during STT, stopping STT.");
            sttMediaRecorderRef.current.stop();
        }
    }, [isSttRecording, stopWakeWordEngineInternal]);

    const startVoiceCapture = useCallback(async (isWakeWordFollowUp: boolean = false) => {
        if (isSttRecording) { console.log("startVoiceCapture called but already recording STT."); return; }

        if (isAudioModeEnabled && !isWakeWordFollowUp && meydaRef.current?.isRunning()) {
            console.log("Manually starting STT capture, pausing wake word listening.");
            meydaRef.current.stop();
        }

        setIsSttRecording(true);
        // setSttAudioChunks([]); // This was problematic, sttAudioChunksRef.current is the source of truth
        sttAudioChunksRef.current = [];


        if (isWakeWordFollowUp) {
            setWakeWordStatus("Atom detected! Listening for command...");
        } else if (isAudioModeEnabled) {
            setWakeWordStatus("Audio Mode: Listening for your reply/command...");
        } else {
            setWakeWordStatus("Listening (STT)...");
        }

        try {
            // Ensure STT uses its own stream, separate from WW stream
            if (sttStreamRef.current) sttStreamRef.current.getTracks().forEach(track => track.stop());
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            sttStreamRef.current = stream;

            const recorder = new MediaRecorder(stream);
            sttMediaRecorderRef.current = recorder;
            recordingStartTimeRef.current = Date.now();
            lastSpeechTimeRef.current = Date.now();

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) sttAudioChunksRef.current.push(event.data);
                if (isAudioModeEnabled && isSttRecording) { // Check isSttRecording as well
                    lastSpeechTimeRef.current = Date.now();
                    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
                    silenceTimeoutRef.current = setTimeout(() => {
                        if (Date.now() - lastSpeechTimeRef.current >= SILENCE_THRESHOLD_MS &&
                            Date.now() - recordingStartTimeRef.current > MIN_RECORDING_DURATION_MS &&
                            isSttRecording) { // Check isSttRecording again before stopping
                            console.log("Silence detected, stopping STT capture.");
                            stopVoiceCapture();
                        }
                    }, SILENCE_THRESHOLD_MS);
                }
            };

            recorder.onstop = async () => {
                console.log("STT MediaRecorder.onstop triggered.");
                if (silenceTimeoutRef.current) { clearTimeout(silenceTimeoutRef.current); silenceTimeoutRef.current = null; }

                setIsTranscribing(true);
                setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: Transcribing..." : "Transcribing...");

                const audioBlob = new Blob(sttAudioChunksRef.current, { type: 'audio/webm' });
                sttAudioChunksRef.current = []; // Clear chunks after creating blob

                if (audioBlob.size > 0) {
                    const audioFile = new File([audioBlob], "voice_input.webm", { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append("audio_file", audioFile);
                    try {
                        const response = await fetch('/api/audio_processor/stt', { method: 'POST', body: formData });
                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || `STT API Error: ${response.status}`);
                        }
                        const result = await response.json();
                        if (result.transcription) {
                            setText(prevText => prevText ? `${prevText} ${result.transcription}`.trim() : result.transcription);
                            if (inputRef.current) inputRef.current.focus();
                             setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: Transcription complete. Ready..." : "Transcription complete.");
                        } else if (result.error) {
                            alert(`Transcription Error: ${result.error}`);
                            setWakeWordStatus(isAudioModeEnabled ? "Error: Transcription failed. Try again." : "Transcription Error.");
                        } else {
                             setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: Empty transcription. Ready..." : "Empty transcription.");
                        }
                    } catch (e: any) {
                        console.error("STT Error:", e);
                        alert(`STT Error: ${e.message}`);
                        setWakeWordStatus(isAudioModeEnabled ? "Error: STT request failed. Try again." : "STT Request Error.");
                    }
                } else {
                    console.log("No audio chunks to process for STT.");
                    setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: No speech detected. Ready..." : "No speech detected.");
                }

                setIsTranscribing(false);
                sttStreamRef.current?.getTracks().forEach(track => track.stop());
                sttStreamRef.current = null; // Clean up STT stream
                setIsSttRecording(false); // Ensure this is set after all processing

                // If audio mode is still on, re-initialize wake word listening
                if (isAudioModeEnabled) {
                    initializeWakeWordEngine();
                } else {
                    setWakeWordStatus("Audio Mode Disabled");
                }
            };
            recorder.start(1000); // Optional: timeslice to get data more frequently if needed
        } catch (error) {
            console.error("Error starting STT voice capture:", error);
            alert("Could not access microphone for STT. Please check permissions.");
            setIsSttRecording(false);
            setWakeWordStatus(isAudioModeEnabled ? "Error: Mic access denied for STT." : "Mic Access Denied.");
            if(isAudioModeEnabled) {
                // Consider if toggling audio mode off is the best UX here, or just resetting state.
                // For now, let's just reset status and not toggle mode off automatically on STT mic error.
                 initializeWakeWordEngine(); // Try to go back to WW listening if possible
            }
        }
    }, [isAudioModeEnabled, isSttRecording, stopVoiceCapture, setText, /*toggleAudioMode,*/ tfModel, initializeWakeWordEngine]);


    const handleManualSttToggle = () => {
        if (isSttRecording) {
            stopVoiceCapture();
        } else {
            // If in audio mode and wake word is listening, stop it first.
            if (isAudioModeEnabled && meydaRef.current?.isRunning()) {
                meydaRef.current.stop();
                // No need to fully cleanup WW engine here, just pause listening.
            }
            startVoiceCapture(false);
        }
    };

    useEffect(() => {
        if (isAudioModeEnabled) {
            if (!isSttRecording && !isTranscribing) { // Only init WW if not actively doing STT/transcribing
                initializeWakeWordEngine();
            }
        } else {
            stopWakeWordEngine(); // This will also stop STT if it was initiated by WW
        }
        // Explicit cleanup for ww engine when component unmounts or isAudioModeEnabled changes from true to false.
        return () => {
            if (isAudioModeEnabled) { // Only run stopWakeWordEngine if it was enabled
                 stopWakeWordEngine();
            }
        };
    }, [isAudioModeEnabled, initializeWakeWordEngine, stopWakeWordEngine, isSttRecording, isTranscribing]);


    useEffect(() => {
        if (replyRequestCount > 0 && isAudioModeEnabled && !isSttRecording && !isTranscribing) {
            console.log(`ChatInput: Context requested listen for reply (count: ${replyRequestCount}).`);
            if (meydaRef.current?.isRunning()) {
                console.log("Pausing wake word engine for reply capture.");
                meydaRef.current.stop();
            }
            // Ensure any existing STT stream is stopped before starting a new one
            sttStreamRef.current?.getTracks().forEach(track => track.stop());
            if (sttMediaRecorderRef.current?.state === "recording") {
                sttMediaRecorderRef.current.stop(); // Stop existing recorder if any
            }
            sttAudioChunksRef.current = []; // Clear previous chunks
            startVoiceCapture(false); // Start STT for reply
        }
    }, [replyRequestCount, isAudioModeEnabled, isSttRecording, isTranscribing, startVoiceCapture]);

    // This effect seems redundant given the logic in initializeWakeWordEngine and the main isAudioModeEnabled effect.
    // Simplified: if audio mode is on, not doing STT, and WW model loaded, ensure WW is running.
    useEffect(() => {
        if (isAudioModeEnabled && !isSttRecording && !isTranscribing && tfModel && !meydaRef.current?.isRunning()) {
            console.log("ChatInput Effect: Conditions met to (re)start wake word listening.");
            initializeWakeWordEngine(); // This will re-check conditions and start Meyda if needed
        } else if (meydaRef.current?.isRunning() && (!isAudioModeEnabled || isSttRecording || isTranscribing)) {
            console.log("ChatInput Effect: Conditions met to pause Meyda.");
            meydaRef.current.stop();
            if (!isSttRecording && !isTranscribing && !isAudioModeEnabled) { // If Meyda stopped because audio mode turned off (and not STT)
                setWakeWordStatus("Audio Mode Disabled");
            } else if (!isSttRecording && !isTranscribing && isAudioModeEnabled && wakeWordStatus.startsWith("Audio Mode: Listening for 'Atom'...")) {
                // If meyda stopped for other reasons but should be listening
            }
        }
    }, [isAudioModeEnabled, isSttRecording, isTranscribing, tfModel, initializeWakeWordEngine, wakeWordStatus]);


    const sttMicButtonDisabled = isTranscribing || (isAudioModeEnabled && tfModel && meydaRef.current?.isRunning() && !isSttRecording);
    // Simplified: Disable if transcribing. If in audio mode with WW running, it means WW is active, so manual STT should be disabled
    // unless STT is already active (then it's a stop button).

    const onSubmitForm = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (text.trim()) {
            if (text.trim().toLowerCase() === 'show me an image') {
                const message = {
                    role: 'assistant',
                    content: 'Here is an image:',
                    id: Date.now(),
                    date: new Date().toISOString(),
                    customComponentType: 'image_display',
                    customComponentProps: {
                        imageUrl: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D'
                    }
                };
                // @ts-ignore
                sendMessage(message);
            } else {
                sendMessage(text);
            }
            setText('');
            if (inputRef.current) {
                inputRef.current.style.height = 'auto'; // Reset height after send
            }
        }
    };

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        }
    }, [text]);


    return (
        <div className={cn('fixed w-full md:max-w-2xl bottom-0 left-1/2 -translate-x-1/2 font-sans z-50 px-2 md:px-0 pb-2 md:pb-4')}>
            <div className="flex justify-center items-center mb-2 space-x-2 px-2">
                <Button
                    size="sm"
                    variant={isAudioModeEnabled ? "default" : "outline"}
                    onClick={toggleAudioMode}
                    className="rounded-full text-xs" // sm:text-sm removed for consistency
                    disabled={isTranscribing || (!isAudioModeEnabled && isSttRecording) /* Allow disabling if STT is on but audio mode is off */}
                >
                    {isAudioModeEnabled ? <IconMicOff className="mr-1 h-4 w-4" /> : <IconMic className="mr-1 h-4 w-4" />}
                    {isAudioModeEnabled ? "Disable Audio Mode" : "Enable Audio Mode"}
                </Button>
                <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1 text-center">
                    {isTranscribing ? "Transcribing..." : wakeWordStatus}
                </span>
            </div>
            
            <form onSubmit={onSubmitForm}  ref={formRef} className={cn(
                'space-y-0 border-t px-3 py-3 shadow-xl sm:rounded-xl sm:border md:py-3',
                'bg-white dark:bg-gray-800 dark:border-gray-700',
                { 'opacity-60 pointer-events-none': isNewSession }
                )}>
                {/* <label htmlFor="chat-input" className={cn("sr-only")}>Your message</label> */}
                <div className="relative flex w-full grow flex-col overflow-hidden items-center"> {/* Added items-center */}
                    <TooltipProvider delayDuration={300}>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost" // Changed to ghost for a cleaner look
                                    size="icon"
                                    type="button"
                                    disabled={isNewSession}
                                onClick={e => {
                                    e.preventDefault()
                                    callNewSession()
                                }}
                                className={cn(
                                    // 'absolute left-1 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full p-0' // Original positioning
                                    'shrink-0 mr-2 self-center text-gray-500 hover:text-sky-600 dark:text-gray-400 dark:hover:text-sky-500'
                                )}
                                >
                                <IconPlus className="h-5 w-5"/>
                                <span className="sr-only">New Chat</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">New Chat</TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                    <Textarea
                        id="chat-input"
                        ref={inputRef}
                        tabIndex={0}
                        onKeyDown={onKeyDown}
                        spellCheck={false}
                        rows={1}
                        className={cn(
                            "flex-1 min-h-[44px] max-h-[150px] w-full rounded-lg resize-none py-2.5 pl-3 pr-20 sm:text-sm", // Adjusted padding and height
                            "border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700",
                            "focus:ring-0 focus:ring-offset-0 focus:border-sky-500 dark:focus:border-sky-500" // Simplified focus
                        )}
                        placeholder="Your message..."
                        value={text}
                        onChange={onChangeText}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center space-x-1">
                        <TooltipProvider delayDuration={300}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        type="button"
                                        size="icon"
                                        variant={isSttRecording ? "destructive" : "ghost"} // Changed to ghost
                                        onClick={handleManualSttToggle}
                                        className="h-8 w-8 rounded-full p-0 text-gray-500 hover:text-sky-600 dark:text-gray-400 dark:hover:text-sky-500"
                                        disabled={sttMicButtonDisabled}
                                    >
                                        {isSttRecording ? <IconMicOff className="h-5 w-5" /> : <IconMic className="h-5 w-5" />}
                                        <span className="sr-only">{isSttRecording ? "Stop recording" : "Start recording"}</span>
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="top">{isTranscribing ? "Transcribing..." : (isSttRecording ? "Stop recording" : "Start recording")}</TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                        <TooltipProvider delayDuration={300}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        size="icon"
                                        disabled={isNewSession || !text.trim()}
                                        type="submit"
                                        className={cn(
                                            "h-8 w-8 rounded-full p-0 bg-sky-600 hover:bg-sky-700 text-white dark:bg-sky-500 dark:hover:bg-sky-600",
                                            {"opacity-50 cursor-not-allowed": isNewSession || !text.trim()}
                                            )}
                                        >
                                        <IconArrowElbow className="h-5 w-5" />
                                        <span className="sr-only">Send message</span>
                                    </Button>
                                </TooltipTrigger>
                            <TooltipContent side="top">Send message</TooltipContent>
                        </Tooltip>
                        </TooltipProvider>
                    </div>
                </div>
            </form>
        </div>
    )
}

export default ChatInput;
