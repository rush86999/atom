"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const Button_1 = __importDefault(require("@components/Button"));
const Select_1 = __importDefault(require("@components/common/Select"));
const VoiceSettings = () => {
    const [ttsProvider, setTtsProvider] = (0, react_1.useState)('elevenlabs');
    const [apiKey, setApiKey] = (0, react_1.useState)('');
    const [message, setMessage] = (0, react_1.useState)('');
    const [error, setError] = (0, react_1.useState)('');
    const [isLoading, setIsLoading] = (0, react_1.useState)(true);
    (0, react_1.useEffect)(() => {
        const fetchSettings = async () => {
            setIsLoading(true);
            try {
                const response = await fetch('/api/integrations/credentials?service=tts_provider');
                const data = await response.json();
                if (response.ok && data.value) {
                    setTtsProvider(data.value);
                    const keyResponse = await fetch(`/api/integrations/credentials?service=${data.value}_api_key`);
                    const keyData = await keyResponse.json();
                    if (keyResponse.ok && keyData.isConnected) {
                        setApiKey('********');
                    }
                }
            }
            catch (err) {
                setError('Failed to fetch voice settings.');
            }
            setIsLoading(false);
        };
        fetchSettings();
    }, []);
    const handleSave = async () => {
        setMessage('');
        setError('');
        try {
            // Save the provider choice
            await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: 'tts_provider', secret: ttsProvider }),
            });
            // Save the API key
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: `${ttsProvider}_api_key`, secret: apiKey }),
            });
            const data = await response.json();
            if (response.ok) {
                setMessage('Voice settings saved successfully.');
                setApiKey('********');
            }
            else {
                setError(data.message || 'Failed to save API key.');
            }
        }
        catch (err) {
            setError('Failed to connect to the server.');
        }
    };
    const providerOptions = [
        { label: 'ElevenLabs', value: 'elevenlabs' },
        { label: 'Deepgram', value: 'deepgram' },
    ];
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { marginTop: "m", paddingTop: "m", borderTopWidth: 1, borderColor: "hairline", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subHeader", marginBottom: "s", children: "Voice Settings" }), message && ((0, jsx_runtime_1.jsx)(Box_1.default, { backgroundColor: "green.100", padding: "s", marginBottom: "m", borderRadius: "s", children: (0, jsx_runtime_1.jsx)(Text_1.default, { color: "green.700", children: message }) })), error && ((0, jsx_runtime_1.jsx)(Box_1.default, { backgroundColor: "red.100", padding: "s", marginBottom: "m", borderRadius: "s", children: (0, jsx_runtime_1.jsx)(Text_1.default, { color: "red.700", children: error }) })), (0, jsx_runtime_1.jsx)(Select_1.default, { label: "TTS Provider", options: providerOptions, value: ttsProvider, onChange: (value) => {
                    setTtsProvider(value);
                    setApiKey(''); // Clear API key when provider changes
                }, placeholder: "Select a TTS provider" }), (0, jsx_runtime_1.jsx)("input", { type: "password", value: apiKey, onChange: (e) => setApiKey(e.target.value), placeholder: `Enter ${providerOptions.find(p => p.value === ttsProvider)?.label} API Key`, style: {
                    width: '100%',
                    padding: '8px',
                    marginTop: '8px',
                    marginBottom: '8px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                } }), (0, jsx_runtime_1.jsx)(Button_1.default, { onPress: handleSave, variant: "primary", title: "Save Voice Settings" })] }));
};
exports.default = VoiceSettings;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVm9pY2VTZXR0aW5ncy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlZvaWNlU2V0dGluZ3MudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLGlDQUFtRDtBQUNuRCxpRUFBeUM7QUFDekMsbUVBQTJDO0FBQzNDLGdFQUF3QztBQUN4Qyx1RUFBK0M7QUFFL0MsTUFBTSxhQUFhLEdBQUcsR0FBRyxFQUFFO0lBQ3pCLE1BQU0sQ0FBQyxXQUFXLEVBQUUsY0FBYyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLFlBQVksQ0FBQyxDQUFDO0lBQzdELE1BQU0sQ0FBQyxNQUFNLEVBQUUsU0FBUyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQ3pDLE1BQU0sQ0FBQyxPQUFPLEVBQUUsVUFBVSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQzNDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsUUFBUSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQ3ZDLE1BQU0sQ0FBQyxTQUFTLEVBQUUsWUFBWSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLElBQUksQ0FBQyxDQUFDO0lBRWpELElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixNQUFNLGFBQWEsR0FBRyxLQUFLLElBQUksRUFBRTtZQUMvQixZQUFZLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDbkIsSUFBSSxDQUFDO2dCQUNILE1BQU0sUUFBUSxHQUFHLE1BQU0sS0FBSyxDQUFDLG9EQUFvRCxDQUFDLENBQUM7Z0JBQ25GLE1BQU0sSUFBSSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO2dCQUNuQyxJQUFJLFFBQVEsQ0FBQyxFQUFFLElBQUksSUFBSSxDQUFDLEtBQUssRUFBRSxDQUFDO29CQUM5QixjQUFjLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO29CQUMzQixNQUFNLFdBQVcsR0FBRyxNQUFNLEtBQUssQ0FBQyx5Q0FBeUMsSUFBSSxDQUFDLEtBQUssVUFBVSxDQUFDLENBQUM7b0JBQy9GLE1BQU0sT0FBTyxHQUFHLE1BQU0sV0FBVyxDQUFDLElBQUksRUFBRSxDQUFDO29CQUN6QyxJQUFJLFdBQVcsQ0FBQyxFQUFFLElBQUksT0FBTyxDQUFDLFdBQVcsRUFBRSxDQUFDO3dCQUMxQyxTQUFTLENBQUMsVUFBVSxDQUFDLENBQUM7b0JBQ3hCLENBQUM7Z0JBQ0gsQ0FBQztZQUNILENBQUM7WUFBQyxPQUFPLEdBQUcsRUFBRSxDQUFDO2dCQUNiLFFBQVEsQ0FBQyxpQ0FBaUMsQ0FBQyxDQUFDO1lBQzlDLENBQUM7WUFDRCxZQUFZLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDdEIsQ0FBQyxDQUFDO1FBQ0YsYUFBYSxFQUFFLENBQUM7SUFDbEIsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBRVAsTUFBTSxVQUFVLEdBQUcsS0FBSyxJQUFJLEVBQUU7UUFDNUIsVUFBVSxDQUFDLEVBQUUsQ0FBQyxDQUFDO1FBQ2YsUUFBUSxDQUFDLEVBQUUsQ0FBQyxDQUFDO1FBQ2IsSUFBSSxDQUFDO1lBQ0gsMkJBQTJCO1lBQzNCLE1BQU0sS0FBSyxDQUFDLCtCQUErQixFQUFFO2dCQUMzQyxNQUFNLEVBQUUsTUFBTTtnQkFDZCxPQUFPLEVBQUUsRUFBRSxjQUFjLEVBQUUsa0JBQWtCLEVBQUU7Z0JBQy9DLElBQUksRUFBRSxJQUFJLENBQUMsU0FBUyxDQUFDLEVBQUUsT0FBTyxFQUFFLGNBQWMsRUFBRSxNQUFNLEVBQUUsV0FBVyxFQUFFLENBQUM7YUFDdkUsQ0FBQyxDQUFDO1lBRUgsbUJBQW1CO1lBQ25CLE1BQU0sUUFBUSxHQUFHLE1BQU0sS0FBSyxDQUFDLCtCQUErQixFQUFFO2dCQUM1RCxNQUFNLEVBQUUsTUFBTTtnQkFDZCxPQUFPLEVBQUUsRUFBRSxjQUFjLEVBQUUsa0JBQWtCLEVBQUU7Z0JBQy9DLElBQUksRUFBRSxJQUFJLENBQUMsU0FBUyxDQUFDLEVBQUUsT0FBTyxFQUFFLEdBQUcsV0FBVyxVQUFVLEVBQUUsTUFBTSxFQUFFLE1BQU0sRUFBRSxDQUFDO2FBQzVFLENBQUMsQ0FBQztZQUVILE1BQU0sSUFBSSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ25DLElBQUksUUFBUSxDQUFDLEVBQUUsRUFBRSxDQUFDO2dCQUNoQixVQUFVLENBQUMsb0NBQW9DLENBQUMsQ0FBQztnQkFDakQsU0FBUyxDQUFDLFVBQVUsQ0FBQyxDQUFDO1lBQ3hCLENBQUM7aUJBQU0sQ0FBQztnQkFDTixRQUFRLENBQUMsSUFBSSxDQUFDLE9BQU8sSUFBSSx5QkFBeUIsQ0FBQyxDQUFDO1lBQ3RELENBQUM7UUFDSCxDQUFDO1FBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztZQUNiLFFBQVEsQ0FBQyxrQ0FBa0MsQ0FBQyxDQUFDO1FBQy9DLENBQUM7SUFDSCxDQUFDLENBQUM7SUFFRixNQUFNLGVBQWUsR0FBRztRQUN0QixFQUFFLEtBQUssRUFBRSxZQUFZLEVBQUUsS0FBSyxFQUFFLFlBQVksRUFBRTtRQUM1QyxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRTtLQUN6QyxDQUFDO0lBRUYsT0FBTyxDQUNMLHdCQUFDLGFBQUcsSUFBQyxTQUFTLEVBQUMsR0FBRyxFQUFDLFVBQVUsRUFBQyxHQUFHLEVBQUMsY0FBYyxFQUFFLENBQUMsRUFBRSxXQUFXLEVBQUMsVUFBVSxhQUN6RSx1QkFBQyxjQUFJLElBQUMsT0FBTyxFQUFDLFdBQVcsRUFBQyxZQUFZLEVBQUMsR0FBRywrQkFFbkMsRUFDTixPQUFPLElBQUksQ0FDVix1QkFBQyxhQUFHLElBQUMsZUFBZSxFQUFDLFdBQVcsRUFBQyxPQUFPLEVBQUMsR0FBRyxFQUFDLFlBQVksRUFBQyxHQUFHLEVBQUMsWUFBWSxFQUFDLEdBQUcsWUFDNUUsdUJBQUMsY0FBSSxJQUFDLEtBQUssRUFBQyxXQUFXLFlBQUUsT0FBTyxHQUFRLEdBQ3BDLENBQ1AsRUFDQSxLQUFLLElBQUksQ0FDUix1QkFBQyxhQUFHLElBQUMsZUFBZSxFQUFDLFNBQVMsRUFBQyxPQUFPLEVBQUMsR0FBRyxFQUFDLFlBQVksRUFBQyxHQUFHLEVBQUMsWUFBWSxFQUFDLEdBQUcsWUFDMUUsdUJBQUMsY0FBSSxJQUFDLEtBQUssRUFBQyxTQUFTLFlBQUUsS0FBSyxHQUFRLEdBQ2hDLENBQ1AsRUFFRCx1QkFBQyxnQkFBTSxJQUNMLEtBQUssRUFBQyxjQUFjLEVBQ3BCLE9BQU8sRUFBRSxlQUFlLEVBQ3hCLEtBQUssRUFBRSxXQUFXLEVBQ2xCLFFBQVEsRUFBRSxDQUFDLEtBQUssRUFBRSxFQUFFO29CQUNsQixjQUFjLENBQUMsS0FBZSxDQUFDLENBQUM7b0JBQ2hDLFNBQVMsQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDLHNDQUFzQztnQkFDdkQsQ0FBQyxFQUNELFdBQVcsRUFBQyx1QkFBdUIsR0FDbkMsRUFFRixrQ0FDRSxJQUFJLEVBQUMsVUFBVSxFQUNmLEtBQUssRUFBRSxNQUFNLEVBQ2IsUUFBUSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsRUFDMUMsV0FBVyxFQUFFLFNBQVMsZUFBZSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQyxLQUFLLEtBQUssV0FBVyxDQUFDLEVBQUUsS0FBSyxVQUFVLEVBQ3pGLEtBQUssRUFBRTtvQkFDTCxLQUFLLEVBQUUsTUFBTTtvQkFDYixPQUFPLEVBQUUsS0FBSztvQkFDZCxTQUFTLEVBQUUsS0FBSztvQkFDaEIsWUFBWSxFQUFFLEtBQUs7b0JBQ25CLE1BQU0sRUFBRSxnQkFBZ0I7b0JBQ3hCLFlBQVksRUFBRSxLQUFLO2lCQUNwQixHQUNELEVBQ0YsdUJBQUMsZ0JBQU0sSUFBQyxPQUFPLEVBQUUsVUFBVSxFQUFFLE9BQU8sRUFBQyxTQUFTLEVBQUMsS0FBSyxFQUFDLHFCQUFxQixHQUFHLElBQ3pFLENBQ1AsQ0FBQztBQUNKLENBQUMsQ0FBQztBQUVGLGtCQUFlLGFBQWEsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VTdGF0ZSwgdXNlRWZmZWN0IH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94JztcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0JztcbmltcG9ydCBCdXR0b24gZnJvbSAnQGNvbXBvbmVudHMvQnV0dG9uJztcbmltcG9ydCBTZWxlY3QgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1NlbGVjdCc7XG5cbmNvbnN0IFZvaWNlU2V0dGluZ3MgPSAoKSA9PiB7XG4gIGNvbnN0IFt0dHNQcm92aWRlciwgc2V0VHRzUHJvdmlkZXJdID0gdXNlU3RhdGUoJ2VsZXZlbmxhYnMnKTtcbiAgY29uc3QgW2FwaUtleSwgc2V0QXBpS2V5XSA9IHVzZVN0YXRlKCcnKTtcbiAgY29uc3QgW21lc3NhZ2UsIHNldE1lc3NhZ2VdID0gdXNlU3RhdGUoJycpO1xuICBjb25zdCBbZXJyb3IsIHNldEVycm9yXSA9IHVzZVN0YXRlKCcnKTtcbiAgY29uc3QgW2lzTG9hZGluZywgc2V0SXNMb2FkaW5nXSA9IHVzZVN0YXRlKHRydWUpO1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgY29uc3QgZmV0Y2hTZXR0aW5ncyA9IGFzeW5jICgpID0+IHtcbiAgICAgIHNldElzTG9hZGluZyh0cnVlKTtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvaW50ZWdyYXRpb25zL2NyZWRlbnRpYWxzP3NlcnZpY2U9dHRzX3Byb3ZpZGVyJyk7XG4gICAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICAgIGlmIChyZXNwb25zZS5vayAmJiBkYXRhLnZhbHVlKSB7XG4gICAgICAgICAgc2V0VHRzUHJvdmlkZXIoZGF0YS52YWx1ZSk7XG4gICAgICAgICAgY29uc3Qga2V5UmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHM/c2VydmljZT0ke2RhdGEudmFsdWV9X2FwaV9rZXlgKTtcbiAgICAgICAgICBjb25zdCBrZXlEYXRhID0gYXdhaXQga2V5UmVzcG9uc2UuanNvbigpO1xuICAgICAgICAgIGlmIChrZXlSZXNwb25zZS5vayAmJiBrZXlEYXRhLmlzQ29ubmVjdGVkKSB7XG4gICAgICAgICAgICBzZXRBcGlLZXkoJyoqKioqKioqJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlcnIpIHtcbiAgICAgICAgc2V0RXJyb3IoJ0ZhaWxlZCB0byBmZXRjaCB2b2ljZSBzZXR0aW5ncy4nKTtcbiAgICAgIH1cbiAgICAgIHNldElzTG9hZGluZyhmYWxzZSk7XG4gICAgfTtcbiAgICBmZXRjaFNldHRpbmdzKCk7XG4gIH0sIFtdKTtcblxuICBjb25zdCBoYW5kbGVTYXZlID0gYXN5bmMgKCkgPT4ge1xuICAgIHNldE1lc3NhZ2UoJycpO1xuICAgIHNldEVycm9yKCcnKTtcbiAgICB0cnkge1xuICAgICAgLy8gU2F2ZSB0aGUgcHJvdmlkZXIgY2hvaWNlXG4gICAgICBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAndHRzX3Byb3ZpZGVyJywgc2VjcmV0OiB0dHNQcm92aWRlciB9KSxcbiAgICAgIH0pO1xuXG4gICAgICAvLyBTYXZlIHRoZSBBUEkga2V5XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKCcvYXBpL2ludGVncmF0aW9ucy9jcmVkZW50aWFscycsIHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIGhlYWRlcnM6IHsgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyB9LFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHNlcnZpY2U6IGAke3R0c1Byb3ZpZGVyfV9hcGlfa2V5YCwgc2VjcmV0OiBhcGlLZXkgfSksXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICBzZXRNZXNzYWdlKCdWb2ljZSBzZXR0aW5ncyBzYXZlZCBzdWNjZXNzZnVsbHkuJyk7XG4gICAgICAgIHNldEFwaUtleSgnKioqKioqKionKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldEVycm9yKGRhdGEubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNhdmUgQVBJIGtleS4nKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnIpIHtcbiAgICAgIHNldEVycm9yKCdGYWlsZWQgdG8gY29ubmVjdCB0byB0aGUgc2VydmVyLicpO1xuICAgIH1cbiAgfTtcblxuICBjb25zdCBwcm92aWRlck9wdGlvbnMgPSBbXG4gICAgeyBsYWJlbDogJ0VsZXZlbkxhYnMnLCB2YWx1ZTogJ2VsZXZlbmxhYnMnIH0sXG4gICAgeyBsYWJlbDogJ0RlZXBncmFtJywgdmFsdWU6ICdkZWVwZ3JhbScgfSxcbiAgXTtcblxuICByZXR1cm4gKFxuICAgIDxCb3ggbWFyZ2luVG9wPVwibVwiIHBhZGRpbmdUb3A9XCJtXCIgYm9yZGVyVG9wV2lkdGg9ezF9IGJvcmRlckNvbG9yPVwiaGFpcmxpbmVcIj5cbiAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJIZWFkZXJcIiBtYXJnaW5Cb3R0b209XCJzXCI+XG4gICAgICAgIFZvaWNlIFNldHRpbmdzXG4gICAgICA8L1RleHQ+XG4gICAgICB7bWVzc2FnZSAmJiAoXG4gICAgICAgIDxCb3ggYmFja2dyb3VuZENvbG9yPVwiZ3JlZW4uMTAwXCIgcGFkZGluZz1cInNcIiBtYXJnaW5Cb3R0b209XCJtXCIgYm9yZGVyUmFkaXVzPVwic1wiPlxuICAgICAgICAgIDxUZXh0IGNvbG9yPVwiZ3JlZW4uNzAwXCI+e21lc3NhZ2V9PC9UZXh0PlxuICAgICAgICA8L0JveD5cbiAgICAgICl9XG4gICAgICB7ZXJyb3IgJiYgKFxuICAgICAgICA8Qm94IGJhY2tncm91bmRDb2xvcj1cInJlZC4xMDBcIiBwYWRkaW5nPVwic1wiIG1hcmdpbkJvdHRvbT1cIm1cIiBib3JkZXJSYWRpdXM9XCJzXCI+XG4gICAgICAgICAgPFRleHQgY29sb3I9XCJyZWQuNzAwXCI+e2Vycm9yfTwvVGV4dD5cbiAgICAgICAgPC9Cb3g+XG4gICAgICApfVxuICAgICAgXG4gICAgICA8U2VsZWN0XG4gICAgICAgIGxhYmVsPVwiVFRTIFByb3ZpZGVyXCJcbiAgICAgICAgb3B0aW9ucz17cHJvdmlkZXJPcHRpb25zfVxuICAgICAgICB2YWx1ZT17dHRzUHJvdmlkZXJ9XG4gICAgICAgIG9uQ2hhbmdlPXsodmFsdWUpID0+IHtcbiAgICAgICAgICBzZXRUdHNQcm92aWRlcih2YWx1ZSBhcyBzdHJpbmcpO1xuICAgICAgICAgIHNldEFwaUtleSgnJyk7IC8vIENsZWFyIEFQSSBrZXkgd2hlbiBwcm92aWRlciBjaGFuZ2VzXG4gICAgICAgIH19XG4gICAgICAgIHBsYWNlaG9sZGVyPVwiU2VsZWN0IGEgVFRTIHByb3ZpZGVyXCJcbiAgICAgIC8+XG5cbiAgICAgIDxpbnB1dFxuICAgICAgICB0eXBlPVwicGFzc3dvcmRcIlxuICAgICAgICB2YWx1ZT17YXBpS2V5fVxuICAgICAgICBvbkNoYW5nZT17KGUpID0+IHNldEFwaUtleShlLnRhcmdldC52YWx1ZSl9XG4gICAgICAgIHBsYWNlaG9sZGVyPXtgRW50ZXIgJHtwcm92aWRlck9wdGlvbnMuZmluZChwID0+IHAudmFsdWUgPT09IHR0c1Byb3ZpZGVyKT8ubGFiZWx9IEFQSSBLZXlgfVxuICAgICAgICBzdHlsZT17e1xuICAgICAgICAgIHdpZHRoOiAnMTAwJScsXG4gICAgICAgICAgcGFkZGluZzogJzhweCcsXG4gICAgICAgICAgbWFyZ2luVG9wOiAnOHB4JyxcbiAgICAgICAgICBtYXJnaW5Cb3R0b206ICc4cHgnLFxuICAgICAgICAgIGJvcmRlcjogJzFweCBzb2xpZCAjY2NjJyxcbiAgICAgICAgICBib3JkZXJSYWRpdXM6ICc0cHgnLFxuICAgICAgICB9fVxuICAgICAgLz5cbiAgICAgIDxCdXR0b24gb25QcmVzcz17aGFuZGxlU2F2ZX0gdmFyaWFudD1cInByaW1hcnlcIiB0aXRsZT1cIlNhdmUgVm9pY2UgU2V0dGluZ3NcIiAvPlxuICAgIDwvQm94PlxuICApO1xufTtcblxuZXhwb3J0IGRlZmF1bHQgVm9pY2VTZXR0aW5ncztcbiJdfQ==