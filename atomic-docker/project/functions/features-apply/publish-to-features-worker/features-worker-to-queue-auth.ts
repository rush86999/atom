import { Request, Response } from 'express';
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';
import { kafkaFeaturesApplyGroupId, kafkaFeaturesApplyTopic } from '../_libs/constants';
import _ from 'lodash';
import { FeaturesApplyResponse, SkillError } from '../_libs/types'; // Import standardized types

interface SuccessPayload {
    message: string;
    messageId?: string;
}

const kafka = new Kafka({
    logLevel: logLevel.ERROR, // Changed to ERROR
    brokers: [`kafka1:29092`], // Consider making brokers configurable
    clientId: `atomic-features-apply-auth-publisher-${ip.address()}`, // More specific client ID
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
    // Additional validation for specific fields if this endpoint expects a certain structure
    // For example, if it's for Hasura Event Triggers, check for event.data.new or event.data.old
    if (!req.body.event || !req.body.event.data || (!req.body.event.data.new && !req.body.event.data.old)) {
        return res.status(400).json({
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Invalid Hasura event trigger payload structure.' }
        });
    }


    const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
    let transaction;

    try {
        await producer.connect();
        transaction = await producer.transaction();
  
        const eventItem = req.body;
  
        const response = await transaction.send({
            topic: kafkaFeaturesApplyTopic,
            messages: [{ value: JSON.stringify(eventItem) }]
        });

        // Simplified: Removed complex offset management from publisher side
        await transaction.commit();

        const messageId = response?.[0]?.baseOffset || 'N/A';
        console.log(`Message successfully added to queue topic ${kafkaFeaturesApplyTopic} by auth-publisher. Message ID/Offset: ${messageId}`);

        return res.status(202).json({
            ok: true,
            data: {
                message: 'Successfully published message to features worker queue (auth).',
                messageId: messageId.toString()
            }
        });

    } catch(e: any) {
        console.error('Failed to publish message to Kafka (auth-publisher):', e);
        if (transaction) {
            try {
                await transaction.abort();
            } catch (abortError: any) {
                console.error('Failed to abort Kafka transaction (auth-publisher):', abortError);
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
                console.error('Failed to disconnect Kafka producer (auth-publisher):', disconnectError);
            }
        }
    }
};


export default publisher

