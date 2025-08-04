"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useWakeWord = exports.WakeWordProvider = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
// Define a global variable to hold the AudioContext instance
let globalAudioContext = null;
const getGlobalAudioContext = () => {
    if (!globalAudioContext) {
        globalAudioContext = new AudioContext();
    }
    return globalAudioContext;
};
const WakeWordContext = (0, react_1.createContext)(undefined);
const WakeWordProvider = ({ children }) => {
    const [isWakeWordEnabled, setIsWakeWordEnabled] = (0, react_1.useState)(false);
    const [isListening, setIsListening] = (0, react_1.useState)(false);
    const [wakeWordError, setWakeWordError] = (0, react_1.useState)(null);
    const audioContextRef = (0, react_1.useRef)(null);
    const mediaStreamRef = (0, react_1.useRef)(null);
    const processorNodeRef = (0, react_1.useRef)(null); // Or AudioWorkletNode
    const webSocketRef = (0, react_1.useRef)(null);
    // TODO: Get this from environment variables via Next.js config
    const AUDIO_PROCESSOR_URL = process.env.NEXT_PUBLIC_AUDIO_PROCESSOR_URL;
    const MOCK_WAKE_WORD_DETECTION = process.env.NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION === 'true';
    const connectWebSocket = (0, react_1.useCallback)(() => {
        if (!AUDIO_PROCESSOR_URL) {
            setWakeWordError("Audio processor URL is not configured.");
            console.error("Audio processor URL is not configured.");
            setIsListening(false);
            return null;
        }
        console.log(`Attempting to connect to WebSocket: ${AUDIO_PROCESSOR_URL}`);
        const ws = new WebSocket(AUDIO_PROCESSOR_URL);
        ws.onopen = () => {
            console.log("WakeWord WebSocket connection established.");
            setWakeWordError(null);
            // Optionally send a configuration message if the STT service requires it
            // ws.send(JSON.stringify({ type: 'config', sampleRate: audioContextRef.current?.sampleRate }));
        };
        ws.onmessage = (event) => {
            // Assuming the STT service sends a message upon wake word detection
            const message = JSON.parse(event.data);
            console.log("WakeWord WebSocket message received:", message);
            if (message.type === 'WAKE_WORD_DETECTED' || (message.transcript && message.transcript.toLowerCase().includes("atom"))) { // Example detection
                console.log("Wake word detected!");
                // TODO: Trigger action (e.g., open chat, send message to agent)
                // For now, just log and maybe set a state
                alert("Wake word 'Atom' detected! (Simulated)");
                // Potentially stop listening or wait for command
            }
            else if (message.type === 'ERROR') {
                setWakeWordError(message.error || "Unknown error from audio processor.");
                console.error("Error from audio processor:", message.error);
            }
        };
        ws.onerror = (error) => {
            console.error("WakeWord WebSocket error:", error);
            setWakeWordError("WebSocket connection error. Ensure the audio processor is running.");
            setIsListening(false); // Stop listening on error
        };
        ws.onclose = (event) => {
            console.log("WakeWord WebSocket connection closed.", event.reason);
            if (isWakeWordEnabled && !event.wasClean) { // If enabled and not closed cleanly
                setWakeWordError("WebSocket connection closed unexpectedly. Retrying...");
                // Basic retry logic (consider more robust backoff)
                // setTimeout(connectWebSocket, 5000); // Reconnect after 5s if still enabled
            }
            if (webSocketRef.current === ws) { // Avoid issues if a new WS was created quickly
                webSocketRef.current = null;
            }
            //setIsListening(false); // Already handled by error or explicit stop
        };
        return ws;
    }, [AUDIO_PROCESSOR_URL, isWakeWordEnabled]);
    const startAudioProcessing = (0, react_1.useCallback)(async () => {
        if (!isWakeWordEnabled || isListening) {
            console.log("Not starting audio processing: disabled or already listening.");
            return;
        }
        setWakeWordError(null);
        setIsListening(true);
        console.log("Attempting to start audio processing for wake word...");
        if (MOCK_WAKE_WORD_DETECTION) {
            console.log("Mock Wake Word Detection is ON. Simulating listening.");
            // Simulate detection after a few seconds for testing
            setTimeout(() => {
                if (isWakeWordEnabled && isListening) { // Check if still relevant
                    console.log("Mock Wake Word 'Atom' detected!");
                    alert("Mock Wake word 'Atom' detected!");
                    // Here you would typically trigger some app action
                }
            }, 5000);
            return;
        }
        if (!AUDIO_PROCESSOR_URL) {
            setWakeWordError("Audio processor URL not configured.");
            setIsListening(false);
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setWakeWordError("getUserMedia not supported on this browser.");
            setIsListening(false);
            return;
        }
        try {
            audioContextRef.current = getGlobalAudioContext();
            if (audioContextRef.current.state === 'suspended') {
                await audioContextRef.current.resume();
            }
            mediaStreamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            const source = audioContextRef.current.createMediaStreamSource(mediaStreamRef.current);
            // WebSocket connection
            webSocketRef.current = connectWebSocket();
            if (!webSocketRef.current) {
                setIsListening(false); // connectWebSocket will set error if URL is missing
                return;
            }
            // ScriptProcessorNode for audio processing (legacy, consider AudioWorklet for modern browsers)
            // Buffer size, input channels, output channels
            const bufferSize = 4096;
            processorNodeRef.current = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1);
            processorNodeRef.current.onaudioprocess = (event) => {
                if (webSocketRef.current && webSocketRef.current.readyState === WebSocket.OPEN) {
                    const inputData = event.inputBuffer.getChannelData(0);
                    // Convert to 16-bit PCM or format expected by STT service
                    const pcmData = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    webSocketRef.current.send(pcmData.buffer);
                }
            };
            source.connect(processorNodeRef.current);
            processorNodeRef.current.connect(audioContextRef.current.destination); // Connect to destination to avoid suspension
            console.log("Audio processing started for wake word.");
        }
        catch (err) {
            console.error("Error starting audio processing:", err);
            setWakeWordError(`Error accessing microphone: ${err.message}`);
            setIsListening(false);
            stopAudioProcessing(); // Clean up
        }
    }, [isWakeWordEnabled, isListening, AUDIO_PROCESSOR_URL, MOCK_WAKE_WORD_DETECTION, connectWebSocket]);
    const stopAudioProcessing = (0, react_1.useCallback)(() => {
        console.log("Stopping audio processing for wake word.");
        setIsListening(false);
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach(track => track.stop());
            mediaStreamRef.current = null;
        }
        if (processorNodeRef.current) {
            processorNodeRef.current.disconnect();
            processorNodeRef.current = null;
        }
        // Do not close globalAudioContext here, it can be reused.
        // If it was created just for this, then:
        // if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        //   // audioContextRef.current.close(); // This is handled by global context now
        //   // audioContextRef.current = null;
        // }
        if (webSocketRef.current) {
            if (webSocketRef.current.readyState === WebSocket.OPEN || webSocketRef.current.readyState === WebSocket.CONNECTING) {
                webSocketRef.current.close(1000, "Client stopping listening");
            }
            webSocketRef.current = null;
        }
    }, []);
    const toggleWakeWord = (0, react_1.useCallback)((forceEnable) => {
        const targetState = typeof forceEnable === 'boolean' ? forceEnable : !isWakeWordEnabled;
        console.log(`Toggling wake word. Current: ${isWakeWordEnabled}, Target: ${targetState}`);
        setIsWakeWordEnabled(targetState);
        if (!targetState) {
            stopAudioProcessing();
        }
        // startAudioProcessing will be called by useEffect if isWakeWordEnabled becomes true
    }, [isWakeWordEnabled, stopAudioProcessing]);
    (0, react_1.useEffect)(() => {
        if (isWakeWordEnabled && !isListening && !wakeWordError) {
            // Check for AudioContext resume on user gesture if needed, though getUserMedia often handles this.
            const resumeAudio = async () => {
                const ctx = getGlobalAudioContext();
                if (ctx.state === 'suspended') {
                    console.log("AudioContext is suspended, attempting to resume for wake word.");
                    try {
                        await ctx.resume();
                        console.log("AudioContext resumed successfully.");
                        startAudioProcessing();
                    }
                    catch (e) {
                        console.error("Failed to resume AudioContext:", e);
                        setWakeWordError("Audio system could not be started. Please interact with the page and try again.");
                    }
                }
                else {
                    startAudioProcessing();
                }
            };
            resumeAudio();
        }
        else if (!isWakeWordEnabled && isListening) {
            stopAudioProcessing();
        }
    }, [isWakeWordEnabled, isListening, startAudioProcessing, stopAudioProcessing, wakeWordError]);
    // Cleanup on unmount
    (0, react_1.useEffect)(() => {
        return () => {
            console.log("WakeWordProvider unmounting. Cleaning up audio resources.");
            stopAudioProcessing();
            if (globalAudioContext && globalAudioContext.state !== 'closed') {
                // globalAudioContext.close(); // Decide if global context should be closed on app exit
                // globalAudioContext = null;
            }
        };
    }, [stopAudioProcessing]);
    return ((0, jsx_runtime_1.jsx)(WakeWordContext.Provider, { value: { isWakeWordEnabled, isListening, wakeWordError, toggleWakeWord, startListening: startAudioProcessing, stopListening: stopAudioProcessing }, children: children }));
};
exports.WakeWordProvider = WakeWordProvider;
const useWakeWord = () => {
    const context = (0, react_1.useContext)(WakeWordContext);
    if (context === undefined) {
        throw new Error('useWakeWord must be used within a WakeWordProvider');
    }
    return context;
};
exports.useWakeWord = useWakeWord;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiV2FrZVdvcmRDb250ZXh0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiV2FrZVdvcmRDb250ZXh0LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7O0FBQUEsaUNBQThHO0FBRTlHLDZEQUE2RDtBQUM3RCxJQUFJLGtCQUFrQixHQUF3QixJQUFJLENBQUM7QUFDbkQsTUFBTSxxQkFBcUIsR0FBRyxHQUFpQixFQUFFO0lBQzdDLElBQUksQ0FBQyxrQkFBa0IsRUFBRSxDQUFDO1FBQ3RCLGtCQUFrQixHQUFHLElBQUksWUFBWSxFQUFFLENBQUM7SUFDNUMsQ0FBQztJQUNELE9BQU8sa0JBQWtCLENBQUM7QUFDOUIsQ0FBQyxDQUFDO0FBWUYsTUFBTSxlQUFlLEdBQUcsSUFBQSxxQkFBYSxFQUFrQyxTQUFTLENBQUMsQ0FBQztBQUUzRSxNQUFNLGdCQUFnQixHQUFzQyxDQUFDLEVBQUUsUUFBUSxFQUFFLEVBQUUsRUFBRTtJQUNsRixNQUFNLENBQUMsaUJBQWlCLEVBQUUsb0JBQW9CLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUM7SUFDM0UsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUM7SUFDL0QsTUFBTSxDQUFDLGFBQWEsRUFBRSxnQkFBZ0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBZ0IsSUFBSSxDQUFDLENBQUM7SUFFeEUsTUFBTSxlQUFlLEdBQUcsSUFBQSxjQUFNLEVBQXNCLElBQUksQ0FBQyxDQUFDO0lBQzFELE1BQU0sY0FBYyxHQUFHLElBQUEsY0FBTSxFQUFxQixJQUFJLENBQUMsQ0FBQztJQUN4RCxNQUFNLGdCQUFnQixHQUFHLElBQUEsY0FBTSxFQUE2QixJQUFJLENBQUMsQ0FBQyxDQUFDLHNCQUFzQjtJQUN6RixNQUFNLFlBQVksR0FBRyxJQUFBLGNBQU0sRUFBbUIsSUFBSSxDQUFDLENBQUM7SUFFcEQsK0RBQStEO0lBQy9E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T0FBTyxPQUFPLENBQUM7QUFDakIsQ0FBQyxDQUFDO0FBTlcsUUFBQSxXQUFXLGVBTXRCIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IGNyZWF0ZUNvbnRleHQsIHVzZVN0YXRlLCB1c2VDb250ZXh0LCBSZWFjdE5vZGUsIHVzZUNhbGxiYWNrLCB1c2VFZmZlY3QsIHVzZVJlZiB9IGZyb20gJ3JlYWN0JztcblxuLy8gRGVmaW5lIGEgZ2xvYmFsIHZhcmlhYmxlIHRvIGhvbGQgdGhlIEF1ZGlvQ29udGV4dCBpbnN0YW5jZVxubGV0IGdsb2JhbEF1ZGlvQ29udGV4dDogQXVkaW9Db250ZXh0IHwgbnVsbCA9IG51bGw7XG5jb25zdCBnZXRHbG9iYWxBdWRpb0NvbnRleHQgPSAoKTogQXVkaW9Db250ZXh0ID0+IHtcbiAgICBpZiAoIWdsb2JhbEF1ZGlvQ29udGV4dCkge1xuICAgICAgICBnbG9iYWxBdWRpb0NvbnRleHQgPSBuZXcgQXVkaW9Db250ZXh0KCk7XG4gICAgfVxuICAgIHJldHVybiBnbG9iYWxBdWRpb0NvbnRleHQ7XG59O1xuXG5cbmludGVyZmFjZSBXYWtlV29yZENvbnRleHRUeXBlIHtcbiAgaXNXYWtlV29yZEVuYWJsZWQ6IGJvb2xlYW47XG4gIGlzTGlzdGVuaW5nOiBib29sZWFuO1xuICB3YWtlV29yZEVycm9yOiBzdHJpbmcgfCBudWxsO1xuICB0b2dnbGVXYWtlV29yZDogKGZvcmNlRW5hYmxlPzogYm9vbGVhbikgPT4gdm9pZDtcbiAgc3RhcnRMaXN0ZW5pbmc6ICgpID0+IHZvaWQ7IC8vIEV4cG9zZWQgZm9yIG1hbnVhbCBzdGFydCBpZiBuZWVkZWQsIGJ1dCB0eXBpY2FsbHkgYXV0b1xuICBzdG9wTGlzdGVuaW5nOiAoKSA9PiB2b2lkO1xufVxuXG5jb25zdCBXYWtlV29yZENvbnRleHQgPSBjcmVhdGVDb250ZXh0PFdha2VXb3JkQ29udGV4dFR5cGUgfCB1bmRlZmluZWQ+KHVuZGVmaW5lZCk7XG5cbmV4cG9ydCBjb25zdCBXYWtlV29yZFByb3ZpZGVyOiBSZWFjdC5GQzx7IGNoaWxkcmVuOiBSZWFjdE5vZGUgfT4gPSAoeyBjaGlsZHJlbiB9KSA9PiB7XG4gIGNvbnN0IFtpc1dha2VXb3JkRW5hYmxlZCwgc2V0SXNXYWtlV29yZEVuYWJsZWRdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpO1xuICBjb25zdCBbaXNMaXN0ZW5pbmcsIHNldElzTGlzdGVuaW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKTtcbiAgY29uc3QgW3dha2VXb3JkRXJyb3IsIHNldFdha2VXb3JkRXJyb3JdID0gdXNlU3RhdGU8c3RyaW5nIHwgbnVsbD4obnVsbCk7XG5cbiAgY29uc3QgYXVkaW9Db250ZXh0UmVmID0gdXNlUmVmPEF1ZGlvQ29udGV4dCB8IG51bGw+KG51bGwpO1xuICBjb25zdCBtZWRpYVN0cmVhbVJlZiA9IHVzZVJlZjxNZWRpYVN0cmVhbSB8IG51bGw+KG51bGwpO1xuICBjb25zdCBwcm9jZXNzb3JOb2RlUmVmID0gdXNlUmVmPFNjcmlwdFByb2Nlc3Nvck5vZGUgfCBudWxsPihudWxsKTsgLy8gT3IgQXVkaW9Xb3JrbGV0Tm9kZVxuICBjb25zdCB3ZWJTb2NrZXRSZWYgPSB1c2VSZWY8V2ViU29ja2V0IHwgbnVsbD4obnVsbCk7XG5cbiAgLy8gVE9ETzogR2V0IHRoaXMgZnJvbSBlbnZpcm9ubWVudCB2YXJpYWJsZXMgdmlhIE5leHQuanMgY29uZmlnXG4gIGNvbnN0IEFVRElPX1BST0NFU1NPUl9VUkwgPSBwcm9jZXNzLmVudi5ORVhUX1BVQkxJQ19BVURJT19QUk9DRVNTT1JfVVJMO1xuICBjb25zdCBNT0NLX1dBS0VfV09SRF9ERVRFQ1RJT04gPSBwcm9jZXNzLmVudi5ORVhUX1BVQkxJQ19NT0NLX1dBS0VfV09SRF9ERVRFQ1RJT04gPT09ICd0cnVlJztcblxuXG4gIGNvbnN0IGNvbm5lY3RXZWJTb2NrZXQgPSB1c2VDYWxsYmFjaygoKSA9PiB7XG4gICAgaWYgKCFBVURJT19QUk9DRVNTT1JfVVJMKSB7XG4gICAgICBzZXRXYWtlV29yZEVycm9yKFwiQXVkaW8gcHJvY2Vzc29yIFVSTCBpcyBub3QgY29uZmlndXJlZC5cIik7XG4gICAgICBjb25zb2xlLmVycm9yKFwiQXVkaW8gcHJvY2Vzc29yIFVSTCBpcyBub3QgY29uZmlndXJlZC5cIik7XG4gICAgICBzZXRJc0xpc3RlbmluZyhmYWxzZSk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhgQXR0ZW1wdGluZyB0byBjb25uZWN0IHRvIFdlYlNvY2tldDogJHtBVURJT19QUk9DRVNTT1JfVVJMfWApO1xuICAgIGNvbnN0IHdzID0gbmV3IFdlYlNvY2tldChBVURJT19QUk9DRVNTT1JfVVJMKTtcblxuICAgIHdzLm9ub3BlbiA9ICgpID0+IHtcbiAgICAgIGNvbnNvbGUubG9nKFwiV2FrZVdvcmQgV2ViU29ja2V0IGNvbm5lY3Rpb24gZXN0YWJsaXNoZWQuXCIpO1xuICAgICAgc2V0V2FrZVdvcmRFcnJvcihudWxsKTtcbiAgICAgIC8vIE9wdGlvbmFsbHkgc2VuZCBhIGNvbmZpZ3VyYXRpb24gbWVzc2FnZSBpZiB0aGUgU1RUIHNlcnZpY2UgcmVxdWlyZXMgaXRcbiAgICAgIC8vIHdzLnNlbmQoSlNPTi5zdHJpbmdpZnkoeyB0eXBlOiAnY29uZmlnJywgc2FtcGxlUmF0ZTogYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQ/LnNhbXBsZVJhdGUgfSkpO1xuICAgIH07XG5cbiAgICB3cy5vbm1lc3NhZ2UgPSAoZXZlbnQpID0+IHtcbiAgICAgIC8vIEFzc3VtaW5nIHRoZSBTVFQgc2VydmljZSBzZW5kcyBhIG1lc3NhZ2UgdXBvbiB3YWtlIHdvcmQgZGV0ZWN0aW9uXG4gICAgICBjb25zdCBtZXNzYWdlID0gSlNPTi5wYXJzZShldmVudC5kYXRhIGFzIHN0cmluZyk7XG4gICAgICBjb25zb2xlLmxvZyhcIldha2VXb3JkIFdlYlNvY2tldCBtZXNzYWdlIHJlY2VpdmVkOlwiLCBtZXNzYWdlKTtcbiAgICAgIGlmIChtZXNzYWdlLnR5cGUgPT09ICdXQUtFX1dPUkRfREVURUNURUQnIHx8IChtZXNzYWdlLnRyYW5zY3JpcHQgJiYgbWVzc2FnZS50cmFuc2NyaXB0LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoXCJhdG9tXCIpKSkgeyAvLyBFeGFtcGxlIGRldGVjdGlvblxuICAgICAgICBjb25zb2xlLmxvZyhcIldha2Ugd29yZCBkZXRlY3RlZCFcIik7XG4gICAgICAgIC8vIFRPRE86IFRyaWdnZXIgYWN0aW9uIChlLmcuLCBvcGVuIGNoYXQsIHNlbmQgbWVzc2FnZSB0byBhZ2VudClcbiAgICAgICAgLy8gRm9yIG5vdywganVzdCBsb2cgYW5kIG1heWJlIHNldCBhIHN0YXRlXG4gICAgICAgIGFsZXJ0KFwiV2FrZSB3b3JkICdBdG9tJyBkZXRlY3RlZCEgKFNpbXVsYXRlZClcIik7XG4gICAgICAgIC8vIFBvdGVudGlhbGx5IHN0b3AgbGlzdGVuaW5nIG9yIHdhaXQgZm9yIGNvbW1hbmRcbiAgICAgIH0gZWxzZSBpZiAobWVzc2FnZS50eXBlID09PSAnRVJST1InKSB7XG4gICAgICAgIHNldFdha2VXb3JkRXJyb3IobWVzc2FnZS5lcnJvciB8fCBcIlVua25vd24gZXJyb3IgZnJvbSBhdWRpbyBwcm9jZXNzb3IuXCIpO1xuICAgICAgICBjb25zb2xlLmVycm9yKFwiRXJyb3IgZnJvbSBhdWRpbyBwcm9jZXNzb3I6XCIsIG1lc3NhZ2UuZXJyb3IpO1xuICAgICAgfVxuICAgIH07XG5cbiAgICB3cy5vbmVycm9yID0gKGVycm9yKSA9PiB7XG4gICAgICBjb25zb2xlLmVycm9yKFwiV2FrZVdvcmQgV2ViU29ja2V0IGVycm9yOlwiLCBlcnJvcik7XG4gICAgICBzZXRXYWtlV29yZEVycm9yKFwiV2ViU29ja2V0IGNvbm5lY3Rpb24gZXJyb3IuIEVuc3VyZSB0aGUgYXVkaW8gcHJvY2Vzc29yIGlzIHJ1bm5pbmcuXCIpO1xuICAgICAgc2V0SXNMaXN0ZW5pbmcoZmFsc2UpOyAvLyBTdG9wIGxpc3RlbmluZyBvbiBlcnJvclxuICAgIH07XG5cbiAgICB3cy5vbmNsb3NlID0gKGV2ZW50KSA9PiB7XG4gICAgICBjb25zb2xlLmxvZyhcIldha2VXb3JkIFdlYlNvY2tldCBjb25uZWN0aW9uIGNsb3NlZC5cIiwgZXZlbnQucmVhc29uKTtcbiAgICAgIGlmIChpc1dha2VXb3JkRW5hYmxlZCAmJiAhZXZlbnQud2FzQ2xlYW4pIHsgLy8gSWYgZW5hYmxlZCBhbmQgbm90IGNsb3NlZCBjbGVhbmx5XG4gICAgICAgIHNldFdha2VXb3JkRXJyb3IoXCJXZWJTb2NrZXQgY29ubmVjdGlvbiBjbG9zZWQgdW5leHBlY3RlZGx5LiBSZXRyeWluZy4uLlwiKTtcbiAgICAgICAgLy8gQmFzaWMgcmV0cnkgbG9naWMgKGNvbnNpZGVyIG1vcmUgcm9idXN0IGJhY2tvZmYpXG4gICAgICAgIC8vIHNldFRpbWVvdXQoY29ubmVjdFdlYlNvY2tldCwgNTAwMCk7IC8vIFJlY29ubmVjdCBhZnRlciA1cyBpZiBzdGlsbCBlbmFibGVkXG4gICAgICB9XG4gICAgICAgaWYgKHdlYlNvY2tldFJlZi5jdXJyZW50ID09PSB3cykgeyAvLyBBdm9pZCBpc3N1ZXMgaWYgYSBuZXcgV1Mgd2FzIGNyZWF0ZWQgcXVpY2tseVxuICAgICAgICAgICB3ZWJTb2NrZXRSZWYuY3VycmVudCA9IG51bGw7XG4gICAgICAgfVxuICAgICAgIC8vc2V0SXNMaXN0ZW5pbmcoZmFsc2UpOyAvLyBBbHJlYWR5IGhhbmRsZWQgYnkgZXJyb3Igb3IgZXhwbGljaXQgc3RvcFxuICAgIH07XG4gICAgcmV0dXJuIHdzO1xuICB9LCBbQVVESU9fUFJPQ0VTU09SX1VSTCwgaXNXYWtlV29yZEVuYWJsZWRdKTtcblxuXG4gIGNvbnN0IHN0YXJ0QXVkaW9Qcm9jZXNzaW5nID0gdXNlQ2FsbGJhY2soYXN5bmMgKCkgPT4ge1xuICAgIGlmICghaXNXYWtlV29yZEVuYWJsZWQgfHwgaXNMaXN0ZW5pbmcpIHtcbiAgICAgIGNvbnNvbGUubG9nKFwiTm90IHN0YXJ0aW5nIGF1ZGlvIHByb2Nlc3Npbmc6IGRpc2FibGVkIG9yIGFscmVhZHkgbGlzdGVuaW5nLlwiKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBzZXRXYWtlV29yZEVycm9yKG51bGwpO1xuICAgIHNldElzTGlzdGVuaW5nKHRydWUpO1xuICAgIGNvbnNvbGUubG9nKFwiQXR0ZW1wdGluZyB0byBzdGFydCBhdWRpbyBwcm9jZXNzaW5nIGZvciB3YWtlIHdvcmQuLi5cIik7XG5cbiAgICBpZiAoTU9DS19XQUtFX1dPUkRfREVURUNUSU9OKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFwiTW9jayBXYWtlIFdvcmQgRGV0ZWN0aW9uIGlzIE9OLiBTaW11bGF0aW5nIGxpc3RlbmluZy5cIik7XG4gICAgICAgIC8vIFNpbXVsYXRlIGRldGVjdGlvbiBhZnRlciBhIGZldyBzZWNvbmRzIGZvciB0ZXN0aW5nXG4gICAgICAgIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgICAgICAgICAgaWYgKGlzV2FrZVdvcmRFbmFibGVkICYmIGlzTGlzdGVuaW5nKSB7IC8vIENoZWNrIGlmIHN0aWxsIHJlbGV2YW50XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coXCJNb2NrIFdha2UgV29yZCAnQXRvbScgZGV0ZWN0ZWQhXCIpO1xuICAgICAgICAgICAgICAgIGFsZXJ0KFwiTW9jayBXYWtlIHdvcmQgJ0F0b20nIGRldGVjdGVkIVwiKTtcbiAgICAgICAgICAgICAgICAvLyBIZXJlIHlvdSB3b3VsZCB0eXBpY2FsbHkgdHJpZ2dlciBzb21lIGFwcCBhY3Rpb25cbiAgICAgICAgICAgIH1cbiAgICAgICAgfSwgNTAwMCk7XG4gICAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpZiAoIUFVRElPX1BST0NFU1NPUl9VUkwpIHtcbiAgICAgICAgc2V0V2FrZVdvcmRFcnJvcihcIkF1ZGlvIHByb2Nlc3NvciBVUkwgbm90IGNvbmZpZ3VyZWQuXCIpO1xuICAgICAgICBzZXRJc0xpc3RlbmluZyhmYWxzZSk7XG4gICAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpZiAoIW5hdmlnYXRvci5tZWRpYURldmljZXMgfHwgIW5hdmlnYXRvci5tZWRpYURldmljZXMuZ2V0VXNlck1lZGlhKSB7XG4gICAgICBzZXRXYWtlV29yZEVycm9yKFwiZ2V0VXNlck1lZGlhIG5vdCBzdXBwb3J0ZWQgb24gdGhpcyBicm93c2VyLlwiKTtcbiAgICAgIHNldElzTGlzdGVuaW5nKGZhbHNlKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICB0cnkge1xuICAgICAgYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQgPSBnZXRHbG9iYWxBdWRpb0NvbnRleHQoKTtcbiAgICAgIGlmIChhdWRpb0NvbnRleHRSZWYuY3VycmVudC5zdGF0ZSA9PT0gJ3N1c3BlbmRlZCcpIHtcbiAgICAgICAgYXdhaXQgYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQucmVzdW1lKCk7XG4gICAgICB9XG5cbiAgICAgIG1lZGlhU3RyZWFtUmVmLmN1cnJlbnQgPSBhd2FpdCBuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSh7IGF1ZGlvOiB0cnVlLCB2aWRlbzogZmFsc2UgfSk7XG4gICAgICBjb25zdCBzb3VyY2UgPSBhdWRpb0NvbnRleHRSZWYuY3VycmVudC5jcmVhdGVNZWRpYVN0cmVhbVNvdXJjZShtZWRpYVN0cmVhbVJlZi5jdXJyZW50KTtcblxuICAgICAgLy8gV2ViU29ja2V0IGNvbm5lY3Rpb25cbiAgICAgIHdlYlNvY2tldFJlZi5jdXJyZW50ID0gY29ubmVjdFdlYlNvY2tldCgpO1xuICAgICAgaWYgKCF3ZWJTb2NrZXRSZWYuY3VycmVudCkge1xuICAgICAgICAgIHNldElzTGlzdGVuaW5nKGZhbHNlKTsgLy8gY29ubmVjdFdlYlNvY2tldCB3aWxsIHNldCBlcnJvciBpZiBVUkwgaXMgbWlzc2luZ1xuICAgICAgICAgIHJldHVybjtcbiAgICAgIH1cblxuICAgICAgLy8gU2NyaXB0UHJvY2Vzc29yTm9kZSBmb3IgYXVkaW8gcHJvY2Vzc2luZyAobGVnYWN5LCBjb25zaWRlciBBdWRpb1dvcmtsZXQgZm9yIG1vZGVybiBicm93c2VycylcbiAgICAgIC8vIEJ1ZmZlciBzaXplLCBpbnB1dCBjaGFubmVscywgb3V0cHV0IGNoYW5uZWxzXG4gICAgICBjb25zdCBidWZmZXJTaXplID0gNDA5NjtcbiAgICAgIHByb2Nlc3Nvck5vZGVSZWYuY3VycmVudCA9IGF1ZGlvQ29udGV4dFJlZi5jdXJyZW50LmNyZWF0ZVNjcmlwdFByb2Nlc3NvcihidWZmZXJTaXplLCAxLCAxKTtcblxuICAgICAgcHJvY2Vzc29yTm9kZVJlZi5jdXJyZW50Lm9uYXVkaW9wcm9jZXNzID0gKGV2ZW50KSA9PiB7XG4gICAgICAgIGlmICh3ZWJTb2NrZXRSZWYuY3VycmVudCAmJiB3ZWJTb2NrZXRSZWYuY3VycmVudC5yZWFkeVN0YXRlID09PSBXZWJTb2NrZXQuT1BFTikge1xuICAgICAgICAgIGNvbnN0IGlucHV0RGF0YSA9IGV2ZW50LmlucHV0QnVmZmVyLmdldENoYW5uZWxEYXRhKDApO1xuICAgICAgICAgIC8vIENvbnZlcnQgdG8gMTYtYml0IFBDTSBvciBmb3JtYXQgZXhwZWN0ZWQgYnkgU1RUIHNlcnZpY2VcbiAgICAgICAgICBjb25zdCBwY21EYXRhID0gbmV3IEludDE2QXJyYXkoaW5wdXREYXRhLmxlbmd0aCk7XG4gICAgICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBpbnB1dERhdGEubGVuZ3RoOyBpKyspIHtcbiAgICAgICAgICAgIHBjbURhdGFbaV0gPSBNYXRoLm1heCgtMSwgTWF0aC5taW4oMSwgaW5wdXREYXRhW2ldKSkgKiAweDdGRkY7XG4gICAgICAgICAgfVxuICAgICAgICAgIHdlYlNvY2tldFJlZi5jdXJyZW50LnNlbmQocGNtRGF0YS5idWZmZXIpO1xuICAgICAgICB9XG4gICAgICB9O1xuXG4gICAgICBzb3VyY2UuY29ubmVjdChwcm9jZXNzb3JOb2RlUmVmLmN1cnJlbnQpO1xuICAgICAgcHJvY2Vzc29yTm9kZVJlZi5jdXJyZW50LmNvbm5lY3QoYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQuZGVzdGluYXRpb24pOyAvLyBDb25uZWN0IHRvIGRlc3RpbmF0aW9uIHRvIGF2b2lkIHN1c3BlbnNpb25cblxuICAgICAgY29uc29sZS5sb2coXCJBdWRpbyBwcm9jZXNzaW5nIHN0YXJ0ZWQgZm9yIHdha2Ugd29yZC5cIik7XG5cbiAgICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcIkVycm9yIHN0YXJ0aW5nIGF1ZGlvIHByb2Nlc3Npbmc6XCIsIGVycik7XG4gICAgICBzZXRXYWtlV29yZEVycm9yKGBFcnJvciBhY2Nlc3NpbmcgbWljcm9waG9uZTogJHtlcnIubWVzc2FnZX1gKTtcbiAgICAgIHNldElzTGlzdGVuaW5nKGZhbHNlKTtcbiAgICAgIHN0b3BBdWRpb1Byb2Nlc3NpbmcoKTsgLy8gQ2xlYW4gdXBcbiAgICB9XG4gIH0sIFtpc1dha2VXb3JkRW5hYmxlZCwgaXNMaXN0ZW5pbmcsIEFVRElPX1BST0NFU1NPUl9VUkwsIE1PQ0tfV0FLRV9XT1JEX0RFVEVDVElPTiwgY29ubmVjdFdlYlNvY2tldF0pO1xuXG4gIGNvbnN0IHN0b3BBdWRpb1Byb2Nlc3NpbmcgPSB1c2VDYWxsYmFjaygoKSA9PiB7XG4gICAgY29uc29sZS5sb2coXCJTdG9wcGluZyBhdWRpbyBwcm9jZXNzaW5nIGZvciB3YWtlIHdvcmQuXCIpO1xuICAgIHNldElzTGlzdGVuaW5nKGZhbHNlKTtcblxuICAgIGlmIChtZWRpYVN0cmVhbVJlZi5jdXJyZW50KSB7XG4gICAgICBtZWRpYVN0cmVhbVJlZi5jdXJyZW50LmdldFRyYWNrcygpLmZvckVhY2godHJhY2sgPT4gdHJhY2suc3RvcCgpKTtcbiAgICAgIG1lZGlhU3RyZWFtUmVmLmN1cnJlbnQgPSBudWxsO1xuICAgIH1cbiAgICBpZiAocHJvY2Vzc29yTm9kZVJlZi5jdXJyZW50KSB7XG4gICAgICBwcm9jZXNzb3JOb2RlUmVmLmN1cnJlbnQuZGlzY29ubmVjdCgpO1xuICAgICAgcHJvY2Vzc29yTm9kZVJlZi5jdXJyZW50ID0gbnVsbDtcbiAgICB9XG4gICAgLy8gRG8gbm90IGNsb3NlIGdsb2JhbEF1ZGlvQ29udGV4dCBoZXJlLCBpdCBjYW4gYmUgcmV1c2VkLlxuICAgIC8vIElmIGl0IHdhcyBjcmVhdGVkIGp1c3QgZm9yIHRoaXMsIHRoZW46XG4gICAgLy8gaWYgKGF1ZGlvQ29udGV4dFJlZi5jdXJyZW50ICYmIGF1ZGlvQ29udGV4dFJlZi5jdXJyZW50LnN0YXRlICE9PSAnY2xvc2VkJykge1xuICAgIC8vICAgLy8gYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQuY2xvc2UoKTsgLy8gVGhpcyBpcyBoYW5kbGVkIGJ5IGdsb2JhbCBjb250ZXh0IG5vd1xuICAgIC8vICAgLy8gYXVkaW9Db250ZXh0UmVmLmN1cnJlbnQgPSBudWxsO1xuICAgIC8vIH1cbiAgICBpZiAod2ViU29ja2V0UmVmLmN1cnJlbnQpIHtcbiAgICAgIGlmICh3ZWJTb2NrZXRSZWYuY3VycmVudC5yZWFkeVN0YXRlID09PSBXZWJTb2NrZXQuT1BFTiB8fCB3ZWJTb2NrZXRSZWYuY3VycmVudC5yZWFkeVN0YXRlID09PSBXZWJTb2NrZXQuQ09OTkVDVElORykge1xuICAgICAgICB3ZWJTb2NrZXRSZWYuY3VycmVudC5jbG9zZSgxMDAwLCBcIkNsaWVudCBzdG9wcGluZyBsaXN0ZW5pbmdcIik7XG4gICAgICB9XG4gICAgICB3ZWJTb2NrZXRSZWYuY3VycmVudCA9IG51bGw7XG4gICAgfVxuICB9LCBbXSk7XG5cbiAgY29uc3QgdG9nZ2xlV2FrZVdvcmQgPSB1c2VDYWxsYmFjaygoZm9yY2VFbmFibGU/OiBib29sZWFuKSA9PiB7XG4gICAgY29uc3QgdGFyZ2V0U3RhdGUgPSB0eXBlb2YgZm9yY2VFbmFibGUgPT09ICdib29sZWFuJyA/IGZvcmNlRW5hYmxlIDogIWlzV2FrZVdvcmRFbmFibGVkO1xuICAgIGNvbnNvbGUubG9nKGBUb2dnbGluZyB3YWtlIHdvcmQuIEN1cnJlbnQ6ICR7aXNXYWtlV29yZEVuYWJsZWR9LCBUYXJnZXQ6ICR7dGFyZ2V0U3RhdGV9YCk7XG4gICAgc2V0SXNXYWtlV29yZEVuYWJsZWQodGFyZ2V0U3RhdGUpO1xuICAgIGlmICghdGFyZ2V0U3RhdGUpIHtcbiAgICAgIHN0b3BBdWRpb1Byb2Nlc3NpbmcoKTtcbiAgICB9XG4gICAgLy8gc3RhcnRBdWRpb1Byb2Nlc3Npbmcgd2lsbCBiZSBjYWxsZWQgYnkgdXNlRWZmZWN0IGlmIGlzV2FrZVdvcmRFbmFibGVkIGJlY29tZXMgdHJ1ZVxuICB9LCBbaXNXYWtlV29yZEVuYWJsZWQsIHN0b3BBdWRpb1Byb2Nlc3NpbmddKTtcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGlmIChpc1dha2VXb3JkRW5hYmxlZCAmJiAhaXNMaXN0ZW5pbmcgJiYgIXdha2VXb3JkRXJyb3IpIHtcbiAgICAgIC8vIENoZWNrIGZvciBBdWRpb0NvbnRleHQgcmVzdW1lIG9uIHVzZXIgZ2VzdHVyZSBpZiBuZWVkZWQsIHRob3VnaCBnZXRVc2VyTWVkaWEgb2Z0ZW4gaGFuZGxlcyB0aGlzLlxuICAgICAgY29uc3QgcmVzdW1lQXVkaW8gPSBhc3luYyAoKSA9PiB7XG4gICAgICAgICAgY29uc3QgY3R4ID0gZ2V0R2xvYmFsQXVkaW9Db250ZXh0KCk7XG4gICAgICAgICAgaWYgKGN0eC5zdGF0ZSA9PT0gJ3N1c3BlbmRlZCcpIHtcbiAgICAgICAgICAgICAgY29uc29sZS5sb2coXCJBdWRpb0NvbnRleHQgaXMgc3VzcGVuZGVkLCBhdHRlbXB0aW5nIHRvIHJlc3VtZSBmb3Igd2FrZSB3b3JkLlwiKTtcbiAgICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICAgIGF3YWl0IGN0eC5yZXN1bWUoKTtcbiAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiQXVkaW9Db250ZXh0IHJlc3VtZWQgc3VjY2Vzc2Z1bGx5LlwiKTtcbiAgICAgICAgICAgICAgICAgIHN0YXJ0QXVkaW9Qcm9jZXNzaW5nKCk7XG4gICAgICAgICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXCJGYWlsZWQgdG8gcmVzdW1lIEF1ZGlvQ29udGV4dDpcIiwgZSk7XG4gICAgICAgICAgICAgICAgICBzZXRXYWtlV29yZEVycm9yKFwiQXVkaW8gc3lzdGVtIGNvdWxkIG5vdCBiZSBzdGFydGVkLiBQbGVhc2UgaW50ZXJhY3Qgd2l0aCB0aGUgcGFnZSBhbmQgdHJ5IGFnYWluLlwiKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIHN0YXJ0QXVkaW9Qcm9jZXNzaW5nKCk7XG4gICAgICAgICAgfVxuICAgICAgfTtcbiAgICAgIHJlc3VtZUF1ZGlvKCk7XG4gICAgfSBlbHNlIGlmICghaXNXYWtlV29yZEVuYWJsZWQgJiYgaXNMaXN0ZW5pbmcpIHtcbiAgICAgIHN0b3BBdWRpb1Byb2Nlc3NpbmcoKTtcbiAgICB9XG4gIH0sIFtpc1dha2VXb3JkRW5hYmxlZCwgaXNMaXN0ZW5pbmcsIHN0YXJ0QXVkaW9Qcm9jZXNzaW5nLCBzdG9wQXVkaW9Qcm9jZXNzaW5nLCB3YWtlV29yZEVycm9yXSk7XG5cbiAgLy8gQ2xlYW51cCBvbiB1bm1vdW50XG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgcmV0dXJuICgpID0+IHtcbiAgICAgIGNvbnNvbGUubG9nKFwiV2FrZVdvcmRQcm92aWRlciB1bm1vdW50aW5nLiBDbGVhbmluZyB1cCBhdWRpbyByZXNvdXJjZXMuXCIpO1xuICAgICAgc3RvcEF1ZGlvUHJvY2Vzc2luZygpO1xuICAgICAgaWYgKGdsb2JhbEF1ZGlvQ29udGV4dCAmJiBnbG9iYWxBdWRpb0NvbnRleHQuc3RhdGUgIT09ICdjbG9zZWQnKSB7XG4gICAgICAgICAgLy8gZ2xvYmFsQXVkaW9Db250ZXh0LmNsb3NlKCk7IC8vIERlY2lkZSBpZiBnbG9iYWwgY29udGV4dCBzaG91bGQgYmUgY2xvc2VkIG9uIGFwcCBleGl0XG4gICAgICAgICAgLy8gZ2xvYmFsQXVkaW9Db250ZXh0ID0gbnVsbDtcbiAgICAgIH1cbiAgICB9O1xuICB9LCBbc3RvcEF1ZGlvUHJvY2Vzc2luZ10pO1xuXG4gIHJldHVybiAoXG4gICAgPFdha2VXb3JkQ29udGV4dC5Qcm92aWRlciB2YWx1ZT17eyBpc1dha2VXb3JkRW5hYmxlZCwgaXNMaXN0ZW5pbmcsIHdha2VXb3JkRXJyb3IsIHRvZ2dsZVdha2VXb3JkLCBzdGFydExpc3RlbmluZzogc3RhcnRBdWRpb1Byb2Nlc3NpbmcsIHN0b3BMaXN0ZW5pbmc6IHN0b3BBdWRpb1Byb2Nlc3NpbmcgfX0+XG4gICAgICB7Y2hpbGRyZW59XG4gICAgPC9XYWtlV29yZENvbnRleHQuUHJvdmlkZXI+XG4gICk7XG59O1xuXG5leHBvcnQgY29uc3QgdXNlV2FrZVdvcmQgPSAoKTogV2FrZVdvcmRDb250ZXh0VHlwZSA9PiB7XG4gIGNvbnN0IGNvbnRleHQgPSB1c2VDb250ZXh0KFdha2VXb3JkQ29udGV4dCk7XG4gIGlmIChjb250ZXh0ID09PSB1bmRlZmluZWQpIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ3VzZVdha2VXb3JkIG11c3QgYmUgdXNlZCB3aXRoaW4gYSBXYWtlV29yZFByb3ZpZGVyJyk7XG4gIH1cbiAgcmV0dXJuIGNvbnRleHQ7XG59O1xuIl19