import React, {
    useState,
    useEffect,
  } from 'react'
import { useToast } from '@chakra-ui/react'
import { dayjs } from '@lib/date-utils'
import { v4 as uuid } from 'uuid'
import Button from '@components/Button'
import Wizard from '@components/Wizard'
import RegularCard from '@components/RegularCard'
import { 
    generateDefaultCategories, 
    createUserPreference, 
    createDefaultUser,
    createInitialSelectedCalendar,
    getUserPreference,
    updateUserPreferenceOnBoarded,
} from '@lib/OnBoard/OnBoardHelper2'
import { createInitialCalendarIntegrations } from '@lib/Settings/calendar_integrationHelper'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import { EndTimeType, StartTimeType } from '@lib/dataTypes/User_PreferenceType'
import UserEnableIntegrations from '@pages/OnBoard/OnBoardWizard/UserEnableIntegrations'
import UserSelectPrimaryCalendar from '@pages/OnBoard/OnBoardWizard/UserSelectPrimaryCalendar'
import UserAddTags from '@pages/OnBoard/OnBoardWizard/UserAddTags'
import UserDefaultAlarms from '@pages/OnBoard/OnBoardWizard/UserDefaultAlarms'
import UserWorkDay from '@pages/OnBoard/OnBoardWizard/UserWorkDay'
// import UserPreferenceForTimeBlockElements from '@pages/OnBoard/OnBoardWizard/UserPreferenceForTimeBlockElements' // DELETED
// import UserPreferenceForTimeBlockElements2 from '@pages/OnBoard/OnBoardWizard/UserPreferenceForTimeBlockElements2' // DELETED
// import UserPreferenceForTimeBlockElements3 from '@pages/OnBoard/OnBoardWizard/UserPreferenceForTimeBlockElements3' // DELETED
// Consolidated component (conceptual - will be rendered directly in UserOnBoard for now)
// import UserEventDefaultsPreference from '@pages/OnBoard/OnBoardWizard/UserEventDefaultsPreference'
import _ from 'lodash'
import { gql, useQuery } from '@apollo/client'
import { UserType } from '@lib/dataTypes/UserType'
import getUserById from '@lib/apollo/gql/getUserById'
import { ActivityIndicator, Pressable, ScrollView, useColorScheme } from 'react-native'
import Switch1 from '@components/Switch'
import TextField from '@components/TextField'
import EditBreakPreferenceColor from '@pages/Settings/UserPreferenceWizard/EditBreakPreferenceColor'
import Circle from '@uiw/react-color-circle'
import { colorsPalette as Colors } from '@lib/theme/colorsPalette'

import { palette } from '@lib/theme/theme'
import { getGlobalPrimaryCalendarFunction } from '@lib/Schedule/ScheduleHelper'
import { useRouter } from 'next/router'
import { useAppContext } from '@lib/user-context'
import { ChatMeetingPreferencesType } from '@lib/dataTypes/ChatMeetingPreferenceType'
import { upsertChatMeetingPreferencesGivenUserId } from '@lib/OnBoard/OnBoardHelper3'

const DEFAULT_START_TIMES = [
    {
        day: 1,
        hour: 7,
        minutes: 0,
    },
    {
        day: 2,
        hour: 7,
        minutes: 0,
    },
    {
        day: 3,
        hour: 7,
        minutes: 0,
    },
    {
        day: 4,
        hour: 7,
        minutes: 0,  
    },
    {
        day: 5,
        hour: 7,
        minutes: 0,  
    },
    {
        day: 6,
        hour: 7,
        minutes: 0,
    },
    {
        day: 7,
        hour: 7,
        minutes: 0,
    }
]

const DEFAULT_END_TIMES = [
    {
        day: 1,
        hour: 23,
        minutes: 0,
    },
    {
        day: 2,
        hour: 23,
        minutes: 0,
    },
    {
        day: 3,
        hour: 23,
        minutes: 0,
    },
    {
        day: 4,
        hour: 23,
        minutes: 0,
    },
    {
        day: 5,
        hour: 23,
        minutes: 0,
    },
    {
        day: 6,
        hour: 23,
        minutes: 0,
    },
    {
        day: 7,
        hour: 23,
        minutes: 0,
    }
]

import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
import Session from 'supertokens-node/recipe/session'
import ThirdPartyEmailPassword from "supertokens-node/recipe/thirdpartyemailpassword"

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
    const userInfo = await ThirdPartyEmailPassword.getUserById(session.getUserId())
    return {
        props: {
            sub: session.getUserId(),
            email: userInfo?.email,
        }
    }
}

type Props = {
    sub: string,
    email: string,
}

function UserOnBoard(props: Props) {
    const [reminders, setReminders] = useState<number[]>([])
    const [startTimes, setStartTimes] = useState<StartTimeType[]>([])
    const [endTimes, setEndTimes] = useState<EndTimeType[]>([])
    const [copyAvailability, setCopyAvailability] = useState<boolean>(false)
    const [copyTimeBlocking, setCopyTimeBlocking] = useState<boolean>(false)
    const [copyTimePreference, setCopyTimePreference] = useState<boolean>(false)
    const [copyReminders, setCopyReminders] = useState<boolean>(false)
    const [copyPriorityLevel, setCopyPriorityLevel] = useState<boolean>(false)
    const [copyModifiable, setCopyModifiable] = useState<boolean>(false)
    const [copyCategories, setCopyCategories] = useState<boolean>(false)
    const [copyIsBreak, setCopyIsBreak] = useState<boolean>(false)
    const [maxWorkLoadPercent, setMaxWorkLoadPercent] = useState<number>(85)
    const [minNumberOfBreaks, setMinNumberOfBreaks] = useState<number>()
    const [breakLength, setBreakLength] = useState<number>()
    const [backToBackMeetings, setBackToBackMeetings] = useState<boolean>(false)
    const [maxNumberOfMeetings, setMaxNumberOfMeetings] = useState<number>(6)
    const [copyIsMeeting, setCopyIsMeeting] = useState<boolean>(false)
    const [copyIsExternalMeeting, setCopyIsExternalMeeting] = useState<boolean>(false)
    const [copyColor, setCopyColor] = useState<boolean>(true) // Defaulted to true
    const [activeIndex, setActiveIndex] = useState<number>(0)
    const [completedStep, setCompletedStep] = useState<number | undefined>()
    const [breakColor, setBreakColor] = useState<string>('#F7EBF7') // Default break color
    const [selectedCalendarId, setSelectedCalendarId] = useState<string>()
    const [enableSelectColor, setEnableSelectColor] = useState<boolean>(false) // For break color picker
    const [showAdvancedOptions, setShowAdvancedOptions] = useState<boolean>(false) // For advanced options toggle
    
    const { sub, client } = useAppContext()
    const { email } = props
    const { loading, error, data, refetch } = useQuery<{ User_by_pk: UserType }>(getUserById, {
        variables: { id: sub },
    })

    
    const router = useRouter()

    const userId = sub
    const taskType = router.query?.taskType
    const user = data?.User_by_pk
    const toast = useToast()

    if (error) {
        toast({
            status: 'error',
            title: 'Error',
            description: 'Oops...',
            duration: 9000,
            isClosable: true,
        })
    }

    useEffect(() => {
    (async () => {
        if (!userId && !user) {
            return
        }
      const user_preferenceDoc = await getUserPreference(client, userId)
      console.log(user_preferenceDoc?.onBoarded, ' user_preferenceDoc?.onBoarded')
      if (user_preferenceDoc?.onBoarded) {
        console.log(' already onBoarded')
        return taskType
                ? router.push({pathname: '/Progress/Todo/UserTask', query: { taskType }})
                : router.push({ pathname: '/' })
      }
        })()
    }, [client, router, taskType, userId])


    // getglobal primary calendar if any
    useEffect(() => {
        (async () => {
            if (!userId) {
                return
            }
            const result = await getGlobalPrimaryCalendarFunction(client, userId)
            if (result?.id) setSelectedCalendarId(result?.id)
        })()
    }, [client, userId])

    // generateDefaultCategories
    useEffect(() => {
        (async () => {
            if (!user?.id) {
                return
            }
            await generateDefaultCategories(client, userId)
        })()
    }, [client, user?.id, userId])

    // createDefaultUser
    useEffect(() => {
        (async () => {
            if (!userId) {
                return
            }
            
            await createDefaultUser(client, userId, email)
            await refetch()
        })()
    }
    , [client, email, refetch, userId])

    // createuser_preference
    useEffect(() => {
        (async () => {
            if (!user?.id) {
                return
            }

            const user_preferenceDoc = await getUserPreference(client, userId)
            if (!user_preferenceDoc?.id) {
                await createUserPreference(client, userId)
            }
            
        })()
    }
    , [client, user?.id, userId])

    useEffect(() => {
        (async () => {
            if (!user?.id) {
                return
            }

            const chatMeetingPreference: ChatMeetingPreferencesType = {
                id: uuid(),
                userId,
                timezone: dayjs.tz.guess(),
                enableConference: true,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format()
            }
            
            await upsertChatMeetingPreferencesGivenUserId(client, chatMeetingPreference)
            
        })()
    }
    , [client, user?.id, userId])

    // createInitialcalendar_integrations
    useEffect(() => {
        (async () => {
            if (!user?.id) {
                return
            }
            await createInitialCalendarIntegrations(client, userId)
        })()
    }
    , [client, user?.id, userId])

    // createInitialSelectedCalendar
    useEffect(() => {
        (async () => {
            if (!user?.id) {
                return
            }
            await createInitialSelectedCalendar(client, userId, setSelectedCalendarId)
        })()
    }, [client, user?.id, userId])

    // get user preferences
    useEffect(() => {
        (async () => {
            try {
                if (!user?.id) {
                    return
                }
                const existinguser_preferences = await getUserPreference(client, userId)
                setReminders(existinguser_preferences?.reminders)
                setStartTimes((existinguser_preferences?.startTimes as StartTimeType[]) || (DEFAULT_START_TIMES as StartTimeType[]))
                setEndTimes((existinguser_preferences?.endTimes as EndTimeType[]) || (DEFAULT_END_TIMES as EndTimeType[]))
                setCopyAvailability(existinguser_preferences?.copyAvailability !== undefined ? existinguser_preferences?.copyAvailability : true)
                setCopyTimeBlocking(existinguser_preferences?.copyTimeBlocking !== undefined ? existinguser_preferences?.copyTimeBlocking : true)
                setCopyTimePreference(existinguser_preferences?.copyTimePreference !== undefined ? existinguser_preferences?.copyTimePreference : true)
                setCopyReminders(existinguser_preferences?.copyReminders !== undefined ? existinguser_preferences?.copyReminders : true)
                setCopyPriorityLevel(existinguser_preferences?.copyPriorityLevel !== undefined ? existinguser_preferences?.copyPriorityLevel : true)
                setCopyModifiable(existinguser_preferences?.copyModifiable !== undefined ? existinguser_preferences?.copyModifiable : true)
                setCopyCategories(existinguser_preferences?.copyCategories !== undefined ? existinguser_preferences?.copyCategories : true)
                setCopyIsBreak(existinguser_preferences?.copyIsBreak !== undefined ? existinguser_preferences?.copyIsBreak : true)
                setMaxWorkLoadPercent(existinguser_preferences?.maxWorkLoadPercent || 85)
                setMinNumberOfBreaks(existinguser_preferences?.minNumberOfBreaks || 1)
                setBreakLength(existinguser_preferences?.breakLength || 30)
                setBackToBackMeetings(existinguser_preferences?.backToBackMeetings !== undefined ? existinguser_preferences?.backToBackMeetings : false)
                setMaxNumberOfMeetings(existinguser_preferences?.maxNumberOfMeetings || 6)
                setCopyIsMeeting(existinguser_preferences?.copyIsMeeting !== undefined ? existinguser_preferences?.copyIsMeeting : true)
                setCopyIsExternalMeeting(existinguser_preferences?.copyIsExternalMeeting !== undefined ? existinguser_preferences?.copyIsExternalMeeting : true)
                setCopyColor(existinguser_preferences?.copyColor !== undefined ? existinguser_preferences?.copyColor : true)
                setBreakColor(existinguser_preferences?.breakColor || '#F7EBF7')
            } catch (e) {
                console.log(e, ' error in useEffect for UserCalendarPreferences')
            }
        })()
    }, [client, user?.id, userId])

    // save reminders
    const saveReminders = async () => {
        try {
            // save
            const existinguser_preferences = await getUserPreference(client, userId)
            if (!existinguser_preferences) {
                toast({
                    title: 'Error',
                    description: 'Error saving user preferences',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                })
                return
            }

            const upsertUserPreferenceMutation = gql`
            mutation InsertUserPreference($userPreference: User_Preference_insert_input!) {
                insert_User_Preference_one(
                    object: $userPreference,
                    on_conflict: {
                    constraint: UserPreference_pkey,
                    update_columns: [
                        ${(reminders?.length > 0)
                            && !_.isEqual(reminders, existinguser_preferences?.reminders) ? 'reminders,' : ''}
                        updatedAt,
                    ]
                    }
                ) {
                    id
                    reminders
                    followUp
                    isPublicCalendar
                    publicCalendarCategories
                    startTimes
                    endTimes
                    copyAvailability
                    copyTimeBlocking
                    copyTimePreference
                    copyReminders
                    copyPriorityLevel
                    copyModifiable
                    copyCategories
                    copyIsBreak
                    maxWorkLoadPercent
                    backToBackMeetings
                    maxNumberOfMeetings
                    minNumberOfBreaks
                    breakLength
                    breakColor
                    copyIsMeeting
                    copyIsExternalMeeting
                    copyColor
                    deleted
                    createdDate
                    updatedAt
                    userId
                }
                }`
            const valuesToUpsert: any = {
                id: existinguser_preferences?.id,
                userId,
            }

            if ((reminders?.length > 0)
            && !_.isEqual(reminders, existinguser_preferences?.reminders)) {
                valuesToUpsert.reminders = reminders
            }
            
            if (valuesToUpsert?.reminders?.length > 0) {
                await client.mutate({
                    mutation: upsertUserPreferenceMutation,
                    variables: {
                        userPreference: valuesToUpsert,
                    },
                })
            }

            console.log('reminders saved')
        } catch (e) {
            console.log(e, ' error in saveReminders')
        }
    }

    // save selected Calendar
    // const saveSelectedCalendar = async () => {
    //     try {
    //         // save
    //         await setPrimaryCalendar(client, selectedCalendar as CalendarType)
    //     } catch (e) {
    //         console.log(e, ' error in saveSelectedCalendar')
    //     }
    // }

    // save work day
    const saveWorkDay = async () => {
        try {
            // save
            const existinguser_preferences = await getUserPreference(client, userId)
            if (!existinguser_preferences) {
                toast({
                    title: 'Error',
                    description: 'Error saving user preferences',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                })
                return
            }

            const upsertUserPreferenceMutation = gql`
            mutation InsertUserPreference($userPreference: User_Preference_insert_input!) {
                insert_User_Preference_one(
                    object: $userPreference,
                    on_conflict: {
                    constraint: UserPreference_pkey,
                    update_columns: [
                        ${(startTimes?.length > 0)
                            && !_.isEqual(startTimes, existinguser_preferences?.startTimes) ? 'startTimes,' : ''}
                        ${(endTimes?.length > 0)
                        && !_.isEqual(endTimes, existinguser_preferences?.endTimes) ? 'endTimes,' : ''}
                        updatedAt,
                    ]
                    }
                ) {
                    id
                    reminders
                    followUp
                    isPublicCalendar
                    publicCalendarCategories
                    startTimes
                    endTimes
                    copyAvailability
                    copyTimeBlocking
                    copyTimePreference
                    copyReminders
                    copyPriorityLevel
                    copyModifiable
                    copyCategories
                    copyIsBreak
                    maxWorkLoadPercent
                    backToBackMeetings
                    maxNumberOfMeetings
                    minNumberOfBreaks
                    breakLength
                    breakColor
                    copyIsMeeting
                    copyIsExternalMeeting
                    copyColor
                    deleted
                    createdDate
                    updatedAt
                    userId
                }
                }`
            const valuesToUpsert: any = {
                id: existinguser_preferences?.id,
                userId,
            }

            if ((startTimes?.length > 0)
                && !_.isEqual(startTimes, existinguser_preferences?.startTimes)) {
                valuesToUpsert.startTimes = startTimes
            }

            if ((endTimes?.length > 0)
                && !_.isEqual(endTimes, existinguser_preferences?.endTimes)) {
                valuesToUpsert.endTimes = endTimes
            }
            
            if ((valuesToUpsert?.startTimes?.length > 0) || (valuesToUpsert?.endTimes?.length > 0)) {
                const { data } = await client.mutate({
                    mutation: upsertUserPreferenceMutation,
                    variables: {
                        userPreference: valuesToUpsert,
                    },
                })
                console.log(data, 'updated work day saved')
            }
            
        } catch (e) {
            console.log(e, ' error in saveWorkDay')
        }
    }

    // save user preferences for the consolidated step
    const saveEventDefaultPreferences = async () => {
        try {
            const existinguser_preferences = await getUserPreference(client, userId)
            if (!existinguser_preferences) {
                toast({
                    title: 'Error',
                    description: 'Error saving user preferences',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                })
                return
            }

            const existinguser_preferences = await getUserPreference(client, userId)
            if (!existinguser_preferences) {
                toast({
                    title: 'Error',
                    description: 'Error saving user preferences',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                })
                return
            }

            const upsertUserPreferenceMutation = gql`
            mutation InsertUserPreference($userPreference: User_Preference_insert_input!) {
                insert_User_Preference_one(
                    object: $userPreference,
                    on_conflict: {
                    constraint: UserPreference_pkey,
                    update_columns: [
                        ${copyColor !== undefined ? 'copyColor,' : ''}
                        ${copyIsMeeting !== undefined ? 'copyIsMeeting,' : ''}
                        ${copyIsExternalMeeting !== undefined ? 'copyIsExternalMeeting,' : ''}
                        ${backToBackMeetings !== undefined ? 'backToBackMeetings,' : ''}
                        ${breakColor !== undefined ? 'breakColor,' : ''}
                        updatedAt,
                    ]
                    }
                ) {
                    id
                    reminders
                    followUp
                    isPublicCalendar
                    publicCalendarCategories
                    startTimes
                    endTimes
                    copyAvailability
                    copyTimeBlocking
                    copyTimePreference
                    copyReminders
                    copyPriorityLevel
                    copyModifiable
                    copyCategories
                    copyIsBreak
                    maxWorkLoadPercent
                    backToBackMeetings
                    maxNumberOfMeetings
                    minNumberOfBreaks
                    breakLength
                    breakColor
                    copyIsMeeting
                    copyIsExternalMeeting
                    copyColor
                    deleted
                    createdDate
                    updatedAt
                    userId
                }
                }`

            const valuesToUpsert: any = {
                id: existinguser_preferences?.id,
                userId,
            }

            if (copyColor !== undefined) {
                valuesToUpsert.copyColor = copyColor
            }

            if (copyIsMeeting !== undefined) {
                valuesToUpsert.copyIsMeeting = copyIsMeeting
            }

            if (copyIsExternalMeeting !== undefined) {
                valuesToUpsert.copyIsExternalMeeting = copyIsExternalMeeting
            }

            if (backToBackMeetings !== undefined) {
                valuesToUpsert.backToBackMeetings = backToBackMeetings
            }

            if (breakColor !== undefined) {
                valuesToUpsert.breakColor = breakColor
            }

            await client.mutate({
                mutation: upsertUserPreferenceMutation,
                variables: {
                    userPreference: valuesToUpsert,
                },
            })

        } catch (e) {
            console.log(e, ' error in saveuser_preferencesTimeBlock3')
        }
    }

    const onActiveIndexChanged = (index: number) => setActiveIndex(index)

    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex
        const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1
        setActiveIndex(newActiveIndex)
    }

    const renderPrevButton = () => {
        if (activeIndex === 0) {
            return <Box pt={{ phone: 'm', tablet: 's' }}/>
        }

        return (
            <Box mb={{ phone: 's', tablet: 'm' }} ml={{ phone: 's', tablet: 'm' }}>
                <Button onClick={goToPrevStep}>
                    Back
                </Button>
            </Box>
        )
    }

    const goToNextStep = async () => {
        try {
            /*
                0 - Intro message
                1 - UserEnableIntegrations
                2 - UserSelectPrimaryCalendar
                3 - UserAddTags
                4 - UserDefaultAlarms
                5 - UserWorkDay
                6 - UserEventDefaultsPreference (New Consolidated Step)
                7 - Exit message (Previously 9)
            */

            const prevActiveIndex = activeIndex
            const prevCompletedStep = completedStep
            
            // Adjusted exit condition due to reduced steps
            if (prevActiveIndex === 7) {
                return
            }

            // if (prevActiveIndex === 2) {
            //     await saveSelectedCalendar()
            // }

            if (prevActiveIndex === 4) { // UserDefaultAlarms
                await saveReminders()
            }

            if (prevActiveIndex === 5) { // UserWorkDay
                console.log(startTimes, ' startTimes in parent')
                await saveWorkDay()
            }

            if (prevActiveIndex === 6) { // New consolidated step: UserEventDefaultsPreference
                await saveEventDefaultPreferences()
            }

            let newActiveIndex = prevActiveIndex + 1

            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex
                setCompletedStep(newCompletedStep)
            }
    
            if (newActiveIndex !== prevActiveIndex) {
                setActiveIndex(newActiveIndex)
            }
        } catch (e) {
            console.log(e, ' error in goToNextStep')
        }
    }

    const renderNextButton = () => {
        // Adjusted condition due to reduced steps
        if (activeIndex === 7) {
        return <Box pt={{ phone: 'm', tablet: 's' }}/>
        }

        return (
        <Box mb={{ phone: 's', tablet: 'm' }} mr={{ phone: 's', tablet: 'm' }}>
            <Button onClick={goToNextStep}>
                Next
            </Button>
        </Box>
        )
    }


    const completeOnboarding = async () => {
        // Ensure preferences are saved if user jumps to complete from the last settings step
        if (activeIndex === 6) {
            await saveEventDefaultPreferences()
        }
        await updateUserPreferenceOnBoarded(client, userId, true)

        if (taskType) {
            router.push({ pathname: '/Progress/Todo/UserTask', query: { taskType }})
        } else {
            router.push('/')
        }
        
    }

    const renderCurrentStep = () => {
        switch (activeIndex) {
            case 0:
                return (
                    <Box style={{ width: '100%'}} flex={1} justifyContent="center" alignItems="center">
                        <Text variant="subheader" p={{ phone: 'm', tablet: 'l' }}>
                            Welcome to Atomic! Let&apos;s Get You Set Up.
                        </Text>
                        <Box p={{ phone: 'm', tablet: 'l' }}>
                            <Text variant="optionHeader" p={{ phone: 'm', tablet: 'l' }}>
                                This quick setup wizard will personalize Atomic to your work style.
                            </Text>
                            <Text variant="optionHeader" p={{ phone: 'm', tablet: 'l' }}>
                                The preferences you set here will power Atomic&apos;s intelligent scheduling assistance, helping you save time and stay organized.
                            </Text>
                            <Text variant="optionHeader" p={{ phone: 'm', tablet: 'l' }}>
                                You can always adjust these settings later.
                            </Text>
                            <Text variant="optionHeader" p={{ phone: 'm', tablet: 'l' }}>
                                For example, soon you&apos;ll be able to tell Atomic things like: &apos;Schedule two project update meetings next Monday morning.&apos;
                            </Text>
                        </Box>
                        <Box style={{ width: '100%' }} p={{ phone: 'l', tablet: 'xl' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            <Box />
                            {renderNextButton()}
                        </Box>
                    </Box>

                )
            case 1:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <Box style={{ width: '100%' }} flex={1} justifyContent="center" alignItems="center">
                            <UserEnableIntegrations 
                                sub={userId} 
                                client={client} 
                            />
                        </Box>
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 2:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <UserSelectPrimaryCalendar
                            selectedCalendarId={selectedCalendarId}
                            userId={userId} 
                            setParentSelectedCalendarId={setSelectedCalendarId}
                            client={client}
                        />
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 3:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <UserAddTags sub={userId} client={client} />
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 4:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <UserDefaultAlarms reminders={reminders} setParentReminders={setReminders} />
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 5:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <UserWorkDay startTimes={startTimes} setParentStartTimes={setStartTimes} endTimes={endTimes} setParentEndTimes={setEndTimes} />
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 6: // New Consolidated Step: Customize Event Defaults
                if (enableSelectColor) { // For break color picker
                    return (
                        <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <EditBreakPreferenceColor
                            breakColor={breakColor}
                            setParentBreakColor={setBreakColor}
                            setParentEnableSelectColor={setEnableSelectColor}
                        />
                        </Box>
                    )
                }
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <ScrollView style={{ width: '100%' }} contentContainerStyle={{ width: '100%', justifyContent: 'center', alignItems: 'center' }}>
                            <Box p="m" width="90%" alignItems="center">
                                <Text textAlign="center" variant="optionHeader">
                                    Customize your event defaults. These settings help Atomic intelligently schedule and manage your time.
                                </Text>
                            </Box>

                            {/* maxWorkLoadPercent */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                <Box flexDirection="row" justifyContent="flex-start" alignItems="center" style={{ width: '100%' }}>
                                    <Text variant="optionHeader">
                                        Maximum daily workload percentage:
                                    </Text>
                                </Box>
                                <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                                    <TextField
                                        type="number"
                                        onChange={(e: { target: { value: string } }) => setMaxWorkLoadPercent(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                                        value={`${maxWorkLoadPercent}`}
                                        placeholder="85"
                                        trailingAccessory={(<Text pl={{ phone: 's', tablet: 'm' }} variant="cardTitle">%</Text>)}
                                    />
                                </Box>
                            </Box>

                            {/* minNumberOfBreaks */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}>
                                    <Text variant="optionHeader">
                                        Minimum number of daily breaks:
                                    </Text>
                                </Box>
                                <Box flexDirection="row" justifyContent="flex-end"  style={{ width: '100%' }}>
                                    <TextField
                                        type="number"
                                        onChange={(e: { target: { value: string } }) => setMinNumberOfBreaks(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                                        value={`${minNumberOfBreaks}`}
                                        placeholder="1"
                                    />
                                </Box>
                            </Box>

                            {/* breakLength */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}>
                                    <Text variant="optionHeader">
                                        Default break length (minutes):
                                    </Text>
                                </Box>
                                <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                                    <TextField
                                        type="number"
                                        onChange={(e: { target: { value: string } }) => setBreakLength(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                                        value={`${breakLength}`}
                                        placeholder="30"
                                        trailingAccessory={(<Text pl={{ phone: 's', tablet: 'm' }} variant="cardTitle">minutes</Text>)}
                                    />
                                </Box>
                            </Box>

                            {/* backToBackMeetings */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                <Box flexDirection="row" justifyContent="flex-start" alignItems="center">
                                    <Text variant="optionHeader">Allow back-to-back meetings?</Text>
                                </Box>
                                <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}>
                                    <Switch1
                                        checked={backToBackMeetings}
                                        onValueChange={setBackToBackMeetings}
                                    />
                                </Box>
                            </Box>

                            {/* breakColor */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                    <Text variant="optionHeader">Default break color:</Text>
                                    <Pressable onPress={() => setEnableSelectColor(true)}>
                                        <Box width={20} height={20} style={{ backgroundColor: breakColor, borderRadius: 10, borderWidth: 1, borderColor: palette.text }} />
                                    </Pressable>
                                </Box>
                            </Box>

                            {/* Advanced Options Toggle */}
                            <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }} mt="l">
                                <Pressable onPress={() => setShowAdvancedOptions(!showAdvancedOptions)}>
                                    <Text variant="buttonLink" textAlign="center">
                                        {showAdvancedOptions ? 'Hide Advanced Options' : 'Show Advanced Options'}
                                    </Text>
                                </Pressable>
                            </Box>

                            {showAdvancedOptions && (
                                <>
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }} mt="m">
                                        <Text variant="subheader" textAlign="center">Auto-Copy Settings</Text>
                                        <Text variant="body" textAlign="center" mt="s">These settings allow Atomic to learn from your past events to speed up future event creation.</Text>
                                    </Box>

                                    {/* copyAvailability */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse 'Busy/Free' status from similar events?</Text>
                                            <Switch1 checked={copyAvailability} onValueChange={setCopyAvailability} />
                                        </Box>
                                    </Box>
                                    {/* copyTimeBlocking */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse buffer times (before/after) from similar events?</Text>
                                            <Switch1 checked={copyTimeBlocking} onValueChange={setCopyTimeBlocking} />
                                        </Box>
                                    </Box>
                                    {/* copyTimePreference */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse time preferences (e.g., morning, afternoon) for similar events?</Text>
                                            <Switch1 checked={copyTimePreference} onValueChange={setCopyTimePreference} />
                                        </Box>
                                    </Box>
                                    {/* copyReminders */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse reminder settings for similar events?</Text>
                                            <Switch1 checked={copyReminders} onValueChange={setCopyReminders} />
                                        </Box>
                                    </Box>
                                    {/* copyPriorityLevel */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse priority levels for similar tasks/events?</Text>
                                            <Switch1 checked={copyPriorityLevel} onValueChange={setCopyPriorityLevel} />
                                        </Box>
                                    </Box>
                                    {/* copyModifiable */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse 'modifiable by assistant' setting for similar events?</Text>
                                            <Switch1 checked={copyModifiable} onValueChange={setCopyModifiable} />
                                        </Box>
                                    </Box>
                                    {/* copyCategories */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse tags/categories for similar events?</Text>
                                            <Switch1 checked={copyCategories} onValueChange={setCopyCategories} />
                                        </Box>
                                    </Box>
                                    {/* copyIsBreak */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Mark similar future events as breaks if original was a break?</Text>
                                            <Switch1 checked={copyIsBreak} onValueChange={setCopyIsBreak} />
                                        </Box>
                                    </Box>
                                    {/* copyIsMeeting */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Mark similar future events as meetings if original was a meeting?</Text>
                                            <Switch1 checked={copyIsMeeting} onValueChange={setCopyIsMeeting} />
                                        </Box>
                                    </Box>
                                    {/* copyIsExternalMeeting */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Mark similar as external meetings if original was external?</Text>
                                            <Switch1 checked={copyIsExternalMeeting} onValueChange={setCopyIsExternalMeeting} />
                                        </Box>
                                    </Box>
                                    {/* copyColor */}
                                    <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                                        <Box flexDirection="row" justifyContent="space-between" alignItems="center">
                                            <Text variant="optionHeader" style={{ flexShrink: 1, marginRight: 's' }}>Reuse event background color for similar new events?</Text>
                                            <Switch1 checked={copyColor} onValueChange={setCopyColor} />
                                        </Box>
                                    </Box>
                                </>
                            )}
                        </ScrollView>
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center" mt="m">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 7: // Previously 9 (Exit Message)
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                            <Text p={{ phone: 's', tablet: 'm' }} variant="subheader" textAlign="center">
                                You are almost done!
                            </Text>
                            <Text p={{ phone: 's', tablet: 'm' }} variant="optionHeader" textAlign="center">
                                Finalize your choices by pressing below.
                            </Text>
                            <Text p={{ phone: 's', tablet: 'm' }} variant="optionHeader" textAlign="center">
                                Atomic is now set up to intelligently assist you with scheduling, thanks to the preferences you&apos;ve provided!
                            </Text>
                            <Text p={{ phone: 's', tablet: 'm' }} variant="optionHeader" textAlign="center">
                                P.S. Once you&apos;re in, explore Task Management to track your to-dos and our built-in Chat for quick discussions!
                            </Text>
                            <Pressable onPress={completeOnboarding}>
                                <Text variant="buttonLink" textAlign="center">
                                    Complete Onboarding
                                </Text>
                            </Pressable>
                        </Box>
                        <Box p={{ phone: 's', tablet: 'm' }} flexDirection="row" justifyContent="flex-start" width="100%">
                            {renderPrevButton()}
                        </Box>
                    </Box>
                )
            
            default:
                return (
                    <Box justifyContent="center" alignItems="center">
                        <RegularCard>
                        <Text variant="header">
                            Oops... something went wrong
                        </Text>
                        </RegularCard>
                    </Box>
                )
        }
    }

    const darkMode = useColorScheme() === 'dark'

    if (loading) {
        return (
          <Box backgroundColor="primaryCardBackground" flex={1} justifyContent="center" alignItems="center" style={{ width: '100%'}} minHeight="80vh">
              <ActivityIndicator size="large" color={darkMode ? palette.textBlack : palette.white} />
          </Box>
          )
      }

    return (
        <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center" minHeight="70vh">
            <Wizard
                items={[
                    {
                        index: 0,
                        label: 'Welcome',
                    },
                    {
                        index: 1,
                        label: 'Integrations',
                    },
                    {
                        index: 2,
                        label: 'Calendar',
                    },
                    {
                        index: 3,
                        label: 'Tags',
                    },
                    {
                        index: 4,
                        label: 'Alarms',
                    },
                     {
                        index: 5,
                        label: 'Work Hours',
                    },
                     {
                        index: 6,
                        label: 'Event Defaults', // Consolidated step
                    },
                    {
                        index: 7, // Previously 9
                        label: 'All Done!',
                    },
                ]}

                completed={completedStep}
                activeIndex={activeIndex}
            />
            {renderCurrentStep()}
        </Box>
    )
}

export default UserOnBoard