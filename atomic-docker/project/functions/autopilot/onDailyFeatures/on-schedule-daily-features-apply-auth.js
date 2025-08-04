import { onScheduleDailyFeaturesApply7DayWindowToEventTrigger } from '@autopilot/_libs/api-helper';
const handler = async (req, res) => {
    try {
        const eventItem = req.body;
        const payload = eventItem.payload;
        console.log(payload, ' parsed payload');
        // Validation checks
        const validationErrors = [];
        if (!payload?.body?.userId)
            validationErrors.push('Missing body.userId.');
        if (!payload?.body?.windowStartDate)
            validationErrors.push('Missing body.windowStartDate.');
        if (!payload?.body?.windowEndDate)
            validationErrors.push('Missing body.windowEndDate.');
        if (!payload?.body?.timezone)
            validationErrors.push('Missing body.timezone.');
        if (!payload?.autopilot?.userId)
            validationErrors.push('Missing autopilot.userId.');
        if (!payload?.autopilot?.scheduleAt)
            validationErrors.push('Missing autopilot.scheduleAt.');
        if (!payload?.autopilot?.timezone)
            validationErrors.push('Missing autopilot.timezone.'); // Note: This might be redundant if body.timezone is primary
        if (!payload?.autopilot?.payload)
            validationErrors.push('Missing autopilot.payload.');
        if (validationErrors.length > 0) {
            const errorMessage = validationErrors.join(' ');
            console.error('Validation failed:', errorMessage);
            return res.status(400).json({
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: `Invalid input: ${errorMessage}`,
                    details: { event: eventItem }, // Keep event details for debugging
                },
            });
        }
        // Call the core logic from api-helper
        // Assuming onScheduleDailyFeaturesApply7DayWindowToEventTrigger might throw an error or return a value indicating success/failure
        await onScheduleDailyFeaturesApply7DayWindowToEventTrigger(payload.autopilot, // Not null checked based on prior validation
        payload.body // Not null checked based on prior validation
        );
        return res.status(200).json({
            ok: true,
            data: {
                message: 'Successfully triggered on schedule daily features apply to event.',
            },
        });
    }
    catch (e) {
        console.error('Error in on-schedule-daily-features-apply-auth handler:', e);
        // Check if the error is from api-helper or an unexpected one
        // For now, using a generic API_HELPER_ERROR or INTERNAL_SERVER_ERROR
        return res.status(500).json({
            // Use 500 for server-side errors
            ok: false,
            error: {
                code: e.isApiHelperError ? 'API_HELPER_ERROR' : 'INTERNAL_SERVER_ERROR', // Hypothetical isApiHelperError property
                message: e.message ||
                    'An unexpected error occurred while processing the schedule.',
                details: e.toString(), // Include string representation of the error
            },
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoib24tc2NoZWR1bGUtZGFpbHktZmVhdHVyZXMtYXBwbHktYXV0aC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm9uLXNjaGVkdWxlLWRhaWx5LWZlYXR1cmVzLWFwcGx5LWF1dGgudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBTUEsT0FBTyxFQUFFLG9EQUFvRCxFQUFFLE1BQU0sNkJBQTZCLENBQUM7QUFRbkcsTUFBTSxPQUFPLEdBQUcsS0FBSyxFQUNuQixHQUFZLEVBQ1osR0FBMEQsRUFDMUQsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sU0FBUyxHQUEwQixHQUFHLENBQUMsSUFBSSxDQUFDO1FBQ2xELE1BQU0sT0FBTyxHQUFHLFNBQVMsQ0FBQyxPQUFPLENBQUM7UUFDbEMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxPQUFPLEVBQUUsaUJBQWlCLENBQUMsQ0FBQztRQUV4QyxvQkFBb0I7UUFDcEIsTUFBTSxnQkFBZ0IsR0FBYSxFQUFFLENBQUM7UUFDdEMsSUFBSSxDQUFDLE9BQU8sRUFBRSxJQUFJLEVBQUUsTUFBTTtZQUFFLGdCQUFnQixDQUFDLElBQUksQ0FBQyxzQkFBc0IsQ0FBQyxDQUFDO1FBQzFFLElBQUksQ0FBQyxPQUFPLEVBQUUsSUFBSSxFQUFFLGVBQWU7WUFDakMsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLCtCQUErQixDQUFDLENBQUM7UUFDekQsSUFBSSxDQUFDLE9BQU8sRUFBRSxJQUFJLEVBQUUsYUFBYTtZQUMvQixnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsNkJBQTZCLENBQUMsQ0FBQztRQUN2RCxJQUFJLENBQUMsT0FBTyxFQUFFLElBQUksRUFBRSxRQUFRO1lBQzFCLGdCQUFnQixDQUFDLElBQUksQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDO1FBQ2xELElBQUksQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLE1BQU07WUFDN0IsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLDJCQUEyQixDQUFDLENBQUM7UUFDckQsSUFBSSxDQUFDLE9BQU8sRUFBRSxTQUFTLEVBQUUsVUFBVTtZQUNqQyxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsK0JBQStCLENBQUMsQ0FBQztRQUN6RCxJQUFJLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxRQUFRO1lBQy9CLGdCQUFnQixDQUFDLElBQUksQ0FBQyw2QkFBNkIsQ0FBQyxDQUFDLENBQUMsNERBQTREO1FBQ3BILElBQUksQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLE9BQU87WUFDOUIsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLDRCQUE0QixDQUFDLENBQUM7UUFFdEQsSUFBSSxnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDaEMsTUFBTSxZQUFZLEdBQUcsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLEdBQUcsQ0FBQyxDQUFDO1lBQ2hELE9BQU8sQ0FBQyxLQUFLLENBQUMsb0JBQW9CLEVBQUUsWUFBWSxDQUFDLENBQUM7WUFDbEQsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztnQkFDMUIsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSxrQkFBa0I7b0JBQ3hCLE9BQU8sRUFBRSxrQkFBa0IsWUFBWSxFQUFFO29CQUN6QyxPQUFPLEVBQUUsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLEVBQUUsbUNBQW1DO2lCQUNuRTthQUNGLENBQUMsQ0FBQztRQUNMLENBQUM7UUFFRCxzQ0FBc0M7UUFDdEMsa0lBQWtJO1FBQ2xJLE1BQU0sb0RBQW9ELENBQ3hELE9BQU8sQ0FBQyxTQUFTLEVBQUUsNkNBQTZDO1FBQ2hFLE9BQU8sQ0FBQyxJQUFJLENBQUMsNkNBQTZDO1NBQzNELENBQUM7UUFFRixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLEVBQUUsRUFBRSxJQUFJO1lBQ1IsSUFBSSxFQUFFO2dCQUNKLE9BQU8sRUFDTCxtRUFBbUU7YUFDdEU7U0FDRixDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixPQUFPLENBQUMsS0FBSyxDQUFDLHlEQUF5RCxFQUFFLENBQUMsQ0FBQyxDQUFDO1FBQzVFLDZEQUE2RDtRQUM3RCxxRUFBcUU7UUFDckUsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixpQ0FBaUM7WUFDakMsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsa0JBQWtCLENBQUMsQ0FBQyxDQUFDLHVCQUF1QixFQUFFLHlDQUF5QztnQkFDbEgsT0FBTyxFQUNMLENBQUMsQ0FBQyxPQUFPO29CQUNULDZEQUE2RDtnQkFDL0QsT0FBTyxFQUFFLENBQUMsQ0FBQyxRQUFRLEVBQUUsRUFBRSw2Q0FBNkM7YUFDckU7U0FDRixDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuaW1wb3J0IHtcbiAgSGFzdXJhVHJpZ2dlckJvZHlUeXBlLFxuICBBdXRvcGlsb3RBcGlSZXNwb25zZSxcbiAgU2tpbGxFcnJvcixcbn0gZnJvbSAnQGF1dG9waWxvdC9fbGlicy90eXBlcyc7IC8vIEFkZGVkIEF1dG9waWxvdEFwaVJlc3BvbnNlLCBTa2lsbEVycm9yXG5pbXBvcnQgeyBvblNjaGVkdWxlRGFpbHlGZWF0dXJlc0FwcGx5N0RheVdpbmRvd1RvRXZlbnRUcmlnZ2VyIH0gZnJvbSAnQGF1dG9waWxvdC9fbGlicy9hcGktaGVscGVyJztcblxuLy8gRGVmaW5lIGEgdHlwZSBmb3IgdGhlIHN1Y2Nlc3MgcmVzcG9uc2UgZGF0YSBwYXlsb2FkIGlmIHNwZWNpZmljIGRhdGEgaXMgcmV0dXJuZWRcbmludGVyZmFjZSBTdWNjZXNzUGF5bG9hZCB7XG4gIG1lc3NhZ2U6IHN0cmluZztcbiAgZGV0YWlscz86IGFueTtcbn1cblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChcbiAgcmVxOiBSZXF1ZXN0LFxuICByZXM6IFJlc3BvbnNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPFN1Y2Nlc3NQYXlsb2FkIHwgbnVsbD4+XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBldmVudEl0ZW06IEhhc3VyYVRyaWdnZXJCb2R5VHlwZSA9IHJlcS5ib2R5O1xuICAgIGNvbnN0IHBheWxvYWQgPSBldmVudEl0ZW0ucGF5bG9hZDtcbiAgICBjb25zb2xlLmxvZyhwYXlsb2FkLCAnIHBhcnNlZCBwYXlsb2FkJyk7XG5cbiAgICAvLyBWYWxpZGF0aW9uIGNoZWNrc1xuICAgIGNvbnN0IHZhbGlkYXRpb25FcnJvcnM6IHN0cmluZ1tdID0gW107XG4gICAgaWYgKCFwYXlsb2FkPy5ib2R5Py51c2VySWQpIHZhbGlkYXRpb25FcnJvcnMucHVzaCgnTWlzc2luZyBib2R5LnVzZXJJZC4nKTtcbiAgICBpZiAoIXBheWxvYWQ/LmJvZHk/LndpbmRvd1N0YXJ0RGF0ZSlcbiAgICAgIHZhbGlkYXRpb25FcnJvcnMucHVzaCgnTWlzc2luZyBib2R5LndpbmRvd1N0YXJ0RGF0ZS4nKTtcbiAgICBpZiAoIXBheWxvYWQ/LmJvZHk/LndpbmRvd0VuZERhdGUpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYm9keS53aW5kb3dFbmREYXRlLicpO1xuICAgIGlmICghcGF5bG9hZD8uYm9keT8udGltZXpvbmUpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYm9keS50aW1lem9uZS4nKTtcbiAgICBpZiAoIXBheWxvYWQ/LmF1dG9waWxvdD8udXNlcklkKVxuICAgICAgdmFsaWRhdGlvbkVycm9ycy5wdXNoKCdNaXNzaW5nIGF1dG9waWxvdC51c2VySWQuJyk7XG4gICAgaWYgKCFwYXlsb2FkPy5hdXRvcGlsb3Q/LnNjaGVkdWxlQXQpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnNjaGVkdWxlQXQuJyk7XG4gICAgaWYgKCFwYXlsb2FkPy5hdXRvcGlsb3Q/LnRpbWV6b25lKVxuICAgICAgdmFsaWRhdGlvbkVycm9ycy5wdXNoKCdNaXNzaW5nIGF1dG9waWxvdC50aW1lem9uZS4nKTsgLy8gTm90ZTogVGhpcyBtaWdodCBiZSByZWR1bmRhbnQgaWYgYm9keS50aW1lem9uZSBpcyBwcmltYXJ5XG4gICAgaWYgKCFwYXlsb2FkPy5hdXRvcGlsb3Q/LnBheWxvYWQpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnBheWxvYWQuJyk7XG5cbiAgICBpZiAodmFsaWRhdGlvbkVycm9ycy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBlcnJvck1lc3NhZ2UgPSB2YWxpZGF0aW9uRXJyb3JzLmpvaW4oJyAnKTtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ1ZhbGlkYXRpb24gZmFpbGVkOicsIGVycm9yTWVzc2FnZSk7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6IGBJbnZhbGlkIGlucHV0OiAke2Vycm9yTWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IHsgZXZlbnQ6IGV2ZW50SXRlbSB9LCAvLyBLZWVwIGV2ZW50IGRldGFpbHMgZm9yIGRlYnVnZ2luZ1xuICAgICAgICB9LFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gQ2FsbCB0aGUgY29yZSBsb2dpYyBmcm9tIGFwaS1oZWxwZXJcbiAgICAvLyBBc3N1bWluZyBvblNjaGVkdWxlRGFpbHlGZWF0dXJlc0FwcGx5N0RheVdpbmRvd1RvRXZlbnRUcmlnZ2VyIG1pZ2h0IHRocm93IGFuIGVycm9yIG9yIHJldHVybiBhIHZhbHVlIGluZGljYXRpbmcgc3VjY2Vzcy9mYWlsdXJlXG4gICAgYXdhaXQgb25TY2hlZHVsZURhaWx5RmVhdHVyZXNBcHBseTdEYXlXaW5kb3dUb0V2ZW50VHJpZ2dlcihcbiAgICAgIHBheWxvYWQuYXV0b3BpbG90LCAvLyBOb3QgbnVsbCBjaGVja2VkIGJhc2VkIG9uIHByaW9yIHZhbGlkYXRpb25cbiAgICAgIHBheWxvYWQuYm9keSAvLyBOb3QgbnVsbCBjaGVja2VkIGJhc2VkIG9uIHByaW9yIHZhbGlkYXRpb25cbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YToge1xuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdTdWNjZXNzZnVsbHkgdHJpZ2dlcmVkIG9uIHNjaGVkdWxlIGRhaWx5IGZlYXR1cmVzIGFwcGx5IHRvIGV2ZW50LicsXG4gICAgICB9LFxuICAgIH0pO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBpbiBvbi1zY2hlZHVsZS1kYWlseS1mZWF0dXJlcy1hcHBseS1hdXRoIGhhbmRsZXI6JywgZSk7XG4gICAgLy8gQ2hlY2sgaWYgdGhlIGVycm9yIGlzIGZyb20gYXBpLWhlbHBlciBvciBhbiB1bmV4cGVjdGVkIG9uZVxuICAgIC8vIEZvciBub3csIHVzaW5nIGEgZ2VuZXJpYyBBUElfSEVMUEVSX0VSUk9SIG9yIElOVEVSTkFMX1NFUlZFUl9FUlJPUlxuICAgIHJldHVybiByZXMuc3RhdHVzKDUwMCkuanNvbih7XG4gICAgICAvLyBVc2UgNTAwIGZvciBzZXJ2ZXItc2lkZSBlcnJvcnNcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGUuaXNBcGlIZWxwZXJFcnJvciA/ICdBUElfSEVMUEVSX0VSUk9SJyA6ICdJTlRFUk5BTF9TRVJWRVJfRVJST1InLCAvLyBIeXBvdGhldGljYWwgaXNBcGlIZWxwZXJFcnJvciBwcm9wZXJ0eVxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGUubWVzc2FnZSB8fFxuICAgICAgICAgICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIHByb2Nlc3NpbmcgdGhlIHNjaGVkdWxlLicsXG4gICAgICAgIGRldGFpbHM6IGUudG9TdHJpbmcoKSwgLy8gSW5jbHVkZSBzdHJpbmcgcmVwcmVzZW50YXRpb24gb2YgdGhlIGVycm9yXG4gICAgICB9LFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19