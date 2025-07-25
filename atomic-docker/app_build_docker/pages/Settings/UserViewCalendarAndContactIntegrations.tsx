import React, {
  useState,
  forwardRef,
  useImperativeHandle,
  useRef,
  useEffect,
} from 'react'
import {
  FlatList,
  Pressable,
  ActivityIndicator,
  Platform,
 } from 'react-native'
import Image from 'next/image'
import Switch1 from '@components/Switch'
import { useToast } from '@chakra-ui/react'
import { Overlay } from '@rneui/themed'
import UserCalendarList from '@pages/Settings/Google/UserCalendarList'

import { ApolloClient, NormalizedCacheObject, useQuery } from '@apollo/client'

import Box from '@components/common/Box'
import Text from '@components/common/Text'
import Button from '@components/Button'
import { palette } from '@lib/theme/theme'

import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType'
import {
  updateIntegration,
  deleteEventTriggers,
  deleteEventTriggerByResourceId,
 } from '@lib/Settings/calendar_integrationHelper';
import GithubManager from '@components/Settings/GithubManager';

import {
   googleCalendarName,
   googleResourceName,
   googleOAuthStartUrl,
} from '@lib/calendarLib/constants'

 import {
   googlePeopleName,
 } from '@lib/contactLib/constants'
 

 import {
   zoomOAuthStartUrl,
   zoomResourceName,
   zoomName,
 } from '@lib/zoom/constants'

import { getGoogleToken } from '@lib/calendarLib/googleCalendarHelper'
import { bulkRemoveCalendarsInDb, deleteEventsByCalendarId, getItemsToRemove } from '@lib/calendarLib/calendarDbHelper'

import listCalendarIntegrations from '@lib/apollo/gql/listCalendarIntegrations'
import _ from 'lodash'
import getCalendarIntegrationByResourceAndName from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName'

import googleButtonLightNormal from '@assets/images/google-signin-normal.png'
import googleButtonPressedLightNormal from '@assets/images/google-signin-pressed.png'

import { useAppContext } from '@lib/user-context'
import { useRouter } from 'next/router'


type checkBoxProps = {
  updateEnabledValue: (index: number, value: boolean, id: string) => Promise<any>,
  index: number,
  enabled: boolean,
  name: string,
  // dark: boolean,
  id: string,
}

type RenderItemType = {
  item: CalendarIntegrationType,
  index: number,
}

type Props = {
  sub: string,
  client: ApolloClient<NormalizedCacheObject>,

}

// const dark = Appearance.getColorScheme() === 'dark'
// const googleButtonPressed = dark ? googleButtonPressedDarkNormal : googleButtonPressedLightNormal
// const googleButtonNormal = dark ? googleButtonDarkNormal : googleButtonLightNormal
const googleButtonPressed = googleButtonPressedLightNormal
const googleButtonNormal = googleButtonLightNormal

import { gql } from '@apollo/client'; // Import gql

// Define the GraphQL mutation for generating Gmail Auth URL
const GENERATE_GMAIL_AUTH_URL_MUTATION = gql`
  mutation GenerateGmailAuthUrl {
    generateGmailAuthUrl {
      authorizationUrl
    }
  }
`;

const GENERATE_OUTLOOK_AUTH_URL_MUTATION = gql`
  mutation GenerateOutlookAuthUrl {
    generateOutlookAuthUrl {
      authUrl
    }
  }
`;

const GET_OUTLOOK_CONNECTION_STATUS_QUERY = gql`
  query GetOutlookConnectionStatus {
    getOutlookConnectionStatus {
      isConnected
      userEmail
    }
  }
`;

const DISCONNECT_OUTLOOK_ACCOUNT_MUTATION = gql`
  mutation DisconnectOutlookAccount {
    disconnectOutlookAccount {
      success
      message
    }
  }
`;

// GraphQL for Gmail Connection Status and Disconnect
const GET_GMAIL_CONNECTION_STATUS_QUERY = gql`
  query GetGmailConnectionStatus {
    getGmailConnectionStatus {
      isConnected
      userEmail
    }
  }
`;

const DISCONNECT_GMAIL_ACCOUNT_MUTATION = gql`
  mutation DisconnectGmailAccount {
    disconnectGmailAccount {
      success
      message
    }
  }
`;


import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
import Session from 'supertokens-node/recipe/session'

export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig())
  let session
  try {
    session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return []
      },
    })
  } catch (err: any) {
    if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } }
    } else if (err.type === Session.Error.UNAUTHORISED) {
      // this will force the frontend to try and refresh which will fail
      // clearing all cookies and redirecting the user to the login screen.
      return { props: { fromSupertokens: 'needs-refresh' } }
    }
    throw err
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: '/User/Login/UserLogin',
        permanent: false,
      },
    }
  }

  return {
    props: {
      sub: session.getUserId(),
    }
  }
}

// eslint-disable-next-line react/display-name
const IntegrationCheckBox = forwardRef((props: checkBoxProps, ref) => {
    const {
      enabled: oldEnabled,
      updateEnabledValue,
      index,
      name,
      // dark,
      id,
    } = props
    const [enabled, setEnabled] = useState<boolean>(oldEnabled)
    const [pressed, setPressed] = useState<boolean>(false)
  
    const updateEnabled = async (value: boolean) => {
      setEnabled(value)
      return updateEnabledValue(index, value, id)
    }
  
    const disableEnabled = async () => {
      setEnabled(false)
      return updateEnabledValue(index, false, id)
    }
  
    useImperativeHandle(ref, () => ({
        disableEnabled,
    }))

    const onPressIn = () => setPressed(true)
    const onPressOut = () => setPressed(false)

    const onPress = async () => updateEnabled(!enabled)
        

    if ((name === googleCalendarName) || (name === googlePeopleName)) {
        return (
            <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="stretch">
                <Box flex={1} flexDirection="row" justifyContent="space-between" alignItems="center">
                    <Box mr={{ phone: 's', tablet: 'm' }}>
                    <Text variant="optionHeader" style={{ color: palette.darkGray }}>
                        {name}
                    </Text>
                    </Box>
                    <Box ml={{ phone: 's', tablet: 'm' }}>
                        {enabled
                            ? <Text variant="optionHeader">On</Text>
                            : <Text variant="optionHeader">Off</Text>
                        }
                    </Box>
            
                </Box>
                <Box flex={1} justifyContent="center" alignItems="center" pt={{ phone: 'm', tablet: 's' }}>
                    {enabled
                        ? (
                            <Pressable onPress={onPress}>
                                <Text variant="buttonLink">
                                    Disable
                                </Text>
                            </Pressable>
                        ) : (
                            <Pressable onPressIn={onPressIn} onPressOut={onPressOut} onPress={onPress}>
                                <Image
                                    src={pressed ? googleButtonPressed : googleButtonNormal}
                                    style={{ width: 240, height: 50 }}
                                    alt={'google sign-in button'}
                                />
                            </Pressable>
                        )}
                </Box>
            </Box>
        )
    }
  
    return (
      <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} flexDirection="row" justifyContent="space-between" alignItems="center">
        <Box mr={{ phone: 's', tablet: 'm' }}>
          <Text variant="optionHeader" style={{ color: palette.darkGray }}>
            {name}
          </Text>
        </Box>
        <Box ml={{ phone: 's', tablet: 'm' }}>
          <Switch1
            onValueChange={updateEnabled}
            checked={enabled}
          />
        </Box>
  
      </Box>
    )
})

function UserViewCalendarAndContactIntegrations() {
    const [loading, setLoading] = useState<boolean>(false)
    const [isWarning, setIsWarning] = useState<boolean>(false)
    const [selectedIndex, setSelectedIndex] = useState<number>(-1)
    const [selectedId, setSelectedId] = useState<string>()
    const [selectedValue, setSelectedValue] = useState<boolean>(false)
    // const [googleCalendarEnabled, setGoogleCalendarEnabled] = useState<boolean>(false)
    const [isGoogleCalendarList, setIsGoogleCalendarList] = useState<boolean>(false)
    const [googleToken, setGoogleToken] = useState<string>()

    // State for Gmail Integration
    const [isGmailConnected, setIsGmailConnected] = useState<boolean>(false);
    const [gmailUserEmail, setGmailUserEmail] = useState<string | null>(null);
    const [isGmailStatusLoading, setIsGmailStatusLoading] = useState<boolean>(true);

    // State for Outlook Integration
    const [isOutlookConnected, setIsOutlookConnected] = useState<boolean>(false);
    const [outlookUserEmail, setOutlookUserEmail] = useState<string | null>(null);
    const [isOutlookStatusLoading, setIsOutlookStatusLoading] = useState<boolean>(true);


    const googleCalendarElement = useRef<any>()
    const toast = useToast()
    // const dark = useColorScheme() === 'dark'
    
    const router = useRouter()
    const { sub, client,  } = useAppContext()
    const userId = sub

    const { loading: googleIntegrationLoading, error: googleIntegrationError, data: googleIntegrationData, refetch: googleIntRefetch } = useQuery<{ Calendar_Integration: CalendarIntegrationType[] }>(getCalendarIntegrationByResourceAndName, {
        variables: {
            name: googleCalendarName,
            resource: googleResourceName,
            userId: userId,
        }
    })

    const { loading: integrationLoading, error: integrationError, data: integrationData, refetch: calIntRefetch } = useQuery<{ Calendar_Integration: CalendarIntegrationType[] }>(listCalendarIntegrations, {
        variables: {
            userId: userId,
        }
    })
    
    const googleCalendarEnabled = googleIntegrationData?.Calendar_Integration?.[0]?.enabled
    const integrations = integrationData?.Calendar_Integration
    // const [integrations, setIntegrations] = useState<CalendarIntegrationType[]>(oldIntegrations)

    console.log(integrations, ' integrations')

    // Gmail Connection Handler
    const handleConnectGmail = async () => {
      setLoading(true); // Reuse existing loading state
      try {
        const response = await client.mutate({
          mutation: GENERATE_GMAIL_AUTH_URL_MUTATION,
        });

        if (response.data?.generateGmailAuthUrl?.authorizationUrl) {
          window.location.href = response.data.generateGmailAuthUrl.authorizationUrl;
        } else {
          console.error('Failed to get Gmail authorization URL from mutation response:', response);
          throw new Error('Failed to get Gmail authorization URL.');
        }
      } catch (error) {
        console.error('Error initiating Gmail connection:', error);
        toast({
          title: 'Error Connecting Gmail',
          description: (error as Error).message || 'Could not initiate Gmail connection. Please try again.',
          status: 'error',
          duration: 9000,
          isClosable: true,
        });
        setLoading(false);
      }
      // setLoading(false) might not be reached if window.location.href happens
    };
  
  // just in case
 
  useEffect(() => {
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
      } else {
        throw new Error(response.data?.disconnectGmailAccount?.message || 'Failed to disconnect Gmail account.');
      }
    } catch (error) {
      console.error('Error disconnecting Gmail:', error);
      toast({
        title: 'Error Disconnecting Gmail',
        description: (error as Error).message || 'Could not disconnect Gmail. Please try again.',
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
    } finally {
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
      } else {
        throw new Error('Failed to get Outlook authorization URL.');
      }
    } catch (error) {
      console.error('Error initiating Outlook connection:', error);
      toast({
        title: 'Error Connecting Outlook',
        description: (error as Error).message || 'Could not initiate Outlook connection. Please try again.',
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
      setLoading(false);
    }
  };

  useEffect(() => {
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
      } else {
        throw new Error(response.data?.disconnectOutlookAccount?.message || 'Failed to disconnect Outlook account.');
      }
    } catch (error) {
      console.error('Error disconnecting Outlook:', error);
      toast({
        title: 'Error Disconnecting Outlook',
        description: (error as Error).message || 'Could not disconnect Outlook. Please try again.',
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
        if (googleCalendarEnabled) {
            toast({
                status: 'info',
                title: 'Enable a calendar from Google',
                description: 'Please click on View Google Calendars and enable at least 1 calendar to use Atomic',
                duration: 9000,
                isClosable: true,
            })
        }
    }, [googleCalendarEnabled, toast])

  const disableGoogleCalendarCheckBox = () => {
    setSelectedIndex(-1)
    setSelectedId('')
    setSelectedValue(false)
    setIsWarning(false)
    googleCalendarElement.current.disableEnabled()
  }

  const enableGoogleCalendarCheckBox = async () => {
    try {
      setIsWarning(false)
      // const newIntegrations = integrations
      //   .slice(0, selectedIndex)
      //   .concat([{ ...(integrations?.[selectedIndex]), enabled: selectedValue }])
      //   .concat(integrations.slice(selectedIndex + 1))

      // setIntegrations(newIntegrations)

      await submitIntegration(
        selectedIndex,
        selectedValue,
        selectedId,
      )

      await googleIntRefetch()
      await calIntRefetch()

      setSelectedIndex(-1)
      setSelectedId('')
      setSelectedValue(false)
    } catch (e) {
      setIsWarning(false)
      console.log(e, ' this is error for enable google calendar checkbox')
      toast({
        status: 'error',
        title: 'Error',
        description: 'Something went wrong',
        duration: 9000,
        isClosable: true,
      })
    }
  }

  const updateEnabledValue = async (index: number, value: boolean, id: string) => {
    const selectedIntegration = integrations[index]
    if (
      (selectedIntegration.name === googleCalendarName)
      && (value === false)
    ) {
      setSelectedIndex(index)
      setSelectedId(id)
      setSelectedValue(value)
      setIsWarning(true)
    } else {
      // const newIntegrations = integrations
      // .slice(0, index)
      // .concat([{ ...(integrations?.[index]), enabled: value }])
      // .concat(integrations.slice(index + 1))

      // setIntegrations(newIntegrations)

      await submitIntegration(
        index,
        value,
        id,
      )

      await googleIntRefetch()
      await calIntRefetch()
    }
    
  }

  const disableGoogleCalendarSync = async (
    integrationId: string
  ) => {
    try {
      await updateIntegration(
        client,
        integrationId,
        false,
        null,
        undefined,
        null,
      )
      
      await deleteEventTriggers(userId, googleResourceName, googleCalendarName)
      
      const itemsToRemove = await getItemsToRemove(client, userId, googleResourceName)
      
      await bulkRemoveCalendarsInDb(client, itemsToRemove.map(i => (i?.id)))

      // bulk remove events from db
      const eventsToRemovePromise = []

      for (const item of itemsToRemove) {
        if (item?.id) {
          eventsToRemovePromise.push(
            deleteEventsByCalendarId(client, item.id)
          )
        }
      }

      await Promise.all(eventsToRemovePromise)

      await googleIntRefetch()
      await calIntRefetch()
    } catch (e) {
      console.log(e, ' this is e for disable google calendarsync')
      await calIntRefetch()
      await googleIntRefetch()
    }
  }

  const disableZoomAuth = async (
    integrationId: string,
  ): Promise<void> => {
      try {
          await updateIntegration(
              client,
              integrationId,
              false,
              null,
              null,
              null,
              undefined,
              undefined,
              null,
              null,
          )
      } catch (e) {
          console.log(e, ' unable to disable zoom auth')
      }
  }


  const disableGoogleContactSync = async (
    integrationId: string,
  ) => {
    try {
      await updateIntegration(
        client,
        integrationId,
        false,
        null,
        undefined,
        null,
        undefined,
        undefined,
        null,
        null,
      )
      // delete event triggers
      await deleteEventTriggerByResourceId(integrationId)

      await googleIntRefetch()
    } catch (e) {
      console.log(e, ' error in disableGoogleContactSync')
    }
  }

  const submitIntegration = async (index: number, newEnabled: boolean, id: string) => {
    try {
      if (newEnabled === false) {
        // delete triggers
        if (integrations?.[index]?.name === googlePeopleName) {

          return disableGoogleContactSync(integrations?.[index]?.id)
        } else if (integrations?.[index]?.name === googleCalendarName) {

          return disableGoogleCalendarSync(integrations?.[index]?.id)
        } else if (integrations?.[index]?.resource === zoomResourceName) {
               
          return disableZoomAuth(integrations?.[index]?.id)
      }

        return updateIntegration(
          client,
          id,
          newEnabled,
          undefined,
          undefined,
          undefined,
          false,
          undefined,
          undefined,
          undefined,
          integrations?.[index]?.resource === googleResourceName ? 'atomic-web' : 'web',
        )
      }

    } catch(e) {
      console.log(e, ' unable to submit integrations')
      setLoading(false)
      toast({
        status: 'error',
        title: 'Unable to submit integration',
        description: 'Please try again',
        duration: 9000,
        isClosable: true,
      })
    }
  }

  const navigateToGoogleCalendars = async () => {
    try {
      const newAccessToken = await getGoogleToken(client, userId)
      setGoogleToken(newAccessToken)
      // return router.push({ pathname: '/Settings/Google/UserCalendarList', query: { token: newAccessToken }})
      setIsGoogleCalendarList(true)
    } catch (e: any) {
      console.log(e, ' unable to navigate to google calendars')

    }
  }

  const renderItem = ({ item, index }: RenderItemType) => {
    if ((item?.resource === zoomResourceName) && !item?.enabled) {
      return (
        <Box flex={1} mt={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center">
          <Pressable onPress={() => window.location.href = zoomOAuthStartUrl}>
            <Box flex={1} flexDirection="row" justifyContent="space-between" alignItems="center">
              <Box mr={{ phone: 's', tablet: 'm' }}>
                <Text variant="optionHeader" style={{ color: palette.darkGray }}>
                  {item?.name}
                </Text>
              </Box>
              <Box ml={{ phone: 's', tablet: 'm' }}>
                <Text variant="optionHeader">Off</Text>
              </Box>
            </Box>
            <span className="btn btn-link no-underline hover:no-underline">Enable Zoom</span>
          </Pressable>
        </Box>
      )
    }

    if ((item?.resource === zoomResourceName) && item?.enabled) {
        return (
            <Box flex={1}>

                    <IntegrationCheckBox
                        updateEnabledValue={updateEnabledValue}
                        index={index}
                        enabled={item?.enabled}
                        name={item?.name}
                        
                        id={item?.id}
                        
                    />
                
            </Box>
        )
    }

    if ((item?.resource === googleResourceName) && !item?.enabled) {
        return (
            <Box flex={1}>
                <a target="_blank" href={googleOAuthStartUrl} rel="noopener noreferrer">
                    <IntegrationCheckBox
                        updateEnabledValue={updateEnabledValue}
                        index={index}
                        enabled={item?.enabled}
                        name={item?.name}
                        
                        id={item?.id}
                        ref={googleCalendarElement}
                    />
                </a>
            </Box>
        )
    }

    if ((item?.resource === googleResourceName) && item?.enabled) {
        return (
            <Box flex={1}>

                <IntegrationCheckBox
                    updateEnabledValue={updateEnabledValue}
                    index={index}
                    enabled={item?.enabled}
                    name={item?.name}
                    
                    id={item?.id}
                    ref={googleCalendarElement}
                />
                
            </Box>
        )
    }

    return (
      <Box flex={1}>
        <IntegrationCheckBox
          updateEnabledValue={updateEnabledValue}
          index={index}
          enabled={item?.enabled}
          name={item?.name}
          
          id={item?.id}
          />
      </Box>
    )
  }

  if (loading || integrationLoading || googleIntegrationLoading) {
    return (
      <Box backgroundColor="primaryCardBackground" flex={1} justifyContent="center" alignItems="center" style={{ width: '100%'}} minHeight="80vh">
          <ActivityIndicator size="large" color={palette.white} />
      </Box>
    )
  }

  if (isGoogleCalendarList) {
    return (
      <UserCalendarList
        token={googleToken}
        setIsGoogleCalendarList={setIsGoogleCalendarList}
      />
    )
  }


  return (
    <Box justifyContent="center" alignItems="center">
      {
        integrations?.length > 0
          ? (
            <Box justifyContent="center" alignItems="center" minHeight="70vh">
              <Box justifyContent="center" alignItems="center">
                <FlatList
                  data={integrations}
                  keyExtractor={item => item.id}
                  renderItem={renderItem}
                  />
              </Box>
              {googleCalendarEnabled
                ? (
                  <Box pt={{ phone: 's', tablet:'m' }} justifyContent="center" alignItems="center">
                    <Pressable onPress={navigateToGoogleCalendars}>
                        <Text variant="buttonLink">
                          View Google Calendars
                        </Text>
                    </Pressable>
                  </Box>
                ): (
                  null
                )}

              {/* Gmail Integration Section */}
              <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} alignItems="center" width="100%" mt="l">
                <Text variant="optionHeader" style={{ color: palette.darkGray, marginBottom: 10 }}>
                  Gmail Integration
                </Text>
                {/*
                  Gmail Integration
                </Text>
                {isGmailStatusLoading ? (
                  <ActivityIndicator size="small" color={palette.primary} style={{ marginTop: 10 }} />
                ) : isGmailConnected ? (
                  <Box alignItems="center">
                    <Text variant="body" mb="s">
                      {gmailUserEmail ? `Connected as: ${gmailUserEmail}` : "Gmail is connected."}
                    </Text>
                    <Button
                      label="Disconnect Gmail"
                      onClick={handleDisconnectGmail}
                      variant="warning" // Assuming Button component can take a variant for styling
                      disabled={loading} // General loading state for button presses
                    />
                  </Box>
                ) : (
                  <Pressable onPress={handleConnectGmail} disabled={loading || googleIntegrationLoading}>
                    <Image
                        src={googleButtonNormal} // Using Google button for now
                        style={{ width: 240, height: 50 }}
                        alt={'Connect Gmail button'}
                    />
                  </Pressable>
                )}
                {/* Show general loading indicator if connect/disconnect is in progress and not covered by isGmailStatusLoading */}
                {(loading && !isGmailStatusLoading) && <ActivityIndicator style={{ marginTop: 10 }} color={palette.primary} />}
              </Box>

              {/* Outlook Integration Section */}
              <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} alignItems="center" width="100%" mt="l">
                <Text variant="optionHeader" style={{ color: palette.darkGray, marginBottom: 10 }}>
                  Outlook Integration
                </Text>
                {isOutlookStatusLoading ? (
                  <ActivityIndicator size="small" color={palette.primary} style={{ marginTop: 10 }} />
                ) : isOutlookConnected ? (
                  <Box alignItems="center">
                    <Text variant="body" mb="s">
                      {outlookUserEmail ? `Connected as: ${outlookUserEmail}` : "Outlook is connected."}
                    </Text>
                    <Button
                      label="Disconnect Outlook"
                      onClick={handleDisconnectOutlook}
                      variant="warning"
                      disabled={loading}
                    />
                  </Box>
                ) : (
                  <Pressable onPress={handleConnectOutlook} disabled={loading}>
                    <Text>Connect Outlook</Text>
                  </Pressable>
                )}
                {(loading && !isOutlookStatusLoading) && <ActivityIndicator style={{ marginTop: 10 }} color={palette.primary} />}
              </Box>

              {/* Google Drive Integration Section - Conceptual Placement */}
              {/*
                // 1. Import the GDriveManager component at the top of the file:
                // import GDriveManager from '../../components/Settings/GDriveManager';
              */}
              <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} alignItems="center" width="100%" mt="l" mb="l" style={{borderTopWidth: 1, borderTopColor: palette.lightGray, paddingTop: 20}}>
                {/*
                  // 2. Render the GDriveManager component here:
                  // <GDriveManager />
                  // Ensure GDriveManager receives any necessary props, like userId if not handled by a global context.
                  // The GDriveManager component itself handles its internal state and API calls for GDrive.
                */}
                <Text variant="optionHeader" style={{ color: palette.darkGray, marginBottom: 10 }}>
                  Google Drive Integration (Placeholder)
                </Text>
                <Text variant="body" style={{textAlign: 'center', color: palette.mediumGray}}>
                  Management UI for Google Drive connection, file listing, and ingestion would be rendered here using the GDriveManager component.
                </Text>
              </Box>

              {/* GitHub Integration Section */}
              <Box flex={1} pt={{ phone: 'm', tablet: 'l' }} alignItems="center" width="100%" mt="l" mb="l" style={{borderTopWidth: 1, borderTopColor: palette.lightGray, paddingTop: 20}}>
                <GithubManager />
              </Box>


            </Box>
        ) : (
          <Box flex={1} justifyContent="center" alignItems="center">
            <Text variant="header" style={{ color: palette.darkGray }}>
              Still loading
            </Text>
          </Box>
        )
      }
      <Box>
        <Overlay overlayStyle={{ backgroundColor: palette.white, justifyContent: 'center', alignItems: 'center' }} isVisible={isWarning} onBackdropPress={disableGoogleCalendarCheckBox}>
          <Box justifyContent="center" alignItems="center" style={{ width: '80%', backgroundColor: palette.white}}>
            <Box p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center">
              <Text variant="optionHeader">
                Disabling Google Calendar will delete all google related events from your calendar
              </Text>
            </Box>
            <Box justifyContent="center" alignItems="center">
              <Box p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center">
                <Button onClick={enableGoogleCalendarCheckBox}>
                  Okay
                </Button>  
              </Box>
              <Button cancel onClick={disableGoogleCalendarCheckBox}>
                Cancel
              </Button>  
            </Box>
          </Box>
        </Overlay>
      </Box>
    </Box>
  )
}

export default UserViewCalendarAndContactIntegrations
