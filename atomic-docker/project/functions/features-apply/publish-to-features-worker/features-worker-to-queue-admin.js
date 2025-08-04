import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';
import { kafkaFeaturesApplyTopic, } from '../_libs/constants';
import _ from 'lodash';
const kafka = new Kafka({
    logLevel: logLevel.ERROR, // Changed to ERROR to reduce verbosity, DEBUG is very noisy
    brokers: [`kafka1:29092`], // Consider making brokers configurable via env vars
    clientId: `atomic-features-apply-admin-publisher-${ip.address()}`, // More specific client ID
    sasl: {
        mechanism: 'plain',
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
    },
});
const publisher = async (req, res) => {
    // Validate request body
    if (!req.body || _.isEmpty(req.body)) {
        return res.status(400).json({
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Request body cannot be empty.',
            },
        });
    }
    const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
    let transaction;
    try {
        await producer.connect();
        transaction = await producer.transaction();
        const eventItem = req.body; // This is the payload to send
        const response = await transaction.send({
            topic: kafkaFeaturesApplyTopic,
            messages: [{ value: JSON.stringify(eventItem) }],
        });
        // The offset management part seems overly complex for a simple publisher
        // and might be better handled by Kafka's consumer group mechanics or specific admin tasks.
        // For a publisher, successfully sending is often enough.
        // If explicit offset management for the producer side is needed, it implies a more complex Kafka interaction pattern.
        // For now, simplifying by focusing on the send operation.
        // const admin = kafka.admin();
        // await admin.connect();
        // const partitions = await admin.fetchOffsets({ groupId: kafkaFeaturesApplyGroupId, topics: [kafkaFeaturesApplyTopic] });
        // console.log('Fetched partitions for offset commit:', partitions);
        // await admin.disconnect();
        // if (partitions?.[0]?.partitions) {
        //     await transaction.sendOffsets({
        //         consumerGroupId: kafkaFeaturesApplyGroupId, // This seems like consumer group logic in producer
        //         topics: [{ topic: kafkaFeaturesApplyTopic, partitions: partitions[0].partitions }]
        //     });
        // } else {
        //     console.warn("No partitions found to send offsets for, this might be an issue if exactly-once semantics across producer/consumer are manually managed this way.");
        // }
        await transaction.commit();
        const messageId = response?.[0]?.baseOffset || 'N/A'; // Example: Get message offset if available
        console.log(`Message successfully added to queue topic ${kafkaFeaturesApplyTopic}. Message ID/Offset: ${messageId}`);
        return res.status(202).json({
            ok: true,
            data: {
                message: 'Successfully published message to features worker queue.',
                messageId: messageId.toString(),
            },
        });
    }
    catch (e) {
        console.error('Failed to publish message to Kafka:', e);
        if (transaction) {
            try {
                await transaction.abort();
            }
            catch (abortError) {
                console.error('Failed to abort Kafka transaction:', abortError);
            }
        }
        return res.status(500).json({
            ok: false,
            error: {
                code: 'KAFKA_PUBLISH_ERROR',
                message: e.message ||
                    'An error occurred while publishing the message to Kafka.',
                details: e.toString(),
            },
        });
    }
    finally {
        if (producer) {
            try {
                await producer.disconnect();
            }
            catch (disconnectError) {
                console.error('Failed to disconnect Kafka producer:', disconnectError);
            }
        }
    }
};
export default publisher;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZmVhdHVyZXMtd29ya2VyLXRvLXF1ZXVlLWFkbWluLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZmVhdHVyZXMtd29ya2VyLXRvLXF1ZXVlLWFkbWluLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLE1BQU0sU0FBUyxDQUFDO0FBQzFDLE9BQU8sRUFBRSxNQUFNLElBQUksQ0FBQztBQUNwQixPQUFPLEVBRUwsdUJBQXVCLEdBQ3hCLE1BQU0sb0JBQW9CLENBQUM7QUFDNUIsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBUXZCLE1BQU0sS0FBSyxHQUFHLElBQUksS0FBSyxDQUFDO0lBQ3RCLFFBQVEsRUFBRSxRQUFRLENBQUMsS0FBSyxFQUFFLDREQUE0RDtJQUN0RixPQUFPLEVBQUUsQ0FBQyxjQUFjLENBQUMsRUFBRSxvREFBb0Q7SUFDL0UsUUFBUSxFQUFFLHlDQUF5QyxFQUFFLENBQUMsT0FBTyxFQUFFLEVBQUUsRUFBRSwwQkFBMEI7SUFDN0YsSUFBSSxFQUFFO1FBQ0osU0FBUyxFQUFFLE9BQU87UUFDbEIsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYztRQUNwQyxRQUFRLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjO0tBQ3JDO0NBQ0YsQ0FBQyxDQUFDO0FBRUgsTUFBTSxTQUFTLEdBQUcsS0FBSyxFQUNyQixHQUFZLEVBQ1osR0FBb0QsRUFDcEQsRUFBRTtJQUNGLHdCQUF3QjtJQUN4QixJQUFJLENBQUMsR0FBRyxDQUFDLElBQUksSUFBSSxDQUFDLENBQUMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDO1FBQ3JDLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGtCQUFrQjtnQkFDeEIsT0FBTyxFQUFFLCtCQUErQjthQUN6QztTQUNGLENBQUMsQ0FBQztJQUNMLENBQUM7SUFFRCxNQUFNLFFBQVEsR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLEVBQUUsbUJBQW1CLEVBQUUsQ0FBQyxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsQ0FBQyxDQUFDO0lBQzlFLElBQUksV0FBVyxDQUFDO0lBRWhCLElBQUksQ0FBQztRQUNILE1BQU0sUUFBUSxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ3pCLFdBQVcsR0FBRyxNQUFNLFFBQVEsQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUUzQyxNQUFNLFNBQVMsR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDLENBQUMsOEJBQThCO1FBRTFELE1BQU0sUUFBUSxHQUFHLE1BQU0sV0FBVyxDQUFDLElBQUksQ0FBQztZQUN0QyxLQUFLLEVBQUUsdUJBQXVCO1lBQzlCLFFBQVEsRUFBRSxDQUFDLEVBQUUsS0FBSyxFQUFFLElBQUksQ0FBQyxTQUFTLENBQUMsU0FBUyxDQUFDLEVBQUUsQ0FBQztTQUNqRCxDQUFDLENBQUM7UUFFSCx5RUFBeUU7UUFDekUsMkZBQTJGO1FBQzNGLHlEQUF5RDtRQUN6RCxzSEFBc0g7UUFDdEgsMERBQTBEO1FBQzFELCtCQUErQjtRQUMvQix5QkFBeUI7UUFDekIsMEhBQTBIO1FBQzFILG9FQUFvRTtRQUNwRSw0QkFBNEI7UUFDNUIscUNBQXFDO1FBQ3JDLHNDQUFzQztRQUN0QywwR0FBMEc7UUFDMUcsNkZBQTZGO1FBQzdGLFVBQVU7UUFDVixXQUFXO1FBQ1gseUtBQXlLO1FBQ3pLLElBQUk7UUFFSixNQUFNLFdBQVcsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUUzQixNQUFNLFNBQVMsR0FBRyxRQUFRLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxVQUFVLElBQUksS0FBSyxDQUFDLENBQUMsMkNBQTJDO1FBQ2pHLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNkNBQTZDLHVCQUF1Qix3QkFBd0IsU0FBUyxFQUFFLENBQ3hHLENBQUM7UUFFRixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLEVBQUUsRUFBRSxJQUFJO1lBQ1IsSUFBSSxFQUFFO2dCQUNKLE9BQU8sRUFBRSwwREFBMEQ7Z0JBQ25FLFNBQVMsRUFBRSxTQUFTLENBQUMsUUFBUSxFQUFFO2FBQ2hDO1NBQ0YsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxxQ0FBcUMsRUFBRSxDQUFDLENBQUMsQ0FBQztRQUN4RCxJQUFJLFdBQVcsRUFBRSxDQUFDO1lBQ2hCLElBQUksQ0FBQztnQkFDSCxNQUFNLFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUM1QixDQUFDO1lBQUMsT0FBTyxVQUFlLEVBQUUsQ0FBQztnQkFDekIsT0FBTyxDQUFDLEtBQUssQ0FBQyxvQ0FBb0MsRUFBRSxVQUFVLENBQUMsQ0FBQztZQUNsRSxDQUFDO1FBQ0gsQ0FBQztRQUNELE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLHFCQUFxQjtnQkFDM0IsT0FBTyxFQUNMLENBQUMsQ0FBQyxPQUFPO29CQUNULDBEQUEwRDtnQkFDNUQsT0FBTyxFQUFFLENBQUMsQ0FBQyxRQUFRLEVBQUU7YUFDdEI7U0FDRixDQUFDLENBQUM7SUFDTCxDQUFDO1lBQVMsQ0FBQztRQUNULElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixJQUFJLENBQUM7Z0JBQ0gsTUFBTSxRQUFRLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDOUIsQ0FBQztZQUFDLE9BQU8sZUFBb0IsRUFBRSxDQUFDO2dCQUM5QixPQUFPLENBQUMsS0FBSyxDQUFDLHNDQUFzQyxFQUFFLGVBQWUsQ0FBQyxDQUFDO1lBQ3pFLENBQUM7UUFDSCxDQUFDO0lBQ0gsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsU0FBUyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCB7IEthZmthLCBsb2dMZXZlbCB9IGZyb20gJ2thZmthanMnO1xuaW1wb3J0IGlwIGZyb20gJ2lwJztcbmltcG9ydCB7XG4gIGthZmthRmVhdHVyZXNBcHBseUdyb3VwSWQsXG4gIGthZmthRmVhdHVyZXNBcHBseVRvcGljLFxufSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7IEZlYXR1cmVzQXBwbHlSZXNwb25zZSwgU2tpbGxFcnJvciB9IGZyb20gJy4uL19saWJzL3R5cGVzJzsgLy8gSW1wb3J0IHN0YW5kYXJkaXplZCB0eXBlc1xuXG5pbnRlcmZhY2UgU3VjY2Vzc1BheWxvYWQge1xuICBtZXNzYWdlOiBzdHJpbmc7XG4gIG1lc3NhZ2VJZD86IHN0cmluZzsgLy8gS2Fma2EgbWVzc2FnZSBJRCBpZiBhdmFpbGFibGUgYW5kIHJlbGV2YW50IGZyb20gcmVzcG9uc2Vcbn1cblxuY29uc3Qga2Fma2EgPSBuZXcgS2Fma2Eoe1xuICBsb2dMZXZlbDogbG9nTGV2ZWwuRVJST1IsIC8vIENoYW5nZWQgdG8gRVJST1IgdG8gcmVkdWNlIHZlcmJvc2l0eSwgREVCVUcgaXMgdmVyeSBub2lzeVxuICBicm9rZXJzOiBbYGthZmthMToyOTA5MmBdLCAvLyBDb25zaWRlciBtYWtpbmcgYnJva2VycyBjb25maWd1cmFibGUgdmlhIGVudiB2YXJzXG4gIGNsaWVudElkOiBgYXRvbWljLWZlYXR1cmVzLWFwcGx5LWFkbWluLXB1Ymxpc2hlci0ke2lwLmFkZHJlc3MoKX1gLCAvLyBNb3JlIHNwZWNpZmljIGNsaWVudCBJRFxuICBzYXNsOiB7XG4gICAgbWVjaGFuaXNtOiAncGxhaW4nLFxuICAgIHVzZXJuYW1lOiBwcm9jZXNzLmVudi5LQUZLQV9VU0VSTkFNRSxcbiAgICBwYXNzd29yZDogcHJvY2Vzcy5lbnYuS0FGS0FfUEFTU1dPUkQsXG4gIH0sXG59KTtcblxuY29uc3QgcHVibGlzaGVyID0gYXN5bmMgKFxuICByZXE6IFJlcXVlc3QsXG4gIHJlczogUmVzcG9uc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPFN1Y2Nlc3NQYXlsb2FkPj5cbikgPT4ge1xuICAvLyBWYWxpZGF0ZSByZXF1ZXN0IGJvZHlcbiAgaWYgKCFyZXEuYm9keSB8fCBfLmlzRW1wdHkocmVxLmJvZHkpKSB7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1JlcXVlc3QgYm9keSBjYW5ub3QgYmUgZW1wdHkuJyxcbiAgICAgIH0sXG4gICAgfSk7XG4gIH1cblxuICBjb25zdCBwcm9kdWNlciA9IGthZmthLnByb2R1Y2VyKHsgbWF4SW5GbGlnaHRSZXF1ZXN0czogMSwgaWRlbXBvdGVudDogdHJ1ZSB9KTtcbiAgbGV0IHRyYW5zYWN0aW9uO1xuXG4gIHRyeSB7XG4gICAgYXdhaXQgcHJvZHVjZXIuY29ubmVjdCgpO1xuICAgIHRyYW5zYWN0aW9uID0gYXdhaXQgcHJvZHVjZXIudHJhbnNhY3Rpb24oKTtcblxuICAgIGNvbnN0IGV2ZW50SXRlbSA9IHJlcS5ib2R5OyAvLyBUaGlzIGlzIHRoZSBwYXlsb2FkIHRvIHNlbmRcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgdHJhbnNhY3Rpb24uc2VuZCh7XG4gICAgICB0b3BpYzoga2Fma2FGZWF0dXJlc0FwcGx5VG9waWMsXG4gICAgICBtZXNzYWdlczogW3sgdmFsdWU6IEpTT04uc3RyaW5naWZ5KGV2ZW50SXRlbSkgfV0sXG4gICAgfSk7XG5cbiAgICAvLyBUaGUgb2Zmc2V0IG1hbmFnZW1lbnQgcGFydCBzZWVtcyBvdmVybHkgY29tcGxleCBmb3IgYSBzaW1wbGUgcHVibGlzaGVyXG4gICAgLy8gYW5kIG1pZ2h0IGJlIGJldHRlciBoYW5kbGVkIGJ5IEthZmthJ3MgY29uc3VtZXIgZ3JvdXAgbWVjaGFuaWNzIG9yIHNwZWNpZmljIGFkbWluIHRhc2tzLlxuICAgIC8vIEZvciBhIHB1Ymxpc2hlciwgc3VjY2Vzc2Z1bGx5IHNlbmRpbmcgaXMgb2Z0ZW4gZW5vdWdoLlxuICAgIC8vIElmIGV4cGxpY2l0IG9mZnNldCBtYW5hZ2VtZW50IGZvciB0aGUgcHJvZHVjZXIgc2lkZSBpcyBuZWVkZWQsIGl0IGltcGxpZXMgYSBtb3JlIGNvbXBsZXggS2Fma2EgaW50ZXJhY3Rpb24gcGF0dGVybi5cbiAgICAvLyBGb3Igbm93LCBzaW1wbGlmeWluZyBieSBmb2N1c2luZyBvbiB0aGUgc2VuZCBvcGVyYXRpb24uXG4gICAgLy8gY29uc3QgYWRtaW4gPSBrYWZrYS5hZG1pbigpO1xuICAgIC8vIGF3YWl0IGFkbWluLmNvbm5lY3QoKTtcbiAgICAvLyBjb25zdCBwYXJ0aXRpb25zID0gYXdhaXQgYWRtaW4uZmV0Y2hPZmZzZXRzKHsgZ3JvdXBJZDoga2Fma2FGZWF0dXJlc0FwcGx5R3JvdXBJZCwgdG9waWNzOiBba2Fma2FGZWF0dXJlc0FwcGx5VG9waWNdIH0pO1xuICAgIC8vIGNvbnNvbGUubG9nKCdGZXRjaGVkIHBhcnRpdGlvbnMgZm9yIG9mZnNldCBjb21taXQ6JywgcGFydGl0aW9ucyk7XG4gICAgLy8gYXdhaXQgYWRtaW4uZGlzY29ubmVjdCgpO1xuICAgIC8vIGlmIChwYXJ0aXRpb25zPy5bMF0/LnBhcnRpdGlvbnMpIHtcbiAgICAvLyAgICAgYXdhaXQgdHJhbnNhY3Rpb24uc2VuZE9mZnNldHMoe1xuICAgIC8vICAgICAgICAgY29uc3VtZXJHcm91cElkOiBrYWZrYUZlYXR1cmVzQXBwbHlHcm91cElkLCAvLyBUaGlzIHNlZW1zIGxpa2UgY29uc3VtZXIgZ3JvdXAgbG9naWMgaW4gcHJvZHVjZXJcbiAgICAvLyAgICAgICAgIHRvcGljczogW3sgdG9waWM6IGthZmthRmVhdHVyZXNBcHBseVRvcGljLCBwYXJ0aXRpb25zOiBwYXJ0aXRpb25zWzBdLnBhcnRpdGlvbnMgfV1cbiAgICAvLyAgICAgfSk7XG4gICAgLy8gfSBlbHNlIHtcbiAgICAvLyAgICAgY29uc29sZS53YXJuKFwiTm8gcGFydGl0aW9ucyBmb3VuZCB0byBzZW5kIG9mZnNldHMgZm9yLCB0aGlzIG1pZ2h0IGJlIGFuIGlzc3VlIGlmIGV4YWN0bHktb25jZSBzZW1hbnRpY3MgYWNyb3NzIHByb2R1Y2VyL2NvbnN1bWVyIGFyZSBtYW51YWxseSBtYW5hZ2VkIHRoaXMgd2F5LlwiKTtcbiAgICAvLyB9XG5cbiAgICBhd2FpdCB0cmFuc2FjdGlvbi5jb21taXQoKTtcblxuICAgIGNvbnN0IG1lc3NhZ2VJZCA9IHJlc3BvbnNlPy5bMF0/LmJhc2VPZmZzZXQgfHwgJ04vQSc7IC8vIEV4YW1wbGU6IEdldCBtZXNzYWdlIG9mZnNldCBpZiBhdmFpbGFibGVcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBNZXNzYWdlIHN1Y2Nlc3NmdWxseSBhZGRlZCB0byBxdWV1ZSB0b3BpYyAke2thZmthRmVhdHVyZXNBcHBseVRvcGljfS4gTWVzc2FnZSBJRC9PZmZzZXQ6ICR7bWVzc2FnZUlkfWBcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAyKS5qc29uKHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YToge1xuICAgICAgICBtZXNzYWdlOiAnU3VjY2Vzc2Z1bGx5IHB1Ymxpc2hlZCBtZXNzYWdlIHRvIGZlYXR1cmVzIHdvcmtlciBxdWV1ZS4nLFxuICAgICAgICBtZXNzYWdlSWQ6IG1lc3NhZ2VJZC50b1N0cmluZygpLFxuICAgICAgfSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHB1Ymxpc2ggbWVzc2FnZSB0byBLYWZrYTonLCBlKTtcbiAgICBpZiAodHJhbnNhY3Rpb24pIHtcbiAgICAgIHRyeSB7XG4gICAgICAgIGF3YWl0IHRyYW5zYWN0aW9uLmFib3J0KCk7XG4gICAgICB9IGNhdGNoIChhYm9ydEVycm9yOiBhbnkpIHtcbiAgICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIGFib3J0IEthZmthIHRyYW5zYWN0aW9uOicsIGFib3J0RXJyb3IpO1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4gcmVzLnN0YXR1cyg1MDApLmpzb24oe1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0tBRktBX1BVQkxJU0hfRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgIGUubWVzc2FnZSB8fFxuICAgICAgICAgICdBbiBlcnJvciBvY2N1cnJlZCB3aGlsZSBwdWJsaXNoaW5nIHRoZSBtZXNzYWdlIHRvIEthZmthLicsXG4gICAgICAgIGRldGFpbHM6IGUudG9TdHJpbmcoKSxcbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gZmluYWxseSB7XG4gICAgaWYgKHByb2R1Y2VyKSB7XG4gICAgICB0cnkge1xuICAgICAgICBhd2FpdCBwcm9kdWNlci5kaXNjb25uZWN0KCk7XG4gICAgICB9IGNhdGNoIChkaXNjb25uZWN0RXJyb3I6IGFueSkge1xuICAgICAgICBjb25zb2xlLmVycm9yKCdGYWlsZWQgdG8gZGlzY29ubmVjdCBLYWZrYSBwcm9kdWNlcjonLCBkaXNjb25uZWN0RXJyb3IpO1xuICAgICAgfVxuICAgIH1cbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgcHVibGlzaGVyO1xuIl19