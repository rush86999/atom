"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const handler_1 = require("../../../../project/functions/atom-agent/handler"); // Adjust path as necessary
const pino_1 = __importDefault(require("pino"));
const api_1 = require("@opentelemetry/api");
// Import custom metrics
const instrumentation_node_1 = require("../../../instrumentation.node"); // Adjust path as needed relative to pages/api/atom/message.ts
const serviceName = process.env.OTEL_SERVICE_NAME || 'app-service';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';
const logger = (0, pino_1.default)({
    level: process.env.LOG_LEVEL || 'info',
    formatters: {
        level: (label) => ({ level: label.toUpperCase() }),
        log: (object) => {
            object.service_name = serviceName;
            object.version = serviceVersion;
            const currentSpan = api_1.trace.getSpan(api_1.context.active());
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
async function handler(req, res) {
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
        instrumentation_node_1.apiRequestCounter.add(1, attributes);
        instrumentation_node_1.apiRequestLatencyHistogram.record(durationMs / 1000, attributes); // Record in seconds
        logger.info({
            operation_name,
            http_status_code: res.statusCode,
            duration_ms: durationMs,
            success: res.statusCode >= 200 && res.statusCode < 300,
        }, `Finished ${operation_name}`);
    });
    if (req.method === 'POST') {
        const { message, userId, conversationId, intentName, entities } = req.body; // Assuming these might be passed
        logger.info({
            operation_name,
            body_message_present: !!message,
            user_id: userId,
            conversation_id: conversationId,
        }, `Received request for ${operation_name}`);
        if (!message) {
            logger.warn({ operation_name, error_code: 'MISSING_MESSAGE', success: false }, 'Missing message in request body');
            return res
                .status(400)
                .json({ text: '', error: 'Missing message in request body' });
        }
        try {
            // Construct options for handleMessage if they are passed from client
            const options = {}; // Define a proper type for options if structure is known
            if (userId)
                options.userId = userId; // Pass userId if available
            if (conversationId)
                options.conversationId = conversationId;
            if (intentName)
                options.intentName = intentName;
            if (entities)
                options.entities = entities;
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
                return res
                    .status(400)
                    .json({ text: '', error: 'Missing userId in request body' });
            }
            const atomResponse = await (0, handler_1.handleMessage)('text', // interfaceType
            message, userId, // Assuming userId is passed in body
            options // Contains conversationId, intentName, entities if passed
            );
            // Note: res.on('finish') will log the final status and duration.
            // No need for explicit success log here if covered by finish event.
            return res.status(200).json(atomResponse);
        }
        catch (error) {
            logger.error({
                operation_name,
                error_message: error.message,
                stack_trace: error.stack,
                exception_type: error.name,
                success: false,
            }, 'Error calling Atom agent handleMessage');
            // res.on('finish') will log the 500 status.
            return res
                .status(500)
                .json({
                text: '',
                error: error.message || 'Internal Server Error from Atom agent',
            });
        }
    }
    else {
        logger.warn({ operation_name, http_method: req.method, success: false }, `Method ${req.method} Not Allowed`);
        res.setHeader('Allow', ['POST']);
        return res.status(405).end(`Method ${req.method} Not Allowed`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWVzc2FnZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm1lc3NhZ2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUEwQ0EsMEJBd0hDO0FBaktELDhFQUcwRCxDQUFDLDJCQUEyQjtBQUN0RixnREFBd0I7QUFDeEIsNENBQW1FO0FBRW5FLHdCQUF3QjtBQUN4Qix3RUFHdUMsQ0FBQyw4REFBOEQ7QUFFdEcsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxpQkFBaUIsSUFBSSxhQUFhLENBQUM7QUFDbkUsTUFBTSxjQUFjLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxvQkFBb0IsSUFBSSxPQUFPLENBQUM7QUFFbkUsTUFBTSxNQUFNLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDbEIsS0FBSyxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsU0FBUyxJQUFJLE1BQU07SUFDdEMsVUFBVSxFQUFFO1FBQ1YsS0FBSyxFQUFFLENBQUMsS0FBSyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsS0FBSyxFQUFFLEtBQUssQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDO1FBQ2xELEdBQUcsRUFBRSxDQUFDLE1BQU0sRUFBRSxFQUFFO1lBQ2QsTUFBTSxDQUFDLFlBQVksR0FBRyxXQUFXLENBQUM7WUFDbEMsTUFBTSxDQUFDLE9BQU8sR0FBRyxjQUFjLENBQUM7WUFDaEMsTUFBTSxXQUFXLEdBQUcsV0FBSyxDQUFDLE9BQU8sQ0FBQyxhQUFXLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQztZQUN4RCxJQUFJLFdBQVcsRUFBRSxDQUFDO2dCQUNoQixNQUFNLFdBQVcsR0FBRyxXQUFXLENBQUMsV0FBVyxFQUFFLENBQUM7Z0JBQzlDLElBQUksV0FBVyxJQUFJLFdBQVcsQ0FBQyxPQUFPLEVBQUUsQ0FBQztvQkFDdkMsTUFBTSxDQUFDLFFBQVEsR0FBRyxXQUFXLENBQUMsT0FBTyxDQUFDO29CQUN0QyxNQUFNLENBQUMsT0FBTyxHQUFHLFdBQVcs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aUJBQ1gsSUFBSSxDQUFDO2dCQUNKLElBQUksRUFBRSxFQUFFO2dCQUNSLEtBQUssRUFBRSxLQUFLLENBQUMsT0FBTyxJQUFJLHVDQUF1QzthQUNoRSxDQUFDLENBQUM7UUFDUCxDQUFDO0lBQ0gsQ0FBQztTQUFNLENBQUM7UUFDTixNQUFNLENBQUMsSUFBSSxDQUNULEVBQUUsY0FBYyxFQUFFLFdBQVcsRUFBRSxHQUFHLENBQUMsTUFBTSxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFDM0QsVUFBVSxHQUFHLENBQUMsTUFBTSxjQUFjLENBQ25DLENBQUM7UUFDRixHQUFHLENBQUMsU0FBUyxDQUFDLE9BQU8sRUFBRSxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUM7UUFDakMsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxVQUFVLEdBQUcsQ0FBQyxNQUFNLGNBQWMsQ0FBQyxDQUFDO0lBQ2pFLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHR5cGUgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQge1xuICBoYW5kbGVNZXNzYWdlLFxuICBIYW5kbGVNZXNzYWdlUmVzcG9uc2UsXG59IGZyb20gJy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvaGFuZGxlcic7IC8vIEFkanVzdCBwYXRoIGFzIG5lY2Vzc2FyeVxuaW1wb3J0IHBpbm8gZnJvbSAncGlubyc7XG5pbXBvcnQgeyB0cmFjZSwgY29udGV4dCBhcyBvdGVsQ29udGV4dCB9IGZyb20gJ0BvcGVudGVsZW1ldHJ5L2FwaSc7XG5cbi8vIEltcG9ydCBjdXN0b20gbWV0cmljc1xuaW1wb3J0IHtcbiAgYXBpUmVxdWVzdENvdW50ZXIsXG4gIGFwaVJlcXVlc3RMYXRlbmN5SGlzdG9ncmFtLFxufSBmcm9tICcuLi8uLi8uLi9pbnN0cnVtZW50YXRpb24ubm9kZSc7IC8vIEFkanVzdCBwYXRoIGFzIG5lZWRlZCByZWxhdGl2ZSB0byBwYWdlcy9hcGkvYXRvbS9tZXNzYWdlLnRzXG5cbmNvbnN0IHNlcnZpY2VOYW1lID0gcHJvY2Vzcy5lbnYuT1RFTF9TRVJWSUNFX05BTUUgfHwgJ2FwcC1zZXJ2aWNlJztcbmNvbnN0IHNlcnZpY2VWZXJzaW9uID0gcHJvY2Vzcy5lbnYuT1RFTF9TRVJWSUNFX1ZFUlNJT04gfHwgJzEuMC4wJztcblxuY29uc3QgbG9nZ2VyID0gcGlubyh7XG4gIGxldmVsOiBwcm9jZXNzLmVudi5MT0dfTEVWRUwgfHwgJ2luZm8nLFxuICBmb3JtYXR0ZXJzOiB7XG4gICAgbGV2ZWw6IChsYWJlbCkgPT4gKHsgbGV2ZWw6IGxhYmVsLnRvVXBwZXJDYXNlKCkgfSksXG4gICAgbG9nOiAob2JqZWN0KSA9PiB7XG4gICAgICBvYmplY3Quc2VydmljZV9uYW1lID0gc2VydmljZU5hbWU7XG4gICAgICBvYmplY3QudmVyc2lvbiA9IHNlcnZpY2VWZXJzaW9uO1xuICAgICAgY29uc3QgY3VycmVudFNwYW4gPSB0cmFjZS5nZXRTcGFuKG90ZWxDb250ZXh0LmFjdGl2ZSgpKTtcbiAgICAgIGlmIChjdXJyZW50U3Bhbikge1xuICAgICAgICBjb25zdCBzcGFuQ29udGV4dCA9IGN1cnJlbnRTcGFuLnNwYW5Db250ZXh0KCk7XG4gICAgICAgIGlmIChzcGFuQ29udGV4dCAmJiBzcGFuQ29udGV4dC50cmFjZUlkKSB7XG4gICAgICAgICAgb2JqZWN0LnRyYWNlX2lkID0gc3BhbkNvbnRleHQudHJhY2VJZDtcbiAgICAgICAgICBvYmplY3Quc3Bhbl9pZCA9IHNwYW5Db250ZXh0LnNwYW5JZDtcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgcmV0dXJuIG9iamVjdDtcbiAgICB9LFxuICB9LFxuICB0aW1lc3RhbXA6ICgpID0+IGAsXCJ0aW1lc3RhbXBcIjpcIiR7bmV3IERhdGUoRGF0ZS5ub3coKSkudG9JU09TdHJpbmcoKX1cImAsXG4gIC8vIFVzZSBwaW5vLXByZXR0eSBmb3IgbG9jYWwgZGV2ZWxvcG1lbnQgaWYgZGVzaXJlZCwgYnkgcGlwaW5nIG91dHB1dDpcbiAgLy8gZS5nLiwgYG5leHQgZGV2IHwgcGluby1wcmV0dHlgXG59KTtcblxudHlwZSBEYXRhID0gSGFuZGxlTWVzc2FnZVJlc3BvbnNlO1xuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZTxEYXRhPlxuKSB7XG4gIGNvbnN0IG9wZXJhdGlvbl9uYW1lID0gJ1BPU1QgL2FwaS9hdG9tL21lc3NhZ2UnOyAvLyBGb3IgbG9nZ2luZyBhbmQgbWV0cmljc1xuICBjb25zdCBzdGFydFRpbWUgPSBEYXRlLm5vdygpO1xuXG4gIC8vIEF0dGFjaCBhIHJlc3BvbnNlLmZpbmlzaCBsaXN0ZW5lciB0byBsb2cgcmVzcG9uc2UgYW5kIHJlY29yZCBtZXRyaWNzXG4gIHJlcy5vbignZmluaXNoJywgKCkgPT4ge1xuICAgIGNvbnN0IGR1cmF0aW9uTXMgPSBEYXRlLm5vdygpIC0gc3RhcnRUaW1lO1xuICAgIGNvbnN0IGF0dHJpYnV0ZXMgPSB7XG4gICAgICBodHRwX21ldGhvZDogcmVxLm1ldGhvZCxcbiAgICAgIGh0dHBfcm91dGU6ICcvYXBpL2F0b20vbWVzc2FnZScsIC8vIE9yIGEgbW9yZSBwYXJhbWV0ZXJpemVkIHJvdXRlIGlmIGFwcGxpY2FibGVcbiAgICAgIHN0YXR1c19jb2RlOiByZXMuc3RhdHVzQ29kZSxcbiAgICB9O1xuICAgIGFwaVJlcXVlc3RDb3VudGVyLmFkZCgxLCBhdHRyaWJ1dGVzKTtcbiAgICBhcGlSZXF1ZXN0TGF0ZW5jeUhpc3RvZ3JhbS5yZWNvcmQoZHVyYXRpb25NcyAvIDEwMDAsIGF0dHJpYnV0ZXMpOyAvLyBSZWNvcmQgaW4gc2Vjb25kc1xuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICB7XG4gICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICBodHRwX3N0YXR1c19jb2RlOiByZXMuc3RhdHVzQ29kZSxcbiAgICAgICAgZHVyYXRpb25fbXM6IGR1cmF0aW9uTXMsXG4gICAgICAgIHN1Y2Nlc3M6IHJlcy5zdGF0dXNDb2RlID49IDIwMCAmJiByZXMuc3RhdHVzQ29kZSA8IDMwMCxcbiAgICAgIH0sXG4gICAgICBgRmluaXNoZWQgJHtvcGVyYXRpb25fbmFtZX1gXG4gICAgKTtcbiAgfSk7XG5cbiAgaWYgKHJlcS5tZXRob2QgPT09ICdQT1NUJykge1xuICAgIGNvbnN0IHsgbWVzc2FnZSwgdXNlcklkLCBjb252ZXJzYXRpb25JZCwgaW50ZW50TmFtZSwgZW50aXRpZXMgfSA9IHJlcS5ib2R5OyAvLyBBc3N1bWluZyB0aGVzZSBtaWdodCBiZSBwYXNzZWRcblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAge1xuICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgYm9keV9tZXNzYWdlX3ByZXNlbnQ6ICEhbWVzc2FnZSxcbiAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICBjb252ZXJzYXRpb25faWQ6IGNvbnZlcnNhdGlvbklkLFxuICAgICAgfSxcbiAgICAgIGBSZWNlaXZlZCByZXF1ZXN0IGZvciAke29wZXJhdGlvbl9uYW1lfWBcbiAgICApO1xuXG4gICAgaWYgKCFtZXNzYWdlKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgeyBvcGVyYXRpb25fbmFtZSwgZXJyb3JfY29kZTogJ01JU1NJTkdfTUVTU0FHRScsIHN1Y2Nlc3M6IGZhbHNlIH0sXG4gICAgICAgICdNaXNzaW5nIG1lc3NhZ2UgaW4gcmVxdWVzdCBib2R5J1xuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHsgdGV4dDogJycsIGVycm9yOiAnTWlzc2luZyBtZXNzYWdlIGluIHJlcXVlc3QgYm9keScgfSk7XG4gICAgfVxuXG4gICAgdHJ5IHtcbiAgICAgIC8vIENvbnN0cnVjdCBvcHRpb25zIGZvciBoYW5kbGVNZXNzYWdlIGlmIHRoZXkgYXJlIHBhc3NlZCBmcm9tIGNsaWVudFxuICAgICAgY29uc3Qgb3B0aW9uczogYW55ID0ge307IC8vIERlZmluZSBhIHByb3BlciB0eXBlIGZvciBvcHRpb25zIGlmIHN0cnVjdHVyZSBpcyBrbm93blxuICAgICAgaWYgKHVzZXJJZCkgb3B0aW9ucy51c2VySWQgPSB1c2VySWQ7IC8vIFBhc3MgdXNlcklkIGlmIGF2YWlsYWJsZVxuICAgICAgaWYgKGNvbnZlcnNhdGlvbklkKSBvcHRpb25zLmNvbnZlcnNhdGlvbklkID0gY29udmVyc2F0aW9uSWQ7XG4gICAgICBpZiAoaW50ZW50TmFtZSkgb3B0aW9ucy5pbnRlbnROYW1lID0gaW50ZW50TmFtZTtcbiAgICAgIGlmIChlbnRpdGllcykgb3B0aW9ucy5lbnRpdGllcyA9IGVudGl0aWVzO1xuICAgICAgLy8gQXNzdW1pbmcgaGFuZGxlTWVzc2FnZSBjYW4gbm93IHRha2UgYW4gb3B0aW9ucyBvYmplY3Qgb3IgYWRkaXRpb25hbCBwYXJhbWV0ZXJzXG4gICAgICAvLyBGb3Igc2ltcGxpY2l0eSwgaWYgaGFuZGxlTWVzc2FnZSBvbmx5IHRha2VzIGBtZXNzYWdlOiBzdHJpbmdgLCB0aGlzIG5lZWRzIGFkanVzdG1lbnQuXG4gICAgICAvLyBUaGUgb3JpZ2luYWwgY2FsbCB3YXMgYGhhbmRsZU1lc3NhZ2UobWVzc2FnZSBhcyBzdHJpbmcpYC5cbiAgICAgIC8vIExldCdzIGFzc3VtZSBoYW5kbGVNZXNzYWdlIGNhbiBub3cgdGFrZSBgbWVzc2FnZWAgYW5kIGBvcHRpb25zYC5cbiAgICAgIC8vIFRoaXMgcGFydCBkZXBlbmRzIG9uIGBoYW5kbGVNZXNzYWdlYCBzaWduYXR1cmUgZnJvbSBgLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9oYW5kbGVyYFxuXG4gICAgICAvLyBTaW1wbGlmaWVkOiBBc3N1bWluZyBoYW5kbGVNZXNzYWdlIG5lZWRzIG1vcmUgY29udGV4dCwgd2hpY2ggbWlnaHQgYmUgcGFzc2VkIHZpYSBib2R5XG4gICAgICAvLyBUaGUgY2FsbCB0byBoYW5kbGVNZXNzYWdlIGluIGZ1bmN0aW9ucy9hdG9tLWFnZW50L2hhbmRsZXIudHMgaXMgX2ludGVybmFsSGFuZGxlTWVzc2FnZShpbnRlcmZhY2VUeXBlLCBtZXNzYWdlLCB1c2VySWQsIG9wdGlvbnMpO1xuICAgICAgLy8gVGhlIEFQSSByb3V0ZSBoZXJlIGlzIGVmZmVjdGl2ZWx5IHRoZSBlbnRyeSBwb2ludCBmb3IgJ3RleHQnIGludGVyZmFjZVR5cGUuXG4gICAgICAvLyBUaGUgX2ludGVybmFsSGFuZGxlTWVzc2FnZSBleHBlY3RzIHVzZXJJZCBhbmQgb3B0aW9ucy5cbiAgICAgIC8vIFdlIG5lZWQgdG8gZW5zdXJlIGB1c2VySWRgIGlzIGF2YWlsYWJsZSwgcGVyaGFwcyBmcm9tIHNlc3Npb24gb3IgcGFzc2VkIGluIGJvZHkuXG4gICAgICAvLyBGb3IgdGhpcyBleGFtcGxlLCBsZXQncyBhc3N1bWUgYHVzZXJJZGAgaXMgcGFzc2VkIGluIHRoZSBib2R5IGZvciBzaW1wbGljaXR5LlxuICAgICAgLy8gSW4gYSByZWFsIGFwcCwgaXQgd291bGQgbGlrZWx5IGNvbWUgZnJvbSBhbiBhdXRoZW50aWNhdGVkIHNlc3Npb24uXG5cbiAgICAgIGlmICghdXNlcklkKSB7XG4gICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgIHsgb3BlcmF0aW9uX25hbWUsIGVycm9yX2NvZGU6ICdNSVNTSU5HX1VTRVJJRCcsIHN1Y2Nlc3M6IGZhbHNlIH0sXG4gICAgICAgICAgJ01pc3NpbmcgdXNlcklkIGluIHJlcXVlc3QgYm9keSBmb3IgaGFuZGxlTWVzc2FnZSdcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAgIC5qc29uKHsgdGV4dDogJycsIGVycm9yOiAnTWlzc2luZyB1c2VySWQgaW4gcmVxdWVzdCBib2R5JyB9KTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgYXRvbVJlc3BvbnNlOiBIYW5kbGVNZXNzYWdlUmVzcG9uc2UgPSBhd2FpdCBoYW5kbGVNZXNzYWdlKFxuICAgICAgICAndGV4dCcsIC8vIGludGVyZmFjZVR5cGVcbiAgICAgICAgbWVzc2FnZSBhcyBzdHJpbmcsXG4gICAgICAgIHVzZXJJZCBhcyBzdHJpbmcsIC8vIEFzc3VtaW5nIHVzZXJJZCBpcyBwYXNzZWQgaW4gYm9keVxuICAgICAgICBvcHRpb25zIC8vIENvbnRhaW5zIGNvbnZlcnNhdGlvbklkLCBpbnRlbnROYW1lLCBlbnRpdGllcyBpZiBwYXNzZWRcbiAgICAgICk7XG5cbiAgICAgIC8vIE5vdGU6IHJlcy5vbignZmluaXNoJykgd2lsbCBsb2cgdGhlIGZpbmFsIHN0YXR1cyBhbmQgZHVyYXRpb24uXG4gICAgICAvLyBObyBuZWVkIGZvciBleHBsaWNpdCBzdWNjZXNzIGxvZyBoZXJlIGlmIGNvdmVyZWQgYnkgZmluaXNoIGV2ZW50LlxuICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKGF0b21SZXNwb25zZSk7XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICB7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgZXJyb3JfbWVzc2FnZTogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgICAgICAgZXhjZXB0aW9uX3R5cGU6IGVycm9yLm5hbWUsXG4gICAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIH0sXG4gICAgICAgICdFcnJvciBjYWxsaW5nIEF0b20gYWdlbnQgaGFuZGxlTWVzc2FnZSdcbiAgICAgICk7XG4gICAgICAvLyByZXMub24oJ2ZpbmlzaCcpIHdpbGwgbG9nIHRoZSA1MDAgc3RhdHVzLlxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHRleHQ6ICcnLFxuICAgICAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlIHx8ICdJbnRlcm5hbCBTZXJ2ZXIgRXJyb3IgZnJvbSBBdG9tIGFnZW50JyxcbiAgICAgICAgfSk7XG4gICAgfVxuICB9IGVsc2Uge1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgeyBvcGVyYXRpb25fbmFtZSwgaHR0cF9tZXRob2Q6IHJlcS5tZXRob2QsIHN1Y2Nlc3M6IGZhbHNlIH0sXG4gICAgICBgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgXG4gICAgKTtcbiAgICByZXMuc2V0SGVhZGVyKCdBbGxvdycsIFsnUE9TVCddKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDUpLmVuZChgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgKTtcbiAgfVxufVxuIl19