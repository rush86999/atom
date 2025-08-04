import { Request, Response } from 'express';
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';
import { ScheduleAssistWithMeetingQueueBodyType } from '@schedule_assist/_libs/types/scheduleMeetingWorker/types';
import {
  kafkaScheduleAssistGroupId,
  kafkaScheduleAssistTopic,
} from '../_libs/constants';

const kafka = new Kafka({
  logLevel: logLevel.DEBUG,
  brokers: [`kafka1:29092`],
  clientId: 'atomic',
  // ssl: true,
  sasl: {
    mechanism: 'plain', // scram-sha-256 or scram-sha-512
    username: process.env.KAFKA_USERNAME,
    password: process.env.KAFKA_PASSWORD,
  },
});

const publisher = async (req: Request, res: Response) => {
  const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
  await producer.connect();

  const transaction = await producer.transaction();
  try {
    const eventItem: ScheduleAssistWithMeetingQueueBodyType = req.body;

    const response = await transaction.send({
      topic: kafkaScheduleAssistTopic,
      messages: [{ value: JSON.stringify(eventItem) }],
    });

    const admin = kafka.admin();

    await admin.connect();
    const partitions = await admin.fetchOffsets({
      groupId: kafkaScheduleAssistGroupId,
      topics: [kafkaScheduleAssistTopic],
    });
    console.log(partitions);
    await admin.disconnect();

    await transaction.sendOffsets({
      consumerGroupId: kafkaScheduleAssistGroupId,
      topics: [
        {
          topic: kafkaScheduleAssistTopic,
          partitions: partitions?.[0]?.partitions,
        },
      ],
    });

    await transaction.commit();

    console.log(
      response,
      ' response successfully added to queue inside features-worker-queue-admin'
    );

    res.status(202).send('succesfully created day schedule');
  } catch (e) {
    console.log(e, ' unable to process message');

    await transaction.abort();
    res.status(400).json(e);
  }
};

export default publisher;
