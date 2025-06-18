import React, {
    useState,
    Dispatch,
    SetStateAction,
  } from 'react'

import Switch1 from '@components/Switch'
import TextField from '@components/TextField'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
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
      copyCategories: boolean,
      copyIsBreak: boolean,
      maxWorkLoadPercent: number,
      minNumberOfBreaks: number,
      breakLength: number,
      setParentCopyCategories: Dispatch<SetStateAction<boolean>>,
      setParentCopyIsBreak: Dispatch<SetStateAction<boolean>>,
      setParentMaxWorkLoadPercent: Dispatch<SetStateAction<number>>,
      setParentMinNumberOfBreaks: Dispatch<SetStateAction<number>>,
      setParentBreakLength: Dispatch<SetStateAction<number>>,
  }
  
  function UserPreferenceForTimeBlockElements2(props: Props) {
      const [copyCategories, setCopyCategories] = useState<boolean>(props?.copyCategories)
      const [copyIsBreak, setCopyIsBreak] = useState<boolean>(props?.copyIsBreak)
      const [maxWorkLoadPercent, setMaxWorkLoadPercent] = useState<number>(props?.maxWorkLoadPercent)
      const [minNumberOfBreaks, setMinNumberOfBreaks] = useState<number>(props?.minNumberOfBreaks)
      const [breakLength, setBreakLength] = useState<number>(props?.breakLength)
  
      const setParentCopyCategories = props?.setParentCopyCategories
      const setParentCopyIsBreak = props?.setParentCopyIsBreak
      const setParentMaxWorkLoadPercent = props?.setParentMaxWorkLoadPercent
      const setParentMinNumberOfBreaks = props?.setParentMinNumberOfBreaks
      const setParentBreakLength = props?.setParentBreakLength
  
      const changeCopyCategories = (value: boolean) => {
          setCopyCategories(value)
          setParentCopyCategories(value)
      }
  
      const changeCopyIsBreak = (value: boolean) => {
          setCopyIsBreak(value)
          setParentCopyIsBreak(value)
      }
  
      const changeMaxWorkLoadPercent = (value: number) => {
          setMaxWorkLoadPercent(value)
          setParentMaxWorkLoadPercent(value)
      }
  
      const changeMinNumberOfBreaks = (value: number) => {
          setMinNumberOfBreaks(value)
          setParentMinNumberOfBreaks(value)
      }
  
      const changeBreakLength = (value: number) => {
          setBreakLength(value)
          setParentBreakLength(value)
      }
  
      return (
        <Box justifyContent="center" alignItems="center">
            <Box p="m" width="90%" alignItems="center">
                <Text textAlign="center" variant="optionHeader">
                    Fine-tune how Atomic helps manage your schedule and well-being. These settings improve scheduling suggestions.
                </Text>
            </Box>
            <Box justifyContent="center" alignItems="flex-start" minHeight="70vh">
                <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                    <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}>  
                        <Text variant="optionHeader">Automatically copy tags for similar new events?</Text>
                    </Box>
                    <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                        <Switch1
                            checked={copyCategories}
                            onValueChange={changeCopyCategories}
                            style={{ marginBottom: 20 }}
                        />
                    </Box>
                </Box>
                <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                    <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}>   
                        <Text variant="optionHeader">If an event is a break, automatically mark similar new events as breaks for smarter scheduling?</Text>
                    </Box>
                    <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                        <Switch1
                            checked={copyIsBreak}
                            onValueChange={changeCopyIsBreak}
                            style={{ marginBottom: 20 }}
                        />
                    </Box>
                </Box>
                <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                    <Box flexDirection="row" justifyContent="flex-start" alignItems="center" style={{ width: '100%' }}> 
                        <Text variant="optionHeader">
                            Maximum daily workload percentage for scheduling assistance:
                        </Text>
                    </Box>
                    <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                        <TextField
                            type="number"
                            onChange={(e: { target: { value: string } }) => changeMaxWorkLoadPercent(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                            value={`${maxWorkLoadPercent}`}
                            placeholder="0"
                            trailingAccessory={(<Text pl={{ phone: 's', tablet: 'm' }} variant="cardTitle">%</Text>)}
                        />
                        
                    </Box>
                </Box>
                <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                    <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}>
                        <Text variant="optionHeader">
                            Minimum number of daily breaks for scheduling assistance:
                        </Text>
                    </Box>
                    <Box flexDirection="row" justifyContent="flex-end"  style={{ width: '100%' }}>
                        <TextField
                            type="number"
                            onChange={(e: { target: { value: string } }) => changeMinNumberOfBreaks(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                            value={`${minNumberOfBreaks}`}
                            placeholder="0"
                            
                        />
                    </Box>  
                </Box>
                <Box flex={1} style={{ width: '90%' }} p={{ phone: 's', tablet: 'm' }}>
                    <Box flexDirection="row" justifyContent="flex-start" alignItems="center"  style={{ width: '100%' }}> 
                        <Text variant="optionHeader">
                            Default break length (in minutes) for scheduling assistance:
                        </Text>
                    </Box>
                    <Box flexDirection="row" justifyContent="flex-end" pt={{ phone: 'm', tablet: 's' }}  style={{ width: '100%' }}>
                        <TextField
                            type="number"
                            onChange={(e: { target: { value: string } }) => changeBreakLength(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10))}
                            value={`${breakLength}`}
                            placeholder="0"
                            trailingAccessory={(<Text pl={{ phone: 's', tablet: 'm' }} variant="cardTitle">minutes</Text>)}
                        />
                        
                    </Box>
                </Box>
            </Box>
        </Box>
      )
  }
  
  export default UserPreferenceForTimeBlockElements2
  