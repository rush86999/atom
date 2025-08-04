"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.receiveMessageFromBrain = exports.addMessageToBrain = exports.sendMessage = exports.newSession = exports.createChatSocket = void 0;
const date_utils_1 = require("@lib/date-utils");
const constants_1 = require("./constants");
const qs_1 = __importDefault(require("qs"));
const uuid_1 = require("uuid");
const createChatSocket = async (token) => {
    try {
        const socket = new WebSocket(`${constants_1.chatWSAPIUrl}?${qs_1.default.stringify({ Auth: `Bearer ${token}` })}`);
        return socket;
    }
    catch (e) {
        console.log(e, ' unable to create client');
    }
};
exports.createChatSocket = createChatSocket;
const newSession = (setChatHistory, setMessageHistory, setReconnect, reconnect) => {
    setChatHistory([
        {
            role: 'assistant',
            content: 'How can I help you today?',
            id: 0,
            date: (0, date_utils_1.dayjs)().format(),
        },
    ]);
    setMessageHistory([
        {
            skill: 'pending',
            query: 'pending',
            messages: [],
        },
    ]);
    setReconnect(!reconnect);
};
exports.newSession = newSession;
const sendMessage = async (socket, body) => {
    try {
        socket.send(JSON.stringify(body));
    }
    catch (e) {
        console.log(e, ' unable to send message');
    }
};
exports.sendMessage = sendMessage;
const addMessageToBrain = async (socket, userMessage, userId, timezone, chatHistory, messageHistory, setChatHistory, setMessageHistory, setIsLoading) => {
    console.log(chatHistory, ' chatHistory inside addNewQuestion');
    const newChatHistory = (chatHistory || [])?.concat([
        {
            role: 'user',
            content: userMessage,
            id: chatHistory?.length, // old length so matche index
            date: (0, date_utils_1.dayjs)().format(),
        },
    ]);
    try {
        console.log(newChatHistory, ' newChatHistory inside addNewQuestion');
        const newChatHistory2 = (newChatHistory || [])?.concat([
            {
                role: 'assistant',
                content: 'working ...',
                id: newChatHistory?.length,
                date: (0, date_utils_1.dayjs)().format(),
            },
        ]);
        console.log(newChatHistory2, ' newChatHistory2 inside addNewQuestion');
        setChatHistory(newChatHistory2);
        setIsLoading(true);
        /**{
        skill: SkillType,
        messages: MessageHistoryType,
        query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending' | 'error',
        required?: RequiredFieldsType,
        formData?: ReceiverTimezoneFormDataResponseType,
        prevData?: any,
        prevDataExtra?: any,
    }
     */ const index = messageHistory?.length === 0 ? 0 : messageHistory?.length - 1;
        const newMessage = {
            ...messageHistory?.[index],
            messages: [
                ...messageHistory?.[index]?.messages,
                { role: 'user', content: userMessage },
            ],
        };
        const body = {
            chat: newMessage,
            userId,
            timezone,
            id: (0, uuid_1.v4)(),
        };
        await (0, exports.sendMessage)(socket, body);
        const newMessageHistory = messageHistory.concat([newMessage]);
        setMessageHistory(newMessageHistory);
    }
    catch (e) {
        console.log(e, ' unable to add message to brain');
    }
};
exports.addMessageToBrain = addMessageToBrain;
const receiveMessageFromBrain = async (skillDataForLog, // Renamed to reflect its purpose for logging
messageHistory, setMessageHistory
// setChatHistory and setIsLoading are removed as they are handled by the caller (UserViewChat.tsx)
) => {
    try {
        // This function now *only* updates messageHistory (the skill log).
        // It does not construct or set the visual chat messages in chatHistory.
        // The existing switch logic was mainly for updating chatHistory's "working..." message
        // and then setting messageHistory.
        // Since chatHistory is handled by the caller, we simplify this.
        // We need to decide how to update messageHistory based on skillDataForLog.
        // The old logic replaced the last item in messageHistory if it was 'pending'
        // and then added a new 'pending' item if the query was 'completed' or 'event_not_found'.
        let updatedMessageHistory = [...messageHistory];
        if (skillDataForLog.query === 'missing_fields') {
            // Replace the last 'pending' message in messageHistory with the new skillDataForLog
            if (updatedMessageHistory.length > 0 &&
                updatedMessageHistory[updatedMessageHistory.length - 1].query ===
                    'pending') {
                updatedMessageHistory[updatedMessageHistory.length - 1] =
                    skillDataForLog;
            }
            else {
                // This case should ideally not happen if addMessageToBrain correctly sets up a pending state.
                updatedMessageHistory.push(skillDataForLog);
            }
            setMessageHistory(updatedMessageHistory);
        }
        else if (skillDataForLog.query === 'completed' ||
            skillDataForLog.query === 'event_not_found' ||
            skillDataForLog.query === 'error') {
            // Replace the last 'pending' message and add a new 'pending' state for the next interaction.
            if (updatedMessageHistory.length > 0 &&
                updatedMessageHistory[updatedMessageHistory.length - 1].query ===
                    'pending') {
                updatedMessageHistory[updatedMessageHistory.length - 1] =
                    skillDataForLog;
            }
            else {
                updatedMessageHistory.push(skillDataForLog);
            }
            // Add a new pending state for the next turn
            updatedMessageHistory.push({
                skill: 'pending',
                query: 'pending',
                messages: [],
            });
            setMessageHistory(updatedMessageHistory);
        }
        else if (skillDataForLog.query === 'pending') {
            // If the incoming data itself is 'pending' (e.g. an ack), update the last item.
            // This might happen if the agent sends multiple updates for a single turn.
            if (updatedMessageHistory.length > 0) {
                updatedMessageHistory[updatedMessageHistory.length - 1] =
                    skillDataForLog;
                setMessageHistory(updatedMessageHistory);
            }
            else {
                setMessageHistory([skillDataForLog]);
            }
        }
        else {
            // Default behavior: just append if the query state is unknown or doesn't fit above.
            // This ensures the log captures it.
            console.warn('receiveMessageFromBrain: Unhandled skillDataForLog.query state:', skillDataForLog.query, 'Appending to log.');
            setMessageHistory([...updatedMessageHistory, skillDataForLog]);
        }
        // setIsLoading(false) is now handled by the caller (UserViewChat.tsx)
    }
    catch (e) {
        console.log(e, ' unabl eto receive message from brain');
    }
};
exports.receiveMessageFromBrain = receiveMessageFromBrain;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2hhdEhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkNoYXRIZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBTUEsZ0RBQXdDO0FBRXhDLDJDQUEyQztBQUMzQyw0Q0FBb0I7QUFDcEIsK0JBQWtDO0FBRTNCLE1BQU0sZ0JBQWdCLEdBQUcsS0FBSyxFQUFFLEtBQWEsRUFBRSxFQUFFO0lBQ3RELElBQUksQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFHLElBQUksU0FBUyxDQUMxQixHQUFHLHdCQUFZLElBQUksWUFBRSxDQUFDLFNBQVMsQ0FBQyxFQUFFLElBQUksRUFBRSxVQUFVLEtBQUssRUFBRSxFQUFFLENBQUMsRUFBRSxDQUMvRCxDQUFDO1FBQ0YsT0FBTyxNQUFNLENBQUM7SUFDaEIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwwQkFBMEIsQ0FBQyxDQUFDO0lBQzdDLENBQUM7QUFDSCxDQUFDLENBQUM7QUFUVyxRQUFBLGdCQUFnQixvQkFTM0I7QUFFSyxNQUFNLFVBQVUsR0FBRyxDQUN4QixjQUEwRSxFQUMxRSxpQkFFQyxFQUNELFlBQTJELEVBQzNELFNBQWtCLEVBQ2xCLEVBQUU7SUFDRixjQUFjLENBQUM7UUFDYjtZQUNFLElBQUksRUFBRSxXQUFXO1lBQ2pCLE9BQU8sRUFBRSwyQkFBMkI7WUFDcEMsRUFBRSxFQUFFLENBQUM7WUFDTCxJQUFJLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1NBQ3ZCO0tBQ0YsQ0FBQyxDQUFDO0lBQ0gsaUJBQWlCLENBQUM7UUFDaEI7WUFDRSxLQUFLLEVBQUUsU0FBUztZQUNoQixLQUFLLEVBQUUsU0FBUztZQUNoQixRQUFRLEVBQUUsRUFBRTtTQUNiO0tBQ0YsQ0FBQyxDQUFDO0lBQ0gsWUFBWSxDQUFDLENBQUMsU0FBUyxDQUFDLENBQUM7QUFDM0IsQ0FBQyxDQUFDO0FBeEJX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QUFDO0lBQzFELENBQUM7QUFDSCxDQUFDLENBQUM7QUFwRlcsUUFBQSx1QkFBdUIsMkJBb0ZsQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIENoYXRCcmFpbkJvZHlUeXBlLFxuICBDaGF0SGlzdG9yeVR5cGUsXG4gIFNraWxsQ2hhdEhpc3RvcnlUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQgeyBjaGF0V1NBUElVcmwgfSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgcXMgZnJvbSAncXMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuXG5leHBvcnQgY29uc3QgY3JlYXRlQ2hhdFNvY2tldCA9IGFzeW5jICh0b2tlbjogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgc29ja2V0ID0gbmV3IFdlYlNvY2tldChcbiAgICAgIGAke2NoYXRXU0FQSVVybH0/JHtxcy5zdHJpbmdpZnkoeyBBdXRoOiBgQmVhcmVyICR7dG9rZW59YCB9KX1gXG4gICAgKTtcbiAgICByZXR1cm4gc29ja2V0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIGNsaWVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbmV3U2Vzc2lvbiA9IChcbiAgc2V0Q2hhdEhpc3Rvcnk6IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPENoYXRIaXN0b3J5VHlwZSB8IFtdPj4sXG4gIHNldE1lc3NhZ2VIaXN0b3J5OiBSZWFjdC5EaXNwYXRjaDxcbiAgICBSZWFjdC5TZXRTdGF0ZUFjdGlvbjxbXSB8IFNraWxsQ2hhdEhpc3RvcnlUeXBlPlxuICA+LFxuICBzZXRSZWNvbm5lY3Q6IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPGJvb2xlYW4+PixcbiAgcmVjb25uZWN0OiBib29sZWFuXG4pID0+IHtcbiAgc2V0Q2hhdEhpc3RvcnkoW1xuICAgIHtcbiAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgY29udGVudDogJ0hvdyBjYW4gSSBoZWxwIHlvdSB0b2RheT8nLFxuICAgICAgaWQ6IDAsXG4gICAgICBkYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIH0sXG4gIF0pO1xuICBzZXRNZXNzYWdlSGlzdG9yeShbXG4gICAge1xuICAgICAgc2tpbGw6ICdwZW5kaW5nJyxcbiAgICAgIHF1ZXJ5OiAncGVuZGluZycsXG4gICAgICBtZXNzYWdlczogW10sXG4gICAgfSxcbiAgXSk7XG4gIHNldFJlY29ubmVjdCghcmVjb25uZWN0KTtcbn07XG5cbmV4cG9ydCBjb25zdCBzZW5kTWVzc2FnZSA9IGFzeW5jIChcbiAgc29ja2V0OiBXZWJTb2NrZXQsXG4gIGJvZHk6IENoYXRCcmFpbkJvZHlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBzb2NrZXQuc2VuZChKU09OLnN0cmluZ2lmeShib2R5KSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzZW5kIG1lc3NhZ2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGFkZE1lc3NhZ2VUb0JyYWluID0gYXN5bmMgKFxuICBzb2NrZXQ6IFdlYlNvY2tldCxcbiAgdXNlck1lc3NhZ2U6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGNoYXRIaXN0b3J5OiBDaGF0SGlzdG9yeVR5cGUsXG4gIG1lc3NhZ2VIaXN0b3J5OiBTa2lsbENoYXRIaXN0b3J5VHlwZSxcbiAgc2V0Q2hhdEhpc3Rvcnk6IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPENoYXRIaXN0b3J5VHlwZSB8IFtdPj4sXG4gIHNldE1lc3NhZ2VIaXN0b3J5OiBSZWFjdC5EaXNwYXRjaDxcbiAgICBSZWFjdC5TZXRTdGF0ZUFjdGlvbjxbXSB8IFNraWxsQ2hhdEhpc3RvcnlUeXBlPlxuICA+LFxuICBzZXRJc0xvYWRpbmc6IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPGJvb2xlYW4+PlxuKSA9PiB7XG4gIGNvbnNvbGUubG9nKGNoYXRIaXN0b3J5LCAnIGNoYXRIaXN0b3J5IGluc2lkZSBhZGROZXdRdWVzdGlvbicpO1xuICBjb25zdCBuZXdDaGF0SGlzdG9yeSA9IChjaGF0SGlzdG9yeSB8fCBbXSk/LmNvbmNhdChbXG4gICAge1xuICAgICAgcm9sZTogJ3VzZXInLFxuICAgICAgY29udGVudDogdXNlck1lc3NhZ2UsXG4gICAgICBpZDogY2hhdEhpc3Rvcnk/Lmxlbmd0aCwgLy8gb2xkIGxlbmd0aCBzbyBtYXRjaGUgaW5kZXhcbiAgICAgIGRhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgfSxcbiAgXSk7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2cobmV3Q2hhdEhpc3RvcnksICcgbmV3Q2hhdEhpc3RvcnkgaW5zaWRlIGFkZE5ld1F1ZXN0aW9uJyk7XG4gICAgY29uc3QgbmV3Q2hhdEhpc3RvcnkyID0gKG5ld0NoYXRIaXN0b3J5IHx8IFtdKT8uY29uY2F0KFtcbiAgICAgIHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6ICd3b3JraW5nIC4uLicsXG4gICAgICAgIGlkOiBuZXdDaGF0SGlzdG9yeT8ubGVuZ3RoLFxuICAgICAgICBkYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgfSxcbiAgICBdKTtcblxuICAgIGNvbnNvbGUubG9nKG5ld0NoYXRIaXN0b3J5MiwgJyBuZXdDaGF0SGlzdG9yeTIgaW5zaWRlIGFkZE5ld1F1ZXN0aW9uJyk7XG5cbiAgICBzZXRDaGF0SGlzdG9yeShuZXdDaGF0SGlzdG9yeTIpO1xuXG4gICAgc2V0SXNMb2FkaW5nKHRydWUpO1xuXG4gICAgLyoqe1xuICAgIHNraWxsOiBTa2lsbFR5cGUsXG4gICAgbWVzc2FnZXM6IE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZycgfCAnZXJyb3InLFxuICAgIHJlcXVpcmVkPzogUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgIGZvcm1EYXRhPzogUmVjZWl2ZXJUaW1lem9uZUZvcm1EYXRhUmVzcG9uc2VUeXBlLFxuICAgIHByZXZEYXRhPzogYW55LFxuICAgIHByZXZEYXRhRXh0cmE/OiBhbnksXG59XG4gKi8gY29uc3QgaW5kZXggPSBtZXNzYWdlSGlzdG9yeT8ubGVuZ3RoID09PSAwID8gMCA6IG1lc3NhZ2VIaXN0b3J5Py5sZW5ndGggLSAxO1xuICAgIGNvbnN0IG5ld01lc3NhZ2U6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3Rvcnk/LltpbmRleF0sXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICAuLi5tZXNzYWdlSGlzdG9yeT8uW2luZGV4XT8ubWVzc2FnZXMsXG4gICAgICAgIHsgcm9sZTogJ3VzZXInLCBjb250ZW50OiB1c2VyTWVzc2FnZSB9LFxuICAgICAgXSxcbiAgICB9O1xuICAgIGNvbnN0IGJvZHk6IENoYXRCcmFpbkJvZHlUeXBlID0ge1xuICAgICAgY2hhdDogbmV3TWVzc2FnZSxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgaWQ6IHV1aWQoKSxcbiAgICB9O1xuXG4gICAgYXdhaXQgc2VuZE1lc3NhZ2Uoc29ja2V0LCBib2R5KTtcblxuICAgIGNvbnN0IG5ld01lc3NhZ2VIaXN0b3J5ID0gbWVzc2FnZUhpc3RvcnkuY29uY2F0KFtuZXdNZXNzYWdlXSk7XG5cbiAgICBzZXRNZXNzYWdlSGlzdG9yeShuZXdNZXNzYWdlSGlzdG9yeSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBhZGQgbWVzc2FnZSB0byBicmFpbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcmVjZWl2ZU1lc3NhZ2VGcm9tQnJhaW4gPSBhc3luYyAoXG4gIHNraWxsRGF0YUZvckxvZzogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsIC8vIFJlbmFtZWQgdG8gcmVmbGVjdCBpdHMgcHVycG9zZSBmb3IgbG9nZ2luZ1xuICBtZXNzYWdlSGlzdG9yeTogU2tpbGxDaGF0SGlzdG9yeVR5cGUsXG4gIHNldE1lc3NhZ2VIaXN0b3J5OiBSZWFjdC5EaXNwYXRjaDxcbiAgICBSZWFjdC5TZXRTdGF0ZUFjdGlvbjxbXSB8IFNraWxsQ2hhdEhpc3RvcnlUeXBlPlxuICA+XG4gIC8vIHNldENoYXRIaXN0b3J5IGFuZCBzZXRJc0xvYWRpbmcgYXJlIHJlbW92ZWQgYXMgdGhleSBhcmUgaGFuZGxlZCBieSB0aGUgY2FsbGVyIChVc2VyVmlld0NoYXQudHN4KVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gVGhpcyBmdW5jdGlvbiBub3cgKm9ubHkqIHVwZGF0ZXMgbWVzc2FnZUhpc3RvcnkgKHRoZSBza2lsbCBsb2cpLlxuICAgIC8vIEl0IGRvZXMgbm90IGNvbnN0cnVjdCBvciBzZXQgdGhlIHZpc3VhbCBjaGF0IG1lc3NhZ2VzIGluIGNoYXRIaXN0b3J5LlxuXG4gICAgLy8gVGhlIGV4aXN0aW5nIHN3aXRjaCBsb2dpYyB3YXMgbWFpbmx5IGZvciB1cGRhdGluZyBjaGF0SGlzdG9yeSdzIFwid29ya2luZy4uLlwiIG1lc3NhZ2VcbiAgICAvLyBhbmQgdGhlbiBzZXR0aW5nIG1lc3NhZ2VIaXN0b3J5LlxuICAgIC8vIFNpbmNlIGNoYXRIaXN0b3J5IGlzIGhhbmRsZWQgYnkgdGhlIGNhbGxlciwgd2Ugc2ltcGxpZnkgdGhpcy5cblxuICAgIC8vIFdlIG5lZWQgdG8gZGVjaWRlIGhvdyB0byB1cGRhdGUgbWVzc2FnZUhpc3RvcnkgYmFzZWQgb24gc2tpbGxEYXRhRm9yTG9nLlxuICAgIC8vIFRoZSBvbGQgbG9naWMgcmVwbGFjZWQgdGhlIGxhc3QgaXRlbSBpbiBtZXNzYWdlSGlzdG9yeSBpZiBpdCB3YXMgJ3BlbmRpbmcnXG4gICAgLy8gYW5kIHRoZW4gYWRkZWQgYSBuZXcgJ3BlbmRpbmcnIGl0ZW0gaWYgdGhlIHF1ZXJ5IHdhcyAnY29tcGxldGVkJyBvciAnZXZlbnRfbm90X2ZvdW5kJy5cblxuICAgIGxldCB1cGRhdGVkTWVzc2FnZUhpc3RvcnkgPSBbLi4ubWVzc2FnZUhpc3RvcnldO1xuXG4gICAgaWYgKHNraWxsRGF0YUZvckxvZy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgLy8gUmVwbGFjZSB0aGUgbGFzdCAncGVuZGluZycgbWVzc2FnZSBpbiBtZXNzYWdlSGlzdG9yeSB3aXRoIHRoZSBuZXcgc2tpbGxEYXRhRm9yTG9nXG4gICAgICBpZiAoXG4gICAgICAgIHVwZGF0ZWRNZXNzYWdlSGlzdG9yeS5sZW5ndGggPiAwICYmXG4gICAgICAgIHVwZGF0ZWRNZXNzYWdlSGlzdG9yeVt1cGRhdGVkTWVzc2FnZUhpc3RvcnkubGVuZ3RoIC0gMV0ucXVlcnkgPT09XG4gICAgICAgICAgJ3BlbmRpbmcnXG4gICAgICApIHtcbiAgICAgICAgdXBkYXRlZE1lc3NhZ2VIaXN0b3J5W3VwZGF0ZWRNZXNzYWdlSGlzdG9yeS5sZW5ndGggLSAxXSA9XG4gICAgICAgICAgc2tpbGxEYXRhRm9yTG9nO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgLy8gVGhpcyBjYXNlIHNob3VsZCBpZGVhbGx5IG5vdCBoYXBwZW4gaWYgYWRkTWVzc2FnZVRvQnJhaW4gY29ycmVjdGx5IHNldHMgdXAgYSBwZW5kaW5nIHN0YXRlLlxuICAgICAgICB1cGRhdGVkTWVzc2FnZUhpc3RvcnkucHVzaChza2lsbERhdGFGb3JMb2cpO1xuICAgICAgfVxuICAgICAgc2V0TWVzc2FnZUhpc3RvcnkodXBkYXRlZE1lc3NhZ2VIaXN0b3J5KTtcbiAgICB9IGVsc2UgaWYgKFxuICAgICAgc2tpbGxEYXRhRm9yTG9nLnF1ZXJ5ID09PSAnY29tcGxldGVkJyB8fFxuICAgICAgc2tpbGxEYXRhRm9yTG9nLnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJyB8fFxuICAgICAgc2tpbGxEYXRhRm9yTG9nLnF1ZXJ5ID09PSAnZXJyb3InXG4gICAgKSB7XG4gICAgICAvLyBSZXBsYWNlIHRoZSBsYXN0ICdwZW5kaW5nJyBtZXNzYWdlIGFuZCBhZGQgYSBuZXcgJ3BlbmRpbmcnIHN0YXRlIGZvciB0aGUgbmV4dCBpbnRlcmFjdGlvbi5cbiAgICAgIGlmIChcbiAgICAgICAgdXBkYXRlZE1lc3NhZ2VIaXN0b3J5Lmxlbmd0aCA+IDAgJiZcbiAgICAgICAgdXBkYXRlZE1lc3NhZ2VIaXN0b3J5W3VwZGF0ZWRNZXNzYWdlSGlzdG9yeS5sZW5ndGggLSAxXS5xdWVyeSA9PT1cbiAgICAgICAgICAncGVuZGluZydcbiAgICAgICkge1xuICAgICAgICB1cGRhdGVkTWVzc2FnZUhpc3RvcnlbdXBkYXRlZE1lc3NhZ2VIaXN0b3J5Lmxlbmd0aCAtIDFdID1cbiAgICAgICAgICBza2lsbERhdGFGb3JMb2c7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB1cGRhdGVkTWVzc2FnZUhpc3RvcnkucHVzaChza2lsbERhdGFGb3JMb2cpO1xuICAgICAgfVxuICAgICAgLy8gQWRkIGEgbmV3IHBlbmRpbmcgc3RhdGUgZm9yIHRoZSBuZXh0IHR1cm5cbiAgICAgIHVwZGF0ZWRNZXNzYWdlSGlzdG9yeS5wdXNoKHtcbiAgICAgICAgc2tpbGw6ICdwZW5kaW5nJyxcbiAgICAgICAgcXVlcnk6ICdwZW5kaW5nJyxcbiAgICAgICAgbWVzc2FnZXM6IFtdLFxuICAgICAgfSk7XG4gICAgICBzZXRNZXNzYWdlSGlzdG9yeSh1cGRhdGVkTWVzc2FnZUhpc3RvcnkpO1xuICAgIH0gZWxzZSBpZiAoc2tpbGxEYXRhRm9yTG9nLnF1ZXJ5ID09PSAncGVuZGluZycpIHtcbiAgICAgIC8vIElmIHRoZSBpbmNvbWluZyBkYXRhIGl0c2VsZiBpcyAncGVuZGluZycgKGUuZy4gYW4gYWNrKSwgdXBkYXRlIHRoZSBsYXN0IGl0ZW0uXG4gICAgICAvLyBUaGlzIG1pZ2h0IGhhcHBlbiBpZiB0aGUgYWdlbnQgc2VuZHMgbXVsdGlwbGUgdXBkYXRlcyBmb3IgYSBzaW5nbGUgdHVybi5cbiAgICAgIGlmICh1cGRhdGVkTWVzc2FnZUhpc3RvcnkubGVuZ3RoID4gMCkge1xuICAgICAgICB1cGRhdGVkTWVzc2FnZUhpc3RvcnlbdXBkYXRlZE1lc3NhZ2VIaXN0b3J5Lmxlbmd0aCAtIDFdID1cbiAgICAgICAgICBza2lsbERhdGFGb3JMb2c7XG4gICAgICAgIHNldE1lc3NhZ2VIaXN0b3J5KHVwZGF0ZWRNZXNzYWdlSGlzdG9yeSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzZXRNZXNzYWdlSGlzdG9yeShbc2tpbGxEYXRhRm9yTG9nXSk7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIERlZmF1bHQgYmVoYXZpb3I6IGp1c3QgYXBwZW5kIGlmIHRoZSBxdWVyeSBzdGF0ZSBpcyB1bmtub3duIG9yIGRvZXNuJ3QgZml0IGFib3ZlLlxuICAgICAgLy8gVGhpcyBlbnN1cmVzIHRoZSBsb2cgY2FwdHVyZXMgaXQuXG4gICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICdyZWNlaXZlTWVzc2FnZUZyb21CcmFpbjogVW5oYW5kbGVkIHNraWxsRGF0YUZvckxvZy5xdWVyeSBzdGF0ZTonLFxuICAgICAgICBza2lsbERhdGFGb3JMb2cucXVlcnksXG4gICAgICAgICdBcHBlbmRpbmcgdG8gbG9nLidcbiAgICAgICk7XG4gICAgICBzZXRNZXNzYWdlSGlzdG9yeShbLi4udXBkYXRlZE1lc3NhZ2VIaXN0b3J5LCBza2lsbERhdGFGb3JMb2ddKTtcbiAgICB9XG5cbiAgICAvLyBzZXRJc0xvYWRpbmcoZmFsc2UpIGlzIG5vdyBoYW5kbGVkIGJ5IHRoZSBjYWxsZXIgKFVzZXJWaWV3Q2hhdC50c3gpXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsIGV0byByZWNlaXZlIG1lc3NhZ2UgZnJvbSBicmFpbicpO1xuICB9XG59O1xuIl19