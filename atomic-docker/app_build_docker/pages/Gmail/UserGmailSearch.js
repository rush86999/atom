"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const client_1 = require("@apollo/client");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const Button_1 = __importDefault(require("@components/Button"));
const TextField_1 = __importDefault(require("@components/TextField"));
const react_native_1 = require("react-native");
const theme_1 = require("@lib/theme/theme");
const react_2 = require("@chakra-ui/react");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
const backendConfig_1 = require("@config/backendConfig");
async function getServerSideProps({ req, res }) {
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
    let session;
    try {
        session = await session_1.default.getSession(req, res, {
            overrideGlobalClaimValidators: async () => [],
        });
    }
    catch (err) {
        if (err.type === session_1.default.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        else if (err.type === session_1.default.Error.UNAUTHORISED) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        throw err;
    }
    if (!session?.getUserId()) {
        return {
            redirect: {
                destination: '/User/Login/UserLogin',
                permanent: false,
            },
        };
    }
    return { props: { userId: session.getUserId() } };
}
const SEARCH_USER_GMAIL_MUTATION = (0, client_1.gql) `
  mutation SearchUserGmail($input: GmailSearchQueryInput!) {
    searchUserGmail(input: $input) {
      success
      message
      results {
        id
        threadId
        snippet
        subject
        from
        date
      }
    }
  }
`;
const CREATE_EMAIL_REMINDER_MUTATION = (0, client_1.gql) `
  mutation CreateEmailReminder($input: CreateEmailReminderInput!) {
    createEmailReminder(input: $input) {
      id
    }
  }
`;
const GET_USER_GMAIL_CONTENT_MUTATION = (0, client_1.gql) `
  mutation GetUserGmailContent($input: GetUserGmailContentInput!) {
    getUserGmailContent(input: $input) {
      success
      message
      email {
        id
        threadId
        snippet
        subject
        from
        date
        body
      }
    }
  }
`;
const UserGmailSearchPage = () => {
    const [searchQuery, setSearchQuery] = (0, react_1.useState)('');
    const [searchResults, setSearchResults] = (0, react_1.useState)([]);
    const toast = (0, react_2.useToast)();
    const [selectedEmail, setSelectedEmail] = (0, react_1.useState)(null);
    const [isDetailLoading, setIsDetailLoading] = (0, react_1.useState)(false);
    const [showDetailModal, setShowDetailModal] = (0, react_1.useState)(false);
    const [showReminderModal, setShowReminderModal] = (0, react_1.useState)(false);
    const [reminderDate, setReminderDate] = (0, react_1.useState)(new Date());
    const [searchGmailMutation, { loading: searchLoading, error: searchError }] = (0, client_1.useMutation)(SEARCH_USER_GMAIL_MUTATION, {
        onCompleted: (data) => {
            if (data.searchUserGmail.success) {
                const results = data.searchUserGmail.results || [];
                setSearchResults(results);
                if (results.length === 0 && searchQuery.trim() !== '') {
                    toast({
                        title: 'No Search Results',
                        description: 'Your search did not return any emails.',
                        status: 'info',
                        duration: 3000,
                        isClosable: true,
                    });
                }
            }
            else {
                toast({
                    title: 'Search Failed',
                    description: data.searchUserGmail.message || 'An error occurred during the search.',
                    status: 'error',
                    duration: 5000,
                    isClosable: true,
                });
                setSearchResults([]);
            }
        },
        onError: (err) => {
            toast({
                title: 'Search Error',
                description: err.message || 'An unexpected error occurred.',
                status: 'error',
                duration: 5000,
                isClosable: true,
            });
            setSearchResults([]);
        },
    });
    const [getGmailContentMutation, { loading: detailFetchLoading, error: detailFetchError },] = (0, client_1.useMutation)(GET_USER_GMAIL_CONTENT_MUTATION, {
        onCompleted: (data) => {
            setIsDetailLoading(false);
            if (data.getUserGmailContent.success && data.getUserGmailContent.email) {
                const emailData = data.getUserGmailContent.email;
                setSelectedEmail({
                    id: emailData.id,
                    threadId: emailData.threadId || null,
                    subject: emailData.subject || null,
                    from: emailData.from || null,
                    date: emailData.date || null,
                    body: emailData.body || null,
                    snippet: emailData.snippet || null,
                });
            }
            else {
                toast({
                    title: 'Error Fetching Email Details',
                    description: data.getUserGmailContent.message || 'Could not load email details.',
                    status: 'error',
                    duration: 5000,
                    isClosable: true,
                });
                setSelectedEmail(null);
                setShowDetailModal(false);
            }
        },
        onError: (err) => {
            setIsDetailLoading(false);
            toast({
                title: 'Error Fetching Email Details',
                description: err.message || 'An unexpected error occurred.',
                status: 'error',
                duration: 5000,
                isClosable: true,
            });
            setSelectedEmail(null);
            setShowDetailModal(false);
        },
    });
    const [createEmailReminderMutation, { loading: reminderLoading, error: reminderError }] = (0, client_1.useMutation)(CREATE_EMAIL_REMINDER_MUTATION, {
        onCompleted: (data) => {
            if (data.createEmailReminder.id) {
                toast({
                    title: 'Reminder Set',
                    description: 'Your reminder has been set successfully.',
                    status: 'success',
                    duration: 3000,
                    isClosable: true,
                });
                setShowReminderModal(false);
            }
            else {
                toast({
                    title: 'Failed to Set Reminder',
                    description: 'An error occurred while setting the reminder.',
                    status: 'error',
                    duration: 5000,
                    isClosable: true,
                });
            }
        },
        onError: (err) => {
            toast({
                title: 'Reminder Error',
                description: err.message || 'An unexpected error occurred.',
                status: 'error',
                duration: 5000,
                isClosable: true,
            });
        },
    });
    const handleSetReminder = () => {
        if (selectedEmail) {
            createEmailReminderMutation({
                variables: {
                    input: {
                        emailId: selectedEmail.id,
                        service: 'gmail',
                        remindAt: reminderDate.toISOString(),
                    },
                },
            });
        }
    };
    const handleSearch = () => {
        if (searchQuery.trim() === '') {
            toast({
                title: 'Empty Search Query',
                description: 'Please enter a search query.',
                status: 'warning',
                duration: 3000,
                isClosable: true,
            });
            return;
        }
        setShowDetailModal(false); // Close detail modal on new search
        setSelectedEmail(null);
        setSearchResults([]);
        searchGmailMutation({ variables: { input: { query: searchQuery, maxResults: 20 } } });
    };
    const handleViewDetails = (emailId) => {
        if (!emailId)
            return;
        setSelectedEmail(null);
        setIsDetailLoading(true);
        setShowDetailModal(true);
        getGmailContentMutation({ variables: { input: { emailId } } });
    };
    const renderItem = ({ item }) => ((0, jsx_runtime_1.jsxs)(react_native_1.Pressable, { onPress: () => handleViewDetails(item.id), style: styles.itemContainer, children: [(0, jsx_runtime_1.jsxs)(Text_1.default, { style: styles.itemTextStrong, children: ["ID: ", item.id] }), item.snippet && (0, jsx_runtime_1.jsxs)(Text_1.default, { style: styles.itemText, numberOfLines: 2, children: ["Snippet: ", item.snippet] }), item.subject && (0, jsx_runtime_1.jsxs)(Text_1.default, { style: styles.itemText, children: ["Subject: ", item.subject] }), item.from && (0, jsx_runtime_1.jsxs)(Text_1.default, { style: styles.itemText, children: ["From: ", item.from] }), item.date && (0, jsx_runtime_1.jsxs)(Text_1.default, { style: styles.itemText, children: ["Date: ", item.date] }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.viewDetailsLink, children: "View Details" })] }));
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, p: "m", alignItems: "center", backgroundColor: "primaryCardBackground", style: styles.pageContainer, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", mb: "l", style: styles.headerText, children: "Search Your Gmail" }), (0, jsx_runtime_1.jsx)(Box_1.default, { width: "100%", maxWidth: 600, mb: "m", children: (0, jsx_runtime_1.jsx)(TextField_1.default, { placeholder: "e.g., from:name@example.com subject:contract", value: searchQuery, onChangeText: setSearchQuery }) }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Search Emails", onClick: handleSearch, disabled: searchLoading }), searchLoading && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.primary, style: styles.activityIndicator }), searchError && ((0, jsx_runtime_1.jsxs)(Text_1.default, { color: "error", mt: "m", style: styles.errorText, children: ["Error searching: ", searchError.message] })), !searchLoading && searchResults.length > 0 && ((0, jsx_runtime_1.jsx)(react_native_1.FlatList, { data: searchResults, renderItem: renderItem, keyExtractor: (item) => item.id, style: styles.listStyle })), !searchLoading && !searchError && searchResults.length === 0 && searchQuery !== '' && ((0, jsx_runtime_1.jsx)(Text_1.default, { mt: "m", style: styles.itemText, children: "No results found for your query." })), showDetailModal && ((0, jsx_runtime_1.jsx)(react_native_1.Modal, { animationType: "slide", transparent: true, visible: showDetailModal, onRequestClose: () => {
                    setShowDetailModal(false);
                    setSelectedEmail(null);
                }, children: (0, jsx_runtime_1.jsx)(react_native_1.View, { style: styles.modalOverlay, children: (0, jsx_runtime_1.jsxs)(react_native_1.View, { style: styles.modalContainer, children: [(0, jsx_runtime_1.jsxs)(react_native_1.ScrollView, { children: [isDetailLoading && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.primary }), detailFetchError && (0, jsx_runtime_1.jsxs)(Text_1.default, { color: "error", children: ["Error loading details: ", detailFetchError.message] }), selectedEmail && !isDetailLoading && ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTitle, children: "Email Details" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "ID:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalText, children: selectedEmail.id }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "Subject:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalText, children: selectedEmail.subject || 'N/A' }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "From:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalText, children: selectedEmail.from || 'N/A' }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "Date:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalText, children: selectedEmail.date || 'N/A' }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "Snippet:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalText, children: selectedEmail.snippet || 'N/A' }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextStrong, children: "Body:" }), (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTextBody, children: selectedEmail.body || '(No body content)' })] }))] }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Remind me", onClick: () => setShowReminderModal(true) }), (0, jsx_runtime_1.jsx)(react_native_1.Pressable, { style: styles.closeButton, onPress: () => {
                                    setShowDetailModal(false);
                                    setSelectedEmail(null);
                                }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.closeButtonText, children: "Close" }) })] }) }) })), showReminderModal && ((0, jsx_runtime_1.jsx)(react_native_1.Modal, { animationType: "slide", transparent: true, visible: showReminderModal, onRequestClose: () => setShowReminderModal(false), children: (0, jsx_runtime_1.jsx)(react_native_1.View, { style: styles.modalOverlay, children: (0, jsx_runtime_1.jsxs)(react_native_1.View, { style: styles.modalContainer, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.modalTitle, children: "Set Reminder" }), (0, jsx_runtime_1.jsx)(Text_1.default, { children: "Select a date and time for your reminder:" }), (0, jsx_runtime_1.jsx)(TextField_1.default, { placeholder: "YYYY-MM-DDTHH:mm:ss.sssZ", value: reminderDate.toISOString(), onChangeText: (text) => setReminderDate(new Date(text)) }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Set Reminder", onClick: handleSetReminder, disabled: reminderLoading }), (0, jsx_runtime_1.jsx)(react_native_1.Pressable, { style: styles.closeButton, onPress: () => setShowReminderModal(false), children: (0, jsx_runtime_1.jsx)(Text_1.default, { style: styles.closeButtonText, children: "Cancel" }) })] }) }) }))] }));
};
const styles = react_native_1.StyleSheet.create({
    pageContainer: {
        paddingTop: 20,
    },
    headerText: {
        color: theme_1.palette.text,
    },
    itemContainer: {
        padding: 15,
        borderBottomWidth: 1,
        borderBottomColor: theme_1.palette.mediumGray,
        backgroundColor: theme_1.palette.white,
        borderRadius: 5,
        marginVertical: 5,
    },
    itemText: {
        fontSize: 14,
        color: theme_1.palette.text,
        marginBottom: 3,
    },
    itemTextStrong: {
        fontSize: 14,
        fontWeight: 'bold',
        color: theme_1.palette.text,
        marginBottom: 3,
    },
    viewDetailsLink: {
        fontSize: 14,
        color: theme_1.palette.primary, // Use primary color for link
        marginTop: 5,
        textDecorationLine: 'underline',
    },
    activityIndicator: {
        marginTop: 20,
    },
    errorText: {
        fontSize: 14,
        color: theme_1.palette.error, // Ensure palette has an error color
    },
    listStyle: {
        width: '100%',
        maxWidth: 600,
        marginTop: 20,
    },
    // Modal styles
    modalOverlay: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: 'rgba(0,0,0,0.5)', // Semi-transparent background
    },
    modalContainer: {
        width: '90%',
        maxWidth: 600,
        maxHeight: '80%',
        backgroundColor: theme_1.palette.white,
        borderRadius: 10,
        padding: 20,
        shadowColor: '#000',
        shadowOffset: {
            width: 0,
            height: 2,
        },
        shadowOpacity: 0.25,
        shadowRadius: 4,
        elevation: 5,
    },
    modalTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        marginBottom: 15,
        color: theme_1.palette.text,
        textAlign: 'center',
    },
    modalTextStrong: {
        fontSize: 15,
        fontWeight: 'bold',
        marginTop: 10,
        color: theme_1.palette.text,
    },
    modalText: {
        fontSize: 14,
        marginBottom: 5,
        color: theme_1.palette.textSecondary, // Assuming a secondary text color
    },
    modalTextBody: {
        fontSize: 14,
        marginBottom: 5,
        color: theme_1.palette.textSecondary,
        marginTop: 5,
        borderWidth: 1,
        borderColor: theme_1.palette.lightGray, // Assuming lightGray
        padding: 10,
        borderRadius: 3,
        maxHeight: 200, // Make body scrollable if too long, but ScrollView handles this
    },
    closeButton: {
        marginTop: 20,
        backgroundColor: theme_1.palette.primary,
        paddingVertical: 10,
        paddingHorizontal: 20,
        borderRadius: 5,
        alignSelf: 'center',
    },
    closeButtonText: {
        color: theme_1.palette.white,
        fontWeight: 'bold',
        textAlign: 'center',
    },
});
exports.default = UserGmailSearchPage;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckdtYWlsU2VhcmNoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlckdtYWlsU2VhcmNoLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWNBLGdEQXlCQzs7QUF2Q0QsaUNBQXdDO0FBQ3hDLDJDQUFrRDtBQUNsRCxpRUFBeUM7QUFDekMsbUVBQTJDO0FBQzNDLGdFQUF3QztBQUN4QyxzRUFBOEM7QUFDOUMsK0NBQTJHO0FBQzNHLDRDQUEyQztBQUMzQyw0Q0FBNEM7QUFFNUMsd0VBQStDO0FBQy9DLDhFQUFzRDtBQUN0RCx5REFBc0Q7QUFFL0MsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDbEcsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQztJQUN0QyxJQUFJLE9BQU8sQ0FBQztJQUNaLElBQUksQ0FBQztRQUNILE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDM0MsNkJBQTZCLEVBQUUsS0FBSyxJQUFJLEVBQUUsQ0FBQyxFQUFFO1NBQzlDLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2xCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2pELE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQztRQUN6RCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ25ELE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQztRQUN6RCxDQUFDO1FBQ0QsTUFBTSxHQUFHLENBQUM7SUFDWixDQUFDO0lBRUQs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QVUsRUFBRSxNQUFNO1FBQ2xCLFNBQVMsRUFBRSxFQUFFO1FBQ2IsS0FBSyxFQUFFLGVBQU8sQ0FBQyxJQUFJO0tBQ3BCO0lBQ0QsU0FBUyxFQUFFO1FBQ1QsUUFBUSxFQUFFLEVBQUU7UUFDWixZQUFZLEVBQUUsQ0FBQztRQUNmLEtBQUssRUFBRSxlQUFPLENBQUMsYUFBYSxFQUFFLGtDQUFrQztLQUNqRTtJQUNELGFBQWEsRUFBRTtRQUNiLFFBQVEsRUFBRSxFQUFFO1FBQ1osWUFBWSxFQUFFLENBQUM7UUFDZixLQUFLLEVBQUUsZUFBTyxDQUFDLGFBQWE7UUFDNUIsU0FBUyxFQUFFLENBQUM7UUFDWixXQUFXLEVBQUUsQ0FBQztRQUNkLFdBQVcsRUFBRSxlQUFPLENBQUMsU0FBUyxFQUFFLHFCQUFxQjtRQUNyRCxPQUFPLEVBQUUsRUFBRTtRQUNYLFlBQVksRUFBRSxDQUFDO1FBQ2YsU0FBUyxFQUFFLEdBQUcsRUFBRSxnRUFBZ0U7S0FDakY7SUFDRCxXQUFXLEVBQUU7UUFDWCxTQUFTLEVBQUUsRUFBRTtRQUNiLGVBQWUsRUFBRSxlQUFPLENBQUMsT0FBTztRQUNoQyxlQUFlLEVBQUUsRUFBRTtRQUNuQixpQkFBaUIsRUFBRSxFQUFFO1FBQ3JCLFlBQVksRUFBRSxDQUFDO1FBQ2YsU0FBUyxFQUFFLFFBQVE7S0FDcEI7SUFDRCxlQUFlLEVBQUU7UUFDZixLQUFLLEVBQUUsZUFBTyxDQUFDLEtBQUs7UUFDcEIsVUFBVSxFQUFFLE1BQU07UUFDbEIsU0FBUyxFQUFFLFFBQVE7S0FDcEI7Q0FDRixDQUFDLENBQUM7QUFFSCxrQkFBZSxtQkFBbUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VTdGF0ZSB9IGZyb20gJ3JlYWN0JztcbmltcG9ydCB7IHVzZU11dGF0aW9uLCBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnO1xuaW1wb3J0IFRleHQgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1RleHQnO1xuaW1wb3J0IEJ1dHRvbiBmcm9tICdAY29tcG9uZW50cy9CdXR0b24nO1xuaW1wb3J0IFRleHRGaWVsZCBmcm9tICdAY29tcG9uZW50cy9UZXh0RmllbGQnO1xuaW1wb3J0IHsgQWN0aXZpdHlJbmRpY2F0b3IsIEZsYXRMaXN0LCBWaWV3LCBTdHlsZVNoZWV0LCBQcmVzc2FibGUsIE1vZGFsLCBTY3JvbGxWaWV3IH0gZnJvbSAncmVhY3QtbmF0aXZlJztcbmltcG9ydCB7IHBhbGV0dGUgfSBmcm9tICdAbGliL3RoZW1lL3RoZW1lJztcbmltcG9ydCB7IHVzZVRvYXN0IH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCc7XG5pbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgc3VwZXJ0b2tlbnNOb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUnO1xuaW1wb3J0IFNlc3Npb24gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnQGNvbmZpZy9iYWNrZW5kQ29uZmlnJztcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFNlcnZlclNpZGVQcm9wcyh7IHJlcSwgcmVzIH06IHsgcmVxOiBOZXh0QXBpUmVxdWVzdCwgcmVzOiBOZXh0QXBpUmVzcG9uc2UgfSkge1xuICBzdXBlcnRva2Vuc05vZGUuaW5pdChiYWNrZW5kQ29uZmlnKCkpO1xuICBsZXQgc2Vzc2lvbjtcbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgKCkgPT4gW10sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGVycjogYW55KSB7XG4gICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH07XG4gICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfTtcbiAgICB9XG4gICAgdGhyb3cgZXJyO1xuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgcmV0dXJuIHsgcHJvcHM6IHsgdXNlcklkOiBzZXNzaW9uLmdldFVzZXJJZCgpIH0gfTtcbn1cblxuY29uc3QgU0VBUkNIX1VTRVJfR01BSUxfTVVUQVRJT04gPSBncWxgXG4gIG11dGF0aW9uIFNlYXJjaFVzZXJHbWFpbCgkaW5wdXQ6IEdtYWlsU2VhcmNoUXVlcnlJbnB1dCEpIHtcbiAgICBzZWFyY2hVc2VyR21haWwoaW5wdXQ6ICRpbnB1dCkge1xuICAgICAgc3VjY2Vzc1xuICAgICAgbWVzc2FnZVxuICAgICAgcmVzdWx0cyB7XG4gICAgICAgIGlkXG4gICAgICAgIHRocmVhZElkXG4gICAgICAgIHNuaXBwZXRcbiAgICAgICAgc3ViamVjdFxuICAgICAgICBmcm9tXG4gICAgICAgIGRhdGVcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG5cbmNvbnN0IENSRUFURV9FTUFJTF9SRU1JTkRFUl9NVVRBVElPTiA9IGdxbGBcbiAgbXV0YXRpb24gQ3JlYXRlRW1haWxSZW1pbmRlcigkaW5wdXQ6IENyZWF0ZUVtYWlsUmVtaW5kZXJJbnB1dCEpIHtcbiAgICBjcmVhdGVFbWFpbFJlbWluZGVyKGlucHV0OiAkaW5wdXQpIHtcbiAgICAgIGlkXG4gICAgfVxuICB9XG5gO1xuXG5jb25zdCBHRVRfVVNFUl9HTUFJTF9DT05URU5UX01VVEFUSU9OID0gZ3FsYFxuICBtdXRhdGlvbiBHZXRVc2VyR21haWxDb250ZW50KCRpbnB1dDogR2V0VXNlckdtYWlsQ29udGVudElucHV0ISkge1xuICAgIGdldFVzZXJHbWFpbENvbnRlbnQoaW5wdXQ6ICRpbnB1dCkge1xuICAgICAgc3VjY2Vzc1xuICAgICAgbWVzc2FnZVxuICAgICAgZW1haWwge1xuICAgICAgICBpZFxuICAgICAgICB0aHJlYWRJZFxuICAgICAgICBzbmlwcGV0XG4gICAgICAgIHN1YmplY3RcbiAgICAgICAgZnJvbVxuICAgICAgICBkYXRlXG4gICAgICAgIGJvZHlcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG5cbmludGVyZmFjZSBEZXRhaWxlZEVtYWlsQ29udGVudCB7XG4gIGlkOiBzdHJpbmc7XG4gIHRocmVhZElkPzogc3RyaW5nIHwgbnVsbDtcbiAgc3ViamVjdD86IHN0cmluZyB8IG51bGw7XG4gIGZyb20/OiBzdHJpbmcgfCBudWxsO1xuICBkYXRlPzogc3RyaW5nIHwgbnVsbDtcbiAgYm9keT86IHN0cmluZyB8IG51bGw7XG4gIHNuaXBwZXQ/OiBzdHJpbmcgfCBudWxsO1xufVxuXG5pbnRlcmZhY2UgR21haWxTZWFyY2hSZXN1bHRJdGVtRkUge1xuICBpZDogc3RyaW5nO1xuICB0aHJlYWRJZD86IHN0cmluZyB8IG51bGw7XG4gIHNuaXBwZXQ/OiBzdHJpbmcgfCBudWxsO1xuICBzdWJqZWN0Pzogc3RyaW5nIHwgbnVsbDtcbiAgZnJvbT86IHN0cmluZyB8IG51bGw7XG4gIGRhdGU/OiBzdHJpbmcgfCBudWxsO1xufVxuXG5jb25zdCBVc2VyR21haWxTZWFyY2hQYWdlID0gKCkgPT4ge1xuICBjb25zdCBbc2VhcmNoUXVlcnksIHNldFNlYXJjaFF1ZXJ5XSA9IHVzZVN0YXRlKCcnKTtcbiAgY29uc3QgW3NlYXJjaFJlc3VsdHMsIHNldFNlYXJjaFJlc3VsdHNdID0gdXNlU3RhdGU8R21haWxTZWFyY2hSZXN1bHRJdGVtRkVbXT4oW10pO1xuICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KCk7XG5cbiAgY29uc3QgW3NlbGVjdGVkRW1haWwsIHNldFNlbGVjdGVkRW1haWxdID0gdXNlU3RhdGU8RGV0YWlsZWRFbWFpbENvbnRlbnQgfCBudWxsPihudWxsKTtcbiAgY29uc3QgW2lzRGV0YWlsTG9hZGluZywgc2V0SXNEZXRhaWxMb2FkaW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKTtcbiAgY29uc3QgW3Nob3dEZXRhaWxNb2RhbCwgc2V0U2hvd0RldGFpbE1vZGFsXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKTtcbiAgY29uc3QgW3Nob3dSZW1pbmRlck1vZGFsLCBzZXRTaG93UmVtaW5kZXJNb2RhbF0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSk7XG4gIGNvbnN0IFtyZW1pbmRlckRhdGUsIHNldFJlbWluZGVyRGF0ZV0gPSB1c2VTdGF0ZShuZXcgRGF0ZSgpKTtcblxuICBjb25zdCBbc2VhcmNoR21haWxNdXRhdGlvbiwgeyBsb2FkaW5nOiBzZWFyY2hMb2FkaW5nLCBlcnJvcjogc2VhcmNoRXJyb3IgfV0gPSB1c2VNdXRhdGlvbihTRUFSQ0hfVVNFUl9HTUFJTF9NVVRBVElPTiwge1xuICAgIG9uQ29tcGxldGVkOiAoZGF0YSkgPT4ge1xuICAgICAgaWYgKGRhdGEuc2VhcmNoVXNlckdtYWlsLnN1Y2Nlc3MpIHtcbiAgICAgICAgY29uc3QgcmVzdWx0cyA9IGRhdGEuc2VhcmNoVXNlckdtYWlsLnJlc3VsdHMgfHwgW107XG4gICAgICAgIHNldFNlYXJjaFJlc3VsdHMocmVzdWx0cyk7XG4gICAgICAgIGlmIChyZXN1bHRzLmxlbmd0aCA9PT0gMCAmJiBzZWFyY2hRdWVyeS50cmltKCkgIT09ICcnKSB7XG4gICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgdGl0bGU6ICdObyBTZWFyY2ggUmVzdWx0cycsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1lvdXIgc2VhcmNoIGRpZCBub3QgcmV0dXJuIGFueSBlbWFpbHMuJyxcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgZHVyYXRpb246IDMwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgdGl0bGU6ICdTZWFyY2ggRmFpbGVkJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogZGF0YS5zZWFyY2hVc2VyR21haWwubWVzc2FnZSB8fCAnQW4gZXJyb3Igb2NjdXJyZWQgZHVyaW5nIHRoZSBzZWFyY2guJyxcbiAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgZHVyYXRpb246IDUwMDAsXG4gICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgfSk7XG4gICAgICAgIHNldFNlYXJjaFJlc3VsdHMoW10pO1xuICAgICAgfVxuICAgIH0sXG4gICAgb25FcnJvcjogKGVycikgPT4ge1xuICAgICAgdG9hc3Qoe1xuICAgICAgICB0aXRsZTogJ1NlYXJjaCBFcnJvcicsXG4gICAgICAgIGRlc2NyaXB0aW9uOiBlcnIubWVzc2FnZSB8fCAnQW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZC4nLFxuICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgIGR1cmF0aW9uOiA1MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSk7XG4gICAgICBzZXRTZWFyY2hSZXN1bHRzKFtdKTtcbiAgICB9LFxuICB9KTtcblxuICBjb25zdCBbXG4gICAgZ2V0R21haWxDb250ZW50TXV0YXRpb24sXG4gICAgeyBsb2FkaW5nOiBkZXRhaWxGZXRjaExvYWRpbmcsIGVycm9yOiBkZXRhaWxGZXRjaEVycm9yIH0sXG4gIF0gPSB1c2VNdXRhdGlvbihHRVRfVVNFUl9HTUFJTF9DT05URU5UX01VVEFUSU9OLCB7XG4gICAgb25Db21wbGV0ZWQ6IChkYXRhKSA9PiB7XG4gICAgICBzZXRJc0RldGFpbExvYWRpbmcoZmFsc2UpO1xuICAgICAgaWYgKGRhdGEuZ2V0VXNlckdtYWlsQ29udGVudC5zdWNjZXNzICYmIGRhdGEuZ2V0VXNlckdtYWlsQ29udGVudC5lbWFpbCkge1xuICAgICAgICBjb25zdCBlbWFpbERhdGEgPSBkYXRhLmdldFVzZXJHbWFpbENvbnRlbnQuZW1haWw7XG4gICAgICAgIHNldFNlbGVjdGVkRW1haWwoe1xuICAgICAgICAgIGlkOiBlbWFpbERhdGEuaWQsXG4gICAgICAgICAgdGhyZWFkSWQ6IGVtYWlsRGF0YS50aHJlYWRJZCB8fCBudWxsLFxuICAgICAgICAgIHN1YmplY3Q6IGVtYWlsRGF0YS5zdWJqZWN0IHx8IG51bGwsXG4gICAgICAgICAgZnJvbTogZW1haWxEYXRhLmZyb20gfHwgbnVsbCxcbiAgICAgICAgICBkYXRlOiBlbWFpbERhdGEuZGF0ZSB8fCBudWxsLFxuICAgICAgICAgIGJvZHk6IGVtYWlsRGF0YS5ib2R5IHx8IG51bGwsXG4gICAgICAgICAgc25pcHBldDogZW1haWxEYXRhLnNuaXBwZXQgfHwgbnVsbCxcbiAgICAgICAgfSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgdGl0bGU6ICdFcnJvciBGZXRjaGluZyBFbWFpbCBEZXRhaWxzJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogZGF0YS5nZXRVc2VyR21haWxDb250ZW50Lm1lc3NhZ2UgfHwgJ0NvdWxkIG5vdCBsb2FkIGVtYWlsIGRldGFpbHMuJyxcbiAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgZHVyYXRpb246IDUwMDAsXG4gICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgfSk7XG4gICAgICAgIHNldFNlbGVjdGVkRW1haWwobnVsbCk7XG4gICAgICAgIHNldFNob3dEZXRhaWxNb2RhbChmYWxzZSk7XG4gICAgICB9XG4gICAgfSxcbiAgICBvbkVycm9yOiAoZXJyKSA9PiB7XG4gICAgICBzZXRJc0RldGFpbExvYWRpbmcoZmFsc2UpO1xuICAgICAgdG9hc3Qoe1xuICAgICAgICB0aXRsZTogJ0Vycm9yIEZldGNoaW5nIEVtYWlsIERldGFpbHMnLFxuICAgICAgICBkZXNjcmlwdGlvbjogZXJyLm1lc3NhZ2UgfHwgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQuJyxcbiAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICBkdXJhdGlvbjogNTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pO1xuICAgICAgc2V0U2VsZWN0ZWRFbWFpbChudWxsKTtcbiAgICAgIHNldFNob3dEZXRhaWxNb2RhbChmYWxzZSk7XG4gICAgfSxcbiAgfSk7XG5cbiAgY29uc3QgW2NyZWF0ZUVtYWlsUmVtaW5kZXJNdXRhdGlvbiwgeyBsb2FkaW5nOiByZW1pbmRlckxvYWRpbmcsIGVycm9yOiByZW1pbmRlckVycm9yIH1dID0gdXNlTXV0YXRpb24oQ1JFQVRFX0VNQUlMX1JFTUlOREVSX01VVEFUSU9OLCB7XG4gICAgb25Db21wbGV0ZWQ6IChkYXRhKSA9PiB7XG4gICAgICBpZiAoZGF0YS5jcmVhdGVFbWFpbFJlbWluZGVyLmlkKSB7XG4gICAgICAgIHRvYXN0KHtcbiAgICAgICAgICB0aXRsZTogJ1JlbWluZGVyIFNldCcsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdZb3VyIHJlbWluZGVyIGhhcyBiZWVuIHNldCBzdWNjZXNzZnVsbHkuJyxcbiAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICBkdXJhdGlvbjogMzAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgICAgc2V0U2hvd1JlbWluZGVyTW9kYWwoZmFsc2UpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgIHRpdGxlOiAnRmFpbGVkIHRvIFNldCBSZW1pbmRlcicsXG4gICAgICAgICAgZGVzY3JpcHRpb246ICdBbiBlcnJvciBvY2N1cnJlZCB3aGlsZSBzZXR0aW5nIHRoZSByZW1pbmRlci4nLFxuICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICBkdXJhdGlvbjogNTAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9LFxuICAgIG9uRXJyb3I6IChlcnIpID0+IHtcbiAgICAgIHRvYXN0KHtcbiAgICAgICAgdGl0bGU6ICdSZW1pbmRlciBFcnJvcicsXG4gICAgICAgIGRlc2NyaXB0aW9uOiBlcnIubWVzc2FnZSB8fCAnQW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZC4nLFxuICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgIGR1cmF0aW9uOiA1MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSk7XG4gICAgfSxcbiAgfSk7XG5cbiAgY29uc3QgaGFuZGxlU2V0UmVtaW5kZXIgPSAoKSA9PiB7XG4gICAgaWYgKHNlbGVjdGVkRW1haWwpIHtcbiAgICAgIGNyZWF0ZUVtYWlsUmVtaW5kZXJNdXRhdGlvbih7XG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIGlucHV0OiB7XG4gICAgICAgICAgICBlbWFpbElkOiBzZWxlY3RlZEVtYWlsLmlkLFxuICAgICAgICAgICAgc2VydmljZTogJ2dtYWlsJyxcbiAgICAgICAgICAgIHJlbWluZEF0OiByZW1pbmRlckRhdGUudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSk7XG4gICAgfVxuICB9O1xuXG4gIGNvbnN0IGhhbmRsZVNlYXJjaCA9ICgpID0+IHtcbiAgICBpZiAoc2VhcmNoUXVlcnkudHJpbSgpID09PSAnJykge1xuICAgICAgdG9hc3Qoe1xuICAgICAgICB0aXRsZTogJ0VtcHR5IFNlYXJjaCBRdWVyeScsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnUGxlYXNlIGVudGVyIGEgc2VhcmNoIHF1ZXJ5LicsXG4gICAgICAgIHN0YXR1czogJ3dhcm5pbmcnLFxuICAgICAgICBkdXJhdGlvbjogMzAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pO1xuICAgICAgcmV0dXJuO1xuICAgIH1cbiAgICBzZXRTaG93RGV0YWlsTW9kYWwoZmFsc2UpOyAvLyBDbG9zZSBkZXRhaWwgbW9kYWwgb24gbmV3IHNlYXJjaFxuICAgIHNldFNlbGVjdGVkRW1haWwobnVsbCk7XG4gICAgc2V0U2VhcmNoUmVzdWx0cyhbXSk7XG4gICAgc2VhcmNoR21haWxNdXRhdGlvbih7IHZhcmlhYmxlczogeyBpbnB1dDogeyBxdWVyeTogc2VhcmNoUXVlcnksIG1heFJlc3VsdHM6IDIwIH0gfSB9KTtcbiAgfTtcblxuICBjb25zdCBoYW5kbGVWaWV3RGV0YWlscyA9IChlbWFpbElkOiBzdHJpbmcpID0+IHtcbiAgICBpZiAoIWVtYWlsSWQpIHJldHVybjtcbiAgICBzZXRTZWxlY3RlZEVtYWlsKG51bGwpO1xuICAgIHNldElzRGV0YWlsTG9hZGluZyh0cnVlKTtcbiAgICBzZXRTaG93RGV0YWlsTW9kYWwodHJ1ZSk7XG4gICAgZ2V0R21haWxDb250ZW50TXV0YXRpb24oeyB2YXJpYWJsZXM6IHsgaW5wdXQ6IHsgZW1haWxJZCB9IH0gfSk7XG4gIH07XG5cbiAgY29uc3QgcmVuZGVySXRlbSA9ICh7IGl0ZW0gfTogeyBpdGVtOiBHbWFpbFNlYXJjaFJlc3VsdEl0ZW1GRSB9KSA9PiAoXG4gICAgPFByZXNzYWJsZSBvblByZXNzPXsoKSA9PiBoYW5kbGVWaWV3RGV0YWlscyhpdGVtLmlkKX0gc3R5bGU9e3N0eWxlcy5pdGVtQ29udGFpbmVyfT5cbiAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMuaXRlbVRleHRTdHJvbmd9PklEOiB7aXRlbS5pZH08L1RleHQ+XG4gICAgICB7aXRlbS5zbmlwcGV0ICYmIDxUZXh0IHN0eWxlPXtzdHlsZXMuaXRlbVRleHR9IG51bWJlck9mTGluZXM9ezJ9PlNuaXBwZXQ6IHtpdGVtLnNuaXBwZXR9PC9UZXh0Pn1cbiAgICAgIHtpdGVtLnN1YmplY3QgJiYgPFRleHQgc3R5bGU9e3N0eWxlcy5pdGVtVGV4dH0+U3ViamVjdDoge2l0ZW0uc3ViamVjdH08L1RleHQ+fVxuICAgICAge2l0ZW0uZnJvbSAmJiA8VGV4dCBzdHlsZT17c3R5bGVzLml0ZW1UZXh0fT5Gcm9tOiB7aXRlbS5mcm9tfTwvVGV4dD59XG4gICAgICB7aXRlbS5kYXRlICYmIDxUZXh0IHN0eWxlPXtzdHlsZXMuaXRlbVRleHR9PkRhdGU6IHtpdGVtLmRhdGV9PC9UZXh0Pn1cbiAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMudmlld0RldGFpbHNMaW5rfT5WaWV3IERldGFpbHM8L1RleHQ+XG4gICAgPC9QcmVzc2FibGU+XG4gICk7XG5cbiAgcmV0dXJuIChcbiAgICA8Qm94IGZsZXg9ezF9IHA9XCJtXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIGJhY2tncm91bmRDb2xvcj1cInByaW1hcnlDYXJkQmFja2dyb3VuZFwiIHN0eWxlPXtzdHlsZXMucGFnZUNvbnRhaW5lcn0+XG4gICAgICA8VGV4dCB2YXJpYW50PVwiaGVhZGVyXCIgbWI9XCJsXCIgc3R5bGU9e3N0eWxlcy5oZWFkZXJUZXh0fT5TZWFyY2ggWW91ciBHbWFpbDwvVGV4dD5cblxuICAgICAgPEJveCB3aWR0aD1cIjEwMCVcIiBtYXhXaWR0aD17NjAwfSBtYj1cIm1cIj5cbiAgICAgICAgPFRleHRGaWVsZFxuICAgICAgICAgIHBsYWNlaG9sZGVyPVwiZS5nLiwgZnJvbTpuYW1lQGV4YW1wbGUuY29tIHN1YmplY3Q6Y29udHJhY3RcIlxuICAgICAgICAgIHZhbHVlPXtzZWFyY2hRdWVyeX1cbiAgICAgICAgICBvbkNoYW5nZVRleHQ9e3NldFNlYXJjaFF1ZXJ5fVxuICAgICAgICAvPlxuICAgICAgPC9Cb3g+XG5cbiAgICAgIDxCdXR0b24gbGFiZWw9XCJTZWFyY2ggRW1haWxzXCIgb25DbGljaz17aGFuZGxlU2VhcmNofSBkaXNhYmxlZD17c2VhcmNoTG9hZGluZ30gLz5cblxuICAgICAge3NlYXJjaExvYWRpbmcgJiYgPEFjdGl2aXR5SW5kaWNhdG9yIHNpemU9XCJsYXJnZVwiIGNvbG9yPXtwYWxldHRlLnByaW1hcnl9IHN0eWxlPXtzdHlsZXMuYWN0aXZpdHlJbmRpY2F0b3J9IC8+fVxuXG4gICAgICB7c2VhcmNoRXJyb3IgJiYgKFxuICAgICAgICA8VGV4dCBjb2xvcj1cImVycm9yXCIgbXQ9XCJtXCIgc3R5bGU9e3N0eWxlcy5lcnJvclRleHR9PlxuICAgICAgICAgIEVycm9yIHNlYXJjaGluZzoge3NlYXJjaEVycm9yLm1lc3NhZ2V9XG4gICAgICAgIDwvVGV4dD5cbiAgICAgICl9XG5cbiAgICAgIHshc2VhcmNoTG9hZGluZyAmJiBzZWFyY2hSZXN1bHRzLmxlbmd0aCA+IDAgJiYgKFxuICAgICAgICA8RmxhdExpc3RcbiAgICAgICAgICBkYXRhPXtzZWFyY2hSZXN1bHRzfVxuICAgICAgICAgIHJlbmRlckl0ZW09e3JlbmRlckl0ZW19XG4gICAgICAgICAga2V5RXh0cmFjdG9yPXsoaXRlbSkgPT4gaXRlbS5pZH1cbiAgICAgICAgICBzdHlsZT17c3R5bGVzLmxpc3RTdHlsZX1cbiAgICAgICAgLz5cbiAgICAgICl9XG4gICAgICAgeyFzZWFyY2hMb2FkaW5nICYmICFzZWFyY2hFcnJvciAmJiBzZWFyY2hSZXN1bHRzLmxlbmd0aCA9PT0gMCAmJiBzZWFyY2hRdWVyeSAhPT0gJycgJiYgKFxuICAgICAgICAgPFRleHQgbXQ9XCJtXCIgc3R5bGU9e3N0eWxlcy5pdGVtVGV4dH0+Tm8gcmVzdWx0cyBmb3VuZCBmb3IgeW91ciBxdWVyeS48L1RleHQ+XG4gICAgICAgKX1cblxuICAgICAge3Nob3dEZXRhaWxNb2RhbCAmJiAoXG4gICAgICAgIDxNb2RhbFxuICAgICAgICAgIGFuaW1hdGlvblR5cGU9XCJzbGlkZVwiXG4gICAgICAgICAgdHJhbnNwYXJlbnQ9e3RydWV9XG4gICAgICAgICAgdmlzaWJsZT17c2hvd0RldGFpbE1vZGFsfVxuICAgICAgICAgIG9uUmVxdWVzdENsb3NlPXsoKSA9PiB7XG4gICAgICAgICAgICBzZXRTaG93RGV0YWlsTW9kYWwoZmFsc2UpO1xuICAgICAgICAgICAgc2V0U2VsZWN0ZWRFbWFpbChudWxsKTtcbiAgICAgICAgICB9fVxuICAgICAgICA+XG4gICAgICAgICAgPFZpZXcgc3R5bGU9e3N0eWxlcy5tb2RhbE92ZXJsYXl9PlxuICAgICAgICAgICAgPFZpZXcgc3R5bGU9e3N0eWxlcy5tb2RhbENvbnRhaW5lcn0+XG4gICAgICAgICAgICAgIDxTY3JvbGxWaWV3PlxuICAgICAgICAgICAgICAgIHtpc0RldGFpbExvYWRpbmcgJiYgPEFjdGl2aXR5SW5kaWNhdG9yIHNpemU9XCJsYXJnZVwiIGNvbG9yPXtwYWxldHRlLnByaW1hcnl9IC8+fVxuICAgICAgICAgICAgICAgIHtkZXRhaWxGZXRjaEVycm9yICYmIDxUZXh0IGNvbG9yPVwiZXJyb3JcIj5FcnJvciBsb2FkaW5nIGRldGFpbHM6IHtkZXRhaWxGZXRjaEVycm9yLm1lc3NhZ2V9PC9UZXh0Pn1cbiAgICAgICAgICAgICAgICB7c2VsZWN0ZWRFbWFpbCAmJiAhaXNEZXRhaWxMb2FkaW5nICYmIChcbiAgICAgICAgICAgICAgICAgIDw+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUaXRsZX0+RW1haWwgRGV0YWlsczwvVGV4dD5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgc3R5bGU9e3N0eWxlcy5tb2RhbFRleHRTdHJvbmd9PklEOjwvVGV4dD5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgc3R5bGU9e3N0eWxlcy5tb2RhbFRleHR9PntzZWxlY3RlZEVtYWlsLmlkfTwvVGV4dD5cblxuICAgICAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLm1vZGFsVGV4dFN0cm9uZ30+U3ViamVjdDo8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUZXh0fT57c2VsZWN0ZWRFbWFpbC5zdWJqZWN0IHx8ICdOL0EnfTwvVGV4dD5cblxuICAgICAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLm1vZGFsVGV4dFN0cm9uZ30+RnJvbTo8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUZXh0fT57c2VsZWN0ZWRFbWFpbC5mcm9tIHx8ICdOL0EnfTwvVGV4dD5cblxuICAgICAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLm1vZGFsVGV4dFN0cm9uZ30+RGF0ZTo8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUZXh0fT57c2VsZWN0ZWRFbWFpbC5kYXRlIHx8ICdOL0EnfTwvVGV4dD5cblxuICAgICAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLm1vZGFsVGV4dFN0cm9uZ30+U25pcHBldDo8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUZXh0fT57c2VsZWN0ZWRFbWFpbC5zbmlwcGV0IHx8ICdOL0EnfTwvVGV4dD5cblxuICAgICAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLm1vZGFsVGV4dFN0cm9uZ30+Qm9keTo8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHN0eWxlPXtzdHlsZXMubW9kYWxUZXh0Qm9keX0+e3NlbGVjdGVkRW1haWwuYm9keSB8fCAnKE5vIGJvZHkgY29udGVudCknfTwvVGV4dD5cbiAgICAgICAgICAgICAgICAgIDwvPlxuICAgICAgICAgICAgICAgICl9XG4gICAgICAgICAgICAgIDwvU2Nyb2xsVmlldz5cbiAgICAgICAgICAgICAgPEJ1dHRvbiBsYWJlbD1cIlJlbWluZCBtZVwiIG9uQ2xpY2s9eygpID0+IHNldFNob3dSZW1pbmRlck1vZGFsKHRydWUpfSAvPlxuICAgICAgICAgICAgICA8UHJlc3NhYmxlXG4gICAgICAgICAgICAgICAgc3R5bGU9e3N0eWxlcy5jbG9zZUJ1dHRvbn1cbiAgICAgICAgICAgICAgICBvblByZXNzPXsoKSA9PiB7XG4gICAgICAgICAgICAgICAgICBzZXRTaG93RGV0YWlsTW9kYWwoZmFsc2UpO1xuICAgICAgICAgICAgICAgICAgc2V0U2VsZWN0ZWRFbWFpbChudWxsKTtcbiAgICAgICAgICAgICAgICB9fVxuICAgICAgICAgICAgICA+XG4gICAgICAgICAgICAgICAgPFRleHQgc3R5bGU9e3N0eWxlcy5jbG9zZUJ1dHRvblRleHR9PkNsb3NlPC9UZXh0PlxuICAgICAgICAgICAgICA8L1ByZXNzYWJsZT5cbiAgICAgICAgICAgIDwvVmlldz5cbiAgICAgICAgICA8L1ZpZXc+XG4gICAgICAgIDwvTW9kYWw+XG4gICAgICApfVxuXG4gICAgICB7c2hvd1JlbWluZGVyTW9kYWwgJiYgKFxuICAgICAgICA8TW9kYWxcbiAgICAgICAgICBhbmltYXRpb25UeXBlPVwic2xpZGVcIlxuICAgICAgICAgIHRyYW5zcGFyZW50PXt0cnVlfVxuICAgICAgICAgIHZpc2libGU9e3Nob3dSZW1pbmRlck1vZGFsfVxuICAgICAgICAgIG9uUmVxdWVzdENsb3NlPXsoKSA9PiBzZXRTaG93UmVtaW5kZXJNb2RhbChmYWxzZSl9XG4gICAgICAgID5cbiAgICAgICAgICA8VmlldyBzdHlsZT17c3R5bGVzLm1vZGFsT3ZlcmxheX0+XG4gICAgICAgICAgICA8VmlldyBzdHlsZT17c3R5bGVzLm1vZGFsQ29udGFpbmVyfT5cbiAgICAgICAgICAgICAgPFRleHQgc3R5bGU9e3N0eWxlcy5tb2RhbFRpdGxlfT5TZXQgUmVtaW5kZXI8L1RleHQ+XG4gICAgICAgICAgICAgIDxUZXh0PlNlbGVjdCBhIGRhdGUgYW5kIHRpbWUgZm9yIHlvdXIgcmVtaW5kZXI6PC9UZXh0PlxuICAgICAgICAgICAgICB7LyogSSB3aWxsIHVzZSBhIHNpbXBsZSB0ZXh0IGlucHV0IGZvciBub3csIGEgcHJvcGVyIGRhdGUgcGlja2VyIHdvdWxkIGJlIGJldHRlciAqL31cbiAgICAgICAgICAgICAgPFRleHRGaWVsZFxuICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiWVlZWS1NTS1ERFRISDptbTpzcy5zc3NaXCJcbiAgICAgICAgICAgICAgICB2YWx1ZT17cmVtaW5kZXJEYXRlLnRvSVNPU3RyaW5nKCl9XG4gICAgICAgICAgICAgICAgb25DaGFuZ2VUZXh0PXsodGV4dCkgPT4gc2V0UmVtaW5kZXJEYXRlKG5ldyBEYXRlKHRleHQpKX1cbiAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgPEJ1dHRvbiBsYWJlbD1cIlNldCBSZW1pbmRlclwiIG9uQ2xpY2s9e2hhbmRsZVNldFJlbWluZGVyfSBkaXNhYmxlZD17cmVtaW5kZXJMb2FkaW5nfSAvPlxuICAgICAgICAgICAgICA8UHJlc3NhYmxlXG4gICAgICAgICAgICAgICAgc3R5bGU9e3N0eWxlcy5jbG9zZUJ1dHRvbn1cbiAgICAgICAgICAgICAgICBvblByZXNzPXsoKSA9PiBzZXRTaG93UmVtaW5kZXJNb2RhbChmYWxzZSl9XG4gICAgICAgICAgICAgID5cbiAgICAgICAgICAgICAgICA8VGV4dCBzdHlsZT17c3R5bGVzLmNsb3NlQnV0dG9uVGV4dH0+Q2FuY2VsPC9UZXh0PlxuICAgICAgICAgICAgICA8L1ByZXNzYWJsZT5cbiAgICAgICAgICAgIDwvVmlldz5cbiAgICAgICAgICA8L1ZpZXc+XG4gICAgICAgIDwvTW9kYWw+XG4gICAgICApfVxuICAgIDwvQm94PlxuICApO1xufTtcblxuY29uc3Qgc3R5bGVzID0gU3R5bGVTaGVldC5jcmVhdGUoe1xuICBwYWdlQ29udGFpbmVyOiB7XG4gICAgcGFkZGluZ1RvcDogMjAsXG4gIH0sXG4gIGhlYWRlclRleHQ6IHtcbiAgICBjb2xvcjogcGFsZXR0ZS50ZXh0LFxuICB9LFxuICBpdGVtQ29udGFpbmVyOiB7XG4gICAgcGFkZGluZzogMTUsXG4gICAgYm9yZGVyQm90dG9tV2lkdGg6IDEsXG4gICAgYm9yZGVyQm90dG9tQ29sb3I6IHBhbGV0dGUubWVkaXVtR3JheSxcbiAgICBiYWNrZ3JvdW5kQ29sb3I6IHBhbGV0dGUud2hpdGUsXG4gICAgYm9yZGVyUmFkaXVzOiA1LFxuICAgIG1hcmdpblZlcnRpY2FsOiA1LFxuICB9LFxuICBpdGVtVGV4dDoge1xuICAgIGZvbnRTaXplOiAxNCxcbiAgICBjb2xvcjogcGFsZXR0ZS50ZXh0LFxuICAgIG1hcmdpbkJvdHRvbTogMyxcbiAgfSxcbiAgaXRlbVRleHRTdHJvbmc6IHtcbiAgICBmb250U2l6ZTogMTQsXG4gICAgZm9udFdlaWdodDogJ2JvbGQnLFxuICAgIGNvbG9yOiBwYWxldHRlLnRleHQsXG4gICAgbWFyZ2luQm90dG9tOiAzLFxuICB9LFxuICB2aWV3RGV0YWlsc0xpbms6IHtcbiAgICBmb250U2l6ZTogMTQsXG4gICAgY29sb3I6IHBhbGV0dGUucHJpbWFyeSwgLy8gVXNlIHByaW1hcnkgY29sb3IgZm9yIGxpbmtcbiAgICBtYXJnaW5Ub3A6IDUsXG4gICAgdGV4dERlY29yYXRpb25MaW5lOiAndW5kZXJsaW5lJyxcbiAgfSxcbiAgYWN0aXZpdHlJbmRpY2F0b3I6IHtcbiAgICBtYXJnaW5Ub3A6IDIwLFxuICB9LFxuICBlcnJvclRleHQ6IHtcbiAgICBmb250U2l6ZTogMTQsXG4gICAgY29sb3I6IHBhbGV0dGUuZXJyb3IsIC8vIEVuc3VyZSBwYWxldHRlIGhhcyBhbiBlcnJvciBjb2xvclxuICB9LFxuICBsaXN0U3R5bGU6IHtcbiAgICB3aWR0aDogJzEwMCUnLFxuICAgIG1heFdpZHRoOiA2MDAsXG4gICAgbWFyZ2luVG9wOiAyMCxcbiAgfSxcbiAgLy8gTW9kYWwgc3R5bGVzXG4gIG1vZGFsT3ZlcmxheToge1xuICAgIGZsZXg6IDEsXG4gICAganVzdGlmeUNvbnRlbnQ6ICdjZW50ZXInLFxuICAgIGFsaWduSXRlbXM6ICdjZW50ZXInLFxuICAgIGJhY2tncm91bmRDb2xvcjogJ3JnYmEoMCwwLDAsMC41KScsIC8vIFNlbWktdHJhbnNwYXJlbnQgYmFja2dyb3VuZFxuICB9LFxuICBtb2RhbENvbnRhaW5lcjoge1xuICAgIHdpZHRoOiAnOTAlJyxcbiAgICBtYXhXaWR0aDogNjAwLFxuICAgIG1heEhlaWdodDogJzgwJScsXG4gICAgYmFja2dyb3VuZENvbG9yOiBwYWxldHRlLndoaXRlLFxuICAgIGJvcmRlclJhZGl1czogMTAsXG4gICAgcGFkZGluZzogMjAsXG4gICAgc2hhZG93Q29sb3I6ICcjMDAwJyxcbiAgICBzaGFkb3dPZmZzZXQ6IHtcbiAgICAgIHdpZHRoOiAwLFxuICAgICAgaGVpZ2h0OiAyLFxuICAgIH0sXG4gICAgc2hhZG93T3BhY2l0eTogMC4yNSxcbiAgICBzaGFkb3dSYWRpdXM6IDQsXG4gICAgZWxldmF0aW9uOiA1LFxuICB9LFxuICBtb2RhbFRpdGxlOiB7XG4gICAgZm9udFNpemU6IDE4LFxuICAgIGZvbnRXZWlnaHQ6ICdib2xkJyxcbiAgICBtYXJnaW5Cb3R0b206IDE1LFxuICAgIGNvbG9yOiBwYWxldHRlLnRleHQsXG4gICAgdGV4dEFsaWduOiAnY2VudGVyJyxcbiAgfSxcbiAgbW9kYWxUZXh0U3Ryb25nOiB7XG4gICAgZm9udFNpemU6IDE1LFxuICAgIGZvbnRXZWlnaHQ6ICdib2xkJyxcbiAgICBtYXJnaW5Ub3A6IDEwLFxuICAgIGNvbG9yOiBwYWxldHRlLnRleHQsXG4gIH0sXG4gIG1vZGFsVGV4dDoge1xuICAgIGZvbnRTaXplOiAxNCxcbiAgICBtYXJnaW5Cb3R0b206IDUsXG4gICAgY29sb3I6IHBhbGV0dGUudGV4dFNlY29uZGFyeSwgLy8gQXNzdW1pbmcgYSBzZWNvbmRhcnkgdGV4dCBjb2xvclxuICB9LFxuICBtb2RhbFRleHRCb2R5OiB7XG4gICAgZm9udFNpemU6IDE0LFxuICAgIG1hcmdpbkJvdHRvbTogNSxcbiAgICBjb2xvcjogcGFsZXR0ZS50ZXh0U2Vjb25kYXJ5LFxuICAgIG1hcmdpblRvcDogNSxcbiAgICBib3JkZXJXaWR0aDogMSxcbiAgICBib3JkZXJDb2xvcjogcGFsZXR0ZS5saWdodEdyYXksIC8vIEFzc3VtaW5nIGxpZ2h0R3JheVxuICAgIHBhZGRpbmc6IDEwLFxuICAgIGJvcmRlclJhZGl1czogMyxcbiAgICBtYXhIZWlnaHQ6IDIwMCwgLy8gTWFrZSBib2R5IHNjcm9sbGFibGUgaWYgdG9vIGxvbmcsIGJ1dCBTY3JvbGxWaWV3IGhhbmRsZXMgdGhpc1xuICB9LFxuICBjbG9zZUJ1dHRvbjoge1xuICAgIG1hcmdpblRvcDogMjAsXG4gICAgYmFja2dyb3VuZENvbG9yOiBwYWxldHRlLnByaW1hcnksXG4gICAgcGFkZGluZ1ZlcnRpY2FsOiAxMCxcbiAgICBwYWRkaW5nSG9yaXpvbnRhbDogMjAsXG4gICAgYm9yZGVyUmFkaXVzOiA1LFxuICAgIGFsaWduU2VsZjogJ2NlbnRlcicsXG4gIH0sXG4gIGNsb3NlQnV0dG9uVGV4dDoge1xuICAgIGNvbG9yOiBwYWxldHRlLndoaXRlLFxuICAgIGZvbnRXZWlnaHQ6ICdib2xkJyxcbiAgICB0ZXh0QWxpZ246ICdjZW50ZXInLFxuICB9LFxufSk7XG5cbmV4cG9ydCBkZWZhdWx0IFVzZXJHbWFpbFNlYXJjaFBhZ2U7XG4iXX0=