"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const pino_1 = __importDefault(require("pino"));
const api_1 = require("@opentelemetry/api");
const serviceName = process.env.OTEL_SERVICE_NAME || 'app-service'; // Or a more specific name if preferred
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';
const appServiceLogger = (0, pino_1.default)({
    level: process.env.LOG_LEVEL || 'info',
    formatters: {
        level: (label) => ({ level: label.toUpperCase() }),
        log: (object) => {
            // Explicitly type 'object'
            // Ensure object is not undefined and is an object
            if (object && typeof object === 'object') {
                object.service_name = serviceName;
                object.version = serviceVersion;
                // Add OpenTelemetry trace and span IDs if available
                const currentSpan = api_1.trace.getSpan(api_1.context.active());
                if (currentSpan) {
                    const spanContext = currentSpan.spanContext();
                    if (spanContext && spanContext.traceId) {
                        object.trace_id = spanContext.traceId;
                        object.span_id = spanContext.spanId;
                    }
                }
            }
            return object;
        },
    },
    timestamp: () => `,"timestamp":"${new Date(Date.now()).toISOString()}"`,
    // Pretty print for local development can be achieved by piping output, e.g., `| pino-pretty`
    // Or by conditionally adding pino-pretty transport if not in production:
    // transport: process.env.NODE_ENV !== 'production' ? { target: 'pino-pretty' } : undefined,
});
exports.default = appServiceLogger;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibG9nZ2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibG9nZ2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBQUEsZ0RBQXdCO0FBQ3hCLDRDQUFtRTtBQUVuRSxNQUFNLFdBQVcsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLGlCQUFpQixJQUFJLGFBQWEsQ0FBQyxDQUFDLHVDQUF1QztBQUMzRyxNQUFNLGNBQWMsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQixJQUFJLE9BQU8sQ0FBQztBQUVuRSxNQUFNLGdCQUFnQixHQUFHLElBQUEsY0FBSSxFQUFDO0lBQzVCLEtBQUssRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLFNBQVMsSUFBSSxNQUFNO0lBQ3RDLFVBQVUsRUFBRTtRQUNWLEtBQUssRUFBRSxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEtBQUssRUFBRSxLQUFLLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQztRQUNsRCxHQUFHLEVBQUUsQ0FBQyxNQUEyQixFQUFFLEVBQUU7WUFDbkMsMkJBQTJCO1lBQzNCLGtEQUFrRDtZQUNsRCxJQUFJLE1BQU0sSUFBSSxPQUFPLE1BQU0sS0FBSyxRQUFRLEVBQUUsQ0FBQztnQkFDekMsTUFBTSxDQUFDLFlBQVksR0FBRyxXQUFXLENBQUM7Z0JBQ2xDLE1BQU0sQ0FBQyxPQUFPLEdBQUcsY0FBYyxDQUFDO2dCQUNoQyxvREFBb0Q7Z0JBQ3BELE1BQU0sV0FBVyxHQUFHLFdBQUssQ0FBQyxPQUFPLENBQUMsYUFBVyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUM7Z0JBQ3hELElBQUksV0FBVyxFQUFFLENBQUM7b0JBQ2hCLE1BQU0sV0FBVyxHQUFHLFdBQVcsQ0FBQyxXQUFXLEVBQUUsQ0FBQztvQkFDOUMsSUFBSSxXQUFXLElBQUksV0FBVyxDQUFDLE9BQU8sRUFBRSxDQUFDO3dCQUN2QyxNQUFNLENBQUMsUUFBUSxHQUFHLFdBQVcsQ0FBQyxPQUFPLENBQUM7d0JBQ3RDLE1BQU0sQ0FBQyxPQUFPLEdBQUcsV0FBVyxDQUFDLE1BQU0sQ0FBQztvQkFDdEMsQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztZQUNELE9BQU8sTUFBTSxDQUFDO1FBQ2hCLENBQUM7S0FDRjtJQUNELFNBQVMsRUFBRSxHQUFHLEVBQUUsQ0FBQyxpQkFBaUIsSUFBSSxJQUFJLENBQUMsSUFBSSxDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUMsV0FBVyxFQUFFLEdBQUc7SUFDdkUsNkZBQTZGO0lBQzdGLHlFQUF5RTtJQUN6RSw0RkFBNEY7Q0FDN0YsQ0FBQyxDQUFDO0FBRUgsa0JBQWUsZ0JBQWdCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgcGlubyBmcm9tICdwaW5vJztcbmltcG9ydCB7IHRyYWNlLCBjb250ZXh0IGFzIG90ZWxDb250ZXh0IH0gZnJvbSAnQG9wZW50ZWxlbWV0cnkvYXBpJztcblxuY29uc3Qgc2VydmljZU5hbWUgPSBwcm9jZXNzLmVudi5PVEVMX1NFUlZJQ0VfTkFNRSB8fCAnYXBwLXNlcnZpY2UnOyAvLyBPciBhIG1vcmUgc3BlY2lmaWMgbmFtZSBpZiBwcmVmZXJyZWRcbmNvbnN0IHNlcnZpY2VWZXJzaW9uID0gcHJvY2Vzcy5lbnYuT1RFTF9TRVJWSUNFX1ZFUlNJT04gfHwgJzEuMC4wJztcblxuY29uc3QgYXBwU2VydmljZUxvZ2dlciA9IHBpbm8oe1xuICBsZXZlbDogcHJvY2Vzcy5lbnYuTE9HX0xFVkVMIHx8ICdpbmZvJyxcbiAgZm9ybWF0dGVyczoge1xuICAgIGxldmVsOiAobGFiZWwpID0+ICh7IGxldmVsOiBsYWJlbC50b1VwcGVyQ2FzZSgpIH0pLFxuICAgIGxvZzogKG9iamVjdDogUmVjb3JkPHN0cmluZywgYW55PikgPT4ge1xuICAgICAgLy8gRXhwbGljaXRseSB0eXBlICdvYmplY3QnXG4gICAgICAvLyBFbnN1cmUgb2JqZWN0IGlzIG5vdCB1bmRlZmluZWQgYW5kIGlzIGFuIG9iamVjdFxuICAgICAgaWYgKG9iamVjdCAmJiB0eXBlb2Ygb2JqZWN0ID09PSAnb2JqZWN0Jykge1xuICAgICAgICBvYmplY3Quc2VydmljZV9uYW1lID0gc2VydmljZU5hbWU7XG4gICAgICAgIG9iamVjdC52ZXJzaW9uID0gc2VydmljZVZlcnNpb247XG4gICAgICAgIC8vIEFkZCBPcGVuVGVsZW1ldHJ5IHRyYWNlIGFuZCBzcGFuIElEcyBpZiBhdmFpbGFibGVcbiAgICAgICAgY29uc3QgY3VycmVudFNwYW4gPSB0cmFjZS5nZXRTcGFuKG90ZWxDb250ZXh0LmFjdGl2ZSgpKTtcbiAgICAgICAgaWYgKGN1cnJlbnRTcGFuKSB7XG4gICAgICAgICAgY29uc3Qgc3BhbkNvbnRleHQgPSBjdXJyZW50U3Bhbi5zcGFuQ29udGV4dCgpO1xuICAgICAgICAgIGlmIChzcGFuQ29udGV4dCAmJiBzcGFuQ29udGV4dC50cmFjZUlkKSB7XG4gICAgICAgICAgICBvYmplY3QudHJhY2VfaWQgPSBzcGFuQ29udGV4dC50cmFjZUlkO1xuICAgICAgICAgICAgb2JqZWN0LnNwYW5faWQgPSBzcGFuQ29udGV4dC5zcGFuSWQ7XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgICByZXR1cm4gb2JqZWN0O1xuICAgIH0sXG4gIH0sXG4gIHRpbWVzdGFtcDogKCkgPT4gYCxcInRpbWVzdGFtcFwiOlwiJHtuZXcgRGF0ZShEYXRlLm5vdygpKS50b0lTT1N0cmluZygpfVwiYCxcbiAgLy8gUHJldHR5IHByaW50IGZvciBsb2NhbCBkZXZlbG9wbWVudCBjYW4gYmUgYWNoaWV2ZWQgYnkgcGlwaW5nIG91dHB1dCwgZS5nLiwgYHwgcGluby1wcmV0dHlgXG4gIC8vIE9yIGJ5IGNvbmRpdGlvbmFsbHkgYWRkaW5nIHBpbm8tcHJldHR5IHRyYW5zcG9ydCBpZiBub3QgaW4gcHJvZHVjdGlvbjpcbiAgLy8gdHJhbnNwb3J0OiBwcm9jZXNzLmVudi5OT0RFX0VOViAhPT0gJ3Byb2R1Y3Rpb24nID8geyB0YXJnZXQ6ICdwaW5vLXByZXR0eScgfSA6IHVuZGVmaW5lZCxcbn0pO1xuXG5leHBvcnQgZGVmYXVsdCBhcHBTZXJ2aWNlTG9nZ2VyO1xuIl19