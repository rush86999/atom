"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateCalendarIntegration = void 0;
const date_utils_1 = require("@lib/date-utils");
const client_1 = require("@apollo/client");
const logger_1 = __importDefault(require("./logger")); // Import the shared logger
// dayjs.extend(utc)
const updateCalendarIntegration = async (client, calIntegId, enabled, token, refreshToken, expiresAt, clientType) => {
    try {
        const updateCalendarIntegration = (0, client_1.gql) `
      mutation UpdateCalendarIntegrationById($id: uuid!, ${enabled !== undefined ? '$enabled: Boolean,' : ''} ${expiresAt ? '$expiresAt: timestamptz,' : ''} ${refreshToken ? '$refreshToken: String,' : ''} ${token ? '$token: String,' : ''} $updatedAt: timestamptz) {
        update_Calendar_Integration_by_pk(_set: {${enabled !== undefined ? 'enabled: $enabled,' : ''} ${expiresAt ? 'expiresAt: $expiresAt,' : ''} ${refreshToken ? 'refreshToken: $refreshToken,' : ''} ${token ? 'token: $token,' : ''} updatedAt: $updatedAt}, pk_columns: {id: $id}) {
          appAccountId
          appEmail
          appId
          colors
          contactEmail
          contactName
          createdDate
          deleted
          enabled
          expiresAt
          id
          name
          pageToken
          password
          refreshToken
          syncEnabled
          resource
          token
          syncToken
          updatedAt
          userId
          username
          clientType
        }
      }
    `;
        let variables = {
            id: calIntegId,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (expiresAt) {
            variables.expiresAt = (0, date_utils_1.dayjs)(expiresAt).toISOString();
        }
        if (refreshToken) {
            variables.refreshToken = refreshToken;
        }
        if (token) {
            variables.token = token;
        }
        if (clientType) {
            variables.clientType = clientType;
        }
        const results = (await client.mutate({
            mutation: updateCalendarIntegration,
            variables,
        }))?.data?.update_Calendar_Integration_by_pk;
        return results;
    }
    catch (e) {
        // Added type annotation for e
        logger_1.default.error({
            message: 'Unable to update calendar_integration in api-helper',
            calIntegId,
            error: e.message,
            stack: e.stack,
            details: e,
        });
        // Decide if to rethrow or return undefined/specific error structure
        // Original code implicitly returned undefined. Maintaining that for now.
    }
};
exports.updateCalendarIntegration = updateCalendarIntegration;
/**
end
 */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsZ0RBQXdDO0FBTXhDLDJDQUEwRTtBQUMxRSxzREFBd0MsQ0FBQywyQkFBMkI7QUFFcEUsb0JBQW9CO0FBRWIsTUFBTSx5QkFBeUIsR0FBRyxLQUFLLEVBQzVDLE1BQTJDLEVBQzNDLFVBQWtCLEVBQ2xCLE9BQWlCLEVBQ2pCLEtBQWMsRUFDZCxZQUFxQixFQUNyQixTQUFrQixFQUNsQixVQUFxRCxFQUNyRCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSx5QkFBeUIsR0FBRyxJQUFBLFlBQUcsRUFBQTsyREFDa0IsT0FBTyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsb0JBQW9CLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxTQUFTLENBQUMsQ0FBQyxDQUFDLDBCQUEwQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksWUFBWSxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRSxJQUFJLEtBQUssQ0FBQyxDQUFDLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLEVBQUU7bURBQzFMLE9BQU8sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksU0FBUyxDQUFDLENBQUMsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLENBQUMsRUFBRSxJQUFJLFlBQVksQ0FBQyxDQUFDLENBQUMsOEJBQThCLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxLQUFLLENBQUMsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztLQTBCbk8sQ0FBQztRQUVGLElBQUksU0FBUyxHQUFRO1lBQ25CLEVBQUUsRUFBRSxVQUFVO1lBQ2QsU0FBUyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtTQUNqQyxDQUFDO1FBRUYsSUFBSSxPQUFPLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDMUIsU0FBUyxDQUFDLE9BQU8sR0FBRyxPQUFPLENBQUM7UUFDOUIsQ0FBQztRQUVELElBQUksU0FBUyxFQUFFLENBQUM7WUFDZCxTQUFTLENBQUMsU0FBUyxHQUFHLElBQUEsa0JBQUssRUFBQyxTQUFTLENBQUMsQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUN2RCxDQUFDO1FBRUQsSUFBSSxZQUFZLEVBQUUsQ0FBQztZQUNqQixTQUFTLENBQUMsWUFBWSxHQUFHLFlBQVksQ0FBQztRQUN4QyxDQUFDO1FBRUQsSUFBSSxLQUFLLEVBQUUsQ0FBQztZQUNWLFNBQVMsQ0FBQyxLQUFLLEdBQUcsS0FBSyxDQUFDO1FBQzFCLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsU0FBUyxDQUFDLFVBQVUsR0FBRyxVQUFVLENBQUM7UUFDcEMsQ0FBQztRQUVELE1BQU0sT0FBTyxHQUFHLENBQ2QsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVoQjtZQUNELFFBQVEsRUFBRSx5QkFBeUI7WUFDbkMsU0FBUztTQUNWLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSxpQ0FBaUMsQ0FBQztRQUUzQyxPQUFPLE9BQU8sQ0FBQztJQUNqQixDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQiw4QkFBOEI7UUFDOUIsZ0JBQWdCLENBQUMsS0FBSyxDQUFDO1lBQ3JCLE9BQU8sRUFBRSxxREFBcUQ7WUFDOUQsVUFBVTtZQUNWLEtBQUssRUFBRSxDQUFDLENBQUMsT0FBTztZQUNoQixLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUs7WUFDZCxPQUFPLEVBQUUsQ0FBQztTQUNYLENBQUMsQ0FBQztRQUNILG9FQUFvRTtRQUNwRSx5RUFBeUU7SUFDM0UsQ0FBQztBQUNILENBQUMsQ0FBQztBQXZGVyxRQUFBLHlCQUF5Qiw2QkF1RnBDO0FBRUY7O0dBRUciLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BsaWIvZGF0ZS11dGlscyc7XG4vLyBVbnVzZWQgaW1wb3J0OiBoYXN1cmFBcGlVcmxcbi8vIGltcG9ydCB7XG4vLyAgIGhhc3VyYUFwaVVybCxcbi8vIH0gZnJvbSAnQGxpYi9jb25zdGFudHMnO1xuaW1wb3J0IHsgQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhcl9JbnRlZ3JhdGlvblR5cGUnO1xuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBncWwsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBhcHBTZXJ2aWNlTG9nZ2VyIGZyb20gJy4vbG9nZ2VyJzsgLy8gSW1wb3J0IHRoZSBzaGFyZWQgbG9nZ2VyXG5cbi8vIGRheWpzLmV4dGVuZCh1dGMpXG5cbmV4cG9ydCBjb25zdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxJbnRlZ0lkOiBzdHJpbmcsXG4gIGVuYWJsZWQ/OiBib29sZWFuLFxuICB0b2tlbj86IHN0cmluZyxcbiAgcmVmcmVzaFRva2VuPzogc3RyaW5nLFxuICBleHBpcmVzQXQ/OiBzdHJpbmcsXG4gIGNsaWVudFR5cGU/OiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uID0gZ3FsYFxuICAgICAgbXV0YXRpb24gVXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQoJGlkOiB1dWlkISwgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnJGVuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfSAke2V4cGlyZXNBdCA/ICckZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9ICR7cmVmcmVzaFRva2VuID8gJyRyZWZyZXNoVG9rZW46IFN0cmluZywnIDogJyd9ICR7dG9rZW4gPyAnJHRva2VuOiBTdHJpbmcsJyA6ICcnfSAkdXBkYXRlZEF0OiB0aW1lc3RhbXB0eikge1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsoX3NldDogeyR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJ2VuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ30gJHtleHBpcmVzQXQgPyAnZXhwaXJlc0F0OiAkZXhwaXJlc0F0LCcgOiAnJ30gJHtyZWZyZXNoVG9rZW4gPyAncmVmcmVzaFRva2VuOiAkcmVmcmVzaFRva2VuLCcgOiAnJ30gJHt0b2tlbiA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ30gdXBkYXRlZEF0OiAkdXBkYXRlZEF0fSwgcGtfY29sdW1uczoge2lkOiAkaWR9KSB7XG4gICAgICAgICAgYXBwQWNjb3VudElkXG4gICAgICAgICAgYXBwRW1haWxcbiAgICAgICAgICBhcHBJZFxuICAgICAgICAgIGNvbG9yc1xuICAgICAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgIGlkXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgIHBhc3N3b3JkXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgc3luY0VuYWJsZWRcbiAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgdXNlcm5hbWVcbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuXG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgaWQ6IGNhbEludGVnSWQsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICB9O1xuXG4gICAgaWYgKGVuYWJsZWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmVuYWJsZWQgPSBlbmFibGVkO1xuICAgIH1cblxuICAgIGlmIChleHBpcmVzQXQpIHtcbiAgICAgIHZhcmlhYmxlcy5leHBpcmVzQXQgPSBkYXlqcyhleHBpcmVzQXQpLnRvSVNPU3RyaW5nKCk7XG4gICAgfVxuXG4gICAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgICAgdmFyaWFibGVzLnJlZnJlc2hUb2tlbiA9IHJlZnJlc2hUb2tlbjtcbiAgICB9XG5cbiAgICBpZiAodG9rZW4pIHtcbiAgICAgIHZhcmlhYmxlcy50b2tlbiA9IHRva2VuO1xuICAgIH1cblxuICAgIGlmIChjbGllbnRUeXBlKSB7XG4gICAgICB2YXJpYWJsZXMuY2xpZW50VHlwZSA9IGNsaWVudFR5cGU7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzdWx0cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGs6IENhbGVuZGFySW50ZWdyYXRpb25UeXBlO1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbixcbiAgICAgICAgdmFyaWFibGVzLFxuICAgICAgfSlcbiAgICApPy5kYXRhPy51cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGs7XG5cbiAgICByZXR1cm4gcmVzdWx0cztcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgLy8gQWRkZWQgdHlwZSBhbm5vdGF0aW9uIGZvciBlXG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcih7XG4gICAgICBtZXNzYWdlOiAnVW5hYmxlIHRvIHVwZGF0ZSBjYWxlbmRhcl9pbnRlZ3JhdGlvbiBpbiBhcGktaGVscGVyJyxcbiAgICAgIGNhbEludGVnSWQsXG4gICAgICBlcnJvcjogZS5tZXNzYWdlLFxuICAgICAgc3RhY2s6IGUuc3RhY2ssXG4gICAgICBkZXRhaWxzOiBlLFxuICAgIH0pO1xuICAgIC8vIERlY2lkZSBpZiB0byByZXRocm93IG9yIHJldHVybiB1bmRlZmluZWQvc3BlY2lmaWMgZXJyb3Igc3RydWN0dXJlXG4gICAgLy8gT3JpZ2luYWwgY29kZSBpbXBsaWNpdGx5IHJldHVybmVkIHVuZGVmaW5lZC4gTWFpbnRhaW5pbmcgdGhhdCBmb3Igbm93LlxuICB9XG59O1xuXG4vKipcbmVuZFxuICovXG4iXX0=