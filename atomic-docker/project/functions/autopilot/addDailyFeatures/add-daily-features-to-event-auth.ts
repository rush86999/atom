import { Request, Response } from 'express';
import {
  AddDailyFeaturesApplyEventTriggerType,
  AutopilotApiResponse,
  SkillError,
} from '@autopilot/_libs/types'; // Added AutopilotApiResponse, SkillError
import { createInitialFeaturesApplyToEventTrigger } from '@autopilot/_libs/api-helper';

// Define a type for the success response data payload
interface SuccessPayload {
  message: string;
  details?: any;
}

const handler = async (
  req: Request,
  res: Response<AutopilotApiResponse<SuccessPayload | null>>
) => {
  try {
    const eventItem: AddDailyFeaturesApplyEventTriggerType = req.body;

    // Validate (using a more consolidated approach)
    const validationErrors: string[] = [];
    if (!eventItem?.body?.userId) validationErrors.push('Missing body.userId.');
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
    await createInitialFeaturesApplyToEventTrigger(
      eventItem.autopilot,
      eventItem.body
    );

    return res.status(200).json({
      ok: true,
      data: { message: 'Successfully started add daily features to event.' },
    });
  } catch (e: any) {
    console.error('Error in add-daily-features-to-event-auth handler:', e);
    return res.status(500).json({
      ok: false,
      error: {
        code: e.isApiHelperError ? 'API_HELPER_ERROR' : 'INTERNAL_SERVER_ERROR', // Hypothetical isApiHelperError
        message:
          e.message ||
          'An unexpected error occurred while adding daily features.',
        details: e.toString(),
      },
    });
  }
};

export default handler;
