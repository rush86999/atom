"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_native_1 = require("react-native");
const image_1 = __importDefault(require("next/image"));
const Switch_1 = __importDefault(require("@components/Switch"));
const react_2 = require("@chakra-ui/react");
const themed_1 = require("@rneui/themed");
const UserCalendarList_1 = __importDefault(require("@pages/Settings/Google/UserCalendarList"));
const client_1 = require("@apollo/client");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const Button_1 = __importDefault(require("@components/Button"));
const theme_1 = require("@lib/theme/theme");
const calendar_integrationHelper_1 = require("@lib/Settings/calendar_integrationHelper");
const GithubManager_1 = __importDefault(require("@components/Settings/GithubManager"));
const constants_1 = require("@lib/calendarLib/constants");
const constants_2 = require("@lib/contactLib/constants");
const constants_3 = require("@lib/zoom/constants");
const googleCalendarHelper_1 = require("@lib/calendarLib/googleCalendarHelper");
const calendarDbHelper_1 = require("@lib/calendarLib/calendarDbHelper");
const listCalendarIntegrations_1 = __importDefault(require("@lib/apollo/gql/listCalendarIntegrations"));
const getCalendarIntegrationByResourceAndName_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationByResourceAndName"));
const google_signin_normal_png_1 = __importDefault(require("@assets/images/google-signin-normal.png"));
const google_signin_pressed_png_1 = __importDefault(require("@assets/images/google-signin-pressed.png"));
const user_context_1 = require("@lib/user-context");
const router_1 = require("next/router");
// const dark = Appearance.getColorScheme() === 'dark'
// const googleButtonPressed = dark ? googleButtonPressedDarkNormal : googleButtonPressedLightNormal
// const googleButtonNormal = dark ? googleButtonDarkNormal : googleButtonLightNormal
const googleButtonPressed = google_signin_pressed_png_1.default;
const googleButtonNormal = google_signin_normal_png_1.default;
const client_2 = require("@apollo/client"); // Import gql
// Define the GraphQL mutation for generating Gmail Auth URL
const GENERATE_GMAIL_AUTH_URL_MUTATION = (0, client_2.gql) `
  mutation GenerateGmailAuthUrl {
    generateGmailAuthUrl {
      authorizationUrl
    }
  }
`;
// GraphQL for Shopify Integration
const GENERATE_SHOPIFY_AUTH_URL_MUTATION = (0, client_2.gql) `
  mutation GenerateShopifyAuthUrl($shopName: String!) {
    generateShopifyAuthUrl(shop_name: $shopName) {
      authUrl
    }
  }
`;
const GET_SHOPIFY_CONNECTION_STATUS_QUERY = (0, client_2.gql) `
  query GetShopifyConnectionStatus {
    getShopifyConnectionStatus {
      isConnected
      shopUrl
    }
  }
`;
const DISCONNECT_SHOPIFY_ACCOUNT_MUTATION = (0, client_2.gql) `
  mutation DisconnectShopifyAccount {
    disconnectShopifyAccount {
      success
      message
    }
  }
`;
const GENERATE_OUTLOOK_AUTH_URL_MUTATION = (0, client_2.gql) `
  mutation GenerateOutlookAuthUrl {
    generateOutlookAuthUrl {
      authUrl
    }
  }
`;
const GET_OUTLOOK_CONNECTION_STATUS_QUERY = (0, client_2.gql) `
  query GetOutlookConnectionStatus {
    getOutlookConnectionStatus {
      isConnected
      userEmail
    }
  }
`;
const DISCONNECT_OUTLOOK_ACCOUNT_MUTATION = (0, client_2.gql) `
  mutation DisconnectOutlookAccount {
    disconnectOutlookAccount {
      success
      message
    }
  }
`;
// GraphQL for Gmail Connection Status and Disconnect
const GET_GMAIL_CONNECTION_STATUS_QUERY = (0, client_2.gql) `
  query GetGmailConnectionStatus {
    getGmailConnectionStatus {
      isConnected
      userEmail
    }
  }
`;
const DISCONNECT_GMAIL_ACCOUNT_MUTATION = (0, client_2.gql) `
  mutation DisconnectGmailAccount {
    disconnectGmailAccount {
      success
      message
    }
  }
`;
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("@config/backendConfig");
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
async function getServerSideProps({ req, res }) {
    // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
    // const SSR = withSSRContext({ req })
    // this runs on the backend, so we must call init on supertokens-node SDK
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
    let session;
    try {
        session = await session_1.default.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return [];
            },
        });
    }
    catch (err) {
        if (err.type === session_1.default.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        else if (err.type === session_1.default.Error.UNAUTHORISED) {
            // this will force the frontend to try and refresh which will fail
            // clearing all cookies and redirecting the user to the login screen.
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
    return {
        props: {
            sub: session.getUserId(),
        }
    };
}
// eslint-disable-next-line react/display-name
const IntegrationCheckBox = (0, react_1.forwardRef)((props, ref) => {
    const { enabled: oldEnabled, updateEnabledValue, index, name, 
    // dark,
    id, } = props;
    const [enabled, setEnabled] = (0, react_1.useState)(oldEnabled);
    const [pressed, setPressed] = (0, react_1.useState)(false);
    const updateEnabled = async (value) => {
        setEnabled(value);
        return updateEnabledValue(index, value, id);
    };
    const disableEnabled = async () => {
        setEnabled(false);
        return updateEnabledValue(index, false, id);
    };
    (0, react_1.useImperativeHandle)(ref, () => ({
        disableEnabled,
    }));
    const onPressIn = () => setPressed(true);
    const onPressOut = () => setPressed(false);
    const onPress = async () => updateEnabled(!enabled);
    if ((name === constants_1.googleCalendarName) || (name === constants_2.googlePeopleName)) {
        return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, justifyContent: "center", alignItems: "stretch", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray }, children: name }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' }, children: enabled
                                ? (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", children: "On" })
                                : (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", children: "Off" }) })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", pt: { phone: 'm', tablet: 's' }, children: enabled
                        ? ((0, jsx_runtime_1.jsx)(react_native_1.Pressable, { onPress: onPress, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "buttonLink", children: "Disable" }) })) : ((0, jsx_runtime_1.jsx)(react_native_1.Pressable, { onPressIn: onPressIn, onPressOut: onPressOut, onPress: onPress, children: (0, jsx_runtime_1.jsx)(image_1.default, { src: pressed ? googleButtonPressed : googleButtonNormal, style: { width: 240, height: 50 }, alt: 'google sign-in button' }) })) })] }));
    }
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray }, children: name }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Switch_1.default, { onValueChange: updateEnabled, checked: enabled }) })] }));
});
function UserViewCalendarAndContactIntegrations() {
    const [loading, setLoading] = (0, react_1.useState)(false);
    const [isWarning, setIsWarning] = (0, react_1.useState)(false);
    const [selectedIndex, setSelectedIndex] = (0, react_1.useState)(-1);
    const [selectedId, setSelectedId] = (0, react_1.useState)();
    const [selectedValue, setSelectedValue] = (0, react_1.useState)(false);
    // const [googleCalendarEnabled, setGoogleCalendarEnabled] = useState<boolean>(false)
    const [isGoogleCalendarList, setIsGoogleCalendarList] = (0, react_1.useState)(false);
    const [googleToken, setGoogleToken] = (0, react_1.useState)();
    // State for Gmail Integration
    const [isGmailConnected, setIsGmailConnected] = (0, react_1.useState)(false);
    const [gmailUserEmail, setGmailUserEmail] = (0, react_1.useState)(null);
    const [isGmailStatusLoading, setIsGmailStatusLoading] = (0, react_1.useState)(true);
    // State for Outlook Integration
    const [isOutlookConnected, setIsOutlookConnected] = (0, react_1.useState)(false);
    const [outlookUserEmail, setOutlookUserEmail] = (0, react_1.useState)(null);
    const [isOutlookStatusLoading, setIsOutlookStatusLoading] = (0, react_1.useState)(true);
    // State for Shopify Integration
    const [isShopifyConnected, setIsShopifyConnected] = (0, react_1.useState)(false);
    const [shopifyShopUrl, setShopifyShopUrl] = (0, react_1.useState)(null);
    const [isShopifyStatusLoading, setIsShopifyStatusLoading] = (0, react_1.useState)(true);
    const [shopifyShopName, setShopifyShopName] = (0, react_1.useState)('');
    const googleCalendarElement = (0, react_1.useRef)();
    const toast = (0, react_2.useToast)();
    // const dark = useColorScheme() === 'dark'
    const router = (0, router_1.useRouter)();
    const { sub, client, } = (0, user_context_1.useAppContext)();
    const userId = sub;
    const { loading: googleIntegrationLoading, error: googleIntegrationError, data: googleIntegrationData, refetch: googleIntRefetch } = (0, client_1.useQuery)(getCalendarIntegrationByResourceAndName_1.default, {
        variables: {
            name: constants_1.googleCalendarName,
            resource: constants_1.googleResourceName,
            userId: userId,
        }
    });
    const { loading: integrationLoading, error: integrationError, data: integrationData, refetch: calIntRefetch } = (0, client_1.useQuery)(listCalendarIntegrations_1.default, {
        variables: {
            userId: userId,
        }
    });
    const googleCalendarEnabled = googleIntegrationData?.Calendar_Integration?.[0]?.enabled;
    const integrations = integrationData?.Calendar_Integration;
    // const [integrations, setIntegrations] = useState<CalendarIntegrationType[]>(oldIntegrations)
    console.log(integrations, ' integrations');
    // Gmail Connection Handler
    const handleConnectGmail = async () => {
        setLoading(true); // Reuse existing loading state
        try {
            const response = await client.mutate({
                mutation: GENERATE_GMAIL_AUTH_URL_MUTATION,
            });
            if (response.data?.generateGmailAuthUrl?.authorizationUrl) {
                window.location.href = response.data.generateGmailAuthUrl.authorizationUrl;
            }
            else {
                console.error('Failed to get Gmail authorization URL from mutation response:', response);
                throw new Error('Failed to get Gmail authorization URL.');
            }
        }
        catch (error) {
            console.error('Error initiating Gmail connection:', error);
            toast({
                title: 'Error Connecting Gmail',
                description: error.message || 'Could not initiate Gmail connection. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
            setLoading(false);
        }
        // setLoading(false) might not be reached if window.location.href happens
    };
    // just in case
    (0, react_1.useEffect)(() => {
        // Fetch Gmail connection status on mount
        setIsGmailStatusLoading(true);
        client.query({ query: GET_GMAIL_CONNECTION_STATUS_QUERY, fetchPolicy: 'network-only' }) // fetchPolicy to ensure fresh data
            .then(response => {
            const status = response.data?.getGmailConnectionStatus;
            if (status) {
                setIsGmailConnected(status.isConnected);
                setGmailUserEmail(status.userEmail || null);
            }
        })
            .catch(err => {
            console.error("Error fetching Gmail connection status:", err);
            toast({
                title: 'Error Fetching Gmail Status',
                description: err.message || "Could not fetch Gmail connection details.",
                status: 'error',
                duration: 5000,
                isClosable: true,
            });
            // Assume not connected on error, or keep current state? For now, assume not connected.
            setIsGmailConnected(false);
            setGmailUserEmail(null);
        })
            .finally(() => {
            setIsGmailStatusLoading(false);
        });
    }, [client, toast]); // Add client and toast to dependency array
    const handleDisconnectGmail = async () => {
        setLoading(true); // Reuse general loading state, or use a specific one for Gmail disconnect
        try {
            const response = await client.mutate({
                mutation: DISCONNECT_GMAIL_ACCOUNT_MUTATION,
            });
            if (response.data?.disconnectGmailAccount?.success) {
                toast({
                    title: 'Gmail Disconnected',
                    description: response.data.disconnectGmailAccount.message || 'Successfully disconnected your Gmail account.',
                    status: 'success',
                    duration: 5000,
                    isClosable: true,
                });
                setIsGmailConnected(false);
                setGmailUserEmail(null);
            }
            else {
                throw new Error(response.data?.disconnectGmailAccount?.message || 'Failed to disconnect Gmail account.');
            }
        }
        catch (error) {
            console.error('Error disconnecting Gmail:', error);
            toast({
                title: 'Error Disconnecting Gmail',
                description: error.message || 'Could not disconnect Gmail. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
        }
        finally {
            setLoading(false);
        }
    };
    // Shopify Connection Handler
    const handleConnectShopify = async () => {
        if (!shopifyShopName.trim()) {
            toast({
                title: 'Shop Name Required',
                description: 'Please enter your Shopify shop name (e.g., my-great-store).',
                status: 'warning',
                duration: 5000,
                isClosable: true,
            });
            return;
        }
        setLoading(true);
        try {
            const response = await client.mutate({
                mutation: GENERATE_SHOPIFY_AUTH_URL_MUTATION,
                variables: { shopName: shopifyShopName },
            });
            if (response.data?.generateShopifyAuthUrl?.authUrl) {
                window.location.href = response.data.generateShopifyAuthUrl.authUrl;
            }
            else {
                throw new Error('Failed to get Shopify authorization URL.');
            }
        }
        catch (error) {
            console.error('Error initiating Shopify connection:', error);
            toast({
                title: 'Error Connecting Shopify',
                description: error.message || 'Could not initiate Shopify connection. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
            setLoading(false);
        }
    };
    (0, react_1.useEffect)(() => {
        // Fetch Shopify connection status on mount
        setIsShopifyStatusLoading(true);
        client.query({ query: GET_SHOPIFY_CONNECTION_STATUS_QUERY, fetchPolicy: 'network-only' })
            .then(response => {
            const status = response.data?.getShopifyConnectionStatus;
            if (status) {
                setIsShopifyConnected(status.isConnected);
                setShopifyShopUrl(status.shopUrl || null);
            }
        })
            .catch(err => {
            console.error("Error fetching Shopify connection status:", err);
            // Assume not connected on error
            setIsShopifyConnected(false);
            setShopifyShopUrl(null);
        })
            .finally(() => {
            setIsShopifyStatusLoading(false);
        });
    }, [client, toast]);
    const handleDisconnectShopify = async () => {
        setLoading(true);
        try {
            const response = await client.mutate({
                mutation: DISCONNECT_SHOPIFY_ACCOUNT_MUTATION,
            });
            if (response.data?.disconnectShopifyAccount?.success) {
                toast({
                    title: 'Shopify Disconnected',
                    description: response.data.disconnectShopifyAccount.message || 'Successfully disconnected your Shopify account.',
                    status: 'success',
                    duration: 5000,
                    isClosable: true,
                });
                setIsShopifyConnected(false);
                setShopifyShopUrl(null);
            }
            else {
                throw new Error(response.data?.disconnectShopifyAccount?.message || 'Failed to disconnect Shopify account.');
            }
        }
        catch (error) {
            console.error('Error disconnecting Shopify:', error);
            toast({
                title: 'Error Disconnecting Shopify',
                description: error.message || 'Could not disconnect Shopify. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
        }
        finally {
            setLoading(false);
        }
    };
    // Outlook Connection Handler
    const handleConnectOutlook = async () => {
        setLoading(true);
        try {
            const response = await client.mutate({
                mutation: GENERATE_OUTLOOK_AUTH_URL_MUTATION,
            });
            if (response.data?.generateOutlookAuthUrl?.authUrl) {
                window.location.href = response.data.generateOutlookAuthUrl.authUrl;
            }
            else {
                throw new Error('Failed to get Outlook authorization URL.');
            }
        }
        catch (error) {
            console.error('Error initiating Outlook connection:', error);
            toast({
                title: 'Error Connecting Outlook',
                description: error.message || 'Could not initiate Outlook connection. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
            setLoading(false);
        }
    };
    (0, react_1.useEffect)(() => {
        // Fetch Outlook connection status on mount
        setIsOutlookStatusLoading(true);
        client.query({ query: GET_OUTLOOK_CONNECTION_STATUS_QUERY, fetchPolicy: 'network-only' })
            .then(response => {
            const status = response.data?.getOutlookConnectionStatus;
            if (status) {
                setIsOutlookConnected(status.isConnected);
                setOutlookUserEmail(status.userEmail || null);
            }
        })
            .catch(err => {
            console.error("Error fetching Outlook connection status:", err);
            // Assume not connected on error
            setIsOutlookConnected(false);
            setOutlookUserEmail(null);
        })
            .finally(() => {
            setIsOutlookStatusLoading(false);
        });
    }, [client, toast]);
    const handleDisconnectOutlook = async () => {
        setLoading(true);
        try {
            const response = await client.mutate({
                mutation: DISCONNECT_OUTLOOK_ACCOUNT_MUTATION,
            });
            if (response.data?.disconnectOutlookAccount?.success) {
                toast({
                    title: 'Outlook Disconnected',
                    description: response.data.disconnectOutlookAccount.message || 'Successfully disconnected your Outlook account.',
                    status: 'success',
                    duration: 5000,
                    isClosable: true,
                });
                setIsOutlookConnected(false);
                setOutlookUserEmail(null);
            }
            else {
                throw new Error(response.data?.disconnectOutlookAccount?.message || 'Failed to disconnect Outlook account.');
            }
        }
        catch (error) {
            console.error('Error disconnecting Outlook:', error);
            toast({
                title: 'Error Disconnecting Outlook',
                description: error.message || 'Could not disconnect Outlook. Please try again.',
                status: 'error',
                duration: 9000,
                isClosable: true,
            });
        }
        finally {
            setLoading(false);
        }
    };
    (0, react_1.useEffect)(() => {
        if (googleCalendarEnabled) {
            toast({
                status: 'info',
                title: 'Enable a calendar from Google',
                description: 'Please click on View Google Calendars and enable at least 1 calendar to use Atomic',
                duration: 9000,
                isClosable: true,
            });
        }
    }, [googleCalendarEnabled, toast]);
    const disableGoogleCalendarCheckBox = () => {
        setSelectedIndex(-1);
        setSelectedId('');
        setSelectedValue(false);
        setIsWarning(false);
        googleCalendarElement.current.disableEnabled();
    };
    const enableGoogleCalendarCheckBox = async () => {
        try {
            setIsWarning(false);
            // const newIntegrations = integrations
            //   .slice(0, selectedIndex)
            //   .concat([{ ...(integrations?.[selectedIndex]), enabled: selectedValue }])
            //   .concat(integrations.slice(selectedIndex + 1))
            // setIntegrations(newIntegrations)
            await submitIntegration(selectedIndex, selectedValue, selectedId);
            await googleIntRefetch();
            await calIntRefetch();
            setSelectedIndex(-1);
            setSelectedId('');
            setSelectedValue(false);
        }
        catch (e) {
            setIsWarning(false);
            console.log(e, ' this is error for enable google calendar checkbox');
            toast({
                status: 'error',
                title: 'Error',
                description: 'Something went wrong',
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const updateEnabledValue = async (index, value, id) => {
        const selectedIntegration = integrations[index];
        if ((selectedIntegration.name === constants_1.googleCalendarName)
            && (value === false)) {
            setSelectedIndex(index);
            setSelectedId(id);
            setSelectedValue(value);
            setIsWarning(true);
        }
        else {
            // const newIntegrations = integrations
            // .slice(0, index)
            // .concat([{ ...(integrations?.[index]), enabled: value }])
            // .concat(integrations.slice(index + 1))
            // setIntegrations(newIntegrations)
            await submitIntegration(index, value, id);
            await googleIntRefetch();
            await calIntRefetch();
        }
    };
    const disableGoogleCalendarSync = async (integrationId) => {
        try {
            await (0, calendar_integrationHelper_1.updateIntegration)(client, integrationId, false, null, undefined, null);
            await (0, calendar_integrationHelper_1.deleteEventTriggers)(userId, constants_1.googleResourceName, constants_1.googleCalendarName);
            const itemsToRemove = await (0, calendarDbHelper_1.getItemsToRemove)(client, userId, constants_1.googleResourceName);
            await (0, calendarDbHelper_1.bulkRemoveCalendarsInDb)(client, itemsToRemove.map(i => (i?.id)));
            // bulk remove events from db
            const eventsToRemovePromise = [];
            for (const item of itemsToRemove) {
                if (item?.id) {
                    eventsToRemovePromise.push((0, calendarDbHelper_1.deleteEventsByCalendarId)(client, item.id));
                }
            }
            await Promise.all(eventsToRemovePromise);
            await googleIntRefetch();
            await calIntRefetch();
        }
        catch (e) {
            console.log(e, ' this is e for disable google calendarsync');
            await calIntRefetch();
            await googleIntRefetch();
        }
    };
    const disableZoomAuth = async (integrationId) => {
        try {
            await (0, calendar_integrationHelper_1.updateIntegration)(client, integrationId, false, null, null, null, undefined, undefined, null, null);
        }
        catch (e) {
            console.log(e, ' unable to disable zoom auth');
        }
    };
    const disableGoogleContactSync = async (integrationId) => {
        try {
            await (0, calendar_integrationHelper_1.updateIntegration)(client, integrationId, false, null, undefined, null, undefined, undefined, null, null);
            // delete event triggers
            await (0, calendar_integrationHelper_1.deleteEventTriggerByResourceId)(integrationId);
            await googleIntRefetch();
        }
        catch (e) {
            console.log(e, ' error in disableGoogleContactSync');
        }
    };
    const submitIntegration = async (index, newEnabled, id) => {
        try {
            if (newEnabled === false) {
                // delete triggers
                if (integrations?.[index]?.name === constants_2.googlePeopleName) {
                    return disableGoogleContactSync(integrations?.[index]?.id);
                }
                else if (integrations?.[index]?.name === constants_1.googleCalendarName) {
                    return disableGoogleCalendarSync(integrations?.[index]?.id);
                }
                else if (integrations?.[index]?.resource === constants_3.zoomResourceName) {
                    return disableZoomAuth(integrations?.[index]?.id);
                }
                return (0, calendar_integrationHelper_1.updateIntegration)(client, id, newEnabled, undefined, undefined, undefined, false, undefined, undefined, undefined, integrations?.[index]?.resource === constants_1.googleResourceName ? 'atomic-web' : 'web');
            }
        }
        catch (e) {
            console.log(e, ' unable to submit integrations');
            setLoading(false);
            toast({
                status: 'error',
                title: 'Unable to submit integration',
                description: 'Please try again',
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const navigateToGoogleCalendars = async () => {
        try {
            const newAccessToken = await (0, googleCalendarHelper_1.getGoogleToken)(client, userId);
            setGoogleToken(newAccessToken);
            // return router.push({ pathname: '/Settings/Google/UserCalendarList', query: { token: newAccessToken }})
            setIsGoogleCalendarList(true);
        }
        catch (e) {
            console.log(e, ' unable to navigate to google calendars');
        }
    };
    const renderItem = ({ item, index }) => {
        if ((item?.resource === constants_3.zoomResourceName) && !item?.enabled) {
            return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, mt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsxs)(react_native_1.Pressable, { onPress: () => window.location.href = constants_3.zoomOAuthStartUrl, children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray }, children: item?.name }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", children: "Off" }) })] }), (0, jsx_runtime_1.jsx)("span", { className: "btn btn-link no-underline hover:no-underline", children: "Enable Zoom" })] }) }));
        }
        if ((item?.resource === constants_3.zoomResourceName) && item?.enabled) {
            return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, children: (0, jsx_runtime_1.jsx)(IntegrationCheckBox, { updateEnabledValue: updateEnabledValue, index: index, enabled: item?.enabled, name: item?.name, id: item?.id }) }));
        }
        if ((item?.resource === constants_1.googleResourceName) && !item?.enabled) {
            return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, children: (0, jsx_runtime_1.jsx)("a", { target: "_blank", href: constants_1.googleOAuthStartUrl, rel: "noopener noreferrer", children: (0, jsx_runtime_1.jsx)(IntegrationCheckBox, { updateEnabledValue: updateEnabledValue, index: index, enabled: item?.enabled, name: item?.name, id: item?.id, ref: googleCalendarElement }) }) }));
        }
        if ((item?.resource === constants_1.googleResourceName) && item?.enabled) {
            return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, children: (0, jsx_runtime_1.jsx)(IntegrationCheckBox, { updateEnabledValue: updateEnabledValue, index: index, enabled: item?.enabled, name: item?.name, id: item?.id, ref: googleCalendarElement }) }));
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, children: (0, jsx_runtime_1.jsx)(IntegrationCheckBox, { updateEnabledValue: updateEnabledValue, index: index, enabled: item?.enabled, name: item?.name, id: item?.id }) }));
    };
    if (loading || integrationLoading || googleIntegrationLoading) {
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { backgroundColor: "primaryCardBackground", flex: 1, justifyContent: "center", alignItems: "center", style: { width: '100%' }, minHeight: "80vh", children: (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.white }) }));
    }
    if (isGoogleCalendarList) {
        return ((0, jsx_runtime_1.jsx)(UserCalendarList_1.default, { token: googleToken, setIsGoogleCalendarList: setIsGoogleCalendarList }));
    }
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", children: [integrations?.length > 0
                ? ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", minHeight: "70vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(react_native_1.FlatList, { data: integrations, keyExtractor: item => item.id, renderItem: renderItem }) }), googleCalendarEnabled
                            ? ((0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(react_native_1.Pressable, { onPress: navigateToGoogleCalendars, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "buttonLink", children: "View Google Calendars" }) }) })) : (null), (0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, alignItems: "center", width: "100%", mt: "l", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray, marginBottom: 10 }, children: "Gmail Integration" }), (loading && !isGmailStatusLoading) && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { style: { marginTop: 10 }, color: theme_1.palette.primary })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, alignItems: "center", width: "100%", mt: "l", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray, marginBottom: 10 }, children: "Outlook Integration" }), isOutlookStatusLoading ? ((0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "small", color: theme_1.palette.primary, style: { marginTop: 10 } })) : isOutlookConnected ? ((0, jsx_runtime_1.jsxs)(Box_1.default, { alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "body", mb: "s", children: outlookUserEmail ? `Connected as: ${outlookUserEmail}` : "Outlook is connected." }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Disconnect Outlook", onClick: handleDisconnectOutlook, variant: "warning", disabled: loading })] })) : ((0, jsx_runtime_1.jsx)(react_native_1.Pressable, { onPress: handleConnectOutlook, disabled: loading, children: (0, jsx_runtime_1.jsx)(Text_1.default, { children: "Connect Outlook" }) })), (loading && !isOutlookStatusLoading) && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { style: { marginTop: 10 }, color: theme_1.palette.primary })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, alignItems: "center", width: "100%", mt: "l", mb: "l", style: { borderTopWidth: 1, borderTopColor: theme_1.palette.lightGray, paddingTop: 20 }, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray, marginBottom: 10 }, children: "Google Drive Integration (Placeholder)" }), (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "body", style: { textAlign: 'center', color: theme_1.palette.mediumGray }, children: "Management UI for Google Drive connection, file listing, and ingestion would be rendered here using the GDriveManager component." })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, alignItems: "center", width: "100%", mt: "l", mb: "l", style: { borderTopWidth: 1, borderTopColor: theme_1.palette.lightGray, paddingTop: 20 }, children: (0, jsx_runtime_1.jsx)(GithubManager_1.default, {}) }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, pt: { phone: 'm', tablet: 'l' }, alignItems: "center", width: "100%", mt: "l", style: { borderTopWidth: 1, borderTopColor: theme_1.palette.lightGray, paddingTop: 20 }, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray, marginBottom: 10 }, children: "Shopify Integration" }), isShopifyStatusLoading ? ((0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "small", color: theme_1.palette.primary, style: { marginTop: 10 } })) : isShopifyConnected ? ((0, jsx_runtime_1.jsxs)(Box_1.default, { alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "body", mb: "s", children: shopifyShopUrl ? `Connected to: ${shopifyShopUrl}` : "Shopify is connected." }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Disconnect Shopify", onClick: handleDisconnectShopify, variant: "warning", disabled: loading })] })) : ((0, jsx_runtime_1.jsxs)(Box_1.default, { alignItems: "center", children: [(0, jsx_runtime_1.jsx)(TextField, { onChange: (e) => setShopifyShopName(e.target.value), value: shopifyShopName, placeholder: "your-store-name", label: "Shopify Shop Name", style: { width: '80%', marginBottom: 10 }, hint: "Enter your shop name (e.g., 'your-store-name' from 'your-store-name.myshopify.com')" }), (0, jsx_runtime_1.jsx)(Button_1.default, { label: "Connect Shopify", onClick: handleConnectShopify, disabled: loading })] })), (loading && !isShopifyStatusLoading) && (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { style: { marginTop: 10 }, color: theme_1.palette.primary })] })] })) : ((0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", style: { color: theme_1.palette.darkGray }, children: "Still loading" }) })), (0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)(themed_1.Overlay, { overlayStyle: { backgroundColor: theme_1.palette.white, justifyContent: 'center', alignItems: 'center' }, isVisible: isWarning, onBackdropPress: disableGoogleCalendarCheckBox, children: (0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", style: { width: '80%', backgroundColor: theme_1.palette.white }, children: [(0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", children: "Disabling Google Calendar will delete all google related events from your calendar" }) }), (0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: enableGoogleCalendarCheckBox, children: "Okay" }) }), (0, jsx_runtime_1.jsx)(Button_1.default, { cancel: true, onClick: disableGoogleCalendarCheckBox, children: "Cancel" })] })] }) }) })] }));
}
exports.default = UserViewCalendarAndContactIntegrations;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclZpZXdDYWxlbmRhckFuZENvbnRhY3RJbnRlZ3JhdGlvbnMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyVmlld0NhbGVuZGFyQW5kQ29udGFjdEludGVncmF0aW9ucy50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFvTEEsZ0RBcUNDOztBQXpORCxpQ0FNYztBQUNkLCtDQUtzQjtBQUN0Qix1REFBOEI7QUFDOUIsZ0VBQXdDO0FBQ3hDLDRDQUEyQztBQUMzQywwQ0FBdUM7QUFDdkMsK0ZBQXNFO0FBRXRFLDJDQUE4RTtBQUU5RSxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBQzFDLGdFQUF1QztBQUN2Qyw0Q0FBMEM7QUFHMUMseUZBSW1EO0FBQ25ELHVGQUErRDtBQUUvRCwwREFJbUM7QUFFbEMseURBRWtDO0FBR2xDLG1EQUk0QjtBQUU3QixnRkFBc0U7QUFDdEUsd0VBQXVIO0FBRXZILHdHQUErRTtBQUUvRSxzSUFBNkc7QUFFN0csdUdBQTZFO0FBQzdFLHlHQUFxRjtBQUVyRixvREFBaUQ7QUFDakQsd0NBQXVDO0FBdUJ2QyxzREFBc0Q7QUFDdEQsb0dBQW9HO0FBQ3BHLHFGQUFxRjtBQUNyRixNQUFNLG1CQUFtQixHQUFHLG1DQUE4QixDQUFBO0FBQzFELE1BQU0sa0JBQWtCLEdBQUcsa0NBQXVCLENBQUE7QUFFbEQsMkNBQXFDLENBQUMsYUFBYTtBQUVuRCw0REFBNEQ7QUFDNUQsTUFBTSxnQ0FBZ0MsR0FBRyxJQUFBLFlBQUcsRUFBQTs7Ozs7O0NBTTNDLENBQUM7QUFFRixrQ0FBa0M7QUFDbEMsTUFBTSxrQ0FBa0MsR0FBRyxJQUFBLFlBQUcsRUFBQTs7Ozs7O0NBTTdDLENBQUM7QUFFRixNQUFNLG1DQUFtQyxHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7O0NBTzlDLENBQUM7QUFFRixNQUFNLG1DQUFtQyxHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7O0NBTzlDLENBQUM7QUFFRixNQUFNLGtDQUFrQyxHQUFHLElB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RCxrQkFBZSxzQ0FBc0MsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwge1xuICB1c2VTdGF0ZSxcbiAgZm9yd2FyZFJlZixcbiAgdXNlSW1wZXJhdGl2ZUhhbmRsZSxcbiAgdXNlUmVmLFxuICB1c2VFZmZlY3QsXG59IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHtcbiAgRmxhdExpc3QsXG4gIFByZXNzYWJsZSxcbiAgQWN0aXZpdHlJbmRpY2F0b3IsXG4gIFBsYXRmb3JtLFxuIH0gZnJvbSAncmVhY3QtbmF0aXZlJ1xuaW1wb3J0IEltYWdlIGZyb20gJ25leHQvaW1hZ2UnXG5pbXBvcnQgU3dpdGNoMSBmcm9tICdAY29tcG9uZW50cy9Td2l0Y2gnXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5pbXBvcnQgeyBPdmVybGF5IH0gZnJvbSAnQHJuZXVpL3RoZW1lZCdcbmltcG9ydCBVc2VyQ2FsZW5kYXJMaXN0IGZyb20gJ0BwYWdlcy9TZXR0aW5ncy9Hb29nbGUvVXNlckNhbGVuZGFyTGlzdCdcblxuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBOb3JtYWxpemVkQ2FjaGVPYmplY3QsIHVzZVF1ZXJ5IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnXG5cbmltcG9ydCBCb3ggZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL0JveCdcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IEJ1dHRvbiBmcm9tICdAY29tcG9uZW50cy9CdXR0b24nXG5pbXBvcnQgeyBwYWxldHRlIH0gZnJvbSAnQGxpYi90aGVtZS90aGVtZSdcblxuaW1wb3J0IHsgQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhcl9JbnRlZ3JhdGlvblR5cGUnXG5pbXBvcnQge1xuICB1cGRhdGVJbnRlZ3JhdGlvbixcbiAgZGVsZXRlRXZlbnRUcmlnZ2VycyxcbiAgZGVsZXRlRXZlbnRUcmlnZ2VyQnlSZXNvdXJjZUlkLFxuIH0gZnJvbSAnQGxpYi9TZXR0aW5ncy9jYWxlbmRhcl9pbnRlZ3JhdGlvbkhlbHBlcic7XG5pbXBvcnQgR2l0aHViTWFuYWdlciBmcm9tICdAY29tcG9uZW50cy9TZXR0aW5ncy9HaXRodWJNYW5hZ2VyJztcblxuaW1wb3J0IHtcbiAgIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgIGdvb2dsZVJlc291cmNlTmFtZSxcbiAgIGdvb2dsZU9BdXRoU3RhcnRVcmwsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvY29uc3RhbnRzJ1xuXG4gaW1wb3J0IHtcbiAgIGdvb2dsZVBlb3BsZU5hbWUsXG4gfSBmcm9tICdAbGliL2NvbnRhY3RMaWIvY29uc3RhbnRzJ1xuIFxuXG4gaW1wb3J0IHtcbiAgIHpvb21PQXV0aFN0YXJ0VXJsLFxuICAgem9vbVJlc291cmNlTmFtZSxcbiAgIHpvb21OYW1lLFxuIH0gZnJvbSAnQGxpYi96b29tL2NvbnN0YW50cydcblxuaW1wb3J0IHsgZ2V0R29vZ2xlVG9rZW4gfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2dvb2dsZUNhbGVuZGFySGVscGVyJ1xuaW1wb3J0IHsgYnVsa1JlbW92ZUNhbGVuZGFyc0luRGIsIGRlbGV0ZUV2ZW50c0J5Q2FsZW5kYXJJZCwgZ2V0SXRlbXNUb1JlbW92ZSB9IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvY2FsZW5kYXJEYkhlbHBlcidcblxuaW1wb3J0IGxpc3RDYWxlbmRhckludGVncmF0aW9ucyBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdENhbGVuZGFySW50ZWdyYXRpb25zJ1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJ1xuaW1wb3J0IGdldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlQW5kTmFtZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lJ1xuXG5pbXBvcnQgZ29vZ2xlQnV0dG9uTGlnaHROb3JtYWwgZnJvbSAnQGFzc2V0cy9pbWFnZXMvZ29vZ2xlLXNpZ25pbi1ub3JtYWwucG5nJ1xuaW1wb3J0IGdvb2dsZUJ1dHRvblByZXNzZWRMaWdodE5vcm1hbCBmcm9tICdAYXNzZXRzL2ltYWdlcy9nb29nbGUtc2lnbmluLXByZXNzZWQucG5nJ1xuXG5pbXBvcnQgeyB1c2VBcHBDb250ZXh0IH0gZnJvbSAnQGxpYi91c2VyLWNvbnRleHQnXG5pbXBvcnQgeyB1c2VSb3V0ZXIgfSBmcm9tICduZXh0L3JvdXRlcidcblxuXG50eXBlIGNoZWNrQm94UHJvcHMgPSB7XG4gIHVwZGF0ZUVuYWJsZWRWYWx1ZTogKGluZGV4OiBudW1iZXIsIHZhbHVlOiBib29sZWFuLCBpZDogc3RyaW5nKSA9PiBQcm9taXNlPGFueT4sXG4gIGluZGV4OiBudW1iZXIsXG4gIGVuYWJsZWQ6IGJvb2xlYW4sXG4gIG5hbWU6IHN0cmluZyxcbiAgLy8gZGFyazogYm9vbGVhbixcbiAgaWQ6IHN0cmluZyxcbn1cblxudHlwZSBSZW5kZXJJdGVtVHlwZSA9IHtcbiAgaXRlbTogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUsXG4gIGluZGV4OiBudW1iZXIsXG59XG5cbnR5cGUgUHJvcHMgPSB7XG4gIHN1Yjogc3RyaW5nLFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuXG59XG5cbi8vIGNvbnN0IGRhcmsgPSBBcHBlYXJhbmNlLmdldENvbG9yU2NoZW1lKCkgPT09ICdkYXJrJ1xuLy8gY29uc3QgZ29vZ2xlQnV0dG9uUHJlc3NlZCA9IGRhcmsgPyBnb29nbGVCdXR0b25QcmVzc2VkRGFya05vcm1hbCA6IGdvb2dsZUJ1dHRvblByZXNzZWRMaWdodE5vcm1hbFxuLy8gY29uc3QgZ29vZ2xlQnV0dG9uTm9ybWFsID0gZGFyayA/IGdvb2dsZUJ1dHRvbkRhcmtOb3JtYWwgOiBnb29nbGVCdXR0b25MaWdodE5vcm1hbFxuY29uc3QgZ29vZ2xlQnV0dG9uUHJlc3NlZCA9IGdvb2dsZUJ1dHRvblByZXNzZWRMaWdodE5vcm1hbFxuY29uc3QgZ29vZ2xlQnV0dG9uTm9ybWFsID0gZ29vZ2xlQnV0dG9uTGlnaHROb3JtYWxcblxuaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnOyAvLyBJbXBvcnQgZ3FsXG5cbi8vIERlZmluZSB0aGUgR3JhcGhRTCBtdXRhdGlvbiBmb3IgZ2VuZXJhdGluZyBHbWFpbCBBdXRoIFVSTFxuY29uc3QgR0VORVJBVEVfR01BSUxfQVVUSF9VUkxfTVVUQVRJT04gPSBncWxgXG4gIG11dGF0aW9uIEdlbmVyYXRlR21haWxBdXRoVXJsIHtcbiAgICBnZW5lcmF0ZUdtYWlsQXV0aFVybCB7XG4gICAgICBhdXRob3JpemF0aW9uVXJsXG4gICAgfVxuICB9XG5gO1xuXG4vLyBHcmFwaFFMIGZvciBTaG9waWZ5IEludGVncmF0aW9uXG5jb25zdCBHRU5FUkFURV9TSE9QSUZZX0FVVEhfVVJMX01VVEFUSU9OID0gZ3FsYFxuICBtdXRhdGlvbiBHZW5lcmF0ZVNob3BpZnlBdXRoVXJsKCRzaG9wTmFtZTogU3RyaW5nISkge1xuICAgIGdlbmVyYXRlU2hvcGlmeUF1dGhVcmwoc2hvcF9uYW1lOiAkc2hvcE5hbWUpIHtcbiAgICAgIGF1dGhVcmxcbiAgICB9XG4gIH1cbmA7XG5cbmNvbnN0IEdFVF9TSE9QSUZZX0NPTk5FQ1RJT05fU1RBVFVTX1FVRVJZID0gZ3FsYFxuICBxdWVyeSBHZXRTaG9waWZ5Q29ubmVjdGlvblN0YXR1cyB7XG4gICAgZ2V0U2hvcGlmeUNvbm5lY3Rpb25TdGF0dXMge1xuICAgICAgaXNDb25uZWN0ZWRcbiAgICAgIHNob3BVcmxcbiAgICB9XG4gIH1cbmA7XG5cbmNvbnN0IERJU0NPTk5FQ1RfU0hPUElGWV9BQ0NPVU5UX01VVEFUSU9OID0gZ3FsYFxuICBtdXRhdGlvbiBEaXNjb25uZWN0U2hvcGlmeUFjY291bnQge1xuICAgIGRpc2Nvbm5lY3RTaG9waWZ5QWNjb3VudCB7XG4gICAgICBzdWNjZXNzXG4gICAgICBtZXNzYWdlXG4gICAgfVxuICB9XG5gO1xuXG5jb25zdCBHRU5FUkFURV9PVVRMT09LX0FVVEhfVVJMX01VVEFUSU9OID0gZ3FsYFxuICBtdXRhdGlvbiBHZW5lcmF0ZU91dGxvb2tBdXRoVXJsIHtcbiAgICBnZW5lcmF0ZU91dGxvb2tBdXRoVXJsIHtcbiAgICAgIGF1dGhVcmxcbiAgICB9XG4gIH1cbmA7XG5cbmNvbnN0IEdFVF9PVVRMT09LX0NPTk5FQ1RJT05fU1RBVFVTX1FVRVJZID0gZ3FsYFxuICBxdWVyeSBHZXRPdXRsb29rQ29ubmVjdGlvblN0YXR1cyB7XG4gICAgZ2V0T3V0bG9va0Nvbm5lY3Rpb25TdGF0dXMge1xuICAgICAgaXNDb25uZWN0ZWRcbiAgICAgIHVzZXJFbWFpbFxuICAgIH1cbiAgfVxuYDtcblxuY29uc3QgRElTQ09OTkVDVF9PVVRMT09LX0FDQ09VTlRfTVVUQVRJT04gPSBncWxgXG4gIG11dGF0aW9uIERpc2Nvbm5lY3RPdXRsb29rQWNjb3VudCB7XG4gICAgZGlzY29ubmVjdE91dGxvb2tBY2NvdW50IHtcbiAgICAgIHN1Y2Nlc3NcbiAgICAgIG1lc3NhZ2VcbiAgICB9XG4gIH1cbmA7XG5cbi8vIEdyYXBoUUwgZm9yIEdtYWlsIENvbm5lY3Rpb24gU3RhdHVzIGFuZCBEaXNjb25uZWN0XG5jb25zdCBHRVRfR01BSUxfQ09OTkVDVElPTl9TVEFUVVNfUVVFUlkgPSBncWxgXG4gIHF1ZXJ5IEdldEdtYWlsQ29ubmVjdGlvblN0YXR1cyB7XG4gICAgZ2V0R21haWxDb25uZWN0aW9uU3RhdHVzIHtcbiAgICAgIGlzQ29ubmVjdGVkXG4gICAgICB1c2VyRW1haWxcbiAgICB9XG4gIH1cbmA7XG5cbmNvbnN0IERJU0NPTk5FQ1RfR01BSUxfQUNDT1VOVF9NVVRBVElPTiA9IGdxbGBcbiAgbXV0YXRpb24gRGlzY29ubmVjdEdtYWlsQWNjb3VudCB7XG4gICAgZGlzY29ubmVjdEdtYWlsQWNjb3VudCB7XG4gICAgICBzdWNjZXNzXG4gICAgICBtZXNzYWdlXG4gICAgfVxuICB9XG5gO1xuXG5cbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gIC8vIE5vdGljZSBob3cgdGhlIHNlcnZlciB1c2VzIGBBUElgIGZyb20gYHdpdGhTU1JDb250ZXh0YCwgaW5zdGVhZCBvZiB0aGUgdG9wLWxldmVsIGBBUElgLlxuICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gIHN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSlcbiAgbGV0IHNlc3Npb25cbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gW11cbiAgICAgIH0sXG4gICAgfSlcbiAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH0gZWxzZSBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICAvLyB0aGlzIHdpbGwgZm9yY2UgdGhlIGZyb250ZW5kIHRvIHRyeSBhbmQgcmVmcmVzaCB3aGljaCB3aWxsIGZhaWxcbiAgICAgIC8vIGNsZWFyaW5nIGFsbCBjb29raWVzIGFuZCByZWRpcmVjdGluZyB0aGUgdXNlciB0byB0aGUgbG9naW4gc2NyZWVuLlxuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfVxuICAgIHRocm93IGVyclxuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgcHJvcHM6IHtcbiAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICB9XG4gIH1cbn1cblxuLy8gZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIHJlYWN0L2Rpc3BsYXktbmFtZVxuY29uc3QgSW50ZWdyYXRpb25DaGVja0JveCA9IGZvcndhcmRSZWYoKHByb3BzOiBjaGVja0JveFByb3BzLCByZWYpID0+IHtcbiAgICBjb25zdCB7XG4gICAgICBlbmFibGVkOiBvbGRFbmFibGVkLFxuICAgICAgdXBkYXRlRW5hYmxlZFZhbHVlLFxuICAgICAgaW5kZXgsXG4gICAgICBuYW1lLFxuICAgICAgLy8gZGFyayxcbiAgICAgIGlkLFxuICAgIH0gPSBwcm9wc1xuICAgIGNvbnN0IFtlbmFibGVkLCBzZXRFbmFibGVkXSA9IHVzZVN0YXRlPGJvb2xlYW4+KG9sZEVuYWJsZWQpXG4gICAgY29uc3QgW3ByZXNzZWQsIHNldFByZXNzZWRdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIFxuICAgIGNvbnN0IHVwZGF0ZUVuYWJsZWQgPSBhc3luYyAodmFsdWU6IGJvb2xlYW4pID0+IHtcbiAgICAgIHNldEVuYWJsZWQodmFsdWUpXG4gICAgICByZXR1cm4gdXBkYXRlRW5hYmxlZFZhbHVlKGluZGV4LCB2YWx1ZSwgaWQpXG4gICAgfVxuICBcbiAgICBjb25zdCBkaXNhYmxlRW5hYmxlZCA9IGFzeW5jICgpID0+IHtcbiAgICAgIHNldEVuYWJsZWQoZmFsc2UpXG4gICAgICByZXR1cm4gdXBkYXRlRW5hYmxlZFZhbHVlKGluZGV4LCBmYWxzZSwgaWQpXG4gICAgfVxuICBcbiAgICB1c2VJbXBlcmF0aXZlSGFuZGxlKHJlZiwgKCkgPT4gKHtcbiAgICAgICAgZGlzYWJsZUVuYWJsZWQsXG4gICAgfSkpXG5cbiAgICBjb25zdCBvblByZXNzSW4gPSAoKSA9PiBzZXRQcmVzc2VkKHRydWUpXG4gICAgY29uc3Qgb25QcmVzc091dCA9ICgpID0+IHNldFByZXNzZWQoZmFsc2UpXG5cbiAgICBjb25zdCBvblByZXNzID0gYXN5bmMgKCkgPT4gdXBkYXRlRW5hYmxlZCghZW5hYmxlZClcbiAgICAgICAgXG5cbiAgICBpZiAoKG5hbWUgPT09IGdvb2dsZUNhbGVuZGFyTmFtZSkgfHwgKG5hbWUgPT09IGdvb2dsZVBlb3BsZU5hbWUpKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8Qm94IGZsZXg9ezF9IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cInN0cmV0Y2hcIj5cbiAgICAgICAgICAgICAgICA8Qm94IGZsZXg9ezF9IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgIDxCb3ggbXI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIiBzdHlsZT17eyBjb2xvcjogcGFsZXR0ZS5kYXJrR3JheSB9fT5cbiAgICAgICAgICAgICAgICAgICAgICAgIHtuYW1lfVxuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICA8Qm94IG1sPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICAgICAgICAgICAgICAgICAge2VuYWJsZWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA/IDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIj5PbjwvVGV4dD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA6IDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIj5PZmY8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fT5cbiAgICAgICAgICAgICAgICAgICAge2VuYWJsZWRcbiAgICAgICAgICAgICAgICAgICAgICAgID8gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxQcmVzc2FibGUgb25QcmVzcz17b25QcmVzc30+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJidXR0b25MaW5rXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBEaXNhYmxlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L1ByZXNzYWJsZT5cbiAgICAgICAgICAgICAgICAgICAgICAgICkgOiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPFByZXNzYWJsZSBvblByZXNzSW49e29uUHJlc3NJbn0gb25QcmVzc091dD17b25QcmVzc091dH0gb25QcmVzcz17b25QcmVzc30+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxJbWFnZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc3JjPXtwcmVzc2VkID8gZ29vZ2xlQnV0dG9uUHJlc3NlZCA6IGdvb2dsZUJ1dHRvbk5vcm1hbH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0eWxlPXt7IHdpZHRoOiAyNDAsIGhlaWdodDogNTAgfX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFsdD17J2dvb2dsZSBzaWduLWluIGJ1dHRvbid9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9QcmVzc2FibGU+XG4gICAgICAgICAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICB9XG4gIFxuICAgIHJldHVybiAoXG4gICAgICA8Qm94IGZsZXg9ezF9IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnIH19IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgIDxCb3ggbXI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiIHN0eWxlPXt7IGNvbG9yOiBwYWxldHRlLmRhcmtHcmF5IH19PlxuICAgICAgICAgICAge25hbWV9XG4gICAgICAgICAgPC9UZXh0PlxuICAgICAgICA8L0JveD5cbiAgICAgICAgPEJveCBtbD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fT5cbiAgICAgICAgICA8U3dpdGNoMVxuICAgICAgICAgICAgb25WYWx1ZUNoYW5nZT17dXBkYXRlRW5hYmxlZH1cbiAgICAgICAgICAgIGNoZWNrZWQ9e2VuYWJsZWR9XG4gICAgICAgICAgLz5cbiAgICAgICAgPC9Cb3g+XG4gIFxuICAgICAgPC9Cb3g+XG4gICAgKVxufSlcblxuZnVuY3Rpb24gVXNlclZpZXdDYWxlbmRhckFuZENvbnRhY3RJbnRlZ3JhdGlvbnMoKSB7XG4gICAgY29uc3QgW2xvYWRpbmcsIHNldExvYWRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2lzV2FybmluZywgc2V0SXNXYXJuaW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtzZWxlY3RlZEluZGV4LCBzZXRTZWxlY3RlZEluZGV4XSA9IHVzZVN0YXRlPG51bWJlcj4oLTEpXG4gICAgY29uc3QgW3NlbGVjdGVkSWQsIHNldFNlbGVjdGVkSWRdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gICAgY29uc3QgW3NlbGVjdGVkVmFsdWUsIHNldFNlbGVjdGVkVmFsdWVdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgLy8gY29uc3QgW2dvb2dsZUNhbGVuZGFyRW5hYmxlZCwgc2V0R29vZ2xlQ2FsZW5kYXJFbmFibGVkXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtpc0dvb2dsZUNhbGVuZGFyTGlzdCwgc2V0SXNHb29nbGVDYWxlbmRhckxpc3RdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2dvb2dsZVRva2VuLCBzZXRHb29nbGVUb2tlbl0gPSB1c2VTdGF0ZTxzdHJpbmc+KClcblxuICAgIC8vIFN0YXRlIGZvciBHbWFpbCBJbnRlZ3JhdGlvblxuICAgIGNvbnN0IFtpc0dtYWlsQ29ubmVjdGVkLCBzZXRJc0dtYWlsQ29ubmVjdGVkXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKTtcbiAgICBjb25zdCBbZ21haWxVc2VyRW1haWwsIHNldEdtYWlsVXNlckVtYWlsXSA9IHVzZVN0YXRlPHN0cmluZyB8IG51bGw+KG51bGwpO1xuICAgIGNvbnN0IFtpc0dtYWlsU3RhdHVzTG9hZGluZywgc2V0SXNHbWFpbFN0YXR1c0xvYWRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4odHJ1ZSk7XG5cbiAgICAvLyBTdGF0ZSBmb3IgT3V0bG9vayBJbnRlZ3JhdGlvblxuICAgIGNvbnN0IFtpc091dGxvb2tDb25uZWN0ZWQsIHNldElzT3V0bG9va0Nvbm5lY3RlZF0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSk7XG4gICAgY29uc3QgW291dGxvb2tVc2VyRW1haWwsIHNldE91dGxvb2tVc2VyRW1haWxdID0gdXNlU3RhdGU8c3RyaW5nIHwgbnVsbD4obnVsbCk7XG4gICAgY29uc3QgW2lzT3V0bG9va1N0YXR1c0xvYWRpbmcsIHNldElzT3V0bG9va1N0YXR1c0xvYWRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4odHJ1ZSk7XG5cbiAgICAvLyBTdGF0ZSBmb3IgU2hvcGlmeSBJbnRlZ3JhdGlvblxuICAgIGNvbnN0IFtpc1Nob3BpZnlDb25uZWN0ZWQsIHNldElzU2hvcGlmeUNvbm5lY3RlZF0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSk7XG4gICAgY29uc3QgW3Nob3BpZnlTaG9wVXJsLCBzZXRTaG9waWZ5U2hvcFVybF0gPSB1c2VTdGF0ZTxzdHJpbmcgfCBudWxsPihudWxsKTtcbiAgICBjb25zdCBbaXNTaG9waWZ5U3RhdHVzTG9hZGluZywgc2V0SXNTaG9waWZ5U3RhdHVzTG9hZGluZ10gPSB1c2VTdGF0ZTxib29sZWFuPih0cnVlKTtcbiAgICBjb25zdCBbc2hvcGlmeVNob3BOYW1lLCBzZXRTaG9waWZ5U2hvcE5hbWVdID0gdXNlU3RhdGU8c3RyaW5nPignJyk7XG5cblxuICAgIGNvbnN0IGdvb2dsZUNhbGVuZGFyRWxlbWVudCA9IHVzZVJlZjxhbnk+KClcbiAgICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcbiAgICAvLyBjb25zdCBkYXJrID0gdXNlQ29sb3JTY2hlbWUoKSA9PT0gJ2RhcmsnXG4gICAgXG4gICAgY29uc3Qgcm91dGVyID0gdXNlUm91dGVyKClcbiAgICBjb25zdCB7IHN1YiwgY2xpZW50LCAgfSA9IHVzZUFwcENvbnRleHQoKVxuICAgIGNvbnN0IHVzZXJJZCA9IHN1YlxuXG4gICAgY29uc3QgeyBsb2FkaW5nOiBnb29nbGVJbnRlZ3JhdGlvbkxvYWRpbmcsIGVycm9yOiBnb29nbGVJbnRlZ3JhdGlvbkVycm9yLCBkYXRhOiBnb29nbGVJbnRlZ3JhdGlvbkRhdGEsIHJlZmV0Y2g6IGdvb2dsZUludFJlZmV0Y2ggfSA9IHVzZVF1ZXJ5PHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfT4oZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lLCB7XG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgbmFtZTogZ29vZ2xlQ2FsZW5kYXJOYW1lLFxuICAgICAgICAgICAgcmVzb3VyY2U6IGdvb2dsZVJlc291cmNlTmFtZSxcbiAgICAgICAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgICAgICB9XG4gICAgfSlcblxuICAgIGNvbnN0IHsgbG9hZGluZzogaW50ZWdyYXRpb25Mb2FkaW5nLCBlcnJvcjogaW50ZWdyYXRpb25FcnJvciwgZGF0YTogaW50ZWdyYXRpb25EYXRhLCByZWZldGNoOiBjYWxJbnRSZWZldGNoIH0gPSB1c2VRdWVyeTx7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0+KGxpc3RDYWxlbmRhckludGVncmF0aW9ucywge1xuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgICAgICB9XG4gICAgfSlcbiAgICBcbiAgICBjb25zdCBnb29nbGVDYWxlbmRhckVuYWJsZWQgPSBnb29nbGVJbnRlZ3JhdGlvbkRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF0/LmVuYWJsZWRcbiAgICBjb25zdCBpbnRlZ3JhdGlvbnMgPSBpbnRlZ3JhdGlvbkRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uXG4gICAgLy8gY29uc3QgW2ludGVncmF0aW9ucywgc2V0SW50ZWdyYXRpb25zXSA9IHVzZVN0YXRlPENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10+KG9sZEludGVncmF0aW9ucylcblxuICAgIGNvbnNvbGUubG9nKGludGVncmF0aW9ucywgJyBpbnRlZ3JhdGlvbnMnKVxuXG4gICAgLy8gR21haWwgQ29ubmVjdGlvbiBIYW5kbGVyXG4gICAgY29uc3QgaGFuZGxlQ29ubmVjdEdtYWlsID0gYXN5bmMgKCkgPT4ge1xuICAgICAgc2V0TG9hZGluZyh0cnVlKTsgLy8gUmV1c2UgZXhpc3RpbmcgbG9hZGluZyBzdGF0ZVxuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBjbGllbnQubXV0YXRlKHtcbiAgICAgICAgICBtdXRhdGlvbjogR0VORVJBVEVfR01BSUxfQVVUSF9VUkxfTVVUQVRJT04sXG4gICAgICAgIH0pO1xuXG4gICAgICAgIGlmIChyZXNwb25zZS5kYXRhPy5nZW5lcmF0ZUdtYWlsQXV0aFVybD8uYXV0aG9yaXphdGlvblVybCkge1xuICAgICAgICAgIHdpbmRvdy5sb2NhdGlvbi5ocmVmID0gcmVzcG9uc2UuZGF0YS5nZW5lcmF0ZUdtYWlsQXV0aFVybC5hdXRob3JpemF0aW9uVXJsO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byBnZXQgR21haWwgYXV0aG9yaXphdGlvbiBVUkwgZnJvbSBtdXRhdGlvbiByZXNwb25zZTonLCByZXNwb25zZSk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdGYWlsZWQgdG8gZ2V0IEdtYWlsIGF1dGhvcml6YXRpb24gVVJMLicpO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbml0aWF0aW5nIEdtYWlsIGNvbm5lY3Rpb246JywgZXJyb3IpO1xuICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgdGl0bGU6ICdFcnJvciBDb25uZWN0aW5nIEdtYWlsJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogKGVycm9yIGFzIEVycm9yKS5tZXNzYWdlIHx8ICdDb3VsZCBub3QgaW5pdGlhdGUgR21haWwgY29ubmVjdGlvbi4gUGxlYXNlIHRyeSBhZ2Fpbi4nLFxuICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XG4gICAgICB9XG4gICAgICAvLyBzZXRMb2FkaW5nKGZhbHNlKSBtaWdodCBub3QgYmUgcmVhY2hlZCBpZiB3aW5kb3cubG9jYXRpb24uaHJlZiBoYXBwZW5zXG4gICAgfTtcbiAgXG4gIC8vIGp1c3QgaW4gY2FzZVxuIFxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIC8vIEZldGNoIEdtYWlsIGNvbm5lY3Rpb24gc3RhdHVzIG9uIG1vdW50XG4gICAgc2V0SXNHbWFpbFN0YXR1c0xvYWRpbmcodHJ1ZSk7XG4gICAgY2xpZW50LnF1ZXJ5KHsgcXVlcnk6IEdFVF9HTUFJTF9DT05ORUNUSU9OX1NUQVRVU19RVUVSWSwgZmV0Y2hQb2xpY3k6ICduZXR3b3JrLW9ubHknIH0pIC8vIGZldGNoUG9saWN5IHRvIGVuc3VyZSBmcmVzaCBkYXRhXG4gICAgICAudGhlbihyZXNwb25zZSA9PiB7XG4gICAgICAgIGNvbnN0IHN0YXR1cyA9IHJlc3BvbnNlLmRhdGE/LmdldEdtYWlsQ29ubmVjdGlvblN0YXR1cztcbiAgICAgICAgaWYgKHN0YXR1cykge1xuICAgICAgICAgIHNldElzR21haWxDb25uZWN0ZWQoc3RhdHVzLmlzQ29ubmVjdGVkKTtcbiAgICAgICAgICBzZXRHbWFpbFVzZXJFbWFpbChzdGF0dXMudXNlckVtYWlsIHx8IG51bGwpO1xuICAgICAgICB9XG4gICAgICB9KVxuICAgICAgLmNhdGNoKGVyciA9PiB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXCJFcnJvciBmZXRjaGluZyBHbWFpbCBjb25uZWN0aW9uIHN0YXR1czpcIiwgZXJyKTtcbiAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgIHRpdGxlOiAnRXJyb3IgRmV0Y2hpbmcgR21haWwgU3RhdHVzJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogZXJyLm1lc3NhZ2UgfHwgXCJDb3VsZCBub3QgZmV0Y2ggR21haWwgY29ubmVjdGlvbiBkZXRhaWxzLlwiLFxuICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICBkdXJhdGlvbjogNTAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgICAgLy8gQXNzdW1lIG5vdCBjb25uZWN0ZWQgb24gZXJyb3IsIG9yIGtlZXAgY3VycmVudCBzdGF0ZT8gRm9yIG5vdywgYXNzdW1lIG5vdCBjb25uZWN0ZWQuXG4gICAgICAgIHNldElzR21haWxDb25uZWN0ZWQoZmFsc2UpO1xuICAgICAgICBzZXRHbWFpbFVzZXJFbWFpbChudWxsKTtcbiAgICAgIH0pXG4gICAgICAuZmluYWxseSgoKSA9PiB7XG4gICAgICAgIHNldElzR21haWxTdGF0dXNMb2FkaW5nKGZhbHNlKTtcbiAgICAgIH0pO1xuICB9LCBbY2xpZW50LCB0b2FzdF0pOyAvLyBBZGQgY2xpZW50IGFuZCB0b2FzdCB0byBkZXBlbmRlbmN5IGFycmF5XG5cbiAgY29uc3QgaGFuZGxlRGlzY29ubmVjdEdtYWlsID0gYXN5bmMgKCkgPT4ge1xuICAgIHNldExvYWRpbmcodHJ1ZSk7IC8vIFJldXNlIGdlbmVyYWwgbG9hZGluZyBzdGF0ZSwgb3IgdXNlIGEgc3BlY2lmaWMgb25lIGZvciBHbWFpbCBkaXNjb25uZWN0XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50Lm11dGF0ZSh7XG4gICAgICAgIG11dGF0aW9uOiBESVNDT05ORUNUX0dNQUlMX0FDQ09VTlRfTVVUQVRJT04sXG4gICAgICB9KTtcbiAgICAgIGlmIChyZXNwb25zZS5kYXRhPy5kaXNjb25uZWN0R21haWxBY2NvdW50Py5zdWNjZXNzKSB7XG4gICAgICAgIHRvYXN0KHtcbiAgICAgICAgICB0aXRsZTogJ0dtYWlsIERpc2Nvbm5lY3RlZCcsXG4gICAgICAgICAgZGVzY3JpcHRpb246IHJlc3BvbnNlLmRhdGEuZGlzY29ubmVjdEdtYWlsQWNjb3VudC5tZXNzYWdlIHx8ICdTdWNjZXNzZnVsbHkgZGlzY29ubmVjdGVkIHlvdXIgR21haWwgYWNjb3VudC4nLFxuICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgIGR1cmF0aW9uOiA1MDAwLFxuICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgIH0pO1xuICAgICAgICBzZXRJc0dtYWlsQ29ubmVjdGVkKGZhbHNlKTtcbiAgICAgICAgc2V0R21haWxVc2VyRW1haWwobnVsbCk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IocmVzcG9uc2UuZGF0YT8uZGlzY29ubmVjdEdtYWlsQWNjb3VudD8ubWVzc2FnZSB8fCAnRmFpbGVkIHRvIGRpc2Nvbm5lY3QgR21haWwgYWNjb3VudC4nKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgZGlzY29ubmVjdGluZyBHbWFpbDonLCBlcnJvcik7XG4gICAgICB0b2FzdCh7XG4gICAgICAgIHRpdGxlOiAnRXJyb3IgRGlzY29ubmVjdGluZyBHbWFpbCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAoZXJyb3IgYXMgRXJyb3IpLm1lc3NhZ2UgfHwgJ0NvdWxkIG5vdCBkaXNjb25uZWN0IEdtYWlsLiBQbGVhc2UgdHJ5IGFnYWluLicsXG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XG4gICAgfVxuICB9O1xuXG4gIC8vIFNob3BpZnkgQ29ubmVjdGlvbiBIYW5kbGVyXG4gIGNvbnN0IGhhbmRsZUNvbm5lY3RTaG9waWZ5ID0gYXN5bmMgKCkgPT4ge1xuICAgIGlmICghc2hvcGlmeVNob3BOYW1lLnRyaW0oKSkge1xuICAgICAgdG9hc3Qoe1xuICAgICAgICB0aXRsZTogJ1Nob3AgTmFtZSBSZXF1aXJlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnUGxlYXNlIGVudGVyIHlvdXIgU2hvcGlmeSBzaG9wIG5hbWUgKGUuZy4sIG15LWdyZWF0LXN0b3JlKS4nLFxuICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgZHVyYXRpb246IDUwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgc2V0TG9hZGluZyh0cnVlKTtcbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBjbGllbnQubXV0YXRlKHtcbiAgICAgICAgbXV0YXRpb246IEdFTkVSQVRFX1NIT1BJRllfQVVUSF9VUkxfTVVUQVRJT04sXG4gICAgICAgIHZhcmlhYmxlczogeyBzaG9wTmFtZTogc2hvcGlmeVNob3BOYW1lIH0sXG4gICAgICB9KTtcblxuICAgICAgaWYgKHJlc3BvbnNlLmRhdGE/LmdlbmVyYXRlU2hvcGlmeUF1dGhVcmw/LmF1dGhVcmwpIHtcbiAgICAgICAgd2luZG93LmxvY2F0aW9uLmhyZWYgPSByZXNwb25zZS5kYXRhLmdlbmVyYXRlU2hvcGlmeUF1dGhVcmwuYXV0aFVybDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcignRmFpbGVkIHRvIGdldCBTaG9waWZ5IGF1dGhvcml6YXRpb24gVVJMLicpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbml0aWF0aW5nIFNob3BpZnkgY29ubmVjdGlvbjonLCBlcnJvcik7XG4gICAgICB0b2FzdCh7XG4gICAgICAgIHRpdGxlOiAnRXJyb3IgQ29ubmVjdGluZyBTaG9waWZ5JyxcbiAgICAgICAgZGVzY3JpcHRpb246IChlcnJvciBhcyBFcnJvcikubWVzc2FnZSB8fCAnQ291bGQgbm90IGluaXRpYXRlIFNob3BpZnkgY29ubmVjdGlvbi4gUGxlYXNlIHRyeSBhZ2Fpbi4nLFxuICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSk7XG4gICAgICBzZXRMb2FkaW5nKGZhbHNlKTtcbiAgICB9XG4gIH07XG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAvLyBGZXRjaCBTaG9waWZ5IGNvbm5lY3Rpb24gc3RhdHVzIG9uIG1vdW50XG4gICAgc2V0SXNTaG9waWZ5U3RhdHVzTG9hZGluZyh0cnVlKTtcbiAgICBjbGllbnQucXVlcnkoeyBxdWVyeTogR0VUX1NIT1BJRllfQ09OTkVDVElPTl9TVEFUVVNfUVVFUlksIGZldGNoUG9saWN5OiAnbmV0d29yay1vbmx5JyB9KVxuICAgICAgLnRoZW4ocmVzcG9uc2UgPT4ge1xuICAgICAgICBjb25zdCBzdGF0dXMgPSByZXNwb25zZS5kYXRhPy5nZXRTaG9waWZ5Q29ubmVjdGlvblN0YXR1cztcbiAgICAgICAgaWYgKHN0YXR1cykge1xuICAgICAgICAgIHNldElzU2hvcGlmeUNvbm5lY3RlZChzdGF0dXMuaXNDb25uZWN0ZWQpO1xuICAgICAgICAgIHNldFNob3BpZnlTaG9wVXJsKHN0YXR1cy5zaG9wVXJsIHx8IG51bGwpO1xuICAgICAgICB9XG4gICAgICB9KVxuICAgICAgLmNhdGNoKGVyciA9PiB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXCJFcnJvciBmZXRjaGluZyBTaG9waWZ5IGNvbm5lY3Rpb24gc3RhdHVzOlwiLCBlcnIpO1xuICAgICAgICAvLyBBc3N1bWUgbm90IGNvbm5lY3RlZCBvbiBlcnJvclxuICAgICAgICBzZXRJc1Nob3BpZnlDb25uZWN0ZWQoZmFsc2UpO1xuICAgICAgICBzZXRTaG9waWZ5U2hvcFVybChudWxsKTtcbiAgICAgIH0pXG4gICAgICAuZmluYWxseSgoKSA9PiB7XG4gICAgICAgIHNldElzU2hvcGlmeVN0YXR1c0xvYWRpbmcoZmFsc2UpO1xuICAgICAgfSk7XG4gIH0sIFtjbGllbnQsIHRvYXN0XSk7XG5cbiAgY29uc3QgaGFuZGxlRGlzY29ubmVjdFNob3BpZnkgPSBhc3luYyAoKSA9PiB7XG4gICAgc2V0TG9hZGluZyh0cnVlKTtcbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBjbGllbnQubXV0YXRlKHtcbiAgICAgICAgbXV0YXRpb246IERJU0NPTk5FQ1RfU0hPUElGWV9BQ0NPVU5UX01VVEFUSU9OLFxuICAgICAgfSk7XG4gICAgICBpZiAocmVzcG9uc2UuZGF0YT8uZGlzY29ubmVjdFNob3BpZnlBY2NvdW50Py5zdWNjZXNzKSB7XG4gICAgICAgIHRvYXN0KHtcbiAgICAgICAgICB0aXRsZTogJ1Nob3BpZnkgRGlzY29ubmVjdGVkJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogcmVzcG9uc2UuZGF0YS5kaXNjb25uZWN0U2hvcGlmeUFjY291bnQubWVzc2FnZSB8fCAnU3VjY2Vzc2Z1bGx5IGRpc2Nvbm5lY3RlZCB5b3VyIFNob3BpZnkgYWNjb3VudC4nLFxuICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgIGR1cmF0aW9uOiA1MDAwLFxuICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgIH0pO1xuICAgICAgICBzZXRJc1Nob3BpZnlDb25uZWN0ZWQoZmFsc2UpO1xuICAgICAgICBzZXRTaG9waWZ5U2hvcFVybChudWxsKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihyZXNwb25zZS5kYXRhPy5kaXNjb25uZWN0U2hvcGlmeUFjY291bnQ/Lm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBkaXNjb25uZWN0IFNob3BpZnkgYWNjb3VudC4nKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgZGlzY29ubmVjdGluZyBTaG9waWZ5OicsIGVycm9yKTtcbiAgICAgIHRvYXN0KHtcbiAgICAgICAgdGl0bGU6ICdFcnJvciBEaXNjb25uZWN0aW5nIFNob3BpZnknLFxuICAgICAgICBkZXNjcmlwdGlvbjogKGVycm9yIGFzIEVycm9yKS5tZXNzYWdlIHx8ICdDb3VsZCBub3QgZGlzY29ubmVjdCBTaG9waWZ5LiBQbGVhc2UgdHJ5IGFnYWluLicsXG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XG4gICAgfVxuICB9O1xuXG4gIC8vIE91dGxvb2sgQ29ubmVjdGlvbiBIYW5kbGVyXG4gIGNvbnN0IGhhbmRsZUNvbm5lY3RPdXRsb29rID0gYXN5bmMgKCkgPT4ge1xuICAgIHNldExvYWRpbmcodHJ1ZSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50Lm11dGF0ZSh7XG4gICAgICAgIG11dGF0aW9uOiBHRU5FUkFURV9PVVRMT09LX0FVVEhfVVJMX01VVEFUSU9OLFxuICAgICAgfSk7XG5cbiAgICAgIGlmIChyZXNwb25zZS5kYXRhPy5nZW5lcmF0ZU91dGxvb2tBdXRoVXJsPy5hdXRoVXJsKSB7XG4gICAgICAgIHdpbmRvdy5sb2NhdGlvbi5ocmVmID0gcmVzcG9uc2UuZGF0YS5nZW5lcmF0ZU91dGxvb2tBdXRoVXJsLmF1dGhVcmw7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ0ZhaWxlZCB0byBnZXQgT3V0bG9vayBhdXRob3JpemF0aW9uIFVSTC4nKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgaW5pdGlhdGluZyBPdXRsb29rIGNvbm5lY3Rpb246JywgZXJyb3IpO1xuICAgICAgdG9hc3Qoe1xuICAgICAgICB0aXRsZTogJ0Vycm9yIENvbm5lY3RpbmcgT3V0bG9vaycsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAoZXJyb3IgYXMgRXJyb3IpLm1lc3NhZ2UgfHwgJ0NvdWxkIG5vdCBpbml0aWF0ZSBPdXRsb29rIGNvbm5lY3Rpb24uIFBsZWFzZSB0cnkgYWdhaW4uJyxcbiAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pO1xuICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XG4gICAgfVxuICB9O1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgLy8gRmV0Y2ggT3V0bG9vayBjb25uZWN0aW9uIHN0YXR1cyBvbiBtb3VudFxuICAgIHNldElzT3V0bG9va1N0YXR1c0xvYWRpbmcodHJ1ZSk7XG4gICAgY2xpZW50LnF1ZXJ5KHsgcXVlcnk6IEdFVF9PVVRMT09LX0NPTk5FQ1RJT05fU1RBVFVTX1FVRVJZLCBmZXRjaFBvbGljeTogJ25ldHdvcmstb25seScgfSlcbiAgICAgIC50aGVuKHJlc3BvbnNlID0+IHtcbiAgICAgICAgY29uc3Qgc3RhdHVzID0gcmVzcG9uc2UuZGF0YT8uZ2V0T3V0bG9va0Nvbm5lY3Rpb25TdGF0dXM7XG4gICAgICAgIGlmIChzdGF0dXMpIHtcbiAgICAgICAgICBzZXRJc091dGxvb2tDb25uZWN0ZWQoc3RhdHVzLmlzQ29ubmVjdGVkKTtcbiAgICAgICAgICBzZXRPdXRsb29rVXNlckVtYWlsKHN0YXR1cy51c2VyRW1haWwgfHwgbnVsbCk7XG4gICAgICAgIH1cbiAgICAgIH0pXG4gICAgICAuY2F0Y2goZXJyID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcihcIkVycm9yIGZldGNoaW5nIE91dGxvb2sgY29ubmVjdGlvbiBzdGF0dXM6XCIsIGVycik7XG4gICAgICAgIC8vIEFzc3VtZSBub3QgY29ubmVjdGVkIG9uIGVycm9yXG4gICAgICAgIHNldElzT3V0bG9va0Nvbm5lY3RlZChmYWxzZSk7XG4gICAgICAgIHNldE91dGxvb2tVc2VyRW1haWwobnVsbCk7XG4gICAgICB9KVxuICAgICAgLmZpbmFsbHkoKCkgPT4ge1xuICAgICAgICBzZXRJc091dGxvb2tTdGF0dXNMb2FkaW5nKGZhbHNlKTtcbiAgICAgIH0pO1xuICB9LCBbY2xpZW50LCB0b2FzdF0pO1xuXG4gIGNvbnN0IGhhbmRsZURpc2Nvbm5lY3RPdXRsb29rID0gYXN5bmMgKCkgPT4ge1xuICAgIHNldExvYWRpbmcodHJ1ZSk7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50Lm11dGF0ZSh7XG4gICAgICAgIG11dGF0aW9uOiBESVNDT05ORUNUX09VVExPT0tfQUNDT1VOVF9NVVRBVElPTixcbiAgICAgIH0pO1xuICAgICAgaWYgKHJlc3BvbnNlLmRhdGE/LmRpc2Nvbm5lY3RPdXRsb29rQWNjb3VudD8uc3VjY2Vzcykge1xuICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgdGl0bGU6ICdPdXRsb29rIERpc2Nvbm5lY3RlZCcsXG4gICAgICAgICAgZGVzY3JpcHRpb246IHJlc3BvbnNlLmRhdGEuZGlzY29ubmVjdE91dGxvb2tBY2NvdW50Lm1lc3NhZ2UgfHwgJ1N1Y2Nlc3NmdWxseSBkaXNjb25uZWN0ZWQgeW91ciBPdXRsb29rIGFjY291bnQuJyxcbiAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICBkdXJhdGlvbjogNTAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgICAgc2V0SXNPdXRsb29rQ29ubmVjdGVkKGZhbHNlKTtcbiAgICAgICAgc2V0T3V0bG9va1VzZXJFbWFpbChudWxsKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihyZXNwb25zZS5kYXRhPy5kaXNjb25uZWN0T3V0bG9va0FjY291bnQ/Lm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBkaXNjb25uZWN0IE91dGxvb2sgYWNjb3VudC4nKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcignRXJyb3IgZGlzY29ubmVjdGluZyBPdXRsb29rOicsIGVycm9yKTtcbiAgICAgIHRvYXN0KHtcbiAgICAgICAgdGl0bGU6ICdFcnJvciBEaXNjb25uZWN0aW5nIE91dGxvb2snLFxuICAgICAgICBkZXNjcmlwdGlvbjogKGVycm9yIGFzIEVycm9yKS5tZXNzYWdlIHx8ICdDb3VsZCBub3QgZGlzY29ubmVjdCBPdXRsb29rLiBQbGVhc2UgdHJ5IGFnYWluLicsXG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KTtcbiAgICB9IGZpbmFsbHkge1xuICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XG4gICAgfVxuICB9O1xuXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICAgIGlmIChnb29nbGVDYWxlbmRhckVuYWJsZWQpIHtcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdpbmZvJyxcbiAgICAgICAgICAgICAgICB0aXRsZTogJ0VuYWJsZSBhIGNhbGVuZGFyIGZyb20gR29vZ2xlJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBjbGljayBvbiBWaWV3IEdvb2dsZSBDYWxlbmRhcnMgYW5kIGVuYWJsZSBhdCBsZWFzdCAxIGNhbGVuZGFyIHRvIHVzZSBBdG9taWMnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICB9KVxuICAgICAgICB9XG4gICAgfSwgW2dvb2dsZUNhbGVuZGFyRW5hYmxlZCwgdG9hc3RdKVxuXG4gIGNvbnN0IGRpc2FibGVHb29nbGVDYWxlbmRhckNoZWNrQm94ID0gKCkgPT4ge1xuICAgIHNldFNlbGVjdGVkSW5kZXgoLTEpXG4gICAgc2V0U2VsZWN0ZWRJZCgnJylcbiAgICBzZXRTZWxlY3RlZFZhbHVlKGZhbHNlKVxuICAgIHNldElzV2FybmluZyhmYWxzZSlcbiAgICBnb29nbGVDYWxlbmRhckVsZW1lbnQuY3VycmVudC5kaXNhYmxlRW5hYmxlZCgpXG4gIH1cblxuICBjb25zdCBlbmFibGVHb29nbGVDYWxlbmRhckNoZWNrQm94ID0gYXN5bmMgKCkgPT4ge1xuICAgIHRyeSB7XG4gICAgICBzZXRJc1dhcm5pbmcoZmFsc2UpXG4gICAgICAvLyBjb25zdCBuZXdJbnRlZ3JhdGlvbnMgPSBpbnRlZ3JhdGlvbnNcbiAgICAgIC8vICAgLnNsaWNlKDAsIHNlbGVjdGVkSW5kZXgpXG4gICAgICAvLyAgIC5jb25jYXQoW3sgLi4uKGludGVncmF0aW9ucz8uW3NlbGVjdGVkSW5kZXhdKSwgZW5hYmxlZDogc2VsZWN0ZWRWYWx1ZSB9XSlcbiAgICAgIC8vICAgLmNvbmNhdChpbnRlZ3JhdGlvbnMuc2xpY2Uoc2VsZWN0ZWRJbmRleCArIDEpKVxuXG4gICAgICAvLyBzZXRJbnRlZ3JhdGlvbnMobmV3SW50ZWdyYXRpb25zKVxuXG4gICAgICBhd2FpdCBzdWJtaXRJbnRlZ3JhdGlvbihcbiAgICAgICAgc2VsZWN0ZWRJbmRleCxcbiAgICAgICAgc2VsZWN0ZWRWYWx1ZSxcbiAgICAgICAgc2VsZWN0ZWRJZCxcbiAgICAgIClcblxuICAgICAgYXdhaXQgZ29vZ2xlSW50UmVmZXRjaCgpXG4gICAgICBhd2FpdCBjYWxJbnRSZWZldGNoKClcblxuICAgICAgc2V0U2VsZWN0ZWRJbmRleCgtMSlcbiAgICAgIHNldFNlbGVjdGVkSWQoJycpXG4gICAgICBzZXRTZWxlY3RlZFZhbHVlKGZhbHNlKVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgIHNldElzV2FybmluZyhmYWxzZSlcbiAgICAgIGNvbnNvbGUubG9nKGUsICcgdGhpcyBpcyBlcnJvciBmb3IgZW5hYmxlIGdvb2dsZSBjYWxlbmRhciBjaGVja2JveCcpXG4gICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgdGl0bGU6ICdFcnJvcicsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnU29tZXRoaW5nIHdlbnQgd3JvbmcnLFxuICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pXG4gICAgfVxuICB9XG5cbiAgY29uc3QgdXBkYXRlRW5hYmxlZFZhbHVlID0gYXN5bmMgKGluZGV4OiBudW1iZXIsIHZhbHVlOiBib29sZWFuLCBpZDogc3RyaW5nKSA9PiB7XG4gICAgY29uc3Qgc2VsZWN0ZWRJbnRlZ3JhdGlvbiA9IGludGVncmF0aW9uc1tpbmRleF1cbiAgICBpZiAoXG4gICAgICAoc2VsZWN0ZWRJbnRlZ3JhdGlvbi5uYW1lID09PSBnb29nbGVDYWxlbmRhck5hbWUpXG4gICAgICAmJiAodmFsdWUgPT09IGZhbHNlKVxuICAgICkge1xuICAgICAgc2V0U2VsZWN0ZWRJbmRleChpbmRleClcbiAgICAgIHNldFNlbGVjdGVkSWQoaWQpXG4gICAgICBzZXRTZWxlY3RlZFZhbHVlKHZhbHVlKVxuICAgICAgc2V0SXNXYXJuaW5nKHRydWUpXG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIGNvbnN0IG5ld0ludGVncmF0aW9ucyA9IGludGVncmF0aW9uc1xuICAgICAgLy8gLnNsaWNlKDAsIGluZGV4KVxuICAgICAgLy8gLmNvbmNhdChbeyAuLi4oaW50ZWdyYXRpb25zPy5baW5kZXhdKSwgZW5hYmxlZDogdmFsdWUgfV0pXG4gICAgICAvLyAuY29uY2F0KGludGVncmF0aW9ucy5zbGljZShpbmRleCArIDEpKVxuXG4gICAgICAvLyBzZXRJbnRlZ3JhdGlvbnMobmV3SW50ZWdyYXRpb25zKVxuXG4gICAgICBhd2FpdCBzdWJtaXRJbnRlZ3JhdGlvbihcbiAgICAgICAgaW5kZXgsXG4gICAgICAgIHZhbHVlLFxuICAgICAgICBpZCxcbiAgICAgIClcblxuICAgICAgYXdhaXQgZ29vZ2xlSW50UmVmZXRjaCgpXG4gICAgICBhd2FpdCBjYWxJbnRSZWZldGNoKClcbiAgICB9XG4gICAgXG4gIH1cblxuICBjb25zdCBkaXNhYmxlR29vZ2xlQ2FsZW5kYXJTeW5jID0gYXN5bmMgKFxuICAgIGludGVncmF0aW9uSWQ6IHN0cmluZ1xuICApID0+IHtcbiAgICB0cnkge1xuICAgICAgYXdhaXQgdXBkYXRlSW50ZWdyYXRpb24oXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgaW50ZWdyYXRpb25JZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIG51bGwsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgbnVsbCxcbiAgICAgIClcbiAgICAgIFxuICAgICAgYXdhaXQgZGVsZXRlRXZlbnRUcmlnZ2Vycyh1c2VySWQsIGdvb2dsZVJlc291cmNlTmFtZSwgZ29vZ2xlQ2FsZW5kYXJOYW1lKVxuICAgICAgXG4gICAgICBjb25zdCBpdGVtc1RvUmVtb3ZlID0gYXdhaXQgZ2V0SXRlbXNUb1JlbW92ZShjbGllbnQsIHVzZXJJZCwgZ29vZ2xlUmVzb3VyY2VOYW1lKVxuICAgICAgXG4gICAgICBhd2FpdCBidWxrUmVtb3ZlQ2FsZW5kYXJzSW5EYihjbGllbnQsIGl0ZW1zVG9SZW1vdmUubWFwKGkgPT4gKGk/LmlkKSkpXG5cbiAgICAgIC8vIGJ1bGsgcmVtb3ZlIGV2ZW50cyBmcm9tIGRiXG4gICAgICBjb25zdCBldmVudHNUb1JlbW92ZVByb21pc2UgPSBbXVxuXG4gICAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgaXRlbXNUb1JlbW92ZSkge1xuICAgICAgICBpZiAoaXRlbT8uaWQpIHtcbiAgICAgICAgICBldmVudHNUb1JlbW92ZVByb21pc2UucHVzaChcbiAgICAgICAgICAgIGRlbGV0ZUV2ZW50c0J5Q2FsZW5kYXJJZChjbGllbnQsIGl0ZW0uaWQpXG4gICAgICAgICAgKVxuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGF3YWl0IFByb21pc2UuYWxsKGV2ZW50c1RvUmVtb3ZlUHJvbWlzZSlcblxuICAgICAgYXdhaXQgZ29vZ2xlSW50UmVmZXRjaCgpXG4gICAgICBhd2FpdCBjYWxJbnRSZWZldGNoKClcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIHRoaXMgaXMgZSBmb3IgZGlzYWJsZSBnb29nbGUgY2FsZW5kYXJzeW5jJylcbiAgICAgIGF3YWl0IGNhbEludFJlZmV0Y2goKVxuICAgICAgYXdhaXQgZ29vZ2xlSW50UmVmZXRjaCgpXG4gICAgfVxuICB9XG5cbiAgY29uc3QgZGlzYWJsZVpvb21BdXRoID0gYXN5bmMgKFxuICAgIGludGVncmF0aW9uSWQ6IHN0cmluZyxcbiAgKTogUHJvbWlzZTx2b2lkPiA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICAgIGF3YWl0IHVwZGF0ZUludGVncmF0aW9uKFxuICAgICAgICAgICAgICBjbGllbnQsXG4gICAgICAgICAgICAgIGludGVncmF0aW9uSWQsXG4gICAgICAgICAgICAgIGZhbHNlLFxuICAgICAgICAgICAgICBudWxsLFxuICAgICAgICAgICAgICBudWxsLFxuICAgICAgICAgICAgICBudWxsLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgbnVsbCxcbiAgICAgICAgICAgICAgbnVsbCxcbiAgICAgICAgICApXG4gICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGlzYWJsZSB6b29tIGF1dGgnKVxuICAgICAgfVxuICB9XG5cblxuICBjb25zdCBkaXNhYmxlR29vZ2xlQ29udGFjdFN5bmMgPSBhc3luYyAoXG4gICAgaW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICApID0+IHtcbiAgICB0cnkge1xuICAgICAgYXdhaXQgdXBkYXRlSW50ZWdyYXRpb24oXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgaW50ZWdyYXRpb25JZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIG51bGwsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgbnVsbCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIG51bGwsXG4gICAgICAgIG51bGwsXG4gICAgICApXG4gICAgICAvLyBkZWxldGUgZXZlbnQgdHJpZ2dlcnNcbiAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZChpbnRlZ3JhdGlvbklkKVxuXG4gICAgICBhd2FpdCBnb29nbGVJbnRSZWZldGNoKClcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIGluIGRpc2FibGVHb29nbGVDb250YWN0U3luYycpXG4gICAgfVxuICB9XG5cbiAgY29uc3Qgc3VibWl0SW50ZWdyYXRpb24gPSBhc3luYyAoaW5kZXg6IG51bWJlciwgbmV3RW5hYmxlZDogYm9vbGVhbiwgaWQ6IHN0cmluZykgPT4ge1xuICAgIHRyeSB7XG4gICAgICBpZiAobmV3RW5hYmxlZCA9PT0gZmFsc2UpIHtcbiAgICAgICAgLy8gZGVsZXRlIHRyaWdnZXJzXG4gICAgICAgIGlmIChpbnRlZ3JhdGlvbnM/LltpbmRleF0/Lm5hbWUgPT09IGdvb2dsZVBlb3BsZU5hbWUpIHtcblxuICAgICAgICAgIHJldHVybiBkaXNhYmxlR29vZ2xlQ29udGFjdFN5bmMoaW50ZWdyYXRpb25zPy5baW5kZXhdPy5pZClcbiAgICAgICAgfSBlbHNlIGlmIChpbnRlZ3JhdGlvbnM/LltpbmRleF0/Lm5hbWUgPT09IGdvb2dsZUNhbGVuZGFyTmFtZSkge1xuXG4gICAgICAgICAgcmV0dXJuIGRpc2FibGVHb29nbGVDYWxlbmRhclN5bmMoaW50ZWdyYXRpb25zPy5baW5kZXhdPy5pZClcbiAgICAgICAgfSBlbHNlIGlmIChpbnRlZ3JhdGlvbnM/LltpbmRleF0/LnJlc291cmNlID09PSB6b29tUmVzb3VyY2VOYW1lKSB7XG4gICAgICAgICAgICAgICBcbiAgICAgICAgICByZXR1cm4gZGlzYWJsZVpvb21BdXRoKGludGVncmF0aW9ucz8uW2luZGV4XT8uaWQpXG4gICAgICB9XG5cbiAgICAgICAgcmV0dXJuIHVwZGF0ZUludGVncmF0aW9uKFxuICAgICAgICAgIGNsaWVudCxcbiAgICAgICAgICBpZCxcbiAgICAgICAgICBuZXdFbmFibGVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIGZhbHNlLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIGludGVncmF0aW9ucz8uW2luZGV4XT8ucmVzb3VyY2UgPT09IGdvb2dsZVJlc291cmNlTmFtZSA/ICdhdG9taWMtd2ViJyA6ICd3ZWInLFxuICAgICAgICApXG4gICAgICB9XG5cbiAgICB9IGNhdGNoKGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHN1Ym1pdCBpbnRlZ3JhdGlvbnMnKVxuICAgICAgc2V0TG9hZGluZyhmYWxzZSlcbiAgICAgIHRvYXN0KHtcbiAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICB0aXRsZTogJ1VuYWJsZSB0byBzdWJtaXQgaW50ZWdyYXRpb24nLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSB0cnkgYWdhaW4nLFxuICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pXG4gICAgfVxuICB9XG5cbiAgY29uc3QgbmF2aWdhdGVUb0dvb2dsZUNhbGVuZGFycyA9IGFzeW5jICgpID0+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgbmV3QWNjZXNzVG9rZW4gPSBhd2FpdCBnZXRHb29nbGVUb2tlbihjbGllbnQsIHVzZXJJZClcbiAgICAgIHNldEdvb2dsZVRva2VuKG5ld0FjY2Vzc1Rva2VuKVxuICAgICAgLy8gcmV0dXJuIHJvdXRlci5wdXNoKHsgcGF0aG5hbWU6ICcvU2V0dGluZ3MvR29vZ2xlL1VzZXJDYWxlbmRhckxpc3QnLCBxdWVyeTogeyB0b2tlbjogbmV3QWNjZXNzVG9rZW4gfX0pXG4gICAgICBzZXRJc0dvb2dsZUNhbGVuZGFyTGlzdCh0cnVlKVxuICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbmF2aWdhdGUgdG8gZ29vZ2xlIGNhbGVuZGFycycpXG5cbiAgICB9XG4gIH1cblxuICBjb25zdCByZW5kZXJJdGVtID0gKHsgaXRlbSwgaW5kZXggfTogUmVuZGVySXRlbVR5cGUpID0+IHtcbiAgICBpZiAoKGl0ZW0/LnJlc291cmNlID09PSB6b29tUmVzb3VyY2VOYW1lKSAmJiAhaXRlbT8uZW5hYmxlZCkge1xuICAgICAgcmV0dXJuIChcbiAgICAgICAgPEJveCBmbGV4PXsxfSBtdD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICA8UHJlc3NhYmxlIG9uUHJlc3M9eygpID0+IHdpbmRvdy5sb2NhdGlvbi5ocmVmID0gem9vbU9BdXRoU3RhcnRVcmx9PlxuICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICA8Qm94IG1yPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIiBzdHlsZT17eyBjb2xvcjogcGFsZXR0ZS5kYXJrR3JheSB9fT5cbiAgICAgICAgICAgICAgICAgIHtpdGVtPy5uYW1lfVxuICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgIDxCb3ggbWw9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiPk9mZjwvVGV4dD5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxzcGFuIGNsYXNzTmFtZT1cImJ0biBidG4tbGluayBuby11bmRlcmxpbmUgaG92ZXI6bm8tdW5kZXJsaW5lXCI+RW5hYmxlIFpvb208L3NwYW4+XG4gICAgICAgICAgPC9QcmVzc2FibGU+XG4gICAgICAgIDwvQm94PlxuICAgICAgKVxuICAgIH1cblxuICAgIGlmICgoaXRlbT8ucmVzb3VyY2UgPT09IHpvb21SZXNvdXJjZU5hbWUpICYmIGl0ZW0/LmVuYWJsZWQpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxCb3ggZmxleD17MX0+XG5cbiAgICAgICAgICAgICAgICAgICAgPEludGVncmF0aW9uQ2hlY2tCb3hcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZUVuYWJsZWRWYWx1ZT17dXBkYXRlRW5hYmxlZFZhbHVlfVxuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg9e2luZGV4fVxuICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlZD17aXRlbT8uZW5hYmxlZH1cbiAgICAgICAgICAgICAgICAgICAgICAgIG5hbWU9e2l0ZW0/Lm5hbWV9XG4gICAgICAgICAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkPXtpdGVtPy5pZH1cbiAgICAgICAgICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICB9XG5cbiAgICBpZiAoKGl0ZW0/LnJlc291cmNlID09PSBnb29nbGVSZXNvdXJjZU5hbWUpICYmICFpdGVtPy5lbmFibGVkKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8Qm94IGZsZXg9ezF9PlxuICAgICAgICAgICAgICAgIDxhIHRhcmdldD1cIl9ibGFua1wiIGhyZWY9e2dvb2dsZU9BdXRoU3RhcnRVcmx9IHJlbD1cIm5vb3BlbmVyIG5vcmVmZXJyZXJcIj5cbiAgICAgICAgICAgICAgICAgICAgPEludGVncmF0aW9uQ2hlY2tCb3hcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZUVuYWJsZWRWYWx1ZT17dXBkYXRlRW5hYmxlZFZhbHVlfVxuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg9e2luZGV4fVxuICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlZD17aXRlbT8uZW5hYmxlZH1cbiAgICAgICAgICAgICAgICAgICAgICAgIG5hbWU9e2l0ZW0/Lm5hbWV9XG4gICAgICAgICAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkPXtpdGVtPy5pZH1cbiAgICAgICAgICAgICAgICAgICAgICAgIHJlZj17Z29vZ2xlQ2FsZW5kYXJFbGVtZW50fVxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgIDwvYT5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgfVxuXG4gICAgaWYgKChpdGVtPy5yZXNvdXJjZSA9PT0gZ29vZ2xlUmVzb3VyY2VOYW1lKSAmJiBpdGVtPy5lbmFibGVkKSB7XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8Qm94IGZsZXg9ezF9PlxuXG4gICAgICAgICAgICAgICAgPEludGVncmF0aW9uQ2hlY2tCb3hcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlRW5hYmxlZFZhbHVlPXt1cGRhdGVFbmFibGVkVmFsdWV9XG4gICAgICAgICAgICAgICAgICAgIGluZGV4PXtpbmRleH1cbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlZD17aXRlbT8uZW5hYmxlZH1cbiAgICAgICAgICAgICAgICAgICAgbmFtZT17aXRlbT8ubmFtZX1cbiAgICAgICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgICAgIGlkPXtpdGVtPy5pZH1cbiAgICAgICAgICAgICAgICAgICAgcmVmPXtnb29nbGVDYWxlbmRhckVsZW1lbnR9XG4gICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgfVxuXG4gICAgcmV0dXJuIChcbiAgICAgIDxCb3ggZmxleD17MX0+XG4gICAgICAgIDxJbnRlZ3JhdGlvbkNoZWNrQm94XG4gICAgICAgICAgdXBkYXRlRW5hYmxlZFZhbHVlPXt1cGRhdGVFbmFibGVkVmFsdWV9XG4gICAgICAgICAgaW5kZXg9e2luZGV4fVxuICAgICAgICAgIGVuYWJsZWQ9e2l0ZW0/LmVuYWJsZWR9XG4gICAgICAgICAgbmFtZT17aXRlbT8ubmFtZX1cbiAgICAgICAgICBcbiAgICAgICAgICBpZD17aXRlbT8uaWR9XG4gICAgICAgICAgLz5cbiAgICAgIDwvQm94PlxuICAgIClcbiAgfVxuXG4gIGlmIChsb2FkaW5nIHx8IGludGVncmF0aW9uTG9hZGluZyB8fCBnb29nbGVJbnRlZ3JhdGlvbkxvYWRpbmcpIHtcbiAgICByZXR1cm4gKFxuICAgICAgPEJveCBiYWNrZ3JvdW5kQ29sb3I9XCJwcmltYXJ5Q2FyZEJhY2tncm91bmRcIiBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzEwMCUnfX0gbWluSGVpZ2h0PVwiODB2aFwiPlxuICAgICAgICAgIDxBY3Rpdml0eUluZGljYXRvciBzaXplPVwibGFyZ2VcIiBjb2xvcj17cGFsZXR0ZS53aGl0ZX0gLz5cbiAgICAgIDwvQm94PlxuICAgIClcbiAgfVxuXG4gIGlmIChpc0dvb2dsZUNhbGVuZGFyTGlzdCkge1xuICAgIHJldHVybiAoXG4gICAgICA8VXNlckNhbGVuZGFyTGlzdFxuICAgICAgICB0b2tlbj17Z29vZ2xlVG9rZW59XG4gICAgICAgIHNldElzR29vZ2xlQ2FsZW5kYXJMaXN0PXtzZXRJc0dvb2dsZUNhbGVuZGFyTGlzdH1cbiAgICAgIC8+XG4gICAgKVxuICB9XG5cblxuICByZXR1cm4gKFxuICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICB7XG4gICAgICAgIGludGVncmF0aW9ucz8ubGVuZ3RoID4gMFxuICAgICAgICAgID8gKFxuICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBtaW5IZWlnaHQ9XCI3MHZoXCI+XG4gICAgICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgPEZsYXRMaXN0XG4gICAgICAgICAgICAgICAgICBkYXRhPXtpbnRlZ3JhdGlvbnN9XG4gICAgICAgICAgICAgICAgICBrZXlFeHRyYWN0b3I9e2l0ZW0gPT4gaXRlbS5pZH1cbiAgICAgICAgICAgICAgICAgIHJlbmRlckl0ZW09e3JlbmRlckl0ZW19XG4gICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAge2dvb2dsZUNhbGVuZGFyRW5hYmxlZFxuICAgICAgICAgICAgICAgID8gKFxuICAgICAgICAgICAgICAgICAgPEJveCBwdD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6J20nIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICA8UHJlc3NhYmxlIG9uUHJlc3M9e25hdmlnYXRlVG9Hb29nbGVDYWxlbmRhcnN9PlxuICAgICAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImJ1dHRvbkxpbmtcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgVmlldyBHb29nbGUgQ2FsZW5kYXJzXG4gICAgICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDwvUHJlc3NhYmxlPlxuICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKTogKFxuICAgICAgICAgICAgICAgICAgbnVsbFxuICAgICAgICAgICAgICAgICl9XG5cbiAgICAgICAgICAgICAgey8qIEdtYWlsIEludGVncmF0aW9uIFNlY3Rpb24gKi99XG4gICAgICAgICAgICAgIDxCb3ggZmxleD17MX0gcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAnbCcgfX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIHdpZHRoPVwiMTAwJVwiIG10PVwibFwiPlxuICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIiBzdHlsZT17eyBjb2xvcjogcGFsZXR0ZS5kYXJrR3JheSwgbWFyZ2luQm90dG9tOiAxMCB9fT5cbiAgICAgICAgICAgICAgICAgIEdtYWlsIEludGVncmF0aW9uXG4gICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICAgIHsvKlxuICAgICAgICAgICAgICAgICAgR21haWwgSW50ZWdyYXRpb25cbiAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAge2lzR21haWxTdGF0dXNMb2FkaW5nID8gKFxuICAgICAgICAgICAgICAgICAgPEFjdGl2aXR5SW5kaWNhdG9yIHNpemU9XCJzbWFsbFwiIGNvbG9yPXtwYWxldHRlLnByaW1hcnl9IHN0eWxlPXt7IG1hcmdpblRvcDogMTAgfX0gLz5cbiAgICAgICAgICAgICAgICApIDogaXNHbWFpbENvbm5lY3RlZCA/IChcbiAgICAgICAgICAgICAgICAgIDxCb3ggYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiYm9keVwiIG1iPVwic1wiPlxuICAgICAgICAgICAgICAgICAgICAgIHtnbWFpbFVzZXJFbWFpbCA/IGBDb25uZWN0ZWQgYXM6ICR7Z21haWxVc2VyRW1haWx9YCA6IFwiR21haWwgaXMgY29ubmVjdGVkLlwifVxuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxCdXR0b25cbiAgICAgICAgICAgICAgICAgICAgICBsYWJlbD1cIkRpc2Nvbm5lY3QgR21haWxcIlxuICAgICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e2hhbmRsZURpc2Nvbm5lY3RHbWFpbH1cbiAgICAgICAgICAgICAgICAgICAgICB2YXJpYW50PVwid2FybmluZ1wiIC8vIEFzc3VtaW5nIEJ1dHRvbiBjb21wb25lbnQgY2FuIHRha2UgYSB2YXJpYW50IGZvciBzdHlsaW5nXG4gICAgICAgICAgICAgICAgICAgICAgZGlzYWJsZWQ9e2xvYWRpbmd9IC8vIEdlbmVyYWwgbG9hZGluZyBzdGF0ZSBmb3IgYnV0dG9uIHByZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICkgOiAoXG4gICAgICAgICAgICAgICAgICA8UHJlc3NhYmxlIG9uUHJlc3M9e2hhbmRsZUNvbm5lY3RHbWFpbH0gZGlzYWJsZWQ9e2xvYWRpbmcgfHwgZ29vZ2xlSW50ZWdyYXRpb25Mb2FkaW5nfT5cbiAgICAgICAgICAgICAgICAgICAgPEltYWdlXG4gICAgICAgICAgICAgICAgICAgICAgICBzcmM9e2dvb2dsZUJ1dHRvbk5vcm1hbH0gLy8gVXNpbmcgR29vZ2xlIGJ1dHRvbiBmb3Igbm93XG4gICAgICAgICAgICAgICAgICAgICAgICBzdHlsZT17eyB3aWR0aDogMjQwLCBoZWlnaHQ6IDUwIH19XG4gICAgICAgICAgICAgICAgICAgICAgICBhbHQ9eydDb25uZWN0IEdtYWlsIGJ1dHRvbid9XG4gICAgICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgICA8L1ByZXNzYWJsZT5cbiAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgIHsvKiBTaG93IGdlbmVyYWwgbG9hZGluZyBpbmRpY2F0b3IgaWYgY29ubmVjdC9kaXNjb25uZWN0IGlzIGluIHByb2dyZXNzIGFuZCBub3QgY292ZXJlZCBieSBpc0dtYWlsU3RhdHVzTG9hZGluZyAqL31cbiAgICAgICAgICAgICAgICB7KGxvYWRpbmcgJiYgIWlzR21haWxTdGF0dXNMb2FkaW5nKSAmJiA8QWN0aXZpdHlJbmRpY2F0b3Igc3R5bGU9e3sgbWFyZ2luVG9wOiAxMCB9fSBjb2xvcj17cGFsZXR0ZS5wcmltYXJ5fSAvPn1cbiAgICAgICAgICAgICAgPC9Cb3g+XG5cbiAgICAgICAgICAgICAgey8qIE91dGxvb2sgSW50ZWdyYXRpb24gU2VjdGlvbiAqL31cbiAgICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJyB9fSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgd2lkdGg9XCIxMDAlXCIgbXQ9XCJsXCI+XG4gICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiIHN0eWxlPXt7IGNvbG9yOiBwYWxldHRlLmRhcmtHcmF5LCBtYXJnaW5Cb3R0b206IDEwIH19PlxuICAgICAgICAgICAgICAgICAgT3V0bG9vayBJbnRlZ3JhdGlvblxuICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICB7aXNPdXRsb29rU3RhdHVzTG9hZGluZyA/IChcbiAgICAgICAgICAgICAgICAgIDxBY3Rpdml0eUluZGljYXRvciBzaXplPVwic21hbGxcIiBjb2xvcj17cGFsZXR0ZS5wcmltYXJ5fSBzdHlsZT17eyBtYXJnaW5Ub3A6IDEwIH19IC8+XG4gICAgICAgICAgICAgICAgKSA6IGlzT3V0bG9va0Nvbm5lY3RlZCA/IChcbiAgICAgICAgICAgICAgICAgIDxCb3ggYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiYm9keVwiIG1iPVwic1wiPlxuICAgICAgICAgICAgICAgICAgICAgIHtvdXRsb29rVXNlckVtYWlsID8gYENvbm5lY3RlZCBhczogJHtvdXRsb29rVXNlckVtYWlsfWAgOiBcIk91dGxvb2sgaXMgY29ubmVjdGVkLlwifVxuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxCdXR0b25cbiAgICAgICAgICAgICAgICAgICAgICBsYWJlbD1cIkRpc2Nvbm5lY3QgT3V0bG9va1wiXG4gICAgICAgICAgICAgICAgICAgICAgb25DbGljaz17aGFuZGxlRGlzY29ubmVjdE91dGxvb2t9XG4gICAgICAgICAgICAgICAgICAgICAgdmFyaWFudD1cIndhcm5pbmdcIlxuICAgICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXtsb2FkaW5nfVxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKSA6IChcbiAgICAgICAgICAgICAgICAgIDxQcmVzc2FibGUgb25QcmVzcz17aGFuZGxlQ29ubmVjdE91dGxvb2t9IGRpc2FibGVkPXtsb2FkaW5nfT5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQ+Q29ubmVjdCBPdXRsb29rPC9UZXh0PlxuICAgICAgICAgICAgICAgICAgPC9QcmVzc2FibGU+XG4gICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICB7KGxvYWRpbmcgJiYgIWlzT3V0bG9va1N0YXR1c0xvYWRpbmcpICYmIDxBY3Rpdml0eUluZGljYXRvciBzdHlsZT17eyBtYXJnaW5Ub3A6IDEwIH19IGNvbG9yPXtwYWxldHRlLnByaW1hcnl9IC8+fVxuICAgICAgICAgICAgICA8L0JveD5cblxuICAgICAgICAgICAgICB7LyogR29vZ2xlIERyaXZlIEludGVncmF0aW9uIFNlY3Rpb24gLSBDb25jZXB0dWFsIFBsYWNlbWVudCAqL31cbiAgICAgICAgICAgICAgey8qXG4gICAgICAgICAgICAgICAgLy8gMS4gSW1wb3J0IHRoZSBHRHJpdmVNYW5hZ2VyIGNvbXBvbmVudCBhdCB0aGUgdG9wIG9mIHRoZSBmaWxlOlxuICAgICAgICAgICAgICAgIC8vIGltcG9ydCBHRHJpdmVNYW5hZ2VyIGZyb20gJy4uLy4uL2NvbXBvbmVudHMvU2V0dGluZ3MvR0RyaXZlTWFuYWdlcic7XG4gICAgICAgICAgICAgICovfVxuICAgICAgICAgICAgICA8Qm94IGZsZXg9ezF9IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnIH19IGFsaWduSXRlbXM9XCJjZW50ZXJcIiB3aWR0aD1cIjEwMCVcIiBtdD1cImxcIiBtYj1cImxcIiBzdHlsZT17e2JvcmRlclRvcFdpZHRoOiAxLCBib3JkZXJUb3BDb2xvcjogcGFsZXR0ZS5saWdodEdyYXksIHBhZGRpbmdUb3A6IDIwfX0+XG4gICAgICAgICAgICAgICAgey8qXG4gICAgICAgICAgICAgICAgICAvLyAyLiBSZW5kZXIgdGhlIEdEcml2ZU1hbmFnZXIgY29tcG9uZW50IGhlcmU6XG4gICAgICAgICAgICAgICAgICAvLyA8R0RyaXZlTWFuYWdlciAvPlxuICAgICAgICAgICAgICAgICAgLy8gRW5zdXJlIEdEcml2ZU1hbmFnZXIgcmVjZWl2ZXMgYW55IG5lY2Vzc2FyeSBwcm9wcywgbGlrZSB1c2VySWQgaWYgbm90IGhhbmRsZWQgYnkgYSBnbG9iYWwgY29udGV4dC5cbiAgICAgICAgICAgICAgICAgIC8vIFRoZSBHRHJpdmVNYW5hZ2VyIGNvbXBvbmVudCBpdHNlbGYgaGFuZGxlcyBpdHMgaW50ZXJuYWwgc3RhdGUgYW5kIEFQSSBjYWxscyBmb3IgR0RyaXZlLlxuICAgICAgICAgICAgICAgICovfVxuICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIiBzdHlsZT17eyBjb2xvcjogcGFsZXR0ZS5kYXJrR3JheSwgbWFyZ2luQm90dG9tOiAxMCB9fT5cbiAgICAgICAgICAgICAgICAgIEdvb2dsZSBEcml2ZSBJbnRlZ3JhdGlvbiAoUGxhY2Vob2xkZXIpXG4gICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJib2R5XCIgc3R5bGU9e3t0ZXh0QWxpZ246ICdjZW50ZXInLCBjb2xvcjogcGFsZXR0ZS5tZWRpdW1HcmF5fX0+XG4gICAgICAgICAgICAgICAgICBNYW5hZ2VtZW50IFVJIGZvciBHb29nbGUgRHJpdmUgY29ubmVjdGlvbiwgZmlsZSBsaXN0aW5nLCBhbmQgaW5nZXN0aW9uIHdvdWxkIGJlIHJlbmRlcmVkIGhlcmUgdXNpbmcgdGhlIEdEcml2ZU1hbmFnZXIgY29tcG9uZW50LlxuICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgPC9Cb3g+XG5cbiAgICAgICAgICAgICAgey8qIEdpdEh1YiBJbnRlZ3JhdGlvbiBTZWN0aW9uICovfVxuICAgICAgICAgICAgICA8Qm94IGZsZXg9ezF9IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnIH19IGFsaWduSXRlbXM9XCJjZW50ZXJcIiB3aWR0aD1cIjEwMCVcIiBtdD1cImxcIiBtYj1cImxcIiBzdHlsZT17e2JvcmRlclRvcFdpZHRoOiAxLCBib3JkZXJUb3BDb2xvcjogcGFsZXR0ZS5saWdodEdyYXksIHBhZGRpbmdUb3A6IDIwfX0+XG4gICAgICAgICAgICAgICAgPEdpdGh1Yk1hbmFnZXIgLz5cbiAgICAgICAgICAgICAgPC9Cb3g+XG5cbiAgICAgICAgICAgICAgey8qIFNob3BpZnkgSW50ZWdyYXRpb24gU2VjdGlvbiAqL31cbiAgICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJyB9fSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgd2lkdGg9XCIxMDAlXCIgbXQ9XCJsXCIgc3R5bGU9e3tib3JkZXJUb3BXaWR0aDogMSwgYm9yZGVyVG9wQ29sb3I6IHBhbGV0dGUubGlnaHRHcmF5LCBwYWRkaW5nVG9wOiAyMH19PlxuICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJvcHRpb25IZWFkZXJcIiBzdHlsZT17eyBjb2xvcjogcGFsZXR0ZS5kYXJrR3JheSwgbWFyZ2luQm90dG9tOiAxMCB9fT5cbiAgICAgICAgICAgICAgICAgIFNob3BpZnkgSW50ZWdyYXRpb25cbiAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAge2lzU2hvcGlmeVN0YXR1c0xvYWRpbmcgPyAoXG4gICAgICAgICAgICAgICAgICA8QWN0aXZpdHlJbmRpY2F0b3Igc2l6ZT1cInNtYWxsXCIgY29sb3I9e3BhbGV0dGUucHJpbWFyeX0gc3R5bGU9e3sgbWFyZ2luVG9wOiAxMCB9fSAvPlxuICAgICAgICAgICAgICAgICkgOiBpc1Nob3BpZnlDb25uZWN0ZWQgPyAoXG4gICAgICAgICAgICAgICAgICA8Qm94IGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImJvZHlcIiBtYj1cInNcIj5cbiAgICAgICAgICAgICAgICAgICAgICB7c2hvcGlmeVNob3BVcmwgPyBgQ29ubmVjdGVkIHRvOiAke3Nob3BpZnlTaG9wVXJsfWAgOiBcIlNob3BpZnkgaXMgY29ubmVjdGVkLlwifVxuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgIDxCdXR0b25cbiAgICAgICAgICAgICAgICAgICAgICBsYWJlbD1cIkRpc2Nvbm5lY3QgU2hvcGlmeVwiXG4gICAgICAgICAgICAgICAgICAgICAgb25DbGljaz17aGFuZGxlRGlzY29ubmVjdFNob3BpZnl9XG4gICAgICAgICAgICAgICAgICAgICAgdmFyaWFudD1cIndhcm5pbmdcIlxuICAgICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXtsb2FkaW5nfVxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKSA6IChcbiAgICAgICAgICAgICAgICAgIDxCb3ggYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICA8VGV4dEZpZWxkXG4gICAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9eyhlOiB7IHRhcmdldDogeyB2YWx1ZTogc3RyaW5nIH0gfSkgPT4gc2V0U2hvcGlmeVNob3BOYW1lKGUudGFyZ2V0LnZhbHVlKX1cbiAgICAgICAgICAgICAgICAgICAgICB2YWx1ZT17c2hvcGlmeVNob3BOYW1lfVxuICAgICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwieW91ci1zdG9yZS1uYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgICBsYWJlbD1cIlNob3BpZnkgU2hvcCBOYW1lXCJcbiAgICAgICAgICAgICAgICAgICAgICBzdHlsZT17eyB3aWR0aDogJzgwJScsIG1hcmdpbkJvdHRvbTogMTAgfX1cbiAgICAgICAgICAgICAgICAgICAgICBoaW50PVwiRW50ZXIgeW91ciBzaG9wIG5hbWUgKGUuZy4sICd5b3VyLXN0b3JlLW5hbWUnIGZyb20gJ3lvdXItc3RvcmUtbmFtZS5teXNob3BpZnkuY29tJylcIlxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICA8QnV0dG9uXG4gICAgICAgICAgICAgICAgICAgICAgbGFiZWw9XCJDb25uZWN0IFNob3BpZnlcIlxuICAgICAgICAgICAgICAgICAgICAgIG9uQ2xpY2s9e2hhbmRsZUNvbm5lY3RTaG9waWZ5fVxuICAgICAgICAgICAgICAgICAgICAgIGRpc2FibGVkPXtsb2FkaW5nfVxuICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICB7KGxvYWRpbmcgJiYgIWlzU2hvcGlmeVN0YXR1c0xvYWRpbmcpICYmIDxBY3Rpdml0eUluZGljYXRvciBzdHlsZT17eyBtYXJnaW5Ub3A6IDEwIH19IGNvbG9yPXtwYWxldHRlLnByaW1hcnl9IC8+fVxuICAgICAgICAgICAgICA8L0JveD5cblxuXG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgKSA6IChcbiAgICAgICAgICA8Qm94IGZsZXg9ezF9IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImhlYWRlclwiIHN0eWxlPXt7IGNvbG9yOiBwYWxldHRlLmRhcmtHcmF5IH19PlxuICAgICAgICAgICAgICBTdGlsbCBsb2FkaW5nXG4gICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICAgIH1cbiAgICAgIDxCb3g+XG4gICAgICAgIDxPdmVybGF5IG92ZXJsYXlTdHlsZT17eyBiYWNrZ3JvdW5kQ29sb3I6IHBhbGV0dGUud2hpdGUsIGp1c3RpZnlDb250ZW50OiAnY2VudGVyJywgYWxpZ25JdGVtczogJ2NlbnRlcicgfX0gaXNWaXNpYmxlPXtpc1dhcm5pbmd9IG9uQmFja2Ryb3BQcmVzcz17ZGlzYWJsZUdvb2dsZUNhbGVuZGFyQ2hlY2tCb3h9PlxuICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgc3R5bGU9e3sgd2lkdGg6ICc4MCUnLCBiYWNrZ3JvdW5kQ29sb3I6IHBhbGV0dGUud2hpdGV9fT5cbiAgICAgICAgICAgIDxCb3ggcD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiPlxuICAgICAgICAgICAgICAgIERpc2FibGluZyBHb29nbGUgQ2FsZW5kYXIgd2lsbCBkZWxldGUgYWxsIGdvb2dsZSByZWxhdGVkIGV2ZW50cyBmcm9tIHlvdXIgY2FsZW5kYXJcbiAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICA8Qm94IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgPEJ1dHRvbiBvbkNsaWNrPXtlbmFibGVHb29nbGVDYWxlbmRhckNoZWNrQm94fT5cbiAgICAgICAgICAgICAgICAgIE9rYXlcbiAgICAgICAgICAgICAgICA8L0J1dHRvbj4gIFxuICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgPEJ1dHRvbiBjYW5jZWwgb25DbGljaz17ZGlzYWJsZUdvb2dsZUNhbGVuZGFyQ2hlY2tCb3h9PlxuICAgICAgICAgICAgICAgIENhbmNlbFxuICAgICAgICAgICAgICA8L0J1dHRvbj4gIFxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIDwvT3ZlcmxheT5cbiAgICAgIDwvQm94PlxuICAgIDwvQm94PlxuICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IFVzZXJWaWV3Q2FsZW5kYXJBbmRDb250YWN0SW50ZWdyYXRpb25zXG4iXX0=