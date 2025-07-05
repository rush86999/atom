/* eslint-disable react-hooks/exhaustive-deps */

import { useToast } from '@chakra-ui/react'
import Button from '@components/Button'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import { addMessageToBrain, createChatSocket, newSession, receiveMessageFromBrain } from '@lib/Chat/ChatHelper'
import { ChatHistoryType, SkillChatHistoryType, SkillMessageHistoryType } from '@lib/dataTypes/Messaging/MessagingTypes'
import { ReceiverTimezoneFormDataResponseType } from '@lib/dataTypes/Messaging/ReceiverTimezoneFormDataResponseType'
import { dayjs } from '@lib/date-utils'
import { formattedTimezones } from '@lib/GPT/MeetingRequest/constants'
import { TimezoneObjectType } from '@lib/GPT/MeetingRequest/types'
import { palette } from '@lib/theme/theme'
import { useAppContext } from '@lib/user-context'
import Session from "supertokens-web-js/recipe/session"
import { useRouter } from 'next/router'
import React, { useState, useEffect } from 'react'
import { IoIosCheckmark } from "react-icons/io"
import {
    Dimensions, Pressable, StyleSheet,
    FlatList, Modal, TouchableOpacity,
} from 'react-native'
import cls from 'classnames'
import ScrollContainer from '@components/chat/ScrollContainer'
import Message from '@components/chat/Message'
import ChatInput from '@components/chat/ChatInput'
import { checkIfCalendarWebhookExpired } from '@lib/calendarLib/googleCalendarHelper'
import { ObjectFieldType } from '@lib/dataTypes/Messaging/RequiredFieldsType'
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '../../../config/backendConfig'
import Session1 from 'supertokens-node/recipe/session'
import { getUserPreference } from '@lib/OnBoard/OnBoardHelper'

export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig())
  let session
  try {
    session = await Session1.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return []
      },
    })
  } catch (err: any) {
    if (err.type === Session1.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } }
    } else if (err.type === Session1.Error.UNAUTHORISED) {
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

const styles = {
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        width: '100%',
    },
    duration: {
        fontSize: '21px',
        lineHeight: '28px',
    },
   centeredView: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
       marginTop: 22,
       marginBottom: 22,
  } as any,
    modalView: {
      flex: 1,
    alignItems: "center",
  } as any,
}

let socket: WebSocket

function UserViewChat() {

    const [chatHistory, setChatHistory] = useState<ChatHistoryType | []>([{
        role: 'assistant',
        content: 'How can I help you today?',
        id: 0,
        date: dayjs().format(),
    }])
    const [messageHistory, setMessageHistory] = useState<SkillChatHistoryType | []>([{
        skill: 'pending',
        query: 'pending',
        messages: [],
    }])
    const [isNewSession, setIsNewSession] = useState<boolean>(false)
    const [isLoading, setIsLoading] = useState<boolean>(false)
    // const [token, setToken] = useState<string>('')
    // const [socket, setSocket] = useState<WebSocket>()
    const [formData, setFormData] = useState<ReceiverTimezoneFormDataResponseType>({
        type: 'select',
        value: dayjs.tz.guess(),
        name: dayjs.tz.guess(),
    })
    const [receiverTimezone, setReceiverTimezone] = useState<string>(dayjs.tz.guess())
    const [search, setSearch] = useState<string>('')
    const [isSelect, setIsSelect] = useState<boolean>(false)
    const [checkBoxArray, setCheckBoxArray] = useState<boolean[]>([])
    const [filteredTimezones, setFilteredTimezones] = useState<TimezoneObjectType[]>([])
    const [isForm, setIsForm] = useState<boolean>(false)
    const [reconnect, setReconnect] = useState<boolean>(false)
    const [htmlEmail, setHtmlEmail] = useState<string>('')

    // formattedTimezones: TimezoneObjectType[]

    const router = useRouter()
    const { sub, client } = useAppContext()
    const userId = sub
    const toast = useToast()
    const { dispatchAgentCommand } = useAgentAudioControl(); // Import from context


    // renew push notifictions
    useEffect(() => {
        if (userId) {
        (async () => checkIfCalendarWebhookExpired(client, userId))()
        }
        
    }, [client, userId])

    // check onboarding
    useEffect(() => {
        (async () => {
          if (!sub) {
              return
          }
          const user_preferenceDoc = await getUserPreference(client, sub)
          console.log(user_preferenceDoc?.onBoarded, ' user_preferenceDoc?.onBoarded')
          if (!user_preferenceDoc?.onBoarded) {
            console.log(' no user preference created')
            return router.push({ pathname: '/OnBoard/UserOnBoard'})
          }
            
        })()
      }, [client, router, sub])
    
    useEffect(() => {
        // This effect manages the WebSocket connection lifecycle.
        let currentSocketInstance: WebSocket | null = null;

        const connectAndSetupSocket = async () => {
            try {
                const access_token = await Session.getAccessToken();
                if (!access_token) {
                    console.warn("UserViewChat: No access token, WebSocket connection not attempted.");
                    return;
                }

                const newSocket = await createChatSocket(access_token);
                if (newSocket) {
                    socket = newSocket; // Assign to module-level variable (as per existing pattern)
                    currentSocketInstance = newSocket; // Local instance for this effect's cleanup
                    console.log("UserViewChat: WebSocket connection initiated.");
                    setReconnect(false);

                    newSocket.onopen = (event) => {
                        console.log("UserViewChat: WebSocket connection established.", event);
                    };

                    newSocket.onmessage = async (event) => {
                        console.log("UserViewChat: Raw message from server: ", event.data);
                        try {
                            const rawData = JSON.parse(event.data as string);

                            // TYPE GUARD for AgentAudioCommand
                            // Assuming AgentClientCommand has 'action' and 'command_id'
                            // and a wrapper type like { type: 'AGENT_COMMAND', payload: AgentAudioCommand }
                            if (rawData && rawData.type === 'AGENT_COMMAND' &&
                                rawData.payload && typeof rawData.payload.action === 'string' &&
                                typeof rawData.payload.command_id === 'string') {

                                const commandPayload = rawData.payload as AgentAudioCommand; // AgentAudioCommand needs to be imported or defined
                                console.log("UserViewChat: Received AGENT_COMMAND for audio:", commandPayload);
                                if (dispatchAgentCommand) {
                                    dispatchAgentCommand(commandPayload);
                                } else {
                                    console.error("UserViewChat: dispatchAgentCommand from AgentAudioControlContext is not available.");
                                }
                                return; // Command handled
                            }

                            if (rawData === 'ping') {
                                console.log("UserViewChat: Received ping.");
                                return;
                            }

                            // Process as SkillMessageHistoryType if not an AGENT_COMMAND
                            const skillMessageHistory: SkillMessageHistoryType = rawData;
                            if ((skillMessageHistory?.skill === 'generate-meeting-invite') || (skillMessageHistory?.skill === 'send-meeting-invite')) {
                                const requiredFormData = skillMessageHistory?.required?.dateTime.required?.find((r) => ((r as ObjectFieldType)?.value === 'receiverTimezone'));
                                if (requiredFormData) {
                                    setIsForm(true);
                                } else {
                                    setIsForm(false);
                                }
                            }
                            if (skillMessageHistory?.htmlEmail) {
                                setHtmlEmail(skillMessageHistory?.htmlEmail);
                            }
                            await onReceiveMessage(skillMessageHistory);

                        } catch (e) {
                            console.error("UserViewChat: Error processing message from server:", e, "Raw data:", event.data);
                        }
                    };

                    newSocket.onerror = (event: Event) => { // Using general Event type
                        console.error("UserViewChat: WebSocket error observed.", event);
                    };

                    newSocket.onclose = (event: CloseEvent) => {
                        console.log("UserViewChat: WebSocket connection closed.", event);
                        if (socket === currentSocketInstance) { // Avoid issues if a new socket was created by reconnect logic
                            socket = null;
                        }
                        // Optionally trigger reconnect logic here if needed, e.g., by setting `setReconnect(true)`
                        // if (!event.wasClean) { setReconnect(true); }
                    };

                } else {
                    console.error("UserViewChat: createChatSocket returned null or undefined.");
                }
            } catch (e) {
                console.error("UserViewChat: Error in connectAndSetupSocket:", e);
            }
        };

        if (sub) { // Only connect if user (sub) is available
            connectAndSetupSocket();
        }

        return () => {
            // Cleanup function
            if (currentSocketInstance) {
                console.log("UserViewChat: Cleaning up WebSocket instance.");
                currentSocketInstance.onopen = null;
                currentSocketInstance.onmessage = null;
                currentSocketInstance.onerror = null;
                currentSocketInstance.onclose = null;
                if (currentSocketInstance.readyState === WebSocket.OPEN || currentSocketInstance.readyState === WebSocket.CONNECTING) {
                    currentSocketInstance.close();
                }
                if (socket === currentSocketInstance) { // Ensure module-level var is also cleared if it's this instance
                    socket = null;
                }
            }
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [reconnect, isNewSession, sub, dispatchAgentCommand]); // Added sub and dispatchAgentCommand


    const onReceiveMessage = async (
        skillMessageHistory: SkillMessageHistoryType,
    ) => {
        try {
            await receiveMessageFromBrain(
                skillMessageHistory,
                chatHistory, 
                messageHistory,
                setChatHistory,
                setMessageHistory,
                setIsLoading,
            )
        } catch (e) {
            console.log(e, ' unable to receive message')
        }
    }

    // Removed direct socket.addEventListener calls as they are now handled within the useEffect's socket instance

    useEffect(() => {
        (() => {
            // generate checked array
            const newCheckedArray = formattedTimezones?.map(_ => false)

            setCheckBoxArray(newCheckedArray)
        })()
    }, [])

    const onSelectedItem = (index: number) => {
        // set selected checkbox
        const newCheckBoxArray = checkBoxArray?.map(_ => false)
        newCheckBoxArray[index] = true
        setCheckBoxArray(newCheckBoxArray)

        const selectedTimezone = formattedTimezones[index]
        setReceiverTimezone(selectedTimezone?.value)
        setFormData({
            type: 'select',
            value: selectedTimezone?.value,
            name: selectedTimezone?.label,
        })
    }

    const closeIsSelect = async () => {
        setIsSelect(false)
        await onSendMessage(formData?.value)
    }

    const openIsSelect = () => setIsSelect(true)
    
    const updateSearch = (text: string) => {
        setSearch(text)
        const regex = new RegExp(`\.*${text || ''}\.*`, 'gmi')
        const newFilteredArray = formattedTimezones?.filter(t => (regex.test(t?.label)))

        setFilteredTimezones(newFilteredArray)
    }

    type RenderItemType = {
        item: TimezoneObjectType,
        index: number,
    }

    const RenderItem = ({ item }: RenderItemType) => {
        const foundIndex = formattedTimezones?.findIndex(t => (t?.value === item?.value))

        return (
            <button onClick={() => onSelectedItem(foundIndex)} >
                <Box style={{ borderColor: palette.darkGray, borderBottomWidth: StyleSheet.hairlineWidth }} p={{ phone: 'm', tablet: 's' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                    <Box style={{ width: '70%'}}>
                        <Text variant="optionHeader">
                            {item?.label}
                        </Text>
                    </Box>
                    <Box style={{ width: '30%'}} pr={{ phone: 'l', tablet: 'm'}} flexDirection="row" justifyContent="flex-end" alignItems="center">
                        {checkBoxArray?.[foundIndex] ? <IoIosCheckmark size="3em" color={palette.pinkPrimary} /> : null}
                    </Box>
                </Box>
            </button>
        )
    }

    const callNewSession = () => {
        newSession(
            setChatHistory,
            setMessageHistory,
            setReconnect,
            reconnect,
        )

        setIsNewSession(false)
    }

    const onSendMessage = async (text: string) => {
        try {
            
            const index = messageHistory?.length === 0 ? 0 : messageHistory?.length - 1

            switch(messageHistory[index]?.skill) {
                case 'generate-meeting-invite':
                    messageHistory[index].formData = formData
                
                case 'send-meeting-invite':
                    messageHistory[index].formData = formData
            }
            

            console.log(text, ' text inside onSendMessage')
            // Add user's message to chat history immediately
            const newUserMessage: UserChatType = {
                id: chatHistory.length, // Or a more robust ID generation
                content: text,
                role: 'user',
                date: dayjs().format(),
            };
            setChatHistory(prevChatHistory => [...prevChatHistory, newUserMessage]);
            setIsLoading(true);

            try {
                const response = await fetch('/api/atom/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: text }),
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `API Error: ${response.status}`);
                }

                const data = await response.json(); // data is expected to be { text: string, audioUrl?: string, error?: string }

                let content = data.text;
                if (!content) {
                    if (data.error) {
                        content = `Error: ${data.error}`;
                    } else {
                        content = "Atom didn't provide a text response.";
                    }
                }

                const atomResponse: UserChatType = {
                    id: chatHistory.length + 1, // Or a more robust ID generation, consider uuid
                    content: data.text, // Default to data.text
                    role: 'assistant',
                    date: dayjs().format(),
                    audioUrl: data.audioUrl,
                };

                // Check for structured data from the agent
                if (data.structuredData && data.structuredData.displayType === 'semantic_search_results') {
                    atomResponse.customComponentType = 'semantic_search_results';
                    atomResponse.customComponentProps = { results: data.structuredData.data };
                    // Use summaryText from structuredData if available, otherwise keep original data.text
                    atomResponse.content = data.structuredData.summaryText || data.text;
                    console.log("UserViewChat: Populated customComponent for semantic_search_results", atomResponse);
                } else {
                    // Ensure content is set if no structuredData or not the expected type
                    atomResponse.content = content;
                }

                setChatHistory(prevChatHistory => [...prevChatHistory, atomResponse]);

            } catch (e: any) {
                console.error(e, ' unable to send message to Atom API');
                const errorMessage: UserChatType = {
                    id: chatHistory.length + 1,
                    content: `Error: ${e.message || 'Failed to get response from Atom.'}`,
                    role: 'assistant', // Display error as an assistant message
                    date: dayjs().format(),
                };
                setChatHistory(prevChatHistory => [...prevChatHistory, errorMessage]);
            } finally {
                setIsLoading(false);
            }
        } catch (e) {
            console.log(e, ' general error in onSendMessage')
            // Fallback for unexpected errors before API call attempt
             const errorMessage: UserChatType = {
                id: chatHistory.length + (chatHistory.find(m => m.role === 'user' && m.content === text) ? 1: 0), // avoid duplicate id if user message was added
                content: `An unexpected error occurred.`,
                role: 'assistant',
                date: dayjs().format(),
            };
            // Check if user message was already added to avoid duplicates if error is before API call
            setChatHistory(prevChatHistory => {
                if (!prevChatHistory.find(m => m.role === 'user' && m.content === text && m.id === newUserMessage.id)) {
                     return [...prevChatHistory, newUserMessage, errorMessage];
                }
                return [...prevChatHistory, errorMessage];
            });
            setIsLoading(false);
        }
    }


    const renderSelectTimezone = () => (
        <div>
            {isForm ?
                (
                    <Box justifyContent="flex-start" alignItems="center" style={{ width: '100%'}}>
                        <Text textAlign="center" p={{ phone: 's', tablet: 'm' }} variant="optionHeader" style={{ width: '80%'}}>
                            Select Receiver&apos;s timezone
                        </Text>
                        <Pressable onPress={openIsSelect}>
                            <Text textAlign="center" variant="buttonLink">
                                {receiverTimezone}
                            </Text>
                        </Pressable>
                    </Box>
                ) : null}
        </div>
    )

    return (
        <div className="flex flex-col items-center h-[60vh] bg-gray-500">
            <div className="bg-primary-content flex flex-col justify-center items-center w-full lg:w-1/2 h-full">
                
                <ScrollContainer scrollCta="New Message!" isNewSession={isNewSession} >
                    {
                        (chatHistory as ChatHistoryType)?.map((m, i) => {
                            // Determine if this message is the last one and an assistant message to potentially show loading/forms
                            const isLastMessage = (chatHistory.length - 1) === i;
                            const showFormsForThisMessage = isLastMessage && m.role === 'assistant';

                            return (
                                <div key={m.id || `msg-${i}`}> {/* Ensure key is always unique */}
                                    <Message
                                        key={m.id || `msg-item-${i}`}
                                        message={m}
                                        isLoading={showFormsForThisMessage && isLoading}
                                        // formData prop will be used for custom components like search results
                                        formData={
                                            m.customComponentType === 'semantic_search_results' && m.customComponentProps?.results ?
                                            // Dynamically import SearchResultsDisplay (will create this component next)
                                            // For now, a placeholder or simple rendering can be used if SearchResultsDisplay isn't ready
                                            // React.createElement(React.lazy(() => import('@components/chat/custom/SearchResultsDisplay')), m.customComponentProps)
                                            // Using a placeholder div for now until SemanticSearchResultsDisplay is created
                                            // This demonstrates where the custom component would go.
                                            // The actual import will be: React.createElement(React.lazy(() => import('@components/chat/custom/SemanticSearchResultsDisplay')), { results: m.customComponentProps.results })
                                             <div>Render SearchResultsDisplay here with results: {JSON.stringify(m.customComponentProps.results.length)} items</div>
                                            : (showFormsForThisMessage && isForm ? renderSelectTimezone() : undefined)
                                        }
                                        htmlEmail={showFormsForThisMessage && m.role === 'assistant' ? htmlEmail : undefined} // Only pass htmlEmail for assistant messages
                                    />
                                </div>
                            )
                        })
                    }
                </ScrollContainer>
                <ChatInput 
                    sendMessage={onSendMessage} 
                    // For Atom, isNewSession and callNewSession might not be directly applicable in the same way
                    // but we'll keep them for now to avoid breaking ChatInput's expected props.
                    // Consider how "new session" should behave with Atom later.
                    isNewSession={false} // Or manage this based on Atom's concept of sessions if any
                    callNewSession={() => {
                        console.log("New session clicked, behavior for Atom TBD");
                        // Potentially clear chatHistory for Atom or send a specific new session signal
                        // For now, let's just log it. A simple clear:
                        // setChatHistory([{ role: 'assistant', content: 'How can I help you today?', id:0, date: dayjs().format() }]);
                    }}
                />
                
            </div>
            {/* The Modal for timezone selection is part of the old system, hiding it for Atom for now by not rendering if isForm is false */}
            {isForm && (
            <Box>
                <Modal animationType="slide"
                    visible={isSelect} onRequestClose={closeIsSelect}>
                    <Box style={styles.centeredView}>
                        <Box style={styles.modalView}>
                            <form>   
                                <label htmlFor="default-search" className="mb-2 text-sm font-medium text-gray-900 sr-only dark:text-white">Search</label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                                        <svg aria-hidden="true" className="w-5 h-5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                    </div>
                                    <input value={search} onChange={(e) => updateSearch(e?.target?.value)} type="search" id="default-search" className="block w-full p-4 pl-10 text-sm text-gray-900 border border-gray-300 rounded-lg bg-gray-50 focus:ring-purple-500 focus:border-purple-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-purple-500 dark:focus:border-purple-500" placeholder="Type Timezone" required />
                                </div>
                            </form>
                            {filteredTimezones?.length > 0
                                ? (
                                    
                                        <FlatList
                                            data={filteredTimezones}
                                            keyExtractor={item => item.key}
                                            renderItem={RenderItem}
                                        />
                                   
                                )
                                : (
                                   
                                        <FlatList
                                            data={formattedTimezones}
                                            keyExtractor={item => item.key}
                                            renderItem={RenderItem}
                                        />
                                    
                                )
                            }
                            <Box>
                                <Button onClick={closeIsSelect}>
                                    Close
                                </Button>
                            </Box>
                        </Box>
                    </Box>
                </Modal>
            </Box>
            )}
        </div>
    )

}

export default UserViewChat


