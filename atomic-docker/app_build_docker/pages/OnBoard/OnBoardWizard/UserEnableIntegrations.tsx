import React, {
    useState,
    forwardRef,
    useImperativeHandle,
    useRef,
    useEffect,
    Dispatch,
    SetStateAction,
  } from 'react'

import {
    FlatList,
    Pressable,
    ActivityIndicator,
} from 'react-native'
import Image from 'next/image'
import Switch1 from '@components/Switch'
import { useToast } from '@chakra-ui/react'
import { Overlay } from '@rneui/themed'

import Box from '@components/common/Box'
import Text from '@components/common/Text'
import Button from '@components/Button'
import { palette } from '@lib/theme/theme'

import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType'
import { CalendarType } from '@lib/dataTypes/CalendarType'
import {
    updateIntegration,
    deleteEventTriggers,
    deleteEventTriggerByResourceId,
    triggerGoogleCalendarSync,
    listGoogleCalendars,
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
    zoomResourceName
} from '@lib/zoom/constants'


import { 
    bulkRemoveCalendarsInDb, 
    deleteEventsByCalendarId, 
    getItemsToRemove,
    deleteGoogleCalendarInDb, 
    upsertGoogleCalendarInDb,
 } from '@lib/calendarLib/calendarDbHelper'

import { CalendarListItemResponseType } from '@lib/calendarLib/types'
import { enabledCalendarType } from '@lib/Settings/types'
import { ApolloClient, NormalizedCacheObject, useQuery } from '@apollo/client'
import getCalendarWithResource from '@lib/apollo/gql/getCalendarWithResource';
import getCalendarIntegrationByResourceAndName from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName'
import listCalendarIntegrations from '@lib/apollo/gql/listCalendarIntegrations'
import { listEventsForCalendar } from '../../../lib/OnBoard/OnBoardHelper2';
import { deleteAttendeesForEvents } from '@lib/Calendar/Attendee/AttendeeHelper'
import { deleteConferencesWithIds } from '@lib/Calendar/Conference/ConferenceHelper'
import { deleteRemindersForEvents } from '@lib/Calendar/Reminder/ReminderHelper'
import { getGoogleToken } from '@lib/calendarLib/googleCalendarHelper'

import { useRouter } from 'next/router'
import googleButtonLightNormal from '@assets/images/google-signin-normal.png'
import googleButtonPressedLightNormal from '@assets/images/google-signin-pressed.png'
/**
 * ['https://www.googleapis.com/auth/calendar.readonly',
      'https://www.googleapis.com/auth/calendar.events',
      'https://www.googleapis.com/auth/contacts.readonly'], // what API you want to access on behalf of the user, default is email and profile
  webClientId: googleClientIdWeb,
  <a target="_blank" href="https://twitter.com/" rel="noopener noreferrer">
 */

// GoogleSignin.configure({
//   scopes: ['https://www.googleapis.com/auth/calendar.readonly',
//       'https://www.googleapis.com/auth/calendar.events',
//       'https://www.googleapis.com/auth/contacts.readonly'], // what API you want to access on behalf of the user, default is email and profile
//   webClientId: googleClientIdWeb, // client ID of type WEB for your server (needed to verify user ID and offline access)
//   offlineAccess: true, // if you want to access Google API on behalf of the user FROM YOUR SERVER
//   forceCodeForRefreshToken: true, // [Android] related to `serverAuthCode`, read the docs link below *.
// })

// dayjs.extend(utc)

type CheckBoxPropsType = {
    updateEnabledValue: (index: number, value: boolean, id: string) => Promise<any>,
    index: number,
    enabled: boolean,
    name: string,
    // dark: boolean,
    id: string,
}

type checkBoxProps2 = {
    updateEnabledValue: (index: number, value: boolean, id: string) => Promise<any>,
    index: number,
    enabled: boolean,
    name: string,
    // dark: boolean,
    id: string,
    calendars: CalendarType[],
}

type RenderItemType = {
    item: enabledCalendarType,
    index: number,
}
type RenderItemType2 = {
    item: CalendarIntegrationType,
    index: number,
}

type googleRenderItem = {
    item: enabledCalendarType,
    index: number,
  }

type googleCheckBoxProps = {
    updateEnabledValue: (index: number, value: boolean, id: string) => Promise<void | void[]>,
    index: number,
    enabled: boolean,
    name: string,
    // dark: boolean,
    id: string,
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
const IntegrationCheckBox = forwardRef((props: CheckBoxPropsType, ref) => {
    const {
      enabled: oldEnabled,
      updateEnabledValue,
      index,
      name,
    //   dark,
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
                <Box flex={1} pt={{ phone: 'm', tablet: 's' }}>
                    {enabled
                        ? (
                            <Pressable onPress={onPress}>
                                <Text textAlign="center" variant="buttonLink">
                                    Disable
                                </Text>
                            </Pressable>
                        ) : (
                            <Pressable onPressIn={onPressIn} onPressOut={onPressOut} onPress={onPress}>
                                <Image
                                    src={pressed ? googleButtonPressed : googleButtonNormal}
                                    style={{ width: 240, height: 50 }}
                                    alt={'google button'}
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

function CalendarCheckBox(props: checkBoxProps2) {
    const {
      enabled: oldEnabled,
      updateEnabledValue,
    index,
    name,
    // dark,
    id,
    calendars,
    } = props
    const [enabled, setEnabled] = useState<boolean>(oldEnabled)

    useEffect(() => {
        (async () => {
            try {

                const index = calendars.findIndex(i => (i?.id === id))
                if (index !== -1) {
                    setEnabled(true)
                }
            } catch (e) {
                console.log(e, ' error in calendar checkbox')
            }
        })()
    }, [calendars, calendars.length, id])
  
    const updateEnabled = async (value: boolean) => {
      setEnabled(value)
      return updateEnabledValue(index, value, id)
    }
  
    return (
      <Box mb={{ phone: 's', tablet: 'm' }} flex={1} style={{ width: '90%'}} flexDirection="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Text variant="optionHeader" style={{ color: palette.darkGray }}>
            {name}
          </Text>
        </Box>
        <Box style={{ width: '30%'}}>
          <Switch1
            onValueChange={updateEnabled}
            checked={enabled}
          />
        </Box>
  
      </Box>
    )
}

type GoogleProps = {
    sub: string, 
    token: string,
    setParentIsGoogleCalendarList: Dispatch<SetStateAction<boolean>>,
    client: ApolloClient<NormalizedCacheObject>,

}

function UserViewGoogleCalendarList(props: GoogleProps) {
    const { sub } = props
    const client = props?.client
    // const calendar_integrationCollection = useRxCollection<calendar_integrationCollection>('calendar_integration')
    
    const [calendarList, setCalendarList] = useState<CalendarListItemResponseType[]>([])
    const [loading, setLoading] = useState<boolean>(false)
    // const [integration, setIntegration] = useState<CalendarIntegrationType>()
    // const [calendars, setCalendars] = useState<CalendarType[]>([])
    const [enabledCalendars, setEnabledCalendars] = useState<enabledCalendarType[]>([])
    const [enableAllCalendars, setEnableAllCalendars] = useState<boolean>(false)
    const [disableLoading, setDisableLoading] = useState<boolean>(false)

    const token = props?.token

    const toast = useToast()

    const { loading: existingCalendarLoading, error: existingCalendarError, data } = useQuery<{ Calendar: CalendarType[] }>(getCalendarWithResource, {
        variables: { userId: sub, resource: googleResourceName },
    })

    const { loading: integrationLoading, error: integrationError, data: integrationData } = useQuery<{ Calendar_Integration: CalendarIntegrationType[] }>(getCalendarIntegrationByResourceAndName, {
        variables: {
            name: googleCalendarName,
            resource: googleResourceName,
            userId: sub,
        }
    })

    if (existingCalendarError) {
        toast({
            status: 'error',
            title: 'Error getting calendars',
            description: existingCalendarError.toString(),
            duration: 9000,
            isClosable: true,
        })
    }

    if (integrationError) {
        toast({
            status: 'error',
            title: 'Error getting calendar integrations',
            description: integrationError.toString(),
            duration: 9000,
            isClosable: true,
        })
    }

    const calendars = data?.Calendar
    const calendarIntegrations = integrationData?.Calendar_Integration
    
    // get calendar list
    useEffect(() => {
        if (!token) return
        (async () => {
            try {
                setLoading(true)
                const results = await listGoogleCalendars(token)
                console.log(results, ' results from listGoogleCalendars')
                const existingEnabledCalendars = results.map(calendar => {
                    const calendarId = calendar.id
                    const calendarName = calendar.summary
                    const calendarIndex = calendars?.findIndex(c => c.id === calendarId)
                    return {
                        id: calendarId,
                        name: calendarName,
                        enabled: (calendarIndex > -1),
                    }
                })
                setCalendarList(results)
                setEnabledCalendars(existingEnabledCalendars)
                setLoading(false)
                setDisableLoading(true)
            } catch (e) {
                console.log(e, ' error getting calendars')
                setLoading(false)
                toast({
                    status: 'error',
                    title: 'Error getting calendars',
                    description: e.toString(),
                    duration: 9000,
                    isClosable: true,
                })
                setDisableLoading(true)
            }
        })()
    }, [token, calendars?.length, calendars, toast])

    // const dark = useColorScheme() === 'dark'
    const updateEnabledCalendarValue = async (index: number, value: boolean) => {
        try {
            const newEnabledCalendars = enabledCalendars.map((c, idx) => {
                if (idx === index) {
                    return {
                        ...c,
                        enabled: value,
                    }
                }
                return c
            })
            setEnabledCalendars(newEnabledCalendars)
        } catch (e) {
            console.log(e, ' error updating enabled value')
            toast({
                status: 'error',
                title: 'Error updating enabled value',
                description: e.toString(),
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const upsertCalendarInDb = async (index: number) => {
        try {
            console.log(calendarList?.[index], sub, ' calendarList?.[index], sub inside  upsertCalendarInDb')
            return upsertGoogleCalendarInDb(
                client,
                calendarList?.[index],
                sub,
            )
        } catch (e) {
            console.log(e, ' error creating calendar')
        }
    }
    const deleteCalendarInDb = async (index: number) => {
        try {
            await deleteGoogleCalendarInDb(client, calendarList?.[index]?.id)
        } catch (e) {
            console.log(e, ' error deleting calendar')
        }
    }

    // delete event trigger in db
    const deleteEventTriggerInDb = async (index: number) => {
        try {
            await deleteEventTriggerByResourceId(calendarList?.[index]?.id)
        } catch (e) {
            console.log(e, ' error deleting event trigger')
        }
    }
    
    const triggerCalendarSync = async (
        index: number,
    ) => {
        try {
            return triggerGoogleCalendarSync(calendarIntegrations?.[0]?.id, calendarList?.[index]?.id, sub)
        } catch (e) {
            console.log(e, ' error triggering calendar sync')
        }
    }

    const addCalendarToSync = async (index: number) => {
        try {
            updateEnabledCalendarValue(index, true)
            await Promise.all([
                upsertCalendarInDb(index),
                triggerCalendarSync(index),
            ])

            toast({
                status: 'success',
                title: 'Pick a Primary Calendar',
                description: 'Make sure to pick a primary calendar in the next step (or under settings) or Atomic will not work properly ',
                duration: 9000,
                isClosable: true,
            })
        } catch (e) {
            console.log(e, ' error adding calendar to sync')
        }
    }

    const removeCalendarFromSync = async (index: number) => {
        try {
            updateEnabledCalendarValue(index, false)

            const eventsToDelete = await listEventsForCalendar(client, calendarList?.[index]?.id)
            await deleteAttendeesForEvents(client, eventsToDelete.map(e => e.id))
            const conferenceIds = eventsToDelete.map(e => e.conferenceId)
                .filter(id => !!id)

            await deleteRemindersForEvents(client, eventsToDelete.map(e => e.id), sub)
            await Promise.all([
                deleteEventTriggerInDb(index),
                deleteEventsByCalendarId(client, calendarList?.[index]?.id),
            ])

            if (conferenceIds?.length > 0) {
                await deleteConferencesWithIds(client, conferenceIds)
            }

            await deleteCalendarInDb(index)
            // await deleteCalendarWebhook(client, calendarList?.[index]?.id)
        } catch (e) {
            console.log(e, ' error removing calendar from sync')
        }
    }

    const addAllCalendarsToSync = async () => {
        try {
            const promises = []
            for (let i = 0; i < calendarList.length; i++) {
                promises.push(addCalendarToSync(i))
            }
            await Promise.all(promises)
        } catch (e) {
            console.log(e, ' error adding calendar to sync all')
        }
    }

    const removeAllCalendarFromSync = async () => {
        try {
            const promises = []
            for (let i = 0; i < calendarList.length; i++) {
                promises.push(removeCalendarFromSync(i))
            }
            await Promise.all(promises)
        } catch (e) {
            console.log(e, ' error removing calendar from sync all')
        }
    }

    const updateEnabledValue = async (index: number, value: boolean) => {
        try {
            
            const newEnabledCalendars = enabledCalendars
                ?.slice(0, index)
                ?.concat([{ ...(enabledCalendars?.[index]), enabled: value }])
                ?.concat(enabledCalendars?.slice(index + 1) || [])
                ?.filter(f => !!f)

            setEnabledCalendars(newEnabledCalendars)
            
            if (value) {
                return addCalendarToSync(index)
            } else {
                return removeCalendarFromSync(index)
            }
        } catch (e) {
            console.log(e, ' error updating enabled value')
            toast({
                status: 'error',
                title: 'Error updating enabled value',
                description: e.toString(),
            })
        }
    }

    const updateAllCalendars = async (value: boolean) => {
        try {
            if (value) {
                setEnableAllCalendars(true)
                return addAllCalendarsToSync()
            }
            setEnableAllCalendars(false)
            return removeAllCalendarFromSync()
        } catch (e) {
            console.log(e, ' error updating all calendars')
            toast({
                status: 'error',
                title: 'Error updating all calendars',
                description: e.toString(),
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const closeGoogleCalendarList = () => props.setParentIsGoogleCalendarList(false)

    const renderItem = ({ item, index }: RenderItemType) => {
        // console.log(item, ' item inside renderItem') // Reduced console noise
        return (
            <CalendarCheckBox
                updateEnabledValue={updateEnabledValue}
                index={index}
                enabled={item?.enabled}
                name={item?.name}
                
                id={item?.id}
                calendars={calendars}
            />
        )
    }
 
    if (loading || existingCalendarLoading || integrationLoading || !disableLoading) {
        return (
         <Box backgroundColor="primaryCardBackground" flex={1} justifyContent="center" alignItems="center" style={{ width: '100%'}} minHeight="80vh">
              <ActivityIndicator size="large" color={palette.white} />
          </Box>
        )
    }

    if (!(calendarIntegrations?.length > 0)) {
        toast({
            status: 'error',
            title: 'Google Not Enabled',
            description: 'Google calendar integration is not enabled',
            duration: 9000,
            isClosable: true,
        })
    }

    return (
        <Box flex={1} justifyContent="space-around" alignItems="center" style={{ width: '100%' }} minHeight="70vh">
            <Box flex={1} style={{ width: '80%' }} flexDirection="row" justifyContent="space-around" alignItems="center">
                <Box>
                    <Text variant="optionHeader" style={{ color: palette.darkGray }}>
                    All Google Calendars
                    </Text>
                </Box>
                <Box>
                    <Switch1
                        onValueChange={updateAllCalendars}
                        checked={enableAllCalendars}
                    />
                </Box>
            </Box>
            <Box style={{ width: '90%' }} flex={3} justifyContent="center" alignItems="center">
            <FlatList
                style={{ flex: 1 }}
                data={enabledCalendars}
                keyExtractor={item => item.id}
                renderItem={renderItem}
                extraData={`${enabledCalendars.map(i => i?.id)}`}
            />
            </Box>
            <Box flex={1} mt="m">
                <Pressable onPress={closeGoogleCalendarList}>
                    <Text variant="buttonLink" textAlign="center">
                        Confirm Calendar Selection
                    </Text>
                </Pressable>
            </Box>
        </Box>
    )
}

function UserEnableIntegrations(props: Props) {
    const [loading, setLoading] = useState<boolean>(false)
    const [isWarning, setIsWarning] = useState<boolean>(false)
    const [selectedIndex, setSelectedIndex] = useState<number>(-1)
    const [selectedId, setSelectedId] = useState<string>()
    const [selectedValue, setSelectedValue] = useState<boolean>(false)
    const [isGoogleCalendarList, setIsGoogleCalendarList] = useState<boolean>(false) // Initial state is false
    const [googleToken, setGoogleToken] = useState<string>()

    const googleCalendarElement = useRef<any>()

    // const dark = useColorScheme() === 'dark'
    const router = useRouter()
    const { sub: userId } = props
    const client = props?.client

    const toast = useToast()
   

    const { loading: googleIntegrationLoading, error: googleIntegrationError, data: googleIntegrationData, refetch: googleIntRefetch } = useQuery<{ Calendar_Integration: CalendarIntegrationType[] }>(getCalendarIntegrationByResourceAndName, {
        variables: {
            name: googleCalendarName,
            resource: googleResourceName,
            userId: userId,
        }
    })

    const { loading: integrationLoading, error: integrationError, data: integrationData, refetch } = useQuery<{ Calendar_Integration: CalendarIntegrationType[] }>(listCalendarIntegrations, {
        variables: {
            userId: userId,
        }
    })
    
    const googleCalendarEnabled = googleIntegrationData?.Calendar_Integration?.[0]?.enabled
    
    const integrations = integrationData?.Calendar_Integration

    // Automatically display calendar list when Google Calendar is enabled and token is available
    useEffect(() => {
        if (googleCalendarEnabled && googleToken) {
            setIsGoogleCalendarList(true)
        }
    }, [googleCalendarEnabled, googleToken])

    //  just in case oldIntegrations are not loaded
    useEffect(() => {
        (async () => {
            if (!(integrations?.length > 0)) {
                await refetch()
                await googleIntRefetch()
            }
        })()
    }, [googleIntRefetch, integrations?.length, refetch])

   
    
    const disableGoogleCalendarCheckBox = () => {
        setSelectedIndex(-1)
        setSelectedId('')
        setSelectedValue(false)
        setIsWarning(false)
        googleCalendarElement?.current?.disableEnabled()
    }
    
    const enableGoogleCalendarCheckBox = async () => {
    try {
        setIsWarning(false)
        // const newIntegrations = integrations
        // .slice(0, selectedIndex)
        // .concat([{ ...(integrations?.[selectedIndex]), enabled: selectedValue }])
        // .concat(integrations.slice(selectedIndex + 1))

        // setIntegrations(newIntegrations)

        await submitIntegration(
            selectedIndex,
            selectedValue,
            selectedId,
        )
        await refetch()
        await googleIntRefetch()
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
            //     .slice(0, index)
            //     .concat([{ ...(integrations?.[index]), enabled: value }])
            //     .concat(integrations.slice(index + 1))

            // setIntegrations(newIntegrations)

            await submitIntegration(
                index,
                value,
                id,
            )

            await refetch()
            await googleIntRefetch()
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
        
        await refetch()
        await googleIntRefetch()
    } catch (e) {
        console.log(e, ' this is e for disable google calendarsync')
        await refetch()
        await googleIntRefetch()
    }
    }


    const disableZoomAuth = async (
        integrationId: string,
    ) => {
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
            console.log(integrations?.[index]?.name, ' integrations?.[index]?.name inside submitIntegration')

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

            // return navigation.navigate('UserViewGoogleCalendarList', { token: newAccessToken })
            setGoogleToken(newAccessToken)
            return setIsGoogleCalendarList(true)
        } catch (e) {
            console.log(e, ' unable to navigate to google calendars')
        }
    }


    const renderItem2 = ({ item, index }: RenderItemType2) => {
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
            <Box flex={1} justifyContent="center" alignItems="center" style={{ width: '100%'}} backgroundColor="lightRegularCardBackground">
                <ActivityIndicator size="large" color={palette.white} />
            </Box>
        )
    }

    if (isGoogleCalendarList){
        return (
            <UserViewGoogleCalendarList 
                client={client} 
                token={googleToken} 
                sub={userId} 
                setParentIsGoogleCalendarList={setIsGoogleCalendarList} 

            />
        )
    }

    return (
        <Box justifyContent="center" alignItems="center" minHeight="70vh">
          {
            integrations?.length > 0
              ? (
                <Box justifyContent="center" alignItems="center" minHeight="70vh">
                    <Box justifyContent="center" alignItems="center">
                        <FlatList
                            data={integrations}
                            keyExtractor={item => item.id}
                            renderItem={renderItem2}
                        />
                    </Box>
                  {googleCalendarEnabled
                    ? (
                    {/* "View Google Calendars" button is hidden if list is already shown or will be shown automatically */}
                    { (googleCalendarEnabled && !isGoogleCalendarList && !googleToken) && // Show button only if enabled but list not yet shown (e.g. token fetch in progress)
                        <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                            <Pressable onPress={navigateToGoogleCalendars}>
                            <Text variant="buttonLink">
                                View Google Calendars
                            </Text>
                            </Pressable>
                        </Box>
                    }
                    { (googleCalendarEnabled && googleToken && !isGoogleCalendarList) && // Case where token is fetched but useEffect for auto-show hasn't run yet or user closed it.
                        <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                            <Pressable onPress={navigateToGoogleCalendars}>
                              <Text variant="buttonLink">
                                Manage Google Calendars
                              </Text>
                            </Pressable>
                        </Box>
                    }
                    { !googleCalendarEnabled && (
                        null // No button if Google Calendar is not enabled
                    )}
                </Box>
            ) : (
              <Box flex={1} justifyContent="center" alignItems="center">
                <Text variant="subheader" style={{ color: palette.darkGray }}>
                  Still loading ...
                </Text>
              </Box>
            )
          }
          <Box>
            <Overlay isVisible={isWarning} onBackdropPress={disableGoogleCalendarCheckBox} overlayStyle={{ backgroundColor: palette.white }}>
                <Box justifyContent="center" alignItems="center" style={{ width: '80%', backgroundColor: palette.white }}>
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

                    <Button disabled onClick={disableGoogleCalendarCheckBox}>
                    Cancel
                    </Button>   
                    </Box>
                </Box>
            </Overlay>
          </Box>
        </Box>
      );
}

export default UserEnableIntegrations






