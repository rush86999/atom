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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWNhbGVuZGFyLXN5bmMtYXV0aC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdvb2dsZS1jYWxlbmRhci1zeW5jLWF1dGgudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsT0FBTyxFQUFFLG1CQUFtQixFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFFMUQsTUFBTSxPQUFPLEdBQUcsS0FBSyxFQUFFLEdBQVksRUFBRSxHQUFhLEVBQUUsRUFBRTtJQUNwRCxJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSxRQUFRLENBQUMsQ0FBQztRQUMzQixvQkFBb0I7UUFDcEI7Ozs7Ozs7Ozs7V0FVRztRQUNILE1BQU0sT0FBTyxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUM7UUFDekIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxHQUFHLEVBQUUsSUFBSSxFQUFFLGFBQWEsQ0FBQyxDQUFDO1FBRXRDLE1BQU0sRUFBRSxxQkFBcUIsRUFBRSxVQUFVLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxHQUFHLE9BQU8sQ0FBQztRQUV4RSwyQ0FBMkM7UUFDM0MsSUFBSSxDQUFDLHFCQUFxQixFQUFFLENBQUM7WUFDM0IsT0FBTyxHQUFHO2lCQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7aUJBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLGdDQUFnQyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO1FBQ3pFLENBQUM7UUFDRCxJQUFJLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDaEIsT0FBTyxHQUFHO2lCQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7aUJBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLHFCQUFxQixFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO1FBQzlELENBQUM7UUFDRCxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7WUFDWixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsaUJBQWlCLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7UUFDMUQsQ0FBQztRQUNELElBQUksQ0FBQyxRQUFRLEVBQUUsQ0FBQztZQUNkLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxxQkFBcUIsRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQUMsQ0FBQztRQUM5RCxDQUFDO1FBRUQsTUFBTSxVQUFVLEdBQUcsTUFBTSxtQkFBbUIsQ0FBQztZQUMzQyxxQkFBcUI7WUFDckIsVUFBVTtZQUNWLE1BQU07WUFDTixRQUFRO1NBQ1QsQ0FBQyxDQUFDO1FBRUgsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLFVBQVUsQ0FBQyxNQUFNLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDeEMsT0FBTyxFQUFFLFVBQVUsQ0FBQyxPQUFPO1lBQzNCLEtBQUssRUFBRSxPQUFPLEVBQUUsa0ZBQWtGO1NBQ25HLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsOEJBQThCLENBQUMsQ0FBQztRQUMvQyxpRUFBaUU7UUFDakUsTUFBTSxPQUFPLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQztRQUN6QixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxpREFBaUQsQ0FBQyxFQUFFLE9BQU8sV0FBVyxDQUFDLEVBQUUsSUFBSSxFQUFFLEVBQUUsNENBQTRDO1lBQ3RJLEtBQUssRUFBRSxPQUFPLEVBQUUsc0RBQXNEO1NBQ3ZFLENBQUMsQ0FBQztJQUNMLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFJlcXVlc3QsIFJlc3BvbnNlIH0gZnJvbSAnZXhwcmVzcyc7XG5pbXBvcnQgeyBwZXJmb3JtQ2FsZW5kYXJTeW5jIH0gZnJvbSAnLi4vX2xpYnMvc3luYy1sb2dpYyc7XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAocmVxOiBSZXF1ZXN0LCByZXM6IFJlc3BvbnNlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2cocmVxLCAnIGV2ZW50Jyk7XG4gICAgLy8gY3VzdG9tIHZhbGlkYXRpb25cbiAgICAvKipcbiAgICAgIGF4aW9zIHBvc3QgQm9keSAtIHN0cmluZ2lmaWVkXG4gICAgICB7XG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICAgICAgICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gICAgICAgIHVzZXJJZDogc3RyaW5nLFxuICAgICAgICBldmVudFRyaWdnZXJJZDogc3RyaW5nLFxuICAgICAgICBpc0luaXRpYWxTeW5jOiBib29sZWFuLFxuICAgICAgICB0aW1lem9uZTogc3RyaW5nLFxuICAgICAgfVxuICAgICAqL1xuICAgIGNvbnN0IGJvZHlPYmogPSByZXEuYm9keTtcbiAgICBjb25zb2xlLmxvZyhyZXE/LmJvZHksICcgYXhpb3MgcG9zdCcpO1xuXG4gICAgY29uc3QgeyBjYWxlbmRhckludGVncmF0aW9uSWQsIGNhbGVuZGFySWQsIHVzZXJJZCwgdGltZXpvbmUgfSA9IGJvZHlPYmo7XG5cbiAgICAvLyBCYXNpYyB2YWxpZGF0aW9uIGZvciByZXF1aXJlZCBwYXJhbWV0ZXJzXG4gICAgaWYgKCFjYWxlbmRhckludGVncmF0aW9uSWQpIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHsgbWVzc2FnZTogJ25vIGNhbGVuZGFySW50ZWdyYXRpb25JZCBmb3VuZCcsIGV2ZW50OiBib2R5T2JqIH0pO1xuICAgIH1cbiAgICBpZiAoIWNhbGVuZGFySWQpIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHsgbWVzc2FnZTogJ25vIGNhbGVuZGFySWQgZm91bmQnLCBldmVudDogYm9keU9iaiB9KTtcbiAgICB9XG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHsgbWVzc2FnZTogJ25vIHVzZXJJZCBmb3VuZCcsIGV2ZW50OiBib2R5T2JqIH0pO1xuICAgIH1cbiAgICBpZiAoIXRpbWV6b25lKSB7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAuanNvbih7IG1lc3NhZ2U6ICdubyB0aW1lem9uZSBwcmVzZW50JywgZXZlbnQ6IGJvZHlPYmogfSk7XG4gICAgfVxuXG4gICAgY29uc3Qgc3luY1Jlc3VsdCA9IGF3YWl0IHBlcmZvcm1DYWxlbmRhclN5bmMoe1xuICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoc3luY1Jlc3VsdC5zdGF0dXMpLmpzb24oe1xuICAgICAgbWVzc2FnZTogc3luY1Jlc3VsdC5tZXNzYWdlLFxuICAgICAgZXZlbnQ6IGJvZHlPYmosIC8vIENvbnNpZGVyIGlmIHlvdSB3YW50IHRvIHJldHVybiB0aGUgb3JpZ2luYWwgcmVxdWVzdCBib2R5IG9yIHBhcnRzIG9mIHN5bmNSZXN1bHRcbiAgICB9KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHN5bmMgZ29vZ2xlIGNhbGVuZGFyJyk7XG4gICAgLy8gRW5zdXJlIGJvZHlPYmogaXMgZGVmaW5lZCBpbiBjYXRjaCBzY29wZSBpZiB5b3UgbmVlZCB0byB1c2UgaXRcbiAgICBjb25zdCBib2R5T2JqID0gcmVxLmJvZHk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6IGBlcnJvciBwcm9jZXNzaW5nIGdvb2dsZUNhbGVuZGFyU3luYzogbWVzc2FnZTogJHtlPy5tZXNzYWdlfSwgY29kZTogJHtlPy5jb2RlfWAsIC8vIEFzc3VtaW5nIGVycm9yIG9iamVjdCBtaWdodCBoYXZlIGEgJ2NvZGUnXG4gICAgICBldmVudDogYm9keU9iaiwgLy8gT3IgZSwgZGVwZW5kaW5nIG9uIHdoYXQncyBtb3JlIHVzZWZ1bCBmb3IgZGVidWdnaW5nXG4gICAgfSk7XG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IGhhbmRsZXI7XG4iXX0=