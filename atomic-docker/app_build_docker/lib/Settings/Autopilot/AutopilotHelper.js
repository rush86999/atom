"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.listAutopilotsByUserId = exports.upsertManyAutopilot = exports.deleteAutopilotsGivenUserId = exports.triggerAddDailyFeaturesApplyUrl = exports.deleteScheduledEvent = void 0;
const deleteAutopilotsByUserId_1 = __importDefault(require("@lib/apollo/gql/deleteAutopilotsByUserId"));
const listAutopilotsGivenUserId_1 = __importDefault(require("@lib/apollo/gql/listAutopilotsGivenUserId"));
const upsertAutopilotMany_1 = __importDefault(require("@lib/apollo/gql/upsertAutopilotMany"));
const constants_1 = require("@lib/Settings/Autopilot/constants");
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const axios_1 = __importDefault(require("axios"));
const deleteScheduledEvent = async (eventId) => {
    try {
        const url = constants_1.deleteScheduledEventProdUrl;
        const data = eventId;
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const res = await axios_1.default.post(url, data, config);
    }
    catch (e) {
        console.log(e, ' unable to delete scheduled event');
    }
};
exports.deleteScheduledEvent = deleteScheduledEvent;
const triggerAddDailyFeaturesApplyUrl = async (autopilot, body) => {
    try {
        const url = constants_1.addDailyFeaturesAutopilotProdUrl;
        const data = {
            autopilot,
            body,
        };
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully triggered add daily features apply');
    }
    catch (e) {
        console.log(e, ' unable to trigger add daily features apply url');
    }
};
exports.triggerAddDailyFeaturesApplyUrl = triggerAddDailyFeaturesApplyUrl;
const deleteAutopilotsGivenUserId = async (client, userId) => {
    try {
        const affectedRows = (await client.mutate({
            mutation: deleteAutopilotsByUserId_1.default,
            variables: {
                userId,
            },
        }))?.data?.delete_Autopilot?.affected_rows;
        console.log(affectedRows, ' successfully deleted autopilots');
    }
    catch (e) {
        console.log(e, ' unable to delete many autopilots');
    }
};
exports.deleteAutopilotsGivenUserId = deleteAutopilotsGivenUserId;
const upsertManyAutopilot = async (client, autopilots) => {
    try {
        const affectedRows = (await client.mutate({
            mutation: upsertAutopilotMany_1.default,
            variables: {
                autopilots,
            },
        }))?.data?.insert_Autopilot?.affected_rows;
        console.log(affectedRows, ' successfully upserted many autopilots');
    }
    catch (e) {
        console.log(e, ' unable to upsert autopilot many');
    }
};
exports.upsertManyAutopilot = upsertManyAutopilot;
const listAutopilotsByUserId = async (client, userId) => {
    try {
        const autopilotsDoc = (await client.query({
            query: listAutopilotsGivenUserId_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.Autopilot;
        return autopilotsDoc;
    }
    catch (e) {
        console.log(e, ' unable to list autopilots by userId');
    }
};
exports.listAutopilotsByUserId = listAutopilotsByUserId;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQXV0b3BpbG90SGVscGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiQXV0b3BpbG90SGVscGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUNBLHdHQUFnRjtBQUNoRiwwR0FBa0Y7QUFDbEYsOEZBQXNFO0FBS3RFLGlFQUcyQztBQUUzQyxnRkFBd0Q7QUFDeEQsa0RBQTBCO0FBRW5CLE1BQU0sb0JBQW9CLEdBQUcsS0FBSyxFQUFFLE9BQWUsRUFBRSxFQUFFO0lBQzVELElBQUksQ0FBQztRQUNILE1BQU0sR0FBRyxHQUFHLHVDQUEyQixDQUFDO1FBQ3hDLE1BQU0sSUFBSSxHQUFHLE9BQU8sQ0FBQztRQUVyQixNQUFNLFdBQVcsR0FBRyxNQUFNLGlCQUFPLENBQUMsY0FBYyxFQUFFLENBQUM7UUFFbkQsTUFBTSxNQUFNLEdBQUc7WUFDYixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsV0FBVyxFQUFFO2dCQUN0QyxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1NBQ0YsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBQyxHQUFHLEVBQUUsSUFBSSxFQUFFLE1BQU0sQ0FBQyxDQUFDO0lBQ2xELENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsbUNBQW1DLENBQUMsQ0FBQztJQUN0RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBbEJXLFFBQUEsb0JBQW9CLHdCQWtCL0I7QUFFSyxNQUFNLCtCQUErQixHQUFHLEtBQUssRUFDbEQsU0FBd0IsRUFDeEIsSUFBNEMsRUFDNUMsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sR0FBRyxHQUFHLDRDQUFnQyxDQUFDO1FBRTdDLE1BQU0sSUFBSSxHQUEwQztZQUNsRCxTQUFTO1lBQ1QsSUFBSTtTQUNMLENBQUM7UUFFRixNQUFNLFdBQVcsR0FBRyxNQUFNLGlCQUFPLENBQUMsY0FBYyxFQUFFLENBQUM7UUFFbkQsTUFBTSxNQUFNLEdBQUc7WUFDYixPQUFPLEVBQUU7Z0JBQ1AsYUFBYSxFQUFFLFVBQVUsV0FBVyxFQUFFO2dCQUN0QyxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1NBQ0YsQ0FBQztRQUVGLE1BQU0sT0FBTyxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBQyxHQUFHLEVBQUUsSUFBSSxFQUFFLE1BQU0sQ0FBQyxDQUFDO1FBRXBELE9BQU8sQ0FBQyxHQUFHLENBQUMsT0FBTyxFQUFFLGtEQUFrRCxDQUFDLENBQUM7SUFDM0UsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxpREFBaUQsQ0FBQyxDQUFDO0lBQ3BFLENBQUM7QUFDSCxDQUFDLENBQUM7QUEzQlcsUUFBQSwrQkFBK0IsbUNBMkIxQztBQUVLLE1BQU0sMkJBQTJCLEdBQUcsS0FBSyxFQUM5QyxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sWUFBWSxHQUFHLENBQ25CLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FFaEI7WUFDRCxRQUFRLEVBQUUsa0NBQXdCO1lBQ2xDLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2FBQ1A7U0FDRixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsZ0JBQWdCLEVBQUUsYUFBYSxDQUFDO1FBRXpDLE9BQU8sQ0FBQyxHQUFHLENBQUMsWUFBWSxFQUFFLGtDQUFrQyxDQUFDLENBQUM7SUFDaEUsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxtQ0FBbUMsQ0FBQyxDQUFDO0lBQ3RELENBQUM7QUFDSCxDQUFDLENBQUM7QUFwQlcsUUFBQSwyQkFBMkIsK0JBb0J0QztBQUVLLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUN0QyxNQUEyQyxFQUMzQyxVQUEyQixFQUMzQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQUcsQ0FDbkIsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVoQjtZQUNELFFBQVEsRUFBRSw2QkFBbUI7WUFDN0IsU0FBUyxFQUFFO2dCQUNULFVBQVU7YUFDWDtTQUNGLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSxnQkFBZ0IsRUFBRSxhQUFhLENBQUM7UUFFekMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxZQUFZLEVBQUUsd0NBQXdDLENBQUMsQ0FBQztJQUN0RSxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGtDQUFrQyxDQUFDLENBQUM7SUFDckQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXBCVyxRQUFBLG1CQUFtQix1QkFvQjlCO0FBRUssTUFBTSxzQkFBc0IsR0FBRyxLQUFLLEVBQ3pDLE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxhQUFhLEdBQUcsQ0FDcEIsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUFpQztZQUNqRCxLQUFLLEVBQUUsbUNBQXlCO1lBQ2hDLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2FBQ1A7WUFDRCxXQUFXLEVBQUUsVUFBVTtTQUN4QixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsU0FBUyxDQUFDO1FBRW5CLE9BQU8sYUFBYSxDQUFDO0lBQ3ZCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsc0NBQXNDLENBQUMsQ0FBQztJQUN6RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBbkJXLFFBQUEsc0JBQXNCLDBCQW1CakMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBkZWxldGVBdXRvcGlsb3RzQnlVc2VySWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUF1dG9waWxvdHNCeVVzZXJJZCc7XG5pbXBvcnQgbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZCc7XG5pbXBvcnQgdXBzZXJ0QXV0b3BpbG90TWFueSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBzZXJ0QXV0b3BpbG90TWFueSc7XG5pbXBvcnQge1xuICBBdXRvcGlsb3RUeXBlLFxuICBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZSxcbn0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQXV0b3BpbG90VHlwZSc7XG5pbXBvcnQge1xuICBhZGREYWlseUZlYXR1cmVzQXV0b3BpbG90UHJvZFVybCxcbiAgZGVsZXRlU2NoZWR1bGVkRXZlbnRQcm9kVXJsLFxufSBmcm9tICdAbGliL1NldHRpbmdzL0F1dG9waWxvdC9jb25zdGFudHMnO1xuaW1wb3J0IHsgQWRkRGFpbHlGZWF0dXJlc0FwcGx5RXZlbnRUcmlnZ2VyVHlwZSB9IGZyb20gJ0BsaWIvU2V0dGluZ3MvQXV0b3BpbG90L3R5cGVzJztcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLXdlYi1qcy9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuXG5leHBvcnQgY29uc3QgZGVsZXRlU2NoZWR1bGVkRXZlbnQgPSBhc3luYyAoZXZlbnRJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgdXJsID0gZGVsZXRlU2NoZWR1bGVkRXZlbnRQcm9kVXJsO1xuICAgIGNvbnN0IGRhdGEgPSBldmVudElkO1xuXG4gICAgY29uc3QgYWNjZXNzVG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHthY2Nlc3NUb2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgYXhpb3MucG9zdCh1cmwsIGRhdGEsIGNvbmZpZyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgc2NoZWR1bGVkIGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB0cmlnZ2VyQWRkRGFpbHlGZWF0dXJlc0FwcGx5VXJsID0gYXN5bmMgKFxuICBhdXRvcGlsb3Q6IEF1dG9waWxvdFR5cGUsXG4gIGJvZHk6IFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1cmwgPSBhZGREYWlseUZlYXR1cmVzQXV0b3BpbG90UHJvZFVybDtcblxuICAgIGNvbnN0IGRhdGE6IEFkZERhaWx5RmVhdHVyZXNBcHBseUV2ZW50VHJpZ2dlclR5cGUgPSB7XG4gICAgICBhdXRvcGlsb3QsXG4gICAgICBib2R5LFxuICAgIH07XG5cbiAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2FjY2Vzc1Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdCh1cmwsIGRhdGEsIGNvbmZpZyk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHN1Y2Nlc3NmdWxseSB0cmlnZ2VyZWQgYWRkIGRhaWx5IGZlYXR1cmVzIGFwcGx5Jyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB0cmlnZ2VyIGFkZCBkYWlseSBmZWF0dXJlcyBhcHBseSB1cmwnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUF1dG9waWxvdHNHaXZlblVzZXJJZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGFmZmVjdGVkUm93cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICBkZWxldGVfQXV0b3BpbG90OiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlcjsgcmV0dXJuaW5nOiBBdXRvcGlsb3RUeXBlW10gfTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IGRlbGV0ZUF1dG9waWxvdHNCeVVzZXJJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5kZWxldGVfQXV0b3BpbG90Py5hZmZlY3RlZF9yb3dzO1xuXG4gICAgY29uc29sZS5sb2coYWZmZWN0ZWRSb3dzLCAnIHN1Y2Nlc3NmdWxseSBkZWxldGVkIGF1dG9waWxvdHMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBtYW55IGF1dG9waWxvdHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydE1hbnlBdXRvcGlsb3QgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGF1dG9waWxvdHM6IEF1dG9waWxvdFR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgYWZmZWN0ZWRSb3dzID0gKFxuICAgICAgYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICAgIGluc2VydF9BdXRvcGlsb3Q6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyOyByZXR1cm5pbmc6IEF1dG9waWxvdFR5cGVbXSB9O1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBzZXJ0QXV0b3BpbG90TWFueSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgYXV0b3BpbG90cyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uaW5zZXJ0X0F1dG9waWxvdD8uYWZmZWN0ZWRfcm93cztcblxuICAgIGNvbnNvbGUubG9nKGFmZmVjdGVkUm93cywgJyBzdWNjZXNzZnVsbHkgdXBzZXJ0ZWQgbWFueSBhdXRvcGlsb3RzJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnQgYXV0b3BpbG90IG1hbnknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RBdXRvcGlsb3RzQnlVc2VySWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBhdXRvcGlsb3RzRG9jID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgICBmZXRjaFBvbGljeTogJ25vLWNhY2hlJyxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uQXV0b3BpbG90O1xuXG4gICAgcmV0dXJuIGF1dG9waWxvdHNEb2M7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IGF1dG9waWxvdHMgYnkgdXNlcklkJyk7XG4gIH1cbn07XG4iXX0=