import { Request, Response } from 'express';

import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import { streamToString } from '@post_process_calendar/_libs/api-helper';
import {
  bucketName,
  kafkaPostProcessCalGroupId,
  kafkaPostProcessCalTopic,
} from '@post_process_calendar/_libs/constants';
import {
  S3Client,
  GetObjectCommand,
  DeleteObjectCommand,
  PutObjectCommand,
} from '@aws-sdk/client-s3';

import { Readable } from 'stream';
import { GetOptaPlanBodyForCalendarType } from '@post_process_calendar/_libs/types/onPostOptaCal/types';
import {
  EventPlannerResponseBodyType,
  OnOptaPlanBodyType,
  TimeSlotType,
  UserPlannerRequestBodyType,
  WorkerS3PayloadType,
} from '@post_process_calendar/_libs/types'; // Added WorkerS3PayloadType
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

// Set the AWS Region.
const s3Client = new S3Client({
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY,
    secretAccessKey: process.env.S3_SECRET_KEY,
  },
  endpoint: process.env.S3_ENDPOINT,
  forcePathStyle: true,
});

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

const processGetOpaPlanBody = async (
  body: GetOptaPlanBodyForCalendarType, // This is the initial S3 payload content
  optaPlanSolution: OnOptaPlanBodyType // This is the direct body from OptaPlanner's callback
) => {
  const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
  await producer.connect();

  const transaction = await producer.transaction();
  try {
    // Extract data from the initial S3 payload (body)
    const {
      singletonId,
      // hostId: initialHostId, // hostId from initial payload might differ from OptaPlanner's solution hostId, prefer solution's
      allEvents,
      hostTimezone,
      newHostBufferTimes,
      newHostReminders,
      breaks,
      oldEvents,
      oldAttendeeEvents,
      isReplan, // New field
      originalGoogleEventId, // New field
      originalCalendarId, // New field
    } = body;

    // Extract data from OptaPlanner's solution
    const {
      timeslotList,
      userList,
      eventPartList,
      score,
      fileKey, // This is the key of the S3 object OptaPlanner read (initial payload key)
      hostId, // This is the hostId OptaPlanner used/returned in its solution
    } = optaPlanSolution;

    /**
     * TODO:
     * 1. get the opta plan
     * 2. if hard score != 0 recurse until 5 times (This is complex, for now, just check score once)
     * 3. still hard score != 0 send message to queue
     * 4. if hard score == 0, send message to queue
     */

    // Construct the S3 payload for the worker
    const workerPayload: WorkerS3PayloadType = {
      eventPartList,
      userList,
      timeslotList,
      score,
      fileKey, // Pass the original fileKey that OptaPlanner reported
      hostId, // Pass the hostId from OptaPlanner's solution
      singletonId, // From initial S3 payload
      allEvents,
      hostTimezone,
      newHostBufferTimes,
      newHostReminders,
      breaks,
      oldEvents,
      oldAttendeeEvents,
      isReplan,
      originalGoogleEventId,
      originalCalendarId,
    };

    const workerS3Key = `${hostId}/${singletonId}_processed.json`; // New S3 key for worker payload

    const params = {
      Body: JSON.stringify(workerPayload),
      Bucket: bucketName,
      Key: workerS3Key, // Use the new key
      ContentType: 'application/json',
    };

    const s3Command = new PutObjectCommand(params);

    const s3Response = await s3Client.send(s3Command);
    console.log(s3Response, ' s3Response for worker payload');

    const response = await transaction.send({
      topic: kafkaPostProcessCalTopic,
      messages: [{ value: JSON.stringify({ fileKey: workerS3Key }) }], // Point Kafka to the new S3 object
    });

    const admin = kafka.admin();

    await admin.connect();
    const partitions = await admin.fetchOffsets({
      groupId: kafkaPostProcessCalGroupId,
      topics: [kafkaPostProcessCalTopic],
    });
    console.log(partitions);
    await admin.disconnect();

    await transaction.sendOffsets({
      consumerGroupId: kafkaPostProcessCalGroupId,
      topics: [
        {
          topic: kafkaPostProcessCalTopic,
          partitions: partitions?.[0]?.partitions,
        },
      ],
    });

    await transaction.commit();

    console.log(
      response,
      ' response successfully added to queue inside publishToCalendarQueue'
    );
  } catch (e) {
    console.log(e, ' processCalendarForOptaPlanner');
  }
};

const handler = async (req: Request, res: Response) => {
  try {
    console.log(req, ' event');
    // hasura trigger
    const bodyOptaPlan: OnOptaPlanBodyType = req.body; // This is the direct payload from OptaPlanner
    console.log(bodyOptaPlan, ' bodyOptaPlan from OptaPlanner callback');

    const { score, fileKey, hostId: optaHostId } = bodyOptaPlan; // fileKey here is the key of the *initial* S3 payload

    // --- Score Check ---
    if (score) {
      const scoreParts = score.split('/');
      const hardScoreMatch = scoreParts[0].match(/(-?\d+)hard/);
      if (hardScoreMatch && hardScoreMatch[1]) {
        const hardScoreValue = parseInt(hardScoreMatch[1], 10);
        if (hardScoreValue < 0) {
          // Must read singletonId from the initial S3 payload for logging.
          // The fileKey from OptaPlanner callback IS the key to the initial S3 payload.
          let initialSingletonId = 'UNKNOWN_SINGLETON_ID';
          try {
            const initialS3GetCommand = new GetObjectCommand({
              Bucket: bucketName,
              Key: fileKey,
            });
            const initialS3GetCommandOutput =
              await s3Client.send(initialS3GetCommand);
            const initialBodyString = await streamToString(
              initialS3GetCommandOutput.Body as Readable
            );
            const initialS3Body: GetOptaPlanBodyForCalendarType =
              JSON.parse(initialBodyString);
            initialSingletonId =
              initialS3Body.singletonId || initialSingletonId;
          } catch (s3Error) {
            console.error(
              `Error reading initial S3 payload ${fileKey} for logging singletonId:`,
              s3Error
            );
          }

          console.error(
            `OptaPlanner solution for fileKey: ${fileKey}, singletonId: ${initialSingletonId} has a negative hard score (${hardScoreValue}). Aborting processing.`
          );
          // It's important to delete the initial S3 file if it's no longer needed, even on failure, to prevent reprocessing or clutter.
          // However, for debugging a hard score failure, one might want to keep it. For now, let's delete.
          try {
            const s3DeleteCmd = new DeleteObjectCommand({
              Bucket: bucketName,
              Key: fileKey,
            });
            await s3Client.send(s3DeleteCmd);
            console.log(
              `Deleted initial S3 object ${fileKey} after negative hard score.`
            );
          } catch (deleteError) {
            console.error(
              `Failed to delete initial S3 object ${fileKey} after negative hard score:`,
              deleteError
            );
          }
          return res
            .status(200)
            .json({
              message:
                'Acknowledged OptaPlanner callback. Negative hard score, solution not processed.',
            });
        }
      } else {
        console.warn(
          `Could not parse hard score from score string: ${score}. Proceeding with processing.`
        );
      }
    } else {
      console.warn(
        'OptaPlanner solution score is null or undefined. Proceeding with processing.'
      );
    }
    // --- End Score Check ---

    if (!optaHostId) {
      // hostId from OptaPlanner's solution payload
      throw new Error('hostId from OptaPlanner solution is not provided');
    }

    if (!fileKey) {
      // fileKey of the initial S3 data object
      throw new Error('no fileKey found in OptaPlanner solution');
    }

    // The rest of the parameters from OptaPlanner's solution (timeslotList, eventPartList, userList)
    // are validated inside processGetOpaPlanBody or by its usage.

    console.log(`Initial S3 fileKey from OptaPlanner: ${fileKey}`);
    const s3GetCommand = new GetObjectCommand({
      Bucket: bucketName,
      Key: fileKey, // fileKey is the key to the *initial* S3 payload
    });

    const s3GetCommandOutput = await s3Client.send(s3GetCommand);
    const bodyString = await streamToString(
      s3GetCommandOutput.Body as Readable
    );
    const initialS3PayloadBody: GetOptaPlanBodyForCalendarType =
      JSON.parse(bodyString);
    console.log(initialS3PayloadBody, ' initialS3PayloadBody content from S3');

    // Now that we have processed the initial S3 payload, delete it.
    const s3DeleteCommand = new DeleteObjectCommand({
      Bucket: bucketName,
      Key: fileKey,
    });
    const s3DeleteCommandOutput = await s3Client.send(s3DeleteCommand);
    console.log(
      s3DeleteCommandOutput,
      ' s3DeleteCommandOutput for initial S3 payload'
    );

    // Validate required fields from the initial S3 payload
    if (!initialS3PayloadBody?.hostId) {
      // This is hostId from the *original* data generation context
      throw new Error('hostId is required in the initial S3 payload');
    } else if (!initialS3PayloadBody?.singletonId) {
      throw new Error('singletonId is required in the initial S3 payload');
    }
    // eventParts and allEvents from initialS3PayloadBody are more for context if needed by worker,
    // the primary data for calendar update comes from bodyOptaPlan.eventPartList

    await processGetOpaPlanBody(
      initialS3PayloadBody, // Pass the content of the initial S3 payload
      bodyOptaPlan // Pass the direct solution from OptaPlanner
    );
    return res.status(202).json({
      message: 'success',
    });
  } catch (e) {
    console.log(e, ' postProcessCalendarOptaPlan');
    return res.status(400).json({
      message: e.message,
    });
  }
};

export default handler;
