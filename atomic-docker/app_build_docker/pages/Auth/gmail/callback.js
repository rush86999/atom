"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
// atomic-docker/app_build_docker/pages/auth/gmail/callback.tsx
const react_1 = require("react");
const router_1 = require("next/router");
const client_1 = require("@apollo/client");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const react_native_1 = require("react-native");
const react_2 = require("@chakra-ui/react");
const theme_1 = require("@lib/theme/theme");
// Define the GraphQL mutation
const HANDLE_GMAIL_AUTH_CALLBACK_MUTATION = (0, client_1.gql) `
  mutation HandleGmailAuthCallback($code: String!) {
    handleGmailAuthCallback(input: { code: $code }) {
      success
      message
    }
  }
`;
const GmailAuthCallbackPage = () => {
    const router = (0, router_1.useRouter)();
    const toast = (0, react_2.useToast)();
    const [statusMessage, setStatusMessage] = (0, react_1.useState)('Processing Gmail authorization...');
    const [isLoading, setIsLoading] = (0, react_1.useState)(true); // General loading for page setup and redirects
    const [handleCallbackMutation, { loading: mutationInProgress }] = (0, client_1.useMutation)(HANDLE_GMAIL_AUTH_CALLBACK_MUTATION);
    (0, react_1.useEffect)(() => {
        if (!router.isReady) {
            return; // Wait for router to be ready to access query params
        }
        const { code, error: googleError, error_description: googleErrorDescription } = router.query;
        if (googleError) {
            const description = googleErrorDescription || googleError || 'Unknown Google error.';
            console.error('Error from Google OAuth:', googleError, description);
            setStatusMessage(`Error from Google: ${description}`);
            toast({
                title: 'Gmail Connection Error',
                description: `Google authentication failed: ${description}`,
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
            setIsLoading(false);
            setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 5000);
            return;
        }
        if (typeof code === 'string' && code) {
            // Do not set isLoading to true here again if it's already true for the page
            // mutationInProgress will cover the mutation's loading state
            handleCallbackMutation({ variables: { code } })
                .then(response => {
                const { success, message } = response.data?.handleGmailAuthCallback || {};
                if (success) {
                    setStatusMessage(message || 'Gmail connected successfully!');
                    toast({
                        title: 'Gmail Connected',
                        description: message || 'Your Gmail account has been successfully connected.',
                        status: 'success',
                        duration: 5000,
                        isClosable: true,
                    });
                }
                else {
                    // Use message from backend if available, otherwise a generic one
                    throw new Error(message || 'Failed to process Gmail authorization with backend.');
                }
            })
                .catch(err => {
                console.error('Error handling Gmail auth callback mutation:', err);
                setStatusMessage(`Error: ${err.message || 'Could not complete Gmail connection.'}`);
                toast({
                    title: 'Gmail Connection Failed',
                    description: err.message || 'An unexpected error occurred while connecting your Gmail account.',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
            })
                .finally(() => {
                setIsLoading(false); // Page processing is done
                setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 3000);
            });
        }
        else if (router.isReady && !code) {
            // router.isReady but no code and no googleError
            setStatusMessage('Invalid callback state. No authorization code found.');
            toast({
                title: 'Gmail Connection Error',
                description: 'Invalid callback state. No authorization code provided by Google.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
            setIsLoading(false);
            setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 5000);
        }
    }, [router.isReady, router.query, handleCallbackMutation, router, toast]);
    // The initial page load might show "Processing..." briefly even before router is ready.
    // Consider a more nuanced loading state if that's an issue.
    const displayLoading = isLoading || mutationInProgress;
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", minHeight: "100vh", backgroundColor: "primaryCardBackground", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", mb: "l", children: statusMessage }), displayLoading && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.primary }), !displayLoading && ((0, jsx_runtime_1.jsx)(Text_1.default, { variant: "body", mt: "m", children: "You will be redirected shortly..." }))] }));
};
exports.default = GmailAuthCallbackPage;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsK0RBQStEO0FBQy9ELGlDQUFtRDtBQUNuRCx3Q0FBd0M7QUFDeEMsMkNBQWtEO0FBQ2xELGlFQUF5QztBQUN6QyxtRUFBMkM7QUFDM0MsK0NBQWlEO0FBQ2pELDRDQUE0QztBQUM1Qyw0Q0FBMkM7QUFFM0MsOEJBQThCO0FBQzlCLE1BQU0sbUNBQW1DLEdBQUcsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Q0FPOUMsQ0FBQztBQUVGLE1BQU0scUJBQXFCLEdBQUcsR0FBRyxFQUFFO0lBQ2pDLE1BQU0sTUFBTSxHQUFHLElBQUEsa0JBQVMsR0FBRSxDQUFDO0lBQzNCLE1BQU0sS0FBSyxHQUFHLElBQUEsZ0JBQVEsR0FBRSxDQUFDO0lBQ3pCLE1BQU0sQ0FBQyxhQUFhLEVBQUUsZ0JBQWdCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsbUNBQW1DLENBQUMsQ0FBQztJQUN4RixNQUFNLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLCtDQUErQztJQUVqRyxNQUFNLENBQUMsc0JBQXNCLEVBQUUsRUFBRSxPQUFPLEVBQUUsa0JBQWtCLEVBQUUsQ0FBQyxHQUFHLElBQUEsb0JBQVcsRUFDM0UsbUNBQW1DLENBQ3BDLENBQUM7SUFFRixJQUFBLGlCQUFTLEVBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLE1BQU0sQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNwQixPQUFPLENBQUMscURBQXFEO1FBQy9ELENBQUM7UUFFRCxNQUFNLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxXQUFXLEVBQUUsaUJBQWlCLEVBQUUsc0JBQXNCLEVBQUUsR0FBRyxNQUFNLENBQUMsS0FBSyxDQUFDO1FBRTdGLElBQUksV0FBVyxFQUFFLENBQUM7WUFDaEIsTUFB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Q0FBQyxLQUFLLENBQUMsQ0FBQztZQUNwQixVQUFVLENBQUMsR0FBRyxFQUFFLENBQUMsTUFBTSxDQUFDLElBQUksQ0FBQyxrREFBa0QsQ0FBQyxFQUFFLElBQUksQ0FBQyxDQUFDO1FBQzFGLENBQUM7SUFDSCxDQUFDLEVBQUUsQ0FBQyxNQUFNLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQyxLQUFLLEVBQUUsc0JBQXNCLEVBQUUsTUFBTSxFQUFFLEtBQUssQ0FBQyxDQUFDLENBQUM7SUFFMUUsd0ZBQXdGO0lBQ3hGLDREQUE0RDtJQUM1RCxNQUFNLGNBQWMsR0FBRyxTQUFTLElBQUksa0JBQWtCLENBQUM7SUFFdkQsT0FBTyxDQUNMLHdCQUFDLGFBQUcsSUFBQyxJQUFJLEVBQUUsQ0FBQyxFQUFFLGNBQWMsRUFBQyxRQUFRLEVBQUMsVUFBVSxFQUFDLFFBQVEsRUFBQyxTQUFTLEVBQUMsT0FBTyxFQUFDLGVBQWUsRUFBQyx1QkFBdUIsYUFDakgsdUJBQUMsY0FBSSxJQUFDLE9BQU8sRUFBQyxRQUFRLEVBQUMsRUFBRSxFQUFDLEdBQUcsWUFBRSxhQUFhLEdBQVEsRUFDbkQsY0FBYyxJQUFJLHVCQUFDLGdDQUFpQixJQUFDLElBQUksRUFBQyxPQUFPLEVBQUMsS0FBSyxFQUFFLGVBQU8sQ0FBQyxPQUFPLEdBQUksRUFDNUUsQ0FBQyxjQUFjLElBQUksQ0FDbEIsdUJBQUMsY0FBSSxJQUFDLE9BQU8sRUFBQyxNQUFNLEVBQUMsRUFBRSxFQUFDLEdBQUcsa0RBRXBCLENBQ1IsSUFDRyxDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxxQkFBcUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIGF0b21pYy1kb2NrZXIvYXBwX2J1aWxkX2RvY2tlci9wYWdlcy9hdXRoL2dtYWlsL2NhbGxiYWNrLnRzeFxuaW1wb3J0IFJlYWN0LCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCc7XG5pbXBvcnQgeyB1c2VSb3V0ZXIgfSBmcm9tICduZXh0L3JvdXRlcic7XG5pbXBvcnQgeyB1c2VNdXRhdGlvbiwgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94JztcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0JztcbmltcG9ydCB7IEFjdGl2aXR5SW5kaWNhdG9yIH0gZnJvbSAncmVhY3QtbmF0aXZlJztcbmltcG9ydCB7IHVzZVRvYXN0IH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCc7XG5pbXBvcnQgeyBwYWxldHRlIH0gZnJvbSAnQGxpYi90aGVtZS90aGVtZSc7XG5cbi8vIERlZmluZSB0aGUgR3JhcGhRTCBtdXRhdGlvblxuY29uc3QgSEFORExFX0dNQUlMX0FVVEhfQ0FMTEJBQ0tfTVVUQVRJT04gPSBncWxgXG4gIG11dGF0aW9uIEhhbmRsZUdtYWlsQXV0aENhbGxiYWNrKCRjb2RlOiBTdHJpbmchKSB7XG4gICAgaGFuZGxlR21haWxBdXRoQ2FsbGJhY2soaW5wdXQ6IHsgY29kZTogJGNvZGUgfSkge1xuICAgICAgc3VjY2Vzc1xuICAgICAgbWVzc2FnZVxuICAgIH1cbiAgfVxuYDtcblxuY29uc3QgR21haWxBdXRoQ2FsbGJhY2tQYWdlID0gKCkgPT4ge1xuICBjb25zdCByb3V0ZXIgPSB1c2VSb3V0ZXIoKTtcbiAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpO1xuICBjb25zdCBbc3RhdHVzTWVzc2FnZSwgc2V0U3RhdHVzTWVzc2FnZV0gPSB1c2VTdGF0ZSgnUHJvY2Vzc2luZyBHbWFpbCBhdXRob3JpemF0aW9uLi4uJyk7XG4gIGNvbnN0IFtpc0xvYWRpbmcsIHNldElzTG9hZGluZ10gPSB1c2VTdGF0ZSh0cnVlKTsgLy8gR2VuZXJhbCBsb2FkaW5nIGZvciBwYWdlIHNldHVwIGFuZCByZWRpcmVjdHNcblxuICBjb25zdCBbaGFuZGxlQ2FsbGJhY2tNdXRhdGlvbiwgeyBsb2FkaW5nOiBtdXRhdGlvbkluUHJvZ3Jlc3MgfV0gPSB1c2VNdXRhdGlvbihcbiAgICBIQU5ETEVfR01BSUxfQVVUSF9DQUxMQkFDS19NVVRBVElPTlxuICApO1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgaWYgKCFyb3V0ZXIuaXNSZWFkeSkge1xuICAgICAgcmV0dXJuOyAvLyBXYWl0IGZvciByb3V0ZXIgdG8gYmUgcmVhZHkgdG8gYWNjZXNzIHF1ZXJ5IHBhcmFtc1xuICAgIH1cblxuICAgIGNvbnN0IHsgY29kZSwgZXJyb3I6IGdvb2dsZUVycm9yLCBlcnJvcl9kZXNjcmlwdGlvbjogZ29vZ2xlRXJyb3JEZXNjcmlwdGlvbiB9ID0gcm91dGVyLnF1ZXJ5O1xuXG4gICAgaWYgKGdvb2dsZUVycm9yKSB7XG4gICAgICBjb25zdCBkZXNjcmlwdGlvbiA9IChnb29nbGVFcnJvckRlc2NyaXB0aW9uIGFzIHN0cmluZykgfHwgKGdvb2dsZUVycm9yIGFzIHN0cmluZykgfHwgJ1Vua25vd24gR29vZ2xlIGVycm9yLic7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBmcm9tIEdvb2dsZSBPQXV0aDonLCBnb29nbGVFcnJvciwgZGVzY3JpcHRpb24pO1xuICAgICAgc2V0U3RhdHVzTWVzc2FnZShgRXJyb3IgZnJvbSBHb29nbGU6ICR7ZGVzY3JpcHRpb259YCk7XG4gICAgICB0b2FzdCh7XG4gICAgICAgIHRpdGxlOiAnR21haWwgQ29ubmVjdGlvbiBFcnJvcicsXG4gICAgICAgIGRlc2NyaXB0aW9uOiBgR29vZ2xlIGF1dGhlbnRpY2F0aW9uIGZhaWxlZDogJHtkZXNjcmlwdGlvbn1gLFxuICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSk7XG4gICAgICBzZXRJc0xvYWRpbmcoZmFsc2UpO1xuICAgICAgc2V0VGltZW91dCgoKSA9PiByb3V0ZXIucHVzaCgnL1NldHRpbmdzL1VzZXJWaWV3Q2FsZW5kYXJBbmRDb250YWN0SW50ZWdyYXRpb25zJyksIDUwMDApO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGlmICh0eXBlb2YgY29kZSA9PT0gJ3N0cmluZycgJiYgY29kZSkge1xuICAgICAgLy8gRG8gbm90IHNldCBpc0xvYWRpbmcgdG8gdHJ1ZSBoZXJlIGFnYWluIGlmIGl0J3MgYWxyZWFkeSB0cnVlIGZvciB0aGUgcGFnZVxuICAgICAgLy8gbXV0YXRpb25JblByb2dyZXNzIHdpbGwgY292ZXIgdGhlIG11dGF0aW9uJ3MgbG9hZGluZyBzdGF0ZVxuICAgICAgaGFuZGxlQ2FsbGJhY2tNdXRhdGlvbih7IHZhcmlhYmxlczogeyBjb2RlIH0gfSlcbiAgICAgICAgLnRoZW4ocmVzcG9uc2UgPT4ge1xuICAgICAgICAgIGNvbnN0IHsgc3VjY2VzcywgbWVzc2FnZSB9ID0gcmVzcG9uc2UuZGF0YT8uaGFuZGxlR21haWxBdXRoQ2FsbGJhY2sgfHwge307XG4gICAgICAgICAgaWYgKHN1Y2Nlc3MpIHtcbiAgICAgICAgICAgIHNldFN0YXR1c01lc3NhZ2UobWVzc2FnZSB8fCAnR21haWwgY29ubmVjdGVkIHN1Y2Nlc3NmdWxseSEnKTtcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgdGl0bGU6ICdHbWFpbCBDb25uZWN0ZWQnLFxuICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogbWVzc2FnZSB8fCAnWW91ciBHbWFpbCBhY2NvdW50IGhhcyBiZWVuIHN1Y2Nlc3NmdWxseSBjb25uZWN0ZWQuJyxcbiAgICAgICAgICAgICAgc3RhdHVzOiAnc3VjY2VzcycsXG4gICAgICAgICAgICAgIGR1cmF0aW9uOiA1MDAwLFxuICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIFVzZSBtZXNzYWdlIGZyb20gYmFja2VuZCBpZiBhdmFpbGFibGUsIG90aGVyd2lzZSBhIGdlbmVyaWMgb25lXG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IobWVzc2FnZSB8fCAnRmFpbGVkIHRvIHByb2Nlc3MgR21haWwgYXV0aG9yaXphdGlvbiB3aXRoIGJhY2tlbmQuJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9KVxuICAgICAgICAuY2F0Y2goZXJyID0+IHtcbiAgICAgICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBoYW5kbGluZyBHbWFpbCBhdXRoIGNhbGxiYWNrIG11dGF0aW9uOicsIGVycik7XG4gICAgICAgICAgc2V0U3RhdHVzTWVzc2FnZShgRXJyb3I6ICR7ZXJyLm1lc3NhZ2UgfHwgJ0NvdWxkIG5vdCBjb21wbGV0ZSBHbWFpbCBjb25uZWN0aW9uLid9YCk7XG4gICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgdGl0bGU6ICdHbWFpbCBDb25uZWN0aW9uIEZhaWxlZCcsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogZXJyLm1lc3NhZ2UgfHwgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgY29ubmVjdGluZyB5b3VyIEdtYWlsIGFjY291bnQuJyxcbiAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgfSlcbiAgICAgICAgLmZpbmFsbHkoKCkgPT4ge1xuICAgICAgICAgIHNldElzTG9hZGluZyhmYWxzZSk7IC8vIFBhZ2UgcHJvY2Vzc2luZyBpcyBkb25lXG4gICAgICAgICAgc2V0VGltZW91dCgoKSA9PiByb3V0ZXIucHVzaCgnL1NldHRpbmdzL1VzZXJWaWV3Q2FsZW5kYXJBbmRDb250YWN0SW50ZWdyYXRpb25zJyksIDMwMDApO1xuICAgICAgICB9KTtcbiAgICB9IGVsc2UgaWYgKHJvdXRlci5pc1JlYWR5ICYmICFjb2RlKSB7XG4gICAgICAvLyByb3V0ZXIuaXNSZWFkeSBidXQgbm8gY29kZSBhbmQgbm8gZ29vZ2xlRXJyb3JcbiAgICAgIHNldFN0YXR1c01lc3NhZ2UoJ0ludmFsaWQgY2FsbGJhY2sgc3RhdGUuIE5vIGF1dGhvcml6YXRpb24gY29kZSBmb3VuZC4nKTtcbiAgICAgIHRvYXN0KHtcbiAgICAgICAgdGl0bGU6ICdHbWFpbCBDb25uZWN0aW9uIEVycm9yJyxcbiAgICAgICAgZGVzY3JpcHRpb246ICdJbnZhbGlkIGNhbGxiYWNrIHN0YXRlLiBObyBhdXRob3JpemF0aW9uIGNvZGUgcHJvdmlkZWQgYnkgR29vZ2xlLicsXG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KTtcbiAgICAgIHNldElzTG9hZGluZyhmYWxzZSk7XG4gICAgICBzZXRUaW1lb3V0KCgpID0+IHJvdXRlci5wdXNoKCcvU2V0dGluZ3MvVXNlclZpZXdDYWxlbmRhckFuZENvbnRhY3RJbnRlZ3JhdGlvbnMnKSwgNTAwMCk7XG4gICAgfVxuICB9LCBbcm91dGVyLmlzUmVhZHksIHJvdXRlci5xdWVyeSwgaGFuZGxlQ2FsbGJhY2tNdXRhdGlvbiwgcm91dGVyLCB0b2FzdF0pO1xuXG4gIC8vIFRoZSBpbml0aWFsIHBhZ2UgbG9hZCBtaWdodCBzaG93IFwiUHJvY2Vzc2luZy4uLlwiIGJyaWVmbHkgZXZlbiBiZWZvcmUgcm91dGVyIGlzIHJlYWR5LlxuICAvLyBDb25zaWRlciBhIG1vcmUgbnVhbmNlZCBsb2FkaW5nIHN0YXRlIGlmIHRoYXQncyBhbiBpc3N1ZS5cbiAgY29uc3QgZGlzcGxheUxvYWRpbmcgPSBpc0xvYWRpbmcgfHwgbXV0YXRpb25JblByb2dyZXNzO1xuXG4gIHJldHVybiAoXG4gICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBtaW5IZWlnaHQ9XCIxMDB2aFwiIGJhY2tncm91bmRDb2xvcj1cInByaW1hcnlDYXJkQmFja2dyb3VuZFwiPlxuICAgICAgPFRleHQgdmFyaWFudD1cImhlYWRlclwiIG1iPVwibFwiPntzdGF0dXNNZXNzYWdlfTwvVGV4dD5cbiAgICAgIHtkaXNwbGF5TG9hZGluZyAmJiA8QWN0aXZpdHlJbmRpY2F0b3Igc2l6ZT1cImxhcmdlXCIgY29sb3I9e3BhbGV0dGUucHJpbWFyeX0gLz59XG4gICAgICB7IWRpc3BsYXlMb2FkaW5nICYmIChcbiAgICAgICAgPFRleHQgdmFyaWFudD1cImJvZHlcIiBtdD1cIm1cIj5cbiAgICAgICAgICBZb3Ugd2lsbCBiZSByZWRpcmVjdGVkIHNob3J0bHkuLi5cbiAgICAgICAgPC9UZXh0PlxuICAgICAgKX1cbiAgICA8L0JveD5cbiAgKTtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IEdtYWlsQXV0aENhbGxiYWNrUGFnZTtcbiJdfQ==