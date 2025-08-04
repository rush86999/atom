"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getChatMeetingPreferences = exports.upsertChatMeetingPreferencesGivenUserId = void 0;
const listChatMeetingPreferencesType_1 = __importDefault(require("@lib/apollo/gql/listChatMeetingPreferencesType"));
const upsertChatMeetingPreferences_1 = __importDefault(require("@lib/apollo/gql/upsertChatMeetingPreferences"));
const upsertChatMeetingPreferencesGivenUserId = async (client, chatMeetingPreference) => {
    try {
        const { data } = await client.mutate({
            mutation: upsertChatMeetingPreferences_1.default,
            variables: {
                chatMeetingPreference,
            },
        });
        console.log(data, ' data inside upsertChatMeetingPreferences');
    }
    catch (e) {
        console.log(e, ' unable to upsert chat meeting preferences given userId');
    }
};
exports.upsertChatMeetingPreferencesGivenUserId = upsertChatMeetingPreferencesGivenUserId;
const getChatMeetingPreferences = async (client, userId) => {
    try {
        const { data } = await client.query({
            query: listChatMeetingPreferencesType_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        });
        console.log(data, ' data getChatMeetingPreferences');
        if (data?.Chat_Meeting_Preference?.length > 0) {
            console.log(data.Chat_Meeting_Preference[0], ' data.Chat_Meeting_Preference[0]');
            return data.Chat_Meeting_Preference[0];
        }
        return null;
    }
    catch (e) {
        console.log(e, ' unable to get chat meeting preferences');
    }
};
exports.getChatMeetingPreferences = getChatMeetingPreferences;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiT25Cb2FyZEhlbHBlcjMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJPbkJvYXJkSGVscGVyMy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFDQSxvSEFBNEY7QUFDNUYsZ0hBQXdGO0FBR2pGLE1BQU0sdUNBQXVDLEdBQUcsS0FBSyxFQUMxRCxNQUEyQyxFQUMzQyxxQkFBaUQsRUFDakQsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxNQUFNLENBRWpDO1lBQ0QsUUFBUSxFQUFFLHNDQUE0QjtZQUN0QyxTQUFTLEVBQUU7Z0JBQ1QscUJBQXFCO2FBQ3RCO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUsMkNBQTJDLENBQUMsQ0FBQztJQUNqRSxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHlEQUF5RCxDQUFDLENBQUM7SUFDNUUsQ0FBQztBQUNILENBQUMsQ0FBQztBQWxCVyxRQUFBLHVDQUF1QywyQ0FrQmxEO0FBQ0ssTUFBTSx5QkFBeUIsR0FBRyxLQUFLLEVBQzVDLE1BQTJDLEVBQzNDLE1BQWMsRUFDdUIsRUFBRTtJQUN2QyxJQUFJLENBQUM7UUFDSCxNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUVoQztZQUNELEtBQUssRUFBRSx3Q0FBOEI7WUFDckMsU0FBUyxFQUFFO2dCQUNULE1BQU07YUFDUDtZQUNELFdBQVcsRUFBRSxVQUFVO1NBQ3hCLENBQUMsQ0FBQztRQUNILE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLGlDQUFpQyxDQUFDLENBQUM7UUFFckQsSUFBSSxJQUFJLEVBQUUsdUJBQXVCLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzlDLE9BQU8sQ0FBQyxHQUFHLENBQ1QsSUFBSSxDQUFDLHVCQUF1QixDQUFDLENBQUMsQ0FBQyxFQUMvQixrQ0FBa0MsQ0FDbkMsQ0FBQztZQUNGLE9BQU8sSUFBSSxDQUFDLHVCQUF1QixDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQ3pDLENBQUM7UUFDRCxPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseUNBQXlDLENBQUMsQ0FBQztJQUM1RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBM0JXLFFBQUEseUJBQXlCLDZCQTJCcEMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBsaXN0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2xpc3RDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSc7XG5pbXBvcnQgdXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcyc7XG5pbXBvcnQgeyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NoYXRNZWV0aW5nUHJlZmVyZW5jZVR5cGUnO1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlc0dpdmVuVXNlcklkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjaGF0TWVldGluZ1ByZWZlcmVuY2U6IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgaW5zZXJ0X0NoYXRfTWVldGluZ19QcmVmZXJlbmNlX29uZTogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGU7XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydENoYXRNZWV0aW5nUHJlZmVyZW5jZXMsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2hhdE1lZXRpbmdQcmVmZXJlbmNlLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgZGF0YSBpbnNpZGUgdXBzZXJ0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBzZXJ0IGNoYXQgbWVldGluZyBwcmVmZXJlbmNlcyBnaXZlbiB1c2VySWQnKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHtcbiAgICAgIENoYXRfTWVldGluZ19QcmVmZXJlbmNlOiBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZVtdO1xuICAgIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgfSxcbiAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgZGF0YSBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VzJyk7XG5cbiAgICBpZiAoZGF0YT8uQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2U/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBkYXRhLkNoYXRfTWVldGluZ19QcmVmZXJlbmNlWzBdLFxuICAgICAgICAnIGRhdGEuQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2VbMF0nXG4gICAgICApO1xuICAgICAgcmV0dXJuIGRhdGEuQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2VbMF07XG4gICAgfVxuICAgIHJldHVybiBudWxsO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNoYXQgbWVldGluZyBwcmVmZXJlbmNlcycpO1xuICB9XG59O1xuIl19