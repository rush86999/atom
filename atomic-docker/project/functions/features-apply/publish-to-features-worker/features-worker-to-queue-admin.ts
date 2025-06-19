import { Request, Response } from 'express';
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';
import { kafkaFeaturesApplyGroupId, kafkaFeaturesApplyTopic } from '../_libs/constants';
import _ from 'lodash';
import { FeaturesApplyResponse, SkillError } from '../_libs/types'; // Import standardized types

interface SuccessPayload {
    message: string;
    messageId?: string; // Kafka message ID if available and relevant from response
}

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

const publisher = async (req: Request, res: Response<FeaturesApplyResponse<SuccessPayload>>) => {
    // Validate request body
    if (!req.body || _.isEmpty(req.body)) {
        return res.status(400).json({
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Request body cannot be empty.' }
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
            messages: [{ value: JSON.stringify(eventItem) }]
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
                messageId: messageId.toString()
            }
        });

    } catch(e: any) {
        console.error('Failed to publish message to Kafka:', e);
        if (transaction) {
            try {
                await transaction.abort();
            } catch (abortError: any) {
                console.error('Failed to abort Kafka transaction:', abortError);
            }
        }
        return res.status(500).json({
            ok: false,
            error: {
                code: 'KAFKA_PUBLISH_ERROR',
                message: e.message || 'An error occurred while publishing the message to Kafka.',
                details: e.toString()
            }
        });
    } finally {
        if (producer) {
            try {
                await producer.disconnect();
            } catch (disconnectError: any) {
                console.error('Failed to disconnect Kafka producer:', disconnectError);
            }
        }
    }
};
  
  export default publisher
