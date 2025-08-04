"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAudioMode = exports.AudioModeProvider = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
// Create the context with a default undefined value
const AudioModeContext = (0, react_1.createContext)(undefined);
// Create the Provider Component
const AudioModeProvider = ({ children }) => {
    const [isAudioModeEnabled, setIsAudioModeEnabled] = (0, react_1.useState)(false);
    const [replyRequestCount, setReplyRequestCount] = (0, react_1.useState)(0);
    const toggleAudioMode = (0, react_1.useCallback)(() => {
        setIsAudioModeEnabled(prev => {
            const newState = !prev;
            if (!newState) {
                // If audio mode is being disabled, reset reply request count as well (optional, but good for consistency)
                setReplyRequestCount(0);
            }
            return newState;
        });
    }, []);
    const triggerReplyListen = (0, react_1.useCallback)(() => {
        if (isAudioModeEnabled) { // Only trigger if audio mode is actually enabled
            console.log("AudioModeContext: triggerReplyListen called, incrementing replyRequestCount.");
            setReplyRequestCount(prev => prev + 1);
        }
        else {
            console.log("AudioModeContext: triggerReplyListen called, but Audio Mode is disabled. No action taken.");
        }
    }, [isAudioModeEnabled]); // Depends on isAudioModeEnabled to decide if it should act
    return ((0, jsx_runtime_1.jsx)(AudioModeContext.Provider, { value: {
            isAudioModeEnabled,
            toggleAudioMode,
            replyRequestCount,
            triggerReplyListen,
        }, children: children }));
};
exports.AudioModeProvider = AudioModeProvider;
// Create a custom hook for convenience
const useAudioMode = () => {
    const context = (0, react_1.useContext)(AudioModeContext);
    if (context === undefined) {
        throw new Error('useAudioMode must be used within an AudioModeProvider');
    }
    return context;
};
exports.useAudioMode = useAudioMode;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQXVkaW9Nb2RlQ29udGV4dC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkF1ZGlvTW9kZUNvbnRleHQudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7QUFBQSxpQ0FBMkY7QUFVM0Ysb0RBQW9EO0FBQ3BELE1BQU0sZ0JBQWdCLEdBQUcsSUFBQSxxQkFBYSxFQUFtQyxTQUFTLENBQUMsQ0FBQztBQUVwRixnQ0FBZ0M7QUFDekIsTUFBTSxpQkFBaUIsR0FBRyxDQUFDLEVBQUUsUUFBUSxFQUEyQixFQUFFLEVBQUU7SUFDekUsTUFBTSxDQUFDLGtCQUFrQixFQUFFLHFCQUFxQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEtBQUssQ0FBQyxDQUFDO0lBQ3BFLE1BQU0sQ0FBQyxpQkFBaUIsRUFBRSxvQkFBb0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxDQUFDLENBQUMsQ0FBQztJQUU5RCxNQUFNLGVBQWUsR0FBRyxJQUFBLG1CQUFXLEVBQUMsR0FBRyxFQUFFO1FBQ3ZDLHFCQUFxQixDQUFDLElBQUksQ0FBQyxFQUFFO1lBQzNCLE1BQU0sUUFBUSxHQUFHLENBQUMsSUFBSSxDQUFDO1lBQ3ZCLElBQUksQ0FBQyxRQUFRLEVBQUUsQ0FBQztnQkFDZCwwR0FBMEc7Z0JBQzFHLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzFCLENBQUM7WUFDRCxPQUFPLFFBQVEsQ0FBQztRQUNsQixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztJQUVQLE1BQU0sa0JBQWtCLEdBQUcsSUFBQSxtQkFBVyxFQUFDLEdBQUcsRUFBRTtRQUMxQyxJQUFJLGtCQUFrQixFQUFFLENBQUMsQ0FBQyxpREFBaUQ7WUFDdkUsT0FBTyxDQUFDLEdBQUcsQ0FBQyw4RUFBOEUsQ0FBQyxDQUFDO1lBQzVGLG9CQUFvQixDQUFDLElBQUksQ0FBQyxFQUFFLENBQUMsSUFBSSxHQUFHLENBQUMsQ0FBQyxDQUFDO1FBQzNDLENBQUM7YUFBTSxDQUFDO1lBQ0osT0FBTyxDQUFDLEdBQUcsQ0FBQywyRkFBMkYsQ0FBQyxDQUFDO1FBQzdHLENBQUM7SUFDSCxDQUFDLEVBQUUsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDLENBQUMsQ0FBQywyREFBMkQ7SUFFckYsT0FBTyxDQUNMLHVCQUFDLGdCQUFnQixDQUFDLFFBQVEsSUFDeEIsS0FBSyxFQUFFO1lBQ0wsa0JBQWtCO1lBQ2xCLGVBQWU7WUFDZixpQkFBaUI7WUFDakIsa0JBQWtCO1NBQ25CLFlBRUEsUUFBUSxHQUNpQixDQUM3QixDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBcENXLFFBQUEsaUJBQWlCLHFCQW9DNUI7QUFFRix1Q0FBdUM7QUFDaEMsTUFBTSxZQUFZLEdBQUcsR0FBRyxFQUFFO0lBQy9CLE1BQU0sT0FBTyxHQUFHLElBQUEsa0JBQVUsRUFBQyxnQkFBZ0IsQ0FBQyxDQUFDO0lBQzdDLElBQUksT0FBTyxLQUFLLFNBQVMsRUFBRSxDQUFDO1FBQzFCLE1BQU0sSUFBSSxLQUFLLENBQUMsdURBQXVELENBQUMsQ0FBQztJQUMzRSxDQUFDO0lBQ0QsT0FBTyxPQUFPLENBQUM7QUFDakIsQ0FBQyxDQUFDO0FBTlcsUUFBQSxZQUFZLGdCQU12QiIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyBjcmVhdGVDb250ZXh0LCB1c2VTdGF0ZSwgdXNlQ29udGV4dCwgUmVhY3ROb2RlLCB1c2VDYWxsYmFjayB9IGZyb20gXCJyZWFjdFwiO1xuXG4vLyBEZWZpbmUgdGhlIGludGVyZmFjZSBmb3IgdGhlIGNvbnRleHQgdmFsdWVcbmludGVyZmFjZSBBdWRpb01vZGVDb250ZXh0VHlwZSB7XG4gIGlzQXVkaW9Nb2RlRW5hYmxlZDogYm9vbGVhbjtcbiAgdG9nZ2xlQXVkaW9Nb2RlOiAoKSA9PiB2b2lkO1xuICByZXBseVJlcXVlc3RDb3VudDogbnVtYmVyOyAgICAvLyBJbmNyZW1lbnRlZCB0byBzaWduYWwgYSByZXBseSBsaXN0ZW4gcmVxdWVzdFxuICB0cmlnZ2VyUmVwbHlMaXN0ZW46ICgpID0+IHZvaWQ7IC8vIEZ1bmN0aW9uIHRvIGluY3JlbWVudCByZXBseVJlcXVlc3RDb3VudFxufVxuXG4vLyBDcmVhdGUgdGhlIGNvbnRleHQgd2l0aCBhIGRlZmF1bHQgdW5kZWZpbmVkIHZhbHVlXG5jb25zdCBBdWRpb01vZGVDb250ZXh0ID0gY3JlYXRlQ29udGV4dDxBdWRpb01vZGVDb250ZXh0VHlwZSB8IHVuZGVmaW5lZD4odW5kZWZpbmVkKTtcblxuLy8gQ3JlYXRlIHRoZSBQcm92aWRlciBDb21wb25lbnRcbmV4cG9ydCBjb25zdCBBdWRpb01vZGVQcm92aWRlciA9ICh7IGNoaWxkcmVuIH06IHsgY2hpbGRyZW46IFJlYWN0Tm9kZSB9KSA9PiB7XG4gIGNvbnN0IFtpc0F1ZGlvTW9kZUVuYWJsZWQsIHNldElzQXVkaW9Nb2RlRW5hYmxlZF0gPSB1c2VTdGF0ZShmYWxzZSk7XG4gIGNvbnN0IFtyZXBseVJlcXVlc3RDb3VudCwgc2V0UmVwbHlSZXF1ZXN0Q291bnRdID0gdXNlU3RhdGUoMCk7XG5cbiAgY29uc3QgdG9nZ2xlQXVkaW9Nb2RlID0gdXNlQ2FsbGJhY2soKCkgPT4ge1xuICAgIHNldElzQXVkaW9Nb2RlRW5hYmxlZChwcmV2ID0+IHtcbiAgICAgIGNvbnN0IG5ld1N0YXRlID0gIXByZXY7XG4gICAgICBpZiAoIW5ld1N0YXRlKSB7XG4gICAgICAgIC8vIElmIGF1ZGlvIG1vZGUgaXMgYmVpbmcgZGlzYWJsZWQsIHJlc2V0IHJlcGx5IHJlcXVlc3QgY291bnQgYXMgd2VsbCAob3B0aW9uYWwsIGJ1dCBnb29kIGZvciBjb25zaXN0ZW5jeSlcbiAgICAgICAgc2V0UmVwbHlSZXF1ZXN0Q291bnQoMCk7XG4gICAgICB9XG4gICAgICByZXR1cm4gbmV3U3RhdGU7XG4gICAgfSk7XG4gIH0sIFtdKTtcblxuICBjb25zdCB0cmlnZ2VyUmVwbHlMaXN0ZW4gPSB1c2VDYWxsYmFjaygoKSA9PiB7XG4gICAgaWYgKGlzQXVkaW9Nb2RlRW5hYmxlZCkgeyAvLyBPbmx5IHRyaWdnZXIgaWYgYXVkaW8gbW9kZSBpcyBhY3R1YWxseSBlbmFibGVkXG4gICAgICAgIGNvbnNvbGUubG9nKFwiQXVkaW9Nb2RlQ29udGV4dDogdHJpZ2dlclJlcGx5TGlzdGVuIGNhbGxlZCwgaW5jcmVtZW50aW5nIHJlcGx5UmVxdWVzdENvdW50LlwiKTtcbiAgICAgICAgc2V0UmVwbHlSZXF1ZXN0Q291bnQocHJldiA9PiBwcmV2ICsgMSk7XG4gICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS5sb2coXCJBdWRpb01vZGVDb250ZXh0OiB0cmlnZ2VyUmVwbHlMaXN0ZW4gY2FsbGVkLCBidXQgQXVkaW8gTW9kZSBpcyBkaXNhYmxlZC4gTm8gYWN0aW9uIHRha2VuLlwiKTtcbiAgICB9XG4gIH0sIFtpc0F1ZGlvTW9kZUVuYWJsZWRdKTsgLy8gRGVwZW5kcyBvbiBpc0F1ZGlvTW9kZUVuYWJsZWQgdG8gZGVjaWRlIGlmIGl0IHNob3VsZCBhY3RcblxuICByZXR1cm4gKFxuICAgIDxBdWRpb01vZGVDb250ZXh0LlByb3ZpZGVyXG4gICAgICB2YWx1ZT17e1xuICAgICAgICBpc0F1ZGlvTW9kZUVuYWJsZWQsXG4gICAgICAgIHRvZ2dsZUF1ZGlvTW9kZSxcbiAgICAgICAgcmVwbHlSZXF1ZXN0Q291bnQsXG4gICAgICAgIHRyaWdnZXJSZXBseUxpc3RlbixcbiAgICAgIH19XG4gICAgPlxuICAgICAge2NoaWxkcmVufVxuICAgIDwvQXVkaW9Nb2RlQ29udGV4dC5Qcm92aWRlcj5cbiAgKTtcbn07XG5cbi8vIENyZWF0ZSBhIGN1c3RvbSBob29rIGZvciBjb252ZW5pZW5jZVxuZXhwb3J0IGNvbnN0IHVzZUF1ZGlvTW9kZSA9ICgpID0+IHtcbiAgY29uc3QgY29udGV4dCA9IHVzZUNvbnRleHQoQXVkaW9Nb2RlQ29udGV4dCk7XG4gIGlmIChjb250ZXh0ID09PSB1bmRlZmluZWQpIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ3VzZUF1ZGlvTW9kZSBtdXN0IGJlIHVzZWQgd2l0aGluIGFuIEF1ZGlvTW9kZVByb3ZpZGVyJyk7XG4gIH1cbiAgcmV0dXJuIGNvbnRleHQ7XG59O1xuIl19