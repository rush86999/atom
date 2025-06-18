import React, {
    useState,
    Dispatch,
    SetStateAction,
  } from 'react'

  import Switch1 from '@components/Switch'
  import Box from '@components/common/Box'
  import Text from '@components/common/Text'
  import { ScrollView } from 'react-native'
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

  type Props = {
    copyAvailability: boolean,
    copyTimeBlocking: boolean,
    copyTimePreference: boolean,
    copyReminders: boolean,
    copyPriorityLevel: boolean,
    copyModifiable: boolean,
    setParentCopyAvailability: Dispatch<SetStateAction<boolean>>,
    setParentCopyTimeBlocking: Dispatch<SetStateAction<boolean>>,
    setParentCopyTimePreference: Dispatch<SetStateAction<boolean>>,
    setParentCopyReminders: Dispatch<SetStateAction<boolean>>,
    setParentCopyPriorityLevel: Dispatch<SetStateAction<boolean>>,
    setParentCopyModifiable: Dispatch<SetStateAction<boolean>>,
  }
  
  function UserPreferenceForTimeBlockElements(props: Props) {
    const [copyAvailability, setCopyAvailability] = useState<boolean>(props?.copyAvailability)
    const [copyTimeBlocking, setCopyTimeBlocking] = useState<boolean>(props?.copyTimeBlocking)
    const [copyTimePreference, setCopyTimePreference] = useState<boolean>(props?.copyTimePreference)
    const [copyReminders, setCopyReminders] = useState<boolean>(props?.copyReminders)
    const [copyPriorityLevel, setCopyPriorityLevel] = useState<boolean>(props?.copyPriorityLevel)
    const [copyModifiable, setCopyModifiable] = useState<boolean>(props?.copyModifiable)
  
    const setParentCopyAvailability = props?.setParentCopyAvailability
    const setParentCopyTimeBlocking = props?.setParentCopyTimeBlocking
    const setParentCopyTimePreference = props?.setParentCopyTimePreference
    const setParentCopyReminders = props?.setParentCopyReminders
    const setParentCopyPriorityLevel = props?.setParentCopyPriorityLevel
    const setParentCopyModifiable = props?.setParentCopyModifiable
  
    const changeCopyAvailability = (value: boolean) => {
      setCopyAvailability(value)
      setParentCopyAvailability(value)
    }
  
    const changeCopyTimeBlocking = (value: boolean) => {
      setCopyTimeBlocking(value)
      setParentCopyTimeBlocking(value)
    }
  
    const changeCopyTimePreference = (value: boolean) => {
      setCopyTimePreference(value)
      setParentCopyTimePreference(value)
    }
  
    const changeCopyReminders = (value: boolean) => {
      setCopyReminders(value)
      setParentCopyReminders(value)
    }
  
    const changeCopyPriorityLevel = (value: boolean) => {
      setCopyPriorityLevel(value)
      setParentCopyPriorityLevel(value)
    }
  
    const changeCopyModifiable = (value: boolean) => {
      setCopyModifiable(value)
      setParentCopyModifiable(value)
    }
  
    return (
      <Box flex={1} justifyContent="center" alignItems="center">
        <Box p="m" width="90%" alignItems="center">
            <Text textAlign="center" variant="optionHeader">
                Automate your event creation! These settings let Atomic learn your preferences for similar events, saving you time.
            </Text>
        </Box>
        <ScrollView style={{ width: '100%' }} contentContainerStyle={{ width: '100%', justifyContent: 'center', alignItems: 'center' }}>
          <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
            <Box flexDirection="row" justifyContent="flex-start" alignItems="center">   
              <Text variant="optionHeader">Automatically copy event transparency (free/busy status) for similar new events?</Text>
            </Box>
            <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}>
              <Switch1
                  checked={copyAvailability}
                  onValueChange={changeCopyAvailability}
                  style={{marginBottom: 20}}
              />
            </Box>
          </Box>
          <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
            <Box style={{ width: '100%' }} flexDirection="row" justifyContent="flex-start" alignItems="center">  
              <Text variant="optionHeader">Automatically copy buffer times (before/after event) for similar new events?</Text>
            </Box>
            <Box style={{ width: '100%' }} flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}>
                <Switch1
                    
                    
                    checked={copyTimeBlocking}
                    onValueChange={changeCopyTimeBlocking}
                    style={{ marginBottom: 20 }}
                />
            </Box>
          </Box>
          <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
            <Box style={{ width: '100%' }} flexDirection="row" justifyContent="flex-start" alignItems="center">
              <Text variant="optionHeader">Automatically copy reminders for similar new events?</Text>
            </Box>
            <Box style={{ width: '100%' }} flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}>
                <Switch1
                    
                    
                    checked={copyReminders}
                    onValueChange={changeCopyReminders} 
                    style={{ marginBottom: 20 }}
                />  
            </Box>
          </Box>
        </ScrollView>
      </Box>
    )
  }
  
  export default UserPreferenceForTimeBlockElements
  
  
  