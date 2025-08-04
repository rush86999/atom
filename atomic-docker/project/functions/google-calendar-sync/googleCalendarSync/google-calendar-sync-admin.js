import { performCalendarSync } from '../_libs/sync-logic';
const handler = async (req, res) => {
    try {
        console.log(req, ' event');
        // custom validation
        /**
          axios post Body - stringified
          {
            calendarIntegrationId: string,
            calendarId: string,
            userId: string,
            eventTriggerId: string,
            isInitialSync: boolean,
            timezone: string,
          }
         */
        const bodyObj = req.body;
        console.log(req?.body, ' axios post');
        const { calendarIntegrationId, calendarId, userId, timezone } = bodyObj;
        // Basic validation for required parameters
        if (!calendarIntegrationId) {
            return res
                .status(400)
                .json({ message: 'no calendarIntegrationId found', event: bodyObj });
        }
        if (!calendarId) {
            return res
                .status(400)
                .json({ message: 'no calendarId found', event: bodyObj });
        }
        if (!userId) {
            return res
                .status(400)
                .json({ message: 'no userId found', event: bodyObj });
        }
        if (!timezone) {
            return res
                .status(400)
                .json({ message: 'no timezone present', event: bodyObj });
        }
        const syncResult = await performCalendarSync({
            calendarIntegrationId,
            calendarId,
            userId,
            timezone,
        });
        return res.status(syncResult.status).json({
            message: syncResult.message,
            event: bodyObj, // Consider if you want to return the original request body or parts of syncResult
        });
    }
    catch (e) {
        console.log(e, ' unable sync google calendar');
        // Ensure bodyObj is defined in catch scope if you need to use it
        const bodyObj = req.body;
        return res.status(400).json({
            message: `error processing googleCalendarSync: message: ${e?.message}, code: ${e?.code}`, // Assuming error object might have a 'code'
            event: bodyObj, // Or e, depending on what's more useful for debugging
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWNhbGVuZGFyLXN5bmMtYWRtaW4uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnb29nbGUtY2FsZW5kYXItc3luYy1hZG1pbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUUxRCxNQUFNLE9BQU8sR0FBRyxLQUFLLEVBQUUsR0FBWSxFQUFFLEdBQWEsRUFBRSxFQUFFO0lBQ3BELElBQUksQ0FBQztRQUNILE9BQU8sQ0FBQyxHQUFHLENBQUMsR0FBRyxFQUFFLFFBQVEsQ0FBQyxDQUFDO1FBQzNCLG9CQUFvQjtRQUNwQjs7Ozs7Ozs7OztXQVVHO1FBQ0gsTUFBTSxPQUFPLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQztRQUN6QixPQUFPLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUUsYUFBYSxDQUFDLENBQUM7UUFFdEMsTUFBTSxFQUFFLHFCQUFxQixFQUFFLFVBQVUsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLEdBQUcsT0FBTyxDQUFDO1FBRXhFLDJDQUEyQztRQUMzQyxJQUFJLENBQUMscUJBQXFCLEVBQUUsQ0FBQztZQUMzQixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsZ0NBQWdDLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7UUFDekUsQ0FBQztRQUNELElBQUksQ0FBQyxVQUFVLEVBQUUsQ0FBQztZQUNoQixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUscUJBQXFCLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7UUFDOUQsQ0FBQztRQUNELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNaLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxpQkFBaUIsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQUMsQ0FBQztRQUMxRCxDQUFDO1FBQ0QsSUFBSSxDQUFDLFFBQVEsRUFBRSxDQUFDO1lBQ2QsT0FBTyxHQUFHO2lCQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7aUJBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLHFCQUFxQixFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO1FBQzlELENBQUM7UUFFRCxNQUFNLFVBQVUsR0FBRyxNQUFNLG1CQUFtQixDQUFDO1lBQzNDLHFCQUFxQjtZQUNyQixVQUFVO1lBQ1YsTUFBTTtZQUNOLFFBQVE7U0FDVCxDQUFDLENBQUM7UUFFSCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsVUFBVSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FBQztZQUN4QyxPQUFPLEVBQUUsVUFBVSxDQUFDLE9BQU87WUFDM0IsS0FBSyxFQUFFLE9BQU8sRUFBRSxrRkFBa0Y7U0FDbkcsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw4QkFBOEIsQ0FBQyxDQUFDO1FBQy9DLGlFQUFpRTtRQUNqRSxNQUFNLE9BQU8sR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDO1FBQ3pCLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsT0FBTyxFQUFFLGlEQUFpRCxDQUFDLEVBQUUsT0FBTyxXQUFXLENBQUMsRUFBRSxJQUFJLEVBQUUsRUFBRSw0Q0FBNEM7WUFDdEksS0FBSyxFQUFFLE9BQU8sRUFBRSxzREFBc0Q7U0FDdkUsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCB7IHBlcmZvcm1DYWxlbmRhclN5bmMgfSBmcm9tICcuLi9fbGlicy9zeW5jLWxvZ2ljJztcblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChyZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhyZXEsICcgZXZlbnQnKTtcbiAgICAvLyBjdXN0b20gdmFsaWRhdGlvblxuICAgIC8qKlxuICAgICAgYXhpb3MgcG9zdCBCb2R5IC0gc3RyaW5naWZpZWRcbiAgICAgIHtcbiAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcsXG4gICAgICAgIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgICAgICAgdXNlcklkOiBzdHJpbmcsXG4gICAgICAgIGV2ZW50VHJpZ2dlcklkOiBzdHJpbmcsXG4gICAgICAgIGlzSW5pdGlhbFN5bmM6IGJvb2xlYW4sXG4gICAgICAgIHRpbWV6b25lOiBzdHJpbmcsXG4gICAgICB9XG4gICAgICovXG4gICAgY29uc3QgYm9keU9iaiA9IHJlcS5ib2R5O1xuICAgIGNvbnNvbGUubG9nKHJlcT8uYm9keSwgJyBheGlvcyBwb3N0Jyk7XG5cbiAgICBjb25zdCB7IGNhbGVuZGFySW50ZWdyYXRpb25JZCwgY2FsZW5kYXJJZCwgdXNlcklkLCB0aW1lem9uZSB9ID0gYm9keU9iajtcblxuICAgIC8vIEJhc2ljIHZhbGlkYXRpb24gZm9yIHJlcXVpcmVkIHBhcmFtZXRlcnNcbiAgICBpZiAoIWNhbGVuZGFySW50ZWdyYXRpb25JZCkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiAnbm8gY2FsZW5kYXJJbnRlZ3JhdGlvbklkIGZvdW5kJywgZXZlbnQ6IGJvZHlPYmogfSk7XG4gICAgfVxuICAgIGlmICghY2FsZW5kYXJJZCkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiAnbm8gY2FsZW5kYXJJZCBmb3VuZCcsIGV2ZW50OiBib2R5T2JqIH0pO1xuICAgIH1cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBtZXNzYWdlOiAnbm8gdXNlcklkIGZvdW5kJywgZXZlbnQ6IGJvZHlPYmogfSk7XG4gICAgfVxuICAgIGlmICghdGltZXpvbmUpIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHsgbWVzc2FnZTogJ25vIHRpbWV6b25lIHByZXNlbnQnLCBldmVudDogYm9keU9iaiB9KTtcbiAgICB9XG5cbiAgICBjb25zdCBzeW5jUmVzdWx0ID0gYXdhaXQgcGVyZm9ybUNhbGVuZGFyU3luYyh7XG4gICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICBjYWxlbmRhcklkLFxuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgfSk7XG5cbiAgICByZXR1cm4gcmVzLnN0YXR1cyhzeW5jUmVzdWx0LnN0YXR1cykuanNvbih7XG4gICAgICBtZXNzYWdlOiBzeW5jUmVzdWx0Lm1lc3NhZ2UsXG4gICAgICBldmVudDogYm9keU9iaiwgLy8gQ29uc2lkZXIgaWYgeW91IHdhbnQgdG8gcmV0dXJuIHRoZSBvcmlnaW5hbCByZXF1ZXN0IGJvZHkgb3IgcGFydHMgb2Ygc3luY1Jlc3VsdFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgc3luYyBnb29nbGUgY2FsZW5kYXInKTtcbiAgICAvLyBFbnN1cmUgYm9keU9iaiBpcyBkZWZpbmVkIGluIGNhdGNoIHNjb3BlIGlmIHlvdSBuZWVkIHRvIHVzZSBpdFxuICAgIGNvbnN0IGJvZHlPYmogPSByZXEuYm9keTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgbWVzc2FnZTogYGVycm9yIHByb2Nlc3NpbmcgZ29vZ2xlQ2FsZW5kYXJTeW5jOiBtZXNzYWdlOiAke2U/Lm1lc3NhZ2V9LCBjb2RlOiAke2U/LmNvZGV9YCwgLy8gQXNzdW1pbmcgZXJyb3Igb2JqZWN0IG1pZ2h0IGhhdmUgYSAnY29kZSdcbiAgICAgIGV2ZW50OiBib2R5T2JqLCAvLyBPciBlLCBkZXBlbmRpbmcgb24gd2hhdCdzIG1vcmUgdXNlZnVsIGZvciBkZWJ1Z2dpbmdcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==