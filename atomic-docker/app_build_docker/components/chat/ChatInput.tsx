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

// Placeholder for Meyda type until it's actually used and imported
// type Meyda = any; // Meyda is now directly imported

type Props = {
    sendMessage: (text: string) => void,
    isNewSession: boolean,
    callNewSession: () => void
}

const WAKE_WORD_MODEL_URL = '/models/atom_wake_word/model.json';
const WAKE_WORD_THRESHOLD = 0.7;
const SILENCE_THRESHOLD_MS = 2000;
const MIN_RECORDING_DURATION_MS = 500;

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

    const audioContextRef = useRef<AudioContext | null>(null);
    const micStreamRef = useRef<MediaStream | null>(null); // For wake word's own stream
    const mediaStreamSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const meydaRef = useRef<Meyda | null>(null);
    const featureBufferRef = useRef<number[][]>([]);

    const expectedFeatureFrames = 43;
    const numMfccCoeffs = 13;

    // Silence Detection for STT
    const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const lastSpeechTimeRef = useRef<number>(0);
    const recordingStartTimeRef = useRef<number>(0);

    useEffect(() => {
        if (inputRef.current) {
          inputRef.current.focus()
        }
      }, []);
    
    // Cleanup STT resources on unmount
    useEffect(() => {
        return () => {
            sttStreamRef.current?.getTracks().forEach(track => track.stop());
            if (sttMediaRecorderRef.current && sttMediaRecorderRef.current.state === "recording") {
                sttMediaRecorderRef.current.stop();
            }
        };
    }, []);

    const onChangeText = (e: { currentTarget: { value: React.SetStateAction<string>; }; }) => (setText(e.currentTarget.value))

    // --- Wake Word Engine Functions ---
    const processFeaturesAndPredict = useCallback(async (features: any) => {
        if (!tfModel || !isAudioModeEnabled || isSttRecording || !features.mfcc || features.mfcc.length !== numMfccCoeffs) {
            return;
        }

        featureBufferRef.current.push(features.mfcc);
        if (featureBufferRef.current.length > expectedFeatureFrames) {
            featureBufferRef.current.shift();
        }

        if (featureBufferRef.current.length === expectedFeatureFrames) {
            const inputTensor = tf.tensor([featureBufferRef.current]);
            try {
                const prediction = tfModel.predict(inputTensor) as tf.Tensor;
                const predictionData = await prediction.data();

                if (predictionData[0] > WAKE_WORD_THRESHOLD) {
                    console.log("Atom detected!");
                    // Status will be set by startVoiceCapture as it's called immediately
                    if(meydaRef.current?.isRunning()){
                       meydaRef.current.stop();
                       setWakeWordStatus("Atom detected! Pausing WW..."); // Indicate Meyda is paused
                    }
                    await startVoiceCapture(true); // isWakeWordFollowUp = true
                }
                tf.dispose([inputTensor, prediction]);
            } catch (error) {
                console.error("Error during wake word prediction:", error);
                setWakeWordStatus("Error: Wake word prediction failed. Try toggling Audio Mode.");
                tf.dispose(inputTensor);
            }
        }
    }, [tfModel, isAudioModeEnabled, isSttRecording]); // Added startVoiceCapture to deps later, will fix if issue

    const stopWakeWordEngineInternal = useCallback(() => {
        console.log("stopWakeWordEngineInternal: Cleaning up wake word resources.");
        meydaRef.current?.stop();
        micStreamRef.current?.getTracks().forEach(track => track.stop());
        micStreamRef.current = null;
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
            audioContextRef.current.close().catch(e => console.error("Error closing WW AudioContext:", e));
            audioContextRef.current = null;
        }
        tfModel?.dispose();
        setTfModel(null);

        meydaRef.current = null;
        mediaStreamSourceRef.current = null;
        featureBufferRef.current = [];
    }, [tfModel]);

    const initializeWakeWordEngine = useCallback(async () => {
        if (!isAudioModeEnabled || tfModel) { // Don't re-initialize if model already loaded or mode is off
            if(tfModel && isAudioModeEnabled && !isSttRecording && !meydaRef.current?.isRunning()){
                // Model loaded, audio mode on, not recording, meyda not running -> just start meyda
                console.log("initializeWakeWordEngine: Meyda instance exists but not running. Starting it.");
                 if (audioContextRef.current && audioContextRef.current.state === 'running' &&
                    micStreamRef.current && micStreamRef.current.active &&
                    mediaStreamSourceRef.current && meydaRef.current) {
                    meydaRef.current.start();
                    setWakeWordStatus("Listening for Atom");
                } else {
                     console.log("Wake word audio resources seem invalid for simple Meyda start, attempting full re-init.");
                     // Fall through to full re-initialization by first stopping everything cleanly
                     stopWakeWordEngineInternal();
                     // Then the rest of this function will try to re-initialize
                }
            } else if (tfModel && isAudioModeEnabled && !isSttRecording && meydaRef.current?.isRunning()) {
                // Already initialized and running
                setWakeWordStatus("Listening for Atom");
                return;
            } else if (!isAudioModeEnabled) {
                return; // Explicitly do nothing if audio mode is off
            }
        }

        console.log("Initializing Wake Word Engine (Full Setup)...");
        setWakeWordStatus("Initializing Engine...");
        let modelError = false, micError = false, audioProcessorError = false;

        try {
            if (!tfModel) { // Only load model if not already loaded
                try {
                    const loadedModel = await tf.loadGraphModel(WAKE_WORD_MODEL_URL);
                    setTfModel(loadedModel);
                    console.log("Wake word model loaded.");
                } catch (e) { modelError = true; throw e; }
            }

            let stream;
            try {
                if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
                    audioContextRef.current = new AudioContext();
                    console.log("New AudioContext created for wake word.");
                }
                if (!micStreamRef.current || !micStreamRef.current.active) {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    micStreamRef.current = stream;
                    console.log("New media stream for wake word.");
                } else {
                    stream = micStreamRef.current;
                }
            } catch (e) { micError = true; throw e; }

            const context = audioContextRef.current;
            if (!context) throw new Error("AudioContext not available for wake word.");

            if (!mediaStreamSourceRef.current || mediaStreamSourceRef.current.context.state === 'closed' || mediaStreamSourceRef.current.mediaStream !== stream ) {
                 mediaStreamSourceRef.current = context.createMediaStreamSource(stream);
                 console.log("New MediaStreamAudioSourceNode for wake word.");
            }
            const source = mediaStreamSourceRef.current;

            if (meydaRef.current) meydaRef.current.stop();
            try {
                meydaRef.current = new Meyda({
                    audioContext: context, source: source,
                    bufferSize: 512, featureExtractors: ["mfcc"],
                    callback: processFeaturesAndPredict
                });
                meydaRef.current.start();
                console.log("Meyda instance created and started.");
            } catch (e) { audioProcessorError = true; throw e; }

            featureBufferRef.current = [];
            setWakeWordStatus("Listening for Atom");
        } catch (e: any) {
            console.error("Wake Word Engine Initialization Error:", e.message);
            if (modelError) setWakeWordStatus("Error: Model load failed.");
            else if (micError) setWakeWordStatus("Error: Mic permission denied for WW.");
            else if (audioProcessorError) setWakeWordStatus("Error: Audio processor setup failed for WW.");
            else setWakeWordStatus("Error: Engine init failed.");

            if (isAudioModeEnabled) toggleAudioMode(); // Auto-disable mode on critical error
            else stopWakeWordEngineInternal(); // Ensure cleanup if mode was already off
        }
    }, [isAudioModeEnabled, toggleAudioMode, tfModel, processFeaturesAndPredict, stopWakeWordEngineInternal]);

    const stopWakeWordEngine = useCallback(() => {
        console.log("stopWakeWordEngine called.");
        stopWakeWordEngineInternal();
        setWakeWordStatus("Audio Mode Disabled");
        if (isSttRecording && sttMediaRecorderRef.current) {
            console.log("Audio mode disabled during STT, stopping STT.");
            sttMediaRecorderRef.current.stop();
        }
    }, [isSttRecording, stopWakeWordEngineInternal]);

    // --- STT Logic ---
    const audioChunksRef = useRef<Blob[]>([]);
    useEffect(() => { audioChunksRef.current = audioChunks; }, [audioChunks]);

    const stopVoiceCapture = useCallback(() => {
        console.log("stopVoiceCapture called. Current STT MediaRecorder state:", sttMediaRecorderRef.current?.state);
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

    const startVoiceCapture = useCallback(async (isWakeWordFollowUp: boolean = false) => {
        if (isSttRecording) {
            console.log("startVoiceCapture called but already recording STT.");
            return;
        }

        if (isAudioModeEnabled && !isWakeWordFollowUp && meydaRef.current?.isRunning()) {
            console.log("Manually starting STT capture, pausing wake word listening.");
            meydaRef.current.stop();
        }

        setIsSttRecording(true);
        setAudioChunks([]);
        audioChunksRef.current = [];

        if (isWakeWordFollowUp) {
            setWakeWordStatus("Atom detected! Listening for command...");
        } else if (isAudioModeEnabled) {
            setWakeWordStatus("Listening (STT in Audio Mode)...");
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
                if (event.data.size > 0) audioChunksRef.current.push(event.data);
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
                setWakeWordStatus("Transcribing...");
                const currentAudioChunks = audioChunksRef.current;
                const audioBlob = new Blob(currentAudioChunks, { type: 'audio/webm' });

                audioChunksRef.current = [];
                setAudioChunks([]);

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
                            if (isAudioModeEnabled) setWakeWordStatus("Agent is processing...");
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
            setWakeWordStatus(isAudioModeEnabled ? "Error: Mic for STT." : "Audio Mode Disabled");
        }
    }, [isAudioModeEnabled, isSttRecording, stopVoiceCapture, tfModel]); // Added tfModel as it's checked in onstop implicitly

    const handleManualSttToggle = () => {
        if (isSttRecording) {
            stopVoiceCapture();
        } else {
            startVoiceCapture(false);
        }
    };
    
    // Effect for Audio Mode ON/OFF
    useEffect(() => {
        if (isAudioModeEnabled) {
            if (isSttRecording) {
                console.log("Audio Mode enabled, but STT is active. Deferring WW init.");
            } else {
                initializeWakeWordEngine();
            }
        } else {
            stopWakeWordEngine();
        }
        return () => {
            stopWakeWordEngine();
        };
    }, [isAudioModeEnabled, initializeWakeWordEngine, stopWakeWordEngine]); // isSttRecording removed

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
            setAudioChunks([]); audioChunksRef.current = [];
            startVoiceCapture(false); // isWakeWordFollowUp = false, this is a reply, status will be set by startVoiceCapture
        }
    }, [replyRequestCount, isAudioModeEnabled, isSttRecording, startVoiceCapture]);

    // Effect to manage Meyda's running state (wake word listening)
    useEffect(() => {
        if (isAudioModeEnabled && !isSttRecording && tfModel) {
            if (!meydaRef.current) {
                console.log("ChatInput Effect: Meyda not initialized. Calling initializeWakeWordEngine.");
                initializeWakeWordEngine();
            } else if (!meydaRef.current.isRunning()) {
                console.log("ChatInput Effect: Meyda exists and is paused. Starting Meyda for wake word detection.");
                if (audioContextRef.current && audioContextRef.current.state === 'running' &&
                    micStreamRef.current && micStreamRef.current.active &&
                    mediaStreamSourceRef.current) {
                    meydaRef.current.start();
                    setWakeWordStatus("Listening for Atom");
                } else {
                    console.log("ChatInput Effect: Wake word audio resources seem invalid, re-initializing.");
                    initializeWakeWordEngine();
                }
            } else {
                 if(wakeWordStatus !== "Atom detected! Listening for command..." &&
                    wakeWordStatus !== "Listening for your reply..." &&
                    wakeWordStatus !== "Atom heard, listening..." &&
                    wakeWordStatus !== "Initializing Engine..." &&
                    wakeWordStatus !== "Error: Mic permission denied for WW." &&
                    wakeWordStatus !== "Error: Model load failed." &&
                    wakeWordStatus !== "Error: Audio feature extractor setup failed for WW." &&
                    wakeWordStatus !== "Error: Engine init failed." &&
                    wakeWordStatus !== "Error: Prediction failed.") {
                    setWakeWordStatus("Listening for Atom");
                 }
            }
        } else if (meydaRef.current?.isRunning() && (!isAudioModeEnabled || isSttRecording)) {
            console.log("ChatInput Effect: Audio Mode off OR STT recording active. Pausing Meyda.");
            meydaRef.current.stop();
        }
    }, [isAudioModeEnabled, isSttRecording, tfModel, wakeWordStatus, initializeWakeWordEngine, stopWakeWordEngine]);

    const sttMicButtonDisabled = isTranscribing || (
        isAudioModeEnabled &&
        !(wakeWordStatus === "Atom detected! Listening for command..." ||
          wakeWordStatus === "Listening for your reply..." ||
          wakeWordStatus === "Atom heard, listening..." ||
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
                                    onClick={handleManualSttToggle} // Renamed handler
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

export default ChatInput

// --- Placeholder Icons (if not available in ui/icons.tsx) ---
// Assuming IconMic and IconMicOff are defined in @components/chat/ui/icons.tsx
// For example:
// export const IconMic = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 18.75a5.25 5.25 0 005.25-5.25v-3.75a5.25 5.25 0 00-10.5 0v3.75A5.25 5.25 0 0012 18.75zM19.5 9.75v3.75a7.5 7.5 0 01-15 0V9.75a7.5 7.5 0 0115 0zM9 9.75h-.75A.75.75 0 007.5 10.5v3A.75.75 0 008.25 14.25H9a.75.75 0 00.75-.75v-3A.75.75 0 009 9.75zm6 0h-.75a.75.75 0 00-.75.75v3a.75.75 0 00.75.75H15A.75.75 0 0015.75 13.5v-3A.75.75 0 0015 9.75z"></path></svg>;
// export const IconMicOff = () => <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M12 1.5a5.25 5.25 0 00-5.25 5.25v3.75a5.25 5.25 0 0010.5 0V6.75A5.25 5.25 0 0012 1.5zm-6.75 5.25a7.5 7.5 0 0115 0v3.75a7.5 7.5 0 01-15 0V6.75zm10.125 9.835a.75.75 0 000-1.06l-2.02-2.02a.75.75 0 00-1.06 0l-.885.884a5.252 5.252 0 01-4.43 0l-.884-.884a.75.75 0 10-1.06 1.06l2.02 2.02a.75.75 0 001.06 0l.22-.22a7.457 7.457 0 004.94-.001l.22.22a.75.75 0 001.06 0z" clipRule="evenodd" /></svg>;
