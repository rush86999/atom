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
 } from '@lib/Settings/calendar_integrationHelper'

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
                    <a target="_blank" href={zoomOAuthStartUrl} rel="noopener noreferrer">
                      <Box flex={1} flexDirection="row" justifyContent="space-between" alignItems="center">
                          <Box mr={{ phone: 's', tablet: 'm' }}>
                            <Text variant="optionHeader" style={{ color: palette.darkGray }}>
                                {item?.name}
                            </Text>
                          </Box>
                          <Box ml={{ phone: 's', tablet: 'm' }}>
                              {item?.enabled
                                  ? <Text variant="optionHeader">On</Text>
                                  : <Text variant="optionHeader">Off</Text>
                              }
                          </Box>
                    
                        </Box>
                        <span className="btn btn-link no-underline hover:no-underline">Enable Zoom</span>
                    </a>
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
                  TODO: Add logic to check if Gmail is already connected.
                  If connected, show "Gmail Connected" and a "Disconnect" button.
                  For now, always showing the "Connect" button.
                */}
                <Pressable onPress={handleConnectGmail} disabled={loading || googleIntegrationLoading}>
                  <Image
                      src={googleButtonNormal} // Using Google button for now, replace with specific Gmail button if available
                      style={{ width: 240, height: 50 }}
                      alt={'Connect Gmail button'}
                  />
                </Pressable>
                {(loading || googleIntegrationLoading) && <ActivityIndicator style={{ marginTop: 10 }} color={palette.primary} />}
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
