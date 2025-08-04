import pino from 'pino';
import { trace, context as otelContext } from '@opentelemetry/api';
const serviceName = process.env.OTEL_SERVICE_NAME || 'functions-service'; // Or a more specific name if preferred
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';
const functionsServiceLogger = pino({
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
                const currentSpan = trace.getSpan(otelContext.active());
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
export default functionsServiceLogger;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibG9nZ2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibG9nZ2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sSUFBSSxNQUFNLE1BQU0sQ0FBQztBQUN4QixPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sSUFBSSxXQUFXLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUVuRSxNQUFNLFdBQVcsR0FBRyxPQUFPLENBQUMsR0FBRyxDQUFDLGlCQUFpQixJQUFJLG1CQUFtQixDQUFDLENBQUMsdUNBQXVDO0FBQ2pILE1BQU0sY0FBYyxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsb0JBQW9CLElBQUksT0FBTyxDQUFDO0FBRW5FLE1BQU0sc0JBQXNCLEdBQUcsSUFBSSxDQUFDO0lBQ2xDLEtBQUssRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLFNBQVMsSUFBSSxNQUFNO0lBQ3RDLFVBQVUsRUFBRTtRQUNWLEtBQUssRUFBRSxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEtBQUssRUFBRSxLQUFLLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQztRQUNsRCxHQUFHLEVBQUUsQ0FBQyxNQUEyQixFQUFFLEVBQUU7WUFDbkMsMkJBQTJCO1lBQzNCLGtEQUFrRDtZQUNsRCxJQUFJLE1BQU0sSUFBSSxPQUFPLE1BQU0sS0FBSyxRQUFRLEVBQUUsQ0FBQztnQkFDekMsTUFBTSxDQUFDLFlBQVksR0FBRyxXQUFXLENBQUM7Z0JBQ2xDLE1BQU0sQ0FBQyxPQUFPLEdBQUcsY0FBYyxDQUFDO2dCQUNoQyxvREFBb0Q7Z0JBQ3BELE1BQU0sV0FBVyxHQUFHLEtBQUssQ0FBQyxPQUFPLENBQUMsV0FBVyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUM7Z0JBQ3hELElBQUksV0FBVyxFQUFFLENBQUM7b0JBQ2hCLE1BQU0sV0FBVyxHQUFHLFdBQVcsQ0FBQyxXQUFXLEVBQUUsQ0FBQztvQkFDOUMsSUFBSSxXQUFXLElBQUksV0FBVyxDQUFDLE9BQU8sRUFBRSxDQUFDO3dCQUN2QyxNQUFNLENBQUMsUUFBUSxHQUFHLFdBQVcsQ0FBQyxPQUFPLENBQUM7d0JBQ3RDLE1BQU0sQ0FBQyxPQUFPLEdBQUcsV0FBVyxDQUFDLE1BQU0sQ0FBQztvQkFDdEMsQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztZQUNELE9BQU8sTUFBTSxDQUFDO1FBQ2hCLENBQUM7S0FDRjtJQUNELFNBQVMsRUFBRSxHQUFHLEVBQUUsQ0FBQyxpQkFBaUIsSUFBSSxJQUFJLENBQUMsSUFBSSxDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUMsV0FBVyxFQUFFLEdBQUc7SUFDdkUsNkZBQTZGO0lBQzdGLHlFQUF5RTtJQUN6RSw0RkFBNEY7Q0FDN0YsQ0FBQyxDQUFDO0FBRUgsZUFBZSxzQkFBc0IsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBwaW5vIGZyb20gJ3Bpbm8nO1xuaW1wb3J0IHsgdHJhY2UsIGNvbnRleHQgYXMgb3RlbENvbnRleHQgfSBmcm9tICdAb3BlbnRlbGVtZXRyeS9hcGknO1xuXG5jb25zdCBzZXJ2aWNlTmFtZSA9IHByb2Nlc3MuZW52Lk9URUxfU0VSVklDRV9OQU1FIHx8ICdmdW5jdGlvbnMtc2VydmljZSc7IC8vIE9yIGEgbW9yZSBzcGVjaWZpYyBuYW1lIGlmIHByZWZlcnJlZFxuY29uc3Qgc2VydmljZVZlcnNpb24gPSBwcm9jZXNzLmVudi5PVEVMX1NFUlZJQ0VfVkVSU0lPTiB8fCAnMS4wLjAnO1xuXG5jb25zdCBmdW5jdGlvbnNTZXJ2aWNlTG9nZ2VyID0gcGlubyh7XG4gIGxldmVsOiBwcm9jZXNzLmVudi5MT0dfTEVWRUwgfHwgJ2luZm8nLFxuICBmb3JtYXR0ZXJzOiB7XG4gICAgbGV2ZWw6IChsYWJlbCkgPT4gKHsgbGV2ZWw6IGxhYmVsLnRvVXBwZXJDYXNlKCkgfSksXG4gICAgbG9nOiAob2JqZWN0OiBSZWNvcmQ8c3RyaW5nLCBhbnk+KSA9PiB7XG4gICAgICAvLyBFeHBsaWNpdGx5IHR5cGUgJ29iamVjdCdcbiAgICAgIC8vIEVuc3VyZSBvYmplY3QgaXMgbm90IHVuZGVmaW5lZCBhbmQgaXMgYW4gb2JqZWN0XG4gICAgICBpZiAob2JqZWN0ICYmIHR5cGVvZiBvYmplY3QgPT09ICdvYmplY3QnKSB7XG4gICAgICAgIG9iamVjdC5zZXJ2aWNlX25hbWUgPSBzZXJ2aWNlTmFtZTtcbiAgICAgICAgb2JqZWN0LnZlcnNpb24gPSBzZXJ2aWNlVmVyc2lvbjtcbiAgICAgICAgLy8gQWRkIE9wZW5UZWxlbWV0cnkgdHJhY2UgYW5kIHNwYW4gSURzIGlmIGF2YWlsYWJsZVxuICAgICAgICBjb25zdCBjdXJyZW50U3BhbiA9IHRyYWNlLmdldFNwYW4ob3RlbENvbnRleHQuYWN0aXZlKCkpO1xuICAgICAgICBpZiAoY3VycmVudFNwYW4pIHtcbiAgICAgICAgICBjb25zdCBzcGFuQ29udGV4dCA9IGN1cnJlbnRTcGFuLnNwYW5Db250ZXh0KCk7XG4gICAgICAgICAgaWYgKHNwYW5Db250ZXh0ICYmIHNwYW5Db250ZXh0LnRyYWNlSWQpIHtcbiAgICAgICAgICAgIG9iamVjdC50cmFjZV9pZCA9IHNwYW5Db250ZXh0LnRyYWNlSWQ7XG4gICAgICAgICAgICBvYmplY3Quc3Bhbl9pZCA9IHNwYW5Db250ZXh0LnNwYW5JZDtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIHJldHVybiBvYmplY3Q7XG4gICAgfSxcbiAgfSxcbiAgdGltZXN0YW1wOiAoKSA9PiBgLFwidGltZXN0YW1wXCI6XCIke25ldyBEYXRlKERhdGUubm93KCkpLnRvSVNPU3RyaW5nKCl9XCJgLFxuICAvLyBQcmV0dHkgcHJpbnQgZm9yIGxvY2FsIGRldmVsb3BtZW50IGNhbiBiZSBhY2hpZXZlZCBieSBwaXBpbmcgb3V0cHV0LCBlLmcuLCBgfCBwaW5vLXByZXR0eWBcbiAgLy8gT3IgYnkgY29uZGl0aW9uYWxseSBhZGRpbmcgcGluby1wcmV0dHkgdHJhbnNwb3J0IGlmIG5vdCBpbiBwcm9kdWN0aW9uOlxuICAvLyB0cmFuc3BvcnQ6IHByb2Nlc3MuZW52Lk5PREVfRU5WICE9PSAncHJvZHVjdGlvbicgPyB7IHRhcmdldDogJ3Bpbm8tcHJldHR5JyB9IDogdW5kZWZpbmVkLFxufSk7XG5cbmV4cG9ydCBkZWZhdWx0IGZ1bmN0aW9uc1NlcnZpY2VMb2dnZXI7XG4iXX0=