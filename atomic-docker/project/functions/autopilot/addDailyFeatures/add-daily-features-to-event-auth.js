import { createInitialFeaturesApplyToEventTrigger } from '@autopilot/_libs/api-helper';
const handler = async (req, res) => {
    try {
        const eventItem = req.body;
        // Validate (using a more consolidated approach)
        const validationErrors = [];
        if (!eventItem?.body?.userId)
            validationErrors.push('Missing body.userId.');
        if (!eventItem?.body?.windowStartDate)
            validationErrors.push('Missing body.windowStartDate.');
        if (!eventItem?.body?.windowEndDate)
            validationErrors.push('Missing body.windowEndDate.');
        if (!eventItem?.body?.timezone)
            validationErrors.push('Missing body.timezone.');
        // Autopilot specific validations
        if (!eventItem?.autopilot?.userId)
            validationErrors.push('Missing autopilot.userId.'); // Corrected error message from "no timezone present"
        if (!eventItem?.autopilot?.scheduleAt)
            validationErrors.push('Missing autopilot.scheduleAt.');
        if (!eventItem?.autopilot?.timezone)
            validationErrors.push('Missing autopilot.timezone.');
        if (!eventItem?.autopilot?.payload)
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
        // Assuming eventItem.autopilot and eventItem.body are now validated to exist
        await createInitialFeaturesApplyToEventTrigger(eventItem.autopilot, eventItem.body);
        return res.status(200).json({
            ok: true,
            data: { message: 'Successfully started add daily features to event.' },
        });
    }
    catch (e) {
        console.error('Error in add-daily-features-to-event-auth handler:', e);
        return res.status(500).json({
            ok: false,
            error: {
                code: e.isApiHelperError ? 'API_HELPER_ERROR' : 'INTERNAL_SERVER_ERROR', // Hypothetical isApiHelperError
                message: e.message ||
                    'An unexpected error occurred while adding daily features.',
                details: e.toString(),
            },
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWRkLWRhaWx5LWZlYXR1cmVzLXRvLWV2ZW50LWF1dGguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhZGQtZGFpbHktZmVhdHVyZXMtdG8tZXZlbnQtYXV0aC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFNQSxPQUFPLEVBQUUsd0NBQXdDLEVBQUUsTUFBTSw2QkFBNkIsQ0FBQztBQVF2RixNQUFNLE9BQU8sR0FBRyxLQUFLLEVBQ25CLEdBQVksRUFDWixHQUEwRCxFQUMxRCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxTQUFTLEdBQTBDLEdBQUcsQ0FBQyxJQUFJLENBQUM7UUFFbEUsZ0RBQWdEO1FBQ2hELE1BQU0sZ0JBQWdCLEdBQWEsRUFBRSxDQUFDO1FBQ3RDLElBQUksQ0FBQyxTQUFTLEVBQUUsSUFBSSxFQUFFLE1BQU07WUFBRSxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsc0JBQXNCLENBQUMsQ0FBQztRQUM1RSxJQUFJLENBQUMsU0FBUyxFQUFFLElBQUksRUFBRSxlQUFlO1lBQ25DLGdCQUFnQixDQUFDLElBQUksQ0FBQywrQkFBK0IsQ0FBQyxDQUFDO1FBQ3pELElBQUksQ0FBQyxTQUFTLEVBQUUsSUFBSSxFQUFFLGFBQWE7WUFDakMsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLDZCQUE2QixDQUFDLENBQUM7UUFDdkQsSUFBSSxDQUFDLFNBQVMsRUFBRSxJQUFJLEVBQUUsUUFBUTtZQUM1QixnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsd0JBQXdCLENBQUMsQ0FBQztRQUNsRCxpQ0FBaUM7UUFDakMsSUFBSSxDQUFDLFNBQVMsRUFBRSxTQUFTLEVBQUUsTUFBTTtZQUMvQixnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsMkJBQTJCLENBQUMsQ0FBQyxDQUFDLHFEQUFxRDtRQUMzRyxJQUFJLENBQUMsU0FBUyxFQUFFLFNBQVMsRUFBRSxVQUFVO1lBQ25DLGdCQUFnQixDQUFDLElBQUksQ0FBQywrQkFBK0IsQ0FBQyxDQUFDO1FBQ3pELElBQUksQ0FBQyxTQUFTLEVBQUUsU0FBUyxFQUFFLFFBQVE7WUFDakMsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLDZCQUE2QixDQUFDLENBQUM7UUFDdkQsSUFBSSxDQUFDLFNBQVMsRUFBRSxTQUFTLEVBQUUsT0FBTztZQUNoQyxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsNEJBQTRCLENBQUMsQ0FBQztRQUV0RCxJQUFJLGdCQUFnQixDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUNoQyxNQUFNLFlBQVksR0FBRyxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDLENBQUM7WUFDaEQsT0FBTyxDQUFDLEtBQUssQ0FBQyxvQkFBb0IsRUFBRSxZQUFZLENBQUMsQ0FBQztZQUNsRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO2dCQUMxQixFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtvQkFDeEIsT0FBTyxFQUFFLGtCQUFrQixZQUFZLEVBQUU7b0JBQ3pDLE9BQU8sRUFBRSxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsRUFBRSxtQ0FBbUM7aUJBQ25FO2FBQ0YsQ0FBQyxDQUFDO1FBQ0wsQ0FBQztRQUVELDZFQUE2RTtRQUM3RSxNQUFNLHdDQUF3QyxDQUM1QyxTQUFTLENBQUMsU0FBUyxFQUNuQixTQUFTLENBQUMsSUFBSSxDQUNmLENBQUM7UUFFRixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLEVBQUUsRUFBRSxJQUFJO1lBQ1IsSUFBSSxFQUFFLEVBQUUsT0FBTyxFQUFFLG1EQUFtRCxFQUFFO1NBQ3ZFLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQUMsb0RBQW9ELEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDdkUsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsQ0FBQyxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDLENBQUMsdUJBQXVCLEVBQUUsZ0NBQWdDO2dCQUN6RyxPQUFPLEVBQ0wsQ0FBQyxDQUFDLE9BQU87b0JBQ1QsMkRBQTJEO2dCQUM3RCxPQUFPLEVBQUUsQ0FBQyxDQUFDLFFBQVEsRUFBRTthQUN0QjtTQUNGLENBQUMsQ0FBQztJQUNMLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFJlcXVlc3QsIFJlc3BvbnNlIH0gZnJvbSAnZXhwcmVzcyc7XG5pbXBvcnQge1xuICBBZGREYWlseUZlYXR1cmVzQXBwbHlFdmVudFRyaWdnZXJUeXBlLFxuICBBdXRvcGlsb3RBcGlSZXNwb25zZSxcbiAgU2tpbGxFcnJvcixcbn0gZnJvbSAnQGF1dG9waWxvdC9fbGlicy90eXBlcyc7IC8vIEFkZGVkIEF1dG9waWxvdEFwaVJlc3BvbnNlLCBTa2lsbEVycm9yXG5pbXBvcnQgeyBjcmVhdGVJbml0aWFsRmVhdHVyZXNBcHBseVRvRXZlbnRUcmlnZ2VyIH0gZnJvbSAnQGF1dG9waWxvdC9fbGlicy9hcGktaGVscGVyJztcblxuLy8gRGVmaW5lIGEgdHlwZSBmb3IgdGhlIHN1Y2Nlc3MgcmVzcG9uc2UgZGF0YSBwYXlsb2FkXG5pbnRlcmZhY2UgU3VjY2Vzc1BheWxvYWQge1xuICBtZXNzYWdlOiBzdHJpbmc7XG4gIGRldGFpbHM/OiBhbnk7XG59XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAoXG4gIHJlcTogUmVxdWVzdCxcbiAgcmVzOiBSZXNwb25zZTxBdXRvcGlsb3RBcGlSZXNwb25zZTxTdWNjZXNzUGF5bG9hZCB8IG51bGw+PlxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXZlbnRJdGVtOiBBZGREYWlseUZlYXR1cmVzQXBwbHlFdmVudFRyaWdnZXJUeXBlID0gcmVxLmJvZHk7XG5cbiAgICAvLyBWYWxpZGF0ZSAodXNpbmcgYSBtb3JlIGNvbnNvbGlkYXRlZCBhcHByb2FjaClcbiAgICBjb25zdCB2YWxpZGF0aW9uRXJyb3JzOiBzdHJpbmdbXSA9IFtdO1xuICAgIGlmICghZXZlbnRJdGVtPy5ib2R5Py51c2VySWQpIHZhbGlkYXRpb25FcnJvcnMucHVzaCgnTWlzc2luZyBib2R5LnVzZXJJZC4nKTtcbiAgICBpZiAoIWV2ZW50SXRlbT8uYm9keT8ud2luZG93U3RhcnREYXRlKVxuICAgICAgdmFsaWRhdGlvbkVycm9ycy5wdXNoKCdNaXNzaW5nIGJvZHkud2luZG93U3RhcnREYXRlLicpO1xuICAgIGlmICghZXZlbnRJdGVtPy5ib2R5Py53aW5kb3dFbmREYXRlKVxuICAgICAgdmFsaWRhdGlvbkVycm9ycy5wdXNoKCdNaXNzaW5nIGJvZHkud2luZG93RW5kRGF0ZS4nKTtcbiAgICBpZiAoIWV2ZW50SXRlbT8uYm9keT8udGltZXpvbmUpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYm9keS50aW1lem9uZS4nKTtcbiAgICAvLyBBdXRvcGlsb3Qgc3BlY2lmaWMgdmFsaWRhdGlvbnNcbiAgICBpZiAoIWV2ZW50SXRlbT8uYXV0b3BpbG90Py51c2VySWQpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnVzZXJJZC4nKTsgLy8gQ29ycmVjdGVkIGVycm9yIG1lc3NhZ2UgZnJvbSBcIm5vIHRpbWV6b25lIHByZXNlbnRcIlxuICAgIGlmICghZXZlbnRJdGVtPy5hdXRvcGlsb3Q/LnNjaGVkdWxlQXQpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnNjaGVkdWxlQXQuJyk7XG4gICAgaWYgKCFldmVudEl0ZW0/LmF1dG9waWxvdD8udGltZXpvbmUpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnRpbWV6b25lLicpO1xuICAgIGlmICghZXZlbnRJdGVtPy5hdXRvcGlsb3Q/LnBheWxvYWQpXG4gICAgICB2YWxpZGF0aW9uRXJyb3JzLnB1c2goJ01pc3NpbmcgYXV0b3BpbG90LnBheWxvYWQuJyk7XG5cbiAgICBpZiAodmFsaWRhdGlvbkVycm9ycy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBlcnJvck1lc3NhZ2UgPSB2YWxpZGF0aW9uRXJyb3JzLmpvaW4oJyAnKTtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ1ZhbGlkYXRpb24gZmFpbGVkOicsIGVycm9yTWVzc2FnZSk7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6IGBJbnZhbGlkIGlucHV0OiAke2Vycm9yTWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IHsgZXZlbnQ6IGV2ZW50SXRlbSB9LCAvLyBLZWVwIGV2ZW50IGRldGFpbHMgZm9yIGRlYnVnZ2luZ1xuICAgICAgICB9LFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gQXNzdW1pbmcgZXZlbnRJdGVtLmF1dG9waWxvdCBhbmQgZXZlbnRJdGVtLmJvZHkgYXJlIG5vdyB2YWxpZGF0ZWQgdG8gZXhpc3RcbiAgICBhd2FpdCBjcmVhdGVJbml0aWFsRmVhdHVyZXNBcHBseVRvRXZlbnRUcmlnZ2VyKFxuICAgICAgZXZlbnRJdGVtLmF1dG9waWxvdCxcbiAgICAgIGV2ZW50SXRlbS5ib2R5XG4gICAgKTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHsgbWVzc2FnZTogJ1N1Y2Nlc3NmdWxseSBzdGFydGVkIGFkZCBkYWlseSBmZWF0dXJlcyB0byBldmVudC4nIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGluIGFkZC1kYWlseS1mZWF0dXJlcy10by1ldmVudC1hdXRoIGhhbmRsZXI6JywgZSk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNTAwKS5qc29uKHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6IGUuaXNBcGlIZWxwZXJFcnJvciA/ICdBUElfSEVMUEVSX0VSUk9SJyA6ICdJTlRFUk5BTF9TRVJWRVJfRVJST1InLCAvLyBIeXBvdGhldGljYWwgaXNBcGlIZWxwZXJFcnJvclxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGUubWVzc2FnZSB8fFxuICAgICAgICAgICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGFkZGluZyBkYWlseSBmZWF0dXJlcy4nLFxuICAgICAgICBkZXRhaWxzOiBlLnRvU3RyaW5nKCksXG4gICAgICB9LFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19