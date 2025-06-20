/* eslint-disable react/self-closing-comp */
import React, { useState, useRef, useEffect, useCallback } from "react";
import * as tf from '@tensorflow/tfjs';
import Meyda from 'meyda';
import cls from 'classnames'
import {Textarea} from '@components/chat/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from "@components/chat/ui/tooltip";
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

    // Memoized stopVoiceCapture for STT
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

    // processFeaturesAndPredict needs startVoiceCapture, so define startVoiceCapture first or pass as ref if circular.
    // For simplicity, ensure startVoiceCapture is defined before processFeaturesAndPredict if directly called.
    // However, processFeaturesAndPredict is a callback for Meyda.
    // We'll use a forward declaration pattern by defining startVoiceCapture later, and ensure it's memoized.

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
                const predictionData = await prediction.data() as Float32Array; // Ensure type
                if (predictionData[0] > WAKE_WORD_THRESHOLD) {
                    console.log("Atom detected with confidence:", predictionData[0]);
                    if(meydaRef.current?.isRunning()) meydaRef.current.stop();

                    // Fully stop wake word audio resources before STT
                    wwMicStreamRef.current?.getTracks().forEach(track => track.stop());
                    wwMicStreamRef.current = null;
                    if (wwAudioContextRef.current && wwAudioContextRef.current.state !== 'closed') {
                       await wwAudioContextRef.current.close();
                    }
                    wwAudioContextRef.current = null;
                    wwMediaStreamSourceRef.current = null;

                    setWakeWordStatus("Atom detected! Listening for command...");
                    await startVoiceCapture(true); // isWakeWordFollowUp = true
                }
                tf.dispose([inputTensor, prediction]);
            } catch (error) {
                console.error("Error during wake word prediction:", error);
                setWakeWordStatus("Error: Wake word prediction failed.");
                tf.dispose(inputTensor);
            }
        }
    }, [tfModel, isAudioModeEnabled, isSttRecording, startVoiceCapture]); // Added startVoiceCapture

    const stopWakeWordEngineInternal = useCallback(() => {
        console.log("stopWakeWordEngineInternal: Cleaning up wake word resources.");
        meydaRef.current?.stop();
        micStreamRef.current?.getTracks().forEach(track => track.stop());
        micStreamRef.current = null;
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
                if (!micStreamRef.current || !micStreamRef.current.active) {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    micStreamRef.current = stream; console.log("New media stream for WW.");
                } else { stream = micStreamRef.current; }
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

            if (isAudioModeEnabled) toggleAudioMode(); // Auto-disable mode
            else stopWakeWordEngineInternal(); // Ensure cleanup if mode was already off
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
        setSttAudioChunks([]);
        sttAudioChunksRef.current = [];

        if (isWakeWordFollowUp) {
            setWakeWordStatus("Atom detected! Listening for command...");
        } else if (isAudioModeEnabled) {
            setWakeWordStatus("Audio Mode: Listening for your reply/command...");
        } else {
            setWakeWordStatus("Listening (STT)...");
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            sttStreamRef.current = stream;
            const recorder = new MediaRecorder(stream);
            sttMediaRecorderRef.current = recorder;
            recordingStartTimeRef.current = Date.now();
            lastSpeechTimeRef.current = Date.now();

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) sttAudioChunksRef.current.push(event.data);
                if (isAudioModeEnabled && isSttRecording) {
                    lastSpeechTimeRef.current = Date.now();
                    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
                    silenceTimeoutRef.current = setTimeout(() => {
                        if (Date.now() - lastSpeechTimeRef.current >= SILENCE_THRESHOLD_MS &&
                            Date.now() - recordingStartTimeRef.current > MIN_RECORDING_DURATION_MS &&
                            isSttRecording) {
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
                setWakeWordStatus("Audio Mode: Transcribing speech...");
                const currentAudioChunks = sttAudioChunksRef.current;
                const audioBlob = new Blob(currentAudioChunks, { type: 'audio/webm' });

                sttAudioChunksRef.current = [];
                setSttAudioChunks([]);

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
                            setText(prevText => prevText ? `${prevText} ${result.transcription}` : result.transcription);
                            if (inputRef.current) inputRef.current.focus();
                            if (isAudioModeEnabled) setWakeWordStatus("Audio Mode: Agent is processing...");
                            else setWakeWordStatus("Transcription complete.");
                        } else if (result.error) {
                            alert(`Transcription Error: ${result.error}`);
                            if (isAudioModeEnabled) setWakeWordStatus("Error: Transcription failed. Please try again.");
                        } else {
                            if (isAudioModeEnabled) setWakeWordStatus("Empty transcription. Agent is processing...");
                            else setWakeWordStatus("Empty transcription received.");
                        }
                    } catch (e: any) {
                        console.error("STT Error:", e);
                        alert(`STT Error: ${e.message}`);
                        if (isAudioModeEnabled) setWakeWordStatus("Error: Transcription failed. Please try again.");
                    }
                } else {
                    console.log("No audio chunks to process for STT.");
                     if (isAudioModeEnabled) setWakeWordStatus("No speech detected. Ready...");
                     else setWakeWordStatus("No speech detected.");
                }

                setIsTranscribing(false);
                sttStreamRef.current?.getTracks().forEach(track => track.stop());
                sttStreamRef.current = null;
                setIsSttRecording(false);

                if (isAudioModeEnabled) {
                    setWakeWordStatus("Processing complete. Ready...");
                } else {
                    setWakeWordStatus("Audio Mode Disabled");
                }
            };
            recorder.start();
        } catch (error) {
            console.error("Error starting STT voice capture:", error);
            alert("Could not access microphone for STT. Please check permissions.");
            setIsSttRecording(false);
            setWakeWordStatus(isAudioModeEnabled ? "Error: Microphone access denied for STT. Please check permissions." : "Audio Mode Disabled");
            if(isAudioModeEnabled) toggleAudioMode();
        }
    }, [isAudioModeEnabled, isSttRecording, stopVoiceCapture, setText, toggleAudioMode, tfModel]); // tfModel added as initializeWakeWordEngine is in its onStop path indirectly

    const handleManualSttToggle = () => {
        if (isSttRecording) {
            stopVoiceCapture();
        } else {
            startVoiceCapture(false);
        }
    };

    // Effect for Audio Mode ON/OFF (Master effect for wake word engine)
    useEffect(() => {
        if (isAudioModeEnabled) {
            if (isSttRecording) {
                console.log("Audio Mode enabled, but STT is active. Deferring WW init until STT completes.");
            } else {
                initializeWakeWordEngine();
            }
        } else {
            stopWakeWordEngine();
        }
        return () => {
            stopWakeWordEngine();
        };
    }, [isAudioModeEnabled, initializeWakeWordEngine, stopWakeWordEngine]);

    // Effect for handling reply requests from context
    useEffect(() => {
        if (replyRequestCount > 0 && isAudioModeEnabled && !isSttRecording) {
            console.log(`ChatInput: Context requested listen for reply (count: ${replyRequestCount}).`);
            if (meydaRef.current?.isRunning()) {
                console.log("Pausing wake word engine for reply capture.");
                meydaRef.current.stop();
            }
            sttStreamRef.current?.getTracks().forEach(track => track.stop());
            if (sttMediaRecorderRef.current?.state === "recording") sttMediaRecorderRef.current.stop();
            setSttAudioChunks([]);
            audioChunksRef.current = [];
            startVoiceCapture(false);
        }
    }, [replyRequestCount, isAudioModeEnabled, isSttRecording, startVoiceCapture]);

    // Effect to manage Meyda's running state (wake word listening) based on other states
    useEffect(() => {
        if (isAudioModeEnabled && !isSttRecording && tfModel) {
            if (!meydaRef.current?.isRunning()) { // Check if not already running
                console.log("ChatInput Effect: Conditions met to listen for wake word. Starting/Re-initializing Meyda.");
                initializeWakeWordEngine();
            } else {
                 if (wakeWordStatus !== "Audio Mode: Listening for 'Atom'..." &&
                     !wakeWordStatus.startsWith("Atom detected") &&
                     !wakeWordStatus.startsWith("Listening for") &&
                     !wakeWordStatus.startsWith("Initializing") &&
                     !wakeWordStatus.startsWith("Error")) {
                    setWakeWordStatus("Audio Mode: Listening for 'Atom'...");
                 }
            }
        } else if (meydaRef.current?.isRunning() && (!isAudioModeEnabled || isSttRecording)) {
            console.log("ChatInput Effect: Audio Mode off OR STT recording active. Pausing Meyda.");
            meydaRef.current.stop();
        }
    }, [isAudioModeEnabled, isSttRecording, tfModel, wakeWordStatus, initializeWakeWordEngine]);


    const sttMicButtonDisabled = isTranscribing || (
        isAudioModeEnabled &&
        !(wakeWordStatus === "Atom detected! Listening for command..." ||
          wakeWordStatus === "Audio Mode: Listening for your reply/command..." ||
          wakeWordStatus === "Listening (STT in Audio Mode)...")
    );

    return (
        <div className={cls('fixed w-full md:w-1/2 bottom-0 ')}>
            <div className="flex justify-center items-center mb-1 space-x-2 px-2">
                <Button
                    size="sm"
                    variant={isAudioModeEnabled ? "default" : "outline"}
                    onClick={toggleAudioMode}
                    className="rounded-full text-xs sm:text-sm"
                    disabled={isTranscribing || isSttRecording}
                >
                    {isAudioModeEnabled ? "Disable Audio Mode" : "Enable Audio Mode"}
                </Button>
                <span className="text-xs text-gray-500 truncate">Status: {wakeWordStatus}</span>
            </div>
            
            <form onSubmit={onSubmit}  ref={formRef} className={cls('space-y-4 border-t px-4 py-2 shadow-lg sm:rounded-t-xl sm:border md:py-4 bg-white', { 'opacity-50': isNewSession })}>
                <label htmlFor="chat-input" className={cls("sr-only")}>Your message</label>
                <div className="relative flex max-h-60 w-full grow flex-col overflow-hidden sm:rounded-md sm:border ">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="outline"
                                size="icon"
                                type="button"
                                disabled={isNewSession}
                            onClick={e => {
                                e.preventDefault()
                                callNewSession()
                            }}
                            className={cn(
                                buttonVariants({ size: 'sm', variant: 'outline' }),
                                'absolute left-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full p-0'
                            )}
                            >
                            <IconPlus />
                            <span className="sr-only">New Chat</span>
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>New Chat</TooltipContent>
                    </Tooltip>
                    <Textarea
                        id="chat-input"
                        ref={inputRef}
                        tabIndex={0}
                        onKeyDown={onKeyDown}
                        spellCheck={false}
                        rows={1}
                        className={cls("min-h-[60px] w-full focus-within:outline-none sm:text-sm focus:ring-0 focus:ring-offset-0 border-none resize-none py-[1.3rem] pl-12 pr-20")}
                        placeholder="Your message..."
                        value={text}
                        onChange={onChangeText}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    type="button"
                                    size="icon"
                                    variant={isSttRecording ? "destructive" : "outline"}
                                    onClick={handleManualSttToggle}
                                    className="h-8 w-8 rounded-full p-0 mr-2"
                                    disabled={sttMicButtonDisabled}
                                >
                                    {isSttRecording ? <IconMicOff /> : <IconMic />}
                                    <span className="sr-only">{isSttRecording ? "Stop STT recording" : "Start STT recording"}</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>{isTranscribing ? "Transcribing..." : (isSttRecording ? "Stop STT recording" : "Start STT recording")}</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button size="icon" disabled={isNewSession || !text.trim()} type="submit" className={cls("text-white h-8 w-8 rounded-full p-0")}>
                                    <IconArrowElbow />
                                    <span className="sr-only">Send message</span>
                                </Button>
                            </TooltipTrigger>
                        <TooltipContent>Send message</TooltipContent>
                    </Tooltip>
                    </div>
                </div>
            </form>
        </div>
    )
}

export default ChatInput;

// --- Placeholder Icons (if not available in ui/icons.tsx) ---
// Assuming IconMic and IconMicOff are defined in @components/chat/ui/icons.tsx
// For example:
// export const IconMic = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 18.75a5.25 5.25 0 005.25-5.25v-3.75a5.25 5.25 0 00-10.5 0v3.75A5.25 5.25 0 0012 18.75zM19.5 9.75v3.75a7.5 7.5 0 01-15 0V9.75a7.5 7.5 0 0115 0zM9 9.75h-.75A.75.75 0 007.5 10.5v3A.75.75 0 008.25 14.25H9a.75.75 0 00.75-.75v-3A.75.75 0 009 9.75zm6 0h-.75a.75.75 0 00-.75.75v3a.75.75 0 00.75.75H15A.75.75 0 0015.75 13.5v-3A.75.75 0 0015 9.75z"></path></svg>;
// export const IconMicOff = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M12 1.5a5.25 5.25 0 00-5.25 5.25v3.75a5.25 5.25 0 0010.5 0V6.75A5.25 5.25 0 0012 1.5zm-6.75 5.25a7.5 7.5 0 0115 0v3.75a7.5 7.5 0 01-15 0V6.75zm10.125 9.835a.75.75 0 000-1.06l-2.02-2.02a.75.75 0 00-1.06 0l-.885.884a5.252 5.252 0 01-4.43 0l-.884-.884a.75.75 0 10-1.06 1.06l2.02 2.02a.75.75 0 001.06 0l.22-.22a7.457 7.457 0 004.94-.001l.22.22a.75.75 0 001.06 0z" clipRule="evenodd" /></svg>;
