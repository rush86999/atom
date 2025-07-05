import type { NextApiRequest, NextApiResponse } from 'next';
import { handleMessage, HandleMessageResponse } from '../../../../project/functions/atom-agent/handler'; // Adjust path as necessary
import pino from 'pino';
import { trace, context as otelContext } from '@opentelemetry/api';

// Import custom metrics
import {
  apiRequestCounter,
  apiRequestLatencyHistogram,
} from '../../../instrumentation.node'; // Adjust path as needed relative to pages/api/atom/message.ts

const serviceName = process.env.OTEL_SERVICE_NAME || 'app-service';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label.toUpperCase() }),
    log: (object) => {
      object.service_name = serviceName;
      object.version = serviceVersion;
      const currentSpan = trace.getSpan(otelContext.active());
      if (currentSpan) {
        const spanContext = currentSpan.spanContext();
        if (spanContext && spanContext.traceId) {
          object.trace_id = spanContext.traceId;
          object.span_id = spanContext.spanId;
        }
      }
      return object;
    },
  },
  timestamp: () => `,"timestamp":"${new Date(Date.now()).toISOString()}"`,
  // Use pino-pretty for local development if desired, by piping output:
  // e.g., `next dev | pino-pretty`
});

type Data = HandleMessageResponse;

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data>
) {
  const operation_name = 'POST /api/atom/message'; // For logging and metrics
  const startTime = Date.now();

  // Attach a response.finish listener to log response and record metrics
  res.on('finish', () => {
    const durationMs = Date.now() - startTime;
    const attributes = {
      http_method: req.method,
      http_route: '/api/atom/message', // Or a more parameterized route if applicable
      status_code: res.statusCode,
    };
    apiRequestCounter.add(1, attributes);
    apiRequestLatencyHistogram.record(durationMs / 1000, attributes); // Record in seconds

    logger.info(
      {
        operation_name,
        http_status_code: res.statusCode,
        duration_ms: durationMs,
        success: res.statusCode >= 200 && res.statusCode < 300,
      },
      `Finished ${operation_name}`
    );
  });

  if (req.method === 'POST') {
    const { message, userId, conversationId, intentName, entities } = req.body; // Assuming these might be passed

    logger.info(
        { operation_name, body_message_present: !!message, user_id: userId, conversation_id: conversationId },
        `Received request for ${operation_name}`
    );

    if (!message) {
      logger.warn({ operation_name, error_code: 'MISSING_MESSAGE', success: false }, 'Missing message in request body');
      return res.status(400).json({ text: '', error: 'Missing message in request body' });
    }

    try {
      // Construct options for handleMessage if they are passed from client
      const options: any = {}; // Define a proper type for options if structure is known
      if (userId) options.userId = userId; // Pass userId if available
      if (conversationId) options.conversationId = conversationId;
      if (intentName) options.intentName = intentName;
      if (entities) options.entities = entities;
      // Assuming handleMessage can now take an options object or additional parameters
      // For simplicity, if handleMessage only takes `message: string`, this needs adjustment.
      // The original call was `handleMessage(message as string)`.
      // Let's assume handleMessage can now take `message` and `options`.
      // This part depends on `handleMessage` signature from `../../../../project/functions/atom-agent/handler`

      // Simplified: Assuming handleMessage needs more context, which might be passed via body
      // The call to handleMessage in functions/atom-agent/handler.ts is _internalHandleMessage(interfaceType, message, userId, options);
      // The API route here is effectively the entry point for 'text' interfaceType.
      // The _internalHandleMessage expects userId and options.
      // We need to ensure `userId` is available, perhaps from session or passed in body.
      // For this example, let's assume `userId` is passed in the body for simplicity.
      // In a real app, it would likely come from an authenticated session.

      if (!userId) {
        logger.warn({ operation_name, error_code: 'MISSING_USERID', success: false }, 'Missing userId in request body for handleMessage');
        return res.status(400).json({ text: '', error: 'Missing userId in request body' });
      }

      const atomResponse: HandleMessageResponse = await handleMessage(
        'text', // interfaceType
        message as string,
        userId as string, // Assuming userId is passed in body
        options // Contains conversationId, intentName, entities if passed
      );

      // Note: res.on('finish') will log the final status and duration.
      // No need for explicit success log here if covered by finish event.
      return res.status(200).json(atomResponse);

    } catch (error: any) {
      logger.error(
        {
          operation_name,
          error_message: error.message,
          stack_trace: error.stack,
          exception_type: error.name,
          success: false,
        },
        'Error calling Atom agent handleMessage'
      );
      // res.on('finish') will log the 500 status.
      return res.status(500).json({ text: '', error: error.message || 'Internal Server Error from Atom agent' });
    }
  } else {
    logger.warn({ operation_name, http_method: req.method, success: false }, `Method ${req.method} Not Allowed`);
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
