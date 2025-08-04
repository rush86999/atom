"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
/* eslint-disable react/self-closing-comp */
const react_1 = require("react");
const tf = __importStar(require("@tensorflow/tfjs"));
const meyda_1 = __importDefault(require("meyda"));
// import cls from 'classnames' // cn is preferred now
const textarea_1 = require("@components/chat/ui/textarea");
const tooltip_1 = require("@components/chat/ui/tooltip");
const utils_1 = require("@lib/Chat/utils");
const button_1 = require("@components/chat/ui/button");
const icons_1 = require("@components/chat/ui/icons");
const use_enter_submit_1 = require("@lib/Chat/hooks/use-enter-submit");
const AudioModeContext_1 = require("@lib/contexts/AudioModeContext");
const WAKE_WORD_MODEL_URL = '/models/atom_wake_word/model.json';
const WAKE_WORD_THRESHOLD = 0.7;
const SILENCE_THRESHOLD_MS = 2000;
const MIN_RECORDING_DURATION_MS = 500;
const MEYDA_BUFFER_SIZE = 512;
const MEYDA_FEATURE_EXTRACTORS = ["mfcc"];
const MEYDA_MFCC_COEFFS = 13;
const WAKE_WORD_EXPECTED_FRAMES = 43;
const ChatInput = ({ sendMessage, isNewSession, callNewSession }) => {
    const [text, setText] = (0, react_1.useState)('');
    const { formRef, onKeyDown } = (0, use_enter_submit_1.useEnterSubmit)();
    const inputRef = (0, react_1.useRef)(null);
    // --- STT States ---
    const [isSttRecording, setIsSttRecording] = (0, react_1.useState)(false);
    const sttMediaRecorderRef = (0, react_1.useRef)(null);
    const sttAudioChunksRef = (0, react_1.useRef)([]);
    const [isTranscribing, setIsTranscribing] = (0, react_1.useState)(false);
    const sttStreamRef = (0, react_1.useRef)(null);
    // --- Audio Mode & Wake Word States ---
    const { isAudioModeEnabled, toggleAudioMode, replyRequestCount } = (0, AudioModeContext_1.useAudioMode)();
    const [wakeWordStatus, setWakeWordStatus] = (0, react_1.useState)("Audio Mode Disabled");
    const [tfModel, setTfModel] = (0, react_1.useState)(null);
    const wwAudioContextRef = (0, react_1.useRef)(null); // Dedicated for Wake Word
    const wwMicStreamRef = (0, react_1.useRef)(null);
    const wwMediaStreamSourceRef = (0, react_1.useRef)(null);
    const meydaRef = (0, react_1.useRef)(null);
    const featureBufferRef = (0, react_1.useRef)([]);
    const recordingStartTimeRef = (0, react_1.useRef)(0);
    const lastSpeechTimeRef = (0, react_1.useRef)(0);
    const silenceTimeoutRef = (0, react_1.useRef)(null);
    (0, react_1.useEffect)(() => { if (inputRef.current)
        inputRef.current.focus(); }, []);
    (0, react_1.useEffect)(() => {
        return () => {
            sttStreamRef.current?.getTracks().forEach(track => track.stop());
            if (sttMediaRecorderRef.current?.state === "recording")
                sttMediaRecorderRef.current.stop();
        };
    }, []);
    const onChangeText = (e) => setText(e.currentTarget.value);
    const stopVoiceCapture = (0, react_1.useCallback)(() => {
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
    const processFeaturesAndPredict = (0, react_1.useCallback)(async (features) => {
        if (!tfModel || !isAudioModeEnabled || isSttRecording || !meydaRef.current?.isRunning() || !features.mfcc || features.mfcc.length !== MEYDA_MFCC_COEFFS) {
            return;
        }
        featureBufferRef.current.push(features.mfcc);
        if (featureBufferRef.current.length > WAKE_WORD_EXPECTED_FRAMES)
            featureBufferRef.current.shift();
        if (featureBufferRef.current.length === WAKE_WORD_EXPECTED_FRAMES) {
            const inputTensor = tf.tensor3d([featureBufferRef.current], [1, WAKE_WORD_EXPECTED_FRAMES, MEYDA_MFCC_COEFFS]);
            try {
                const prediction = tfModel.predict(inputTensor);
                const predictionData = await prediction.data();
                if (predictionData[0] > WAKE_WORD_THRESHOLD) {
                    console.log("Atom detected with confidence:", predictionData[0]);
                    if (meydaRef.current?.isRunning())
                        meydaRef.current.stop();
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
            }
            catch (error) {
                console.error("Error during wake word prediction:", error);
                setWakeWordStatus("Error: Wake word prediction failed.");
                tf.dispose(inputTensor);
            }
        }
    }, [tfModel, isAudioModeEnabled, isSttRecording, startVoiceCapture]);
    const stopWakeWordEngineInternal = (0, react_1.useCallback)(() => {
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
    const initializeWakeWordEngine = (0, react_1.useCallback)(async () => {
        if (!isAudioModeEnabled) {
            console.log("Attempted to init WW engine, but Audio Mode is off.");
            return;
        }
        if (tfModel && meydaRef.current?.isRunning()) {
            console.log("WW engine already initialized and running.");
            return;
        }
        console.log("Initializing Wake Word Engine...");
        setWakeWordStatus("Audio Mode: Initializing engine...");
        let modelError = false, micError = false, audioProcessorError = false;
        try {
            if (!tfModel) {
                try {
                    const loadedModel = await tf.loadGraphModel(WAKE_WORD_MODEL_URL);
                    setTfModel(loadedModel);
                    console.log("Wake word model loaded.");
                }
                catch (e) {
                    modelError = true;
                    throw e;
                }
            }
            let stream;
            try {
                if (!wwAudioContextRef.current || wwAudioContextRef.current.state === 'closed') {
                    wwAudioContextRef.current = new AudioContext();
                    console.log("New AudioContext for WW.");
                }
                // Use wwMicStreamRef for wake word specific stream
                if (!wwMicStreamRef.current || !wwMicStreamRef.current.active) {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    wwMicStreamRef.current = stream;
                    console.log("New media stream for WW.");
                }
                else {
                    stream = wwMicStreamRef.current;
                }
            }
            catch (e) {
                micError = true;
                throw e;
            }
            const context = wwAudioContextRef.current;
            if (!context)
                throw new Error("AudioContext not available for WW.");
            if (!wwMediaStreamSourceRef.current || wwMediaStreamSourceRef.current.context.state === 'closed' || wwMediaStreamSourceRef.current.mediaStream !== stream) {
                wwMediaStreamSourceRef.current = context.createMediaStreamSource(stream);
                console.log("New MediaStreamAudioSourceNode for WW.");
            }
            const source = wwMediaStreamSourceRef.current;
            if (meydaRef.current)
                meydaRef.current.stop();
            try {
                meydaRef.current = new meyda_1.default({
                    audioContext: context, source: source,
                    bufferSize: MEYDA_BUFFER_SIZE, featureExtractors: MEYDA_FEATURE_EXTRACTORS,
                    callback: processFeaturesAndPredict
                });
                meydaRef.current.start();
                console.log("Meyda instance created and started for WW.");
            }
            catch (e) {
                audioProcessorError = true;
                throw e;
            }
            featureBufferRef.current = [];
            setWakeWordStatus("Audio Mode: Listening for 'Atom'...");
        }
        catch (e) {
            console.error("Wake Word Engine Initialization Error:", e.message);
            if (modelError)
                setWakeWordStatus("Error: Wake word model failed to load. Please try again.");
            else if (micError)
                setWakeWordStatus("Error: Microphone access denied for wake word. Please check permissions.");
            else if (audioProcessorError)
                setWakeWordStatus("Error: Audio feature setup failed. Please try again.");
            else
                setWakeWordStatus("Error: Engine init failed.");
            if (isAudioModeEnabled)
                toggleAudioMode();
            else
                stopWakeWordEngineInternal();
        }
    }, [isAudioModeEnabled, toggleAudioMode, tfModel, processFeaturesAndPredict, stopWakeWordEngineInternal]);
    const stopWakeWordEngine = (0, react_1.useCallback)(() => {
        console.log("stopWakeWordEngine called.");
        stopWakeWordEngineInternal();
        setWakeWordStatus("Audio Mode: Disabled.");
        if (isSttRecording && sttMediaRecorderRef.current) {
            console.log("Audio mode disabled/stopped during STT, stopping STT.");
            sttMediaRecorderRef.current.stop();
        }
    }, [isSttRecording, stopWakeWordEngineInternal]);
    const startVoiceCapture = (0, react_1.useCallback)(async (isWakeWordFollowUp = false) => {
        if (isSttRecording) {
            console.log("startVoiceCapture called but already recording STT.");
            return;
        }
        if (isAudioModeEnabled && !isWakeWordFollowUp && meydaRef.current?.isRunning()) {
            console.log("Manually starting STT capture, pausing wake word listening.");
            meydaRef.current.stop();
        }
        setIsSttRecording(true);
        // setSttAudioChunks([]); // This was problematic, sttAudioChunksRef.current is the source of truth
        sttAudioChunksRef.current = [];
        if (isWakeWordFollowUp) {
            setWakeWordStatus("Atom detected! Listening for command...");
        }
        else if (isAudioModeEnabled) {
            setWakeWordStatus("Audio Mode: Listening for your reply/command...");
        }
        else {
            setWakeWordStatus("Listening (STT)...");
        }
        try {
            // Ensure STT uses its own stream, separate from WW stream
            if (sttStreamRef.current)
                sttStreamRef.current.getTracks().forEach(track => track.stop());
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            sttStreamRef.current = stream;
            const recorder = new MediaRecorder(stream);
            sttMediaRecorderRef.current = recorder;
            recordingStartTimeRef.current = Date.now();
            lastSpeechTimeRef.current = Date.now();
            recorder.ondataavailable = (event) => {
                if (event.data.size > 0)
                    sttAudioChunksRef.current.push(event.data);
                if (isAudioModeEnabled && isSttRecording) { // Check isSttRecording as well
                    lastSpeechTimeRef.current = Date.now();
                    if (silenceTimeoutRef.current)
                        clearTimeout(silenceTimeoutRef.current);
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
                if (silenceTimeoutRef.current) {
                    clearTimeout(silenceTimeoutRef.current);
                    silenceTimeoutRef.current = null;
                }
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
                            if (inputRef.current)
                                inputRef.current.focus();
                            setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: Transcription complete. Ready..." : "Transcription complete.");
                        }
                        else if (result.error) {
                            alert(`Transcription Error: ${result.error}`);
                            setWakeWordStatus(isAudioModeEnabled ? "Error: Transcription failed. Try again." : "Transcription Error.");
                        }
                        else {
                            setWakeWordStatus(isAudioModeEnabled ? "Audio Mode: Empty transcription. Ready..." : "Empty transcription.");
                        }
                    }
                    catch (e) {
                        console.error("STT Error:", e);
                        alert(`STT Error: ${e.message}`);
                        setWakeWordStatus(isAudioModeEnabled ? "Error: STT request failed. Try again." : "STT Request Error.");
                    }
                }
                else {
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
                }
                else {
                    setWakeWordStatus("Audio Mode Disabled");
                }
            };
            recorder.start(1000); // Optional: timeslice to get data more frequently if needed
        }
        catch (error) {
            console.error("Error starting STT voice capture:", error);
            alert("Could not access microphone for STT. Please check permissions.");
            setIsSttRecording(false);
            setWakeWordStatus(isAudioModeEnabled ? "Error: Mic access denied for STT." : "Mic Access Denied.");
            if (isAudioModeEnabled) {
                // Consider if toggling audio mode off is the best UX here, or just resetting state.
                // For now, let's just reset status and not toggle mode off automatically on STT mic error.
                initializeWakeWordEngine(); // Try to go back to WW listening if possible
            }
        }
    }, [isAudioModeEnabled, isSttRecording, stopVoiceCapture, setText, /*toggleAudioMode,*/ tfModel, initializeWakeWordEngine]);
    const handleManualSttToggle = () => {
        if (isSttRecording) {
            stopVoiceCapture();
        }
        else {
            // If in audio mode and wake word is listening, stop it first.
            if (isAudioModeEnabled && meydaRef.current?.isRunning()) {
                meydaRef.current.stop();
                // No need to fully cleanup WW engine here, just pause listening.
            }
            startVoiceCapture(false);
        }
    };
    (0, react_1.useEffect)(() => {
        if (isAudioModeEnabled) {
            if (!isSttRecording && !isTranscribing) { // Only init WW if not actively doing STT/transcribing
                initializeWakeWordEngine();
            }
        }
        else {
            stopWakeWordEngine(); // This will also stop STT if it was initiated by WW
        }
        // Explicit cleanup for ww engine when component unmounts or isAudioModeEnabled changes from true to false.
        return () => {
            if (isAudioModeEnabled) { // Only run stopWakeWordEngine if it was enabled
                stopWakeWordEngine();
            }
        };
    }, [isAudioModeEnabled, initializeWakeWordEngine, stopWakeWordEngine, isSttRecording, isTranscribing]);
    (0, react_1.useEffect)(() => {
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
    (0, react_1.useEffect)(() => {
        if (isAudioModeEnabled && !isSttRecording && !isTranscribing && tfModel && !meydaRef.current?.isRunning()) {
            console.log("ChatInput Effect: Conditions met to (re)start wake word listening.");
            initializeWakeWordEngine(); // This will re-check conditions and start Meyda if needed
        }
        else if (meydaRef.current?.isRunning() && (!isAudioModeEnabled || isSttRecording || isTranscribing)) {
            console.log("ChatInput Effect: Conditions met to pause Meyda.");
            meydaRef.current.stop();
            if (!isSttRecording && !isTranscribing && !isAudioModeEnabled) { // If Meyda stopped because audio mode turned off (and not STT)
                setWakeWordStatus("Audio Mode Disabled");
            }
            else if (!isSttRecording && !isTranscribing && isAudioModeEnabled && wakeWordStatus.startsWith("Audio Mode: Listening for 'Atom'...")) {
                // If meyda stopped for other reasons but should be listening
            }
        }
    }, [isAudioModeEnabled, isSttRecording, isTranscribing, tfModel, initializeWakeWordEngine, wakeWordStatus]);
    const sttMicButtonDisabled = isTranscribing || (isAudioModeEnabled && tfModel && meydaRef.current?.isRunning() && !isSttRecording);
    // Simplified: Disable if transcribing. If in audio mode with WW running, it means WW is active, so manual STT should be disabled
    // unless STT is already active (then it's a stop button).
    const onSubmitForm = (e) => {
        e.preventDefault();
        if (text.trim()) {
            sendMessage(text);
            setText('');
            if (inputRef.current) {
                inputRef.current.style.height = 'auto'; // Reset height after send
            }
        }
    };
    // Auto-resize textarea
    (0, react_1.useEffect)(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        }
    }, [text]);
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('fixed w-full md:max-w-2xl bottom-0 left-1/2 -translate-x-1/2 font-sans z-50 px-2 md:px-0 pb-2 md:pb-4'), children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex justify-center items-center mb-2 space-x-2 px-2", children: [(0, jsx_runtime_1.jsxs)(button_1.Button, { size: "sm", variant: isAudioModeEnabled ? "default" : "outline", onClick: toggleAudioMode, className: "rounded-full text-xs" // sm:text-sm removed for consistency
                        , disabled: isTranscribing || (!isAudioModeEnabled && isSttRecording) /* Allow disabling if STT is on but audio mode is off */, children: [isAudioModeEnabled ? (0, jsx_runtime_1.jsx)(icons_1.IconMicOff, { className: "mr-1 h-4 w-4" }) : (0, jsx_runtime_1.jsx)(icons_1.IconMic, { className: "mr-1 h-4 w-4" }), isAudioModeEnabled ? "Disable Audio Mode" : "Enable Audio Mode"] }), (0, jsx_runtime_1.jsx)("span", { className: "text-xs text-gray-500 dark:text-gray-400 truncate flex-1 text-center", children: isTranscribing ? "Transcribing..." : wakeWordStatus })] }), (0, jsx_runtime_1.jsx)("form", { onSubmit: onSubmitForm, ref: formRef, className: (0, utils_1.cn)('space-y-0 border-t px-3 py-3 shadow-xl sm:rounded-xl sm:border md:py-3', 'bg-white dark:bg-gray-800 dark:border-gray-700', { 'opacity-60 pointer-events-none': isNewSession }), children: (0, jsx_runtime_1.jsxs)("div", { className: "relative flex w-full grow flex-col overflow-hidden items-center", children: [" ", (0, jsx_runtime_1.jsx)(tooltip_1.TooltipProvider, { delayDuration: 300, children: (0, jsx_runtime_1.jsxs)(tooltip_1.Tooltip, { children: [(0, jsx_runtime_1.jsx)(tooltip_1.TooltipTrigger, { asChild: true, children: (0, jsx_runtime_1.jsxs)(button_1.Button, { variant: "ghost" // Changed to ghost for a cleaner look
                                            , size: "icon", type: "button", disabled: isNewSession, onClick: e => {
                                                e.preventDefault();
                                                callNewSession();
                                            }, className: (0, utils_1.cn)(
                                            // 'absolute left-1 top-1/2 -translate-y-1/2 h-8 w-8 rounded-full p-0' // Original positioning
                                            'shrink-0 mr-2 self-center text-gray-500 hover:text-sky-600 dark:text-gray-400 dark:hover:text-sky-500'), children: [(0, jsx_runtime_1.jsx)(icons_1.IconPlus, { className: "h-5 w-5" }), (0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: "New Chat" })] }) }), (0, jsx_runtime_1.jsx)(tooltip_1.TooltipContent, { side: "top", children: "New Chat" })] }) }), (0, jsx_runtime_1.jsx)(textarea_1.Textarea, { id: "chat-input", ref: inputRef, tabIndex: 0, onKeyDown: onKeyDown, spellCheck: false, rows: 1, className: (0, utils_1.cn)("flex-1 min-h-[44px] max-h-[150px] w-full rounded-lg resize-none py-2.5 pl-3 pr-20 sm:text-sm", // Adjusted padding and height
                            "border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700", "focus:ring-0 focus:ring-offset-0 focus:border-sky-500 dark:focus:border-sky-500" // Simplified focus
                            ), placeholder: "Your message...", value: text, onChange: onChangeText }), (0, jsx_runtime_1.jsxs)("div", { className: "absolute right-2 top-1/2 -translate-y-1/2 flex items-center space-x-1", children: [(0, jsx_runtime_1.jsx)(tooltip_1.TooltipProvider, { delayDuration: 300, children: (0, jsx_runtime_1.jsxs)(tooltip_1.Tooltip, { children: [(0, jsx_runtime_1.jsx)(tooltip_1.TooltipTrigger, { asChild: true, children: (0, jsx_runtime_1.jsxs)(button_1.Button, { type: "button", size: "icon", variant: isSttRecording ? "destructive" : "ghost", onClick: handleManualSttToggle, className: "h-8 w-8 rounded-full p-0 text-gray-500 hover:text-sky-600 dark:text-gray-400 dark:hover:text-sky-500", disabled: sttMicButtonDisabled, children: [isSttRecording ? (0, jsx_runtime_1.jsx)(icons_1.IconMicOff, { className: "h-5 w-5" }) : (0, jsx_runtime_1.jsx)(icons_1.IconMic, { className: "h-5 w-5" }), (0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: isSttRecording ? "Stop recording" : "Start recording" })] }) }), (0, jsx_runtime_1.jsx)(tooltip_1.TooltipContent, { side: "top", children: isTranscribing ? "Transcribing..." : (isSttRecording ? "Stop recording" : "Start recording") })] }) }), (0, jsx_runtime_1.jsx)(tooltip_1.TooltipProvider, { delayDuration: 300, children: (0, jsx_runtime_1.jsxs)(tooltip_1.Tooltip, { children: [(0, jsx_runtime_1.jsx)(tooltip_1.TooltipTrigger, { asChild: true, children: (0, jsx_runtime_1.jsxs)(button_1.Button, { size: "icon", disabled: isNewSession || !text.trim(), type: "submit", className: (0, utils_1.cn)("h-8 w-8 rounded-full p-0 bg-sky-600 hover:bg-sky-700 text-white dark:bg-sky-500 dark:hover:bg-sky-600", { "opacity-50 cursor-not-allowed": isNewSession || !text.trim() }), children: [(0, jsx_runtime_1.jsx)(icons_1.IconArrowElbow, { className: "h-5 w-5" }), (0, jsx_runtime_1.jsx)("span", { className: "sr-only", children: "Send message" })] }) }), (0, jsx_runtime_1.jsx)(tooltip_1.TooltipContent, { side: "top", children: "Send message" })] }) })] })] }) })] }));
};
exports.default = ChatInput;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2hhdElucHV0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiQ2hhdElucHV0LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUFBQSw0Q0FBNEM7QUFDNUMsaUNBQXdFO0FBQ3hFLHFEQUF1QztBQUN2QyxrREFBMEI7QUFDMUIsc0RBQXNEO0FBQ3RELDJEQUFxRDtBQUNyRCx5REFBdUc7QUFDdkcsMkNBQXFDO0FBQ3JDLHVEQUFvRTtBQUNwRSxxREFBMEY7QUFDMUYsdUVBQWlFO0FBQ2pFLHFFQUE4RDtBQVE5RCxNQUFNLG1CQUFtQixHQUFHLG1DQUFtQyxDQUFDO0FBQ2hFLE1BQU0sbUJBQW1CLEdBQUcsR0FBRyxDQUFDO0FBQ2hDLE1BQU0sb0JBQW9CLEdBQUcsSUFBSSxDQUFDO0FBQ2xDLE1BQU0seUJBQXlCLEdBQUcsR0FBRyxDQUFDO0FBQ3RDLE1BQU0saUJBQWlCLEdBQUcsR0FBRyxDQUFDO0FBQzlCLE1BQU0sd0JBQXdCLEdBQUcsQ0FBQyxNQUFNLENBQUMsQ0FBQztBQUMxQyxNQUFNLGlCQUFpQixHQUFHLEVBQUUsQ0FBQztBQUM3QixNQUFNLHlCQUF5QixHQUFHLEVBQUUsQ0FBQztBQUVyQyxNQUFNLFNBQVMsR0FBRyxDQUFDLEVBQUUsV0FBVyxFQUFFLFlBQVksRUFBRSxjQUFjLEVBQVMsRUFBRSxFQUFFO0lBQ3ZFLE1BQU0sQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFTLEVBQUUsQ0FBQyxDQUFDO0lBQzdDLE1BQU0sRUFBRSxPQUFPLEVBQUUsU0FBUyxFQUFFLEdBQUcsSUFBQSxpQ0FBYyxHQUFFLENBQUM7SUFDaEQsTUFBTSxRQUFRLEdBQUcsSUFBQSxjQUFNLEVBQXNCLElBQUksQ0FBQyxDQUFDO0lBRW5ELHFCQUFxQjtJQUNyQixNQUFNLENBQUMsY0FBYyxFQUFFLGlCQUFpQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFV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bGYtY2xvc2luZy1jb21wICovXG5pbXBvcnQgUmVhY3QsIHsgdXNlU3RhdGUsIHVzZVJlZiwgdXNlRWZmZWN0LCB1c2VDYWxsYmFjayB9IGZyb20gXCJyZWFjdFwiO1xuaW1wb3J0ICogYXMgdGYgZnJvbSAnQHRlbnNvcmZsb3cvdGZqcyc7XG5pbXBvcnQgTWV5ZGEgZnJvbSAnbWV5ZGEnO1xuLy8gaW1wb3J0IGNscyBmcm9tICdjbGFzc25hbWVzJyAvLyBjbiBpcyBwcmVmZXJyZWQgbm93XG5pbXBvcnQge1RleHRhcmVhfSBmcm9tICdAY29tcG9uZW50cy9jaGF0L3VpL3RleHRhcmVhJ1xuaW1wb3J0IHsgVG9vbHRpcCwgVG9vbHRpcENvbnRlbnQsIFRvb2x0aXBQcm92aWRlciwgVG9vbHRpcFRyaWdnZXIgfSBmcm9tIFwiQGNvbXBvbmVudHMvY2hhdC91aS90b29sdGlwXCI7XG5pbXBvcnQgeyBjbiB9IGZyb20gXCJAbGliL0NoYXQvdXRpbHNcIjtcbmltcG9ydCB7IGJ1dHRvblZhcmlhbnRzLCBCdXR0b24gfSBmcm9tIFwiQGNvbXBvbmVudHMvY2hhdC91aS9idXR0b25cIjtcbmltcG9ydCB7IEljb25QbHVzLCBJY29uQXJyb3dFbGJvdywgSWNvbk1pYywgSWNvbk1pY09mZiB9IGZyb20gJ0Bjb21wb25lbnRzL2NoYXQvdWkvaWNvbnMnO1xuaW1wb3J0IHsgdXNlRW50ZXJTdWJtaXQgfSBmcm9tICdAbGliL0NoYXQvaG9va3MvdXNlLWVudGVyLXN1Ym1pdCdcbmltcG9ydCB7IHVzZUF1ZGlvTW9kZSB9IGZyb20gJ0BsaWIvY29udGV4dHMvQXVkaW9Nb2RlQ29udGV4dCc7XG5cbnR5cGUgUHJvcHMgPSB7XG4gICAgc2VuZE1lc3NhZ2U6ICh0ZXh0OiBzdHJpbmcpID0+IHZvaWQsXG4gICAgaXNOZXdTZXNzaW9uOiBib29sZWFuLFxuICAgIGNhbGxOZXdTZXNzaW9uOiAoKSA9PiB2b2lkXG59XG5cbmNvbnN0IFdBS0VfV09SRF9NT0RFTF9VUkwgPSAnL21vZGVscy9hdG9tX3dha2Vfd29yZC9tb2RlbC5qc29uJztcbmNvbnN0IFdBS0VfV09SRF9USFJFU0hPTEQgPSAwLjc7XG5jb25zdCBTSUxFTkNFX1RIUkVTSE9MRF9NUyA9IDIwMDA7XG5jb25zdCBNSU5fUkVDT1JESU5HX0RVUkFUSU9OX01TID0gNTAwO1xuY29uc3QgTUVZREFfQlVGRkVSX1NJWkUgPSA1MTI7XG5jb25zdCBNRVlEQV9GRUFUVVJFX0VYVFJBQ1RPUlMgPSBbXCJtZmNjXCJdO1xuY29uc3QgTUVZREFfTUZDQ19DT0VGRlMgPSAxMztcbmNvbnN0IFdBS0VfV09SRF9FWFBFQ1RFRF9GUkFNRVMgPSA0MztcblxuY29uc3QgQ2hhdElucHV0ID0gKHsgc2VuZE1lc3NhZ2UsIGlzTmV3U2Vzc2lvbiwgY2FsbE5ld1Nlc3Npb24gfTogUHJvcHMpID0+IHtcbiAgICBjb25zdCBbdGV4dCwgc2V0VGV4dF0gPSB1c2VTdGF0ZTxzdHJpbmc+KCcnKTtcbiAgICBjb25zdCB7IGZvcm1SZWYsIG9uS2V5RG93biB9ID0gdXNlRW50ZXJTdWJtaXQoKTtcbiAgICBjb25zdCBpbnB1dFJlZiA9IHVzZVJlZjxIVE1MVGV4dEFyZWFFbGVtZW50PihudWxsKTtcblxuICAgIC8vIC0tLSBTVFQgU3RhdGVzIC0tLVxuICAgIGNvbnN0IFtpc1N0dFJlY29yZGluZywgc2V0SXNTdHRSZWNvcmRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpO1xuICAgIGNvbnN0IHN0dE1lZGlhUmVjb3JkZXJSZWYgPSB1c2VSZWY8TWVkaWFSZWNvcmRlciB8IG51bGw+KG51bGwpO1xuICAgIGNvbnN0IHN0dEF1ZGlvQ2h1bmtzUmVmID0gdXNlUmVmPEJsb2JbXT4oW10pO1xuICAgIGNvbnN0IFtpc1RyYW5zY3JpYmluZywgc2V0SXNUcmFuc2NyaWJpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpO1xuICAgIGNvbnN0IHN0dFN0cmVhbVJlZiA9IHVzZVJlZjxNZWRpYVN0cmVhbSB8IG51bGw+KG51bGwpO1xuXG4gICAgLy8gLS0tIEF1ZGlvIE1vZGUgJiBXYWtlIFdvcmQgU3RhdGVzIC0tLVxuICAgIGNvbnN0IHsgaXNBdWRpb01vZGVFbmFibGVkLCB0b2dnbGVBdWRpb01vZGUsIHJlcGx5UmVxdWVzdENvdW50IH0gPSB1c2VBdWRpb01vZGUoKTtcbiAgICBjb25zdCBbd2FrZVdvcmRTdGF0dXMsIHNldFdha2VXb3JkU3RhdHVzXSA9IHVzZVN0YXRlPHN0cmluZz4oXCJBdWRpbyBNb2RlIERpc2FibGVkXCIpO1xuICAgIGNvbnN0IFt0Zk1vZGVsLCBzZXRUZk1vZGVsXSA9IHVzZVN0YXRlPHRmLkdyYXBoTW9kZWwgfCB0Zi5MYXllcnNNb2RlbCB8IG51bGw+KG51bGwpO1xuXG4gICAgY29uc3Qgd3dBdWRpb0NvbnRleHRSZWYgPSB1c2VSZWY8QXVkaW9Db250ZXh0IHwgbnVsbD4obnVsbCk7IC8vIERlZGljYXRlZCBmb3IgV2FrZSBXb3JkXG4gICAgY29uc3Qgd3dNaWNTdHJlYW1SZWYgPSB1c2VSZWY8TWVkaWFTdHJlYW0gfCBudWxsPihudWxsKTtcbiAgICBjb25zdCB3d01lZGlhU3RyZWFtU291cmNlUmVmID0gdXNlUmVmPE1lZGlhU3RyZWFtQXVkaW9Tb3VyY2VOb2RlIHwgbnVsbD4obnVsbCk7XG4gICAgY29uc3QgbWV5ZGFSZWYgPSB1c2VSZWY8TWV5ZGEgfCBudWxsPihudWxsKTtcbiAgICBjb25zdCBmZWF0dXJlQnVmZmVyUmVmID0gdXNlUmVmPG51bWJlcltdW10+KFtdKTtcblxuICAgIGNvbnN0IHJlY29yZGluZ1N0YXJ0VGltZVJlZiA9IHVzZVJlZjxudW1iZXI+KDApO1xuICAgIGNvbnN0IGxhc3RTcGVlY2hUaW1lUmVmID0gdXNlUmVmPG51bWJlcj4oMCk7XG4gICAgY29uc3Qgc2lsZW5jZVRpbWVvdXRSZWYgPSB1c2VSZWY8Tm9kZUpTLlRpbWVvdXQgfCBudWxsPihudWxsKTtcblxuICAgIHVzZUVmZmVjdCgoKSA9PiB7IGlmIChpbnB1dFJlZi5jdXJyZW50KSBpbnB1dFJlZi5jdXJyZW50LmZvY3VzKCkgfSwgW10pO1xuXG4gICAgdXNlRWZmZWN0KCgpID0+IHsgLy8gQ2xlYW51cCBTVFQgcmVzb3VyY2VzXG4gICAgICAgIHJldHVybiAoKSA9PiB7XG4gICAgICAgICAgICBzdHRTdHJlYW1SZWYuY3VycmVudD8uZ2V0VHJhY2tzKCkuZm9yRWFjaCh0cmFjayA9PiB0cmFjay5zdG9wKCkpO1xuICAgICAgICAgICAgaWYgKHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudD8uc3RhdGUgPT09IFwicmVjb3JkaW5nXCIpIHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudC5zdG9wKCk7XG4gICAgICAgIH07XG4gICAgfSwgW10pO1xuXG4gICAgY29uc3Qgb25DaGFuZ2VUZXh0ID0gKGU6IHsgY3VycmVudFRhcmdldDogeyB2YWx1ZTogUmVhY3QuU2V0U3RhdGVBY3Rpb248c3RyaW5nPjsgfTsgfSkgPT4gc2V0VGV4dChlLmN1cnJlbnRUYXJnZXQudmFsdWUpO1xuXG4gICAgY29uc3Qgc3RvcFZvaWNlQ2FwdHVyZSA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coXCJzdG9wVm9pY2VDYXB0dXJlIGNhbGxlZC4gU1RUIE1lZGlhUmVjb3JkZXIgc3RhdGU6XCIsIHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudD8uc3RhdGUpO1xuICAgICAgICBpZiAoc3R0TWVkaWFSZWNvcmRlclJlZi5jdXJyZW50ICYmIHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudC5zdGF0ZSA9PT0gXCJyZWNvcmRpbmdcIikge1xuICAgICAgICAgICAgc3R0TWVkaWFSZWNvcmRlclJlZi5jdXJyZW50LnN0b3AoKTtcbiAgICAgICAgfVxuICAgICAgICBpZiAoc2lsZW5jZVRpbWVvdXRSZWYuY3VycmVudCkge1xuICAgICAgICAgICAgY2xlYXJUaW1lb3V0KHNpbGVuY2VUaW1lb3V0UmVmLmN1cnJlbnQpO1xuICAgICAgICAgICAgc2lsZW5jZVRpbWVvdXRSZWYuY3VycmVudCA9IG51bGw7XG4gICAgICAgIH1cbiAgICAgICAgaWYgKHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudD8uc3RhdGUgIT09IFwicmVjb3JkaW5nXCIgJiYgaXNTdHRSZWNvcmRpbmcpIHtcbiAgICAgICAgICAgICBzZXRJc1N0dFJlY29yZGluZyhmYWxzZSk7XG4gICAgICAgIH1cbiAgICB9LCBbaXNTdHRSZWNvcmRpbmddKTtcblxuICAgIGNvbnN0IHByb2Nlc3NGZWF0dXJlc0FuZFByZWRpY3QgPSB1c2VDYWxsYmFjayhhc3luYyAoZmVhdHVyZXM6IGFueSkgPT4ge1xuICAgICAgICBpZiAoIXRmTW9kZWwgfHwgIWlzQXVkaW9Nb2RlRW5hYmxlZCB8fCBpc1N0dFJlY29yZGluZyB8fCAhbWV5ZGFSZWYuY3VycmVudD8uaXNSdW5uaW5nKCkgfHwgIWZlYXR1cmVzLm1mY2MgfHwgZmVhdHVyZXMubWZjYy5sZW5ndGggIT09IE1FWURBX01GQ0NfQ09FRkZTKSB7XG4gICAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cbiAgICAgICAgZmVhdHVyZUJ1ZmZlclJlZi5jdXJyZW50LnB1c2goZmVhdHVyZXMubWZjYyk7XG4gICAgICAgIGlmIChmZWF0dXJlQnVmZmVyUmVmLmN1cnJlbnQubGVuZ3RoID4gV0FLRV9XT1JEX0VYUEVDVEVEX0ZSQU1FUykgZmVhdHVyZUJ1ZmZlclJlZi5jdXJyZW50LnNoaWZ0KCk7XG5cbiAgICAgICAgaWYgKGZlYXR1cmVCdWZmZXJSZWYuY3VycmVudC5sZW5ndGggPT09IFdBS0VfV09SRF9FWFBFQ1RFRF9GUkFNRVMpIHtcbiAgICAgICAgICAgIGNvbnN0IGlucHV0VGVuc29yID0gdGYudGVuc29yM2QoW2ZlYXR1cmVCdWZmZXJSZWYuY3VycmVudF0sIFsxLCBXQUtFX1dPUkRfRVhQRUNURURfRlJBTUVTLCBNRVlEQV9NRkNDX0NPRUZGU10pO1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBjb25zdCBwcmVkaWN0aW9uID0gdGZNb2RlbC5wcmVkaWN0KGlucHV0VGVuc29yKSBhcyB0Zi5UZW5zb3I7XG4gICAgICAgICAgICAgICAgY29uc3QgcHJlZGljdGlvbkRhdGEgPSBhd2FpdCBwcmVkaWN0aW9uLmRhdGEoKSBhcyBGbG9hdDMyQXJyYXk7XG4gICAgICAgICAgICAgICAgaWYgKHByZWRpY3Rpb25EYXRhWzBdID4gV0FLRV9XT1JEX1RIUkVTSE9MRCkge1xuICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhcIkF0b20gZGV0ZWN0ZWQgd2l0aCBjb25maWRlbmNlOlwiLCBwcmVkaWN0aW9uRGF0YVswXSk7XG4gICAgICAgICAgICAgICAgICAgIGlmKG1leWRhUmVmLmN1cnJlbnQ/LmlzUnVubmluZygpKSBtZXlkYVJlZi5jdXJyZW50LnN0b3AoKTtcblxuICAgICAgICAgICAgICAgICAgICB3d01pY1N0cmVhbVJlZi5jdXJyZW50Py5nZXRUcmFja3MoKS5mb3JFYWNoKHRyYWNrID0+IHRyYWNrLnN0b3AoKSk7XG4gICAgICAgICAgICAgICAgICAgIHd3TWljU3RyZWFtUmVmLmN1cnJlbnQgPSBudWxsO1xuICAgICAgICAgICAgICAgICAgICBpZiAod3dBdWRpb0NvbnRleHRSZWYuY3VycmVudCAmJiB3d0F1ZGlvQ29udGV4dFJlZi5jdXJyZW50LnN0YXRlICE9PSAnY2xvc2VkJykge1xuICAgICAgICAgICAgICAgICAgICAgICBhd2FpdCB3d0F1ZGlvQ29udGV4dFJlZi5jdXJyZW50LmNsb3NlKCk7XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgd3dBdWRpb0NvbnRleHRSZWYuY3VycmVudCA9IG51bGw7XG4gICAgICAgICAgICAgICAgICAgIHd3TWVkaWFTdHJlYW1Tb3VyY2VSZWYuY3VycmVudCA9IG51bGw7XG5cbiAgICAgICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJBdG9tIGRldGVjdGVkISBMaXN0ZW5pbmcgZm9yIGNvbW1hbmQuLi5cIik7XG4gICAgICAgICAgICAgICAgICAgIGF3YWl0IHN0YXJ0Vm9pY2VDYXB0dXJlKHRydWUpO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB0Zi5kaXNwb3NlKFtpbnB1dFRlbnNvciwgcHJlZGljdGlvbl0pO1xuICAgICAgICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmVycm9yKFwiRXJyb3IgZHVyaW5nIHdha2Ugd29yZCBwcmVkaWN0aW9uOlwiLCBlcnJvcik7XG4gICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJFcnJvcjogV2FrZSB3b3JkIHByZWRpY3Rpb24gZmFpbGVkLlwiKTtcbiAgICAgICAgICAgICAgICB0Zi5kaXNwb3NlKGlucHV0VGVuc29yKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH0sIFt0Zk1vZGVsLCBpc0F1ZGlvTW9kZUVuYWJsZWQsIGlzU3R0UmVjb3JkaW5nLCBzdGFydFZvaWNlQ2FwdHVyZV0pO1xuXG4gICAgY29uc3Qgc3RvcFdha2VXb3JkRW5naW5lSW50ZXJuYWwgPSB1c2VDYWxsYmFjaygoKSA9PiB7XG4gICAgICAgIGNvbnNvbGUubG9nKFwic3RvcFdha2VXb3JkRW5naW5lSW50ZXJuYWw6IENsZWFuaW5nIHVwIHdha2Ugd29yZCByZXNvdXJjZXMuXCIpO1xuICAgICAgICBtZXlkYVJlZi5jdXJyZW50Py5zdG9wKCk7XG4gICAgICAgIC8vIG1pY1N0cmVhbVJlZiBpcyB3d01pY1N0cmVhbVJlZiBpbiB0aGlzIGNvbnRleHRcbiAgICAgICAgd3dNaWNTdHJlYW1SZWYuY3VycmVudD8uZ2V0VHJhY2tzKCkuZm9yRWFjaCh0cmFjayA9PiB0cmFjay5zdG9wKCkpO1xuICAgICAgICB3d01pY1N0cmVhbVJlZi5jdXJyZW50ID0gbnVsbDtcbiAgICAgICAgaWYgKHd3QXVkaW9Db250ZXh0UmVmLmN1cnJlbnQgJiYgd3dBdWRpb0NvbnRleHRSZWYuY3VycmVudC5zdGF0ZSAhPT0gJ2Nsb3NlZCcpIHtcbiAgICAgICAgICAgIHd3QXVkaW9Db250ZXh0UmVmLmN1cnJlbnQuY2xvc2UoKS5jYXRjaChlID0+IGNvbnNvbGUuZXJyb3IoXCJFcnJvciBjbG9zaW5nIFdXIEF1ZGlvQ29udGV4dDpcIiwgZSkpO1xuICAgICAgICB9XG4gICAgICAgIHd3QXVkaW9Db250ZXh0UmVmLmN1cnJlbnQgPSBudWxsO1xuICAgICAgICB0Zk1vZGVsPy5kaXNwb3NlKCk7XG4gICAgICAgIHNldFRmTW9kZWwobnVsbCk7XG4gICAgICAgIG1leWRhUmVmLmN1cnJlbnQgPSBudWxsO1xuICAgICAgICB3d01lZGlhU3RyZWFtU291cmNlUmVmLmN1cnJlbnQgPSBudWxsO1xuICAgICAgICBmZWF0dXJlQnVmZmVyUmVmLmN1cnJlbnQgPSBbXTtcbiAgICB9LCBbdGZNb2RlbF0pO1xuXG4gICAgY29uc3QgaW5pdGlhbGl6ZVdha2VXb3JkRW5naW5lID0gdXNlQ2FsbGJhY2soYXN5bmMgKCkgPT4ge1xuICAgICAgICBpZiAoIWlzQXVkaW9Nb2RlRW5hYmxlZCkgeyBjb25zb2xlLmxvZyhcIkF0dGVtcHRlZCB0byBpbml0IFdXIGVuZ2luZSwgYnV0IEF1ZGlvIE1vZGUgaXMgb2ZmLlwiKTsgcmV0dXJuOyB9XG4gICAgICAgIGlmICh0Zk1vZGVsICYmIG1leWRhUmVmLmN1cnJlbnQ/LmlzUnVubmluZygpKSB7IGNvbnNvbGUubG9nKFwiV1cgZW5naW5lIGFscmVhZHkgaW5pdGlhbGl6ZWQgYW5kIHJ1bm5pbmcuXCIpOyByZXR1cm47IH1cblxuICAgICAgICBjb25zb2xlLmxvZyhcIkluaXRpYWxpemluZyBXYWtlIFdvcmQgRW5naW5lLi4uXCIpO1xuICAgICAgICBzZXRXYWtlV29yZFN0YXR1cyhcIkF1ZGlvIE1vZGU6IEluaXRpYWxpemluZyBlbmdpbmUuLi5cIik7XG4gICAgICAgIGxldCBtb2RlbEVycm9yID0gZmFsc2UsIG1pY0Vycm9yID0gZmFsc2UsIGF1ZGlvUHJvY2Vzc29yRXJyb3IgPSBmYWxzZTtcblxuICAgICAgICB0cnkge1xuICAgICAgICAgICAgaWYgKCF0Zk1vZGVsKSB7XG4gICAgICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgbG9hZGVkTW9kZWwgPSBhd2FpdCB0Zi5sb2FkR3JhcGhNb2RlbChXQUtFX1dPUkRfTU9ERUxfVVJMKTtcbiAgICAgICAgICAgICAgICAgICAgc2V0VGZNb2RlbChsb2FkZWRNb2RlbCk7IGNvbnNvbGUubG9nKFwiV2FrZSB3b3JkIG1vZGVsIGxvYWRlZC5cIik7XG4gICAgICAgICAgICAgICAgfSBjYXRjaCAoZSkgeyBtb2RlbEVycm9yID0gdHJ1ZTsgdGhyb3cgZTsgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgbGV0IHN0cmVhbTtcbiAgICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICAgICAgaWYgKCF3d0F1ZGlvQ29udGV4dFJlZi5jdXJyZW50IHx8IHd3QXVkaW9Db250ZXh0UmVmLmN1cnJlbnQuc3RhdGUgPT09ICdjbG9zZWQnKSB7XG4gICAgICAgICAgICAgICAgICAgIHd3QXVkaW9Db250ZXh0UmVmLmN1cnJlbnQgPSBuZXcgQXVkaW9Db250ZXh0KCk7IGNvbnNvbGUubG9nKFwiTmV3IEF1ZGlvQ29udGV4dCBmb3IgV1cuXCIpO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgLy8gVXNlIHd3TWljU3RyZWFtUmVmIGZvciB3YWtlIHdvcmQgc3BlY2lmaWMgc3RyZWFtXG4gICAgICAgICAgICAgICAgaWYgKCF3d01pY1N0cmVhbVJlZi5jdXJyZW50IHx8ICF3d01pY1N0cmVhbVJlZi5jdXJyZW50LmFjdGl2ZSkge1xuICAgICAgICAgICAgICAgICAgICBzdHJlYW0gPSBhd2FpdCBuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSh7IGF1ZGlvOiB0cnVlIH0pO1xuICAgICAgICAgICAgICAgICAgICB3d01pY1N0cmVhbVJlZi5jdXJyZW50ID0gc3RyZWFtOyBjb25zb2xlLmxvZyhcIk5ldyBtZWRpYSBzdHJlYW0gZm9yIFdXLlwiKTtcbiAgICAgICAgICAgICAgICB9IGVsc2UgeyBzdHJlYW0gPSB3d01pY1N0cmVhbVJlZi5jdXJyZW50OyB9XG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7IG1pY0Vycm9yID0gdHJ1ZTsgdGhyb3cgZTsgfVxuXG4gICAgICAgICAgICBjb25zdCBjb250ZXh0ID0gd3dBdWRpb0NvbnRleHRSZWYuY3VycmVudDtcbiAgICAgICAgICAgIGlmICghY29udGV4dCkgdGhyb3cgbmV3IEVycm9yKFwiQXVkaW9Db250ZXh0IG5vdCBhdmFpbGFibGUgZm9yIFdXLlwiKTtcblxuICAgICAgICAgICAgaWYgKCF3d01lZGlhU3RyZWFtU291cmNlUmVmLmN1cnJlbnQgfHwgd3dNZWRpYVN0cmVhbVNvdXJjZVJlZi5jdXJyZW50LmNvbnRleHQuc3RhdGUgPT09ICdjbG9zZWQnIHx8IHd3TWVkaWFTdHJlYW1Tb3VyY2VSZWYuY3VycmVudC5tZWRpYVN0cmVhbSAhPT0gc3RyZWFtICkge1xuICAgICAgICAgICAgICAgICB3d01lZGlhU3RyZWFtU291cmNlUmVmLmN1cnJlbnQgPSBjb250ZXh0LmNyZWF0ZU1lZGlhU3RyZWFtU291cmNlKHN0cmVhbSk7IGNvbnNvbGUubG9nKFwiTmV3IE1lZGlhU3RyZWFtQXVkaW9Tb3VyY2VOb2RlIGZvciBXVy5cIik7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBjb25zdCBzb3VyY2UgPSB3d01lZGlhU3RyZWFtU291cmNlUmVmLmN1cnJlbnQ7XG5cbiAgICAgICAgICAgIGlmIChtZXlkYVJlZi5jdXJyZW50KSBtZXlkYVJlZi5jdXJyZW50LnN0b3AoKTtcbiAgICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICAgICAgbWV5ZGFSZWYuY3VycmVudCA9IG5ldyBNZXlkYSh7XG4gICAgICAgICAgICAgICAgICAgIGF1ZGlvQ29udGV4dDogY29udGV4dCwgc291cmNlOiBzb3VyY2UsXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclNpemU6IE1FWURBX0JVRkZFUl9TSVpFLCBmZWF0dXJlRXh0cmFjdG9yczogTUVZREFfRkVBVFVSRV9FWFRSQUNUT1JTLFxuICAgICAgICAgICAgICAgICAgICBjYWxsYmFjazogcHJvY2Vzc0ZlYXR1cmVzQW5kUHJlZGljdFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgIG1leWRhUmVmLmN1cnJlbnQuc3RhcnQoKTsgY29uc29sZS5sb2coXCJNZXlkYSBpbnN0YW5jZSBjcmVhdGVkIGFuZCBzdGFydGVkIGZvciBXVy5cIik7XG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7IGF1ZGlvUHJvY2Vzc29yRXJyb3IgPSB0cnVlOyB0aHJvdyBlOyB9XG5cbiAgICAgICAgICAgIGZlYXR1cmVCdWZmZXJSZWYuY3VycmVudCA9IFtdO1xuICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJBdWRpbyBNb2RlOiBMaXN0ZW5pbmcgZm9yICdBdG9tJy4uLlwiKTtcbiAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgICBjb25zb2xlLmVycm9yKFwiV2FrZSBXb3JkIEVuZ2luZSBJbml0aWFsaXphdGlvbiBFcnJvcjpcIiwgZS5tZXNzYWdlKTtcbiAgICAgICAgICAgIGlmIChtb2RlbEVycm9yKSBzZXRXYWtlV29yZFN0YXR1cyhcIkVycm9yOiBXYWtlIHdvcmQgbW9kZWwgZmFpbGVkIHRvIGxvYWQuIFBsZWFzZSB0cnkgYWdhaW4uXCIpO1xuICAgICAgICAgICAgZWxzZSBpZiAobWljRXJyb3IpIHNldFdha2VXb3JkU3RhdHVzKFwiRXJyb3I6IE1pY3JvcGhvbmUgYWNjZXNzIGRlbmllZCBmb3Igd2FrZSB3b3JkLiBQbGVhc2UgY2hlY2sgcGVybWlzc2lvbnMuXCIpO1xuICAgICAgICAgICAgZWxzZSBpZiAoYXVkaW9Qcm9jZXNzb3JFcnJvcikgc2V0V2FrZVdvcmRTdGF0dXMoXCJFcnJvcjogQXVkaW8gZmVhdHVyZSBzZXR1cCBmYWlsZWQuIFBsZWFzZSB0cnkgYWdhaW4uXCIpO1xuICAgICAgICAgICAgZWxzZSBzZXRXYWtlV29yZFN0YXR1cyhcIkVycm9yOiBFbmdpbmUgaW5pdCBmYWlsZWQuXCIpO1xuXG4gICAgICAgICAgICBpZiAoaXNBdWRpb01vZGVFbmFibGVkKSB0b2dnbGVBdWRpb01vZGUoKTtcbiAgICAgICAgICAgIGVsc2Ugc3RvcFdha2VXb3JkRW5naW5lSW50ZXJuYWwoKTtcbiAgICAgICAgfVxuICAgIH0sIFtpc0F1ZGlvTW9kZUVuYWJsZWQsIHRvZ2dsZUF1ZGlvTW9kZSwgdGZNb2RlbCwgcHJvY2Vzc0ZlYXR1cmVzQW5kUHJlZGljdCwgc3RvcFdha2VXb3JkRW5naW5lSW50ZXJuYWxdKTtcblxuICAgIGNvbnN0IHN0b3BXYWtlV29yZEVuZ2luZSA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coXCJzdG9wV2FrZVdvcmRFbmdpbmUgY2FsbGVkLlwiKTtcbiAgICAgICAgc3RvcFdha2VXb3JkRW5naW5lSW50ZXJuYWwoKTtcbiAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJBdWRpbyBNb2RlOiBEaXNhYmxlZC5cIik7XG4gICAgICAgIGlmIChpc1N0dFJlY29yZGluZyAmJiBzdHRNZWRpYVJlY29yZGVyUmVmLmN1cnJlbnQpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiQXVkaW8gbW9kZSBkaXNhYmxlZC9zdG9wcGVkIGR1cmluZyBTVFQsIHN0b3BwaW5nIFNUVC5cIik7XG4gICAgICAgICAgICBzdHRNZWRpYVJlY29yZGVyUmVmLmN1cnJlbnQuc3RvcCgpO1xuICAgICAgICB9XG4gICAgfSwgW2lzU3R0UmVjb3JkaW5nLCBzdG9wV2FrZVdvcmRFbmdpbmVJbnRlcm5hbF0pO1xuXG4gICAgY29uc3Qgc3RhcnRWb2ljZUNhcHR1cmUgPSB1c2VDYWxsYmFjayhhc3luYyAoaXNXYWtlV29yZEZvbGxvd1VwOiBib29sZWFuID0gZmFsc2UpID0+IHtcbiAgICAgICAgaWYgKGlzU3R0UmVjb3JkaW5nKSB7IGNvbnNvbGUubG9nKFwic3RhcnRWb2ljZUNhcHR1cmUgY2FsbGVkIGJ1dCBhbHJlYWR5IHJlY29yZGluZyBTVFQuXCIpOyByZXR1cm47IH1cblxuICAgICAgICBpZiAoaXNBdWRpb01vZGVFbmFibGVkICYmICFpc1dha2VXb3JkRm9sbG93VXAgJiYgbWV5ZGFSZWYuY3VycmVudD8uaXNSdW5uaW5nKCkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiTWFudWFsbHkgc3RhcnRpbmcgU1RUIGNhcHR1cmUsIHBhdXNpbmcgd2FrZSB3b3JkIGxpc3RlbmluZy5cIik7XG4gICAgICAgICAgICBtZXlkYVJlZi5jdXJyZW50LnN0b3AoKTtcbiAgICAgICAgfVxuXG4gICAgICAgIHNldElzU3R0UmVjb3JkaW5nKHRydWUpO1xuICAgICAgICAvLyBzZXRTdHRBdWRpb0NodW5rcyhbXSk7IC8vIFRoaXMgd2FzIHByb2JsZW1hdGljLCBzdHRBdWRpb0NodW5rc1JlZi5jdXJyZW50IGlzIHRoZSBzb3VyY2Ugb2YgdHJ1dGhcbiAgICAgICAgc3R0QXVkaW9DaHVua3NSZWYuY3VycmVudCA9IFtdO1xuXG5cbiAgICAgICAgaWYgKGlzV2FrZVdvcmRGb2xsb3dVcCkge1xuICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJBdG9tIGRldGVjdGVkISBMaXN0ZW5pbmcgZm9yIGNvbW1hbmQuLi5cIik7XG4gICAgICAgIH0gZWxzZSBpZiAoaXNBdWRpb01vZGVFbmFibGVkKSB7XG4gICAgICAgICAgICBzZXRXYWtlV29yZFN0YXR1cyhcIkF1ZGlvIE1vZGU6IExpc3RlbmluZyBmb3IgeW91ciByZXBseS9jb21tYW5kLi4uXCIpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJMaXN0ZW5pbmcgKFNUVCkuLi5cIik7XG4gICAgICAgIH1cblxuICAgICAgICB0cnkge1xuICAgICAgICAgICAgLy8gRW5zdXJlIFNUVCB1c2VzIGl0cyBvd24gc3RyZWFtLCBzZXBhcmF0ZSBmcm9tIFdXIHN0cmVhbVxuICAgICAgICAgICAgaWYgKHN0dFN0cmVhbVJlZi5jdXJyZW50KSBzdHRTdHJlYW1SZWYuY3VycmVudC5nZXRUcmFja3MoKS5mb3JFYWNoKHRyYWNrID0+IHRyYWNrLnN0b3AoKSk7XG4gICAgICAgICAgICBjb25zdCBzdHJlYW0gPSBhd2FpdCBuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSh7IGF1ZGlvOiB0cnVlIH0pO1xuICAgICAgICAgICAgc3R0U3RyZWFtUmVmLmN1cnJlbnQgPSBzdHJlYW07XG5cbiAgICAgICAgICAgIGNvbnN0IHJlY29yZGVyID0gbmV3IE1lZGlhUmVjb3JkZXIoc3RyZWFtKTtcbiAgICAgICAgICAgIHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudCA9IHJlY29yZGVyO1xuICAgICAgICAgICAgcmVjb3JkaW5nU3RhcnRUaW1lUmVmLmN1cnJlbnQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgbGFzdFNwZWVjaFRpbWVSZWYuY3VycmVudCA9IERhdGUubm93KCk7XG5cbiAgICAgICAgICAgIHJlY29yZGVyLm9uZGF0YWF2YWlsYWJsZSA9IChldmVudCkgPT4ge1xuICAgICAgICAgICAgICAgIGlmIChldmVudC5kYXRhLnNpemUgPiAwKSBzdHRBdWRpb0NodW5rc1JlZi5jdXJyZW50LnB1c2goZXZlbnQuZGF0YSk7XG4gICAgICAgICAgICAgICAgaWYgKGlzQXVkaW9Nb2RlRW5hYmxlZCAmJiBpc1N0dFJlY29yZGluZykgeyAvLyBDaGVjayBpc1N0dFJlY29yZGluZyBhcyB3ZWxsXG4gICAgICAgICAgICAgICAgICAgIGxhc3RTcGVlY2hUaW1lUmVmLmN1cnJlbnQgPSBEYXRlLm5vdygpO1xuICAgICAgICAgICAgICAgICAgICBpZiAoc2lsZW5jZVRpbWVvdXRSZWYuY3VycmVudCkgY2xlYXJUaW1lb3V0KHNpbGVuY2VUaW1lb3V0UmVmLmN1cnJlbnQpO1xuICAgICAgICAgICAgICAgICAgICBzaWxlbmNlVGltZW91dFJlZi5jdXJyZW50ID0gc2V0VGltZW91dCgoKSA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZiAoRGF0ZS5ub3coKSAtIGxhc3RTcGVlY2hUaW1lUmVmLmN1cnJlbnQgPj0gU0lMRU5DRV9USFJFU0hPTERfTVMgJiZcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBEYXRlLm5vdygpIC0gcmVjb3JkaW5nU3RhcnRUaW1lUmVmLmN1cnJlbnQgPiBNSU5fUkVDT1JESU5HX0RVUkFUSU9OX01TICYmXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNTdHRSZWNvcmRpbmcpIHsgLy8gQ2hlY2sgaXNTdHRSZWNvcmRpbmcgYWdhaW4gYmVmb3JlIHN0b3BwaW5nXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2coXCJTaWxlbmNlIGRldGVjdGVkLCBzdG9wcGluZyBTVFQgY2FwdHVyZS5cIik7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc3RvcFZvaWNlQ2FwdHVyZSgpO1xuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB9LCBTSUxFTkNFX1RIUkVTSE9MRF9NUyk7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfTtcblxuICAgICAgICAgICAgcmVjb3JkZXIub25zdG9wID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiU1RUIE1lZGlhUmVjb3JkZXIub25zdG9wIHRyaWdnZXJlZC5cIik7XG4gICAgICAgICAgICAgICAgaWYgKHNpbGVuY2VUaW1lb3V0UmVmLmN1cnJlbnQpIHsgY2xlYXJUaW1lb3V0KHNpbGVuY2VUaW1lb3V0UmVmLmN1cnJlbnQpOyBzaWxlbmNlVGltZW91dFJlZi5jdXJyZW50ID0gbnVsbDsgfVxuXG4gICAgICAgICAgICAgICAgc2V0SXNUcmFuc2NyaWJpbmcodHJ1ZSk7XG4gICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoaXNBdWRpb01vZGVFbmFibGVkID8gXCJBdWRpbyBNb2RlOiBUcmFuc2NyaWJpbmcuLi5cIiA6IFwiVHJhbnNjcmliaW5nLi4uXCIpO1xuXG4gICAgICAgICAgICAgICAgY29uc3QgYXVkaW9CbG9iID0gbmV3IEJsb2Ioc3R0QXVkaW9DaHVua3NSZWYuY3VycmVudCwgeyB0eXBlOiAnYXVkaW8vd2VibScgfSk7XG4gICAgICAgICAgICAgICAgc3R0QXVkaW9DaHVua3NSZWYuY3VycmVudCA9IFtdOyAvLyBDbGVhciBjaHVua3MgYWZ0ZXIgY3JlYXRpbmcgYmxvYlxuXG4gICAgICAgICAgICAgICAgaWYgKGF1ZGlvQmxvYi5zaXplID4gMCkge1xuICAgICAgICAgICAgICAgICAgICBjb25zdCBhdWRpb0ZpbGUgPSBuZXcgRmlsZShbYXVkaW9CbG9iXSwgXCJ2b2ljZV9pbnB1dC53ZWJtXCIsIHsgdHlwZTogJ2F1ZGlvL3dlYm0nIH0pO1xuICAgICAgICAgICAgICAgICAgICBjb25zdCBmb3JtRGF0YSA9IG5ldyBGb3JtRGF0YSgpO1xuICAgICAgICAgICAgICAgICAgICBmb3JtRGF0YS5hcHBlbmQoXCJhdWRpb19maWxlXCIsIGF1ZGlvRmlsZSk7XG4gICAgICAgICAgICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKCcvYXBpL2F1ZGlvX3Byb2Nlc3Nvci9zdHQnLCB7IG1ldGhvZDogJ1BPU1QnLCBib2R5OiBmb3JtRGF0YSB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlmICghcmVzcG9uc2Uub2spIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBlcnJvckRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKGVycm9yRGF0YS5lcnJvciB8fCBgU1RUIEFQSSBFcnJvcjogJHtyZXNwb25zZS5zdGF0dXN9YCk7XG4gICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZiAocmVzdWx0LnRyYW5zY3JpcHRpb24pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRUZXh0KHByZXZUZXh0ID0+IHByZXZUZXh0ID8gYCR7cHJldlRleHR9ICR7cmVzdWx0LnRyYW5zY3JpcHRpb259YC50cmltKCkgOiByZXN1bHQudHJhbnNjcmlwdGlvbik7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKGlucHV0UmVmLmN1cnJlbnQpIGlucHV0UmVmLmN1cnJlbnQuZm9jdXMoKTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoaXNBdWRpb01vZGVFbmFibGVkID8gXCJBdWRpbyBNb2RlOiBUcmFuc2NyaXB0aW9uIGNvbXBsZXRlLiBSZWFkeS4uLlwiIDogXCJUcmFuc2NyaXB0aW9uIGNvbXBsZXRlLlwiKTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVzdWx0LmVycm9yKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYWxlcnQoYFRyYW5zY3JpcHRpb24gRXJyb3I6ICR7cmVzdWx0LmVycm9yfWApO1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFdha2VXb3JkU3RhdHVzKGlzQXVkaW9Nb2RlRW5hYmxlZCA/IFwiRXJyb3I6IFRyYW5zY3JpcHRpb24gZmFpbGVkLiBUcnkgYWdhaW4uXCIgOiBcIlRyYW5zY3JpcHRpb24gRXJyb3IuXCIpO1xuICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoaXNBdWRpb01vZGVFbmFibGVkID8gXCJBdWRpbyBNb2RlOiBFbXB0eSB0cmFuc2NyaXB0aW9uLiBSZWFkeS4uLlwiIDogXCJFbXB0eSB0cmFuc2NyaXB0aW9uLlwiKTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmVycm9yKFwiU1RUIEVycm9yOlwiLCBlKTtcbiAgICAgICAgICAgICAgICAgICAgICAgIGFsZXJ0KGBTVFQgRXJyb3I6ICR7ZS5tZXNzYWdlfWApO1xuICAgICAgICAgICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoaXNBdWRpb01vZGVFbmFibGVkID8gXCJFcnJvcjogU1RUIHJlcXVlc3QgZmFpbGVkLiBUcnkgYWdhaW4uXCIgOiBcIlNUVCBSZXF1ZXN0IEVycm9yLlwiKTtcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiTm8gYXVkaW8gY2h1bmtzIHRvIHByb2Nlc3MgZm9yIFNUVC5cIik7XG4gICAgICAgICAgICAgICAgICAgIHNldFdha2VXb3JkU3RhdHVzKGlzQXVkaW9Nb2RlRW5hYmxlZCA/IFwiQXVkaW8gTW9kZTogTm8gc3BlZWNoIGRldGVjdGVkLiBSZWFkeS4uLlwiIDogXCJObyBzcGVlY2ggZGV0ZWN0ZWQuXCIpO1xuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHNldElzVHJhbnNjcmliaW5nKGZhbHNlKTtcbiAgICAgICAgICAgICAgICBzdHRTdHJlYW1SZWYuY3VycmVudD8uZ2V0VHJhY2tzKCkuZm9yRWFjaCh0cmFjayA9PiB0cmFjay5zdG9wKCkpO1xuICAgICAgICAgICAgICAgIHN0dFN0cmVhbVJlZi5jdXJyZW50ID0gbnVsbDsgLy8gQ2xlYW4gdXAgU1RUIHN0cmVhbVxuICAgICAgICAgICAgICAgIHNldElzU3R0UmVjb3JkaW5nKGZhbHNlKTsgLy8gRW5zdXJlIHRoaXMgaXMgc2V0IGFmdGVyIGFsbCBwcm9jZXNzaW5nXG5cbiAgICAgICAgICAgICAgICAvLyBJZiBhdWRpbyBtb2RlIGlzIHN0aWxsIG9uLCByZS1pbml0aWFsaXplIHdha2Ugd29yZCBsaXN0ZW5pbmdcbiAgICAgICAgICAgICAgICBpZiAoaXNBdWRpb01vZGVFbmFibGVkKSB7XG4gICAgICAgICAgICAgICAgICAgIGluaXRpYWxpemVXYWtlV29yZEVuZ2luZSgpO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHNldFdha2VXb3JkU3RhdHVzKFwiQXVkaW8gTW9kZSBEaXNhYmxlZFwiKTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9O1xuICAgICAgICAgICAgcmVjb3JkZXIuc3RhcnQoMTAwMCk7IC8vIE9wdGlvbmFsOiB0aW1lc2xpY2UgdG8gZ2V0IGRhdGEgbW9yZSBmcmVxdWVudGx5IGlmIG5lZWRlZFxuICAgICAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcihcIkVycm9yIHN0YXJ0aW5nIFNUVCB2b2ljZSBjYXB0dXJlOlwiLCBlcnJvcik7XG4gICAgICAgICAgICBhbGVydChcIkNvdWxkIG5vdCBhY2Nlc3MgbWljcm9waG9uZSBmb3IgU1RULiBQbGVhc2UgY2hlY2sgcGVybWlzc2lvbnMuXCIpO1xuICAgICAgICAgICAgc2V0SXNTdHRSZWNvcmRpbmcoZmFsc2UpO1xuICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoaXNBdWRpb01vZGVFbmFibGVkID8gXCJFcnJvcjogTWljIGFjY2VzcyBkZW5pZWQgZm9yIFNUVC5cIiA6IFwiTWljIEFjY2VzcyBEZW5pZWQuXCIpO1xuICAgICAgICAgICAgaWYoaXNBdWRpb01vZGVFbmFibGVkKSB7XG4gICAgICAgICAgICAgICAgLy8gQ29uc2lkZXIgaWYgdG9nZ2xpbmcgYXVkaW8gbW9kZSBvZmYgaXMgdGhlIGJlc3QgVVggaGVyZSwgb3IganVzdCByZXNldHRpbmcgc3RhdGUuXG4gICAgICAgICAgICAgICAgLy8gRm9yIG5vdywgbGV0J3MganVzdCByZXNldCBzdGF0dXMgYW5kIG5vdCB0b2dnbGUgbW9kZSBvZmYgYXV0b21hdGljYWxseSBvbiBTVFQgbWljIGVycm9yLlxuICAgICAgICAgICAgICAgICBpbml0aWFsaXplV2FrZVdvcmRFbmdpbmUoKTsgLy8gVHJ5IHRvIGdvIGJhY2sgdG8gV1cgbGlzdGVuaW5nIGlmIHBvc3NpYmxlXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9LCBbaXNBdWRpb01vZGVFbmFibGVkLCBpc1N0dFJlY29yZGluZywgc3RvcFZvaWNlQ2FwdHVyZSwgc2V0VGV4dCwgLyp0b2dnbGVBdWRpb01vZGUsKi8gdGZNb2RlbCwgaW5pdGlhbGl6ZVdha2VXb3JkRW5naW5lXSk7XG5cblxuICAgIGNvbnN0IGhhbmRsZU1hbnVhbFN0dFRvZ2dsZSA9ICgpID0+IHtcbiAgICAgICAgaWYgKGlzU3R0UmVjb3JkaW5nKSB7XG4gICAgICAgICAgICBzdG9wVm9pY2VDYXB0dXJlKCk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAvLyBJZiBpbiBhdWRpbyBtb2RlIGFuZCB3YWtlIHdvcmQgaXMgbGlzdGVuaW5nLCBzdG9wIGl0IGZpcnN0LlxuICAgICAgICAgICAgaWYgKGlzQXVkaW9Nb2RlRW5hYmxlZCAmJiBtZXlkYVJlZi5jdXJyZW50Py5pc1J1bm5pbmcoKSkge1xuICAgICAgICAgICAgICAgIG1leWRhUmVmLmN1cnJlbnQuc3RvcCgpO1xuICAgICAgICAgICAgICAgIC8vIE5vIG5lZWQgdG8gZnVsbHkgY2xlYW51cCBXVyBlbmdpbmUgaGVyZSwganVzdCBwYXVzZSBsaXN0ZW5pbmcuXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBzdGFydFZvaWNlQ2FwdHVyZShmYWxzZSk7XG4gICAgICAgIH1cbiAgICB9O1xuXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgaWYgKGlzQXVkaW9Nb2RlRW5hYmxlZCkge1xuICAgICAgICAgICAgaWYgKCFpc1N0dFJlY29yZGluZyAmJiAhaXNUcmFuc2NyaWJpbmcpIHsgLy8gT25seSBpbml0IFdXIGlmIG5vdCBhY3RpdmVseSBkb2luZyBTVFQvdHJhbnNjcmliaW5nXG4gICAgICAgICAgICAgICAgaW5pdGlhbGl6ZVdha2VXb3JkRW5naW5lKCk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBzdG9wV2FrZVdvcmRFbmdpbmUoKTsgLy8gVGhpcyB3aWxsIGFsc28gc3RvcCBTVFQgaWYgaXQgd2FzIGluaXRpYXRlZCBieSBXV1xuICAgICAgICB9XG4gICAgICAgIC8vIEV4cGxpY2l0IGNsZWFudXAgZm9yIHd3IGVuZ2luZSB3aGVuIGNvbXBvbmVudCB1bm1vdW50cyBvciBpc0F1ZGlvTW9kZUVuYWJsZWQgY2hhbmdlcyBmcm9tIHRydWUgdG8gZmFsc2UuXG4gICAgICAgIHJldHVybiAoKSA9PiB7XG4gICAgICAgICAgICBpZiAoaXNBdWRpb01vZGVFbmFibGVkKSB7IC8vIE9ubHkgcnVuIHN0b3BXYWtlV29yZEVuZ2luZSBpZiBpdCB3YXMgZW5hYmxlZFxuICAgICAgICAgICAgICAgICBzdG9wV2FrZVdvcmRFbmdpbmUoKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfTtcbiAgICB9LCBbaXNBdWRpb01vZGVFbmFibGVkLCBpbml0aWFsaXplV2FrZVdvcmRFbmdpbmUsIHN0b3BXYWtlV29yZEVuZ2luZSwgaXNTdHRSZWNvcmRpbmcsIGlzVHJhbnNjcmliaW5nXSk7XG5cblxuICAgIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICAgIGlmIChyZXBseVJlcXVlc3RDb3VudCA+IDAgJiYgaXNBdWRpb01vZGVFbmFibGVkICYmICFpc1N0dFJlY29yZGluZyAmJiAhaXNUcmFuc2NyaWJpbmcpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGBDaGF0SW5wdXQ6IENvbnRleHQgcmVxdWVzdGVkIGxpc3RlbiBmb3IgcmVwbHkgKGNvdW50OiAke3JlcGx5UmVxdWVzdENvdW50fSkuYCk7XG4gICAgICAgICAgICBpZiAobWV5ZGFSZWYuY3VycmVudD8uaXNSdW5uaW5nKCkpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhcIlBhdXNpbmcgd2FrZSB3b3JkIGVuZ2luZSBmb3IgcmVwbHkgY2FwdHVyZS5cIik7XG4gICAgICAgICAgICAgICAgbWV5ZGFSZWYuY3VycmVudC5zdG9wKCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICAvLyBFbnN1cmUgYW55IGV4aXN0aW5nIFNUVCBzdHJlYW0gaXMgc3RvcHBlZCBiZWZvcmUgc3RhcnRpbmcgYSBuZXcgb25lXG4gICAgICAgICAgICBzdHRTdHJlYW1SZWYuY3VycmVudD8uZ2V0VHJhY2tzKCkuZm9yRWFjaCh0cmFjayA9PiB0cmFjay5zdG9wKCkpO1xuICAgICAgICAgICAgaWYgKHN0dE1lZGlhUmVjb3JkZXJSZWYuY3VycmVudD8uc3RhdGUgPT09IFwicmVjb3JkaW5nXCIpIHtcbiAgICAgICAgICAgICAgICBzdHRNZWRpYVJlY29yZGVyUmVmLmN1cnJlbnQuc3RvcCgpOyAvLyBTdG9wIGV4aXN0aW5nIHJlY29yZGVyIGlmIGFueVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgc3R0QXVkaW9DaHVua3NSZWYuY3VycmVudCA9IFtdOyAvLyBDbGVhciBwcmV2aW91cyBjaHVua3NcbiAgICAgICAgICAgIHN0YXJ0Vm9pY2VDYXB0dXJlKGZhbHNlKTsgLy8gU3RhcnQgU1RUIGZvciByZXBseVxuICAgICAgICB9XG4gICAgfSwgW3JlcGx5UmVxdWVzdENvdW50LCBpc0F1ZGlvTW9kZUVuYWJsZWQsIGlzU3R0UmVjb3JkaW5nLCBpc1RyYW5zY3JpYmluZywgc3RhcnRWb2ljZUNhcHR1cmVdKTtcblxuICAgIC8vIFRoaXMgZWZmZWN0IHNlZW1zIHJlZHVuZGFudCBnaXZlbiB0aGUgbG9naWMgaW4gaW5pdGlhbGl6ZVdha2VXb3JkRW5naW5lIGFuZCB0aGUgbWFpbiBpc0F1ZGlvTW9kZUVuYWJsZWQgZWZmZWN0LlxuICAgIC8vIFNpbXBsaWZpZWQ6IGlmIGF1ZGlvIG1vZGUgaXMgb24sIG5vdCBkb2luZyBTVFQsIGFuZCBXVyBtb2RlbCBsb2FkZWQsIGVuc3VyZSBXVyBpcyBydW5uaW5nLlxuICAgIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICAgIGlmIChpc0F1ZGlvTW9kZUVuYWJsZWQgJiYgIWlzU3R0UmVjb3JkaW5nICYmICFpc1RyYW5zY3JpYmluZyAmJiB0Zk1vZGVsICYmICFtZXlkYVJlZi5jdXJyZW50Py5pc1J1bm5pbmcoKSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coXCJDaGF0SW5wdXQgRWZmZWN0OiBDb25kaXRpb25zIG1ldCB0byAocmUpc3RhcnQgd2FrZSB3b3JkIGxpc3RlbmluZy5cIik7XG4gICAgICAgICAgICBpbml0aWFsaXplV2FrZVdvcmRFbmdpbmUoKTsgLy8gVGhpcyB3aWxsIHJlLWNoZWNrIGNvbmRpdGlvbnMgYW5kIHN0YXJ0IE1leWRhIGlmIG5lZWRlZFxuICAgICAgICB9IGVsc2UgaWYgKG1leWRhUmVmLmN1cnJlbnQ/LmlzUnVubmluZygpICYmICghaXNBdWRpb01vZGVFbmFibGVkIHx8IGlzU3R0UmVjb3JkaW5nIHx8IGlzVHJhbnNjcmliaW5nKSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coXCJDaGF0SW5wdXQgRWZmZWN0OiBDb25kaXRpb25zIG1ldCB0byBwYXVzZSBNZXlkYS5cIik7XG4gICAgICAgICAgICBtZXlkYVJlZi5jdXJyZW50LnN0b3AoKTtcbiAgICAgICAgICAgIGlmICghaXNTdHRSZWNvcmRpbmcgJiYgIWlzVHJhbnNjcmliaW5nICYmICFpc0F1ZGlvTW9kZUVuYWJsZWQpIHsgLy8gSWYgTWV5ZGEgc3RvcHBlZCBiZWNhdXNlIGF1ZGlvIG1vZGUgdHVybmVkIG9mZiAoYW5kIG5vdCBTVFQpXG4gICAgICAgICAgICAgICAgc2V0V2FrZVdvcmRTdGF0dXMoXCJBdWRpbyBNb2RlIERpc2FibGVkXCIpO1xuICAgICAgICAgICAgfSBlbHNlIGlmICghaXNTdHRSZWNvcmRpbmcgJiYgIWlzVHJhbnNjcmliaW5nICYmIGlzQXVkaW9Nb2RlRW5hYmxlZCAmJiB3YWtlV29yZFN0YXR1cy5zdGFydHNXaXRoKFwiQXVkaW8gTW9kZTogTGlzdGVuaW5nIGZvciAnQXRvbScuLi5cIikpIHtcbiAgICAgICAgICAgICAgICAvLyBJZiBtZXlkYSBzdG9wcGVkIGZvciBvdGhlciByZWFzb25zIGJ1dCBzaG91bGQgYmUgbGlzdGVuaW5nXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9LCBbaXNBdWRpb01vZGVFbmFibGVkLCBpc1N0dFJlY29yZGluZywgaXNUcmFuc2NyaWJpbmcsIHRmTW9kZWwsIGluaXRpYWxpemVXYWtlV29yZEVuZ2luZSwgd2FrZVdvcmRTdGF0dXNdKTtcblxuXG4gICAgY29uc3Qgc3R0TWljQnV0dG9uRGlzYWJsZWQgPSBpc1RyYW5zY3JpYmluZyB8fCAoaXNBdWRpb01vZGVFbmFibGVkICYmIHRmTW9kZWwgJiYgbWV5ZGFSZWYuY3VycmVudD8uaXNSdW5uaW5nKCkgJiYgIWlzU3R0UmVjb3JkaW5nKTtcbiAgICAvLyBTaW1wbGlmaWVkOiBEaXNhYmxlIGlmIHRyYW5zY3JpYmluZy4gSWYgaW4gYXVkaW8gbW9kZSB3aXRoIFdXIHJ1bm5pbmcsIGl0IG1lYW5zIFdXIGlzIGFjdGl2ZSwgc28gbWFudWFsIFNUVCBzaG91bGQgYmUgZGlzYWJsZWRcbiAgICAvLyB1bmxlc3MgU1RUIGlzIGFscmVhZHkgYWN0aXZlICh0aGVuIGl0J3MgYSBzdG9wIGJ1dHRvbikuXG5cbiAgICBjb25zdCBvblN1Ym1pdEZvcm0gPSAoZTogUmVhY3QuRm9ybUV2ZW50PEhUTUxGb3JtRWxlbWVudD4pID0+IHtcbiAgICAgICAgZS5wcmV2ZW50RGVmYXVsdCgpO1xuICAgICAgICBpZiAodGV4dC50cmltKCkpIHtcbiAgICAgICAgICAgIHNlbmRNZXNzYWdlKHRleHQpO1xuICAgICAgICAgICAgc2V0VGV4dCgnJyk7XG4gICAgICAgICAgICBpZiAoaW5wdXRSZWYuY3VycmVudCkge1xuICAgICAgICAgICAgICAgIGlucHV0UmVmLmN1cnJlbnQuc3R5bGUuaGVpZ2h0ID0gJ2F1dG8nOyAvLyBSZXNldCBoZWlnaHQgYWZ0ZXIgc2VuZFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgfTtcblxuICAgIC8vIEF1dG8tcmVzaXplIHRleHRhcmVhXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgaWYgKGlucHV0UmVmLmN1cnJlbnQpIHtcbiAgICAgICAgICAgIGlucHV0UmVmLmN1cnJlbnQuc3R5bGUuaGVpZ2h0ID0gJ2F1dG8nO1xuICAgICAgICAgICAgaW5wdXRSZWYuY3VycmVudC5zdHlsZS5oZWlnaHQgPSBgJHtpbnB1dFJlZi5jdXJyZW50LnNjcm9sbEhlaWdodH1weGA7XG4gICAgICAgIH1cbiAgICB9LCBbdGV4dF0pO1xuXG5cbiAgICByZXR1cm4gKFxuICAgICAgICA8ZGl2IGNsYXNzTmFtZT17Y24oJ2ZpeGVkIHctZnVsbCBtZDptYXgtdy0yeGwgYm90dG9tLTAgbGVmdC0xLzIgLXRyYW5zbGF0ZS14LTEvMiBmb250LXNhbnMgei01MCBweC0yIG1kOnB4LTAgcGItMiBtZDpwYi00Jyl9PlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlciBtYi0yIHNwYWNlLXgtMiBweC0yXCI+XG4gICAgICAgICAgICAgICAgPEJ1dHRvblxuICAgICAgICAgICAgICAgICAgICBzaXplPVwic21cIlxuICAgICAgICAgICAgICAgICAgICB2YXJpYW50PXtpc0F1ZGlvTW9kZUVuYWJsZWQgPyBcImRlZmF1bHRcIiA6IFwib3V0bGluZVwifVxuICAgICAgICAgICAgICAgICAgICBvbkNsaWNrPXt0b2dnbGVBdWRpb01vZGV9XG4gICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cInJvdW5kZWQtZnVsbCB0ZXh0LXhzXCIgLy8gc206dGV4dC1zbSByZW1vdmVkIGZvciBjb25zaXN0ZW5jeVxuICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17aXNUcmFuc2NyaWJpbmcgfHwgKCFpc0F1ZGlvTW9kZUVuYWJsZWQgJiYgaXNTdHRSZWNvcmRpbmcpIC8qIEFsbG93IGRpc2FibGluZyBpZiBTVFQgaXMgb24gYnV0IGF1ZGlvIG1vZGUgaXMgb2ZmICovfVxuICAgICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICAgICAge2lzQXVkaW9Nb2RlRW5hYmxlZCA/IDxJY29uTWljT2ZmIGNsYXNzTmFtZT1cIm1yLTEgaC00IHctNFwiIC8+IDogPEljb25NaWMgY2xhc3NOYW1lPVwibXItMSBoLTQgdy00XCIgLz59XG4gICAgICAgICAgICAgICAgICAgIHtpc0F1ZGlvTW9kZUVuYWJsZWQgPyBcIkRpc2FibGUgQXVkaW8gTW9kZVwiIDogXCJFbmFibGUgQXVkaW8gTW9kZVwifVxuICAgICAgICAgICAgICAgIDwvQnV0dG9uPlxuICAgICAgICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cInRleHQteHMgdGV4dC1ncmF5LTUwMCBkYXJrOnRleHQtZ3JheS00MDAgdHJ1bmNhdGUgZmxleC0xIHRleHQtY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgIHtpc1RyYW5zY3JpYmluZyA/IFwiVHJhbnNjcmliaW5nLi4uXCIgOiB3YWtlV29yZFN0YXR1c31cbiAgICAgICAgICAgICAgICA8L3NwYW4+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgIFxuICAgICAgICAgICAgPGZvcm0gb25TdWJtaXQ9e29uU3VibWl0Rm9ybX0gIHJlZj17Zm9ybVJlZn0gY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICAgICAnc3BhY2UteS0wIGJvcmRlci10IHB4LTMgcHktMyBzaGFkb3cteGwgc206cm91bmRlZC14bCBzbTpib3JkZXIgbWQ6cHktMycsXG4gICAgICAgICAgICAgICAgJ2JnLXdoaXRlIGRhcms6YmctZ3JheS04MDAgZGFyazpib3JkZXItZ3JheS03MDAnLFxuICAgICAgICAgICAgICAgIHsgJ29wYWNpdHktNjAgcG9pbnRlci1ldmVudHMtbm9uZSc6IGlzTmV3U2Vzc2lvbiB9XG4gICAgICAgICAgICAgICAgKX0+XG4gICAgICAgICAgICAgICAgey8qIDxsYWJlbCBodG1sRm9yPVwiY2hhdC1pbnB1dFwiIGNsYXNzTmFtZT17Y24oXCJzci1vbmx5XCIpfT5Zb3VyIG1lc3NhZ2U8L2xhYmVsPiAqL31cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInJlbGF0aXZlIGZsZXggdy1mdWxsIGdyb3cgZmxleC1jb2wgb3ZlcmZsb3ctaGlkZGVuIGl0ZW1zLWNlbnRlclwiPiB7LyogQWRkZWQgaXRlbXMtY2VudGVyICovfVxuICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcFByb3ZpZGVyIGRlbGF5RHVyYXRpb249ezMwMH0+XG4gICAgICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcFRyaWdnZXIgYXNDaGlsZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPEJ1dHRvblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdmFyaWFudD1cImdob3N0XCIgLy8gQ2hhbmdlZCB0byBnaG9zdCBmb3IgYSBjbGVhbmVyIGxvb2tcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNpemU9XCJpY29uXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU9XCJidXR0b25cIlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9e2lzTmV3U2Vzc2lvbn1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgb25DbGljaz17ZSA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBlLnByZXZlbnREZWZhdWx0KClcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNhbGxOZXdTZXNzaW9uKClcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPXtjbihcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC8vICdhYnNvbHV0ZSBsZWZ0LTEgdG9wLTEvMiAtdHJhbnNsYXRlLXktMS8yIGgtOCB3LTggcm91bmRlZC1mdWxsIHAtMCcgLy8gT3JpZ2luYWwgcG9zaXRpb25pbmdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICdzaHJpbmstMCBtci0yIHNlbGYtY2VudGVyIHRleHQtZ3JheS01MDAgaG92ZXI6dGV4dC1za3ktNjAwIGRhcms6dGV4dC1ncmF5LTQwMCBkYXJrOmhvdmVyOnRleHQtc2t5LTUwMCdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8SWNvblBsdXMgY2xhc3NOYW1lPVwiaC01IHctNVwiLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwic3Itb25seVwiPk5ldyBDaGF0PC9zcGFuPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L1Rvb2x0aXBUcmlnZ2VyPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUb29sdGlwQ29udGVudCBzaWRlPVwidG9wXCI+TmV3IENoYXQ8L1Rvb2x0aXBDb250ZW50PlxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Ub29sdGlwPlxuICAgICAgICAgICAgICAgICAgICA8L1Rvb2x0aXBQcm92aWRlcj5cbiAgICAgICAgICAgICAgICAgICAgPFRleHRhcmVhXG4gICAgICAgICAgICAgICAgICAgICAgICBpZD1cImNoYXQtaW5wdXRcIlxuICAgICAgICAgICAgICAgICAgICAgICAgcmVmPXtpbnB1dFJlZn1cbiAgICAgICAgICAgICAgICAgICAgICAgIHRhYkluZGV4PXswfVxuICAgICAgICAgICAgICAgICAgICAgICAgb25LZXlEb3duPXtvbktleURvd259XG4gICAgICAgICAgICAgICAgICAgICAgICBzcGVsbENoZWNrPXtmYWxzZX1cbiAgICAgICAgICAgICAgICAgICAgICAgIHJvd3M9ezF9XG4gICAgICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFwiZmxleC0xIG1pbi1oLVs0NHB4XSBtYXgtaC1bMTUwcHhdIHctZnVsbCByb3VuZGVkLWxnIHJlc2l6ZS1ub25lIHB5LTIuNSBwbC0zIHByLTIwIHNtOnRleHQtc21cIiwgLy8gQWRqdXN0ZWQgcGFkZGluZyBhbmQgaGVpZ2h0XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgXCJib3JkZXItZ3JheS0zMDAgZGFyazpib3JkZXItZ3JheS02MDAgYmctZ3JheS01MCBkYXJrOmJnLWdyYXktNzAwXCIsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgXCJmb2N1czpyaW5nLTAgZm9jdXM6cmluZy1vZmZzZXQtMCBmb2N1czpib3JkZXItc2t5LTUwMCBkYXJrOmZvY3VzOmJvcmRlci1za3ktNTAwXCIgLy8gU2ltcGxpZmllZCBmb2N1c1xuICAgICAgICAgICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiWW91ciBtZXNzYWdlLi4uXCJcbiAgICAgICAgICAgICAgICAgICAgICAgIHZhbHVlPXt0ZXh0fVxuICAgICAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e29uQ2hhbmdlVGV4dH1cbiAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJhYnNvbHV0ZSByaWdodC0yIHRvcC0xLzIgLXRyYW5zbGF0ZS15LTEvMiBmbGV4IGl0ZW1zLWNlbnRlciBzcGFjZS14LTFcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxUb29sdGlwUHJvdmlkZXIgZGVsYXlEdXJhdGlvbj17MzAwfT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPFRvb2x0aXBUcmlnZ2VyIGFzQ2hpbGQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8QnV0dG9uXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdHlwZT1cImJ1dHRvblwiXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2l6ZT1cImljb25cIlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHZhcmlhbnQ9e2lzU3R0UmVjb3JkaW5nID8gXCJkZXN0cnVjdGl2ZVwiIDogXCJnaG9zdFwifSAvLyBDaGFuZ2VkIHRvIGdob3N0XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgb25DbGljaz17aGFuZGxlTWFudWFsU3R0VG9nZ2xlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImgtOCB3LTggcm91bmRlZC1mdWxsIHAtMCB0ZXh0LWdyYXktNTAwIGhvdmVyOnRleHQtc2t5LTYwMCBkYXJrOnRleHQtZ3JheS00MDAgZGFyazpob3Zlcjp0ZXh0LXNreS01MDBcIlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXtzdHRNaWNCdXR0b25EaXNhYmxlZH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7aXNTdHRSZWNvcmRpbmcgPyA8SWNvbk1pY09mZiBjbGFzc05hbWU9XCJoLTUgdy01XCIgLz4gOiA8SWNvbk1pYyBjbGFzc05hbWU9XCJoLTUgdy01XCIgLz59XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3NOYW1lPVwic3Itb25seVwiPntpc1N0dFJlY29yZGluZyA/IFwiU3RvcCByZWNvcmRpbmdcIiA6IFwiU3RhcnQgcmVjb3JkaW5nXCJ9PC9zcGFuPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvVG9vbHRpcFRyaWdnZXI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUb29sdGlwQ29udGVudCBzaWRlPVwidG9wXCI+e2lzVHJhbnNjcmliaW5nID8gXCJUcmFuc2NyaWJpbmcuLi5cIiA6IChpc1N0dFJlY29yZGluZyA/IFwiU3RvcCByZWNvcmRpbmdcIiA6IFwiU3RhcnQgcmVjb3JkaW5nXCIpfTwvVG9vbHRpcENvbnRlbnQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9Ub29sdGlwPlxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Ub29sdGlwUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcFByb3ZpZGVyIGRlbGF5RHVyYXRpb249ezMwMH0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPFRvb2x0aXA+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUb29sdGlwVHJpZ2dlciBhc0NoaWxkPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPEJ1dHRvblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNpemU9XCJpY29uXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkaXNhYmxlZD17aXNOZXdTZXNzaW9uIHx8ICF0ZXh0LnRyaW0oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlPVwic3VibWl0XCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9e2NuKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBcImgtOCB3LTggcm91bmRlZC1mdWxsIHAtMCBiZy1za3ktNjAwIGhvdmVyOmJnLXNreS03MDAgdGV4dC13aGl0ZSBkYXJrOmJnLXNreS01MDAgZGFyazpob3ZlcjpiZy1za3ktNjAwXCIsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtcIm9wYWNpdHktNTAgY3Vyc29yLW5vdC1hbGxvd2VkXCI6IGlzTmV3U2Vzc2lvbiB8fCAhdGV4dC50cmltKCl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxJY29uQXJyb3dFbGJvdyBjbGFzc05hbWU9XCJoLTUgdy01XCIgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzc05hbWU9XCJzci1vbmx5XCI+U2VuZCBtZXNzYWdlPC9zcGFuPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvVG9vbHRpcFRyaWdnZXI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPFRvb2x0aXBDb250ZW50IHNpZGU9XCJ0b3BcIj5TZW5kIG1lc3NhZ2U8L1Rvb2x0aXBDb250ZW50PlxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Ub29sdGlwPlxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Ub29sdGlwUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgPC9mb3JtPlxuICAgICAgICA8L2Rpdj5cbiAgICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IENoYXRJbnB1dDtcbiJdfQ==