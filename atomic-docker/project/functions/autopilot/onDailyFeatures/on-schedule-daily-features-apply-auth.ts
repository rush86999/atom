import { Request, Response } from 'express';
import { HasuraTriggerBodyType, AutopilotApiResponse, SkillError } from '@autopilot/_libs/types'; // Added AutopilotApiResponse, SkillError
import { onScheduleDailyFeaturesApply7DayWindowToEventTrigger } from '@autopilot/_libs/api-helper';

// Define a type for the success response data payload if specific data is returned
interface SuccessPayload {
    message: string;
    details?: any;
}

const handler = async (req: Request, res: Response<AutopilotApiResponse<SuccessPayload | null>>) => {
    try {
        const eventItem: HasuraTriggerBodyType = req.body;
        const payload = eventItem.payload;
        console.log(payload, ' parsed payload');

        // Validation checks
        const validationErrors: string[] = [];
        if (!payload?.body?.userId) validationErrors.push('Missing body.userId.');
        if (!payload?.body?.windowStartDate) validationErrors.push('Missing body.windowStartDate.');
        if (!payload?.body?.windowEndDate) validationErrors.push('Missing body.windowEndDate.');
        if (!payload?.body?.timezone) validationErrors.push('Missing body.timezone.');
        if (!payload?.autopilot?.userId) validationErrors.push('Missing autopilot.userId.');
        if (!payload?.autopilot?.scheduleAt) validationErrors.push('Missing autopilot.scheduleAt.');
        if (!payload?.autopilot?.timezone) validationErrors.push('Missing autopilot.timezone.'); // Note: This might be redundant if body.timezone is primary
        if (!payload?.autopilot?.payload) validationErrors.push('Missing autopilot.payload.');

        if (validationErrors.length > 0) {
            const errorMessage = validationErrors.join(' ');
            console.error('Validation failed:', errorMessage);
            return res.status(400).json({
                ok: false,
                error: {
                    code: 'VALIDATION_ERROR',
                    message: `Invalid input: ${errorMessage}`,
                    details: { event: eventItem } // Keep event details for debugging
                }
            });
        }
    
        // Call the core logic from api-helper
        // Assuming onScheduleDailyFeaturesApply7DayWindowToEventTrigger might throw an error or return a value indicating success/failure
        await onScheduleDailyFeaturesApply7DayWindowToEventTrigger(
            payload.autopilot, // Not null checked based on prior validation
            payload.body,      // Not null checked based on prior validation
        );

        return res.status(200).json({
            ok: true,
            data: { message: 'Successfully triggered on schedule daily features apply to event.' }
        });

    } catch (e: any) {
        console.error('Error in on-schedule-daily-features-apply-auth handler:', e);
        // Check if the error is from api-helper or an unexpected one
        // For now, using a generic API_HELPER_ERROR or INTERNAL_SERVER_ERROR
        return res.status(500).json({ // Use 500 for server-side errors
            ok: false,
            error: {
                code: e.isApiHelperError ? 'API_HELPER_ERROR' : 'INTERNAL_SERVER_ERROR', // Hypothetical isApiHelperError property
                message: e.message || 'An unexpected error occurred while processing the schedule.',
                details: e.toString() // Include string representation of the error
            }
        });
    }
};

export default handler